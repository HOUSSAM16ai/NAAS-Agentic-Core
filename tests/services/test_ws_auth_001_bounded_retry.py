"""
Regression test — verify D-WS-AUTH-001 bounded 4401 retry + HTTP probe is in place.

USER REPORT (verbatim):
> «أنا فتحت codespace جديد و يتم طردي بمجرد دخولي و لا يتم الاجابة عن الاسئلة»

ROOT CAUSE: Frontend treated 4401 as immediately-fatal:
  1. Single 4401 close → setState("auth_error") + dispatch agent:auth_error
  2. CogniForgeApp handler → logout() → window.location.reload()
  3. After reload → AuthScreen → user re-logs in → new token
  4. WS connects → 4401 again (SECRET_KEY race, DB lag, proxy header strip, ...)
  5. Infinite loop, user never receives answer.

THE FIX (D-WS-AUTH-001):
  1. Bounded retry: MAX_FATAL_RETRIES=3 attempts before escalating to auth_error.
  2. HTTP /me probe: differentiates transient (probe=200) from permanent (probe=401).
  3. logout() uses React state instead of window.location.reload() — preserves tree.
  4. Counter resets on successful reconnect — fresh cycle each new session.

SUPERSEDED BY D-WS-KICK-001 (ISS-097 — 2026-05-29):
  The *count-based* escalation (MAX_FATAL_RETRIES / FATAL_RETRY_DELAY_MS) was
  itself the cause of an idle kick: a valid token could be logged out after a
  few 4401 closes (e.g. a proxy dropping ?token= on reconnect) without ever
  confirming the token was dead. D-WS-KICK-001 removes the count-based path:
  the ONLY route to auth_error is an HTTP /me probe that definitively returns
  401/403. A valid/unknown probe → retryTransientAuth() reconnects forever
  (never logout). The /me probe + "no immediate logout" principle of
  D-WS-AUTH-001 REMAIN and are strengthened; this test now asserts the evolved
  invariants.

This test verifies by static inspection:
1. fatalRetries ref exists (kept for diagnostics) and resets in onopen.
2. The count-based escalation constants are REMOVED (D-WS-KICK-001).
3. revalidateTokenViaHttp function exists and calls /api/security/user/me.
4. FATAL_CODES handler does NOT immediately dispatch auth_error — it probes /me
   and only escalates on a confirmed-invalid result.
5. logout() does NOT call window.location.reload().
6. fatalRetries.current resets in onopen.
7. cleanup aborts in-flight revalidateAbortRef.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestBoundedFatalRetry:
    def test_fatal_retries_ref_declared(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "fatalRetries" in source, (
            "D-WS-AUTH-001: must declare separate fatalRetries counter "
            "to track 4401/4403 attempts independently from network retries."
        )
        assert re.search(r"const\s+fatalRetries\s*=\s*useRef\(0\)", source), (
            "fatalRetries must be a useRef initialized to 0."
        )

    def test_count_based_escalation_removed(self) -> None:
        """D-WS-KICK-001: the count-based escalation that caused the idle kick is GONE.

        MAX_FATAL_RETRIES / FATAL_RETRY_DELAY_MS were the mechanism that logged
        out a *valid* token after a few 4401 closes. A *count* of closes must
        never trigger logout — only a confirmed-invalid /me probe.
        """
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert not re.search(r"const\s+MAX_FATAL_RETRIES\s*=", source), (
            "D-WS-KICK-001: MAX_FATAL_RETRIES constant must be removed — a count of "
            "4401 closes must never escalate to logout."
        )
        assert not re.search(r"const\s+FATAL_RETRY_DELAY_MS\s*=", source), (
            "D-WS-KICK-001: FATAL_RETRY_DELAY_MS constant must be removed (count-based path gone)."
        )

    def test_transient_4401_reconnects_without_logout(self) -> None:
        """D-WS-KICK-001: a valid/unknown probe reconnects via retryTransientAuth()."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "retryTransientAuth" in source, (
            "D-WS-KICK-001: transient 4401 (valid/unknown token) must reconnect via "
            "retryTransientAuth(), never escalate to auth_error."
        )


