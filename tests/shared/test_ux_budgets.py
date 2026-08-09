"""ميزانيات الإدراك — الحدود مُصرَّحة والتصنيف حتمي (D-230)."""

from __future__ import annotations

import pytest

from shared.ux import (
    ATTENTION_LIMIT_S,
    FIRST_OBJECT_PAINT_MS,
    FLOW_LIMIT_S,
    INSTANT_LIMIT_MS,
    LatencyVerdict,
    classify_latency,
)
from shared.ux.budgets import BudgetError


class TestDeclaredLimits:
    def test_limits_are_ordered(self) -> None:
        """السلّم مُرتَّب — حدٌّ أعلى من التالي يجعل التصنيف بلا معنى."""
        assert INSTANT_LIMIT_MS < FIRST_OBJECT_PAINT_MS
        assert FIRST_OBJECT_PAINT_MS / 1000 < FLOW_LIMIT_S < ATTENTION_LIMIT_S

    def test_doherty_threshold_is_400ms(self) -> None:
        """Brady, IBM Systems Journal 1982 — الرقم مرجعٌ لا تفضيل."""
        assert FIRST_OBJECT_PAINT_MS == 400

    def test_nielsen_limits(self) -> None:
        """0.1s فوري · 1s تدفّق · 10s حدّ الانتباه (Nielsen 1993)."""
        assert INSTANT_LIMIT_MS == 100
        assert FLOW_LIMIT_S == 1.0
        assert ATTENTION_LIMIT_S == 10.0


class TestClassification:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0.0, LatencyVerdict.INSTANT),
            (0.1, LatencyVerdict.INSTANT),
            (0.4, LatencyVerdict.FLOWING),
            (1.0, LatencyVerdict.FLOWING),
            (1.01, LatencyVerdict.NOTICEABLE),
            (9.99, LatencyVerdict.NOTICEABLE),
            (10.0, LatencyVerdict.ATTENTION_LOST),
            (72.57, LatencyVerdict.ATTENTION_LOST),
        ],
    )
    def test_boundaries(self, seconds: float, expected: LatencyVerdict) -> None:
        assert classify_latency(seconds) is expected

    def test_measured_production_p50_loses_flow(self) -> None:
        """p50 المقيس = 7.57s — داخل الانتباه، وخارج التدفّق تماماً."""
        assert classify_latency(7.57) is LatencyVerdict.NOTICEABLE

    def test_measured_production_p95_loses_attention(self) -> None:
        """p95 المقيس = 72.57s — الطالب ذهب."""
        assert classify_latency(72.57) is LatencyVerdict.ATTENTION_LOST

    def test_negative_is_an_error_not_an_optimistic_verdict(self) -> None:
        """⛔ قياسٌ فاسد يُعلَن ولا يُصنَّف «فوريّاً» (§0: لا صفر مضلِّل)."""
        with pytest.raises(BudgetError):
            classify_latency(-1.0)

    def test_determinism(self) -> None:
        assert {classify_latency(3.3) for _ in range(50)} == {LatencyVerdict.NOTICEABLE}
