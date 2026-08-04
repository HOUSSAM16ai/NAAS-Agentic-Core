"""D-212 — التصنيف الرباعي لفجوة الوهم، والخانة الحمراء هي المنتج.

الاختبار يثبت الفصل الذي يقوم عليه المنتج كلّه: **فجوة معرفة** (يعرف أنه لا يعرف)
شيء، و**معرفة خاطئة راسخة** (واثقٌ ومخطئ) شيءٌ آخر تماماً — والثانية هي التي تُسقِط
في البكالوريا لأن صاحبها لا يراجعها أصلاً.
"""

from __future__ import annotations

import pytest

from shared.illusion import (
    ConceptIllusion,
    IllusionError,
    Quadrant,
    classify,
    dangerous_concepts,
    illusion_gap_index,
    quadrant_counts,
)

#: مفهومٌ حقيقي من سجلّ المنهاج — لا مُعرَّف مخترَع (D-193).
CONCEPT = "sequences"
STREAM = "experimental_sciences"


def _classify(confidence: float, durable: float, observations: int = 6) -> ConceptIllusion | None:
    return classify(
        CONCEPT,
        confidence=confidence,
        durable_mastery=durable,
        unaided_observations=observations,
    )


class TestQuadrants:
    def test_confident_and_wrong_is_dangerous(self) -> None:
        """🔴 الخانة التي يُباع بها المنتج."""
        measurement = _classify(0.90, 0.20)
        assert measurement is not None
        assert measurement.quadrant is Quadrant.DANGEROUS
        assert measurement.is_dangerous is True
        assert measurement.gap == pytest.approx(0.70)

    def test_confident_and_right_is_mastered(self) -> None:
        measurement = _classify(0.90, 0.88)
        assert measurement is not None
        assert measurement.quadrant is Quadrant.MASTERED

    def test_unsure_but_right_is_hidden_skill(self) -> None:
        """🔵 يحتاج ثقةً لا تعليماً — والفجوة سالبة."""
        measurement = _classify(0.15, 0.85)
        assert measurement is not None
        assert measurement.quadrant is Quadrant.HIDDEN_SKILL
        assert measurement.gap < 0

    def test_unsure_and_wrong_is_known_gap(self) -> None:
        measurement = _classify(0.15, 0.20)
        assert measurement is not None
        assert measurement.quadrant is Quadrant.KNOWN_GAP


class TestAggregation:
    def test_dangerous_only_and_sorted_by_gap(self) -> None:
        wide = _classify(0.95, 0.05)
        narrow = _classify(0.70, 0.50)
        safe = _classify(0.90, 0.90)
        assert dangerous_concepts([safe, narrow, wide, None]) == (wide, narrow)

    def test_index_ignores_hidden_skill_direction(self) -> None:
        """المهارة المخفيّة لا تُخصَم من الوهم.

        متوسّطٌ يجمع الاتجاهين يُظهر طالباً واثقاً ومخطئاً في نصف المنهاج «معتدلاً» —
        وهو بالضبط التقرير الذي يجعل الوليّ يطمئنّ في غير موضعه.
        """
        dangerous = _classify(0.90, 0.10)
        hidden = _classify(0.10, 0.90)
        assert illusion_gap_index([dangerous, hidden], STREAM) == pytest.approx(0.40)

    def test_index_is_none_when_no_weighted_measurement(self) -> None:
        """امتناعٌ لا صفر: «لا وهم لديه» أخطر جملة يمكن أن يقرأها وليّ."""
        assert illusion_gap_index([], STREAM) is None
        assert illusion_gap_index([None, None], STREAM) is None

    def test_quadrant_counts_skip_immature(self) -> None:
        counts = quadrant_counts([_classify(0.9, 0.1), None, _classify(0.9, 0.9)])
        assert counts["dangerous"] == 1
        assert counts["mastered"] == 1
        assert sum(counts.values()) == 2


class TestDomainGuards:
    @pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan")])
    def test_confidence_out_of_range_raises(self, confidence: float) -> None:
        with pytest.raises(IllusionError):
            _classify(confidence, 0.5)

    def test_negative_observations_raise(self) -> None:
        with pytest.raises(IllusionError):
            classify(CONCEPT, confidence=0.5, durable_mastery=0.5, unaided_observations=-1)

    def test_blank_concept_raises(self) -> None:
        with pytest.raises(IllusionError):
            classify("  ", confidence=0.5, durable_mastery=0.5, unaided_observations=9)

    def test_unknown_concept_raises_at_classification_not_later(self) -> None:
        """المُعرَّف يُحسَم في `shared/curriculum` وحده (D-193).

        لو قُبِل المجهول هنا لانفجر عند حساب الوزن — بعد أن يكون قد لُوِّن في الخريطة،
        أي أن العطب يظهر متأخّراً وفي المكان الخطأ.
        """
        with pytest.raises(IllusionError):
            classify(
                "not_a_real_concept", confidence=0.5, durable_mastery=0.5, unaided_observations=9
            )

    def test_unknown_stream_raises_from_the_index(self) -> None:
        with pytest.raises(IllusionError):
            illusion_gap_index([_classify(0.9, 0.1)], "not_a_real_stream")

    def test_blank_stream_raises(self) -> None:
        with pytest.raises(IllusionError):
            illusion_gap_index([_classify(0.9, 0.1)], "")

    def test_bool_is_not_a_probability(self) -> None:
        """`True` تعبر `0 <= x <= 1` صامتةً — والصمت هنا يعني ثقةً مخترَعة."""
        with pytest.raises(IllusionError):
            _classify(True, 0.5)  # type: ignore[arg-type]
