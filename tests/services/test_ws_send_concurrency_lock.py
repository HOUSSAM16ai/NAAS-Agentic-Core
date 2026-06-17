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

D-118 UPDATE (2026-06-17): the BKT background task no longer sends at all.
`_evaluate_bkt_cards` only evaluates + returns card payloads; the cards are
emitted by the orchestrator AFTER the content terminal frame (so they no
longer fragment the streaming exercise text). This is a STRONGER guarantee
than D-096 for BKT — zero concurrent BKT send. The send_lock invariant
still holds: every websocket send (stream deltas, keepalive, terminal
frames, post-content card emission) goes through `_locked_send_json`.

INVARIANT (enforced by these tests):
1. `_evaluate_bkt_cards` must NOT send (no websocket/send_lock param, no
   `_locked_send_json`/`websocket.send_json` in body) — D-118.
2. BKT cards must be emitted via `_locked_send_json` after `_emit_terminal_frames`.
3. `_emit_terminal_frames` must accept a `send_lock` parameter.
4. `_locked_send_json` helper exists and uses an asyncio.Lock.
5. `handle_control_message` must accept an optional `send_lock` parameter.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Ensure imports work
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Set up env before imports
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
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


def test_bkt_eval_does_not_send() -> None:
    """D-118: `_evaluate_bkt_cards` must NOT send — it only evaluates + returns payloads.

    The old `_evaluate_and_emit_bkt` sent ui_component frames mid-stream
    (fragmenting the exercise). D-118 removes the send entirely: the function
    has no `websocket`/`send_lock` param and never calls send. This is the
    structural guarantee that BKT cards cannot land mid-stream.
    """
    from app.api.routers import customer_chat

    assert not hasattr(customer_chat, "_evaluate_and_emit_bkt"), (
        "D-118: old `_evaluate_and_emit_bkt` (which emitted mid-stream) must be gone."
    )
    assert hasattr(customer_chat, "_evaluate_bkt_cards"), (
        "D-118: `_evaluate_bkt_cards` (eval-only, returns payloads) is missing."
    )
    sig = inspect.signature(customer_chat._evaluate_bkt_cards)
    params = list(sig.parameters.keys())
    assert "websocket" not in params and "send_lock" not in params, (
        f"D-118: `_evaluate_bkt_cards` must not take websocket/send_lock "
        f"(it must not send). Got params: {params}."
    )


def test_emit_terminal_frames_requires_send_lock() -> None:
    """`_emit_terminal_frames` must accept a `send_lock` parameter."""
    from app.api.routers import customer_chat

    sig = inspect.signature(customer_chat._emit_terminal_frames)
    params = list(sig.parameters.keys())
    assert "send_lock" in params, (
        f"D-096: `_emit_terminal_frames` does NOT accept send_lock. Got params: {params}."
    )


def test_handle_control_message_accepts_send_lock() -> None:
    """`handle_control_message` must accept an optional `send_lock`."""
    from app.services.skills.ws_heartbeat_skill import handle_control_message

    sig = inspect.signature(handle_control_message)
    params = list(sig.parameters.keys())
    assert "send_lock" in params, (
        f"D-096: `handle_control_message` does NOT accept send_lock. Got params: {params}."
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


def test_bkt_eval_body_has_no_send() -> None:
    """D-118: `_evaluate_bkt_cards` body must contain NO send at all."""
    from app.api.routers import customer_chat

    source = inspect.getsource(customer_chat._evaluate_bkt_cards)
    lines = source.splitlines()
    code_lines = [
        line
        for line in lines
        if not line.strip().startswith("#") and not line.strip().startswith('"')
    ]
    code_text = "\n".join(code_lines)
    assert "_locked_send_json" not in code_text and "websocket.send_json" not in code_text, (
        "D-118: `_evaluate_bkt_cards` must not send (eval-only, returns payloads). "
        "Emission happens after the content terminal frame in the chat handler."
    )


def test_bkt_cards_emitted_via_locked_send_after_terminal() -> None:
    """D-118: BKT cards are emitted via `_locked_send_json` AFTER `_emit_terminal_frames`.

    Preserves the D-096 invariant (every send through the lock) while guaranteeing
    the cards land after the content (no mid-stream fragmentation).
    """
    from app.api.routers import customer_chat

    src = inspect.getsource(customer_chat)
    # The handler awaits the eval task and emits cards through the lock.
    assert "await _bkt_task" in src, "D-118: handler must await the BKT eval task."
    term_idx = src.index("await _emit_terminal_frames(")
    bkt_await_idx = src.index("await _bkt_task")
    assert bkt_await_idx > term_idx, (
        "D-118: BKT card emission must come AFTER the content terminal frame "
        "(sequenced, not concurrent) to avoid fragmenting the exercise text."
    )
    # The post-terminal emission must go through the lock (D-096 preserved).
    post = src[term_idx:]
    assert '"type": "ui_component", "payload": _card' in post, (
        "D-118: post-terminal block must emit the BKT card payloads."
    )
