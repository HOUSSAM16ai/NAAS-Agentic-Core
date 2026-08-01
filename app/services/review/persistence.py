"""
تخزين جدول المراجعة المتباعدة (D-194).

يربط `ReviewSchedulerSkill` (القرار) بجدول `student_review_schedule` (التخزين):

1. `latest_state(user_id, concept_id)` — يقرأ أحدث حالة FSRS ويُعيد بناءها.
2. `schedule_from_evaluation(...)` — التنسيق الكامل: يقرأ الحالة السابقة ⇒ يستدعي
   المهارة ⇒ يُدرج الصفّ (مُلحَق-فقط) ⇒ يُرجِع القرار.
3. `due_reviews(user_id, now)` — طابور اليوم، مرتّباً بوزن الامتحان.

**العزل**: نقطة الدخول من مسار الطالب (`schedule_from_evaluation`) لا ترفع أبداً.
فشل الجدولة يُسجَّل ويُبتلَع — تماماً كـBKT (D-074: «BKT لا يكسر الدردشة أبداً»).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.review_schedule import StudentReviewSchedule
from app.services.skills.review_scheduler_skill import (
    ReviewDecision,
    ReviewSchedulerInput,
    get_review_scheduler_skill,
)
from shared.curriculum import CurriculumError, concept, exam_weight, label
from shared.scheduling.fsrs import ReviewState, SchedulingError

logger = logging.getLogger("cogniforge.review.schedule")

#: الشعبة الافتراضية لترتيب الطابور حتى تُخزَّن شعبة الطالب على حسابه.
DEFAULT_STREAM = "experimental_sciences"


@dataclass(frozen=True)
class DueReview:
    """عنصرٌ مستحقّ في طابور المراجعة، مع ما يكفي لعرضه دون استعلامٍ ثانٍ."""

    concept_id: str
    title: str
    due_at: datetime
    overdue_days: float
    stability: float
    difficulty: float
    lapses: int
    exam_weight: float


def _as_utc(moment: datetime) -> datetime:
    """
    يضمن أنّ الزمن واعٍ بالمنطقة الزمنية.

    SQLite يُعيد أزمنةً عارية حتى لو كُتبت واعية، وFSRS يرفض العارية عمداً. بلا هذا
    التطبيع تنكسر الجدولة في الاختبارات وفي أيّ نشرٍ على SQLite بينما تعمل على
    Postgres — أسوأ صنف عطب: يعتمد على المحرّك.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


