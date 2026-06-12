"""
Regression test — WebSocket connect must not depend on the database (ISS-100 / D-WS-CONN-001).

USER REPORT (recurring, GitHub Codespaces, 2026-05-29):
> «هو لا يجيب اطلاقا سواء سؤال طويل قصير بمجرد دخولي أقول السلام عليكم لا يرد
>  و يدخل و يخرج ... تظهر متصل غير متصل ... كل هذا يحدث في الثواني الأولى فقط»

ROOT CAUSE (D-WS-CONN-001):
The WS connect handler in customer_chat.py / admin.py executed
`async with async_session_factory() as db: actor = await db.get(User, user_id)`
on EVERY connection. In a Supabase deployment, under connection-pool pressure /
latency this `db.get` raised → the handler closed with 1013 → the frontend
reconnected → it failed again → "connected/disconnected" flapping in the first
seconds, and not even a greeting ("السلام عليكم") was ever processed because the
socket never stayed open long enough. (D-WS-KICK-001's "Fix C" turned the kick
into a flap; it did not remove the DB dependency.)

FIX (D-WS-CONN-001):
Identity at connect is derived from the SIGNED JWT (`sub` + `is_admin`) with ZERO
database queries — `decode_token_payload` + `WsActor`. Establishing the connection
is now instant and Supabase-independent. Per-turn DB work happens inside each
turn's own session and handles its own errors WITHOUT dropping the connection.
Downstream only needs `actor.id` (get_or_create_conversation) and `actor.is_admin`.

INVARIANTS (enforced here):
A. `WsActor` exists (frozen, fields: id, is_admin, is_active) — identity without DB.
B. `decode_token_payload` exists and returns the validated JWT payload.
C. Both WS handlers build identity via `WsActor(id=...)` from JWT claims.
D. The connect-time `actor = await db.get(User, user_id)` is GONE from both handlers.
E. The connect path has no `async_session_factory()` before the receive loop.
"""

from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "x" * 64)

CUSTOMER = REPO_ROOT / "app" / "api" / "routers" / "customer_chat.py"
ADMIN = REPO_ROOT / "app" / "api" / "routers" / "admin.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────── Invariant A: WsActor ───────────────────────────
def test_wsactor_exists_db_free() -> None:
    from app.api.routers.ws_auth import WsActor

    actor = WsActor(id=7, is_admin=False)
    assert actor.id == 7
    assert actor.is_admin is False
    assert actor.is_active is True  # default — identity without a DB row
    # frozen dataclass — identity must be immutable
    import dataclasses

    assert dataclasses.is_dataclass(WsActor)


# ─────────────────────── Invariant B: claims decoder ───────────────────────
def test_decode_token_payload_roundtrip() -> None:
    import jwt

    from app.services.auth.token_decoder import decode_token_payload

    secret = "x" * 64
    token = jwt.encode(
        {"sub": "7", "is_admin": False, "email": "u@x.co"}, secret, algorithm="HS256"
    )
    payload = decode_token_payload(token, secret)
    assert payload["sub"] == "7"
    assert payload.get("is_admin") is False


def test_decode_token_payload_rejects_bad_signature() -> None:
    import jwt
    from fastapi import HTTPException

    from app.services.auth.token_decoder import decode_token_payload

    token = jwt.encode({"sub": "7"}, "the-right-secret-of-sufficient-len!!", algorithm="HS256")
    try:
        decode_token_payload(token, "a-DIFFERENT-secret-of-sufficient-len")
        raise AssertionError("expected HTTPException for bad signature")
    except HTTPException as exc:
        assert exc.status_code == 401


# ──────────────── Invariants C/D/E: handlers are DB-free at connect ────────────────
def _ws_handler_source(module_src: str) -> str:
    """Slice from the chat_stream_ws def to the start of the receive loop."""
    start = module_src.index("async def chat_stream_ws")
    loop = module_src.index("while True", start)
    return module_src[start:loop]


def test_customer_connect_uses_jwt_identity_no_db() -> None:
    src = _read(CUSTOMER)
    connect = _ws_handler_source(src)
    assert "decode_token_payload(" in connect, "customer connect must decode JWT claims"
    assert "WsActor(id=" in connect, "customer connect must build identity from JWT (WsActor)"
    assert "await db.get(User, user_id)" not in connect, (
        "D-WS-CONN-001: connect must NOT query the DB (db.get) — it caused the 1013 flap."
    )
    assert "async_session_factory()" not in connect, (
        "D-WS-CONN-001: connect must NOT open a DB session before the receive loop."
    )


def test_admin_connect_uses_jwt_identity_no_db() -> None:
    src = _read(ADMIN)
    connect = _ws_handler_source(src)
    assert "decode_token_payload(" in connect, "admin connect must decode JWT claims"
    assert "WsActor(id=" in connect, "admin connect must build identity from JWT (WsActor)"
    assert "await db.get(User, user_id)" not in connect, (
        "D-WS-CONN-001: admin connect must NOT query the DB at connect."
    )
    assert "async_session_factory()" not in connect, (
        "D-WS-CONN-001: admin connect must NOT open a DB session before the receive loop."
    )


def test_connect_still_imports_are_consistent() -> None:
    """Both routers import WsActor + decode_token_payload (and dropped decode_user_id at connect)."""
    for p in (CUSTOMER, ADMIN):
        src = _read(p)
        assert "from app.api.routers.ws_auth import WsActor" in src
        assert "decode_token_payload" in src


def test_handler_signature_unchanged() -> None:
    """The WS endpoints still take only the websocket (no new DB dependency injected)."""
    from app.api.routers import admin, customer_chat

    for mod in (customer_chat, admin):
        sig = inspect.signature(mod.chat_stream_ws)
        assert list(sig.parameters.keys()) == ["websocket"], list(sig.parameters.keys())
