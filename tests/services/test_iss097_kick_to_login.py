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


# ─────────────────────────── Invariant C (backend 1013 not 4401) ───────────────────────────


def test_customer_ws_transient_lookup_closes_1013() -> None:
    src = _read(CUSTOMER)
    assert "WS_BACKEND_TRANSIENT" in src and "close(code=1013)" in src, (
        "D-WS-KICK-001: customer_chat WS must close a transient user-lookup failure "
        "with retryable 1013, not 4401."
    )
    # The guard must wrap db.get(User, user_id) in try/except.
    assert re.search(
        r"try:\s*\n\s*actor = await db\.get\(User, user_id\)\s*\n\s*except Exception",
        src,
    ), "D-WS-KICK-001: customer_chat WS user lookup must be wrapped in try/except."


def test_admin_ws_transient_lookup_closes_1013() -> None:
    src = _read(ADMIN)
    assert "WS_BACKEND_TRANSIENT" in src and "close(code=1013)" in src, (
        "D-WS-KICK-001: admin WS must close a transient user-lookup failure with 1013, not 4401."
    )
    assert re.search(
        r"try:\s*\n\s*actor = await db\.get\(User, user_id\)\s*\n\s*except Exception",
        src,
    ), "D-WS-KICK-001: admin WS user lookup must be wrapped in try/except."


def test_genuine_invalid_user_still_4401() -> None:
    """A genuinely missing/inactive user must still close 4401 (correct behavior)."""
    for src in (_read(CUSTOMER), _read(ADMIN)):
        assert "WS_AUTH_USER_INACTIVE" in src and "close(code=4401)" in src, (
            "D-WS-KICK-001: a genuinely None/inactive user must still close 4401 — "
            "only *transient* lookup failures downgrade to 1013."
        )
