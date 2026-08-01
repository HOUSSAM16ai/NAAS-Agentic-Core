"""اختيار ناقل الأحداث ونشرٌ لا يكسر دور طالب (D-201).

القاعدة الحاكمة
---------------
النشر **تابعٌ** لا أصل. أيّ فشلٍ في الناقل يُسجَّل ويُبتلَع هنا وهنا **فقط** — لا يصعد
إلى دور الطالب أبداً، بنفس انضباط BKT (D-074) والتحليلات (D-197). حدثٌ ضائع خسارةُ
قياس؛ دورٌ ساقط خسارةُ طالب.

والوجه الآخر من نفس القاعدة: الابتلاع مسموحٌ **هنا** لأنّ هذه هي الحافة المُصرَّح بها.
داخل الطبقة نفسها (`shared/messaging`) كلّ خطأ يرتفع — وإلّا صار «لا فشل صامت» شعاراً.

اختيار السائق
-------------
`KAFKA_BOOTSTRAP_SERVERS` مضبوطاً ⇒ سائق Kafka. غيرَ مضبوط ⇒ السائق في الذاكرة، وهو
**افتراضٌ حيّ لا نموذج أوّلي**: مسار الأحداث يبقى عاملاً ومختبَراً بلا بنية تحتية.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from shared.messaging import (
    EventEnvelope,
    EventPublisher,
    InMemoryEventBus,
    Topic,
    new_event_id,
)

logger = logging.getLogger("cogniforge.messaging")

_publisher: EventPublisher | None = None


def get_event_publisher() -> EventPublisher:
    """
    الناشر الفعّال لهذه العملية (singleton كسول).

    السائق يُختار مرّةً عند أوّل نشر. تبديله وقت التشغيل ليس مدعوماً عمداً: ناشرٌ
    يتبدّل تحت حِمل يعني أحداثاً موزّعة على وسيطين بلا ترتيبٍ بينهما.
    """
    global _publisher
    if _publisher is None:
        _publisher = _build_publisher()
    return _publisher


def reset_event_publisher() -> None:
    """يُعيد ضبط الاختيار — للاختبارات ولإعادة التهيئة الصريحة."""
    global _publisher
    _publisher = None


def _build_publisher() -> EventPublisher:
    from app.core.config import get_settings

    settings = get_settings()
    bootstrap = getattr(settings, "KAFKA_BOOTSTRAP_SERVERS", None)
    if not bootstrap:
        logger.info("event_publisher_selected driver=in_memory (no KAFKA_BOOTSTRAP_SERVERS)")
        return InMemoryEventBus()

    try:
        from app.services.messaging.kafka_publisher import KafkaEventPublisher

        publisher = KafkaEventPublisher(
            bootstrap_servers=bootstrap,
            client_id=getattr(settings, "KAFKA_CLIENT_ID", "cogniforge-monolith"),
        )
        logger.info("event_publisher_selected driver=kafka bootstrap=%s", bootstrap)
        return publisher
    except Exception as exc:
        # سقوطٌ **مُعلَن** إلى الذاكرة: عنوانٌ مضبوط ووسيطٌ متعذّر يعني عطباً تشغيلياً
        # يجب أن يُرى في السجلّات، لا أن يمرّ كأنّ شيئاً لم يكن.
        logger.error("kafka_publisher_unavailable falling_back=in_memory error=%s", exc)
        return InMemoryEventBus()


def build_envelope(
    *,
    topic: Topic,
    event_name: str,
    payload: dict[str, Any],
    partition_key: str | None = None,
    correlation_id: str | None = None,
    occurred_at: datetime | None = None,
) -> EventEnvelope:
    """يبني ظرفاً بمُعرَّفٍ جديد. يُستدعى **مرّةً** لكل حدث، لا لكل محاولة نشر."""
    return EventEnvelope(
        event_id=new_event_id(),
        event_name=event_name,
        topic=topic.value,
        payload=payload,
        occurred_at=occurred_at or datetime.now(UTC),
        partition_key=partition_key,
        correlation_id=correlation_id or _ambient_correlation_id(),
    )


def _ambient_correlation_id() -> str | None:
    """
    المُعرَّف المحيط للدور الجاري — **يُمَدّ ولا يُخترَع** (D-189).

    مُعرَّفٌ جديد لكل حدث يقطع السلسلة بدل مدّها، فتصير الترويسة موجودةً وبلا قيمة.
    """
    try:
        from app.core.logging import correlation_id

        return correlation_id.get()
    except Exception:  # pragma: no cover - حارس دفاعي؛ الغياب لا يُسقِط النشر
        return None


async def publish_event(envelope: EventEnvelope) -> bool:
    """
    ينشر ظرفاً. **لا يرفع أبداً** — يُرجِع نجاح النشر.

    هذه هي الحافة الوحيدة المُصرَّح لها بابتلاع خطأ الناقل (انظر رأس الملفّ).
    """
    try:
        await get_event_publisher().publish(envelope)
        return True
    except Exception as exc:
        logger.warning(
            "event_publish_failed topic=%s event_id=%s error=%s",
            envelope.topic,
            envelope.event_id,
            exc,
        )
        return False


__all__ = [
    "build_envelope",
    "get_event_publisher",
    "publish_event",
    "reset_event_publisher",
]
