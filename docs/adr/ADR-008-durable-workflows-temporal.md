# ADR-008: Durable workflows on Temporal

**Status**: Accepted (worker DORMANT until a server exists)
**Date**: 2026-08-01
**Decision record**: D-201
**Related**: ADR-007 (event streaming), D-195 (Africa/Algiers), D-196 (guardian report)

---

## Context and problem statement

Three pieces of work in this platform run for minutes to hours, must survive a restart,
and need to be cancellable and observable:

* the **weekly guardian report** — an aggregation across every linked student;
* **corpus ingestion** — validate, chunk, embed, index;
* **streak-reminder fan-out** — a wide daily broadcast.

Today none of them exists as a managed process. The obvious cheap answer is cron plus a
retry loop, and it fails in a specific way: a run that dies halfway leaves no record of
how far it got, so the next run either redoes everything or silently skips. For the
guardian report that means a parent gets a report built from a partial week, and nobody
finds out.

## Decision drivers

* Resumability after a crash, without hand-rolled checkpointing.
* Cancellation during an incident — a fan-out that cannot be stopped is a liability.
* Visibility: "which run is stuck, and on which step" must be answerable.
* The decisions themselves must be testable **without** running a workflow engine.

## Decision

**Adopt Temporal for exactly those three workflows, and keep every decision outside it.**

The split is the whole point:

* **`shared/workflows/plans.py` is data.** Steps, timeouts, retry ceilings, which steps
  are critical, the cron schedule. Dep-free, no `temporalio` import, 100% covered.
* **`app/workflows/temporal_worker.py` is a thin translation.** It maps activity names to
  callables and hands the plan to the engine. It holds no policy.

Logic living inside a `@workflow.defn` decorator cannot be tested without a server, so it
ships untested and its defects surface in production. Making the plan data moves "what
runs and when it gives up" into ordinary unit tests, and means replacing Temporal later
would not touch a single decision.

### Schedules are in the student's calendar, not UTC

The reminder fan-out is `0 17 * * *` — 18:00 in Africa/Algiers, before the evening study
session. The guardian report is `0 5 * * 0` — Sunday 06:00 local. Scheduling in raw UTC
sends the reminder into the middle of the school day. This is the same defect class
D-195 already fixed for streaks; encoding it here in a tested assertion stops it
recurring.

### Non-critical steps are declared, not discovered

`queue_guardian_notifications` is marked `critical=False`. A report that was built but
not announced is still readable in the dashboard, whereas failing the whole workflow over
one notification denies every other parent their report.

### Every named activity must exist

`missing_activities()` compares a plan's step names against the implemented registry. A
workflow that names a typo'd activity would otherwise fail six days later, at the worst
possible moment to discover a spelling mistake.

## Consequences

**Positive**

* Guardian report generation moves off the request path entirely.
* Ingestion validates first, on a short timeout: a corrupt corpus is caught in a minute
  rather than after an hour of embedding — the same lesson `ingest_knowledge.py` taught.
* Two more workflows (`corpus_ingestion`, `streak_reminder_fanout`) declare their
  activities but do not implement them yet. That gap is asserted in a test, so it is
  visible and counted rather than a plan that looks ready and collapses on first run.

**Negative, and accepted**

* Temporal plus its Postgres is real operational weight: two containers and a schema.
* `temporalio` is an optional dependency; the worker raises a clear error when it or
  `TEMPORAL_ADDRESS` is missing rather than pretending to run.
* **The worker has not been proven against a live server** — no Docker daemon existed in
  the session that wrote this. `.memory/runtime_truth.md` records the worker as DORMANT
  and the plans as ACTIVE. That distinction is the point of §6.6.

## Verification

* 15 tests on the plans, 100% line and branch, no engine involved.
* 10 tests on the worker's activities as plain functions against a real database,
  including the "one failing student must not deny the rest their report" path.
* Compose brings up `temporal` + `postgres-temporal` + `temporal-ui`, each with a real
  health check (`temporal operator cluster health`, not a port probe).