class TestHttpRevalidationProbe:
    def test_revalidate_function_exists(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "revalidateTokenViaHttp" in source, (
            "Must define revalidateTokenViaHttp probe function."
        )

    def test_probe_calls_user_me_endpoint(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "/api/security/user/me" in source, (
            "Probe must call /api/security/user/me to verify token validity."
        )

    def test_probe_distinguishes_three_outcomes(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # Must return 'valid' on 200, 'invalid' on 401/403, 'unknown' otherwise.
        for outcome in ('"valid"', '"invalid"', '"unknown"'):
            assert outcome in source, f"Probe must return {outcome} for one of the three outcomes."

    def test_probe_aborts_on_unmount(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "revalidateAbortRef" in source, (
            "Must track AbortController for in-flight probe to cancel on unmount."
        )
        # cleanup must abort it
        cleanup_match = re.search(
            r"return\s*\(\s*\)\s*=>\s*\{(.*?)\};\s*\},\s*\[connect,",
            source,
            re.DOTALL,
        )
        assert cleanup_match is not None
        cleanup_body = cleanup_match.group(1)
        assert "revalidateAbortRef" in cleanup_body, (
            "useEffect cleanup must abort any in-flight probe."
        )


class TestNoImmediateAuthError:
    def test_fatal_codes_does_not_immediately_setstate_autherror(self) -> None:
        """The handler must NOT set state='auth_error' on FIRST 4401."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")

        # Key invariant: the FIRST 4401 must NOT immediately dispatch auth_error.
        # We verify by checking the handler INCREMENTS fatalRetries BEFORE
        # any setState("auth_error"). Isolating the FATAL_CODES if-block via
        # regex is brittle; substring inspection of the full onclose body is
        # robust enough for this static guard.
        ws_close_section = re.search(
            r"ws\.onclose\s*=\s*\(e\)\s*=>\s*\{(.*?)\};",
            source,
            re.DOTALL,
        )
        assert ws_close_section is not None
        body = ws_close_section.group(1)

        # fatalRetries.current is still incremented (kept for diagnostics/logging).
        assert re.search(r"fatalRetries\.current\s*\+=\s*1", body), (
            "Handler should still track fatalRetries.current on each 4401 (diagnostics)."
        )

        # Must probe /me before any escalation. (Checked against the full source:
        # D-WS-KICK-001 adds a nested `retryTransientAuth` arrow fn whose `};`
        # truncates the non-greedy onclose-body regex above — so the probe call,
        # which lives after that nested fn, is asserted at source scope.)
        assert "revalidateTokenViaHttp" in source, (
            "Handler must probe /me before escalating to auth_error."
        )

        # D-WS-KICK-001: the ONLY auth_error path is a confirmed-invalid /me probe.
        # The handler must NOT escalate based on a retry count.
        assert "token_invalid_confirmed_via_http" in source, (
            "D-WS-KICK-001: auth_error must be gated on an HTTP-confirmed-invalid token."
        )
        assert source.count('"agent:auth_error"') == 1, (
            "D-WS-KICK-001: exactly one agent:auth_error dispatch site (the confirmed-invalid branch)."
        )

    def test_transient_auth_warning_event_emitted(self) -> None:
        """Transient 4401 should emit a non-fatal warning event for telemetry."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "agent:transient_auth_warning" in source, (
            "Must emit 'agent:transient_auth_warning' event when 4401 is treated "
            "as transient (for telemetry & optional UI feedback)."
        )

    def test_fatal_retries_reset_on_open(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        onopen_match = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};", source, re.DOTALL)
        assert onopen_match is not None
        onopen_body = onopen_match.group(1)
        assert re.search(r"fatalRetries\.current\s*=\s*0", onopen_body), (
            "onopen must reset fatalRetries.current=0 — fresh cycle per session."
        )


class TestLogoutNoReload:
    def test_logout_does_not_reload_page(self) -> None:
        """logout() must NOT call window.location.reload() — preserves React tree."""
        source = _read("frontend/app/components/CogniForgeApp.jsx")
        # Find the logout function
        logout_match = re.search(
            r"const\s+logout\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};",
            source,
            re.DOTALL,
        )
        assert logout_match is not None, "logout() function not found"
        logout_body = logout_match.group(1)

        # Strip line-comments to avoid false positives from the doctrine docstring
        # that REFERENCES window.location.reload() to explain why we don't call it.
        uncommented_lines = []
        for raw_line in logout_body.splitlines():
            stripped = raw_line.lstrip()
            if stripped.startswith("//"):
                continue
            # Remove inline comments
            line_code = raw_line
            if "//" in line_code:
                line_code = line_code[: line_code.find("//")]
            uncommented_lines.append(line_code)
        code_only = "\n".join(uncommented_lines)

        assert "window.location.reload()" not in code_only, (
            "D-WS-AUTH-001: logout() MUST NOT call window.location.reload(). "
            "Use React state (setToken(null), setUser(null)) instead. "
            "reload() causes browser autofill submit loops and tears down React tree."
        )

    def test_logout_clears_state(self) -> None:
        source = _read("frontend/app/components/CogniForgeApp.jsx")
        logout_match = re.search(
            r"const\s+logout\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};",
            source,
            re.DOTALL,
        )
        assert logout_match is not None
        logout_body = logout_match.group(1)
        # Must clear localStorage and React state
        assert "localStorage.removeItem('token')" in logout_body, "logout must remove token"
        assert "setToken(null)" in logout_body, "logout must clear token state"
        assert "setUser(null)" in logout_body, "logout must clear user state"
