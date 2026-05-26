"""
Regression test — verify D-WS-FLAP-004 (honest-debounce) UX is in place.

The Catastrophe (user-visible): even after D-WS-FLAP-002 + D-WS-FLAP-003,
the user reported "متصل في أجزاء من الثانية ثم تختفي" — the status indicator
flashes 'connected' for milliseconds then disappears. This happens regardless
of the underlying root cause (proxy idle-kill, network blips, React
re-render race, etc).

The Fix (D-WS-FLAP-004 — honest-debounce):
المبدأ المعماري الحاسم (طلب المستخدم): الـ UI **لا يكذب**. الحالة الداخلية
صادقة دائماً، والـ UI يتأخر قليلاً فقط (debounce 2s) قبل إظهار الانقطاع —
ثم يقول الحقيقة الكاملة بعد OFFLINE_GRACE_MS.

- blip < 2s: UI = "connected" (debounce قصير، تجنب flicker)
- disconnect 2s..15s: UI = "reconnecting" (الحقيقة)
- disconnect > 15s: UI = "offline" (الحقيقة الأصرح)
- auth_error: يطغى فوراً
- لـ debug/telemetry: internalState مكشوفة بشكل منفصل

This test verifies by static inspection that:
1. Hook declares separate `uiState` and exposes `internalState` for honesty.
2. `RECONNECT_VISIBLE_MS` ≈ 2000ms — short enough for honesty.
3. `OFFLINE_GRACE_MS` ≈ 15000ms — reasonable maximum delay.
4. `everConnectedRef` is set in `onopen`.
5. UI promotion is graduated (connected → reconnecting → offline) not all-or-nothing.
6. Hook returns both `state: uiState` and `internalState: state`.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestHonestDebounceUiState:
    def test_separate_ui_state_declared(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "uiState" in source, (
            "D-WS-FLAP-004: must declare separate `uiState` for honest-debounce UX."
        )
        assert re.search(r"const\s+\[uiState\s*,\s*setUiState\]\s*=\s*useState", source), (
            "uiState must be a useState hook."
        )

    def test_ever_connected_ref_exists(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "everConnectedRef" in source, "Must track first-ever-connection flag."

    def test_ever_connected_set_in_onopen(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        onopen_match = re.search(r"ws\.onopen\s*=\s*\(\s*\)\s*=>\s*\{(.*?)\};", source, re.DOTALL)
        assert onopen_match is not None
        onopen_body = onopen_match.group(1)
        assert "everConnectedRef.current = true" in onopen_body

    def test_reconnect_visible_window_is_short(self) -> None:
        """UI لا يكذب طويلاً — بعد 2s فقط من الفقد، يُظهر "reconnecting"."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "RECONNECT_VISIBLE_MS" in source, (
            "Must define RECONNECT_VISIBLE_MS — short window before UI shows reconnect."
        )
        match = re.search(r"RECONNECT_VISIBLE_MS\s*=\s*(\d+)", source)
        assert match
        ms = int(match.group(1))
        assert 1000 <= ms <= 3000, (
            f"RECONNECT_VISIBLE_MS must be 1000-3000ms (got {ms}). "
            "Lower bound prevents flicker; upper bound prevents lying."
        )

    def test_offline_grace_reasonable(self) -> None:
        """UI يظهر "offline" بعد فترة معقولة، ليست طويلة جداً (لا يخفي مشاكل حقيقية)."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        assert "OFFLINE_GRACE_MS" in source
        match = re.search(r"OFFLINE_GRACE_MS\s*=\s*(\d+)", source)
        assert match
        ms = int(match.group(1))
        # 10s minimum — يتيح وقت لـ reconnect.
        # 30s maximum — لا يخفي انقطاع حقيقي.
        assert 10000 <= ms <= 30000, (
            f"OFFLINE_GRACE_MS must be 10000-30000ms (got {ms}). "
            "Lower bound = enough time for retry. Upper bound = honesty to user."
        )

    def test_graduated_ui_promotion_exists(self) -> None:
        """التطوير المُدرَّج: connected → reconnecting → offline (ليس all-or-nothing)."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # يجب أن يوجد timer للترقية
        assert "uiPromotionTimerRef" in source, (
            "Must have uiPromotionTimerRef for graduated promotion."
        )
        # ويجب أن يُجدول الترقية
        assert "scheduleUiPromotionForDisconnect" in source or re.search(
            r"setUiState\(\s*[\"']reconnecting[\"']", source
        ), "Must promote to 'reconnecting' state after debounce."

    def test_hook_exposes_both_states(self) -> None:
        """صدق إلزامي: hook يجب أن يكشف internalState للـ debug/telemetry."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # state: uiState للـ UI
        assert re.search(r"state:\s*uiState", source), "Hook MUST return uiState as 'state'."
        # internalState: state للـ honesty/debug
        assert re.search(r"internalState:\s*state", source), (
            "D-WS-FLAP-004 honesty rule: hook MUST expose internalState for "
            "debugging and telemetry. The UI may debounce, but the internal "
            "truth must remain visible to code that needs it."
        )

    def test_auth_error_overrides_debounce(self) -> None:
        """auth_error حقيقي — لا debounce، يُظهر فوراً."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # يجب وجود branch صريح للـ auth_error قبل أي debounce
        assert re.search(r'state\s*===\s*"auth_error"', source), (
            "auth_error must be checked explicitly to override debounce."
        )

    def test_ui_promotion_timer_cleared_on_unmount(self) -> None:
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        cleanup_match = re.search(
            r"return\s*\(\s*\)\s*=>\s*\{(.*?)\};\s*\},\s*\[connect,",
            source,
            re.DOTALL,
        )
        assert cleanup_match is not None
        cleanup_body = cleanup_match.group(1)
        assert "uiPromotionTimerRef" in cleanup_body, (
            "useEffect cleanup must clear uiPromotionTimerRef."
        )

    def test_internal_state_never_lies(self) -> None:
        """قاعدة معمارية حاسمة: state (internal) يجب أن يُحدَّث في كل blip."""
        source = _read("frontend/app/hooks/useRealtimeConnection.js")
        # setState("reconnecting") و setState("connected") و setState("offline")
        # كلها يجب أن تُستدعى على internal state — لا توجد طبقة وسطى تخفيها.
        assert re.search(r"setState\(\s*[\"\']connected[\"\']", source) or re.search(
            r"setState\(\s*wasReconnect\s*\?\s*[\"\']recovered[\"\']", source
        ), "setState must update internal state on connect."
        assert re.search(r"setState\(\s*[\"\']reconnecting[\"\']", source), (
            "setState must update internal state on reconnect — keeping truth."
        )
        assert re.search(r"setState\(\s*[\"\']offline[\"\']", source), (
            "setState must update internal state on offline — keeping truth."
        )
