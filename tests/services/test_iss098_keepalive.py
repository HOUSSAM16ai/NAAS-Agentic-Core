"""
Regression test — WS turn keepalive prevents false heartbeat-timeout (ISS-098 / D-WS-FLAP-005).

USER REPORT (recurring, GitHub Codespaces):
> «النظام لا يجيب عن الأسئلة ... تفقد الرسائل السابقة بشكل عادي لكن لا يرد عن الأسئلة»

ROOT CAUSE (proven live 2026-05-29):
The WS receive loop in both `customer_chat.py` and `admin.py` BLOCKS on
`await stream_task` for the entire turn. While blocked it cannot read the
client's app-level `ping`, so it never replies with `pong`. The frontend
heartbeat (`useRealtimeConnection.js`) cleared its 90s timeout ONLY on `pong`.

A substantive question produces a long answer. Live evidence: a single turn
took 154.8s (3962 deltas). Without a keepalive, the client falsely declares
the connection stale at ~135s → `ws.close(1001)` → reconnect → the in-progress
answer is LOST ("no answer for substantive questions"). Short answers finish
under the timeout, which is why they appeared to work.

FIX (D-WS-FLAP-005):
1. Backend: a concurrent `_run_turn_keepalive` task sends a lightweight `pong`
   every ~20s (via the shared `send_lock`) for the duration of the turn — for
   BOTH customer and admin paths. This required `send_lock` parity on admin.
2. Frontend: any inbound WS message (not only `pong`) clears the heartbeat
   timeout — streaming deltas prove the connection is alive.

INVARIANTS (enforced here):
- `_run_turn_keepalive` + `_TURN_KEEPALIVE_INTERVAL_SECONDS` exist on both routers.
- The keepalive emits `pong` frames periodically and never raises.
- Admin path has `_locked_send_json` and `_emit_terminal_frames` accepts `send_lock`.
- Both handlers wire a `keepalive_task` around `await stream_task`.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("APP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "x" * 64)


# ─────────────────────────────────────────────────────────────────────────────
# Backend: keepalive helper exists on both routers
# ─────────────────────────────────────────────────────────────────────────────
def test_customer_keepalive_helper_exists() -> None:
    from app.api.routers import customer_chat

    assert hasattr(customer_chat, "_run_turn_keepalive"), (
        "ISS-098: customer_chat must define `_run_turn_keepalive`."
    )
    assert hasattr(customer_chat, "_TURN_KEEPALIVE_INTERVAL_SECONDS"), (
        "ISS-098: customer_chat must define `_TURN_KEEPALIVE_INTERVAL_SECONDS`."
    )
    sig = inspect.signature(customer_chat._run_turn_keepalive)
    assert list(sig.parameters.keys()) == ["websocket", "lock"], (
        f"ISS-098: _run_turn_keepalive signature changed: {list(sig.parameters.keys())}"
    )


def test_admin_keepalive_helper_exists() -> None:
    from app.api.routers import admin

    assert hasattr(admin, "_run_turn_keepalive"), (
        "ISS-098: admin must define `_run_turn_keepalive`."
    )
    assert hasattr(admin, "_TURN_KEEPALIVE_INTERVAL_SECONDS"), (
        "ISS-098: admin must define `_TURN_KEEPALIVE_INTERVAL_SECONDS`."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Backend: admin D-096 parity — concurrent keepalive REQUIRES the send lock
# ─────────────────────────────────────────────────────────────────────────────
def test_admin_has_locked_send_json() -> None:
    from app.api.routers import admin

    assert hasattr(admin, "_locked_send_json"), (
        "D-096 parity: admin.py must define `_locked_send_json` — the keepalive "
        "task sends concurrently with the stream and would corrupt ASGI frames "
        "without a serializing lock."
    )
    params = list(inspect.signature(admin._locked_send_json).parameters.keys())
    assert params == ["websocket", "lock", "payload"], params


def test_admin_emit_terminal_frames_requires_send_lock() -> None:
    from app.api.routers import admin

    params = list(inspect.signature(admin._emit_terminal_frames).parameters.keys())
    assert "send_lock" in params, (
        f"D-096 parity: admin `_emit_terminal_frames` must accept send_lock. Got: {params}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Backend: handlers wire the keepalive task around the stream await
# ─────────────────────────────────────────────────────────────────────────────
def test_customer_handler_wires_keepalive() -> None:
    from app.api.routers import customer_chat

    src = inspect.getsource(customer_chat.chat_stream_ws)
    assert "_run_turn_keepalive" in src, (
        "ISS-098: customer chat_stream_ws must start a keepalive task around the stream."
    )
    assert "keepalive_task" in src and "keepalive_task.cancel()" in src, (
        "ISS-098: customer handler must cancel the keepalive task when the stream ends."
    )


def test_admin_handler_wires_keepalive() -> None:
    from app.api.routers import admin

    src = inspect.getsource(admin.chat_stream_ws)
    assert "_run_turn_keepalive" in src, (
        "ISS-098: admin chat_stream_ws must start a keepalive task around the stream."
    )
    assert "keepalive_task" in src and "keepalive_task.cancel()" in src, (
        "ISS-098: admin handler must cancel the keepalive task when the stream ends."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Functional: keepalive emits pong frames periodically and never raises
# ─────────────────────────────────────────────────────────────────────────────
def _make_connected_ws(sent: list[dict]) -> MagicMock:
    from starlette.websockets import WebSocketState

    ws = MagicMock()
    ws.client_state = WebSocketState.CONNECTED

    async def fake_send_json(payload):
        sent.append(payload)

    ws.send_json = fake_send_json
    return ws


def test_customer_keepalive_emits_pong_periodically(monkeypatch) -> None:
    from app.api.routers import customer_chat

    # Shrink the interval so the test is fast and deterministic.
    monkeypatch.setattr(customer_chat, "_TURN_KEEPALIVE_INTERVAL_SECONDS", 0.02)

    async def run() -> None:
        sent: list[dict] = []
        ws = _make_connected_ws(sent)
        lock = asyncio.Lock()
        task = asyncio.create_task(customer_chat._run_turn_keepalive(ws, lock))
        await asyncio.sleep(0.11)  # ~5 intervals
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task
        assert len(sent) >= 3, f"expected several keepalive pongs, got {len(sent)}"
        assert all(p.get("type") == "pong" for p in sent), sent
        assert all(p.get("payload", {}).get("keepalive") is True for p in sent), sent

    asyncio.run(run())


def test_keepalive_stops_when_ws_disconnected(monkeypatch) -> None:
    from starlette.websockets import WebSocketState

    from app.api.routers import customer_chat

    monkeypatch.setattr(customer_chat, "_TURN_KEEPALIVE_INTERVAL_SECONDS", 0.02)

    async def run() -> None:
        sent: list[dict] = []
        ws = _make_connected_ws(sent)
        ws.client_state = WebSocketState.DISCONNECTED  # already gone
        lock = asyncio.Lock()
        # Should return promptly without sending anything and without raising.
        await asyncio.wait_for(customer_chat._run_turn_keepalive(ws, lock), timeout=1.0)
        assert sent == [], f"keepalive sent on a disconnected socket: {sent}"

    asyncio.run(run())
