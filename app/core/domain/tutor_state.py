"""
Tutor Dialogue State Domain Model (D-142 Phase 2).

سجل **حالة جلسة التدريس الدائم** — صف واحد لكل محادثة (upsert)، يحمل الذاكرة الحوارية
صراحةً بدل إعادة بنائها من نصّ السجل كل دور (جذر كارثة التكرار/الانحراف، السبب #5 في ISS-117).

ليس سجلًّا (chat log) بل **حالة تعليمية ذات معنى**:
- `conversation_id` — المحادثة (مفتاح فريد، صف حيّ واحد).
- `user_id`         — الطالب.
- `active_concept` / `active_misconception` — المفهوم النشط (يقاوم الانحراف).
- `kc_progress`     — JSON لكل مكوّن معرفي: {state, evidence, difficulty,
                       representations_delivered[], attempts} — دليل الفهم + الصعوبة + ما شُرح.
- `ability_snapshot`— قدرة الطالب للمفهوم النشط (من BKT D-126) — لمعايرة الخطوة التالية.
- `last_step_emitted` — مرساة منع التكرار (آخر خطوة/سؤال عُرض) — تنجو من نافذة الـ 50 رسالة.
- `socratic_count_by_concept` — JSON: ميزانية سقراطية **لكل مفهوم** (لا عامّة تتسرّب).
- `turn_count` / `updated_at`.

upsert (لا append-only): صف حيّ واحد لكل محادثة يُحدَّث كل دور. fail-open في الخدمة:
فشل الحالة لا يُجهض دور الطالب أبداً (نمط BKTAnalyticsService).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Text, func
from sqlmodel import Field, SQLModel

from app.core.domain.common import utc_now


class TutorState(SQLModel, table=True):
    """حالة جلسة تدريس واحدة (صف حيّ لكل محادثة — upsert)."""

    __tablename__ = "tutor_state"

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(index=True, unique=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    active_concept: str = Field(default="", max_length=120)
    active_misconception: str = Field(default="", max_length=120)
    #: JSON (نصّ): {kc_id: {state, evidence, difficulty, representations[], attempts}}.
    kc_progress: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    ability_snapshot: float = Field(default=0.0)
    #: JSON (نصّ): {concept_id: count} — ميزانية سقراطية لكل مفهوم.
    socratic_count_by_concept: str = Field(default="{}", sa_column=Column(Text, nullable=False))
    #: مرساة منع التكرار — آخر خطوة/سؤال عُرض للطالب (ينجو من نافذة التاريخ).
    last_step_emitted: str = Field(default="", sa_column=Column(Text, nullable=False))
    turn_count: int = Field(default=0)
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


__all__ = ["TutorState"]
