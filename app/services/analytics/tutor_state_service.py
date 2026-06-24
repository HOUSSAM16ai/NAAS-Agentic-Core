"""
Tutor Dialogue State Persistence (D-142 Phase 2) — ذاكرة جلسة التدريس الدائمة.

يربط بين الذاكرة الحوارية و جدول `tutor_state` (صف حيّ واحد لكل محادثة، upsert):
1. `load(conversation_id)` — يقرأ الحالة الحالية كـ dict (المفهوم النشط، آخر خطوة
   عُرضت، ميزانية كل مفهوم، تقدّم المكوّنات). تُمرَّر للمُنسّق عبر `context["tutor_state"]`
   فتنجو حُرّاس منع التكرار/الانحراف من نافذة الـ 50 رسالة (جذر ISS-117 #5).
2. `record_turn(...)` — upsert بعد الدور (نمط BKT): يضبط `last_step_emitted`،
   المفهوم النشط، ميزانية السقراطية، ويزيد `turn_count`.

fail-open مطلق: كل عملية مُغلَّفة — فشل الحالة لا يُجهض دور الطالب أبداً، ولا يُرجِع
استثناءً للـ router (يُرجِع حالة فارغة عند تعذّر القراءة).
"""

from __future__ import annotations

import contextlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.common import utc_now
from app.core.domain.tutor_state import TutorState

logger = logging.getLogger("cogniforge.analytics.tutor_state")

#: حالة فارغة آمنة تُرجَع عند تعذّر القراءة (fail-open).
EMPTY_STATE: dict[str, object] = {
    "active_concept": "",
    "active_misconception": "",
    "kc_progress": {},
    "ability_snapshot": 0.0,
    "socratic_count_by_concept": {},
    "last_step_emitted": "",
    "turn_count": 0,
}


def _loads(raw: str | None) -> dict:
    """يُحلّل عمود JSON نصّياً — fail-open إلى {}."""
    if not raw:
        return {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except Exception:  # pragma: no cover - fail-safe
        return {}


class TutorStateService:
    """خدمة ذاكرة جلسة التدريس — تعمل ضمن جلسة AsyncSession واحدة."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _row(self, conversation_id: int) -> TutorState | None:
        stmt = select(TutorState).where(TutorState.conversation_id == conversation_id).limit(1)
        return await self.db.scalar(stmt)

    async def load(self, conversation_id: int) -> dict[str, object]:
        """يُرجِع الحالة الحالية للمحادثة كـ dict جاهز للحقن في context. fail-open."""
        try:
            row = await self._row(conversation_id)
            if row is None:
                return dict(EMPTY_STATE)
            return {
                "active_concept": row.active_concept or "",
                "active_misconception": row.active_misconception or "",
                "kc_progress": _loads(row.kc_progress),
                "ability_snapshot": float(row.ability_snapshot or 0.0),
                "socratic_count_by_concept": _loads(row.socratic_count_by_concept),
                "last_step_emitted": row.last_step_emitted or "",
                "turn_count": int(row.turn_count or 0),
            }
        except Exception:  # pragma: no cover - fail-safe (state must never abort a turn)
            logger.debug("tutor_state.load failed", exc_info=True)
            return dict(EMPTY_STATE)

    async def record_turn(
        self,
        *,
        conversation_id: int,
        user_id: int,
        active_concept: str | None,
        assistant_text: str,
        is_socratic_question: bool,
        ability_snapshot: float | None = None,
    ) -> None:
        """upsert بعد الدور: يضبط آخر خطوة عُرضت + المفهوم النشط + ميزانية المفهوم. fail-open.

        ``is_socratic_question`` (آخر مخرَج ينتهي بسؤال) يزيد ميزانية السقراطية للمفهوم
        النشط فقط (لا عامّة تتسرّب بين المفاهيم — جذر ISS-117 #5).
        """
        try:
            row = await self._row(conversation_id)
            concept = (active_concept or "").strip()[:120]
            step = (assistant_text or "").strip()[:4000]
            if row is None:
                row = TutorState(conversation_id=conversation_id, user_id=user_id)
                self.db.add(row)
            if concept:
                row.active_concept = concept
            row.last_step_emitted = step
            row.turn_count = int(row.turn_count or 0) + 1
            if ability_snapshot is not None:
                row.ability_snapshot = float(max(0.0, min(1.0, ability_snapshot)))
            if is_socratic_question and concept:
                budget = _loads(row.socratic_count_by_concept)
                budget[concept] = int(budget.get(concept, 0)) + 1
                row.socratic_count_by_concept = json.dumps(budget, ensure_ascii=False)
            row.updated_at = utc_now()
            await self.db.commit()
        except Exception:  # pragma: no cover - fail-safe
            logger.debug("tutor_state.record_turn failed", exc_info=True)
            with contextlib.suppress(Exception):
                await self.db.rollback()


__all__ = ["EMPTY_STATE", "TutorStateService"]
