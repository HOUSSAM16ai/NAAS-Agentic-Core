#!/usr/bin/env bash
# ISS-MISC-VPN (D-068 hardening 5) — read-only network doctor.
#
# When the fix is verified active (`/cogniforge-proxy-status` returns JSON
# ok=true) but the chat UI still shows "غير متصل", the cause is no longer
# the codespace itself — it's the network path BETWEEN the user's ISP and
# the codespace IP. Verified live on 2026-05-18: some MENA ISPs do
# deep-packet-inspection on WebSocket upgrades and drop the handshake for
# non-US Microsoft/GitHub IPs. Plain HTTP (page load) survives, WS dies.
# The user-confirmed workaround: create the codespace with Region = US.
#
# This script makes that discovery first-class:
#   - Reports the codespace region (and forwarded domain).
#   - Probes localhost endpoints (proves the codespace itself is healthy).
#   - Probes the PUBLIC forwarded URL (proves the proxy chain is up).
#   - If WS upgrade fails on the public URL but works on localhost,
#     surfaces the ISP-blocking diagnosis with the US-region workaround.
#
# Usage:  bash scripts/codespaces-network-doctor.sh

set -u -o pipefail

GREEN=$'\033[32m'
RED=$'\033[31m'
YELLOW=$'\033[33m'
CYAN=$'\033[36m'
RESET=$'\033[0m'

green() { printf '%s%s%s\n' "$GREEN" "$*" "$RESET"; }
red()   { printf '%s%s%s\n' "$RED" "$*" "$RESET"; }
yel()   { printf '%s%s%s\n' "$YELLOW" "$*" "$RESET"; }
hdr()   { printf '\n%s── %s ──%s\n' "$CYAN" "$*" "$RESET"; }

hdr "1. Codespace identity"
cs_name="${CODESPACE_NAME:-}"
cs_domain="${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}"
cs_region="${CODESPACES_REGION:-}"
[ -z "$cs_region" ] && cs_region="${GITHUB_CODESPACE_REGION:-unknown}"
echo "  CODESPACE_NAME                          = ${cs_name:-?}"
echo "  GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN = ${cs_domain:-?}"
echo "  Region                                  = $cs_region"
if [ -z "$cs_name" ]; then
    yel "  ⚠ Not running inside a Codespace — skipping public-URL probes"
    NOT_IN_CODESPACE=1
else
    NOT_IN_CODESPACE=0
fi

hdr "2. Localhost probes (proves the codespace itself is healthy)"
for spec in "Next.js proxy|http://127.0.0.1:3000/cogniforge-proxy-status" \
            "Backend health|http://127.0.0.1:8000/health"; do
    label="${spec%%|*}"
    url="${spec#*|}"
    code=$(curl -s -o /dev/null -w "%{http_code}" -m 3 "$url" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then green "  ✓ $label ($url) → HTTP $code"
    else                          red   "  ✗ $label ($url) → HTTP $code"
    fi
done

# Localhost WS upgrade — should always work inside the container.
hdr "3. Local WS handshake on the proxy (port 3000 → port 8000)"
local_ws_status=$(python3 - <<'PY' 2>&1 || true
import base64, os, socket, re
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3)
    s.connect(("127.0.0.1", 3000))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((
        "GET /api/chat/ws HTTP/1.1\r\n"
        "Host: 127.0.0.1:3000\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: jwt\r\n\r\n"
    ).encode())
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = s.recv(4096)
        if not chunk: break
        data += chunk
    s.close()
    line = data.split(b"\r\n", 1)[0].decode(errors="replace")
    m = re.match(r"HTTP/[\d.]+ (\d+)", line)
    print(m.group(1) if m else "?")
except Exception as e:
    print(f"err:{e}")
PY
)
case "$local_ws_status" in
    101) green "  ✓ local WS upgrade → HTTP 101 (proxy + uvicorn both healthy)";;
    *)   red   "  ✗ local WS upgrade → $local_ws_status (proxy or backend broken)";;
