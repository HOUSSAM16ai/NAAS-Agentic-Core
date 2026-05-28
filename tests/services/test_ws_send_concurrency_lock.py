"""
Regression test — WebSocket send concurrency must be serialized (ISS-094 round 3 / D-096).

USER REPORT (2026-05-28):
> «النظام لا يجيب عن الأسئلة و أجد نفسي مطرود إلى صفحة تسجيل الدخول
>  ثم يعود يدخل إلى التطبيق ... بعد ثواني فقط ... بعد سؤال أو اثنين»

ROOT CAUSE (D-096):
`customer_chat.py` was running `_evaluate_and_emit_bkt` as a background task
concurrently with `stream_and_forward`. Both call `websocket.send_json`
on the same WebSocket WITHOUT any lock. Starlette's WebSocket.send_json
is NOT coroutine-safe for concurrent sends.

On fast DB (SQLite), BKT completes before stream starts (no concurrent
sends). On slow DB (Supabase, 300ms-2s per write), BKT and stream
overlap → ASGI protocol corruption → silent WebSocket close → frontend
reconnects → if SECRET_KEY/state mismatch → 4401 → kick to login.

INVARIANT (enforced by these tests):
1. `_evaluate_and_emit_bkt` must accept a `send_lock` parameter.
2. `_emit_terminal_frames` must accept a `send_lock` parameter.
3. `_locked_send_json` helper exists and uses an asyncio.Lock.
4. `handle_control_message` must accept an optional `send_lock` parameter.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Ensure imports work
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Set up env before imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("APP_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "x" * 64)


def test_locked_send_json_exists() -> None:
    """The `_locked_send_json` helper must exist and use a lock."""
    from app.api.routers import customer_chat

    assert hasattr(customer_chat, "_locked_send_json"), (
        "D-096: `_locked_send_json` helper is missing from customer_chat.py. "
        "This is required to prevent concurrent send_json on the WebSocket."
    )

    fn = customer_chat._locked_send_json
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    assert params == ["websocket", "lock", "payload"], (
        f"D-096: _locked_send_json signature changed: {params}. "
        f"Expected ['websocket', 'lock', 'payload']."
    )


def test_evaluate_and_emit_bkt_requires_send_lock() -> None:
    """`_evaluate_and_emit_bkt` must accept a `send_lock` parameter."""
    from app.api.routers import customer_chat

    sig = inspect.signature(customer_chat._evaluate_and_emit_bkt)
    params = list(sig.parameters.keys())
    assert "send_lock" in params, (
        f"D-096: `_evaluate_and_emit_bkt` does NOT accept send_lock. "
        f"Got params: {params}. Without it, BKT races with stream_and_forward "
        f"on websocket.send_json → ASGI corruption → silent close → kick."
    )


def test_emit_terminal_frames_requires_send_lock() -> None:
    """`_emit_terminal_frames` must accept a `send_lock` parameter."""
    from app.api.routers import customer_chat

    sig = inspect.signature(customer_chat._emit_terminal_frames)
    params = list(sig.parameters.keys())
    assert "send_lock" in params, (
        f"D-096: `_emit_terminal_frames` does NOT accept send_lock. "
        f"Got params: {params}."
    )


def test_handle_control_message_accepts_send_lock() -> None:
    """`handle_control_message` must accept an optional `send_lock`."""
    from app.services.skills.ws_heartbeat_skill import handle_control_message

    sig = inspect.signature(handle_control_message)
    params = list(sig.parameters.keys())
    assert "send_lock" in params, (
        f"D-096: `handle_control_message` does NOT accept send_lock. "
        f"Got params: {params}."
    )


def test_locked_send_json_serializes_concurrent_sends() -> None:
    """Verify the lock actually serializes concurrent send attempts."""
    from app.api.routers import customer_chat

    async def run() -> None:
        # Mock websocket
        ws = MagicMock()
        # Track call order
        call_log: list[str] = []

        async def fake_send_json(payload):
            call_log.append(f"start:{payload['n']}")
            # Yield to event loop — simulates network I/O
            await asyncio.sleep(0.01)
            call_log.append(f"end:{payload['n']}")

        ws.send_json = fake_send_json
        lock = asyncio.Lock()

        # Fire 5 concurrent sends
        tasks = [
            asyncio.create_task(customer_chat._locked_send_json(ws, lock, {"n": i}))
            for i in range(5)
        ]
        await asyncio.gather(*tasks)

        # Verify each send completed before the next started (perfect serialization)
        for i in range(5):
            start_idx = call_log.index(f"start:{i}")
            end_idx = call_log.index(f"end:{i}")
            # No other "start" should appear between this start and end
            between = call_log[start_idx + 1 : end_idx]
            other_starts = [c for c in between if c.startswith("start:")]
            assert not other_starts, (
                f"D-096 FAILURE: send #{i} interleaved with: {other_starts}. "
                f"The lock should serialize sends. Full log: {call_log}"
            )

    asyncio.run(run())


def test_evaluate_and_emit_bkt_uses_locked_send() -> None:
    """The BKT function body must NOT use raw `websocket.send_json` — only locked."""
    from app.api.routers import customer_chat

    source = inspect.getsource(customer_chat._evaluate_and_emit_bkt)

    # The function should call _locked_send_json, not websocket.send_json directly
    assert "_locked_send_json" in source, (
        "D-096: `_evaluate_and_emit_bkt` body does NOT use _locked_send_json. "
        "This is required to prevent races with stream_and_forward."
    )
    # Should NOT contain raw `websocket.send_json` call
    # (well, the docstring may mention it — search for actual call pattern)
    lines = source.splitlines()
    code_lines = [
        line for line in lines
        if not line.strip().startswith("#") and not line.strip().startswith('"')
    ]
    code_text = "\n".join(code_lines)
    assert "await websocket.send_json" not in code_text, (
        "D-096: `_evaluate_and_emit_bkt` still calls `await websocket.send_json` "
        "directly. Use `_locked_send_json` instead."
    )
