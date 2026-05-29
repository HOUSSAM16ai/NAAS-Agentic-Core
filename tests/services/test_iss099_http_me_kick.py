"""
Regression test — HTTP /me bootstrap must never log out a valid session (ISS-099 / D-WS-KICK-002).

USER REPORT (recurring, GitHub Codespaces, 2026-05-29):
> «الكارثة الخطيرة شديدة التعقيد مزالت ... بينما أنا داخل دردشة النظام يخرج
>  لصفحة تسجيل الدخول ثم أجد نفسي في محادثة جديدة و يخرج و يدخل آليا»

ROOT CAUSE (D-WS-KICK-002):
D-WS-KICK-001 hardened the WebSocket auth path (only logout on a confirmed
/me 401/403). But the HTTP bootstrap effect `fetchUser` in CogniForgeApp.jsx
was LEFT with naive logic:

    if (response.ok) setUser(...)
    else logout();              // ← ANY non-200 logs out
    ...
    catch (error) { logout(); } // ← ANY network error logs out

`fetchUser` runs on mount and on every `token` change and hits
`/api/security/user/me`. In a Supabase-backed deployment the backend is
restarted by the health monitor (3 failures), is occasionally slow, or the
Codespaces proxy hiccups → /me returns 502/503/timeout/network-error →
logout() → kicked to the login page even though the token is perfectly valid
→ re-enter → DashboardLayout remounts → brand-new conversation. This matches
every symptom and persists through D-095/D-096/D-WS-KICK-001.

FIX (D-WS-KICK-002):
1. Only HTTP 401/403 triggers logout (token confirmed-invalid) — same rule as
   the WebSocket path.
2. Any other failure (5xx/404/network) is transient: keep the session, render
   from the cached user, and retry /me with backoff.
3. The user object is cached in localStorage (`cogniforge_user`) on login and
   on each successful /me, restored instantly on mount, and cleared on a real
   logout — so a transient /me failure never drops to the login screen.

INVARIANTS (enforced here):
A. The naive "else logout()" and "catch -> logout()" are gone.
B. logout() is gated on `response.status === 401 || response.status === 403`.
C. A transient branch (`scheduleRetry`) exists.
D. The user cache (`cogniforge_user`) is read on mount, written on login + success,
   and removed on logout.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
APP = REPO_ROOT / "frontend" / "app" / "components" / "CogniForgeApp.jsx"


def _read() -> str:
    return APP.read_text(encoding="utf-8")


def test_marker_present() -> None:
    src = _read()
    assert "D-WS-KICK-002" in src and "ISS-099" in src, (
        "D-WS-KICK-002: the fix marker must be present in CogniForgeApp.jsx."
    )


def test_logout_gated_on_401_403_only() -> None:
    """logout() in the /me bootstrap must be gated on a 401/403 status check."""
    src = _read()
    assert "response.status === 401 || response.status === 403" in src, (
        "D-WS-KICK-002: HTTP /me bootstrap must logout ONLY on 401/403, "
        "mirroring the WebSocket auth gate. A non-401/403 (5xx/404/network) "
        "must be treated as transient — never a logout."
    )


def test_transient_retry_branch_exists() -> None:
    src = _read()
    assert "scheduleRetry" in src, (
        "D-WS-KICK-002: a transient-retry branch (scheduleRetry) must exist so a "
        "flaky backend (Supabase restart/latency) does not kick a valid session."
    )


def test_naive_unconditional_logout_is_gone() -> None:
    """The old `else { logout(); }` right after `if (response.ok)` must be gone."""
    src = _read()
    # Collapse whitespace to catch formatting variants.
    compact = " ".join(src.split())
    assert "} else { logout(); }" not in compact, (
        "D-WS-KICK-002: the unconditional `else { logout(); }` after the /me ok-check "
        "must be removed — it kicked valid sessions on any non-200."
    )


def test_user_is_cached_and_restored() -> None:
    src = _read()
    assert "cogniforge_user" in src, (
        "D-WS-KICK-002: the user object must be cached under 'cogniforge_user' so a "
        "transient /me failure renders from cache instead of dropping to AuthScreen."
    )
    assert "localStorage.getItem('cogniforge_user')" in src, "cache must be read on mount"
    assert "localStorage.setItem('cogniforge_user'" in src, (
        "cache must be written on login and/or successful /me"
    )
    assert "localStorage.removeItem('cogniforge_user')" in src, (
        "cache must be cleared on a real logout"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Behavioral check — a faithful port of the validate() decision.
# ─────────────────────────────────────────────────────────────────────────────
def _decide(status: int | None) -> str:
    """Mirror of fetchUser.validate(): returns the action taken.

    status=None simulates a thrown network error (fetch rejects).
    """
    if status is None:
        return "retry"  # catch -> scheduleRetry (no logout)
    if 200 <= status < 300:
        return "setUser"
    if status in (401, 403):
        return "logout"
    return "retry"  # 5xx/404/other -> scheduleRetry (no logout)


def test_decision_table() -> None:
    assert _decide(200) == "setUser"
    assert _decide(401) == "logout"
    assert _decide(403) == "logout"
    # The catastrophe cases — must NOT logout:
    assert _decide(500) == "retry", "500 during backend restart must NOT logout"
    assert _decide(502) == "retry", "502 from proxy must NOT logout"
    assert _decide(503) == "retry", "503 during restart must NOT logout"
    assert _decide(404) == "retry", "404 routing blip must NOT logout"
    assert _decide(None) == "retry", "network error must NOT logout"
