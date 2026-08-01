"""
Guardian Link Domain Model (D-196).

ربط وليّ الأمر بالطالب — **برضا الطالب حصراً**.

الرضا شرطٌ بنيوي لا سياسة مكتوبة: الطالب يُولِّد `link_code` ويسلّمه لوليّه، والوليّ
يستبدله فيُملأ `guardian_user_id`. لا يوجد مسارٌ في هذا النموذج يربط حساب طالب بحساب
آخر دون فعلٍ صريح من الطالب — لأنّ الصفّ **يبدأ** بـ`guardian_user_id = NULL`.

المنصّة تخدم قاصرين، فالخيار الافتراضي يجب أن يكون الخصوصية لا الشفافية.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from app.core.domain.common import utc_now


class GuardianLink(SQLModel, table=True):
    """رابطٌ واحد بين وليّ أمر وطالب."""

    __tablename__ = "guardian_links"

    id: int | None = Field(default=None, primary_key=True)
    #: فارغ حتى يستبدل الوليُّ الرمز.
    guardian_user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    student_user_id: int = Field(foreign_key="users.id", index=True)
    link_code: str = Field(max_length=32, index=True)
    status: str = Field(default="pending", max_length=16)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    accepted_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    revoked_at: datetime | None = Field(
        default=None, sa_column=Column(DateTime(timezone=True), nullable=True)
    )


__all__ = ["GuardianLink"]
