# ADR-007: Event streaming on the Kafka protocol (Redpanda)

**Status**: Accepted
**Date**: 2026-08-01
**Decision record**: D-201
**Supersedes**: nothing. **Related**: ADR-008 (durable workflows), D-006 (single writer)

---

## Context and problem statement

CogniForge has one real asynchronous path today: the orchestrator's transactional
outbox relaying mission events to Redis pub/sub. Everything else that *should* be a
fan-out is a direct in-process call — BKT evaluation calls the FSRS scheduler, the
analytics recorder writes a row and stops, and `NotificationRequested` has existed as a
domain-event class since its creation with **no producer, no consumer and no transport**.

The cost of that shape is not theoretical. Every new consumer of a learning event means
editing the turn path, which is the one code path where a mistake costs a student their
answer. And Redis pub/sub is fire-and-forget: a consumer that is down when a message is
published never learns the message existed.

The platform owner asked for Kafka adoption explicitly, after being told the
infrastructure cost is real for a product with no traffic yet. This ADR records the
decision and — more importantly — the discipline that makes it worth the cost.

## Decision drivers

* A consumer must be able to be added **without touching the student turn path**.
* A message must survive a consumer being down (Redis pub/sub does not give that).
* The operational weight must match a team of this size, today, not an imagined one.
* Nothing may become ZOMBIE: an event bus with no live consumer is worse than no bus.

## Decision

**Adopt the Kafka protocol, served by Redpanda, with the delivery discipline shipped as
tested code before the broker is ever switched on.**

Three parts, in this order:

1. **`shared/messaging/` — the discipline, dep-free and fully tested without a broker.**
   The envelope (`event_id`, `correlation_id`, `schema_version`, partition key), the
   closed topic registry, the idempotency ledger, the retry policy and the dead-letter
   decision. This is where "exactly once" actually lives; Kafka gives *at least once*,
   and everything past that is our code.
2. **A driver seam.** `EventPublisher` is two methods. `InMemoryEventBus` is the live
   default; `KafkaEventPublisher` (aiokafka, `acks=all`, `enable_idempotence`) takes over
   when `KAFKA_BOOTSTRAP_SERVERS` is set. No producer or consumer changes when it does.
3. **Redpanda, not Apache Kafka.** Kafka-protocol compatible from a single binary: no
   ZooKeeper, no separate controller quorum, roughly a tenth of the memory of a JVM
   broker. At this scale that is the honest weight.

### Why the in-memory driver is not a prototype

It is the live default, and it runs the *same* `consume_once` loop the Kafka consumer
will run — claim once, handle, then decide retry or dead-letter. That means the delivery
discipline is exercised on every product event today, and turning on Redpanda swaps a
driver rather than activating untested code.

### Reusing the outbox, not inventing a second publish path

`OUTBOX_RELAY_ENABLED` already ships and defaults on (D-031 → Step 4). The transactional
outbox stays the atomicity mechanism; the bus is the fan-out. `publish_many` is
explicitly documented as **not atomic** so nobody mistakes it for one.

### Topics are declared, never auto-created

`auto.create.topics.enable` lets one typo mint a topic nobody consumes, which then
swallows messages in silence until retention expires. Topics live in
`shared/messaging/topics.py` with their consumer group, partitions and retention, and
are created by an explicit `rpk topic create` step in compose. A topic with no declared
consumer is ZOMBIE by §6.6 and is not accepted into the registry.

## Consequences

**Positive**

* A new consumer is a subscriber registration, not an edit to the turn path.
* `NotificationRequested` finally has a real road: product event → bus → subscriber →
  a row in `notification_outbox`, guarded by a unique `event_id`.
* Poison messages are bounded: `MessagingError` is treated as permanent and dead-lettered
  immediately, because a message that cannot be parsed now will not parse in an hour, and
  retrying it freezes its whole partition.

**Negative, and accepted**

* Two more containers to operate (Redpanda + its topic bootstrap).
* An in-memory idempotency ledger is bounded by LRU, so a *very* old redelivery could
  slip through. Stated explicitly rather than papered over; a database-backed ledger is
  the documented next step if it ever matters.
* The in-memory idempotency ledger's LRU window remains the one soft edge; a
  database-backed ledger is the documented next step if it ever matters.

## Verification

* 92 tests over `shared/messaging` + `app/services/messaging`, 100% line and branch.
* The Kafka driver's decisions are tested against an injected fake producer: lazy
  connect, `acks=all`, mandatory partition key, explicit send timeout, loud failure when
  the library is absent.
* Live evidence of the in-process consumer: a guardian-link event produces exactly one
  `notification_outbox` row, and a redelivery of the same event produces none.

**Proven against a real broker (2026-08-01, CI job `event-stack-live`, 10 checks, 0
failures).** The ADR originally shipped with "not proven live — no Docker daemon in the
verifying environment". That is no longer true, and the run says exactly this:

* Redpanda healthy; all four topics present with the partitions and retention
  `TOPIC_SPECS` declares (3/30d, 3/14d, 1/7d, 1/90d).
* A round trip through the broker preserves `event_id`, `correlation_id` and the
  partition key.
* Redelivering the same `event_id` is skipped — the handler runs once. This is the
  exactly-once claim measured against a broker's real redelivery rather than a fake.
* An undecodable record is dead-lettered at a real offset and **the partition keeps
  moving** — the failure this ADR most wanted to prevent.

Booting it also produced three defects a config check cannot see: the Kafka consumer did
not exist at all, `rpk topic create … || true` swallowed every failure, and Redpanda
advertised only its in-network address so any host client hung. None were visible while
nothing ever connected.
