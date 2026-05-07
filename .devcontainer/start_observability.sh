#!/usr/bin/env bash
###############################################################################
# start_observability.sh — STATUS CHECKER (post-§6.17)
#
# Mission Control (Grafana + Prometheus) is now started by supervisor.sh as
# NATIVE binaries baked into the Dockerfile. The Docker-compose-based stack
# this script used to launch is retired (see CLAUDE.md §6.13/§6.16/§6.17).
#
# This script is kept as a thin compatibility shim so users / docs / muscle
# memory pointing at it still get useful output. It does NOT start anything.
#
# To restart Mission Control: kill the grafana-server / prometheus processes
# and re-run supervisor.sh, or rebuild the container.
###############################################################################

set -uo pipefail

readonly REPO_ROOT="${REPO_ROOT:-/app}"
readonly OBS_DIR="${REPO_ROOT}/.observability"

cat <<EOF
════════════════════════════════════════════════════════════════════
🛰️  Mission Control — Native Binary Mode (post-§6.17)
════════════════════════════════════════════════════════════════════

This script no longer launches the observability stack — the supervisor
(.devcontainer/supervisor.sh) now starts Grafana + Prometheus as native
processes in Step 4C. No Docker required. See CLAUDE.md §6.17.

EOF

# ---- Status probe ---------------------------------------------------------
if pgrep -f "/opt/grafana/bin/grafana-server" >/dev/null 2>&1; then
    echo "✅ Grafana process: RUNNING"
else
    echo "❌ Grafana process: NOT RUNNING"
fi

if pgrep -f "/opt/prometheus/prometheus" >/dev/null 2>&1; then
    echo "✅ Prometheus process: RUNNING"
else
    echo "❌ Prometheus process: NOT RUNNING"
fi

# ---- Listener probe -------------------------------------------------------
if command -v curl >/dev/null 2>&1; then
    if curl -fsS -o /dev/null --max-time 2 "http://localhost:3001/api/health" 2>/dev/null; then
        echo "✅ Grafana HTTP   : http://localhost:3001/  (HEALTHY)"
    else
        echo "⏳ Grafana HTTP   : not yet healthy on :3001"
    fi
    if curl -fsS -o /dev/null --max-time 2 "http://localhost:9090/-/ready" 2>/dev/null; then
        echo "✅ Prometheus HTTP: http://localhost:9090/  (READY)"
    else
        echo "⏳ Prometheus HTTP: not yet ready on :9090"
    fi
fi

# ---- Public URL ----------------------------------------------------------
if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    public_url="https://${CODESPACE_NAME}-3001.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"
elif [ -n "${CODESPACE_NAME:-}" ]; then
    public_url="https://${CODESPACE_NAME}-3001.preview.app.github.dev/"
else
    public_url="http://localhost:3001/"
fi

echo ""
echo "🌐 Public URL: ${public_url}"
echo "📝 Logs     :"
echo "   Grafana   : tail -f ${OBS_DIR}/grafana.log"
echo "   Prometheus: tail -f ${OBS_DIR}/prometheus.log"
echo "   Launch    : tail -f ${OBS_DIR}/launch.log"
echo ""
echo "═════════════════════════════════════════════════════════════════"

exit 0
