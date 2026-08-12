# ADR-009: Decomposing `/agent/chat` under a measured complexity budget

**Status**: Accepted
**Date**: 2026-08-11
**Deciders**: repository owner · Claude Code
**Technical Story**: CodeScene hotspot — project 83416 · `chat_with_agent_endpoint`

---

## Context and Problem Statement

CodeScene measured `microservices/orchestrator_service/src/api/routes.py:chat_with_agent_endpoint`
at **336 LOC, complexity 48, change frequency 43** — the repository's worst hotspot,
carrying Complex Conditional, Complex Method, Bumpy Road and Deep Nested Complexity at
once. One function held 21% of a 1,566-line file, in the shape of two full async
generators declared inside a request handler.

Reproduced independently with stdlib AST under Python 3.12: **CC 51 / LOC 336 /
nesting 13**. LOC agrees with CodeScene exactly; complexity differs by 3 because the
metrics differ.

Two facts shaped the decision more than the numbers:

1. **`/agent/chat` is the rollback path, not the default.** `routing_policy.py:26` sets
   `_DEFAULT_ENDPOINT_MODE = "state_graph"`; this endpoint is reached only when
   `ORCHESTRATOR_CHAT_ENDPOINT=agent`, which no deployment sets. By §6.6 it is
   **PARTIAL**. The work therefore buys code health and a safe rollback lever — not
   better answers for students, who do not traverse it by default.
2. **The hotspot score predicted real defects.** Measuring it surfaced three, all inside
   the function: two dead per-request checkpointer probes, a `persisted` flag stripped
   before reaching the wire, and missing `query` in the admin graph inputs.

## Decision Drivers

* Behaviour must be provably unchanged — this path is the emergency lever.
* The API contract is frozen: status codes, schemas, streaming semantics, headers.
* No new CI dependency without justification (protocol constraint 10).
* Whatever is fixed must stay fixed after the PR that fixed it.
* The live student path (`/api/chat/ws`) must not be destabilised by this work.

## Decision

Decompose the handler into a thin HTTP boundary plus three sibling modules, following
the D-168 pattern already used six times in this package (verbatim move + one-line
append to `API_SOURCE_FILES`), and guard the result with a stdlib fitness gate.

```
routes.py :: chat_with_agent_endpoint   ← authenticate → build turn → pick stream → return
    ├── agent_chat_request.py           build_agent_chat_turn        26 LOC · cc 2
    ├── agent_chat_admin_stream.py      stream_admin_agent_chat      54 LOC · cc 5
    └── agent_chat_customer_stream.py   stream_customer_agent_chat   58 LOC · cc 9
```

| | before | after | budget |
|---|---|---|---|
| endpoint LOC | 336 | **39** | ≤ 40 |
| endpoint CC | 51 | **2** | ≤ 6 |
| endpoint nesting | 13 | **1** | ≤ 2 |
| `routes.py` LOC | 1,566 | **1,272** | — |

Equivalence is proven three ways: 10 committed golden-master frame sequences unchanged,
the **entire** orchestrator OpenAPI spec byte-identical to the committed contract, and
521 tests green across the differential, contract, source-inspection, D-171, D-117 and
seed-strategy suites.

## Alternatives Rejected

**Convert `/agent/chat` to LangGraph, reusing `_run_chat_langgraph`.** It deliberately
runs `OrchestratorAgent`; that difference *is* the rollback value (D-021). Converting it
deletes the lever it exists to be.

**radon + xenon + import-linter, as the protocol names.** Three new CI dependencies for
numbers this repo already computes in stdlib, in a package with 67 AST gates and an
established shrink-only ratchet. `check_endpoint_complexity.py` gates our own number, so
the gate can never disagree with itself, and no ADR-for-dependencies is needed.

**Dual-run behind a feature flag (protocol Phase 6).** It requires keeping the old
implementation alive with no live caller, which §6.8 forbids and for which Kagent was
deleted. Committed golden-master fixtures give the same 100% equivalence proof and
surface drift as a reviewable diff.

**Unify the two persistence blocks.** They implement the same §6.5 contract with
*deliberately* different failure behaviour: admin emits `assistant_final` in both arms;
customer emits `[DB SAVED]` only on success and finalises after the try/except. Merging
them is a behaviour change wearing a refactor's clothes. Recorded as a follow-up instead.

**Unify the two WebSocket twins** (`chat_ws_stategraph` / `admin_chat_ws_stategraph`,
CC 20/23, 148/153 LOC, near-identical). They are a large part of the change-coupling
number, but they are the **live default student path**. Frozen in the debt baseline so
they cannot grow; restructuring them is its own PR.

## Consequences

