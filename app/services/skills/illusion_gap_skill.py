"""
IllusionGapSkill — فجوة الوهم كمخرَجٍ للوليّ، لا كإشارةٍ داخلية (D-212).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تحويل **الثقة المُعلَنة** + **الإتقان الدائم** + **تاريخ المراجعة** إلى **خريطة وهم**
قابلة للعرض. لا تقيس الإتقان (`BKTEngine` يفعل)، ولا تُجدوِل (`ReviewSchedulerSkill`
يفعل)، ولا تُخزِّن، ولا تقرّر ماذا يُعرَض للطالب.

## لماذا هذه المهارة موجودة
`bkt_engine.update_mastery_two_signal` يُنتج قناتين — `assisted` و`durable` — وفجوةُ
الوهم بينهما هي **مقياس النجاح الوحيد** المُعتمَد (§0.6). لكنها بقيت رقماً داخلياً:
لا الطالب يراها ولا الوليّ. وهذه المهارة هي الطرف المستقبِل — القياس يصير **خريطة**.

## القاعدة التي تحمي المصداقية
دون `MIN_OBS` ملاحظةً غير مدعومة: **لا تصنيف ولا لون** (`classify` تُرجِع `None`،
والمهارة تُبلِّغ `mature=false`). تقريرٌ يلوّن كلّ المنهاج بعد جلستين هو تقريرٌ كاذب،
والوليّ الذي يكتشف ذلك لا يجدّد أبداً. راقب `immature_suppressed` — ارتفاعه يعني أنّك
تبيع تقارير فارغة.

## ما لا يجوز ادّعاؤه
لا «نقيس الفهم». بل: نقيس الفجوة بين ثقةٍ **مُعلَنة** وأداءٍ **غير مدعوم بعد تأخير**.
إشارة سلوكية، لا قراءة للذهن.

## الاستقلالية
لا تستورد مهارةً أخرى. المحرّك الحتمي في `shared/illusion/` (dep-free)، والأوزان من
`shared/curriculum` — لا مصدر ثانٍ.

## القياس (Prometheus)
- `cogniforge_skill_illusion_gap_invocations_total{outcome}`
- `cogniforge_skill_illusion_gap_duration_seconds`
- `cogniforge_skill_illusion_gap_immature_suppressed_total` — حارس الأمانة
"""

from __future__ import annotations

import logging
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from shared.illusion import (
    ConceptIllusion,
    IllusionError,
    classify,
    dangerous_concepts,
    durable_after_decay,
    illusion_gap_index,
    quadrant_counts,
)

__all__ = [
    "ConceptMeasurement",
    "IllusionGapInput",
    "IllusionGapReport",
    "IllusionGapSkill",
    "get_illusion_gap_skill",
]

logger = logging.getLogger("cogniforge.skills.illusion_gap")

_INVOCATIONS = skill_counter(
    "cogniforge_skill_illusion_gap_invocations_total",
    "Total illusion-gap map invocations",
    ("outcome",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_illusion_gap_duration_seconds",
    "Illusion-gap map build duration",
)
#: حارس الأمانة: كم قياساً امتنعنا عن تصنيفه لعدم النضج. ارتفاعه إشارةُ تقاريرَ فارغة.
_IMMATURE = skill_counter(
    "cogniforge_skill_illusion_gap_immature_suppressed_total",
    "Concept measurements suppressed because observations < MIN_OBS",
    (),
)


class ConceptMeasurement(RobustBaseModel):
    """قياسٌ خام لمفهومٍ واحد — كلّه مُشتقّ من مخرجات BKT/FSRS القائمة."""

    concept_id: str = Field(..., min_length=1, max_length=120)
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="الثقة المُعلَنة **قبل** الإجابة (بعدها تتلوّث)"
    )
    durable_mastery: float = Field(
        ..., ge=0.0, le=1.0, description="القناة الدائمة من BKT (غير مدعومة)"
    )
    unaided_observations: int = Field(
        ..., ge=0, description="عدد المحاولات **غير المدعومة** — المدعومة لا تُعَدّ"
    )
    elapsed_days: float | None = Field(
        None, ge=0.0, description="أيامٌ منذ آخر مراجعة — لتطبيق منحنى النسيان"
    )
    stability: float | None = Field(None, gt=0.0, description="استقرار FSRS للمفهوم")


class IllusionGapInput(RobustBaseModel):
    """مدخلات بناء الخريطة."""

    stream: str = Field(..., min_length=1, max_length=60, description="شعبة البكالوريا")
    measurements: list[ConceptMeasurement] = Field(default_factory=list)


