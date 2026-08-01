"""المستهلكون داخل العملية — الطرف الحيّ من الناقل (D-201).

لماذا مستهلكٌ حقيقي وليس مقعداً
-------------------------------
ناشرٌ بلا مستهلك ZOMBIE بتعريف §6.6: كودٌ يعمل ولا يُنتج أثراً يمكن ملاحظته. لذلك
يُشحَن هنا **مستهلكٌ فعلي** يعمل بلا وسيط: يسحب من السائق في الذاكرة، ويمرّ بنفس حلقة
`consume_once` التي سيمرّ بها مستهلك Kafka حرفياً — المطالبة مرّةً واحدة، ثمّ المعالجة،
ثمّ قرار DLQ عند الفشل.

النتيجة العملية: انضباط التسليم مُختبَرٌ ومُشغَّل **اليوم**، فلا يبقى تشغيل Kafka إلّا
تبديل سائق. هذا هو الفرق بين تبنّي تقنية وبين تعليق النظام على انتظارها.

المشتركون
---------
سجلٌّ صريح: موضوع ⇒ دوالّ. لا اكتشاف تلقائي — مستهلكٌ يُكتشَف بالسحر يختفي بالسحر.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable

from prometheus_client import Counter

from shared.messaging import (
    ConsumeOutcome,
    Disposition,
    EventEnvelope,
    IdempotencyLedger,
    InMemoryEventBus,
    Topic,
    consume_once,
)

logger = logging.getLogger("cogniforge.messaging.consumer")

Subscriber = Callable[[EventEnvelope], Awaitable[None]]

_SUBSCRIBERS: dict[str, list[Subscriber]] = defaultdict(list)
#: سجلّ «مرّة واحدة» لهذه العملية. مقيَّد الحجم بحكم `IdempotencyLedger`.
_LEDGER = IdempotencyLedger()

# التسمية بالموضوع والنتيجة فقط — **لا مُعرَّف مستخدم ولا مُعرَّف حدث** (حظر التسميات
# عالية الكاردينالية، §0). عدّادٌ بمُعرَّف حدث يُفجِّر Prometheus خلال يوم.
CONSUMED_EVENTS = Counter(
    "cogniforge_messaging_events_consumed_total",
    "Envelopes processed by the in-process consumer",
    ["topic", "result"],
)


def subscribe(topic: Topic, subscriber: Subscriber) -> None:
    """يُسجِّل مُعالِجاً لموضوع. التسجيل صريح ويحدث عند الإقلاع."""
    _SUBSCRIBERS[topic.value].append(subscriber)


def subscribers_for(topic: Topic) -> tuple[Subscriber, ...]:
    """المشتركون المُسجَّلون — للتشخيص وللاختبار."""
    return tuple(_SUBSCRIBERS[topic.value])


def reset_subscribers() -> None:
    """يُفرِّغ السجلّ — للاختبارات."""
    _SUBSCRIBERS.clear()


def reset_ledger() -> None:
    """سجلٌّ نظيف — للاختبارات فقط. في التشغيل يفقد ذلك ضمان «مرّة واحدة»."""
    global _LEDGER
    _LEDGER = IdempotencyLedger()


async def _fan_out(envelope: EventEnvelope) -> None:
    """
    يُسلِّم الظرف لكل مشترك.

    فشل أيّ مشترك يرتفع، فيقرّر `consume_once` مصير الرسالة. الابتلاع هنا كان سيجعل
    الرسالة المسمومة تبدو ناجحة إلى الأبد.
    """
    for subscriber in _SUBSCRIBERS[envelope.topic]:
        await subscriber(envelope)


async def drain(bus: InMemoryEventBus, topic: Topic) -> list[ConsumeOutcome]:
    """
    يستهلك كلّ المعلّق في موضوع، ويُرجِع نتيجة كلّ ظرف.

    النتائج مُرجَعة لا مُبتلَعة: مستهلكٌ لا يقول ماذا فعل غير قابل للتشخيص.
    """
    outcomes: list[ConsumeOutcome] = []
    for envelope in bus.drain(topic):
        outcome = await consume_once(envelope, _fan_out, ledger=_LEDGER, publisher=bus)
        CONSUMED_EVENTS.labels(topic=topic.value, result=_result_label(outcome)).inc()
        outcomes.append(outcome)
    return outcomes


def _result_label(outcome: ConsumeOutcome) -> str:
    if outcome.handled:
        return "handled"
    if outcome.duplicate:
        return "duplicate"
    if outcome.disposition is Disposition.DEAD_LETTER:
        return "dead_letter"
    return "retry"


async def drain_all(bus: InMemoryEventBus) -> dict[str, int]:
    """
    دورةُ استهلاكٍ واحدة عبر كلّ المواضيع عدا DLQ.

    الـDLQ مُستثنى عمداً: إعادة تشغيله آلياً تُعيد نفس الرسالة المسمومة إلى نفس
    المستهلك الذي عجز عنها — حلقةٌ مضمونة. يُفحَص بشرياً.
    """
    summary = {"handled": 0, "duplicate": 0, "dead_letter": 0, "retry": 0}
    for topic in Topic:
        if topic is Topic.DEAD_LETTER:
            continue
        for outcome in await drain(bus, topic):
            summary[_result_label(outcome)] += 1
    return summary


__all__ = [
    "CONSUMED_EVENTS",
    "drain",
    "drain_all",
    "reset_ledger",
    "reset_subscribers",
    "subscribe",
    "subscribers_for",
]
