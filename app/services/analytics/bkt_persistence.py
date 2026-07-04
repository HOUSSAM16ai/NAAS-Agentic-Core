"""
BKT Analytics Persistence — كتابة لقطات تتبّع المعرفة إلى Supabase (append-only).

يربط بين `BKTEngine` (الحساب) و جدول `student_bkt_analytics` (التخزين):
1. `latest_mastery(user_id, concept_id)` — يقرأ آخر إتقان مسجَّل (prior).
2. `record_interaction(...)` — يُدرج صفاً جديداً (append-only).
3. `evaluate_and_record(...)` — orchestration: تقدير المفهوم أولاً → قراءة
   prior → تشغيل BKTEngine → إدراج الصف → إرجاع `BKTEvaluation`.

كل عملية كتابة async ولا ترفع استثناءات للمستدعي إلا عبر القناة المعتادة —
الـ router يلفّها في try/except حتى لا يكسر التحليلات مسار المحادثة أبداً.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.bkt_analytics import StudentBKTAnalytic
from app.services.skills.bkt_engine import (
    BKTEvaluation,
    BKTEvaluationInput,
    classify_concept_with_context,
    durable_update_continuous,
    get_bkt_engine,
    illusion_gap,
)
from app.services.skills.tutor_metrics import (
    record_durable_rise,
    record_illusion_gap,
    record_mastery_channels,
)

logger = logging.getLogger("cogniforge.analytics.bkt")


class BKTAnalyticsService:
    """خدمة تخزين تحليلات BKT — تعمل ضمن جلسة AsyncSession واحدة."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def latest_mastery(self, user_id: int, concept_id: str) -> float | None:
        """يُرجع آخر `student_mastery_probability` لهذا (طالب، مفهوم) أو None."""
        stmt = (
            select(StudentBKTAnalytic.student_mastery_probability)
            .where(
                StudentBKTAnalytic.user_id == user_id,
                StudentBKTAnalytic.concept_id == concept_id,
            )
            .order_by(desc(StudentBKTAnalytic.interaction_timestamp))
            .limit(1)
        )
        # `await db.scalar(...)` (SQLAlchemy 2.0 idiom) — استدعاء async واحد بلا
        # سلسلة `.scalar_one_or_none()` متزامنة تترك coroutine مُعلَّقاً عند
        # محاكاة الجلسة بـ AsyncMock في اختبارات الـ WS.
        row = await self.db.scalar(stmt)
        return float(row) if row is not None else None

    async def interaction_count(self, user_id: int, concept_id: str) -> int:
        """يُرجع عدد التفاعلات السابقة لهذا (طالب، مفهوم)."""
        stmt = (
            select(StudentBKTAnalytic.interaction_count)
            .where(
                StudentBKTAnalytic.user_id == user_id,
                StudentBKTAnalytic.concept_id == concept_id,
            )
            .order_by(desc(StudentBKTAnalytic.interaction_timestamp))
            .limit(1)
        )
        row = await self.db.scalar(stmt)
        return int(row) if row is not None else 0

    async def latest_durable_mastery(self, user_id: int, concept_id: str) -> float:
        """D-126: يُرجع آخر `durable_mastery` (القناة الدائمة الصادقة) أو 0.0."""
        stmt = (
            select(StudentBKTAnalytic.durable_mastery)
            .where(
                StudentBKTAnalytic.user_id == user_id,
                StudentBKTAnalytic.concept_id == concept_id,
            )
            .order_by(desc(StudentBKTAnalytic.interaction_timestamp))
            .limit(1)
        )
        row = await self.db.scalar(stmt)
        return float(row) if row is not None else 0.0

    async def _latest_timestamp(self, user_id: int, concept_id: str) -> datetime | None:
        """آخر وقت تفاعل لنفس (طالب، مفهوم) — لحساب delay_hours (أثر المباعدة)."""
        stmt = (
            select(StudentBKTAnalytic.interaction_timestamp)
            .where(
                StudentBKTAnalytic.user_id == user_id,
                StudentBKTAnalytic.concept_id == concept_id,
            )
            .order_by(desc(StudentBKTAnalytic.interaction_timestamp))
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def record_interaction(
        self,
        *,
        user_id: int,
        session_id: int | None,
        evaluation: BKTEvaluation,
        interaction_count: int,
    ) -> StudentBKTAnalytic:
        """يُدرج صف تحليلات جديداً (append-only) ويعيده محمَّلاً بـ id."""
        row = StudentBKTAnalytic(
            user_id=user_id,
            session_id=session_id,
            concept_id=evaluation.concept_id,
            cognitive_load_estimate=evaluation.cognitive_load_estimate,
            student_mastery_probability=evaluation.student_mastery_probability,
            interaction_count=interaction_count,
            # D-126: القناة الدائمة الصادقة + مدخلاتها (append-only).
            durable_mastery=evaluation.durable_mastery,
            support_level=evaluation.support_level,
            delay_hours=evaluation.delay_hours,
            novel_item=evaluation.novel_item,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def evaluate_and_record(
        self,
        *,
        user_id: int,
        session_id: int | None,
        question: str,
        history: list[dict[str, str]] | None = None,
        support_level: int | None = None,
        novel_item: bool = False,
        correctness_signal: str | None = None,
    ) -> BKTEvaluation:
        """ينفّذ التقييم الكامل ويُخزّنه — نقطة الدخول الوحيدة من الـ router.

        يقرأ الإتقان السابق لنفس المفهوم لاستخدامه كـ prior، فيتراكم الإتقان
        عبر التفاعلات (سجل append-only).

        D-126: يحسب أيضاً **القناة الدائمة الصادقة** (durable) عبر
        ``update_mastery_two_signal``. ``student_mastery_probability`` يبقى القناة
        المدعومة (دون تغيير — لا كسر سلسلة prior). durable لا يرتفع إلا بأداء غير
        مدعوم (support_level≥5) + مؤجَّل (delay_hours≥24) + بند جديد (novel_item).
        ``illusion_gap = assisted − durable`` = مقياس النجاح الوحيد (§0.6).
        """
        # ISS-112: نفس التصنيف الواعي بالسياق الذي يستخدمه BKTEngine.evaluate —
        # وإلا قُرئ الـ prior من مفهوم وكُتب التقييم على مفهوم آخر.
        concept_id = classify_concept_with_context(question, history)
        prior = await self.latest_mastery(user_id, concept_id)
        prior_count = await self.interaction_count(user_id, concept_id)
        prior_durable = await self.latest_durable_mastery(user_id, concept_id)
        last_ts = await self._latest_timestamp(user_id, concept_id)

        evaluation = get_bkt_engine().evaluate(
            BKTEvaluationInput(
                question=question,
                prior_mastery=prior,
                history=history,
                # D-157 (A1b): تجاوز رمزي مُتحقَّق (الأوراكل الحتمي D-155) إن توفّر.
                correctness_signal=correctness_signal,
            )
        )

        # D-157: القناة الدائمة الصادقة بمنحنى نسيان متّصل (حتمي، صفر LLM). delay_hours
        # من آخر تفاعل لنفس المفهوم (أثر المباعدة). ``novel_item`` مشتقّ حتمياً: أول
        # تفاعل على هذا المفهوم = بند جديد. UNKNOWN (لا دليل) ⇒ durable يُحمَل دون
        # تغيير. بلا support_level ⇒ نفترض دعماً ثقيلاً (1) فلا يُضخَّم durable.
        delay_hours = _hours_since(last_ts)
        effective_novel = novel_item or prior_count == 0
        if evaluation.correctness_signal == "unknown":
            durable = round(min(max(prior_durable, 0.0), 1.0), 4)
            durable_cause = "none"
        else:
            sup = support_level if support_level is not None else 1
            durable, durable_cause = durable_update_continuous(
                prior_durable,
                evaluation.evidence_correct,
                support_level=sup,
                delay_hours=delay_hours if delay_hours is not None else 0.0,
                novel_item=effective_novel,
            )

        gap = illusion_gap(evaluation.student_mastery_probability, durable)
        evaluation = evaluation.model_copy(
            update={
                "durable_mastery": durable,
                "support_level": support_level,
                "delay_hours": delay_hours,
                "novel_item": effective_novel,
                "illusion_gap": gap,
            }
        )

        # D-157 (M9 §0.6): بثّ النجم القطبي — فجوة الوهم + القناتان (fail-open داخلياً).
        record_illusion_gap(gap)
        record_mastery_channels(evaluation.student_mastery_probability, durable)
        if durable > prior_durable + 1e-9:
            record_durable_rise(durable_cause)

        await self.record_interaction(
            user_id=user_id,
            session_id=session_id,
            evaluation=evaluation,
            interaction_count=prior_count + 1,
        )
        logger.info(
            "bkt_recorded user_id=%s concept=%s load=%s assisted=%.4f durable=%.4f "
            "illusion_gap=%.4f support=%s prior=%.4f",
            user_id,
            evaluation.concept_id,
            evaluation.cognitive_load_estimate,
            evaluation.student_mastery_probability,
            evaluation.durable_mastery,
            evaluation.illusion_gap,
            evaluation.support_level,
            evaluation.prior_mastery,
        )
        return evaluation


def _hours_since(ts: datetime | None) -> float | None:
    """عدد الساعات منذ ``ts`` حتى الآن (UTC). None إن لم يوجد تفاعل سابق."""
    if ts is None:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    delta = datetime.now(UTC) - ts
    return max(0.0, delta.total_seconds() / 3600.0)


__all__ = ["BKTAnalyticsService"]