class ConceptIllusionOut(RobustBaseModel):
    """صفٌّ واحد في الخريطة."""

    concept_id: str
    confidence: float
    durable_mastery: float
    gap: float
    quadrant: str
    observations: int


class IllusionGapReport(RobustBaseModel):
    """الخريطة. `index is None` يعني: لا قياس ناضج بوزنٍ موجب — امتناعٌ لا صفر."""

    stream: str
    #: `IGI` الموزون بوزن الامتحان، أو `None` إن لم ينضج شيء.
    index: float | None = None
    concepts: list[ConceptIllusionOut] = Field(default_factory=list)
    #: الخانة الحمراء وحدها («واثقٌ ومخطئ») — وهي المنتج.
    dangerous: list[ConceptIllusionOut] = Field(default_factory=list)
    quadrants: dict[str, int] = Field(default_factory=dict)
    #: كم مفهوماً امتنعنا عن تصنيفه لعدم النضج. يُعرَض ولا يُخفى.
    immature_suppressed: int = 0
    reason: str = ""


def _to_out(measurement: ConceptIllusion) -> ConceptIllusionOut:
    return ConceptIllusionOut(
        concept_id=measurement.concept_id,
        confidence=measurement.confidence,
        durable_mastery=measurement.durable_mastery,
        gap=measurement.gap,
        quadrant=measurement.quadrant.value,
        observations=measurement.observations,
    )


class IllusionGapSkill(BaseSkill[IllusionGapInput, IllusionGapReport]):
    """يبني خريطة فجوة الوهم لطالبٍ واحد. حتمي 100%، صفر LLM."""

    name = "illusion_gap"
    version = "1.0.0"

    def build(self, payload: IllusionGapInput) -> IllusionGapReport:
        """يبني الخريطة.

        **لا يرفع أبداً** لمُستدعيه: نفس عزل BKT (D-074) — فشلُ قياسٍ يُبلَّغ في
        `reason` ولا يُسقِط دور طالب ولا تقرير وليّ.
        """
        started = time.perf_counter()
        matured: list[ConceptIllusion] = []
        suppressed = 0
        rejected = 0

        for raw in payload.measurements:
            try:
                durable = raw.durable_mastery
                if raw.elapsed_days is not None and raw.stability is not None:
                    durable = durable_after_decay(durable, raw.elapsed_days, raw.stability)
                verdict = classify(
                    raw.concept_id,
                    confidence=raw.confidence,
                    durable_mastery=durable,
                    unaided_observations=raw.unaided_observations,
                )
            except IllusionError:
                # قياسٌ خارج المجال لا يُلوَّن ولا يُسقِط الخريطة — يُعَدّ ويُبلَّغ.
                logger.warning("illusion_gap: rejected measurement for %s", raw.concept_id)
                rejected += 1
                continue
            if verdict is None:
                suppressed += 1
                _IMMATURE.inc()
                continue
            matured.append(verdict)

        try:
            index = illusion_gap_index(matured, payload.stream)
        except IllusionError as exc:
            _INVOCATIONS.labels(outcome="error").inc()
            _DURATION.observe(time.perf_counter() - started)
            return IllusionGapReport(
                stream=payload.stream,
                immature_suppressed=suppressed,
                reason=f"illusion_error: {exc}",
            )

        _INVOCATIONS.labels(outcome="built" if matured else "immature").inc()
        _DURATION.observe(time.perf_counter() - started)
        return IllusionGapReport(
            stream=payload.stream,
            index=index,
            concepts=[_to_out(m) for m in matured],
            dangerous=[_to_out(m) for m in dangerous_concepts(matured)],
            quadrants=dict(quadrant_counts(matured)),
            immature_suppressed=suppressed,
            reason=_reason(matured, suppressed, rejected),
        )

    def run(self, payload: IllusionGapInput) -> IllusionGapReport:  # type: ignore[override]
        return self.build(payload)


def _reason(matured: list[ConceptIllusion], suppressed: int, rejected: int) -> str:
    """سببٌ منطوق دائماً — الغياب لا يعني الغموض (D-206 · L11)."""
    if rejected:
        return f"partial: {rejected} measurement(s) out of domain"
    if not matured:
        return "no_mature_measurement" if suppressed else "no_measurements"
    return "built"


def get_illusion_gap_skill() -> IllusionGapSkill:
    """نقطة الوصول الموحَّدة (singleton كسول عبر `BaseSkill.instance`)."""
    return IllusionGapSkill.instance()
