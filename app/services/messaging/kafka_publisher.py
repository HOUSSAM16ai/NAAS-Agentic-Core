"""سائق Kafka/Redpanda للنشر (D-201).

**الحالة الصادقة:** هذا السائق يعمل فقط حين يكون `KAFKA_BOOTSTRAP_SERVERS` مضبوطاً
و`aiokafka` مثبَّتاً ووسيطٌ مُشغَّلاً. بلا ذلك يبقى السائق في الذاكرة هو الحيّ. لا
يُدَّعى غير ذلك في `.memory/runtime_truth.md` (§6.6: القدرة تُثبَت بالبرهان الثلاثي).

قرارات مقصودة
-------------
* **المفتاح إلزامي حين يطلبه عقد الموضوع.** بلا مفتاح تتوزّع أحداث الطالب الواحد على
  أقسام، فتصل بترتيبٍ غير ترتيب وقوعها — و«جُدوِل مراجعة» تسبق «قُيِّم» تعني جدولةً
  على معطى قديم.
* **`acks="all"` + `enable_idempotence`.** الافتراض الأسرع (`acks=1`) يفقد رسائل عند
  سقوط القائد، وحدثُ تعلّمٍ ضائع لا يُعوَّض.
* **الاتصال كسول.** بناء الناشر يجب ألّا يفتح مقبساً: الإقلاع يُعلَّق على وسيطٍ بطيء
  فتصير «العملية حيّة والخدمة ميتة» (§0).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared.messaging import EventEnvelope, EventPublisher, MessagingError, spec_for

logger = logging.getLogger("cogniforge.messaging.kafka")

#: مهلة صريحة دائماً — الانتظار المفتوح على حدّ بنية تحتية يحوّل البطء إلى تعليق (D-189).
SEND_TIMEOUT_SECONDS = 10.0


class KafkaEventPublisher(EventPublisher):
    """ناشرٌ فوق `aiokafka` بعقد `EventPublisher` نفسه."""

    def __init__(self, *, bootstrap_servers: str, client_id: str = "cogniforge") -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._producer: Any | None = None
        self._lock = asyncio.Lock()

    async def _ensure_producer(self) -> Any:
        """يبني المُنتِج ويبدؤه مرّةً واحدة — تحت قفلٍ كي لا يتسابق دوران متزامنان."""
        if self._producer is not None:
            return self._producer
        async with self._lock:
            if self._producer is not None:  # pragma: no cover - سباقٌ نادر
                return self._producer
            try:
                from aiokafka import AIOKafkaProducer
            except ImportError as exc:
                raise MessagingError(
                    "aiokafka is not installed — set KAFKA_BOOTSTRAP_SERVERS only with the driver"
                ) from exc
            producer = AIOKafkaProducer(
                bootstrap_servers=self._bootstrap_servers,
                client_id=self._client_id,
                acks="all",
                enable_idempotence=True,
                value_serializer=lambda value: value.encode("utf-8"),
                key_serializer=lambda key: key.encode("utf-8") if key else None,
            )
            await producer.start()
            self._producer = producer
            logger.info("kafka_producer_started bootstrap=%s", self._bootstrap_servers)
            return producer

    async def publish(self, envelope: EventEnvelope) -> None:
        spec = spec_for(envelope.topic)
        if spec.requires_key and not envelope.partition_key:
            raise MessagingError(
                f"topic {envelope.topic} requires a partition key to preserve per-entity order"
            )
        producer = await self._ensure_producer()
        payload = envelope.to_json()
        await asyncio.wait_for(
            producer.send_and_wait(
                envelope.topic,
                value=payload,
                key=envelope.partition_key,
                headers=[(name, value.encode("utf-8")) for name, value in envelope.headers.items()],
            ),
            timeout=SEND_TIMEOUT_SECONDS,
        )

    async def close(self) -> None:
        """يُغلِق المُنتِج. آمنٌ إن لم يُفتَح قطّ."""
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None


__all__ = ["SEND_TIMEOUT_SECONDS", "KafkaEventPublisher"]
