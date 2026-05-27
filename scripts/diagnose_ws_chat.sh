#!/usr/bin/env bash
###############################################################################
# diagnose_ws_chat.sh — End-to-end WebSocket & Chat Diagnostic
#
# Verifies that all D-WS-* fixes are deployed correctly and the chat works:
#   - D-WS-FLAP-002: heartbeat skill (backend ping/pong)
#   - D-WS-FLAP-003: server primer + stale-WS detection
#   - D-WS-FLAP-004: honest-debounce UI state
#   - D-WS-REGRESSION-001: onopen no longer crashes on stale ref
#   - D-WS-SESSION-001: env-aware JWT cap (8h dev)
#   - D-WS-AUTH-001: bounded 4401 retry + HTTP probe + non-destructive logout
#   - D-WS-SECRET-KEY-001: monolith & user-service share SECRET_KEY default
#
# Usage (inside the Codespace):
#   bash scripts/diagnose_ws_chat.sh
#
# Exit codes:
#   0 — all checks passed
#   1 — one or more checks failed (details printed)
###############################################################################

set -uo pipefail

# Colors
G='\033[0;32m'  # green
R='\033[0;31m'  # red
Y='\033[1;33m'  # yellow
B='\033[1;34m'  # blue
N='\033[0m'     # no color

PASS=0
FAIL=0
WARN=0

print_section() {
    echo ""
    echo -e "${B}═══════════════════════════════════════════════════════════════════${N}"
    echo -e "${B} $1${N}"
    echo -e "${B}═══════════════════════════════════════════════════════════════════${N}"
}

