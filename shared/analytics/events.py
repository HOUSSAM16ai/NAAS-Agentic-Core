"""أسماء أحداث المنتج القانونية — المصدر الوحيد (D-197).

لماذا قائمة مغلقة
-----------------
تحليلاتٌ بأسماء أحداث حرّة تصير غير قابلة للاستعمال خلال أسابيع: `chat_start` و
`chat_started` و`ChatStarted` تعيش معاً، فيصير كلّ استعلامٍ تخميناً، وكلّ رقمٍ في لوحة
المستثمر مبنيّاً على تجميعٍ ناقص. نفس درس D-186 في نيّة الطالب: **مصدر واحد للأسماء،
وأيّ اسمٍ خارجه يُرفَض عند الكتابة لا يُكتشَف بعد شهر**.

الأسماء بصيغة الماضي (`user_signed_up` لا `sign_up`): الحدث شيءٌ **وقع**، وهذا يمنع
الخلط بين الحدث والنيّة.

عقد الموقع
----------
stdlib فقط. لا استيراد من `app/` ولا من أيّ خدمة (قانون الحدود §6.7.و).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

__all__ = [
    "CANONICAL_EVENTS",
    "AnalyticsError",
    "EventName",
    "is_canonical",
    "validate_event_name",
]


class AnalyticsError(ValueError):
    """اسم حدثٍ خارج السجلّ القانوني."""


class EventName(StrEnum):
    """كلّ حدثٍ يكتبه النظام. الإضافة هنا شرطٌ لأيّ تتبّع جديد."""

    #: اكتساب
    USER_SIGNED_UP = "user_signed_up"
    USER_SIGNED_IN = "user_signed_in"

    #: التفاعل الأساسي — دور الطالب.
    CHAT_TURN_STARTED = "chat_turn_started"

    #: حلقة المراجعة المتباعدة (D-194).
    REVIEW_SCHEDULED = "review_scheduled"
    REVIEW_QUEUE_VIEWED = "review_queue_viewed"

    #: حلقة وليّ الأمر (D-196) — مسار التحويل التجاري.
    GUARDIAN_LINK_ISSUED = "guardian_link_issued"
    GUARDIAN_LINK_ACCEPTED = "guardian_link_accepted"
    GUARDIAN_REPORT_VIEWED = "guardian_report_viewed"


CANONICAL_EVENTS: Final[frozenset[str]] = frozenset(item.value for item in EventName)


def is_canonical(event_name: str) -> bool:
    """هل الاسم مُسجَّل؟"""
    return event_name in CANONICAL_EVENTS


def validate_event_name(event_name: str) -> str:
    """يُعيد الاسم إن كان قانونياً، وإلّا يرفع — الرفض عند الكتابة لا بعد شهر."""
    if not is_canonical(event_name):
        raise AnalyticsError(
            f"unknown event name: {event_name!r}. "
            f"Register it in shared/analytics/events.py:EventName first."
        )
    return event_name
