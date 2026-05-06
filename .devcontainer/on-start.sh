#!/usr/bin/env bash
###############################################################################
# on-start.sh - DevContainer Post-Start Hook (v2.0)
#
# يُنفَّذ في كل مرة تبدأ فيها الحاوية
# Executed every time the container starts
#
# المسؤوليات (Responsibilities):
#   1. إطلاق المشرف في الخلفية
#   2. الخروج فوراً لإلغاء حظر IDE
#   3. تسجيل معلومات الحالة
#
# المبادئ (Principles):
#   - Non-Blocking: Exit immediately after launching background process
#   - Idempotent: Safe to run multiple times
#   - Observable: All output logged to file
#   - Fail Safe: Errors don't block IDE
#
# الإصدار (Version): 2.0.0
# التاريخ (Date): 2025-12-31
###############################################################################

set -Eeuo pipefail

# ==============================================================================
# INITIALIZATION (التهيئة)
# ==============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly APP_ROOT="/app"
readonly SUPERVISOR_SCRIPT="$SCRIPT_DIR/supervisor.sh"
readonly LOG_FILE="$APP_ROOT/.superhuman_bootstrap.log"

cd "$APP_ROOT"

# Load core library
if [ -f "$SCRIPT_DIR/lib/lifecycle_core.sh" ]; then
    source "$SCRIPT_DIR/lib/lifecycle_core.sh"
else
    echo "ERROR: lifecycle_core.sh not found" >&2
    exit 1
fi

lifecycle_info "═══════════════════════════════════════════════════════"
lifecycle_info "🚀 Post-Start Hook: Background Service Launcher"
lifecycle_info "═══════════════════════════════════════════════════════"

# ==============================================================================
# SUPERVISOR LAUNCH (إطلاق المشرف)
# ==============================================================================

# Check if supervisor already running
if lifecycle_has_state "supervisor_running"; then
    supervisor_pid=$(lifecycle_get_state "supervisor_running")
    if kill -0 "$supervisor_pid" 2>/dev/null; then
        lifecycle_info "Supervisor already running (PID: $supervisor_pid)"
        lifecycle_info "Logs: tail -f $LOG_FILE"
        exit 0
    else
        lifecycle_warn "Stale supervisor PID found, cleaning up..."
        lifecycle_clear_state "supervisor_running"
    fi
fi

# Verify supervisor script exists
if [ ! -f "$SUPERVISOR_SCRIPT" ]; then
    lifecycle_error "Supervisor script not found: $SUPERVISOR_SCRIPT"
    exit 1
fi

# Launch supervisor in background
lifecycle_info "Launching background supervisor..."

# Use nohup to detach from terminal and redirect all output
nohup bash "$SUPERVISOR_SCRIPT" > "$LOG_FILE" 2>&1 &
SUPERVISOR_PID=$!

# Ensure Codespaces ports are public when gh CLI is available
if command -v gh >/dev/null 2>&1; then
    lifecycle_info "Setting Codespaces port visibility (8000, 3000) to public..."
    gh codespace ports visibility 8000:public >/dev/null 2>&1 || true
    gh codespace ports visibility 3000:public >/dev/null 2>&1 || true
fi

# Save supervisor PID
lifecycle_set_state "supervisor_running" "$SUPERVISOR_PID"
lifecycle_set_state "supervisor_started_at" "$(date +%s)"

# ==============================================================================
# USER INFORMATION (معلومات المستخدم)
# ==============================================================================

lifecycle_info "═══════════════════════════════════════════════════════"
lifecycle_info "✅ Background Supervisor Launched"
lifecycle_info "   PID: $SUPERVISOR_PID"
lifecycle_info "   Logs: tail -f $LOG_FILE"
lifecycle_info ""
lifecycle_info "⏳ Application Startup Timeline:"
lifecycle_info "   • Dependencies: ~10-15 seconds"
lifecycle_info "   • Migrations: ~5-10 seconds"
lifecycle_info "   • Server Launch: ~5-10 seconds"
lifecycle_info "   • Health Check: ~5-10 seconds"
lifecycle_info "   • Total: ~30-45 seconds"
lifecycle_info ""
lifecycle_info "🌐 Access Application:"
lifecycle_info "   • Wait for 'Application is healthy' message"
lifecycle_info "   • Backend API: http://localhost:8000"
lifecycle_info "   • Next.js UI: http://localhost:3000"
lifecycle_info ""
lifecycle_info "🔍 Monitor Progress:"
lifecycle_info "   tail -f $LOG_FILE"
lifecycle_info "═══════════════════════════════════════════════════════"

# ==============================================================================
# Observability Stack — auto-start in background (Codespaces only by default)
# ==============================================================================
# Wakes Grafana + Prometheus + Loki + Tempo + OTel Collector.
# Resource-guarded (refuses under 1.5 GB free RAM). Non-blocking, logs to
# .observability/boot.log. Disable explicitly:
#   export OBSERVABILITY_AUTOSTART=0
if [ -x "$(dirname "${BASH_SOURCE[0]}")/start_observability.sh" ]; then
    nohup bash "$(dirname "${BASH_SOURCE[0]}")/start_observability.sh" \
        >/dev/null 2>&1 < /dev/null &
    lifecycle_info ""
    lifecycle_info "📊 Observability stack starting in background..."
    lifecycle_info "   Mission Control: http://localhost:3001/  (Grafana — port 3001)"
    lifecycle_info "   Logs:           tail -f .observability/boot.log"
fi

# Exit immediately to unblock IDE
exit 0