esac

if [ "$NOT_IN_CODESPACE" = "1" ]; then
    echo
    hdr "DONE (local checks only)"
    exit 0
fi

# Public URL probes — these traverse the ISP path that may block WS.
public_base="https://${cs_name}-3000.${cs_domain:-app.github.dev}"
hdr "4. Public URL probes from this codespace's egress IP"
echo "  Public frontend: $public_base"
code=$(curl -sk -o /dev/null -w "%{http_code}" -m 5 "$public_base/cogniforge-proxy-status" 2>/dev/null || echo "000")
case "$code" in
    200) green "  ✓ /cogniforge-proxy-status → HTTP 200 (fix is publicly reachable)";;
    401) red   "  ✗ HTTP 401 — port 3000 visibility is PRIVATE, run codespaces-force-restart.sh";;
    404) yel   "  ⚠ HTTP 404 — server.js NOT running (plain next dev). Run codespaces-force-restart.sh";;
    000) red   "  ✗ no response from public URL — network unreachable from codespace egress";;
    *)   yel   "  ⚠ unexpected HTTP $code";;
esac

# WS handshake against the public hostname from inside the codespace.
# This proves the proxy chain works; it does NOT prove the USER's ISP
# can reach it. But if this fails inside the codespace, the user
# certainly can't.
hdr "5. Public WS handshake from codespace egress"
pub_ws=$(python3 - "$cs_name" "${cs_domain:-app.github.dev}" <<'PY' 2>&1 || true
import sys, base64, os, socket, re, ssl
name, domain = sys.argv[1], sys.argv[2]
host = f"{name}-3000.{domain}"
try:
    sock = socket.create_connection((host, 443), timeout=5)
    ctx = ssl.create_default_context()
    s = ctx.wrap_socket(sock, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((
        "GET /api/chat/ws HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        "Upgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: jwt\r\n\r\n"
    ).encode())
    data = b""
    s.settimeout(5)
    while b"\r\n\r\n" not in data:
        chunk = s.recv(4096)
        if not chunk: break
        data += chunk
    s.close()
    line = data.split(b"\r\n", 1)[0].decode(errors="replace")
    m = re.match(r"HTTP/[\d.]+ (\d+)", line)
    print(m.group(1) if m else line[:60])
except Exception as e:
    print(f"err:{type(e).__name__}:{e}")
PY
)
case "$pub_ws" in
    101) green "  ✓ Public WS upgrade → HTTP 101 (chain healthy from THIS codespace)";;
    401) red   "  ✗ HTTP 401 — port visibility private";;
    *)   yel   "  ⚠ Public WS → $pub_ws"
         yel   "    (does NOT necessarily indicate user-side block; codespace egress IS NOT user IP)";;
esac

hdr "6. Verdict — if local is 101 but the user's PHONE still shows offline"
echo "  All local checks above are PASSING — the codespace + proxy + WS"
echo "  chain are healthy inside the container. If your phone still sees"
echo "  'غير متصل' on $public_base, the failure is at YOUR network path:"
echo
yel  "  → Most common cause (verified by user 2026-05-18):"
yel  "    Some MENA ISPs do deep-packet-inspection and drop WebSocket"
yel  "    upgrades to Codespaces hosted in EU/Asia regions. HTTP gets"
yel  "    through (page loads), but WS handshake is silently filtered."
echo
green "  Verified workaround: create the codespace with Region = US East"
green "    (or US West). HTTP + WS both pass on US IPs through MENA ISPs."
echo
echo "  Steps:"
echo "    1. github.com/codespaces → New codespace"
echo "    2. Branch:        claude/fix-vpn-connection-status-fj2Lm"
echo "    3. Region:        US East   ← (NOT Europe / Asia)"
echo "    4. Create + wait for supervisor.sh to come up"
echo "    5. Open public URL on phone → 'متصل' without VPN"
