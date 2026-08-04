"""محرّك فجوة الوهم — حتمي 100%، صفر LLM، dep-free (D-212).

يحوّل عقيدة «فجوة الوهم» (CLAUDE.md §0.6) من إشارةٍ تشخيصية داخلية إلى **مخرَجٍ**
قابل للعرض على الوليّ. ثلاث كمّيات لكل مفهوم:

1. **الثقة المُعلَنة** — تُلتقط بضغطةٍ واحدة **قبل** الإجابة.
2. **الإتقان الدائم غير المدعوم** — القناة `durable` من `bkt_engine`، مضروبةً في قابلية
   الاسترجاع من ``shared/scheduling/fsrs`` (مفهومٌ أُتقن قبل شهرٍ ولم يُراجَع **ليس**
   مُتقناً اليوم — وهذا بالضبط ما ينهار يوم الامتحان).
3. **الفجوة** = الأولى ناقص الثانية.

⛔ **لا استيراد من ``app``** — هذه الوحدة تُورَّد إلى المونوليث والخدمات معاً، فتستقبل
الإتقان وقابلية الاسترجاع **وسائطَ** ولا تعرف BKT ولا قاعدة بيانات.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from shared.curriculum import CurriculumError, concept, exam_weight
from shared.illusion.model import (
    MIN_OBS,
    ConceptIllusion,
    IllusionError,
    Quadrant,
    quadrant_for,
)
from shared.scheduling.fsrs import SchedulingError, retrievability

__all__ = [
    "classify",
    "dangerous_concepts",
    "durable_after_decay",
    "illusion_gap_index",
]


def _unit_interval(value: float, label: str) -> float:
    """يتحقّق أن القيمة احتمالٌ صالح. يرفع ولا يقصّ بصمت."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise IllusionError(f"{label} must be a real number, got {value!r}")
    numeric = float(value)
    if not math.isfinite(numeric) or not 0.0 <= numeric <= 1.0:
        raise IllusionError(f"{label} must be finite in [0,1], got {value!r}")
    return numeric


def durable_after_decay(
    durable_mastery: float,
    elapsed_days: float,
    stability: float,
) -> float:
    """الإتقان الدائم **كما هو اليوم**: `durable × R(Δt, S)`.

    الضرب في قابلية الاسترجاع مقصود وليس تجميلاً — بدونه يُحسَب مفهومٌ لم يُلمَس منذ
    ستّة أسابيع كأنه مُتقَن، فيُخفي المحرّكُ النسيانَ الذي وُجد ليكشفه. هذا هو الفرق
    بين **قياس** و**تخزين**.
    """
    durable = _unit_interval(durable_mastery, "durable_mastery")
    try:
        recall = retrievability(elapsed_days, stability)
    except SchedulingError as exc:  # نُترجم ولا نبتلع: الحدود تبقى منطوقة
        raise IllusionError(f"retrievability rejected the interval: {exc}") from exc
    return durable * recall


def classify(
    concept_id: str,
    *,
    confidence: float,
    durable_mastery: float,
    unaided_observations: int,
) -> ConceptIllusion | None:
    """يُصنّف مفهوماً واحداً، أو يُرجِع ``None`` إن لم ينضج القياس.

    ``None`` ليست فشلاً بل **امتناعاً معلَناً**: دون ``MIN_OBS`` ملاحظةً غير مدعومة لا
    لون ولا خانة ولا ادّعاء. مَن يعرض «مُتقَن» بملاحظتين يبيع تقريراً فارغاً، ومَن
    يكتشف ذلك من الأولياء لا يجدّد.

    ``durable_mastery`` يجب أن يكون **بعد** تطبيق ``durable_after_decay`` — المُنادي هو
    من يملك تاريخ المراجعة، لا هذه الوحدة.
    """
    if not concept_id or not concept_id.strip():
        raise IllusionError("concept_id must be a non-empty identifier")
    try:
        # المُعرَّف يُحسَم في `shared/curriculum` وحده (D-193)، ويُطبَّع عبر صيغه البديلة.
        # ولو قبلنا مُعرَّفاً مجهولاً هنا لانفجر لاحقاً عند حساب الوزن — بعد أن يكون قد
        # لُوِّن في الخريطة، أي أن العطب يظهر متأخّراً وفي المكان الخطأ.
        canonical = concept(concept_id.strip()).concept_id
    except CurriculumError as exc:
        raise IllusionError(f"unknown concept_id: {concept_id!r}") from exc
    if not isinstance(unaided_observations, int) or isinstance(unaided_observations, bool):
        raise IllusionError(f"unaided_observations must be an int, got {unaided_observations!r}")
    if unaided_observations < 0:
        raise IllusionError(f"unaided_observations cannot be negative, got {unaided_observations}")

    conf = _unit_interval(confidence, "confidence")
    durable = _unit_interval(durable_mastery, "durable_mastery")

    if unaided_observations < MIN_OBS:
        return None

    return ConceptIllusion(
        concept_id=canonical,
        confidence=conf,
        durable_mastery=durable,
        gap=round(conf - durable, 4),
        quadrant=quadrant_for(conf, durable),
        observations=unaided_observations,
    )


