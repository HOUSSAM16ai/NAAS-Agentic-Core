"""
Regression test — verify D-WS-FLAP-003 hardening is in place.

After D-WS-FLAP-002 (heartbeat skill) the user still saw fast-cycle UI flapping
(every 3 seconds). The root cause was a stale-WS race condition in React's
useEffect + missing proxy primer event.

This test verifies by static inspection that:
1. `useRealtimeConnection.js` has stale-WS check (`wsRef.current !== ws`).
2. `useRealtimeConnection.js` has debounced state transitions
   (`stateDebounceRef` + `STABLE_THRESHOLD_MS`).
3. `useRealtimeConnection.js` treats close codes 1000/1001 as silent.
4. `MAX_RETRIES >= 30` and `HEARTBEAT_INTERVAL >= 45000` (tolerance tuning).
5. `customer_chat.py` sends `session_ready` primer event after accept.
6. `admin.py` sends `session_ready` primer event after accept.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestStaleWsDetection:
    def test_onclose_checks_wsref_identity(self) -> None:
        """قبل D-WS-FLAP-003 كان onclose يحدّث retries بدون فحص لو الـ ws هو الحالي.
        النتيجة: re-render في React → false reconnect → flapping UI."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # نُتأكد من وجود فحص wsRef.current !== ws داخل onclose
        # النمط: if (wsRef.current && wsRef.current !== ws) { ... return; }
        pattern = r"wsRef\.current\s*&&\s*wsRef\.current\s*!==\s*ws"
        assert re.search(pattern, source), (
            "D-WS-FLAP-003: onclose must check `wsRef.current !== ws` to ignore "
            "stale close events from React re-render race conditions."
        )

    def test_stale_close_logged(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "ignoring close of stale ws" in source, (
            "Stale-WS detection must log to console for debugging."
        )


class TestDebouncedStateTransitions:
    def test_stable_threshold_defined(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "STABLE_THRESHOLD_MS" in source, (
            "Must define STABLE_THRESHOLD_MS constant for stable-connection window."
        )
        # Should be >= 3000 (3 seconds) for proper stability assessment
        match = re.search(r"STABLE_THRESHOLD_MS\s*=\s*(\d+)", source)
        assert match, "STABLE_THRESHOLD_MS must be a numeric literal"
        threshold = int(match.group(1))
        assert threshold >= 3000, (
            f"STABLE_THRESHOLD_MS must be >= 3000ms (got {threshold}) — "
            "below this, brief disconnects show flicker."
        )

    def test_state_debounce_ref_exists(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "stateDebounceRef" in source, (
            "Must have stateDebounceRef for debounced setState('reconnecting')."
        )

    def test_silent_close_codes_handled(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "SILENT_CLOSE_CODES" in source, "Must define SILENT_CLOSE_CODES set."
        # Should include 1000 (NORMAL_CLOSURE) and 1001 (GOING_AWAY)
        assert re.search(r"SILENT_CLOSE_CODES.*=.*new Set\(\[\s*1000\s*,\s*1001", source), (
            "SILENT_CLOSE_CODES must include 1000 and 1001 (normal close)."
        )


class TestToleranceTuning:
    def test_max_retries_increased(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        match = re.search(r"const\s+MAX_RETRIES\s*=\s*(\d+)", source)
        assert match, "MAX_RETRIES must be defined"
        max_retries = int(match.group(1))
        assert max_retries >= 30, (
            f"D-WS-FLAP-003: MAX_RETRIES must be >= 30 (got {max_retries}) — "
            "lower values cause premature 'offline' on flaky mobile networks."
        )

    def test_heartbeat_interval_increased(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        match = re.search(r"const\s+HEARTBEAT_INTERVAL\s*=\s*(\d+)", source)
        assert match, "HEARTBEAT_INTERVAL must be defined"
        interval = int(match.group(1))
        assert interval >= 45000, (
            f"D-WS-FLAP-003: HEARTBEAT_INTERVAL must be >= 45000ms (got {interval})."
        )

    def test_heartbeat_timeout_increased(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        match = re.search(r"const\s+HEARTBEAT_TIMEOUT\s*=\s*(\d+)", source)
        assert match, "HEARTBEAT_TIMEOUT must be defined"
        timeout = int(match.group(1))
        assert timeout >= 15000, (
            f"D-WS-FLAP-003: HEARTBEAT_TIMEOUT must be >= 15000ms (got {timeout})."
        )


class TestServerPrimerEvent:
    def test_customer_chat_sends_primer(self) -> None:
        source = _read("app/api/routers/customer_chat.py")
        # primer must include `session_ready` type
        assert '"session_ready"' in source or "'session_ready'" in source, (
            "D-WS-FLAP-003: customer_chat.py must send session_ready primer event."
        )
        # primer must happen after accept and before the main loop
        ws_section_match = re.search(
            r"async def chat_stream_ws\b.*?(?=\n@router\.|\Z)",
            source,
            re.DOTALL,
        )
        assert ws_section_match is not None
        ws_section = ws_section_match.group(0)
        accept_idx = ws_section.find("websocket.accept(")
        primer_idx = ws_section.find("session_ready")
        loop_idx = ws_section.find("while True")
        assert accept_idx > 0 and primer_idx > accept_idx, (
            "primer must happen AFTER websocket.accept()"
        )
        assert loop_idx > primer_idx, "primer must happen BEFORE the message loop"

    def test_admin_sends_primer(self) -> None:
        source = _read("app/api/routers/admin.py")
        assert '"session_ready"' in source or "'session_ready'" in source, (
            "D-WS-FLAP-003: admin.py must send session_ready primer event."
        )
        # primer must be in WS endpoint context
        ws_section_match = re.search(
            r"@router\.websocket\(['\"]/api/chat/ws['\"]\).*?(?=\n@router\.|\Z)",
            source,
            re.DOTALL,
        )
        assert ws_section_match is not None
        ws_section = ws_section_match.group(0)
        accept_idx = ws_section.find("websocket.accept(")
        primer_idx = ws_section.find("session_ready")
        loop_idx = ws_section.find("while True")
        assert accept_idx > 0 and primer_idx > accept_idx
        assert loop_idx > primer_idx


class TestCleanupTimer:
    def test_use_effect_cleanup_clears_debounce_timer(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # The cleanup function in useEffect should clear stateDebounceRef
        # to prevent leaking timers on unmount. We use a flexible regex that
        # finds the cleanup arrow function and checks its body contains
        # both `stateDebounceRef` and `clearTimeout`.
        cleanup_match = re.search(
            r"return\s*\(\s*\)\s*=>\s*\{(.*?)\};\s*\},\s*\[connect,",
            source,
            re.DOTALL,
        )
        assert cleanup_match is not None, "useEffect cleanup function not found"
        cleanup_body = cleanup_match.group(1)
        assert "stateDebounceRef" in cleanup_body, (
            "useEffect cleanup must reference stateDebounceRef to clear it on unmount."
        )
        assert "clearTimeout" in cleanup_body, "useEffect cleanup must call clearTimeout."
