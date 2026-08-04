"""D-212 — النظام يكتشف النسيان: مفهومٌ قديم ينزل من 🟢 إلى 🔴.

هذا أهمّ اختبار في الوحدة، لأنه يفصل بين **قياس** و**تخزين**. من يخزّن الإتقان يقول
«أتقنه في مارس» إلى الأبد؛ ومن يقيسه يعرف أن مفهوماً لم يُلمَس منذ ستّة أسابيع لم يعد
مُتقناً اليوم — وهذا بالضبط ما ينهار يوم الامتحان.

الضرب في قابلية الاسترجاع من `shared/scheduling/fsrs` هو ما يجعل الخريطة تصف **اليوم**
لا الماضي.
"""

from __future__ import annotations

import pytest

from shared.illusion import IllusionError, Quadrant, classify, durable_after_decay
from shared.scheduling.fsrs import retrievability

CONCEPT = "sequences"


def test_fresh_mastery_stays_green() -> None:
    """مراجعةٌ اليوم: قابلية الاسترجاع ١ فلا يتغيّر شيء."""
    durable = durable_after_decay(0.90, elapsed_days=0.0, stability=10.0)
    assert durable == pytest.approx(0.90)
    measurement = classify(
        CONCEPT, confidence=0.90, durable_mastery=durable, unaided_observations=8
    )
    assert measurement is not None
    assert measurement.quadrant is Quadrant.MASTERED


def test_stale_mastery_turns_red() -> None:
    """نفس الطالب، نفس الثقة، بعد ستّة أسابيع: 🟢 ⇒ 🔴 — والفجوة تنكشف."""
    fresh = classify(CONCEPT, confidence=0.90, durable_mastery=0.90, unaided_observations=8)
    assert fresh is not None and fresh.quadrant is Quadrant.MASTERED

    decayed = durable_after_decay(0.90, elapsed_days=42.0, stability=6.0)
    stale = classify(CONCEPT, confidence=0.90, durable_mastery=decayed, unaided_observations=8)
    assert stale is not None
    assert stale.quadrant is Quadrant.DANGEROUS
    assert stale.gap > fresh.gap


def test_decay_is_monotonic_in_elapsed_time() -> None:
    """كلّما طال الغياب نزل الإتقان — بلا استثناء."""
    values = [durable_after_decay(0.8, elapsed_days=d, stability=7.0) for d in (0, 3, 14, 60)]
    assert values == sorted(values, reverse=True)


def test_decay_matches_the_scheduler_curve() -> None:
    """لا منحنى نسيانٍ ثانٍ — نستهلك FSRS ولا نُعيد اشتقاقه (قاعدة المصدر الواحد)."""
    assert durable_after_decay(0.5, 10.0, 4.0) == pytest.approx(0.5 * retrievability(10.0, 4.0))


def test_scheduling_domain_errors_are_translated_not_swallowed() -> None:
    """حدود المُجدوِل تبقى منطوقة: استقرارٌ غير صالح يرفع، ولا يُنتج صفراً مضلِّلاً."""
    with pytest.raises(IllusionError):
        durable_after_decay(0.5, 10.0, 0.0)
    with pytest.raises(IllusionError):
        durable_after_decay(0.5, -1.0, 4.0)
