"""
Regression test — ensure the onopen handler doesn't reference deleted refs.

ROOT CAUSE (2026-05-26): During the D-WS-FLAP-004 honest-debounce refactor,
the `offlineGraceTimerRef` useRef was renamed to `uiPromotionTimerRef`,
but the `ws.onopen` handler was NOT updated. It still referenced
`offlineGraceTimerRef.current`, which threw `ReferenceError` on every
successful WebSocket handshake. Result: `setState("connected")` was never
called, and the user-facing "متصل" indicator NEVER appeared.

USER REPORT: "متصل لم تظهر إطلاقاً" — connected never appears at all.

This test ensures:
1. All `Ref.current` references inside the hook point to declared useRef calls.
2. The onopen handler reaches `setState("connected")` cleanly.
3. No dangling references from refactors.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestNoDanglingRefs:
    def test_all_ref_usages_are_declared(self) -> None:
        """Every `xxxRef.current` usage must point to a declared `useRef` variable."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")

        # Find all `const xxxRef = useRef(...)` declarations
        declared = set()
        for m in re.finditer(r"const\s+(\w+Ref)\s*=\s*useRef\(", source):
            declared.add(m.group(1))

        # Find all `xxxRef.current` usages
        used = set()
        for m in re.finditer(r"(\w+Ref)\.current", source):
            used.add(m.group(1))

        undefined = used - declared
        assert not undefined, (
            "ROOT CAUSE GUARD: useRealtimeConnection.js references undefined refs: "
            f"{sorted(undefined)}. This crashes the WS handler with ReferenceError. "
            "The D-WS-FLAP-004 regression that broke 'متصل' was caused by "
            "`offlineGraceTimerRef` being referenced in onopen after deletion."
        )

    def test_onopen_does_not_reference_offline_grace_timer(self) -> None:
        """Explicit guard for the specific bug that broke 'متصل'."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # Find onopen body
        m = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};", source, re.DOTALL)
        assert m is not None, "ws.onopen handler not found"
        onopen_body = m.group(1)

        # The dangling `offlineGraceTimerRef.current` must NOT appear in onopen
        assert "offlineGraceTimerRef.current" not in onopen_body, (
            "REGRESSION: onopen still references deleted `offlineGraceTimerRef`. "
            "This throws ReferenceError and prevents setState('connected') from "
            "ever being called, making 'متصل' invisible to the user. "
            "Use `uiPromotionTimerRef` instead (the renamed equivalent)."
        )

    def test_onopen_calls_setstate_connected(self) -> None:
        """onopen must reach setState('connected') — otherwise user never sees 'متصل'."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        m = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};", source, re.DOTALL)
        assert m is not None
        onopen_body = m.group(1)

        # Must call setState with "connected" or via wasReconnect ternary
        has_connected = bool(re.search(r"setState\(\s*[\"\']connected[\"\']", onopen_body))
        has_recovered = bool(
            re.search(r"setState\(\s*wasReconnect\s*\?\s*[\"\']recovered[\"\']", onopen_body)
        )
        assert has_connected or has_recovered, (
            "onopen must call setState with 'connected' (or wasReconnect ternary). "
            "Without this, the UI never shows 'متصل'."
        )

    def test_onopen_sets_ever_connected_flag(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        m = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};", source, re.DOTALL)
        assert m is not None
        onopen_body = m.group(1)

        assert "everConnectedRef.current = true" in onopen_body, (
            "onopen must mark everConnectedRef.current=true so the state-sync "
            "useEffect knows we're past the initial connection."
        )
