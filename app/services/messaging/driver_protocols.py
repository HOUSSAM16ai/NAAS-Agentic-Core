"""عقود سائقي Kafka — أنواعٌ بدل `Any` (D-204).

لماذا Protocol وليس `Any`
-------------------------
`aiokafka` تبعية **اختيارية** (`requirements-messaging.txt`)، فلا يمكن استيراد أنواعها
وقت التحقّق. الحلّ الكسول هو `Any`، وثمنه أنّ خطأً مطبعياً في اسم دالّة على حدّ البنية
التحتية لا يُكتشَف إلّا حين يُشغَّل وسيطٌ حقيقي — أي في أسوأ لحظة ممكنة.

هنا نُصرّح بما **نستعمله فعلاً** من السائق: أربع دوالّ للمُنتِج وأربع للمستهلك. المُدقِّق
يتحقّق منها، والمزيّف في الاختبارات يجب أن يُحقّقها هو الآخر — فيصير الاختبار حارساً
للعقد لا محاكاةً حرّة.

القاعدة الدائمة: تبعيةٌ اختيارية تُوصَف بـProtocol، لا تُغطّى بـ`Any` (D-192).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class KafkaProducerLike(Protocol):
    """ما نطلبه من مُنتِج Kafka — لا أكثر."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def send_and_wait(
        self,
        topic: str,
        *,
        value: str | bytes,
        key: str | bytes | None,
        headers: Sequence[tuple[str, bytes]],
    ) -> object: ...


class ConsumerRecordLike(Protocol):
    """سجلٌّ كما يصل من المستهلك."""

    @property
    def value(self) -> bytes | str: ...


class KafkaConsumerLike(Protocol):
    """ما نطلبه من مستهلك Kafka — لا أكثر."""

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def commit(self) -> None: ...

    async def getmany(
        self, *, timeout_ms: int, max_records: int
    ) -> dict[object, list[ConsumerRecordLike]]: ...


__all__ = ["ConsumerRecordLike", "KafkaConsumerLike", "KafkaProducerLike"]
