"""
ReviewSchedulerSkill — جدولة المراجعة المتباعدة فوق الطبقة المعرفية (D-194).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill».

## المسؤولية الواحدة
تحويل **نتيجة تقييم BKT** إلى **موعد مراجعة تالٍ** — لا أكثر. لا تقيس الإتقان (BKT
يفعل)، ولا تُخزِّن (`ReviewScheduleService` يفعل)، ولا تُقرِّر ماذا يُعرَض للطالب.

## لماذا هذه المهارة موجودة
`BKTEngine` يحسب أصلاً `durable_mastery` و`delay_hours` و`support_level` — أي منحنى
نسيان وإشارة دعم — ثمّ **تُرمى كلّها** بعد سطر `logger.info`. الطالب يُقاس ولا يُذكَّر.
هذه المهارة هي الطرف المستقبِل: القياس يصير جدولاً.

## قاعدة التقدير — فجوة الوهم مُفعَّلة عملياً
إجابةٌ صحيحة **بدعمٍ ثقيل** لا تستحقّ فاصلاً طويلاً. هذا ليس تفصيلاً: هو الترجمة
التنفيذية للمقياس الوحيد المُعتمَد (§0.6 — فجوة الوهم = المدعوم − الدائم). لو منحنا
`EASY` لإجابةٍ سُقِّفت بالكامل، لبنينا جدولاً يقيس **الأداء اللحظي** ويؤخّر المراجعة
عن طالبٍ لم يتعلّم — أي أنّنا نُؤتمِت وَهْم الطلاقة بدل محاربته.

| إشارة BKT | التقدير | لماذا |
|-----------|---------|-------|
| `evidence_correct=False` | `AGAIN` | انتكاسة — الفاصل ينهار |
| صحيح · `support_level ≥ 5` · `durable ≥ 0.85` | `EASY` | غير مدعوم + دائم = إتقان حقيقي |
| صحيح · `support_level ≥ 3` | `GOOD` | دعم خفيف |
| صحيح · دعم ثقيل | `HARD` | أداء مدعوم — فاصل قصير عمداً |
| `correctness_signal="unknown"` | — | **لا قرار**: لا دليل ⇒ لا تعديل للجدول |

## الاستقلالية
لا تستورد مهارةً أخرى. المحرّك الرياضي في `shared/scheduling/fsrs.py` (dep-free).

## القياس (Prometheus)
- `cogniforge_skill_review_scheduler_invocations_total{rating,outcome}`
- `cogniforge_skill_review_scheduler_duration_seconds`
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Final

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from shared.scheduling.fsrs import (
    Rating,
    ReviewState,
    SchedulingError,
    initial_state,
    interval_days,
    review,
)

__all__ = [
    "ReviewDecision",
    "ReviewSchedulerInput",
    "ReviewSchedulerSkill",
    "get_review_scheduler_skill",
]

#: عتبة الدعم التي تُعتبر عندها الإجابة «غير مدعومة» (سُلّم الدعم الخماسي، D-113 ج2).
UNAIDED_SUPPORT_LEVEL: Final = 5
#: عتبة الدعم الخفيف — دونها يُعتبر الأداء مدعوماً بثقل.
LIGHT_SUPPORT_LEVEL: Final = 3
#: عتبة الإتقان الدائم التي تسمح بتقدير `EASY`.
DURABLE_MASTERY_FOR_EASY: Final = 0.85

_INVOCATIONS = skill_counter(
    "cogniforge_skill_review_scheduler_invocations_total",
    "Total review-scheduler invocations",
    ("rating", "outcome"),
)
_DURATION = skill_histogram(
    "cogniforge_skill_review_scheduler_duration_seconds",
    "Review-scheduler decision duration",
)


class ReviewSchedulerInput(RobustBaseModel):
    """مدخلات القرار — كلّها مُشتقّة من تقييم BKT، فلا قياس مُكرَّر."""

    concept_id: str = Field(..., min_length=1, max_length=120)
    evidence_correct: bool = Field(..., description="هل دلّ التفاعل على استرجاع ناجح")
    correctness_signal: str = Field(
        "unknown", description="correct | incorrect | unknown — مصدره الأوراكل الرمزي"
    )
    durable_mastery: float = Field(0.0, ge=0.0, le=1.0)
    support_level: int | None = Field(
        None, ge=1, le=5, description="١ دعم كامل … ٥ بلا دعم (D-113)"
    )


class ReviewDecision(RobustBaseModel):
    """مخرَج القرار. `state is None` يعني: لا دليل ⇒ لا تعديل للجدول."""

    concept_id: str
    rating: int | None = None
    scheduled: bool = False
    reason: str = ""
    stability: float | None = None
    difficulty: float | None = None
    due_at: datetime | None = None
    interval_days: float | None = None
    lapses: int | None = None
    state: str | None = None


def derive_rating(payload: ReviewSchedulerInput) -> Rating | None:
    """
    يشتقّ تقدير المراجعة من إشارات BKT — حتمي تماماً، صفر LLM.

    يُرجِع `None` حين لا يوجد دليل: الجدولة على لا-دليل ضجيجٌ يُغرِق الطالب
    بمراجعاتٍ لم يُثبِت شيءٌ أنّه يحتاجها (§0: المجهول أفضل من يقين زائف).
    """
    if payload.correctness_signal == "unknown":
        return None
    if not payload.evidence_correct:
        return Rating.AGAIN

    support = payload.support_level if payload.support_level is not None else 1
    if support >= UNAIDED_SUPPORT_LEVEL and payload.durable_mastery >= DURABLE_MASTERY_FOR_EASY:
        return Rating.EASY
    if support >= LIGHT_SUPPORT_LEVEL:
        return Rating.GOOD
    return Rating.HARD


class ReviewSchedulerSkill(BaseSkill[ReviewSchedulerInput, ReviewDecision]):
    """يحوّل تقييماً معرفياً إلى موعد المراجعة التالي."""

    name = "review_scheduler"
    version = "1.0.0"

    def decide(
        self,
        payload: ReviewSchedulerInput,
        *,
        now: datetime,
        previous: ReviewState | None = None,
    ) -> ReviewDecision:
        """يُطبِّق FSRS على الحالة السابقة (أو يُنشئها) ويُرجِع القرار.

        **لا يرفع أبداً** لمُستدعيه: المسار الحيّ مسارُ طالب، وفشل الجدولة يجب أن
        يُبلَّغ لا أن يُسقِط الدور (نفس عزل BKT — D-074).
        """
        started = time.perf_counter()
        rating = derive_rating(payload)

        if rating is None:
            _INVOCATIONS.labels(rating="none", outcome="skipped").inc()
            _DURATION.observe(time.perf_counter() - started)
            return ReviewDecision(
                concept_id=payload.concept_id,
                scheduled=False,
                reason="no_evidence",
            )

        try:
            state = (
                initial_state(rating, now) if previous is None else review(previous, rating, now)
            )
        except SchedulingError as exc:
            _INVOCATIONS.labels(rating=rating.name.lower(), outcome="error").inc()
            _DURATION.observe(time.perf_counter() - started)
            return ReviewDecision(
                concept_id=payload.concept_id,
                rating=int(rating),
                scheduled=False,
                reason=f"scheduling_error: {exc}",
            )

        _INVOCATIONS.labels(rating=rating.name.lower(), outcome="scheduled").inc()
        _DURATION.observe(time.perf_counter() - started)
        return ReviewDecision(
            concept_id=payload.concept_id,
            rating=int(rating),
            scheduled=True,
            reason="first_review" if previous is None else "recurring_review",
            stability=state.stability,
            difficulty=state.difficulty,
            due_at=state.due_at,
            interval_days=interval_days(state.stability),
            lapses=state.lapses,
            state=state.state,
        )

    def run(  # type: ignore[override]
        self,
        payload: ReviewSchedulerInput,
        *,
        now: datetime,
        previous: ReviewState | None = None,
    ) -> ReviewDecision:
        return self.decide(payload, now=now, previous=previous)


def get_review_scheduler_skill() -> ReviewSchedulerSkill:
    """نقطة الوصول الموحَّدة (singleton كسول عبر `BaseSkill.instance`)."""
    return ReviewSchedulerSkill.instance()
