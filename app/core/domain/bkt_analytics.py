"""
Student BKT Analytics Domain Model.

يخزّن لقطات Bayesian Knowledge Tracing (BKT) لكل تفاعل طالب — سجل
append-only يتتبّع تطوّر إتقان الطالب لكل مفهوم عبر الزمن.

كل صف = تقييم تفاعل واحد:
- `user_id`        — الطالب (FK → users.id)
- `session_id`     — معرّف المحادثة (conversation_id) للتفاعل، إن وُجد
- `concept_id`     — المفهوم (مثل "conditional_probability")
- `cognitive_load_estimate` — تقدير الحِمل المعرفي (low/medium/high)
- `student_mastery_probability` — احتمال الإتقان P(L) بعد تحديث BKT [0.0, 1.0]
- `interaction_count` — رقم التفاعل التراكمي لهذا (طالب، مفهوم)
- `interaction_timestamp` — وقت التفاعل (timestamptz)

السجل append-only: نقرأ آخر صف لاستخراج الإتقان السابق (prior)، نحدّثه، ثم
نُدرج صفاً جديداً. لا تعديل في المكان — التاريخ الكامل محفوظ للتحليلات.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from app.core.domain.common import utc_now


class StudentBKTAnalytic(SQLModel, table=True):
    """لقطة تتبّع معرفي واحدة لتفاعل طالب (سجل append-only)."""

    __tablename__ = "student_bkt_analytics"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    session_id: int | None = Field(default=None, index=True)
    concept_id: str = Field(max_length=120, index=True)
    cognitive_load_estimate: str = Field(default="medium", max_length=10)
    student_mastery_probability: float = Field(default=0.0)
    interaction_count: int = Field(default=1)
    interaction_timestamp: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


__all__ = ["StudentBKTAnalytic"]
