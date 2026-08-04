"""D-212 — دون `MIN_OBS`: لا لون ولا خانة ولا ادّعاء.

القاعدة التي تحمي المصداقية التجارية للمنتج كلّه، على سابقة
`shared/analytics/retention.py` حرفياً: **الفوج غير الناضج يُرجِع `None` لا صفراً** —
صفرٌ يقرأ «فقدناهم» والحقيقة «لم يحن الوقت».

تقريرٌ يلوّن كلّ المنهاج بعد جلستين هو **تقريرٌ كاذب**، والوليّ الذي يكتشف ذلك لا يجدّد
أبداً. فالامتناع هنا ليس نقصاً في الميزة — هو الميزة.
"""

from __future__ import annotations

import pytest

from shared.illusion import MIN_OBS, classify, dangerous_concepts, illusion_gap_index

CONCEPT = "sequences"
STREAM = "experimental_sciences"


@pytest.mark.parametrize("observations", list(range(MIN_OBS)))
def test_below_min_obs_returns_none(observations: int) -> None:
    """أيّ عددٍ دون العتبة ⇒ `None`، مهما كانت الأرقام مغرية."""
    assert (
        classify(
            CONCEPT,
            confidence=0.95,
            durable_mastery=0.95,
            unaided_observations=observations,
        )
        is None
    )


def test_at_min_obs_classifies() -> None:
    """العتبة شاملة — وإلّا كان الحدّ الفعلي `MIN_OBS + 1` بلا أن يقول أحد ذلك."""
    assert (
        classify(
            CONCEPT,
            confidence=0.95,
            durable_mastery=0.95,
            unaided_observations=MIN_OBS,
        )
        is not None
    )


def test_immature_never_reaches_the_red_quadrant() -> None:
    """قياسٌ غير ناضج ليس «غير خطر» — هو **غير معروف**، فلا يُدرَج بأي لون."""
    immature = classify(
        CONCEPT, confidence=0.99, durable_mastery=0.01, unaided_observations=MIN_OBS - 1
    )
    assert immature is None
    assert dangerous_concepts([immature]) == ()


def test_immature_does_not_move_the_parent_facing_index() -> None:
    """ملاحظتان لا تُنتجان رقماً يُعرَض على وليّ."""
    immature = classify(CONCEPT, confidence=0.99, durable_mastery=0.01, unaided_observations=2)
    assert illusion_gap_index([immature], STREAM) is None
