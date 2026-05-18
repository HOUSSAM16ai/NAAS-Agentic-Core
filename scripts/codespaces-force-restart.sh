#!/usr/bin/env bash
# ISS-MISC-VPN (D-068) — one-shot force-restart for CogniForge on Codespaces.
#
# Usage (on the Codespace terminal):
#     bash scripts/codespaces-force-restart.sh
#
# This script does the EXACT sequence a user needs after they pull the fix
# branch and discover their old `next dev` is still running. It:
#   1. Verifies they're on the fix branch (errors out if still on `main`).
#   2. Kills every `next dev` / `node server.js` / uvicorn process.
#   3. Forces port 3000 + 8000 visibility = public via gh (best-effort).
#   4. Re-runs `bash .devcontainer/supervisor.sh` which now invokes
#      `node server.js` (the WS-proxying custom server, D-068 hardening 1).
#
# When it returns, `/cogniforge-proxy-status` on the public URL should
# answer with JSON ok=true, and the chat status will flip to "متصل".

set -u -o pipefail

GREEN=$'\033[32m'
RED=$'\033[31m'
YELLOW=$'\033[33m'
CYAN=$'\033[36m'
RESET=$'\033[0m'

say()   { printf '%s\n' "$@"; }
green() { printf '%s%s%s\n' "$GREEN" "$*" "$RESET"; }
red()   { printf '%s%s%s\n' "$RED" "$*" "$RESET"; }
yel()   { printf '%s%s%s\n' "$YELLOW" "$*" "$RESET"; }
hdr()   { printf '\n%s── %s ──%s\n' "$CYAN" "$*" "$RESET"; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

hdr "1. Branch check"
branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "?")
say "  Current branch: $branch"
if ! grep -q "translateCloudHostnameToBackend" frontend/app/hooks/useAgentSocket.js 2>/dev/null; then
    red  "  ✗ The fix code is NOT present in this checkout."
    red  "    You are likely on 'main' — switch first:"
    say  ""
    say  "      git fetch origin claude/fix-vpn-connection-status-fj2Lm"
    say  "      git checkout claude/fix-vpn-connection-status-fj2Lm"
    say  "      bash scripts/codespaces-force-restart.sh"
    say  ""
    exit 2
fi
if [ ! -f frontend/server.js ]; then
    red  "  ✗ frontend/server.js missing — the fix branch isn't fully checked out."
    exit 2
fi
green "  ✓ fix code present (useAgentSocket.translateCloudHostnameToBackend + server.js)"

hdr "2. Kill all stale frontend / backend / mission-control processes"
for pat in "next dev" "node server.js" "uvicorn app.main:app" "grafana-server" "prometheus" "npm run dev"; do
    pids=$(pgrep -f "$pat" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        yel  "  killing  '$pat' (PIDs: $pids)"
        kill $pids 2>/dev/null || true
    fi
done
sleep 2
for pat in "next dev" "node server.js" "uvicorn app.main:app"; do
    pids=$(pgrep -f "$pat" 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
done
green "  ✓ stale processes cleared"

hdr "3. Force port visibility = public (Codespaces)"
if command -v gh >/dev/null 2>&1; then
    for port_spec in 3000:public 5000:public 8000:public 3001:public; do
        if gh codespace ports visibility "$port_spec" >/tmp/gh.err 2>&1; then
            green "  ✓ $port_spec"
        else
            yel  "  ⚠ $port_spec — $(cat /tmp/gh.err | head -1)"
            yel  "    Manual fallback: VS Code → PORTS tab → right-click port → Port Visibility → Public"
        fi
    done
else
    yel  "  ⚠ gh CLI missing — set ports public manually via VS Code PORTS tab"
fi

hdr "4. Launch supervisor (uvicorn + Next.js custom server)"
nohup bash .devcontainer/supervisor.sh >/tmp/supervisor-restart.log 2>&1 &
SUP_PID=$!
green "  ✓ supervisor launched (PID $SUP_PID) — tailing /tmp/supervisor-restart.log for 25s"
sleep 25

hdr "5. Verify the fix is live"
# Probe Next.js custom server
node_ok="no"
for try in 1 2 3 4 5; do
    if curl -sf -m 3 http://127.0.0.1:3000/cogniforge-proxy-status >/tmp/proxy.json 2>/dev/null; then
        node_ok="yes"; break
    fi
    sleep 3
done
if [ "$node_ok" = "yes" ]; then
    green "  ✓ /cogniforge-proxy-status (port 3000):"
    cat /tmp/proxy.json
    echo
else
    red   "  ✗ /cogniforge-proxy-status not answering yet — supervisor may still be compiling."
    red   "    tail /tmp/supervisor-restart.log  for details."
fi
# Probe uvicorn
if curl -sf -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
    green "  ✓ uvicorn /health (port 8000) answering"
else
    yel   "  ⚠ uvicorn not yet up — give it 30 more seconds (DB warmup)"
fi

hdr "DONE"
say "  Open the public URL on your phone:"
if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
    say  "      https://${CODESPACE_NAME}-3000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"
    say  "      https://${CODESPACE_NAME}-3000.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/cogniforge-proxy-status"
else
    say  "      https://<codespace-name>-3000.app.github.dev/"
fi
say  ""
say  "  Status indicator should now be 'متصل' — no VPN required."
