"""
Product Event Domain Model (D-197).

سجلّ أحداث المنتج — **مُلحَق-فقط**. كلّ صف = حدثٌ واحد وقع.

لماذا جدولٌ أوّلي لا SDK خارجي
------------------------------
بيانات الطلاب القُصّر لا تُصدَّر إلى طرفٍ ثالث بلا سببٍ قاهر. والاحتفاظ المحسوب محلّياً
قابلٌ للتدقيق والاختبار، بينما لوحة مزوّدٍ خارجي صندوقٌ أسود لا يمرّ من بوّابات المشروع.
`AnalyticsAdapter._send_to_platform` كان جسداً فارغاً و`platforms=[]` — أي نيّة تكاملٍ
لم تُنفَّذ قطّ؛ هذا الجدول هو ما يجعل السؤال «هل نجح ما بنيناه؟» قابلاً للإجابة.

`props` نصّ JSON: سياقٌ صغير لكلّ حدث (مثل `concept_id`). **ممنوع** أن يحمل نصّ محادثة
أو إجابة — لنفس سبب D-196.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, func
from sqlmodel import Field, SQLModel

from app.core.domain.common import JSONText, utc_now


class ProductEvent(SQLModel, table=True):
    """حدث منتجٍ واحد (سجلّ مُلحَق-فقط)."""

    __tablename__ = "product_events"

    id: int | None = Field(default=None, primary_key=True)
    #: قد يكون `None` لأحداثٍ سابقة للمصادقة.
    user_id: int | None = Field(default=None, foreign_key="users.id", index=True)
    event_name: str = Field(max_length=64, index=True)
    session_id: int | None = Field(default=None)
    props: dict | None = Field(default=None, sa_column=Column(JSONText))
    occurred_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), index=True),
    )


__all__ = ["ProductEvent"]
