#!/usr/bin/env bash
###############################################################################
# on-attach.sh - DevContainer Post-Attach Hook (v2.0)
#
# يُنفَّذ عند إرفاق IDE بالحاوية
# Executed when IDE attaches to the container
#
# المسؤوليات (Responsibilities):
#   1. عرض حالة النظام
#   2. إظهار معلومات الوصول
#   3. تقديم أوامر مفيدة
#
# المبادئ (Principles):
#   - Informational Only: No execution, just display
#   - Fast: < 1 second
#   - User-Friendly: Clear, actionable information
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
readonly LOG_FILE="$APP_ROOT/.superhuman_bootstrap.log"
readonly APP_PORT="${PORT:-8000}"

cd "$APP_ROOT"

# Load core library
if [ -f "$SCRIPT_DIR/lib/lifecycle_core.sh" ]; then
    source "$SCRIPT_DIR/lib/lifecycle_core.sh"
else
    echo "⚠️  Warning: lifecycle_core.sh not found"
fi

# ==============================================================================
# STATUS DISPLAY (عرض الحالة)
# ==============================================================================

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "🎯 CogniForge Development Environment"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Check application status
if lifecycle_check_http "http://localhost:$APP_PORT/health" 200 2>/dev/null; then
    echo "✅ Application Status: ${COLOR_GREEN}HEALTHY${COLOR_RESET}"
    echo "   🌐 Access: http://localhost:$APP_PORT"
    echo ""
else
    echo "⏳ Application Status: ${COLOR_YELLOW}STARTING${COLOR_RESET}"
    echo "   📝 Monitor: tail -f $LOG_FILE"
    echo "   ⏱️  Expected: 30-45 seconds from container start"
    echo ""
fi

# System information
echo "📊 System Information:"
echo "   • Python: $(python --version 2>/dev/null | cut -d' ' -f2 || echo 'N/A')"
echo "   • Working Directory: $(pwd)"
echo "   • Container: $(hostname)"
echo ""

# Useful commands
echo "🔧 Useful Commands:"
echo "   • View logs:        tail -f $LOG_FILE"
echo "   • Check health:     curl http://localhost:$APP_PORT/health"
echo "   • Restart app:      pkill -f uvicorn && bash .devcontainer/supervisor.sh"
echo "   • Run tests:        pytest tests/"
echo "   • Check processes:  ps aux | grep python"
echo ""

# State information (if available)
if command -v lifecycle_has_state >/dev/null 2>&1; then
    if lifecycle_has_state "app_ready"; then
        echo "🎉 All systems operational!"
    else
        echo "⏳ System is initializing..."
        echo "   Check $LOG_FILE for progress"
    fi
    echo ""
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "💡 Tip: Wait for 'Application is healthy' message before accessing"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# ── Mission Control (Grafana :3001) status banner ────────────────────
# Mirrors the 8000/3000 health-check experience for the observability stack.
# Three states: HEALTHY (HTTP 200), STARTING (boot.log fresh, no answer yet),
# OFFLINE (no boot.log → start_observability.sh did not run, likely missing
# docker-in-docker feature).
echo "🛰️  Mission Control (Grafana — port 3001):"
GRAFANA_URL_LOCAL="http://localhost:3001/api/health"
if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    GRAFANA_URL_PUBLIC="https://${CODESPACE_NAME}-3001.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"
elif [ -n "${CODESPACE_NAME:-}" ]; then
    GRAFANA_URL_PUBLIC="https://${CODESPACE_NAME}-3001.app.github.dev/"
else
    GRAFANA_URL_PUBLIC="http://localhost:3001/"
fi

if curl -fsS -o /dev/null --max-time 2 "${GRAFANA_URL_LOCAL}" 2>/dev/null; then
    echo "   ✅ Status: HEALTHY"
    echo "   🌐 URL   : ${GRAFANA_URL_PUBLIC}"
elif [ -f "$APP_ROOT/.observability/boot.log" ]; then
    last_log_age=$(($(date +%s) - $(stat -c %Y "$APP_ROOT/.observability/boot.log" 2>/dev/null || echo 0)))
    if [ "${last_log_age}" -lt 180 ]; then
        echo "   ⏳ Status: STARTING (Docker is booting + pulling images)"
        echo "   🌐 URL   : ${GRAFANA_URL_PUBLIC}  (will auto-open within ~30-90s)"
        echo "   📝 Tail  : tail -f $APP_ROOT/.observability/boot.log"
    else
        echo "   ⚠️  Status: STALE — last boot attempt was $((last_log_age / 60))m ago"
        echo "   🔧 Re-run: bash .devcontainer/start_observability.sh"
        echo "   📝 Tail  : tail -f $APP_ROOT/.observability/boot.log"
    fi
else
    echo "   ❌ Status: OFFLINE (Docker likely not installed)"
    echo "   🔧 Fix   : devcontainer.json must include feature 'docker-in-docker:2'."
    echo "             Then run 'Codespaces: Rebuild Container'."
    echo "   📝 Detail: see CLAUDE.md §6.13 + .superhuman_bootstrap.log"
fi
echo ""

# ── Runtime observability snapshot (non-blocking, informational) ──
# Refresh `.runtime/*` artifacts so the truth table reflects the tree at
# attach time. Drift is reported but does not fail the attach hook.
# Hard cap of 30s (kill -9 if it ever stalls — shouldn't, since the
# script does only static analysis).
if [ -x "$SCRIPT_DIR/snapshot_runtime.sh" ]; then
    echo "📊 Runtime Snapshot:"
    timeout 30s bash "$SCRIPT_DIR/snapshot_runtime.sh" 2>&1 | sed 's/^/   /' || true
    echo ""
fi

exit 0
