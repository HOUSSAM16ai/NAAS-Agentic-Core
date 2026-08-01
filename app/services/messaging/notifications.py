"""المشترك الحيّ: حدث منتج ⇒ صفٌّ في صندوق صادر الإشعارات (D-201).

هذا هو ما يجعل الناقل **ACTIVE** لا مقعداً: أثرٌ ملاحَظ في قاعدة البيانات ناتجٌ عن
حدثٍ عبر الناقل. `NotificationRequested` (`app/core/domain_events/system_events.py`)
كانت صنفَ حدثٍ **بلا مُرسِل ولا مستقبِل ولا ناقل** منذ إنشائها — هنا تصير طريقاً
حقيقياً.

القرار الحاسم هنا **قيدُ التفرّد على `event_id`**: إعادة تسليم الحدث (وهي الوضع
الطبيعي لا الاستثناء) لا تُنتِج إشعاراً ثانياً، ويحسم ذلك محرّك قاعدة البيانات لا
فحصٌ في التطبيق — «افحص ثمّ اكتب» نافذة سباق يعبرها طلبان متزامنان (درس D-198).
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.exc import IntegrityError

from shared.messaging import EventEnvelope
from shared.messaging.notification_rules import derive_notification

logger = logging.getLogger("cogniforge.messaging.notifications")


async def handle_product_event(envelope: EventEnvelope) -> None:
    """
    يُحوِّل حدث منتجٍ إلى طلب إشعار **إن كانت له قاعدة**.

    غياب القاعدة ليس فشلاً: الافتراض هو الصمت، والقائمة المغلقة في
    `shared/messaging/notification_rules.py` هي المكان الوحيد الذي يُراجَع.
    """
    request = derive_notification(envelope.event_name, envelope.payload)
    if request is None:
        return

    from app.core.database import async_session_factory
    from app.core.domain.notification import NotificationOutbox

    async with async_session_factory() as db:
        db.add(
            NotificationOutbox(
                event_id=envelope.event_id,
                user_id=request.user_id,
                channel=request.channel,
                template=request.template,
                payload_json=json.dumps(request.payload, ensure_ascii=False),
            )
        )
        try:
            await db.commit()
        except IntegrityError:
            # إعادة تسليم — الوضع الطبيعي. القيد الفريد رفض التكرار، وهذا **نجاح**
            # العقد لا فشله، فلا يُعاد الظرف ولا يُرسَل إلى DLQ.
            await db.rollback()
            logger.info("notification_already_queued event_id=%s", envelope.event_id)


def register_subscribers() -> None:
    """يُسجِّل المشتركين. يُستدعى عند الإقلاع — تسجيلٌ صريح لا اكتشافٌ سحري."""
    from app.services.messaging.consumers import subscribe, subscribers_for
    from shared.messaging import Topic

    if handle_product_event in subscribers_for(Topic.PRODUCT_EVENTS):
        return
    subscribe(Topic.PRODUCT_EVENTS, handle_product_event)


__all__ = ["handle_product_event", "register_subscribers"]
