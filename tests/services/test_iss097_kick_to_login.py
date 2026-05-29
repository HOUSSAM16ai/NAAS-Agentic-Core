"""
Regression test — WebSocket 4401 must never log out a valid session (ISS-097 / D-WS-KICK-001).

USER REPORT (2026-05-29):
> «انت تستهزئ بي قم بحل الكارثة ... مشكلة الدخول و الخروج إلى محادثة جديدة
>  بشكل كارثي خطير» — kicked to login after a question or two, landing in a
>  brand-new conversation. Persisted through D-095 and D-096.

ROOT CAUSE (D-WS-KICK-001) — two independent halves:

1. SPURIOUS LOGOUT: `useRealtimeConnection.js` fired `agent:auth_error`
   (→ logout → blank "new conversation") after a *count* of consecutive 4401
   closes (MAX_FATAL_RETRIES), WITHOUT confirming the token was actually dead.
   With FATAL_RETRY_DELAY_MS=2s that was a kick in ~6-8s — even when the token
   was perfectly valid. Any server-side WS hiccup (transient db.get, blip,
   race) was mistranslated into a catastrophic logout.

2. "NEW CONVERSATION" ON EVERY LOGIN: `DashboardLayout` always mounted with
   conversationId=null + empty messages, so any (re)login dropped the user
   into a blank chat.

INVARIANTS (enforced by these tests):
A. Frontend: `agent:auth_error` is dispatched ONLY inside the `result === "invalid"`
   branch (HTTP /me definitively 401/403). The count-based escalation
   (MAX_FATAL_RETRIES) is removed.
B. Frontend: `CogniForgeApp.jsx` restores the latest conversation on mount,
   guarded by `didRestoreRef`.
C. Backend: customer_chat.py + admin.py close a transient user-lookup failure
   with retryable 1013 (NOT 4401) so the client reconnects instead of logging out.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "frontend" / "app" / "hooks" / "useRealtimeConnection.js"
APP = REPO_ROOT / "frontend" / "app" / "components" / "CogniForgeApp.jsx"
CUSTOMER = REPO_ROOT / "app" / "api" / "routers" / "customer_chat.py"
ADMIN = REPO_ROOT / "app" / "api" / "routers" / "admin.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ─────────────────────────── Invariant A (frontend logout) ───────────────────────────


def test_no_count_based_fatal_escalation() -> None:
    """The count-based 4401 escalation constant must be gone (it caused the kick)."""
    src = _read(HOOK)
    assert "const MAX_FATAL_RETRIES" not in src, (
        "D-WS-KICK-001: MAX_FATAL_RETRIES constant must be removed. A *count* of "
        "4401 closes must never trigger logout — only a confirmed-invalid /me probe."
    )
    assert "const FATAL_RETRY_DELAY_MS" not in src, (
        "D-WS-KICK-001: FATAL_RETRY_DELAY_MS constant must be removed (count-based path gone)."
    )


def test_auth_error_only_dispatched_after_invalid_probe() -> None:
    """`agent:auth_error` must be dispatched ONLY in the `result === "invalid"` branch."""
    src = _read(HOOK)
    # Every dispatch of agent:auth_error must be preceded (within the same close
    # handler) by a confirmed-invalid check. We assert the unique reason string
    # introduced by the fix is the sole escalation path.
    auth_error_dispatches = src.count('"agent:auth_error"')
    assert auth_error_dispatches >= 1, "auth_error dispatch missing entirely."
    assert auth_error_dispatches == 1, (
        f"D-WS-KICK-001: expected exactly ONE agent:auth_error dispatch site "
        f"(the confirmed-invalid /me branch), found {auth_error_dispatches}."
    )
    assert "token_invalid_confirmed_via_http" in src, (
        "D-WS-KICK-001: the single auth_error path must be the HTTP-confirmed-invalid branch."
    )
    # The decision marker for the fix must be present.
    assert "D-WS-KICK-001" in src


def test_transient_4401_reconnects_not_logout() -> None:
    """A valid/unknown /me result must reconnect, never logout."""
    src = _read(HOOK)
    assert "retryTransientAuth" in src, (
        "D-WS-KICK-001: transient 4401 (valid/unknown token) must reconnect via "
        "retryTransientAuth(), not escalate to auth_error."
    )


# ─────────────────────────── Invariant B (conversation restore) ───────────────────────────


def test_latest_conversation_restore_on_mount() -> None:
    src = _read(APP)
    assert "/api/chat/latest" in src and "/admin/api/chat/latest" in src, (
        "D-WS-KICK-001: DashboardLayout must restore the latest conversation on mount "
        "(customer + admin /latest endpoints)."
    )
    assert "didRestoreRef" in src, (
        "D-WS-KICK-001: a didRestoreRef guard must prevent overwriting the user's "
        "explicit choice (new chat / opening a conversation)."
    )
    # handleNewChat must set the guard so restore does not clobber a deliberate new chat.
    assert re.search(r"handleNewChat[\s\S]{0,200}didRestoreRef\.current = true", src), (
        "D-WS-KICK-001: handleNewChat must set didRestoreRef so restore is suppressed."
    )


# ─────────────────── Invariant C (SUPERSEDED by D-WS-CONN-001 / ISS-100) ───────────────────
#
# D-WS-KICK-001 originally closed a transient connect-time `db.get(User)` failure
# with 1013 instead of 4401. ISS-100 (D-WS-CONN-001) went further and removed the
# connect-time DB query ENTIRELY — identity now comes from the signed JWT with zero
# DB access — because the `db.get` at connect was itself the flap source (1013 →
# reconnect → flap). The assertions below now enforce the DB-free connect contract.


def _ws_connect_section(src: str) -> str:
    """Slice the WS handler from its def to the start of the receive loop.

    (The HTTP `get_actor_user` dependency elsewhere may legitimately use db.get.)
    """
    start = src.index("async def chat_stream_ws")
    loop = src.index("while True", start)
    return src[start:loop]


def test_customer_connect_has_no_db_lookup_1013_path() -> None:
    """The connect-time db.get + 1013 transient path must be GONE (D-WS-CONN-001)."""
    connect = _ws_connect_section(_read(CUSTOMER))
    assert "db.get(User, user_id)" not in connect, (
        "D-WS-CONN-001: the connect-time db.get(User) must be removed — it caused the "
        "1013 → reconnect flap under Supabase pressure."
    )
    assert "async_session_factory()" not in connect, (
        "D-WS-CONN-001: connect must not open a DB session before the receive loop."
    )
    assert "decode_token_payload(" in connect and "WsActor(id=" in connect, (
        "D-WS-CONN-001: customer connect must derive identity from the JWT (no DB)."
    )


def test_admin_connect_has_no_db_lookup_1013_path() -> None:
    connect = _ws_connect_section(_read(ADMIN))
    assert "db.get(User, user_id)" not in connect, (
        "D-WS-CONN-001: admin connect-time db.get(User) must be removed (flap source)."
    )
    assert "async_session_factory()" not in connect, (
        "D-WS-CONN-001: admin connect must not open a DB session before the receive loop."
    )
    assert "decode_token_payload(" in connect and "WsActor(id=" in connect, (
        "D-WS-CONN-001: admin connect must derive identity from the JWT (no DB)."
    )


def test_invalid_token_still_closes_4401() -> None:
    """An invalid/expired token is still rejected at connect with 4401 (the only auth reject)."""
    for src in (_read(CUSTOMER), _read(ADMIN)):
        assert "WS_AUTH_INVALID" in src and "close(code=4401)" in src, (
            "Invalid/expired token must still close 4401 at connect."
        )


def test_wrong_endpoint_still_closes_4403() -> None:
    """Admin-on-customer / standard-on-admin mismatch still closes 4403 (JWT is_admin claim)."""
    for src in (_read(CUSTOMER), _read(ADMIN)):
        assert "close(code=4403)" in src, (
            "Wrong-endpoint account type must still close 4403 (gate uses the JWT is_admin claim)."
        )
