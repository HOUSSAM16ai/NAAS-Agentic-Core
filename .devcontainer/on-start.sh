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

# Ensure Codespaces ports are public.
#
# ISS-MISC-VPN (D-068 second hardening 2026-05-17): if port 3000 stays
# PRIVATE the frontend itself returns HTTP 401 to an unauthenticated browser
# (e.g. the user's phone, or anyone visiting a shared link without GitHub
# auth). The devcontainer.json `portsAttributes.3000.visibility` is the
# permanent durable setting that ships with new Codespaces; the `gh ports
# visibility` calls below are a runtime safety-net that ALSO retro-fixes
# existing Codespaces created before that JSON was updated.
#
# We surface gh failures (instead of swallowing them) so users can see WHY
# their port is still private when something goes wrong (gh not
# authenticated, codespace name missing, etc.).
if command -v gh >/dev/null 2>&1; then
    lifecycle_info "Setting Codespaces port visibility (3000, 5000, 8000, 3001) to public..."
    for port_spec in 3000:public 5000:public 8000:public 3001:public; do
        if ! gh codespace ports visibility "$port_spec" 2>/tmp/gh_ports_err; then
            err_msg=$(cat /tmp/gh_ports_err 2>/dev/null | head -1 || true)
            lifecycle_warn "Could not set $port_spec — ${err_msg:-no error message}"
            lifecycle_warn "  → Open VS Code → PORTS tab → right-click port → Port Visibility → Public"
        fi
    done
    rm -f /tmp/gh_ports_err
else
    lifecycle_warn "gh CLI missing — cannot auto-set Codespaces port visibility."
    lifecycle_warn "  → Manually set port 3000 to Public in VS Code PORTS tab"
    lifecycle_warn "  → Otherwise the frontend returns HTTP 401 to unauthenticated browsers."
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
# Observability stack — now started inline by supervisor.sh as native binaries
# ==============================================================================
# Mission Control (Grafana :3001) and Prometheus (:9090) are launched as
# background processes by supervisor.sh Step 4C, NOT by a separate script.
# The previous start_observability.sh wrapper is retained as a no-op stub
# in case any user docs or muscle-memory still reference it. See §6.17.

# Exit immediately to unblock IDE
exit 0
