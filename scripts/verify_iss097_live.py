#!/usr/bin/env python3
"""
Live end-to-end verification for ISS-097 / D-WS-KICK-001 — run on a real Codespace.

The "kick to login / new conversation" catastrophe is connection-level (it happens
even without asking a question). This script boots nothing — it drives the *already
running* stack (uvicorn :8000) the way the browser does, and proves:

  1. /me returns 200 for a valid token (the probe Fix A relies on to keep the session).
  2. An IDLE WebSocket with a valid token stays connected: session_ready arrives,
     a heartbeat ping is answered with pong, and the socket is NOT closed / NOT 4401.
  3. A reconnect STORM with the same valid token: every reconnect is accepted
     (session_ready), never 4401 — so the client can never escalate to logout.
  4. A token-stripped connect is correctly rejected with 4401 (genuine auth failure).
  5. The latest-conversation restore endpoint (/api/chat/latest) responds (Fix B).

Usage (on the Codespace, after the stack is up):
    # provide a real JWT (from a login) or let the script log in:
    TOKEN=<jwt> python scripts/verify_iss097_live.py
    # or:
    LOGIN_EMAIL=... LOGIN_PASSWORD=... python scripts/verify_iss097_live.py

Exit code 0 = all checks passed.

This file is intentionally dependency-light (httpx + websockets, both present on the
Codespace). It is NOT part of pytest and never runs in the deps-less CI sandbox.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

BASE_HTTP = os.environ.get("VERIFY_BASE_HTTP", "http://localhost:8000")
BASE_WS = os.environ.get("VERIFY_BASE_WS", "ws://localhost:8000")
ME_PATH = "/api/security/user/me"
WS_PATH = "/api/chat/ws"
LATEST_PATH = "/api/chat/latest"

PASS = "✅"
FAIL = "❌"


def _login_if_needed() -> str:
    token = os.environ.get("TOKEN", "").strip()
    if token:
        return token
    import httpx

    email = os.environ.get("LOGIN_EMAIL")
    password = os.environ.get("LOGIN_PASSWORD")
    if not (email and password):
        sys.exit("Provide TOKEN=<jwt> or LOGIN_EMAIL=.. LOGIN_PASSWORD=..")
    r = httpx.post(
        f"{BASE_HTTP}/api/security/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("access_token") or data.get("token") or data["data"]["access_token"]


async def _connect_once(token: str | None, *, idle_secs: float = 0.0) -> dict:
    """Open the WS like the browser (?token=), optionally idle + heartbeat, then close.

    Returns a dict describing what happened.
    """
    import websockets

    url = f"{BASE_WS}{WS_PATH}"
    if token is not None:
        url += f"?token={token}"

    result: dict = {"connected": False, "session_ready": False, "pong": False, "close_code": None}
    try:
        async with websockets.connect(url, ping_interval=None, open_timeout=15) as ws:
            result["connected"] = True
            # First server frame should be session_ready (D-WS-FLAP-003 primer).
            try:
                first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if first.get("type") == "session_ready":
                    result["session_ready"] = True
            except TimeoutError:
                pass

            if idle_secs:
                await asyncio.sleep(idle_secs)
                await ws.send(json.dumps({"type": "ping"}))
                # drain a few frames looking for a pong
                for _ in range(5):
                    try:
                        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=8))
                    except TimeoutError:
                        break
                    if '"type":"pong"' in json.dumps(msg) or msg.get("type") == "pong":
                        result["pong"] = True
                        break
    except Exception as exc:  # websockets raises with .code on close
        result["close_code"] = getattr(exc, "code", None) or str(exc)
    return result


async def _main() -> int:
    import httpx

    token = _login_if_needed()
    passed = failed = 0

    def check(cond: bool, msg: str) -> None:
        nonlocal passed, failed
        print(f"{PASS if cond else FAIL} {msg}")
        passed += int(cond)
        failed += int(not cond)

    # 1. /me returns 200 for a valid token
    me = httpx.get(
        f"{BASE_HTTP}{ME_PATH}", headers={"Authorization": f"Bearer {token}"}, timeout=20
    )
    check(me.status_code == 200, f"/me with valid token -> 200 (got {me.status_code})")

    # 2. Idle WS stays alive + heartbeat answered
    idle = await _connect_once(token, idle_secs=8.0)
    check(idle["connected"] and idle["session_ready"], "idle WS connects + session_ready")
    check(idle["pong"], "idle WS heartbeat ping -> pong (no spurious close)")
    check(
        idle["close_code"] in (None, 1000, 1001), f"idle WS not 4401 (close={idle['close_code']})"
    )

    # 3. Reconnect storm — same valid token, 5x, all accepted, never 4401
    storm_ok = True
    for i in range(5):
        r = await _connect_once(token)
        ok = r["connected"] and r["session_ready"]
        storm_ok = storm_ok and ok
        print(
            f"   reconnect #{i + 1}: connected={r['connected']} session_ready={r['session_ready']} close={r['close_code']}"
        )
    check(storm_ok, "reconnect storm: every reconnect accepted, never 4401")

    # 4. Token-stripped connect is rejected (genuine auth failure)
    no_tok = await _connect_once(None)
    check(
        no_tok["close_code"] not in (None, 1000, 1001),
        f"no-token connect rejected (close={no_tok['close_code']})",
    )

    # 5. Latest-conversation restore endpoint responds (Fix B)
    latest = httpx.get(
        f"{BASE_HTTP}{LATEST_PATH}", headers={"Authorization": f"Bearer {token}"}, timeout=20
    )
    check(
        latest.status_code in (200, 204, 404), f"/api/chat/latest responds ({latest.status_code})"
    )

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