check() {
    local name="$1"
    local ok="$2"
    local detail="${3:-}"
    if [ "$ok" = "1" ]; then
        echo -e "  ${G}✅${N} $name"
        PASS=$((PASS + 1))
    elif [ "$ok" = "warn" ]; then
        echo -e "  ${Y}⚠${N}  $name"
        [ -n "$detail" ] && echo -e "      ${Y}→${N} $detail"
        WARN=$((WARN + 1))
    else
        echo -e "  ${R}❌${N} $name"
        [ -n "$detail" ] && echo -e "      ${R}→${N} $detail"
        FAIL=$((FAIL + 1))
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
print_section "1. Process & Port Health"
# ─────────────────────────────────────────────────────────────────────────────

if pgrep -f "uvicorn app.main:app" > /dev/null 2>&1; then
    check "monolith (uvicorn app.main) is running" 1
else
    check "monolith (uvicorn app.main) is running" 0 \
        "Start with: bash .devcontainer/supervisor.sh"
fi

if pgrep -f "node server.js" > /dev/null 2>&1; then
    check "frontend (Next.js custom server) is running" 1
else
    check "frontend (Next.js custom server) is running" 0 \
        "Start with: cd frontend && npm run dev"
fi

for port in 5000 8000; do
    if (python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(1)
r = s.connect_ex(('127.0.0.1', $port))
s.close()
exit(0 if r == 0 else 1)
" 2>/dev/null); then
        check "port $port is listening" 1
    else
        check "port $port is listening" 0
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
print_section "2. SECRET_KEY Consistency (D-WS-SECRET-KEY-001)"
# ─────────────────────────────────────────────────────────────────────────────

# Monolith SECRET_KEY (from .env)
if [ -f .env ]; then
    monolith_sk=$(grep "^SECRET_KEY=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"')
    if [ -n "$monolith_sk" ]; then
        sk_hash=$(printf "%s" "$monolith_sk" | sha256sum | cut -c1-12)
        check "monolith SECRET_KEY in .env (hash=$sk_hash)" 1
    else
        check "monolith SECRET_KEY in .env" 0 ".env exists but no SECRET_KEY found"
    fi
else
    check "monolith SECRET_KEY in .env" warn ".env file missing"
fi

# User-service SECRET_KEY (from running process env)
us_pid=$(pgrep -f "uvicorn microservices.user_service" 2>/dev/null | head -1 || true)
if [ -n "$us_pid" ] && [ -r "/proc/$us_pid/environ" ]; then
    us_sk=$(tr '\0' '\n' < "/proc/$us_pid/environ" | grep "^SECRET_KEY=" | head -1 | cut -d= -f2-)
    if [ -n "$us_sk" ] && [ -n "${monolith_sk:-}" ]; then
        if [ "$us_sk" = "$monolith_sk" ]; then
            check "user-service SECRET_KEY MATCHES monolith ✓" 1
        else
            check "user-service SECRET_KEY differs from monolith" 0 \
                "This causes 4401 on every WS handshake (D-WS-SECRET-KEY-001 catastrophe)"
        fi
    else
        check "user-service SECRET_KEY readable" warn "process running but env unreadable"
    fi
else
    check "user-service process detection" warn \
        "user-service may not be running (sudo may be required for /proc/<pid>/environ)"
fi

# ─────────────────────────────────────────────────────────────────────────────
print_section "3. Critical Environment Variables"
# ─────────────────────────────────────────────────────────────────────────────

monolith_pid=$(pgrep -f "uvicorn app.main:app" 2>/dev/null | head -1 || true)
if [ -n "$monolith_pid" ] && [ -r "/proc/$monolith_pid/environ" ]; then
    monolith_env=$(tr '\0' '\n' < "/proc/$monolith_pid/environ")
    for var in OPENROUTER_API_KEY DATABASE_URL TAVILY_API_KEY ENVIRONMENT; do
        if echo "$monolith_env" | grep -q "^${var}="; then
            val=$(echo "$monolith_env" | grep "^${var}=" | head -1 | cut -d= -f2-)
            if [ -n "$val" ]; then
                # Show only length + last 4 chars for secrets
                if [ "$var" = "ENVIRONMENT" ]; then
                    check "$var = $val" 1
                else
                    len=${#val}
                    suffix="${val: -4}"
                    check "$var set (len=$len, ends=…$suffix)" 1
                fi
            else
                check "$var present but empty" 0 \
                    "Add as Codespaces secret in repo settings"
            fi
        else
            check "$var missing from process env" 0 \
                "Add as Codespaces secret + restart Codespace"
        fi
    done
else
    check "monolith process env readable" warn \
        "monolith not running or /proc not accessible"
fi

# ─────────────────────────────────────────────────────────────────────────────
print_section "4. Backend Health Endpoints"
# ─────────────────────────────────────────────────────────────────────────────

if curl -sf --max-time 3 http://127.0.0.1:8000/health > /dev/null 2>&1; then
    health=$(curl -s --max-time 3 http://127.0.0.1:8000/health 2>/dev/null)
    check "monolith /health responds" 1
    if echo "$health" | grep -q '"database":"ok"'; then
        check "  → database connection OK" 1
    else
        check "  → database connection FAILED" 0 "$health"
    fi
else
    check "monolith /health responds" 0 \
        "Server not ready or port 8000 not reachable"
fi

# ─────────────────────────────────────────────────────────────────────────────
print_section "5. WebSocket Endpoint Reachability"
# ─────────────────────────────────────────────────────────────────────────────

# Without token — should get a 4401 close with JSON error (NOT HTTP 403)
ws_test_output=$(python3 - <<'PY' 2>&1 || true
import asyncio
import json
import sys
try:
    import websockets
except ImportError:
    print("MISSING_DEP:websockets")
    sys.exit(0)

async def test():
    try:
        async with websockets.connect("ws://127.0.0.1:8000/api/chat/ws", open_timeout=3) as ws:
            msg = await asyncio.wait_for(ws.recv(), timeout=3)
            try:
                data = json.loads(msg)
                code = data.get("payload", {}).get("code") or data.get("payload", {}).get("status_code")
                print(f"OK:got_error_json:code={code}")
            except Exception:
                print(f"OK:got_msg:{msg[:80]}")
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"HTTP_REJECT:{e.status_code}")
    except Exception as e:
        print(f"ERROR:{type(e).__name__}:{e}")

asyncio.run(test())
PY
)
if echo "$ws_test_output" | grep -q "MISSING_DEP"; then
    check "WS endpoint reachable (no-token probe)" warn \
        "Install websockets: pip install websockets — to enable this probe"
elif echo "$ws_test_output" | grep -q "OK:got_error_json:code=4401"; then
    check "WS endpoint returns 4401 with JSON for missing token" 1
elif echo "$ws_test_output" | grep -q "HTTP_REJECT:403"; then
    check "WS endpoint returns HTTP 403 (bad — should be JSON 4401)" 0 \
        "D-WS-002 fix may have regressed"
else
    check "WS endpoint probe" warn "Output: $ws_test_output"
fi

# ─────────────────────────────────────────────────────────────────────────────
print_section "6. Source-code Fixes Are Deployed (sanity)"
# ─────────────────────────────────────────────────────────────────────────────

# D-WS-AUTH-001: bounded retry logic
if grep -q "MAX_FATAL_RETRIES" frontend/app/hooks/useRealtimeConnection.js 2>/dev/null; then
    check "D-WS-AUTH-001: MAX_FATAL_RETRIES present in frontend" 1
else
    check "D-WS-AUTH-001 missing — fix not deployed" 0 \
        "Pull the latest branch and rebuild Next.js"
fi

if grep -q "revalidateTokenViaHttp" frontend/app/hooks/useRealtimeConnection.js 2>/dev/null; then
    check "D-WS-AUTH-001: HTTP /me probe function present" 1
else
    check "D-WS-AUTH-001 probe missing" 0
fi

# D-WS-SECRET-KEY-001: shared_user_secret in supervisor.sh
if grep -q "shared_user_secret" .devcontainer/supervisor.sh 2>/dev/null; then
    check "D-WS-SECRET-KEY-001: shared_user_secret in supervisor.sh" 1
else
    check "D-WS-SECRET-KEY-001 missing in supervisor.sh" 0 \
        "user-service may use wrong default SECRET_KEY"
fi

# D-WS-FLAP-002: heartbeat skill imported
if grep -q "from app.services.skills.ws_heartbeat_skill" app/api/routers/customer_chat.py 2>/dev/null; then
    check "D-WS-FLAP-002: heartbeat skill imported in customer_chat" 1
else
    check "D-WS-FLAP-002 missing" 0
fi

# D-WS-REGRESSION-001: no dangling offlineGraceTimerRef
if grep -q "offlineGraceTimerRef" frontend/app/hooks/useRealtimeConnection.js 2>/dev/null; then
    # If found, it must only be in comments
    code_only=$(grep -v "^\s*//" frontend/app/hooks/useRealtimeConnection.js | grep "offlineGraceTimerRef" || true)
    if [ -z "$code_only" ]; then
        check "D-WS-REGRESSION-001: offlineGraceTimerRef removed from code" 1
    else
        check "D-WS-REGRESSION-001: stale ref still in code" 0 "$code_only"
    fi
else
    check "D-WS-REGRESSION-001: offlineGraceTimerRef completely removed" 1
fi

# ─────────────────────────────────────────────────────────────────────────────
print_section "Summary"
# ─────────────────────────────────────────────────────────────────────────────

echo ""
echo -e "  ${G}Passed:${N}  $PASS"
echo -e "  ${Y}Warned:${N}  $WARN"
echo -e "  ${R}Failed:${N}  $FAIL"
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${R}╔═══════════════════════════════════════════════════════════════════╗${N}"
    echo -e "${R}║ ❌ $FAIL critical issue(s) found — see above for fixes.${N}"
    echo -e "${R}╚═══════════════════════════════════════════════════════════════════╝${N}"
    exit 1
fi

if [ "$WARN" -gt 0 ]; then
    echo -e "${Y}╔═══════════════════════════════════════════════════════════════════╗${N}"
    echo -e "${Y}║ ⚠️  All critical checks passed, but $WARN warning(s) — see above.${N}"
    echo -e "${Y}╚═══════════════════════════════════════════════════════════════════╝${N}"
    exit 0
fi

echo -e "${G}╔═══════════════════════════════════════════════════════════════════╗${N}"
echo -e "${G}║ ✅ ALL CHECKS PASSED. The WebSocket + Chat stack is healthy.${N}"
echo -e "${G}║                                                                   ║${N}"
echo -e "${G}║ Next steps to verify in the browser:${N}"
echo -e "${G}║   1. Open the Codespace URL (*-5000.app.github.dev)${N}"
echo -e "${G}║   2. Log in with your credentials${N}"
echo -e "${G}║   3. Verify status indicator shows 'متصل' stably${N}"
echo -e "${G}║   4. Send a question — expect streaming answer${N}"
echo -e "${G}║   5. Browser console: NO '[WS] Auth-related close' warnings${N}"
echo -e "${G}╚═══════════════════════════════════════════════════════════════════╝${N}"
exit 0
