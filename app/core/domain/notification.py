"""صندوق صادر الإشعارات (D-201).

**مُلحَق-فقط** بنفس انضباط `student_bkt_analytics` و`student_review_schedule`: كل طلب
إشعار صفٌّ جديد، وحالة التسليم تُحدَّث في مكانها لأنّها حالة **نقل** لا حالة تعلّم.

`event_id` فريد: هو ما يجعل إعادة تسليم الحدث من الناقل **لا تُنتِج إشعاراً ثانياً**.
الحَكَم قيدٌ في قاعدة البيانات لا فحصٌ في التطبيق — «افحص ثمّ اكتب» نافذةُ سباق يعبرها
طلبان متزامنان فيصل الطالبَ إشعاران (نفس درس القسائم، D-198).
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Text, func
from sqlmodel import Field, SQLModel


class NotificationOutbox(SQLModel, table=True):
    __tablename__ = "notification_outbox"

    id: int | None = Field(default=None, primary_key=True)
    #: مُعرَّف الحدث المُنتِج — فريد، فهو حارس «مرّة واحدة» عبر إعادة التسليم.
    event_id: str = Field(max_length=64, unique=True, index=True)
    user_id: int | None = Field(default=None, index=True)
    channel: str = Field(max_length=32, default="in_app")
    template: str = Field(max_length=64)
    payload_json: str | None = Field(default=None, sa_column=Column(Text))
    #: pending → sent | failed. حالة نقلٍ لا حالة تعلّم، فتُحدَّث في مكانها.
    status: str = Field(max_length=16, default="pending", index=True)
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    sent_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
