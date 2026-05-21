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

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.bkt_analytics import StudentBKTAnalytic
from app.services.skills.bkt_engine import (
    BKTEvaluation,
    BKTEvaluationInput,
    classify_concept,
    get_bkt_engine,
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
    ) -> BKTEvaluation:
        """ينفّذ التقييم الكامل ويُخزّنه — نقطة الدخول الوحيدة من الـ router.

        يقرأ الإتقان السابق لنفس المفهوم لاستخدامه كـ prior، فيتراكم الإتقان
        عبر التفاعلات (سجل append-only).
        """
        concept_id = classify_concept(question)
        prior = await self.latest_mastery(user_id, concept_id)
        prior_count = await self.interaction_count(user_id, concept_id)

        evaluation = get_bkt_engine().evaluate(
            BKTEvaluationInput(question=question, prior_mastery=prior, history=history)
        )
        await self.record_interaction(
            user_id=user_id,
            session_id=session_id,
            evaluation=evaluation,
            interaction_count=prior_count + 1,
        )
        logger.info(
            "bkt_recorded user_id=%s concept=%s load=%s mastery=%.4f prior=%.4f",
            user_id,
            evaluation.concept_id,
            evaluation.cognitive_load_estimate,
            evaluation.student_mastery_probability,
            evaluation.prior_mastery,
        )
        return evaluation


__all__ = ["BKTAnalyticsService"]
