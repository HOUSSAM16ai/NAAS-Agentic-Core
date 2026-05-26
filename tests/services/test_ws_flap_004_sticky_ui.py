"""
Regression test — verify D-WS-FLAP-004 sticky-connected UX is in place.

The Catastrophe (user-visible): even after D-WS-FLAP-002 + D-WS-FLAP-003,
the user reported "متصل في أجزاء من الثانية ثم تختفي" — the status indicator
flashes 'connected' for milliseconds then disappears. This happens regardless
of the underlying root cause (proxy idle-kill, network blips, React
re-render race, etc).

The Fix (D-WS-FLAP-004): SEPARATE the internal connection state from the
UI state. Once the connection succeeds even ONCE, the UI stays 'connected'
forever — internal reconnects happen silently. This is a UX-first fix that
works regardless of WHY the underlying connection is unstable.

This test verifies by static inspection that:
1. `useRealtimeConnection` declares a separate `uiState` from `state`.
2. `everConnectedRef` is set in `onopen`.
3. `computeUiState` maps `reconnecting/degraded/connecting` to `connected`
   after first successful connection.
4. There is an offline grace period before showing `offline` in UI.
5. The hook returns `uiState` as the public `state`.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestStickyConnectedUiState:
    def test_separate_ui_state_declared(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert 'useState("idle")' in source or 'useState("idle")' in source
        # uiState should be a separate state
        assert "uiState" in source, "D-WS-FLAP-004: must declare separate `uiState` for sticky UX."
        assert re.search(r"const\s+\[uiState\s*,\s*setUiState\]\s*=\s*useState", source), (
            "uiState must be a useState hook."
        )

    def test_ever_connected_ref_exists(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "everConnectedRef" in source, (
            "Must track first-ever-connection flag for sticky behavior."
        )

    def test_ever_connected_set_in_onopen(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # onopen block must set everConnectedRef.current = true
        onopen_match = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};", source, re.DOTALL)
        assert onopen_match is not None
        onopen_body = onopen_match.group(1)
        assert "everConnectedRef.current = true" in onopen_body, (
            "onopen must mark connection as ever-connected for sticky UX."
        )

    def test_compute_ui_state_maps_silently(self) -> None:
        """After first connection, reconnecting/degraded/connecting → connected (no flicker)."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        compute_match = re.search(
            r"const\s+computeUiState\s*=\s*useCallback\(.*?\}\s*,\s*\[",
            source,
            re.DOTALL,
        )
        assert compute_match is not None, "computeUiState function must exist"
        body = compute_match.group(0)
        # Must check everConnectedRef
        assert "everConnectedRef.current" in body
        # reconnecting/degraded/connecting must all collapse to "connected"
        for s in ("reconnecting", "degraded", "connecting"):
            assert f'"{s}"' in body, f"computeUiState must reference '{s}' state"

    def test_offline_grace_period(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "OFFLINE_GRACE_MS" in source, (
            "Must define grace period before showing 'offline' in UI."
        )
        match = re.search(r"OFFLINE_GRACE_MS\s*=\s*(\d+)", source)
        assert match
        grace_ms = int(match.group(1))
        assert grace_ms >= 15000, (
            f"OFFLINE_GRACE_MS must be >= 15000ms (got {grace_ms}) for proper UX."
        )

    def test_hook_returns_ui_state(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # Must return uiState as the public 'state' field
        assert re.search(r"return\s*\{\s*state:\s*uiState", source), (
            "Hook MUST return uiState (not internal state) to consumers."
        )

    def test_offline_grace_timer_cleared_on_unmount(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        cleanup_match = re.search(
            r"return\s*\(\s*\)\s*=>\s*\{(.*?)\};\s*\},\s*\[connect,",
            source,
            re.DOTALL,
        )
        assert cleanup_match is not None
        cleanup_body = cleanup_match.group(1)
        assert "offlineGraceTimerRef" in cleanup_body, (
            "useEffect cleanup must clear offlineGraceTimerRef."
        )
