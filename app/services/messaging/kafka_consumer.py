"""مستهلك Kafka/Redpanda — النصف الغائب من مسار الأحداث (D-204).

لماذا وُجِد هذا الملفّ متأخّراً
------------------------------
D-201 شحن `KafkaEventPublisher` بلا مستهلك. ناشرٌ بلا مستهلك لا يمكن إثباته طرفاً إلى
طرف مهما كثرت اختباراته: تبقى الرسالة تُرسَل إلى فراغٍ لا أحد يقرؤه، فيظلّ السائق
DORMANT بحقّ. هذا الملفّ يُكمِل الدائرة كي يصير الإثبات ممكناً — ثمّ **مطلوباً** ببوّابة
حيّة (`scripts/verify_event_stack_docker.py`).

لا حلقة تسليم ثانية
-------------------
كلّ الانضباط يعيش في `shared/messaging/bus.py:consume_once`: المطالبة مرّةً واحدة، ثمّ
المعالجة، ثمّ قرار إعادة/DLQ. هنا **نقل بايتات فقط**: فُكّ الظرف، سلّمه لتلك الحلقة،
ثبّت الإزاحة. حلقةٌ ثانية تعني منطقَي «مرّة واحدة» ينحرفان — وهو صنف D-013 بعينه.

قرارات مقصودة
-------------
* **`enable_auto_commit=False`.** التثبيت التلقائي يُقرّ بالرسالة **قبل** أن يعمل
  المُعالِج، فسقوطٌ في المنتصف يفقدها نهائياً. نُثبِّت **بعد** عودة `consume_once`.
* **رسالةٌ لا تُفكَّك تُثبَّت إزاحتها أيضاً.** تبدو مخالفةً للحدس، لكنّ عدم التثبيت يعني
  إعادة تسليمها إلى الأبد فيتجمّد القسم كاملاً — وهي بالفعل مُرسَلة إلى DLQ بسببها،
  فمكانها محفوظ. هذا هو الفرق بين «لا نفقد شيئاً» و«لا يتقدّم شيء».
* **مهلة صريحة على السحب** — انتظارٌ مفتوح على حدّ بنية تحتية يحوّل البطء إلى تعليق (D-189).
* **الاتصال كسول** — بناء المستهلك يجب ألّا يفتح مقبساً (نفس قاعدة الناشر).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from shared.messaging import (
    ConsumeOutcome,
    Disposition,
    EventEnvelope,
    EventPublisher,
    IdempotencyLedger,
    MessagingError,
    RetryPolicy,
    Topic,
    consume_once,
    new_event_id,
    spec_for,
)
from shared.messaging.bus import EventHandler

logger = logging.getLogger("cogniforge.messaging.kafka.consumer")

#: مهلة سحب دفعة واحدة. صريحة دائماً (D-189).
POLL_TIMEOUT_MS = 5_000
#: مهلة إيقاف نظيف — مستهلكٌ لا يُغادر مجموعته يُجمّد إعادة الموازنة للبقيّة.
STOP_TIMEOUT_SECONDS = 10.0


class KafkaEventConsumer:
    """
    مستهلكٌ فوق `aiokafka` يُفوِّض كلّ قرار إلى `shared/messaging`.

    ليس خيطياً-آمناً عمداً: مستهلك واحد لكل قسم هو نموذج Kafka، والقفل كلفةٌ بلا مقابل.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic: Topic,
        group_id: str | None = None,
        client_id: str = "cogniforge-consumer",
        ledger: IdempotencyLedger | None = None,
        dlq_publisher: EventPublisher | None = None,
        policy: RetryPolicy | None = None,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topic = topic
        # مجموعة المستهلكين من **عقد الموضوع** لا من نصٍّ حرّ: مجموعةٌ مكتوبة يدوياً
        # تُنشئ صامتةً مستهلكاً ثانياً يقرأ نفس الرسائل مرّة أخرى.
        self._group_id = group_id or spec_for(topic).consumer_group
        self._client_id = client_id
        self._ledger = ledger or IdempotencyLedger()
        self._dlq_publisher = dlq_publisher
        self._policy = policy
        self._consumer: Any | None = None
        self._lock = asyncio.Lock()

    @property
    def group_id(self) -> str:
        return self._group_id

    async def _ensure_consumer(self) -> Any:
        """يبني المستهلك ويبدؤه مرّةً واحدة — تحت قفلٍ كي لا يتسابق نداءان."""
        if self._consumer is not None:
            return self._consumer
        async with self._lock:
            if self._consumer is not None:  # pragma: no cover - سباقٌ نادر
                return self._consumer
            try:
                from aiokafka import AIOKafkaConsumer
            except ImportError as exc:
                raise MessagingError(
                    "aiokafka is not installed — install requirements-messaging.txt to consume"
                ) from exc
            consumer = AIOKafkaConsumer(
                self._topic.value,
                bootstrap_servers=self._bootstrap_servers,
                client_id=self._client_id,
                group_id=self._group_id,
                # التثبيت اليدوي هو جوهر «لا نفقد رسالة عولجت نصفها» — انظر رأس الملفّ.
                enable_auto_commit=False,
                auto_offset_reset="earliest",
            )
            await consumer.start()
            self._consumer = consumer
            logger.info(
                "kafka_consumer_started topic=%s group=%s", self._topic.value, self._group_id
            )
            return consumer

    async def consume_batch(
        self, handler: EventHandler, *, max_records: int = 100
    ) -> list[ConsumeOutcome]:
        """
        يسحب دفعةً ويُعالجها. يُرجِع نتيجة كلّ ظرف — دفعةٌ صامتة غير قابلة للتشخيص.

        الإزاحة تُثبَّت **بعد** معالجة الدفعة كاملةً: التثبيت لكل رسالة يضاعف رحلات
        الشبكة بلا مقابل، والتثبيت قبل المعالجة يفقد ما لم يُعالَج بعد.
        """
        consumer = await self._ensure_consumer()
        batches = await consumer.getmany(timeout_ms=POLL_TIMEOUT_MS, max_records=max_records)

        outcomes: list[ConsumeOutcome] = []
        for records in batches.values():
            for record in records:
                outcomes.append(await self._handle_record(record, handler))

        if outcomes:
            await consumer.commit()
        return outcomes

    async def _handle_record(self, record: Any, handler: EventHandler) -> ConsumeOutcome:
        """
        يفكّ سجلّاً واحداً ويُمرّره لحلقة الانضباط المشتركة.

        رسالةٌ مشوَّهة **لا تصل** `consume_once` (لا ظرف يُطالَب به)، فتُرسَل إلى DLQ هنا
        مباشرةً بنفس القرار الذي كانت ستتلقّاه: `MessagingError` خطأٌ دائم.
        """
        raw = record.value
        payload = raw.decode("utf-8") if isinstance(raw, bytes | bytearray) else str(raw)
        try:
            envelope = EventEnvelope.from_json(payload)
        except MessagingError as exc:
            logger.warning(
                "kafka_record_undecodable topic=%s offset=%s error=%s",
                getattr(record, "topic", self._topic.value),
                getattr(record, "offset", "?"),
                exc,
            )
            await self._dead_letter_raw(payload, exc)
            return ConsumeOutcome(handled=False, disposition=Disposition.DEAD_LETTER, error=exc)

        return await consume_once(
            envelope,
            handler,
            ledger=self._ledger,
            publisher=self._dlq_publisher,
            policy=self._policy,
        )

    async def _dead_letter_raw(self, payload: str, error: MessagingError) -> None:
        """
        يُرسِل بايتاتٍ لا تُفكَّك إلى DLQ.

        لا `event_id` أصلي هنا — فلا مفرّ من توليد واحد. مُصرَّحٌ به في الحمولة
        (`event_id_synthesized`) كي لا يُقرأ لاحقاً كأنّه مُعرَّف المُنتِج.
        """
        if self._dlq_publisher is None:
            return
        await self._dlq_publisher.publish(
            EventEnvelope(
                event_id=new_event_id(),
                event_name="undecodable_record",
                topic=Topic.DEAD_LETTER.value,
                payload={
                    "original_topic": self._topic.value,
                    "raw": payload[:4000],
                    "error": str(error),
                    "error_type": type(error).__name__,
                    "event_id_synthesized": True,
                },
                occurred_at=datetime.now(UTC),
            )
        )

    async def close(self) -> None:
        """يوقف المستهلك. آمنٌ إن لم يبدأ."""
        if self._consumer is None:
            return
        await asyncio.wait_for(self._consumer.stop(), timeout=STOP_TIMEOUT_SECONDS)
        self._consumer = None


__all__ = ["POLL_TIMEOUT_MS", "STOP_TIMEOUT_SECONDS", "KafkaEventConsumer"]
