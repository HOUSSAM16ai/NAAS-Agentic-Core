#!/usr/bin/env bash
# ISS-101 (D-WS-PROXY-001/002) — one-shot: apply the WS fix in a RUNNING Codespace,
# force a FRESH client bundle, and verify — without a full container rebuild.
#
# Usage (in the Codespaces terminal):
#   DIAG_EMAIL=you@example.com DIAG_PASSWORD=xxxx bash scripts/fix_ws_now.sh
#
# Why .next is cleared: in dev, a stale .next cache (or an unreloaded browser tab)
# keeps serving the OLD client JS — so the frontend fixes (heartbeat, auth) never
# load and the kick/flap persists even though the source on disk is new.

set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "==> [1/6] git pull (latest fix)"
git pull origin claude/chat-session-auth-bugs-aLf74 || echo "  (pull skipped/failed — continuing with current code)"

echo "==> [2/6] ensure real 'ws' is installed in frontend"
if (cd frontend && node -e "require('ws').WebSocketServer" >/dev/null 2>&1); then
  echo "  real ws: present"
else
  echo "  real ws: missing — installing…"
  (cd frontend && npm install ws@^8.18.0) || echo "  (ws install failed)"
fi

echo "==> [3/6] confirm server.js is the NEW ws-library proxy"
if grep -q "loadWs\|ws-lib\|next/dist/compiled/ws" frontend/server.js; then
  echo "  server.js on disk: NEW (ws-lib) ✅"
else
  echo "  server.js on disk: OLD (http-proxy) ❌ — git pull did not update it!"
fi

echo "==> [4/6] restart frontend + CLEAR stale build cache (force fresh client JS)"
pkill -f "node .*server.js" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 2
# نزع كاش البناء بالكامل — يضمن أن المتصفح سيحصل على JS الجديد بعد إعادة التحميل.
rm -rf frontend/.next 2>/dev/null || true
(cd frontend && PORT="${FRONTEND_PORT:-5000}" HOSTNAME=0.0.0.0 nohup npm run dev > /tmp/frontend_iss101.log 2>&1 &)
echo "  waiting for frontend + warming compile (fresh build can take ~30-60s)…"
sleep 18
# دفعة تجميع: أول طلب يُجبر Next على إعادة بناء الـ client bundle.
curl -s -m 60 -o /dev/null "http://127.0.0.1:${FRONTEND_PORT:-5000}/" 2>/dev/null || true
sleep 6
echo "  ----- frontend startup log (tail) -----"
tail -25 /tmp/frontend_iss101.log 2>/dev/null || true
if grep -q "WS-PROXY ISS-101 ws-lib v2 ACTIVE" /tmp/frontend_iss101.log 2>/dev/null; then
  echo "  ✅ NEW instrumented ws-lib proxy is RUNNING (server side)"
else
  echo "  ❌ NEW proxy banner NOT found — startup error (see log above)"
fi

echo "==> [5/6] verify backend path (section F should show [proxy:5000] OK answered)"
python scripts/diagnose_chat.py || true

echo "==> [6/6] BROWSER CHECK — which client JS is loaded?"
echo "  أعد فتح التطبيق في تبويب جديد تماماً (أغلق كل التبويبات القديمة)، أرسل سؤالاً،"
echo "  ثم عُد وشغّل:   tail -40 /tmp/frontend_iss101.log"
echo ""
echo "  ----- recent client connections (build + close codes) -----"
grep -E "client connected \(build=|client closed code=" /tmp/frontend_iss101.log 2>/dev/null | tail -20 || echo "  (no client connections yet — open the app first)"
echo ""
echo "  ➜ build=D-WS-PROXY-002  → المتصفح يُشغّل الكود الجديد ✅"
echo "  ➜ build=UNKNOWN(old-bundle?)  أو  client closed code=1001  → المتصفح يُشغّل JS قديماً:"
echo "     أغلق التبويب تماماً + امسح كاش الموقع (أو افتح نافذة خاصة جديدة) ثم أعد المحاولة."
