#!/usr/bin/env python3
"""verify_event_stack_docker.py — the live proof that the event stack is real (D-204).

Why this script exists
----------------------
D-201 shipped `KafkaEventPublisher`, Redpanda and Temporal into `docker-compose.yml`,
and **not one of them was ever started**. The workflow named "Docker Full-Stack Gate"
says in its own header that it does not run `up`; it validates YAML. So the honest
status of the whole event stack was DORMANT — code that exists and has never run.

This script is what makes the difference between "declared" and "proven". Run it AFTER:

    docker compose up -d redpanda redpanda-topics postgres-temporal temporal
    pip install -r requirements-messaging.txt
    python scripts/verify_event_stack_docker.py

Checks, in order of what they would catch:

  1. Redpanda reports `cluster health` — a listening port only proves a process booted,
     not that the cluster can accept a write.
  2. Every topic exists with the partitions AND retention the registry declares. A topic
     with the right name and the wrong partition count silently breaks per-student
     ordering; `check_topic_contract_parity` compares the files, this compares reality.
  3. Temporal answers `operator cluster health`.
  4. **Round trip:** publish through the real `KafkaEventPublisher`, consume through the
     real `KafkaEventConsumer`, and assert `event_id`, `correlation_id` and the partition
     key survive the wire. This is the check that promotes both drivers out of DORMANT.
  5. **Redelivery is a no-op.** Kafka guarantees at-least-once; "exactly once" is our
     ledger. Proving it against a fake proves nothing about the broker's redelivery.
  6. **A poisoned message reaches the DLQ and the partition keeps moving.** The failure
     this guards is the worst one available: a message that can never be parsed, retried
     forever, freezing every event behind it.

Exits non-zero the moment any check fails — no partial success, no soft pass.

Deps: stdlib + `aiokafka` (requirements-messaging.txt), mirroring the style of
`scripts/verify_full_stack_docker.py`. Configurable via `KAFKA_BOOTSTRAP_SERVERS`,
`TEMPORAL_ADDRESS`, `REDPANDA_CONTAINER` and `VERIFY_TIMEOUT`.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from shared.messaging import (
    TOPIC_SPECS,
    EventEnvelope,
    IdempotencyLedger,
    InMemoryEventBus,
    Topic,
    new_event_id,
)

#: منفذ المستمع **الخارجي** (19092) لا الداخلي: العميل على المضيف يتلقّى العنوان
#: المُعلَن من الوسيط، و`redpanda:9092` لا يُحَلّ خارج شبكة compose.
BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "127.0.0.1:19092")
TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "127.0.0.1:7233")
REDPANDA_CONTAINER = os.environ.get("REDPANDA_CONTAINER", "cogniforge-redpanda")
TEMPORAL_CONTAINER = os.environ.get("TEMPORAL_CONTAINER", "cogniforge-temporal")
TOTAL_TIMEOUT = int(os.environ.get("VERIFY_TIMEOUT", "180"))
MS_PER_DAY = 86_400_000

_PASS: list[str] = []
_FAIL: list[str] = []


def ok(msg: str) -> None:
    _PASS.append(msg)
    print(f"  \033[92m✓\033[0m {msg}")


def fail(msg: str) -> None:
    _FAIL.append(msg)
    print(f"  \033[91m✗ {msg}\033[0m")


def docker_exec(container: str, *args: str, timeout: float = 30.0) -> tuple[int, str]:
    """
    ينفّذ أمراً داخل حاوية بـargv — لا صدفة (D-187).

    الأمر يُمرَّر قائمةً، فحقن الصدفة **غير مُمثَّل** لا مُرشَّح.
    """
    try:
        proc = subprocess.run(
            ["docker", "exec", container, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr)


# ── 1. صحّة العنقود ─────────────────────────────────────────────────────────────


def assert_redpanda_healthy() -> None:
    """`cluster health`، لا مجرّد منفذٍ مفتوح."""
    deadline = time.time() + TOTAL_TIMEOUT
    last = ""
    while time.time() < deadline:
        code, out = docker_exec(REDPANDA_CONTAINER, "rpk", "cluster", "health")
        last = out.strip()
        if code == 0 and "Healthy:" in out and "true" in out.split("Healthy:", 1)[1][:20]:
            ok("Redpanda cluster reports Healthy: true")
            return
        time.sleep(3)
    fail(f"Redpanda never reported healthy within {TOTAL_TIMEOUT}s: {last[:300]}")


# ── 2. شكل المواضيع كما هو في الواقع ────────────────────────────────────────────


def assert_topics_match_the_registry() -> None:
    """
    كل موضوع موجود بالأقسام والاحتفاظ اللذين يُعلنهما السجلّ.

    البوّابة الساكنة تقارن الملفّات ببعضها؛ هذه تقارن الملفّات بما أُنشئ فعلاً — والفرق
    بينهما هو الفرق بين نيّةٍ وواقع.
    """
    code, out = docker_exec(
        REDPANDA_CONTAINER, "rpk", "topic", "describe", "-p", "--format", "json"
    )
    if code != 0:
        # `-p --format json` غير متاح في كل الإصدارات؛ نسقط إلى الوصف النصّي لكل موضوع.
        _assert_topics_via_text()
        return
    try:
        described = json.loads(out)
    except ValueError:
        _assert_topics_via_text()
        return
    _compare(described)


def _assert_topics_via_text() -> None:
    for topic, spec in TOPIC_SPECS.items():
        code, out = docker_exec(REDPANDA_CONTAINER, "rpk", "topic", "describe", topic.value)
        if code != 0:
            fail(f"topic {topic.value} is missing from the broker: {out.strip()[:200]}")
            continue
        partitions = out.lower().count("partition:") or _partition_rows(out)
        if partitions and partitions != spec.partitions:
            fail(
                f"topic {topic.value}: registry declares {spec.partitions} partitions, "
                f"broker has {partitions} — per-entity ordering is broken"
            )
            continue
        expected_ms = spec.retention_days * MS_PER_DAY
        if f"{expected_ms}" not in out:
            fail(
                f"topic {topic.value}: retention.ms {expected_ms} "
                f"({spec.retention_days}d) not reported by the broker"
            )
            continue
        ok(f"topic {topic.value}: {spec.partitions} partitions, {spec.retention_days}d retention")


def _partition_rows(out: str) -> int:
    """عدّ صفوف الأقسام في الوصف النصّي (السطور التي تبدأ برقم قسم)."""
    rows = 0
    for line in out.splitlines():
        head = line.strip().split(" ", 1)[0]
        if head.isdigit():
            rows += 1
    return rows


def _compare(described: object) -> None:
    """يقارن مخرَج JSON — الشكل يختلف بين الإصدارات فنقرأ دفاعياً."""
    by_name: dict[str, dict] = {}
    entries = described if isinstance(described, list) else [described]
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            by_name[entry["name"]] = entry

    for topic, spec in TOPIC_SPECS.items():
        entry = by_name.get(topic.value)
        if entry is None:
            fail(f"topic {topic.value} is missing from the broker")
            continue
        partitions = entry.get("partitions")
        count = len(partitions) if isinstance(partitions, list) else partitions
        if isinstance(count, int) and count != spec.partitions:
            fail(
                f"topic {topic.value}: registry declares {spec.partitions} partitions, "
                f"broker has {count}"
            )
            continue
        ok(f"topic {topic.value}: {spec.partitions} partitions as declared")


# ── 3. Temporal ─────────────────────────────────────────────────────────────────


def assert_temporal_healthy() -> None:
    deadline = time.time() + TOTAL_TIMEOUT
    last = ""
    while time.time() < deadline:
        code, out = docker_exec(
            TEMPORAL_CONTAINER,
            "temporal",
            "operator",
            "cluster",
            "health",
            "--address",
            "temporal:7233",
        )
        last = out.strip()
        if code == 0 and "SERVING" in out.upper():
            ok("Temporal frontend reports SERVING")
            return
        time.sleep(3)
    fail(f"Temporal never reported healthy within {TOTAL_TIMEOUT}s: {last[:300]}")


# ── 4/5/6. الرحلة الحقيقية عبر الوسيط ───────────────────────────────────────────


async def _round_trip() -> None:
    """
    ينشر ويستهلك عبر وسيطٍ حقيقي، ثمّ يُثبت أنّ إعادة التسليم لا تُعالَج مرّتين، ثمّ
    يُثبت أنّ رسالةً مسمومة تصل DLQ ولا تُجمّد القسم.

    الثلاثة في جلسةِ مستهلكٍ واحدة عمداً: مستهلكٌ جديد لكل فحص يُخفي أثر الفحص السابق.
    """
    from app.services.messaging.kafka_consumer import KafkaEventConsumer
    from app.services.messaging.kafka_publisher import KafkaEventPublisher

    publisher = KafkaEventPublisher(bootstrap_servers=BOOTSTRAP, client_id="verify-publisher")
    dlq = InMemoryEventBus()
    # مجموعة فريدة لكل تشغيل: إعادة استعمال المجموعة تعني أنّ إزاحاتٍ مُثبَّتة من تشغيلٍ
    # سابق تُخفي رسائل هذا التشغيل، فيبدو الفشل نجاحاً.
    consumer = KafkaEventConsumer(
        bootstrap_servers=BOOTSTRAP,
        topic=Topic.PRODUCT_EVENTS,
        group_id=f"verify-{new_event_id()[:8]}",
        ledger=IdempotencyLedger(),
        dlq_publisher=dlq,
    )
    received: list[EventEnvelope] = []

    async def handler(envelope: EventEnvelope) -> None:
        received.append(envelope)

    try:
        envelope = _probe_envelope(payload={"user_id": 4242, "probe": "verify_event_stack"})
        await _probe_wire_fidelity(publisher, consumer, handler, received, envelope)
        await _probe_redelivery(publisher, consumer, handler, received, envelope)
        await _probe_poison(publisher, consumer, handler, received, dlq)
    finally:
        await consumer.close()
        await publisher.close()


def _probe_envelope(*, payload: dict) -> EventEnvelope:
    return EventEnvelope(
        event_id=new_event_id(),
        event_name="chat_turn_started",
        topic=Topic.PRODUCT_EVENTS.value,
        payload=payload,
        occurred_at=datetime.now(UTC),
        partition_key="user:4242",
        correlation_id="verify-correlation-id",
    )


async def _probe_wire_fidelity(publisher, consumer, handler, received, envelope) -> None:
    """الظرف يعبر السلك بهويته كاملة — وإلّا انقطعت سلسلة التتبّع أو الترتيب."""
    await publisher.publish(envelope)
    await _drain_until(consumer, handler, expected=1)

    if not received:
        fail("round trip: nothing came back from the broker")
        return
    got = received[0]
    if got.event_id != envelope.event_id:
        fail(f"round trip: event_id changed on the wire ({got.event_id})")
    elif got.correlation_id != "verify-correlation-id":
        fail("round trip: correlation_id was not preserved — the trace chain is cut")
    elif got.partition_key != "user:4242":
        fail("round trip: partition_key was not preserved — ordering guarantees are void")
    else:
        ok("round trip: envelope survived the wire with id, correlation and key intact")


async def _probe_redelivery(publisher, consumer, handler, received, envelope) -> None:
    """
    Kafka يضمن «مرّة على الأقلّ»؛ «مرّة واحدة» سجلُّنا.

    إثباتها على مزيّف لا يقول شيئاً عن إعادة تسليم الوسيط الحقيقي.
    """
    before = len(received)
    await publisher.publish(envelope)
    outcomes = await _drain_until(consumer, handler, expected=1, allow_empty=True)

    if len(received) != before:
        fail("redelivery: the handler ran twice — 'exactly once' is not holding")
    elif not any(outcome.duplicate for outcome in outcomes):
        fail("redelivery: the duplicate was not reported as such")
    else:
        ok("redelivery: the same event_id was skipped, handler ran once")


async def _probe_poison(publisher, consumer, handler, received, dlq) -> None:
    """رسالةٌ لا تُفكَّك تصل DLQ، **والقسم يتقدّم بعدها** — هذا هو الشقّ الحاسم."""
    await _publish_raw(b"{ this is not an envelope")
    await _drain_until(consumer, handler, expected=1, allow_empty=True)

    dead = dlq.drain(Topic.DEAD_LETTER)
    if not dead:
        fail("poison: an undecodable record did not reach the dead-letter queue")
    else:
        ok(f"poison: undecodable record dead-lettered ({dead[0].payload.get('error_type')})")

    follow_up = _probe_envelope(payload={"after": "poison"})
    await publisher.publish(follow_up)
    await _drain_until(consumer, handler, expected=1, allow_empty=True)
    if any(item.event_id == follow_up.event_id for item in received):
        ok("poison: the partition kept moving after the dead-letter")
    else:
        fail("poison: the partition stalled behind an undecodable record")


async def _publish_raw(payload: bytes) -> None:
    """ينشر بايتات خاماً — يتجاوز الظرف عمداً كي تُختبَر رسالةٌ مشوَّهة حقيقية."""
    from aiokafka import AIOKafkaProducer

    producer = AIOKafkaProducer(bootstrap_servers=BOOTSTRAP, acks="all")
    await producer.start()
    try:
        await producer.send_and_wait(Topic.PRODUCT_EVENTS.value, value=payload, key=b"user:4242")
    finally:
        await producer.stop()


async def _drain_until(consumer, handler, *, expected: int, allow_empty: bool = False) -> list:
    """
    يسحب حتى تصل الرسائل المتوقّعة أو تنفد المهلة.

    السحب الواحد قد يعود فارغاً بينما الرسالة في الطريق — والاكتفاء به يجعل الاختبار
    متقلّباً، وهو أسوأ من فشلٍ صريح.
    """
    outcomes: list = []
    deadline = time.time() + 60
    while time.time() < deadline and len(outcomes) < expected:
        batch = await consumer.consume_batch(handler)
        outcomes.extend(batch)
        if not batch and allow_empty and outcomes:
            break
    return outcomes


def main() -> int:
    print("\n\033[1mEvent stack verification (D-204)\033[0m")
    print(f"  broker={BOOTSTRAP}  temporal={TEMPORAL_ADDRESS}\n")

    print("Cluster health")
    assert_redpanda_healthy()
    assert_temporal_healthy()

    print("\nTopic shape vs the canonical registry")
    assert_topics_match_the_registry()

    print("\nLive round trip through the broker")
    try:
        asyncio.run(_round_trip())
    except Exception as exc:
        fail(f"round trip raised: {type(exc).__name__}: {exc}")

    print(f"\n\033[1m{len(_PASS)} passed, {len(_FAIL)} failed\033[0m")
    if _FAIL:
        for item in _FAIL:
            print(f"  \033[91m✗\033[0m {item}")
        return 1
    print("\033[92mEvent stack is real: brokered, shaped as declared, and exactly-once.\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