class ReviewScheduleService:
    """خدمة جدولة المراجعة — تعمل ضمن جلسة `AsyncSession` واحدة."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def latest_state(self, user_id: int, concept_id: str) -> ReviewState | None:
        """يُعيد بناء أحدث حالة FSRS لهذا (طالب، مفهوم)، أو `None` لأول لقاء."""
        stmt = (
            select(StudentReviewSchedule)
            .where(
                StudentReviewSchedule.user_id == user_id,
                StudentReviewSchedule.concept_id == concept_id,
            )
            .order_by(desc(StudentReviewSchedule.reviewed_at), desc(StudentReviewSchedule.id))
            .limit(1)
        )
        row = await self.db.scalar(stmt)
        if row is None:
            return None
        try:
            return ReviewState(
                stability=row.stability,
                difficulty=row.difficulty,
                due_at=_as_utc(row.due_at),
                last_reviewed_at=_as_utc(row.reviewed_at),
                reps=row.reps,
                lapses=row.lapses,
                state=row.state,
            )
        except SchedulingError as exc:
            # صفٌّ تالف لا يجوز أن يُجمِّد جدول الطالب إلى الأبد — نبدأ من جديد بصوت.
            logger.warning(
                "review_state_corrupt user_id=%s concept=%s: %s", user_id, concept_id, exc
            )
            return None

    async def schedule_from_evaluation(
        self,
        *,
        user_id: int,
        concept_id: str,
        evidence_correct: bool,
        correctness_signal: str,
        durable_mastery: float,
        support_level: int | None,
        now: datetime | None = None,
    ) -> ReviewDecision | None:
        """
        نقطة الدخول من مسار الطالب. **لا ترفع أبداً.**

        تُرجِع `None` عند أي تعذّر — المُستدعي يسجّل ويمضي؛ دورُ الطالب أهمّ من جدوله.
        """
        moment = now or datetime.now(UTC)
        try:
            previous = await self.latest_state(user_id, concept_id)
            # `reps` التراكمية تُشتقّ من الحالة السابقة داخل المحرّك؛ نحفظ الرقم الصحيح.
            decision = get_review_scheduler_skill().decide(
                ReviewSchedulerInput(
                    concept_id=concept_id,
                    evidence_correct=evidence_correct,
                    correctness_signal=correctness_signal,
                    durable_mastery=durable_mastery,
                    support_level=support_level,
                ),
                now=moment,
                previous=previous,
            )
            if not decision.scheduled:
                return decision
            reps = (previous.reps + 1) if previous is not None else 1
            self.db.add(
                StudentReviewSchedule(
                    user_id=user_id,
                    concept_id=decision.concept_id,
                    rating=int(decision.rating or 3),
                    stability=float(decision.stability or 1.0),
                    difficulty=float(decision.difficulty or 5.0),
                    reps=reps,
                    lapses=int(decision.lapses or 0),
                    state=decision.state or "review",
                    interval_days=float(decision.interval_days or 1.0),
                    reviewed_at=moment,
                    due_at=decision.due_at,  # type: ignore[arg-type]
                )
            )
            await self.db.commit()
            logger.info(
                "review_scheduled user_id=%s concept=%s rating=%s interval=%.2fd due=%s",
                user_id,
                decision.concept_id,
                decision.rating,
                decision.interval_days or 0.0,
                decision.due_at,
            )
            return decision
        except Exception as exc:
            logger.warning("review_scheduling_failed: %s", exc, exc_info=True)
            return None

    async def due_reviews(
        self,
        user_id: int,
        *,
        now: datetime | None = None,
        stream: str = DEFAULT_STREAM,
        limit: int = 20,
    ) -> list[DueReview]:
        """
        طابور المراجعة المستحقّ، مرتّباً بوزن الامتحان ثمّ بالتأخّر.

        الترتيب ليس تجميلاً: وقت الطالب محدود، ومفهومٌ متواتر في مادةٍ معاملها ٦ يستحقّ
        الأسبقية على مفهومٍ نادر في مادةٍ معاملها ٢ (`shared/curriculum.exam_weight`).
        """
        moment = now or datetime.now(UTC)
        stmt = (
            select(StudentReviewSchedule)
            .where(StudentReviewSchedule.user_id == user_id)
            .order_by(desc(StudentReviewSchedule.reviewed_at), desc(StudentReviewSchedule.id))
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        # أحدث صفّ لكل مفهوم — السجلّ مُلحَق-فقط، فالأوّل في هذا الترتيب هو الحيّ.
        latest: dict[str, StudentReviewSchedule] = {}
        for row in rows:
            latest.setdefault(row.concept_id, row)

        due: list[DueReview] = []
        for concept_id, row in latest.items():
            due_at = _as_utc(row.due_at)
            if due_at > moment:
                continue
            try:
                title = concept(concept_id).title_ar
                weight = exam_weight(concept_id, stream)
            except CurriculumError:
                # مفهومٌ خُزِّن قبل توحيد السجلّ — يُعرَض بلا وزن بدل أن يختفي.
                title = label(concept_id)
                weight = 0.0
            due.append(
                DueReview(
                    concept_id=concept_id,
                    title=title,
                    due_at=due_at,
                    overdue_days=(moment - due_at).total_seconds() / 86400.0,
                    stability=row.stability,
                    difficulty=row.difficulty,
                    lapses=row.lapses,
                    exam_weight=weight,
                )
            )

        due.sort(key=lambda item: (-item.exam_weight, -item.overdue_days, item.concept_id))
        return due[:limit]


async def schedule_review_after_evaluation(
    *,
    user_id: int,
    concept_id: str,
    evidence_correct: bool,
    correctness_signal: str,
    durable_mastery: float,
    support_level: int | None,
    now: datetime | None = None,
) -> ReviewDecision | None:
    """
    نقطة الدخول من مسار الدردشة — **تملك جلستها بنفسها**.

    الجلسة تُفتَح هنا لا في المُوجِّه: المُوجِّه طبقة نقل، وإدارة الجلسات منطق نطاق
    (تفرضه بوّابة `check_router_domain_logic` بدَينٍ مُجمَّد يتقلّص فقط). وهي جلسة
    **مستقلّة** عن جلسة الدور كي لا يتلوّث دور الطالب بفشل جدولة (D-074).
    """
    from app.core.database import async_session_factory

    try:
        async with async_session_factory() as db:
            return await ReviewScheduleService(db).schedule_from_evaluation(
                user_id=user_id,
                concept_id=concept_id,
                evidence_correct=evidence_correct,
                correctness_signal=correctness_signal,
                durable_mastery=durable_mastery,
                support_level=support_level,
                now=now,
            )
    except Exception as exc:
        logger.warning("review_scheduling_session_failed: %s", exc, exc_info=True)
        return None


__all__ = [
    "DEFAULT_STREAM",
    "DueReview",
    "ReviewScheduleService",
    "schedule_review_after_evaluation",
]
