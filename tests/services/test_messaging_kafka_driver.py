"""اختبارات سائق Kafka بلا وسيط — D-201.

الوسيط غير مُشغَّل في هذه البيئة (لا Docker daemon)، وهذا مُصرَّح به في
`.memory/runtime_truth.md`. لكن **قرارات** السائق — إلزام المفتاح، المهلة الصريحة،
الاتصال الكسول، الفشل الواضح عند غياب المكتبة — كلّها قابلة للاختبار اليوم، وتأجيلها
إلى «حين يعمل الوسيط» يعني شحن سائقٍ بلا اختبارٍ واحد.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.services.messaging.kafka_publisher import SEND_TIMEOUT_SECONDS, KafkaEventPublisher
from app.services.messaging.runtime import build_envelope
from shared.messaging import MessagingError, Topic


class _FakeProducer:
    """مُنتِجٌ مزيّف يسجّل ما أُرسِل — يكفي لإثبات شكل النداء."""

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.started = False
        self.stopped = False
        self.sent: list[dict] = []

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def send_and_wait(self, topic, *, value, key, headers) -> None:
        self.sent.append({"topic": topic, "value": value, "key": key, "headers": headers})


@pytest.fixture
def fake_aiokafka(monkeypatch):
    """يحقن وحدة `aiokafka` مزيّفة **داخل الاختبار** (نظافة الاختبارات، D-105)."""
    created: list[_FakeProducer] = []

    def factory(**kwargs):
        producer = _FakeProducer(**kwargs)
        created.append(producer)
        return producer

    module = types.ModuleType("aiokafka")
    module.AIOKafkaProducer = factory
    monkeypatch.setitem(sys.modules, "aiokafka", module)
    return created


def _envelope(**overrides):
    params = {
        "topic": Topic.PRODUCT_EVENTS,
        "event_name": "chat_turn_started",
        "payload": {"user_id": 5},
        "partition_key": "user:5",
    }
    params.update(overrides)
    return build_envelope(**params)


async def test_building_the_publisher_opens_no_socket(fake_aiokafka) -> None:
    """
    الاتصال كسول: إقلاعٌ يُعلَّق على وسيطٍ بطيء يصنع «العملية حيّة والخدمة ميتة» (§0).
    """
    KafkaEventPublisher(bootstrap_servers="broker:9092")
    assert fake_aiokafka == []


async def test_publishing_starts_the_producer_once(fake_aiokafka) -> None:
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092")
    await publisher.publish(_envelope())
    await publisher.publish(_envelope())

    assert len(fake_aiokafka) == 1
    assert fake_aiokafka[0].started is True
    assert len(fake_aiokafka[0].sent) == 2


async def test_the_producer_is_configured_for_durability(fake_aiokafka) -> None:
    """`acks=1` يفقد رسائل عند سقوط القائد — وحدثُ تعلّمٍ ضائع لا يُعوَّض."""
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092", client_id="test")
    await publisher.publish(_envelope())

    kwargs = fake_aiokafka[0].kwargs
    assert kwargs["acks"] == "all"
    assert kwargs["enable_idempotence"] is True
    assert kwargs["client_id"] == "test"


async def test_the_partition_key_travels_with_the_message(fake_aiokafka) -> None:
    """بلا مفتاح تتوزّع أحداث الطالب على أقسام فتصل بترتيبٍ غير ترتيب وقوعها."""
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092")
    await publisher.publish(_envelope())

    assert fake_aiokafka[0].sent[0]["key"] == "user:5"


async def test_a_keyed_topic_rejects_a_keyless_envelope(fake_aiokafka) -> None:
    """
    الرفض عند المُنتِج: مفتاحٌ غائب لا يُكتشَف إلّا كترتيبٍ خاطئ عند القارئ بعد أسابيع.
    """
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092")
    with pytest.raises(MessagingError, match="partition key"):
        await publisher.publish(_envelope(partition_key=None))


async def test_headers_are_encoded_for_the_wire(fake_aiokafka) -> None:
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092")
    envelope = _envelope()
    object.__setattr__(envelope, "headers", {"x-trace": "abc"})
    await publisher.publish(envelope)

    assert fake_aiokafka[0].sent[0]["headers"] == [("x-trace", b"abc")]


async def test_a_missing_driver_library_fails_loudly(monkeypatch) -> None:
    """
    فشلٌ واضح عند غياب المكتبة أفضل من ناشرٍ يبدو حيّاً ولا ينشر.
    """
    monkeypatch.setitem(sys.modules, "aiokafka", None)
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092")
    with pytest.raises(MessagingError, match="aiokafka"):
        await publisher.publish(_envelope(partition_key="user:5"))


async def test_closing_stops_the_producer(fake_aiokafka) -> None:
    publisher = KafkaEventPublisher(bootstrap_servers="broker:9092")
    await publisher.publish(_envelope())
    await publisher.close()

    assert fake_aiokafka[0].stopped is True


async def test_closing_a_publisher_that_never_connected_is_safe() -> None:
    await KafkaEventPublisher(bootstrap_servers="broker:9092").close()


def test_the_send_timeout_is_explicit_and_bounded() -> None:
    """`timeout=None` يعني انتظاراً مفتوحاً — والبطء على حدّ خدمة يصير تعليقاً (D-189)."""
    assert 0 < SEND_TIMEOUT_SECONDS <= 30