**Positive.** The hotspot is gone by measurement. Each responsibility
(`_stream_delta_content`, `_final_response_from_chain_end`, `_classify_agent_chunk`,
`_finalise_*_turn`, …) is independently testable. One fewer DB round-trip per request.
The admin path now resolves tools against the real question. A safety net exists where
there was almost none: 3 tests became 22, covering the `persisted` semantics, both
persistence-failure arms, the empty turn, and fail-closed authorization.

**Negative / accepted.** `routes.py` gained eight `# noqa: F401` re-exports, kept because
`tests/unit/test_chat_context_seed_strategy.py:165` calls `routes._detect_checkpoint_state`.
The endpoint sits at 32 of its 40-line budget — the headroom is deliberate, and growth into
it still requires an explicit, reviewable decision.

**Enforced by.** `scripts/fitness/check_endpoint_complexity.py` in the `guardrails` CI
job, with 12 tests in `tests/fitness/test_check_endpoint_complexity.py` — six of them
seeded violations, one per gate mechanism, plus a clean tree that must pass, because a
gate that fails on everything gets switched off in a week. Raising any budget requires a
written decision (D-209, layer 9).

**Left open, deliberately.** ISS-153 (`persisted` stripped by `StreamFrame`) is
documented and characterised by a test that freezes the broken behaviour, not fixed —
the fix touches every frame on every path and belongs in its own PR.

---

## Outcome — what running it found that the tests could not (D-238)

After this ADR's work closed with 1,296 green tests, 100% differential equivalence and a
byte-identical OpenAPI contract, the full stack was booted (real PostgreSQL 16, real
OpenRouter, 11 processes) and **one** student question was sent. Two further defects
surfaced immediately.

**ISS-156 — every frame encoded twice.** `_make_json_event` returned an already-serialized
frame and the endpoint serialized it again: 32 of 34 frames carried a whole frame inside
`payload.content`, and `customer_messages` stored the envelope instead of the answer —
permanent poisoning of the student's history, proven by SQL. Pre-existing and byte-identical
on `origin/main`, so the decomposition carried it faithfully, exactly as "verbatim" promised.

**ISS-157 — the orchestrator's only model was the one D-067 bans as PRIMARY**, with no
fallback chain, and outside `check_model_chain_parity`'s scope.

**The lesson this ADR should carry, because it is the uncomfortable one:** the safety net
built in Phase 1 was *correct about equivalence and wrong about coverage*. `_FakeAgent`
emitted plain text where the real agent emits frames, so the golden master faithfully froze a
shape the agent never produces. Every claim made about equivalence still holds; none of them
could have caught this. **A test double that does not follow the real producer's contract
turns a green suite into a measurement of itself.** The fake now calls the real
`_make_json_event`, so it cannot drift again.

Both are fixed, both are enforced by gates that need no credentials
(`check_no_double_encoded_frames` and `check_model_client_literals`), and the live
before/after is recorded verbatim in
[`E2E_LIVE_EVIDENCE_D238.md`](../architecture/E2E_LIVE_EVIDENCE_D238.md).

---

## Note 4 — the same trap, avoided by measuring first (D-239 · ISS-155)

The WS twins were decomposed on 2026-08-12. Two things from this ADR were re-tested in
anger and both held.

**Note 3's trap is real and recurs.** The first extraction moved the scope vocabulary and
the turn machine into one module. Run bare, before `--update`, the gate reported
`chat_ws_turn.py: loc=302` against the 300-line newcomer budget. The response was to split
a responsibility out (`chat_ws_scope.py`), not to shorten a docstring by two lines — note 9's
rule that the number comes down through structure or it is Goodhart. The lesson generalises:
*run the gate bare and read it before you let `--update` write anything.*

**Which exposed a hole in the gate itself.** `check_endpoint_complexity.main()` handles
`--update` before any evaluation and `_write_baseline` never calls `_key_violations`. A
module that blows the newcomer budget and is frozen in the same run is judged by the ratchet
forever after — the amnesty lands precisely during a decomposition campaign, the only time
`--update` is ever run. Filed as **ISS-160**; the manual discipline until it is fixed is
bare → read → `--update` → verify → review the diff.

**Note 5's late-binding guard fired for real.** After the move the transcript contract went
23-red with `ConnectionRefusedError` on port 5432: patches were resolving against `routes`'
re-exports while the real callers had moved. The structural AST check named both new modules
and exactly which patched names they called. They were added to `CALLER_MODULES` only after
the gate asked, so the mechanism stayed proven live rather than assumed.

**Note 6's golden-master choice paid off again**, with one correction worth recording. The
customer shell now passes `admin_payload=None` explicitly where it previously omitted the
kwarg; since `_stream_chat_langgraph` defaults it to `None`, the callee cannot tell the two
apart. The recorder was measuring finer than the behaviour and screamed at a real
equivalence. The fix belonged in the test — production code is never bent to satisfy a
measuring instrument — and the golden was re-baselined against the pre-move source so the
proof survived.
