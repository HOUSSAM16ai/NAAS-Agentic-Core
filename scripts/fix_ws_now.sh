#!/usr/bin/env bash
# ISS-101 (D-WS-PROXY-001) — one-shot: apply the WS-proxy fix in a RUNNING Codespace
# and verify it, without a full container rebuild.
#
# Usage (in the Codespaces terminal):
#   DIAG_EMAIL=you@example.com DIAG_PASSWORD=xxxx bash scripts/fix_ws_now.sh
#
# It: pulls the branch, ensures real `ws`, restarts the frontend (server.js) so the
# NEW ws-library proxy is the running process, then runs the diagnostic. Section F
# should now show [proxy:5000] OK answered (instead of close=1006).

set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "==> [1/5] git pull (latest fix)"
git pull origin claude/chat-session-auth-bugs-aLf74 || echo "  (pull skipped/failed — continuing with current code)"

echo "==> [2/5] ensure real 'ws' is installed in frontend"
if (cd frontend && node -e "require('ws').WebSocketServer" >/dev/null 2>&1); then
  echo "  real ws: present"
else
  echo "  real ws: missing — installing…"
  (cd frontend && npm install ws@^8.18.0) || echo "  (ws install failed)"
fi

echo "==> [3/5] confirm server.js is the NEW ws-library proxy"
if grep -q "loadWs\|ws-lib\|next/dist/compiled/ws" frontend/server.js; then
  echo "  server.js on disk: NEW (ws-lib) ✅"
else
  echo "  server.js on disk: OLD (http-proxy) ❌ — git pull did not update it!"
fi

echo "==> [4/5] restart frontend (kill stale server.js, start new)"
pkill -f "node .*server.js" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 2
rm -f frontend/.next/dev/lock 2>/dev/null || true
(cd frontend && PORT="${FRONTEND_PORT:-5000}" HOSTNAME=0.0.0.0 nohup npm run dev > /tmp/frontend_iss101.log 2>&1 &)
echo "  waiting for frontend to come up…"
sleep 14
echo "  ----- frontend startup log (tail) -----"
tail -25 /tmp/frontend_iss101.log 2>/dev/null || true
echo "  ----- which proxy is running? -----"
if grep -q "WS-PROXY ISS-101 ws-lib v2 ACTIVE" /tmp/frontend_iss101.log 2>/dev/null; then
  echo "  ✅ NEW instrumented ws-lib proxy is RUNNING"
else
  echo "  ❌ NEW proxy banner NOT found — old code or a startup error (see log above)"
fi

echo "==> [5/5] verify (section F should show [proxy:5000] OK answered)"
python scripts/diagnose_chat.py
