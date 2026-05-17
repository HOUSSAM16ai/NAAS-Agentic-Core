#!/usr/bin/env bash
# ISS-MISC-VPN (D-068, hardening pass 2026-05-17): live test for the
# Next.js custom server WS proxy that eliminates the cross-port dependency
# on GitHub Codespaces. Without the proxy, the browser had to talk to port
# 8000 directly — which may be private, blocked by GitHub auth, or simply
# unreachable for some Codespaces. With the proxy, the browser only ever
# touches port 3000 and we relay WS to uvicorn over localhost.
#
# Run: bash scripts/test_nextjs_ws_proxy.sh
# Exit: 0 if all green, 1 otherwise.

set -eu -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

GREEN='\033[32m'
RED='\033[31m'
CYAN='\033[36m'
RESET='\033[0m'

pass=0
fail=0
record() {
    local ok="$1"; shift
    local label="$1"
    if [ "$ok" = "y" ]; then
        printf "  ${GREEN}✓${RESET}  %s\n" "$label"
        pass=$((pass+1))
    else
        printf "  ${RED}✗${RESET}  %s\n" "$label"
        fail=$((fail+1))
    fi
}

# ── 1. Static checks ───────────────────────────────────────────────────────
printf "${CYAN}── 1. Static checks ──${RESET}\n"

if [ -f "$ROOT/frontend/server.js" ]; then
    record y "frontend/server.js exists"
else
    record n "frontend/server.js MISSING — the custom server is the primary fix"
fi

if grep -q '"dev": "node server.js"' "$ROOT/frontend/package.json"; then
    record y 'package.json "dev" script invokes node server.js'
else
    record n 'package.json "dev" no longer uses the custom server'
fi

if grep -q "PROXIED_WS_PATTERN" "$ROOT/frontend/server.js" && \
   grep -q "/api/chat/ws" "$ROOT/frontend/server.js"; then
    record y "server.js proxies /api/chat/ws"
else
    record n "server.js does not proxy /api/chat/ws"
fi

if grep -q "isCloudForwardedHostname" "$ROOT/frontend/app/hooks/useAgentSocket.js"; then
    record y "useAgentSocket prefers same-origin on cloud-forwarded hostnames"
else
    record n "useAgentSocket no longer detects cloud-forwarded hostnames"
fi

# server.js MUST honor `--port N` so supervisor.sh's existing CLI shape
# (`npm run dev -- --hostname 0.0.0.0 --port 3000`) keeps working.
if grep -q "getCliFlag" "$ROOT/frontend/server.js"; then
    record y "server.js honors --port / --hostname CLI flags (supervisor.sh compat)"
else
    record n "server.js no longer parses --port CLI flag — supervisor.sh would run on the wrong port"
fi

# devcontainer.json port 3000 MUST be public. If it isn't, the phone gets
# HTTP 401 from GitHub auth and the chat UI never even loads.
if grep -A4 '"3000"' "$ROOT/.devcontainer/devcontainer.json" | grep -q '"visibility": *"public"'; then
    record y "devcontainer.json declares port 3000 visibility=public"
else
    record n "devcontainer.json: port 3000 is NOT public — phone browsers get HTTP 401 without VPN"
fi

# ── 2. Live WS smoke (skipped in plain CI without node_modules) ────────────
printf "\n${CYAN}── 2. Live WS smoke (requires node_modules + python3) ──${RESET}\n"

if [ ! -d "$ROOT/frontend/node_modules" ]; then
    record y "node_modules not present — skipping live smoke (static checks above)"
    printf "\n%d/%d pass\n" "$pass" "$((pass+fail))"
    exit "$fail"
fi

# Boot the same backend the integration test uses.
if [ -f /tmp/live_test_cors.py ]; then
    : # Reuse the existing helper.
else
    # Minimal inline backend matching the production middleware stack.
    cat > /tmp/live_test_cors.py <<'PY'
import os, sys
os.environ.setdefault("CODESPACES", "true")
os.environ.setdefault("CODESPACE_NAME", "my-cs")
os.environ.setdefault("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-pipeline-secure-length")
os.environ.setdefault("ENVIRONMENT", "development")
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
sys.path.insert(0, os.environ.get("REPO_ROOT", "/home/user/NAAS-Agentic-Core"))
from app.core.settings.base import AppSettings
s = AppSettings()
app = FastAPI()
cors = {"allow_origins": s.BACKEND_CORS_ORIGINS, "allow_credentials": True,
        "allow_methods": ["*"], "allow_headers": ["*"]}
if s.BACKEND_CORS_ORIGIN_REGEX: cors["allow_origin_regex"] = s.BACKEND_CORS_ORIGIN_REGEX
app.add_middleware(TrustedHostMiddleware, allowed_hosts=s.ALLOWED_HOSTS)
app.add_middleware(CORSMiddleware, **cors)

@app.get("/health")
def h(): return {"status":"ok"}

@app.websocket("/api/chat/ws")
async def chat(ws: WebSocket):
    await ws.accept(subprotocol="jwt")
    await ws.send_json({"type": "conversation_init", "payload": {"conversation_id": 1}})
    await ws.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")
PY
fi

cleanup() {
    [ -n "${UVP:-}" ] && kill "$UVP" 2>/dev/null || true
    [ -n "${SRVP:-}" ] && kill "$SRVP" 2>/dev/null || true
}
trap cleanup EXIT

REPO_ROOT="$ROOT" python3 /tmp/live_test_cors.py > /tmp/uv.log 2>&1 &
UVP=$!
sleep 2

cd "$ROOT/frontend"
PORT=3001 BACKEND_PORT=8765 NEXT_TELEMETRY_DISABLED=1 nohup node server.js \
    > /tmp/serverjs.log 2>&1 &
SRVP=$!
for _ in $(seq 1 15); do
    if grep -q "ready on\|next-ws-proxy" /tmp/serverjs.log 2>/dev/null; then
        break
    fi
    sleep 1
done

# HTTP probe — Next.js serves frontend
code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:3001/)
if [ "$code" = "200" ]; then record y "Next.js serves frontend (HTTP 200)"
else                          record n "Next.js HTTP failed (got $code)"
fi

# WS probe — same-origin via custom server proxy
ws_status=$(python3 - <<'PY' 2>&1
import asyncio, websockets, sys
async def t():
    try:
        async with websockets.connect("ws://127.0.0.1:3001/api/chat/ws",
                                      subprotocols=["jwt"]) as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)
            print("ok")
    except Exception as e:
        print(f"fail:{type(e).__name__}")
asyncio.run(t())
PY
)
if [ "$ws_status" = "ok" ]; then
    record y "Same-origin WS proxy (browser→3001→uvicorn:8765) — connection upgraded"
else
    record n "Same-origin WS proxy failed: $ws_status"
fi

# WS probe — cross-port fallback (direct to uvicorn) still works
ws2_status=$(python3 - <<'PY' 2>&1
import asyncio, websockets
async def t():
    try:
        async with websockets.connect("ws://127.0.0.1:8765/api/chat/ws",
                                      subprotocols=["jwt"]) as ws:
            await asyncio.wait_for(ws.recv(), timeout=2)
            print("ok")
    except Exception as e:
        print(f"fail:{type(e).__name__}")
asyncio.run(t())
PY
)
if [ "$ws2_status" = "ok" ]; then
    record y "Cross-port fallback WS (direct to uvicorn) — still works"
else
    record n "Cross-port fallback failed: $ws2_status"
fi

printf "\n${CYAN}═══════════════════════════════════════${RESET}\n"
printf "%d/%d pass\n" "$pass" "$((pass+fail))"
exit "$fail"
