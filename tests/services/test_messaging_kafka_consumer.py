"""اختبارات مستهلك Kafka بلا وسيط — D-204.

الوسيط الحيّ يُثبِته `scripts/verify_event_stack_docker.py` في CI. هنا تُختبَر
**القرارات**: التثبيت اليدوي بعد المعالجة، والرسالة المشوَّهة إلى DLQ بدل تجميد القسم،
ومجموعة المستهلكين من عقد الموضوع لا من نصٍّ حرّ.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.services.messaging.kafka_consumer import (
    POLL_TIMEOUT_MS,
    STOP_TIMEOUT_SECONDS,
    KafkaEventConsumer,
)
from app.services.messaging.runtime import build_envelope
from shared.messaging import (
    Disposition,
    EventEnvelope,
    IdempotencyLedger,
    InMemoryEventBus,
    MessagingError,
    Topic,
)


class _Record:
    """سجلٌّ مزيّف بشكل `aiokafka.ConsumerRecord` بقدر ما يلزم."""

    def __init__(self, value: bytes | str, *, offset: int = 0, topic: str = "t") -> None:
        self.value = value
        self.offset = offset
        self.topic = topic


class _FakeConsumer:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.commits = 0
        self.batches: list[dict[str, list[_Record]]] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def commit(self) -> None:
        self.commits += 1

    async def getmany(self, *, timeout_ms: int, max_records: int):
        self.last_poll = {"timeout_ms": timeout_ms, "max_records": max_records}
        return self.batches.pop(0) if self.batches else {}


@pytest.fixture
def fake_aiokafka(monkeypatch):
    """يحقن `aiokafka` مزيّفة **داخل الاختبار** (نظافة الاختبارات، D-105)."""
    created: list[_FakeConsumer] = []

    def factory(*args, **kwargs):
        consumer = _FakeConsumer(*args, **kwargs)
        created.append(consumer)
        return consumer

    module = types.ModuleType("aiokafka")
    module.AIOKafkaConsumer = factory
    monkeypatch.setitem(sys.modules, "aiokafka", module)
    return created


def _consumer(**overrides) -> KafkaEventConsumer:
    params = {"bootstrap_servers": "redpanda:9092", "topic": Topic.PRODUCT_EVENTS}
    params.update(overrides)
    return KafkaEventConsumer(**params)


def _encoded(**overrides) -> bytes:
    params = {
        "topic": Topic.PRODUCT_EVENTS,
        "event_name": "chat_turn_started",
        "payload": {"user_id": 5},
        "partition_key": "user:5",
    }
    params.update(overrides)
    return build_envelope(**params).to_json().encode("utf-8")


async def _noop(_: EventEnvelope) -> None:
    return None


# ── البناء ──────────────────────────────────────────────────────────────────────


def test_the_consumer_group_comes_from_the_topic_contract() -> None:
    """
    مجموعةٌ مكتوبة يدوياً تُنشئ صامتةً مستهلكاً ثانياً يقرأ نفس الرسائل مرّة أخرى.
    """
    assert _consumer().group_id == "cogniforge-analytics-ingest"


def test_an_explicit_group_is_still_honoured() -> None:
    assert _consumer(group_id="replay-2026").group_id == "replay-2026"


async def test_building_the_consumer_opens_no_socket(fake_aiokafka) -> None:
    _consumer()
    assert fake_aiokafka == []


async def test_auto_commit_is_disabled(fake_aiokafka) -> None:
    """
    التثبيت التلقائي يُقرّ بالرسالة **قبل** أن يعمل المُعالِج، فسقوطٌ في المنتصف يفقدها.
    """
    consumer = _consumer()
    await consumer.consume_batch(_noop)

    assert fake_aiokafka[0].kwargs["enable_auto_commit"] is False
    assert fake_aiokafka[0].kwargs["auto_offset_reset"] == "earliest"
    assert fake_aiokafka[0].args[0] == Topic.PRODUCT_EVENTS.value


async def test_a_missing_driver_library_fails_loudly(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "aiokafka", None)
    with pytest.raises(MessagingError, match="aiokafka"):
        await _consumer().consume_batch(_noop)


async def test_the_consumer_starts_only_once(fake_aiokafka) -> None:
    consumer = _consumer()
    await consumer.consume_batch(_noop)
    await consumer.consume_batch(_noop)
    assert len(fake_aiokafka) == 1


# ── الاستهلاك ───────────────────────────────────────────────────────────────────


async def test_a_delivered_envelope_reaches_the_handler(fake_aiokafka) -> None:
    seen: list[str] = []

    async def handler(envelope: EventEnvelope) -> None:
        seen.append(envelope.event_name)

    consumer = _consumer()
    await consumer.consume_batch(handler)  # يبني المستهلك
    fake_aiokafka[0].batches.append({"p0": [_Record(_encoded())]})

    outcomes = await consumer.consume_batch(handler)

    assert [outcome.handled for outcome in outcomes] == [True]
    assert seen == ["chat_turn_started"]


async def test_the_offset_is_committed_only_after_the_batch_is_handled(fake_aiokafka) -> None:
    order: list[str] = []

    async def handler(_: EventEnvelope) -> None:
        order.append("handled")

    consumer = _consumer()
    await consumer.consume_batch(handler)
    committed_before = fake_aiokafka[0].commits
    fake_aiokafka[0].batches.append({"p0": [_Record(_encoded())]})

    await consumer.consume_batch(handler)

    assert committed_before == 0
    assert fake_aiokafka[0].commits == 1
    assert order == ["handled"]


async def test_an_empty_poll_commits_nothing(fake_aiokafka) -> None:
    """تثبيتٌ على دفعةٍ فارغة رحلةُ شبكةٍ بلا معنى."""
    consumer = _consumer()
    assert await consumer.consume_batch(_noop) == []
    assert fake_aiokafka[0].commits == 0


async def test_the_poll_carries_an_explicit_timeout(fake_aiokafka) -> None:
    """انتظارٌ مفتوح على حدّ بنية تحتية يحوّل البطء إلى تعليق (D-189)."""
    consumer = _consumer()
    await consumer.consume_batch(_noop, max_records=7)

    assert fake_aiokafka[0].last_poll == {"timeout_ms": POLL_TIMEOUT_MS, "max_records": 7}
    assert 0 < POLL_TIMEOUT_MS <= 30_000


async def test_a_redelivered_envelope_is_skipped(fake_aiokafka) -> None:
    """«مرّة واحدة» يفرضها السجلّ المشترك — لا منطقٌ ثانٍ هنا."""
    calls: list[str] = []

    async def handler(envelope: EventEnvelope) -> None:
        calls.append(envelope.event_id)

    consumer = _consumer(ledger=IdempotencyLedger())
    await consumer.consume_batch(handler)
    encoded = _encoded()
    fake_aiokafka[0].batches.append({"p0": [_Record(encoded), _Record(encoded, offset=1)]})

    outcomes = await consumer.consume_batch(handler)

    assert [outcome.handled for outcome in outcomes] == [True, False]
    assert outcomes[1].duplicate is True
    assert len(calls) == 1


async def test_records_across_partitions_are_all_handled(fake_aiokafka) -> None:
    seen: list[str] = []

    async def handler(envelope: EventEnvelope) -> None:
        seen.append(envelope.event_id)

    consumer = _consumer()
    await consumer.consume_batch(handler)
    fake_aiokafka[0].batches.append(
        {"p0": [_Record(_encoded())], "p1": [_Record(_encoded())]},
    )

    outcomes = await consumer.consume_batch(handler)
    assert len(outcomes) == 2
    assert len(set(seen)) == 2


async def test_a_string_valued_record_is_accepted(fake_aiokafka) -> None:
    """بعض الوسطاء يسلّمون `str` لا `bytes` — لا ينبغي أن ينهار المستهلك."""
    consumer = _consumer()
    await consumer.consume_batch(_noop)
    fake_aiokafka[0].batches.append({"p0": [_Record(_encoded().decode("utf-8"))]})

    assert (await consumer.consume_batch(_noop))[0].handled is True


# ── الرسالة المسمومة ────────────────────────────────────────────────────────────


async def test_an_undecodable_record_goes_to_the_dead_letter_queue(fake_aiokafka) -> None:
    """
    بايتاتٌ لا تُفكَّك لن تُفكَّك بعد ساعة. إعادتها تُجمِّد القسم كاملاً.
    """
    dlq = InMemoryEventBus()
    consumer = _consumer(dlq_publisher=dlq)
    await consumer.consume_batch(_noop)
    fake_aiokafka[0].batches.append({"p0": [_Record(b"{not json")]})

    outcomes = await consumer.consume_batch(_noop)

    assert outcomes[0].disposition is Disposition.DEAD_LETTER
    dead = dlq.drain(Topic.DEAD_LETTER)
    assert len(dead) == 1
    assert dead[0].payload["original_topic"] == Topic.PRODUCT_EVENTS.value
    assert dead[0].payload["event_id_synthesized"] is True
    assert "{not json" in dead[0].payload["raw"]


async def test_an_undecodable_record_still_commits_so_the_partition_moves(fake_aiokafka) -> None:
    """
    الفرق بين «لا نفقد شيئاً» و«لا يتقدّم شيء»: الرسالة محفوظة في DLQ، فتُثبَّت إزاحتها.
    """
    consumer = _consumer(dlq_publisher=InMemoryEventBus())
    await consumer.consume_batch(_noop)
    fake_aiokafka[0].batches.append({"p0": [_Record(b"garbage")]})

    await consumer.consume_batch(_noop)
    assert fake_aiokafka[0].commits == 1


async def test_an_undecodable_record_without_a_dlq_is_still_reported(fake_aiokafka) -> None:
    consumer = _consumer()
    await consumer.consume_batch(_noop)
    fake_aiokafka[0].batches.append({"p0": [_Record(b"garbage")]})

    outcomes = await consumer.consume_batch(_noop)
    assert outcomes[0].disposition is Disposition.DEAD_LETTER
    assert isinstance(outcomes[0].error, MessagingError)


async def test_a_failing_handler_is_routed_by_the_shared_policy(fake_aiokafka) -> None:
    """القرار من `decide_disposition` المشترك — لا نسخة ثانية منه هنا."""

    async def handler(_: EventEnvelope) -> None:
        raise TimeoutError("db down")

    consumer = _consumer()
    await consumer.consume_batch(handler)
    fake_aiokafka[0].batches.append({"p0": [_Record(_encoded())]})

    outcomes = await consumer.consume_batch(handler)
    assert outcomes[0].disposition is Disposition.RETRY


# ── الإغلاق ─────────────────────────────────────────────────────────────────────


async def test_closing_stops_the_consumer(fake_aiokafka) -> None:
    consumer = _consumer()
    await consumer.consume_batch(_noop)
    await consumer.close()

    assert fake_aiokafka[0].stopped is True


async def test_closing_a_consumer_that_never_connected_is_safe() -> None:
    await _consumer().close()


def test_the_stop_timeout_is_bounded() -> None:
    """مستهلكٌ لا يُغادر مجموعته يُجمّد إعادة الموازنة للبقيّة."""
    assert 0 < STOP_TIMEOUT_SECONDS <= 30
