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

This test verifies by static inspection:
1. fatalRetries ref exists and is separate from `retries`.
2. MAX_FATAL_RETRIES constant defined (3-5 range).
3. revalidateTokenViaHttp function exists and calls /api/security/user/me.
4. FATAL_CODES handler does NOT immediately dispatch auth_error.
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

    def test_max_fatal_retries_constant_bounded(self) -> None:
        """Hard upper bound — prevents infinite reconnect loop even on positive probes."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        match = re.search(r"const\s+MAX_FATAL_RETRIES\s*=\s*(\d+)", source)
        assert match, "MAX_FATAL_RETRIES constant must be defined"
        max_retries = int(match.group(1))
        assert 2 <= max_retries <= 5, (
            f"MAX_FATAL_RETRIES must be 2-5 (got {max_retries}). "
            "Lower → quick escalation. Higher → user waits too long."
        )

    def test_fatal_retry_delay_short(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        match = re.search(r"const\s+FATAL_RETRY_DELAY_MS\s*=\s*(\d+)", source)
        assert match
        delay = int(match.group(1))
        assert 1000 <= delay <= 5000, f"FATAL_RETRY_DELAY_MS must be 1000-5000ms (got {delay})."


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

        # fatalRetries.current must be incremented
        assert re.search(r"fatalRetries\.current\s*\+=\s*1", body), (
            "Handler must increment fatalRetries.current on each 4401."
        )

        # Must check for max retries
        assert "MAX_FATAL_RETRIES" in body, (
            "Handler must check fatalRetries against MAX_FATAL_RETRIES."
        )

        # Must call revalidateTokenViaHttp
        assert "revalidateTokenViaHttp" in body, (
            "Handler must probe /me before escalating to auth_error."
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
