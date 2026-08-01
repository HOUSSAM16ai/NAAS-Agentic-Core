"""اختبارات طبقة الرسائل — D-201.

كل ما يُختبَر هنا يعمل **بلا وسيط مُشغَّل**، وهذا مقصود: انضباط التسليم (مرّة واحدة ·
الرسالة المسمومة · سقف المحاولات) هو جوهر تبنّي Kafka، وتأجيله إلى «حين يعمل الوسيط»
يعني شحنَه بلا اختبارٍ واحد.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shared.messaging import (
    ConsumeOutcome,
    Disposition,
    EventEnvelope,
    IdempotencyLedger,
    InMemoryEventBus,
    MessagingError,
    RetryPolicy,
    Topic,
    UnknownTopicError,
    consume_once,
    decide_disposition,
    new_event_id,
    spec_for,
    validate_topic,
)
from shared.messaging.envelope import MAX_PAYLOAD_BYTES, SCHEMA_VERSION

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


def make_envelope(**overrides) -> EventEnvelope:
    base = {
        "event_id": "evt-1",
        "event_name": "review_scheduled",
        "topic": Topic.LEARNING_EVALUATED.value,
        "payload": {"user_id": 7, "concept_id": "complex_numbers"},
        "occurred_at": NOW,
        "partition_key": "user:7",
        "correlation_id": "corr-abc",
    }
    base.update(overrides)
    return EventEnvelope(**base)


# ── الظرف ──────────────────────────────────────────────────────────────────────


def test_an_envelope_round_trips_through_the_wire() -> None:
    original = make_envelope()
    restored = EventEnvelope.from_json(original.to_json())
    assert restored == original


def test_an_envelope_without_an_event_id_is_rejected() -> None:
    """بلا مُعرَّفٍ ثابت لا وجود لـ«مرّة واحدة» — الرفض عند الإنشاء لا عند المستهلك."""
    with pytest.raises(MessagingError, match="event_id"):
        make_envelope(event_id="")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("event_name", "", "event_name"),
        ("topic", "", "topic"),
        ("schema_version", 0, "schema_version"),
        ("delivery_attempt", 0, "delivery_attempt"),
    ],
)
def test_a_malformed_envelope_is_rejected_at_construction(field, value, message) -> None:
    with pytest.raises(MessagingError, match=message):
        make_envelope(**{field: value})


def test_a_naive_timestamp_is_rejected() -> None:
    """
    وقتٌ بلا منطقة يُقرأ في كل خدمة بمنطقتها — نفس صنف عطب المواظبة (D-195).
    """
    with pytest.raises(MessagingError, match="timezone-aware"):
        make_envelope(occurred_at=datetime(2026, 8, 1, 12, 0))


def test_a_non_serializable_payload_raises_rather_than_dropping() -> None:
    with pytest.raises(MessagingError, match="JSON-serializable"):
        make_envelope(payload={"when": object()}).to_json()


def test_an_oversized_envelope_fails_at_the_producer() -> None:
    """
    الفشل عند المُنتِج برسالة واضحة أفضل من رفضٍ غامض عند الوسيط في الإنتاج.
    """
    with pytest.raises(MessagingError, match="exceeds"):
        make_envelope(payload={"blob": "x" * (MAX_PAYLOAD_BYTES + 1)}).to_json()


def test_the_timestamp_is_normalized_to_utc_on_the_wire() -> None:
    local = NOW.astimezone(tz=None).replace(tzinfo=None).replace(tzinfo=UTC) + timedelta(hours=0)
    assert make_envelope(occurred_at=local).as_dict()["occurred_at"].endswith("+00:00")


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("not json", "malformed"),
        ("[1, 2]", "JSON object"),
        ('{"event_id": "a"}', "occurred_at"),
        ('{"event_id": "a", "occurred_at": "yesterday"}', "ISO-8601"),
        ('{"event_id":"a","occurred_at":"2026-08-01T00:00:00+00:00","payload":5}', "payload"),
        (
            '{"event_id":"a","occurred_at":"2026-08-01T00:00:00+00:00","headers":5}',
            "headers",
        ),
    ],
)
def test_a_corrupt_wire_message_raises_a_messaging_error(raw: str, message: str) -> None:
    """
    الرفع هنا هو ما يُرسِل الرسالة المسمومة إلى DLQ بقرارٍ صريح بدل حلقةٍ لا تنتهي.
    """
    with pytest.raises(MessagingError, match=message):
        EventEnvelope.from_json(raw)


def test_a_missing_payload_defaults_to_empty() -> None:
    restored = EventEnvelope.from_json(
        '{"event_id":"a","event_name":"n","topic":"t","occurred_at":"2026-08-01T00:00:00+00:00"}'
    )
    assert restored.payload == {}
    assert restored.headers == {}
    assert restored.schema_version == SCHEMA_VERSION


def test_headers_are_coerced_to_strings() -> None:
    restored = EventEnvelope.from_json(
        '{"event_id":"a","event_name":"n","topic":"t",'
        '"occurred_at":"2026-08-01T00:00:00+00:00","headers":{"x":5}}'
    )
    assert restored.headers == {"x": "5"}


def test_the_next_attempt_keeps_the_same_event_id() -> None:
    """المُعرَّف يبقى وإلّا صارت كلّ إعادة محاولة حدثاً جديداً — وانهار العقد كلّه."""
    first = make_envelope()
    second = first.next_attempt()
    assert second.event_id == first.event_id
    assert second.delivery_attempt == 2


def test_new_event_ids_are_unique() -> None:
    assert new_event_id() != new_event_id()


# ── سجلّ المواضيع ───────────────────────────────────────────────────────────────


def test_an_unregistered_topic_is_rejected() -> None:
    """
    خطأٌ مطبعي واحد يُنشئ موضوعاً بلا مستهلك، فتُبتلَع الرسائل حتى ينتهي الاحتفاظ.
    """
    with pytest.raises(UnknownTopicError, match="unknown topic"):
        validate_topic("cogniforge.typo.v1")


def test_every_registered_topic_declares_a_consumer() -> None:
    """موضوعٌ بلا مستهلك مُعلَن هو ZOMBIE بتعريف §6.6."""
    for topic in Topic:
        spec = spec_for(topic)
        assert spec.consumer_group
        assert spec.partitions >= 1
        assert spec.retention_days >= 1
        assert spec.description


def test_the_dead_letter_topic_keeps_messages_longest() -> None:
    """الرسالة الميتة تُفحَص بشرياً — وقد يمرّ أسبوعان قبل أن ينتبه أحد."""
    dead_letter = spec_for(Topic.DEAD_LETTER)
    others = [spec_for(topic) for topic in Topic if topic is not Topic.DEAD_LETTER]
    assert all(dead_letter.retention_days > spec.retention_days for spec in others)


# ── سياسة إعادة المحاولة ────────────────────────────────────────────────────────


def test_the_backoff_grows_then_stops_growing() -> None:
    """بلا سقف يصير التراجع الأُسّي انتظاراً بالساعات — خدمةٌ تبدو معلّقة."""
    policy = RetryPolicy(base_delay_seconds=1.0, max_delay_seconds=8.0)
    assert [policy.delay_for(attempt) for attempt in range(1, 7)] == [1, 2, 4, 8, 8, 8]


def test_an_invalid_attempt_number_raises() -> None:
    with pytest.raises(MessagingError, match="attempt"):
        RetryPolicy().delay_for(0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"base_delay_seconds": 0},
        {"base_delay_seconds": 10.0, "max_delay_seconds": 1.0},
    ],
)
def test_an_incoherent_policy_is_rejected(kwargs) -> None:
    with pytest.raises(MessagingError):
        RetryPolicy(**kwargs)


def test_a_permanently_broken_message_goes_straight_to_the_dead_letter_queue() -> None:
    """
    رسالةٌ لا تُفكَّك لن تُفكَّك بعد ساعة. إعادتها تُجمِّد القسم كاملاً — لا يتقدّم أيّ
    حدثٍ خلفها. هذا هو العطب الذي يُسقِط أنظمة Kafka في الإنتاج.
    """
    decision = decide_disposition(make_envelope(), MessagingError("cannot parse"))
    assert decision is Disposition.DEAD_LETTER


def test_a_transient_failure_is_retried() -> None:
    assert decide_disposition(make_envelope(), TimeoutError("db down")) is Disposition.RETRY


def test_retries_stop_at_the_ceiling() -> None:
    exhausted = make_envelope(delivery_attempt=5)
    assert decide_disposition(exhausted, TimeoutError()) is Disposition.DEAD_LETTER


# ── المُعالَجة مرّة واحدة ────────────────────────────────────────────────────────


def test_the_same_event_is_claimed_only_once() -> None:
    """
    إعادة التسليم هي الوضع **الطبيعي** في Kafka. بلا هذا السجلّ يُضاعِف كلّ عدّاد نفسه.
    """
    ledger = IdempotencyLedger()
    envelope = make_envelope()
    assert ledger.claim(envelope) is True
    assert ledger.claim(envelope) is False


def test_the_ledger_is_bounded_so_a_long_lived_consumer_does_not_leak() -> None:
    ledger = IdempotencyLedger(capacity=3)
    for index in range(10):
        ledger.remember(f"evt-{index}")
    assert len(ledger) == 3
    assert ledger.seen("evt-9") is True
    assert ledger.seen("evt-0") is False


def test_reading_an_entry_keeps_it_alive() -> None:
    """الإخلاء بـLRU: الحدث المتكرّر حديثاً يجب ألّا يُخلى قبل حدثٍ خامل."""
    ledger = IdempotencyLedger(capacity=2)
    ledger.remember("a")
    ledger.remember("b")
    assert ledger.seen("a") is True
    ledger.remember("c")
    assert ledger.seen("a") is True
    assert ledger.seen("b") is False


def test_an_empty_event_id_cannot_be_remembered() -> None:
    with pytest.raises(MessagingError, match="event_id"):
        IdempotencyLedger().remember("")


def test_a_zero_capacity_ledger_is_rejected() -> None:
    with pytest.raises(MessagingError, match="capacity"):
        IdempotencyLedger(capacity=0)


def test_the_ledger_reports_its_capacity() -> None:
    assert IdempotencyLedger(capacity=5).capacity == 5


# ── الناقل في الذاكرة ───────────────────────────────────────────────────────────


async def test_publishing_and_draining_preserves_order() -> None:
    bus = InMemoryEventBus()
    await bus.publish(make_envelope(event_id="a"))
    await bus.publish(make_envelope(event_id="b"))
    assert [item.event_id for item in bus.drain(Topic.LEARNING_EVALUATED)] == ["a", "b"]
    assert bus.pending(Topic.LEARNING_EVALUATED) == 0


async def test_the_cumulative_counter_survives_draining() -> None:
    """المقاييس تحتاج عدداً تراكمياً — عدّادٌ يُصفَّر عند السحب يقيس السحب لا النشر."""
    bus = InMemoryEventBus()
    await bus.publish(make_envelope())
    bus.drain(Topic.LEARNING_EVALUATED)
    assert bus.published_total(Topic.LEARNING_EVALUATED) == 1


async def test_publishing_to_an_unregistered_topic_fails() -> None:
    with pytest.raises(UnknownTopicError):
        await InMemoryEventBus().publish(make_envelope(topic="cogniforge.made.up.v1"))


async def test_a_batch_reports_how_many_were_published() -> None:
    bus = InMemoryEventBus()
    envelopes = [make_envelope(event_id=f"e{index}") for index in range(3)]
    assert await bus.publish_many(envelopes) == 3


# ── حلقة الاستهلاك ──────────────────────────────────────────────────────────────


async def test_a_handled_event_reports_success() -> None:
    seen: list[str] = []

    async def handler(envelope: EventEnvelope) -> None:
        seen.append(envelope.event_id)

    outcome = await consume_once(make_envelope(), handler, ledger=IdempotencyLedger())
    assert outcome == ConsumeOutcome(handled=True)
    assert seen == ["evt-1"]


async def test_a_redelivered_event_is_skipped_without_running_the_handler() -> None:
    """التخطّي هنا ليس فشلاً صامتاً — إنّه العقد نفسه، ولذلك يُبلَّغ صراحةً."""
    calls: list[str] = []

    async def handler(envelope: EventEnvelope) -> None:
        calls.append(envelope.event_id)

    ledger = IdempotencyLedger()
    envelope = make_envelope()
    await consume_once(envelope, handler, ledger=ledger)
    outcome = await consume_once(envelope, handler, ledger=ledger)

    assert outcome.duplicate is True
    assert outcome.handled is False
    assert calls == ["evt-1"]


async def test_a_transient_handler_failure_asks_for_a_retry() -> None:
    async def handler(_: EventEnvelope) -> None:
        raise TimeoutError("db down")

    outcome = await consume_once(make_envelope(), handler, ledger=IdempotencyLedger())
    assert outcome.disposition is Disposition.RETRY
    assert isinstance(outcome.error, TimeoutError)


async def test_a_poisoned_message_is_published_to_the_dead_letter_queue_with_its_cause() -> None:
    """
    رسالةٌ ميتة بلا سببٍ مرفق تُجبِر الفاحص على إعادة بناء الحادثة من سجلّات قد دارت.
    """
    bus = InMemoryEventBus()

    async def handler(_: EventEnvelope) -> None:
        raise MessagingError("payload shape unknown")

    outcome = await consume_once(
        make_envelope(), handler, ledger=IdempotencyLedger(), publisher=bus
    )

    assert outcome.disposition is Disposition.DEAD_LETTER
    dead = bus.drain(Topic.DEAD_LETTER)
    assert len(dead) == 1
    assert dead[0].payload["original_topic"] == Topic.LEARNING_EVALUATED.value
    assert dead[0].payload["error_type"] == "MessagingError"
    assert dead[0].payload["original_payload"] == {"user_id": 7, "concept_id": "complex_numbers"}
    assert dead[0].correlation_id == "corr-abc"


async def test_a_dead_letter_without_a_publisher_still_reports_its_disposition() -> None:
    async def handler(_: EventEnvelope) -> None:
        raise MessagingError("bad")

    outcome = await consume_once(make_envelope(), handler, ledger=IdempotencyLedger())
    assert outcome.disposition is Disposition.DEAD_LETTER


async def test_a_custom_policy_shortens_the_road_to_the_dead_letter_queue() -> None:
    async def handler(_: EventEnvelope) -> None:
        raise TimeoutError()

    outcome = await consume_once(
        make_envelope(delivery_attempt=2),
        handler,
        ledger=IdempotencyLedger(),
        policy=RetryPolicy(max_attempts=2),
    )
    assert outcome.disposition is Disposition.DEAD_LETTER


# ── التحقّق عند الحافة (D-204) ──────────────────────────────────────────────────


def test_a_non_string_partition_key_is_rejected_rather_than_coerced() -> None:
    """
    `str(value)` كان سيقبل `partition_key: 5` ويحوّله إلى `"5"` بصمت، فيبدو المفتاح
    سليماً وهو ليس ما أرسله المُنتِج — والترتيب يُبنى على مفتاحٍ مخترَع.
    """
    with pytest.raises(MessagingError, match="partition_key must be a string"):
        EventEnvelope.from_json(
            '{"event_id":"a","event_name":"n","topic":"t",'
            '"occurred_at":"2026-08-01T00:00:00+00:00","partition_key":5}'
        )


def test_a_non_string_correlation_id_is_rejected() -> None:
    with pytest.raises(MessagingError, match="correlation_id must be a string"):
        EventEnvelope.from_json(
            '{"event_id":"a","event_name":"n","topic":"t",'
            '"occurred_at":"2026-08-01T00:00:00+00:00","correlation_id":{"a":1}}'
        )


def test_a_null_partition_key_is_still_allowed() -> None:
    """الغياب مشروع؛ النوع الخاطئ ليس كذلك."""
    restored = EventEnvelope.from_json(
        '{"event_id":"a","event_name":"n","topic":"t",'
        '"occurred_at":"2026-08-01T00:00:00+00:00","partition_key":null}'
    )
    assert restored.partition_key is None


@pytest.mark.parametrize("field", ["schema_version", "delivery_attempt"])
def test_a_boolean_is_not_accepted_as_an_integer(field: str) -> None:
    """
    `isinstance(True, int)` صحيحة في بايثون — فبلا حارسٍ صريح تمرّ `true` كـ`1`
    و`delivery_attempt` يبدو سليماً بينما المُنتِج أرسل قيمة منطقية.
    """
    with pytest.raises(MessagingError, match=f"{field} must be an integer"):
        EventEnvelope.from_json(
            '{"event_id":"a","event_name":"n","topic":"t",'
            f'"occurred_at":"2026-08-01T00:00:00+00:00","{field}":true}}'
        )


def test_a_string_integer_is_rejected_rather_than_parsed() -> None:
    """`"3"` ليست `3` على السلك — والتحويل الصامت يُخفي مُنتِجاً يكتب النوع الخطأ."""
    with pytest.raises(MessagingError, match="schema_version must be an integer"):
        EventEnvelope.from_json(
            '{"event_id":"a","event_name":"n","topic":"t",'
            '"occurred_at":"2026-08-01T00:00:00+00:00","schema_version":"3"}'
        )


def test_the_backoff_never_returns_more_than_its_ceiling() -> None:
    """حارسٌ على إعادة الصياغة: `min` استُبدل بشرطٍ صريح لأجل التحقّق من النوع."""
    policy = RetryPolicy(base_delay_seconds=2.0, max_delay_seconds=5.0)
    assert policy.delay_for(1) == 2.0
    assert policy.delay_for(10) == 5.0
    assert isinstance(policy.delay_for(3), float)
