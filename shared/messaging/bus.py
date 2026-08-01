"""ناقل الأحداث: الواجهة، والسائق الذي يعمل بلا بنية تحتية (D-201).

الفكرة المعمارية
----------------
النشر عقدٌ من دالّتين (`publish` · `publish_many`) لا مكتبة. الوسيط تفصيل: نفس الكود
يعمل على سائقٍ في الذاكرة اليوم وعلى Kafka غداً بلا لمس أيّ مُنتِج أو مستهلك — وهذا
هو الفرق بين «تبنّي Kafka» و«ربط الكود بـKafka».

**السائق في الذاكرة ليس نموذجاً أوّلياً.** هو الافتراض الحيّ: بلا وسيطٍ مُشغَّل يبقى
مسار الأحداث كاملاً عاملاً، وتبقى الطبقة ACTIVE بالبرهان الثلاثي بدل أن تكون قدرةً
معلّقة على بنيةٍ تحتية غائبة (§6.6 — الأسوأ من غياب القدرة ادّعاؤها).

حلقة الاستهلاك هنا **حتمية وقابلة للاختبار بلا وسيط**: طالِب بالحدث (مرّة واحدة) ⇒
عالِج ⇒ قرِّر عند الفشل (إعادة أم DLQ). المستهلك الحقيقي فوق Kafka يستدعي نفس الحلقة.

عقد الموقع: stdlib فقط. لا استيراد من `app/` ولا من خدمة.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .delivery import Disposition, IdempotencyLedger, RetryPolicy, decide_disposition
from .envelope import EventEnvelope
from .topics import Topic, validate_topic

__all__ = [
    "ConsumeOutcome",
    "EventPublisher",
    "InMemoryEventBus",
    "consume_once",
]

logger = logging.getLogger(__name__)

#: مُعالِج حدث: يرفع عند الفشل. الرفع هو الإشارة — لا `return False` صامتة (§0).
EventHandler = Callable[[EventEnvelope], Awaitable[None]]


class EventPublisher(ABC):
    """عقد النشر. كلّ سائق (ذاكرة · Kafka · Redis) يُحقّقه."""

    @abstractmethod
    async def publish(self, envelope: EventEnvelope) -> None:
        """ينشر ظرفاً واحداً. يرفع عند فشل النشر — لا ابتلاع."""

    async def publish_many(self, envelopes: list[EventEnvelope]) -> int:
        """
        ينشر دفعة ويُرجِع عدد المنشور.

        **ليست ذرّية**، والتصريح بذلك جزءٌ من العقد: فشلٌ في المنتصف يترك ما سبق
        منشوراً. الذرّية الحقيقية مسؤولية صندوق الصادر المعاملاتي، لا الناقل.
        """
        published = 0
        for envelope in envelopes:
            await self.publish(envelope)
            published += 1
        return published


class InMemoryEventBus(EventPublisher):
    """
    ناقلٌ في الذاكرة — السائق الافتراضي الحيّ.

    طوابير لكل موضوع، بترتيب النشر. يُحقّق العقد نفسه الذي يُحقّقه سائق Kafka، فينتقل
    الكود بينهما بتبديل السائق فقط.
    """

    def __init__(self, max_queue: int = 10_000) -> None:
        self._queues: dict[str, deque[EventEnvelope]] = defaultdict(lambda: deque(maxlen=max_queue))
        self._published_total: dict[str, int] = defaultdict(int)

    async def publish(self, envelope: EventEnvelope) -> None:
        topic = validate_topic(envelope.topic)
        self._queues[topic.value].append(envelope)
        self._published_total[topic.value] += 1

    def drain(self, topic: str | Topic) -> list[EventEnvelope]:
        """يسحب كلّ ما في موضوع — نقطة الاستهلاك في الاختبارات والتشغيل بلا وسيط."""
        key = validate_topic(str(topic)).value
        drained = list(self._queues[key])
        self._queues[key].clear()
        return drained

    def pending(self, topic: str | Topic) -> int:
        return len(self._queues[validate_topic(str(topic)).value])

    def published_total(self, topic: str | Topic) -> int:
        """العدد التراكمي — يبقى بعد السحب فيصلح للمقاييس."""
        return self._published_total[validate_topic(str(topic)).value]


@dataclass(frozen=True)
class ConsumeOutcome:
    """نتيجة محاولة استهلاك واحدة — صريحة كي يكون كلّ مسارٍ قابلاً للقياس."""

    handled: bool
    duplicate: bool = False
    disposition: Disposition | None = None
    error: Exception | None = None


async def consume_once(
    envelope: EventEnvelope,
    handler: EventHandler,
    *,
    ledger: IdempotencyLedger,
    publisher: EventPublisher | None = None,
    policy: RetryPolicy | None = None,
) -> ConsumeOutcome:
    """
    يستهلك ظرفاً واحداً بانضباط «مرّة واحدة» كامل.

    الترتيب مقصود: **المطالبة أوّلاً**. الترتيب المعكوس (عالِج ثمّ سجِّل) يعني أنّ
    عطباً بين الخطوتين يُعيد المعالجة عند إعادة التسليم — وهذا هو صنف العطب الذي
    يجعل «مرّة واحدة» ادّعاءً لا ضماناً.

    وعند الفشل الدائم يُنشَر الظرف على DLQ **إن وُجد ناشر**: بلا ذلك تُفقَد الرسالة
    المسمومة بلا أثر، وفقدانها الصامت أسوأ من فشلها (§0).
    """
    if not ledger.claim(envelope):
        logger.info(
            "event_skipped_duplicate event_id=%s topic=%s", envelope.event_id, envelope.topic
        )
        return ConsumeOutcome(handled=False, duplicate=True)

    try:
        await handler(envelope)
    except Exception as exc:
        disposition = decide_disposition(envelope, exc, policy=policy)
        if disposition is Disposition.DEAD_LETTER and publisher is not None:
            await publisher.publish(_to_dead_letter(envelope, exc))
        logger.warning(
            "event_handler_failed event_id=%s topic=%s disposition=%s error=%s",
            envelope.event_id,
            envelope.topic,
            disposition.value,
            exc,
        )
        return ConsumeOutcome(handled=False, disposition=disposition, error=exc)

    return ConsumeOutcome(handled=True)


def _to_dead_letter(envelope: EventEnvelope, error: Exception) -> EventEnvelope:
    """
    يلفّ ظرفاً فاشلاً للـDLQ مع **سبب** موته.

    رسالةٌ ميتة بلا سببٍ مرفق تُجبِر الفاحص على إعادة بناء الحادثة من السجلّات —
    وغالباً تكون قد دارت. السبب يسافر مع الرسالة.
    """
    return EventEnvelope(
        event_id=envelope.event_id,
        event_name=envelope.event_name,
        topic=Topic.DEAD_LETTER.value,
        payload={
            "original_topic": envelope.topic,
            "original_payload": envelope.payload,
            "error": str(error),
            "error_type": type(error).__name__,
            "delivery_attempt": envelope.delivery_attempt,
        },
        occurred_at=envelope.occurred_at,
        partition_key=envelope.partition_key,
        correlation_id=envelope.correlation_id,
        schema_version=envelope.schema_version,
        delivery_attempt=envelope.delivery_attempt,
        headers=dict(envelope.headers),
    )
