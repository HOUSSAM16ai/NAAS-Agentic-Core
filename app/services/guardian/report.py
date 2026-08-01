"""
التقرير الأسبوعي لوليّ الأمر (D-196).

**لماذا هذا هو مفتاح البقاء التجاري:** الوليّ يدفع والتلميذ يستعمل. كلّ منافسٍ يُحسِّن
تجربة التلميذ؛ التقرير الذي يرى فيه الوليّ ماذا راجع ابنه وأين تحسّن وأين يتعثّر هو ما
يجعله يجدّد الاشتراك.

**قواعد دائمة:**

1. **صفر LLM.** كلّ رقمٍ هنا تجميعٌ حتمي فوق `student_bkt_analytics` و
   `student_review_schedule` و`customer_messages`. الأرقام لا يُقرِّرها نموذج (§0.6).
2. **صفر إجابات.** التقرير يحمل **مفاهيم ومقادير**، ولا يمسّ نصّ محادثة قطّ. لو حمل
   مقتطفاً واحداً من الحوار لصار باباً خلفياً يلتفّ على القاعدة الذهبية السقراطية
   (D-113): الطالب يفتح تقرير وليّه فيقرأ الحلّ الذي مُنع منه. لذلك لا يستعلم هذا
   الملفّ عن عمود `content` أبداً — الحماية بنيوية لا مُرشِّح نصّي.
3. **فجوة الوهم مرئية للوليّ.** نعرض «المدعوم» و«الدائم» معاً: الأداء اللحظي المرتفع
   مع إتقانٍ دائم منخفض هو **التحذير** الذي يجب أن يراه الوليّ، لا أن يُخفى خلف رقمٍ
   واحدٍ مُطمئن.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.bkt_analytics import StudentBKTAnalytic
from app.core.domain.chat import CustomerConversation, CustomerMessage, MessageRole
from app.core.domain.review_schedule import StudentReviewSchedule
from shared.curriculum import CurriculumError, concept, label
from shared.habit import StreakSummary, summarize_streak

logger = logging.getLogger("cogniforge.guardian.report")

#: طول نافذة التقرير بالأيام.
REPORT_WINDOW_DAYS = 7

#: فجوة الوهم التي تُعتبر عندها المهارة «هشّة» — أداءٌ مدعوم يفوق الإتقان الدائم بوضوح.
FRAGILE_ILLUSION_GAP = 0.25


@dataclass(frozen=True)
class ConceptProgress:
    """تقدّم الطالب في مفهومٍ واحد خلال النافذة."""

    concept_id: str
    title: str
    subject: str
    interactions: int
    assisted_mastery: float
    durable_mastery: float
    illusion_gap: float
    improved: bool
    fragile: bool


@dataclass(frozen=True)
class WeeklyReport:
    """التقرير الكامل — مقادير ومفاهيم، بلا أيّ نصّ محادثة."""

    student_user_id: int
    period_start: datetime
    period_end: datetime
    active_days: int
    current_streak: int
    longest_streak: int
    sessions: int
    concepts_practised: int
    reviews_completed: int
    reviews_due_now: int
    strongest: tuple[ConceptProgress, ...]
    needs_attention: tuple[ConceptProgress, ...]
    all_concepts: tuple[ConceptProgress, ...]


def _subject_of(concept_id: str) -> str:
    try:
        return concept(concept_id).subject
    except CurriculumError:
        return "unknown"


class GuardianReportService:
    """يبني التقرير الأسبوعي — قراءة فقط، تجميع حتمي."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _activity_timestamps(self, student_user_id: int, since: datetime) -> list[datetime]:
        """
        طوابع نشاط الطالب من رسائله هو.

        `customer_messages` هو **الكاتب الواحد** لنشاط الطالب (§6.5)، فلا نُنشئ جدول
        نشاطٍ ثانياً يحتاج مزامنة ويخرج عن الحقيقة. نقرأ الطوابع فقط — لا `content`.
        """
        stmt = (
            select(CustomerMessage.created_at)
            .join(
                CustomerConversation,
                CustomerConversation.id == CustomerMessage.conversation_id,
            )
            .where(
                CustomerConversation.user_id == student_user_id,
                CustomerMessage.role == MessageRole.USER,
                CustomerMessage.created_at >= since,
            )
        )
        rows = await self.db.execute(stmt)
        return [row for row in rows.scalars().all() if row is not None]

    async def _concept_progress(
        self, student_user_id: int, since: datetime
    ) -> tuple[ConceptProgress, ...]:
        """يجمع تقدّم كل مفهوم: أوّل قراءة وآخر قراءة داخل النافذة."""
        stmt = (
            select(StudentBKTAnalytic)
            .where(
                StudentBKTAnalytic.user_id == student_user_id,
                StudentBKTAnalytic.interaction_timestamp >= since,
            )
            .order_by(StudentBKTAnalytic.interaction_timestamp)
        )
        rows = (await self.db.execute(stmt)).scalars().all()

        first: dict[str, StudentBKTAnalytic] = {}
        last: dict[str, StudentBKTAnalytic] = {}
        counts: dict[str, int] = {}
        for row in rows:
            first.setdefault(row.concept_id, row)
            last[row.concept_id] = row
            counts[row.concept_id] = counts.get(row.concept_id, 0) + 1

        progress: list[ConceptProgress] = []
        for concept_id, latest in last.items():
            gap = max(0.0, latest.student_mastery_probability - latest.durable_mastery)
            progress.append(
                ConceptProgress(
                    concept_id=concept_id,
                    title=label(concept_id),
                    subject=_subject_of(concept_id),
                    interactions=counts[concept_id],
                    assisted_mastery=round(latest.student_mastery_probability, 4),
                    durable_mastery=round(latest.durable_mastery, 4),
                    illusion_gap=round(gap, 4),
                    improved=(latest.durable_mastery > first[concept_id].durable_mastery + 1e-9),
                    fragile=gap >= FRAGILE_ILLUSION_GAP,
                )
            )
        progress.sort(key=lambda item: (-item.durable_mastery, item.concept_id))
        return tuple(progress)

    async def build(self, student_user_id: int, *, now: datetime | None = None) -> WeeklyReport:
        """يبني تقرير الأسبوع المنتهي عند `now`."""
        end = now or datetime.now(UTC)
        start = end - timedelta(days=REPORT_WINDOW_DAYS)

        timestamps = await self._activity_timestamps(student_user_id, start)
        streak: StreakSummary = summarize_streak(timestamps, now=end)
        progress = await self._concept_progress(student_user_id, start)

        sessions = await self.db.scalar(
            select(func.count(CustomerConversation.id)).where(
                CustomerConversation.user_id == student_user_id,
                CustomerConversation.created_at >= start,
            )
        )
        reviews_completed = await self.db.scalar(
            select(func.count(StudentReviewSchedule.id)).where(
                StudentReviewSchedule.user_id == student_user_id,
                StudentReviewSchedule.reviewed_at >= start,
            )
        )
        reviews_due = await self.db.scalar(
            select(func.count(func.distinct(StudentReviewSchedule.concept_id))).where(
                StudentReviewSchedule.user_id == student_user_id,
                StudentReviewSchedule.due_at <= end,
            )
        )

        # «يحتاج انتباهاً» = الهشّ أوّلاً (فجوة وهمٍ عالية)، ثمّ الأضعف إتقاناً دائماً.
        attention = sorted(progress, key=lambda item: (not item.fragile, item.durable_mastery))

        return WeeklyReport(
            student_user_id=student_user_id,
            period_start=start,
            period_end=end,
            active_days=streak.total_active_days,
            current_streak=streak.current_streak,
            longest_streak=streak.longest_streak,
            sessions=int(sessions or 0),
            concepts_practised=len(progress),
            reviews_completed=int(reviews_completed or 0),
            reviews_due_now=int(reviews_due or 0),
            strongest=progress[:3],
            needs_attention=tuple(attention[:3]),
            all_concepts=progress,
        )


__all__ = [
    "FRAGILE_ILLUSION_GAP",
    "REPORT_WINDOW_DAYS",
    "ConceptProgress",
    "GuardianReportService",
    "WeeklyReport",
]