def dangerous_concepts(
    measurements: Iterable[ConceptIllusion | None],
) -> tuple[ConceptIllusion, ...]:
    """الخانة الحمراء وحدها، مرتّبةً بالفجوة تنازلياً.

    تتجاوز ``None`` بصمت **بالتصميم**: القياس غير الناضج ليس «غير خطر»، بل غير معروف —
    وإدراجه بأي لون يحوّل الامتناع إلى ادّعاء.
    """
    mature = [m for m in measurements if m is not None and m.is_dangerous]
    return tuple(sorted(mature, key=lambda m: (-m.gap, m.concept_id)))


def illusion_gap_index(
    measurements: Iterable[ConceptIllusion | None],
    stream: str,
) -> float | None:
    """مؤشّر واحد للوليّ: `IGI = Σ wᶜ·max(0,gapᶜ) / Σ wᶜ`.

    الوزن ``wᶜ`` هو ``shared.curriculum.exam_weight`` (معامل المادة × تواتر الظهور) —
    **لا مصدر ثانٍ للأوزان** (D-193). ونأخذ ``max(0, gap)`` لأن المهارة المخفيّة
    (ثقةٌ أقلّ من الإتقان) ليست وهماً يُخصم منه؛ متوسّطٌ يجمع الاتجاهين يُظهر طالباً
    واثقاً ومخطئاً في نصف المنهاج كأنه معتدل.

    يُرجِع ``None`` إن لم يوجد قياسٌ ناضجٌ واحد بوزنٍ موجب — الامتناع نفسه (لا صفراً،
    فالصفر يقرأ «لا وهم لديه» وهو أخطر جملة يمكن أن يقرأها وليّ).
    """
    if not stream or not stream.strip():
        raise IllusionError("stream must be a non-empty identifier")

    total_weight = 0.0
    weighted_gap = 0.0
    for measurement in measurements:
        if measurement is None:
            continue
        try:
            weight = exam_weight(measurement.concept_id, stream.strip())
        except CurriculumError as exc:  # شعبةٌ مجهولة تُقال، لا تُبتلع ولا تُسقِط الاستدعاء
            raise IllusionError(f"curriculum rejected the weighting: {exc}") from exc
        if weight <= 0.0:
            continue  # الشعبة لا تدرس المفهوم — إدراجه يخفّف مؤشّراً ليس له
        total_weight += weight
        weighted_gap += weight * max(0.0, measurement.gap)

    if total_weight <= 0.0:
        return None
    return round(weighted_gap / total_weight, 4)


def quadrant_counts(
    measurements: Iterable[ConceptIllusion | None],
) -> Mapping[str, int]:
    """توزيع الخانات — للوحات والمقاييس. القياسات غير الناضجة **لا تُحتسَب**."""
    counts = {quadrant.value: 0 for quadrant in Quadrant}
    for measurement in measurements:
        if measurement is None:
            continue
        counts[measurement.quadrant.value] += 1
    return counts
