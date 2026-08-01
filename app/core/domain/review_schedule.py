"""
Student Review Schedule Domain Model (D-194).

سجلّ المراجعة المتباعدة (FSRS) — **مُلحَق-فقط**، بنفس انضباط
`student_bkt_analytics`: كلّ مراجعة صفٌّ جديد، والحالة الحيّة لأي (طالب، مفهوم) هي
**أحدث صفّ** بـ`reviewed_at`. لا تحديث في المكان.

لماذا مُلحَق-فقط ولا صفّ حيّ واحد
---------------------------------
معاملات FSRS (١٩ معاملاً) مُدرَّبة على بياناتٍ عامّة، ويُفترَض إعادة تدريبها لاحقاً على
سجلّ مراجعات المنصّة نفسها. تدريبٌ كهذا يحتاج **تسلسل المراجعات كاملاً** (التقدير،
والفاصل المُتوقَّع، والزمن الفعلي بينها). صفٌّ حيّ واحد يُهدِر هذه البيانات إلى الأبد،
ولا يمكن استرجاعها بأثرٍ رجعي.

كلّ صف = مراجعة واحدة:
- `user_id`       — الطالب (FK → users.id)
- `concept_id`    — المفهوم القانوني من `shared/curriculum`
- `rating`        — تقدير FSRS ١..٤ (Again/Hard/Good/Easy)، مُشتقّ من إشارات BKT
- `stability`     — الاستقرار باليوم بعد هذه المراجعة
- `difficulty`    — الصعوبة ١..١٠ بعد هذه المراجعة
- `reps`/`lapses` — العدّادات التراكمية
- `state`         — learning | review | relearning
- `reviewed_at`   — لحظة المراجعة
- `due_at`        — موعد المراجعة التالية
- `interval_days` — الفاصل المُشتقّ (مُخزَّن كي لا يُعاد حسابه في الاستعلامات)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from app.core.domain.common import utc_now


class StudentReviewSchedule(SQLModel, table=True):
    """مراجعة متباعدة واحدة (سجلّ مُلحَق-فقط)."""

    __tablename__ = "student_review_schedule"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    concept_id: str = Field(max_length=120, index=True)
    rating: int = Field(default=3)
    stability: float = Field(default=1.0)
    difficulty: float = Field(default=5.0)
    reps: int = Field(default=1)
    lapses: int = Field(default=0)
    state: str = Field(default="review", max_length=16)
    interval_days: float = Field(default=1.0)
    reviewed_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )
    due_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )


__all__ = ["StudentReviewSchedule"]
