# Spec: CogniForge API-First Microservices Simplification Program

## 1. Purpose

This specification defines a phased plan to reduce destructive complexity, remove split-brain runtime behavior, and move CogniForge toward a 100% API-first microservices architecture without a risky big-bang rewrite.

The requested outcome is not "more technology everywhere." The outcome is a system where each capability is independently replaceable, observable, testable, horizontally scalable, and simple enough to maintain under the CogniForge constitution.

## 2. Scope

### In Scope

- Organize the project around explicit service boundaries and API contracts.
- Eliminate split-brain control paths by making the active runtime path explicit and measured.
- Decompose large high-risk files into smaller modules behind stable interfaces.
- Strengthen the Skills architecture so new AI capabilities, models, RAG components, tools, and agents can be added without graph rewrites.
- Update `CLAUDE.md` and `.memory/` during implementation so they reflect runtime truth, not aspirational architecture.
- Preserve and enforce API-first microservice laws: service independence, own data ownership, HTTP/gRPC/events only, no cross-service imports, no shared business-logic libraries.
- Require live E2E full-stack verification and green GitHub Actions before declaring completion.

### Out of Scope For The First Implementation Wave

- A full rewrite of the application.
- Replacing every existing service at once.
- Introducing Kafka, Temporal, GraphQL, Kagent, MCP, LlamaIndex, DSPy, or a new vector database into production without an ADR, a contract, and live verification.
- Committing secrets, `.env` files, credentials, runtime tokens, personal emails, or passwords.

## 3. Critical Security Note

The user request included live credentials and personal account data. They must be treated as exposed secrets.

Implementation requirements:

- Do not write the secret values into code, docs, tests, logs, PR bodies, or `spec.md`.
- Rotate any exposed API keys, database credentials, Supabase bridge token, and user/admin passwords before live production use.
- Store replacement values only in the runtime secret mechanism already documented by the repository, such as git-ignored `.devcontainer/secrets.env` or the environment.
- Use `SUPABASE_EDGE_FUNCTION_URL` and `SUPABASE_EDGE_FUNCTION_KEY` environment variables for the HTTPS SQL bridge. Never hardcode the endpoint token.
- Never print environment variable values during E2E evidence collection.

## 4. Existing Baseline From Repository Inspection

The repository already contains strong governance that must be reused:

- Canonical microservices constitution: `docs/architecture/MICROSERVICES_CONSTITUTION.md`.
- English summary contract: `docs/ARCH_MICROSERVICES_CONSTITUTION.md`.
- Advanced principles: `docs/architecture/PRINCIPLES.md`.
- Current strangler roadmap: `docs/architecture/05_monolith_to_microservices_roadmap_ar.md`.
- Route ownership source: `config/route_ownership_registry.json` with human summary in `docs/architecture/ROUTE_OWNERSHIP_REGISTRY.md`.
- Runtime memory authority: `.memory/runtime_truth.md`.
- CI gate inventory: `.memory/ci-gates.md`.
- Supabase HTTPS SQL bridge runbook: `.memory/runbooks/supabase-bridge.md`.
- Existing API contracts: `docs/contracts/openapi/*`, `docs/contracts/asyncapi/*`, `docs/contracts/graphql/schema.graphql`, and consumer contracts.
- Existing microservices include API gateway, user, conversation, orchestrator, planning, research, reasoning, memory, observability, content retrieval, auditor, and foundations.
- Existing high-risk large files include `microservices/orchestrator_service/src/api/routes.py`, `app/services/chat/local_graph.py`, `app/services/skills/probability_skill.py`, `app/services/capabilities/exercise_retrieval.py`, `app/api/routers/admin.py`, and `app/api/routers/customer_chat.py`.

This plan must extend those assets rather than creating a competing third architecture document.

## 5. Non-Negotiable Constraints

### Engineering Standards

- Python 3.12+ typing only: no `Any`, no `typing.List`, no `typing.Optional`.
- Arabic professional docstrings for core components.
- Explicit imports and explicit failure modes.
- Functional core, imperative shell: pure domain functions first, side effects at boundaries.
- No business logic in FastAPI route handlers.
- Prefer FastAPI `Depends` and dependency injection. Use global singletons only for documented startup-owned services.
- `ruff check .` and `mypy app/ microservices/` are required before merge.

### Microservice Boundaries

- `app/*` must never import from `microservices/*`.
- One microservice must never import another microservice.
- Cross-service calls must use `httpx.AsyncClient`, gRPC, or events with `X-Correlation-ID`.
- Each service owns its database schema and migrations.
- No cross-service database joins.
- No shared business-logic library across services. Shared generated API clients and schema artifacts are allowed only if generated from contracts and do not contain domain logic.

### Signing Key Persistence (D-241 · K-ROOT — verified live 2026-08-12)

- The JWT signing key must never derive solely from a volatile ephemeral disk (codespace/workspace). Root of trust: environment → a durable `app_state` table in the production database → secure generation and persistence (`token_urlsafe(64)`).
- A codespace rebuild must never break existing logins: the restored key re-validates all previously issued JWTs and previously hashed passwords.
- Admin password must never be rewritten at boot unless the explicit `ADMIN_FORCE_PASSWORD_SYNC=1` flag is set.
- Verified live: monolith booting with no `SECRET_KEY` restores an 86-character key from `app_state` and logs in admin + user with 24/24 E2E on production Supabase.

### Delivery Constraints

- No big-bang rewrite.
- Each PR must be reversible.
- Respect Jules guardrails: maximum 5 created files per PR, cyclomatic complexity <= 15 per function, coverage not dropping more than 1%.
- ADR required before adopting a new platform dependency, communication pattern, workflow engine, vector database, message broker, GraphQL surface, MCP/Kagent runtime, or fine-tuning pipeline.

## 6. Product Truth Constraint

The system must not promise omniscience. "Answer every question" means:

- Every valid user turn returns a terminal outcome: answer, clarification, safe refusal, fallback response, or structured error.
- The system must not hallucinate certainty when retrieval, model, or tool evidence is unavailable.
- Educational flows must preserve the Cognitive Lab doctrine: diagnose reasoning, avoid answer dumps, and guide the student with bounded next steps.

## 7. Target Architecture

### Runtime Shape

```text
Browser / Next.js
  -> API Gateway / BFF
    -> Identity Service
    -> Conversation Service
    -> Orchestrator Service
      -> Planning Skill Service
      -> Research / Retrieval Skill Service
      -> Reasoning Skill Service
      -> Foundations Skill Service
      -> Future Skills via Skill Manifest
    -> Memory Service
    -> Observability Service

Events:
  Services -> Outbox -> Kafka-compatible event bus -> subscribers

Long-running workflows:
  Orchestrator / domain services -> Temporal workflows, only after ADR

Data:
  Postgres/Supabase per service
  Redis for cache/session/rate-limit where explicitly configured
  Vector store behind Retrieval API, initially pgvector unless an ADR selects Qdrant or another store

Observability:
  OpenTelemetry traces/logs/metrics -> collector -> Prometheus/Loki/Tempo/Grafana
```

### Planes

- Control plane: route ownership registry, service catalog, feature flags, model registry, skill registry.
- Data plane: API gateway, service HTTP/gRPC calls, WebSocket/SSE streams, event bus, databases.
- Verification plane: CI gates, contract tests, runtime truth lock, architecture guardrails, live E2E probes.
- AI capability plane: skills, tools, RAG, rerankers, models, evaluation, safety gates.

## 8. API-First Requirements

Every service must have:

- OpenAPI contract in `docs/contracts/openapi/<service>-openapi.*`.
- Optional AsyncAPI contract for emitted/consumed events.
- `/health` with dependency readiness fields, not only `{"status": "ok"}`.
- `/metrics` with a service-owned `CollectorRegistry` for microservices.
- Structured error responses with stable `code`, `message`, and `trace_id`.
- Authentication and authorization by default.
- Correlation ID on inbound logs, outbound calls, traces, and error details.
- Contract tests that compare implementation against the documented API.
- Route ownership entry before new gateway traffic is enabled.

## 9. Skills Architecture Requirements

Skill = independently testable capability with one responsibility.

Each new or migrated skill must define:

- Name, version, owner, description, capability type, input schema, output schema.
- `/execute` or equivalent stable endpoint.
- `/health` and `/metrics`.
- Invocation counter, duration histogram, success/failure labels.
- Happy-path and error-path tests.
- Fallback behavior when dependencies are unavailable.
- Runtime evidence before being marked ACTIVE: import, call chain, live invocation, metrics, and tests.

The monolith `BaseSkill` pattern can remain for in-process transitional skills, but production composition must be through the orchestrator and service APIs.

## 9b. Notation Layer Requirement (D-185 — implemented, live-verified)

A tutoring system must be able to **define every symbol it prints**. ISS-138 proved the
inverse is catastrophic: a student asked what `C` meant — a symbol the tutor itself had just
printed — and the system re-emitted the derivation the student had not understood, leaking
results the student was supposed to derive.

Requirements now enforced:

- One canonical symbol source: `shared/notation/registry.py` (dependency-free), mirrored by a
  vendored copy in the service and guarded byte-for-byte by `check_notation_parity.py`.
- Exposed as an API-first microservice (`notation-service`, port 8011) with a committed
  OpenAPI contract, readiness-bearing `/health`, a service-owned `/metrics` registry, and
  structured errors — bringing the platform to **13/13 services under the contract gate**.
- Exposed in-process as `NotationSkill` with a deterministic local path (no network on a
  student's turn) and graceful degradation when the service is down.
- CI enforces that no symbol the tutor can emit is undefinable, and that every stored example
  is **neutral** — a definition must never become a back door that leaks the current exercise.
- Notation resolution runs **before** any explanation detector: confusing "the letter C" with
  "event C" is a leak, not a nuance.

## 9c. Polyglot Requirement (ADR-006)

The service boundary is the **contract, not the language**. Every gate that governs services
(`check_openapi_parity`, `check_ports_consistency`, `check_service_catalog_parity`) inspects an
OpenAPI contract plus `/health` and `/metrics` — never the implementation language. A service
written in any language that honours those four things enters the system without modifying a
single gate.

Adoption requires all three: a **measured** workload Python/TypeScript cannot carry, a committed
contract before the first line of logic, and live three-leg proof before being called ACTIVE.
TypeScript is adopted (it had a real gap: the frontend consumed none of the 13 contracts). The
other nine languages are documented as seams in `docs/architecture/EXTENSION_SEAMS.md` §7 with
**zero code** until their condition is met — adding ten "Hello World" services would be ten
toolchains and ten drift sources with no consumer, which is precisely what the Kagent lesson
(D-173) forbids.

## 10. AI Extensibility Requirements

The architecture must support these capabilities through replaceable adapters and contracts:

- LangGraph `StateGraph` for deterministic agent orchestration.
- LlamaIndex as an optional retrieval/indexing adapter, not a hard dependency in route handlers.
- DSPy as an optional prompt/program optimizer behind evaluation gates.
- Reranker adapters behind a stable retrieval contract.
- MCP tools exposed through a tool gateway with permission and audit controls.
- Kagent or Kubernetes-native agent operations only behind a separate ops-plane ADR.
- TLM/trust layer as an evaluation and confidence policy layer; the exact meaning of TLM must be clarified by ADR before implementation because the term is overloaded.
- RAG, embeddings, vector search, and fine-tuning pipelines as data products with lineage, evaluation, rollback, and privacy controls.
- Model provider registry supporting OpenRouter and future providers without touching domain logic.

## 11. Data And Workflow Requirements

- Supabase/Postgres remains the primary relational backend unless changed by ADR.
- The HTTPS Supabase bridge is for diagnosis, read verification, and manual DDL only. It is not an application write path.
- Redis is activated only through explicit `CACHE_TYPE=redis` and `REDIS_URL`, with cache hit/miss metrics.
- Vector storage starts with pgvector if it satisfies recall, latency, and operations requirements. Qdrant or another vector DB requires ADR and benchmark evidence.
- Kafka adoption requires an outbox pattern, AsyncAPI contracts, idempotency keys, replay policy, dead-letter handling, and event versioning.
- Temporal adoption requires ADR, workflow ownership, retry policy, compensation strategy, and observability dashboards.
- No 2PC. Use Saga, outbox, idempotency, and compensating actions.

## 12. Complexity Reduction Requirements

Target state:

- High-churn modules should trend below 500 lines.
- Route handlers should be thin and delegate to application services.
- Functions should stay below cyclomatic complexity 15.
- Large files must be decomposed by responsibility, not by arbitrary line count.
- Extract pure functions before extracting services.
- Each extraction must include tests that prove behavioral equivalence.
- Backward compatibility layers must be explicitly deprecated, measured, and removed after traffic reaches zero.

Priority decomposition candidates:

1. `microservices/orchestrator_service/src/api/routes.py`
2. `app/services/chat/local_graph.py`
3. `app/services/skills/probability_skill.py`
4. `app/services/capabilities/exercise_retrieval.py`
5. `app/api/routers/admin.py`
6. `app/api/routers/customer_chat.py`
7. `microservices/orchestrator_service/src/services/overmind/graph/search.py`
8. `microservices/orchestrator_service/src/services/overmind/probability_tutor.py`
9. `microservices/api_gateway/main.py` — **Done (D-254 · 2026-08-14):** CodeScene hotspot (586 سطرًا · ازدواج داخلي 4 · تردد تغيير 10 على دوال البروكسي المتكررة) ⇒ سجل توجيهٍ تصريحي `ROUTE_REGISTRY` (27 مسارًا) يبني المعالجات آليًا صفر تغيير سلوكي · مانيفست مركّب `_sources.py` + حارس نصي `check_gateway_routes_parity` (endpoints لا bytes) · E2E حي 18/18 · CI أخضر 100%.
10. `app/infrastructure/clients/orchestrator_client.py` — **Done (D-256 · 2026-08-14):** CodeScene hotspot (238 سطرًا · Code Duplication على `get_mission`/`get_mission_events` · `_has_indexed_match` أعلى تردد churn=2 · embedded import + try/except واسع) ⇒ قشرة تفويض حرفية + حزمة شرائح نقية `orchestrator_client_support/` [`missions.py`: قلب `_request_mission` الموحد للطلبات الثلاثة + `ServiceJwtPayload` بياناتٌ معلنة للـ JWT · `preempts.py`: `resolve_indexed_anchor` يعزل قرار Supabase · `_sources.py` مانيفست مركّب يتغذى منه حراسا legacy_invariants وskills_doctrine الموسّعان] · 11 اختبارًا سلوكًا جديدًا (مطابقة حرفية: 404 ⇒ None/[] · خطأ HTTP يُرمى حرفًا · JWT بـ claim الإدمن) + القديمة 13/13 خضراء · ruff 0.14.0 أخضر · سجلّ السلسلة كاملة: D-252 (`chat_stream_ws` F(69) تردد 53) · D-253 (`orchestrator.py` خمس دوال B/C) · D-254 · D-255 (`content.py` C(14) churn 40) · D-256 — كلٌ بنمط «القشرة + الشرائح + المانيفست المركّب» صفر تغيير سلوكي.

## 13. Split-Brain Elimination Requirements

The project currently has multiple historical execution paths: monolith fallback, local graph, orchestrator StateGraph, skills pipeline, and probability tutor ports.

Implementation must:

- Define one primary chat control plane in the route registry.
- Keep fallback paths, but mark them as fallback with metrics and feature flags.
- Preserve `thread_id` semantics and document conversion boundaries.
- Remove duplicate decision logic from parallel paths or prove strict parity with tests.
- Promote exactly one runtime path at a time from PARTIAL/DORMANT to ACTIVE.
- Update `.memory/runtime_truth.md` and `.runtime/truth_table.lock.json` whenever a capability status changes.

## 14. Observability And Reliability Requirements

Every critical request must support:

- Trace ID/correlation ID from frontend to gateway to every service.
- Logs, metrics, and traces.
- Golden signals: latency, traffic, errors, saturation.
- Domain signals: pipeline mode, active skills, fallback reason, retrieval source, model provider, token usage where safe.
- Startup readiness state, not just process existence.
- Timeouts on all external calls.
- Retry with exponential backoff only for idempotent operations.
- Circuit breakers for unstable dependencies.
- Bulkheads for LLM calls, retrieval, database, and streaming.
- Graceful degradation when model, retrieval, vector DB, Redis, Kafka, or Temporal is down.

Dashboard panels must have verified emitters. Zombie metrics are a failure.

## 15. Documentation And Memory Requirements

### `CLAUDE.md`

Update during implementation to remain a concise operational contract:

- Keep durable laws and active invariants.
- Replace long historical narratives with pointers to `.memory/`.
- Mark runtime statuses only when backed by evidence.
- Do not paste secrets or one-off command transcripts.

### `.memory/`

Update during implementation:

- `runtime_truth.md`: ACTIVE/PARTIAL/DORMANT/ZOMBIE changes.
- `decisions.md`: new D-### decisions.
- `issues.md`: new ISS-### incidents.
- `tasks.md`: current next actions.
- `ci-gates.md`: any changed or added gates.
- `architecture.md` or `architecture_truth.md`: boundary changes.
- Runbooks only when a repeated operational procedure is proven.

Do not create new operational Markdown files outside `.memory/` unless the repository policy explicitly allows it.

## 16. Implementation Phases

### Phase 0: Safety And Baseline

Actions:

- Rotate exposed secrets and passwords before any live verification.
- Create a working branch following repository convention.
- Record current `git status`.
- Run baseline static checks that are feasible locally.
- Inventory services, contracts, route ownership, current CI gates, and large files.

Exit criteria:

- No secrets are written to the repository.
- Baseline failures are documented, not hidden.
- The implementation branch is ready for reversible PRs.

### Phase 1: Truth Audit And Service Catalog

Actions:

- Build or update a service catalog from existing contracts, ports, health endpoints, owners, and databases.
- Compare service catalog against route ownership registry and OpenAPI contracts.
- Identify DORMANT, PARTIAL, ACTIVE, and ZOMBIE capabilities with evidence.
- Add missing architecture guardrails only if they protect current laws.

Exit criteria:

- One authoritative service catalog exists.
- Route ownership and service contracts agree.
- Runtime truth drift can be checked in CI.

### Phase 2: Documentation Coherence

Actions:

- Refactor `CLAUDE.md` into a concise contract with pointers.
- Curate `.memory/` to remove contradictions and stale claims.
- Add a short implementation roadmap entry to `.memory/tasks.md`.
- Update `.memory/ci-gates.md` if gate names or responsibilities change.

Exit criteria:

- No third copy of the microservices constitution exists.
- Docs distinguish runtime truth from target architecture.
- Doc integrity gate stays green.

### Phase 3: Single Chat Control Plane

Actions:

- Select the primary chat path using route ownership registry.
- Make orchestrator StateGraph or conversation-service path primary only after health, metrics, contract, and E2E evidence.
- Demote local graph paths to measured fallback.
- Preserve greeting fastpath, pedagogical policies, math pipeline, UI component flow, BKT, and output firewall invariants.

Exit criteria:

- One primary path handles chat traffic.
- Fallback usage is visible in metrics.
- No duplicate hidden control plane changes user-visible behavior without a feature flag.

### Phase 4: Large File Decomposition

Actions:

- Decompose one high-risk file per PR.
- Start with route handlers and graph orchestration files.
- Extract pure helpers, request/response mappers, service classes, and policy functions behind stable interfaces.
- Add behavior tests before or with each extraction.

Exit criteria:

- Each touched module has smaller responsibilities.
- No API behavior regression.
- Coverage does not drop.
- Complexity thresholds are respected.

### Phase 5: Contract-First Gateway And Services

Actions:

- Ensure every externally reachable route has an OpenAPI contract.
- Enforce structured errors and auth defaults.
- Ensure outbound calls use `httpx.AsyncClient` and pass `X-Correlation-ID`.
- Remove direct cross-boundary imports if found.
- Strengthen `api_gateway` as BFF/proxy, not a domain-logic container.

Exit criteria:

- Contract tests pass.
- No `app` imports inside microservices and no microservice-to-microservice imports.
- Route registry parity gate passes.

### Phase 6: Skills Platform

Actions:

- Define a minimal skill manifest contract.
- Ensure each active skill has health, metrics, execute path, tests, and runtime evidence.
- Make orchestrator the composition point for skill-to-skill workflows.
- Add model registry/provider abstraction so new OpenRouter models or future providers can be changed by config and evaluation gates.
- Add evaluation fixtures for Arabic, French, Darija, math LaTeX, retrieval, and failure modes.

Exit criteria:

- Adding a new skill does not require editing route handlers.
- Adding a new model does not require editing domain services.
- Skill reality check passes for all ACTIVE skills.

### Phase 7: RAG, Retrieval, Embeddings, And Fine-Tuning

Actions:

- Separate ingestion, chunking, embeddings, vector indexing, retrieval, reranking, synthesis, and evaluation.
- Keep LlamaIndex optional behind the retrieval adapter.
- Keep DSPy optional behind evaluation and optimization workflows.
- Introduce vector DB only through a retrieval API.
- Define fine-tuning data lineage, privacy, evaluation, rollback, and deployment rules before training jobs exist.

Exit criteria:

- Retrieval can be benchmarked independently.
- RAG responses expose retrieval source and confidence metadata.
- Fine-tuning cannot bypass safety and evaluation gates.

### Phase 8: Events, Kafka, And Temporal

Actions:

- Add ADR for Kafka-compatible event streaming before production adoption.
- Use transactional outbox for domain events.
- Add AsyncAPI event contracts.
- Add idempotent consumers and dead-letter policies.
- Add ADR for Temporal before long-running workflow adoption.

Exit criteria:

- No distributed transaction is introduced.
- Event replay and failure behavior are documented and tested.
- Temporal workflows are observable and cancellable.

### Phase 9: Observability And Failure Planning

Actions:

- Fix invalid or no-op OpenTelemetry configuration.
- Ensure each service exposes useful `/health` dependency state.
- Ensure Prometheus targets are up for active services.
- Add dashboard-metric contract checks for Grafana panels.
- Add GameDay/chaos tests for dependency down scenarios.

Exit criteria:

- Operators can diagnose failure without reading code.
- Prometheus/Grafana panels reflect emitted metrics.
- Service failure degrades gracefully instead of cascading.

### Phase 10: Frontend, Streaming, And E2E

Actions:

- Preserve Next.js frontend contracts and WebSocket/SSE streaming semantics.
- Verify terminal frames: exactly one `assistant_final` or structured `error`, plus persistence signal where applicable.
- Ensure generated UI components render only through whitelisted contracts.
- Add Playwright or existing E2E coverage for login, chat, math UI, retrieval, and fallback.

Exit criteria:

- Real browser/user flow passes.
- Streaming does not duplicate terminal frames.
- No hidden auth kick-to-login loop.

### Phase 11: Full-Stack Runtime Verification

Actions:

- Start services using repository/Ona automation where available.
- Verify health matrix for active services.
- Verify `/metrics` for active services.
- Verify Prometheus target state.
- Run skills pipeline request and require `pipeline_mode="full"` when all dependencies are intentionally enabled.
- Run real user and admin login flows with rotated secrets.
- Run Arabic math, retrieval-backed, greeting, and general reasoning prompts.
- Verify persisted rows through supported application paths or the HTTPS bridge without exposing secret values.

Exit criteria:

- GitHub Actions required jobs are green.
- Local or environment E2E evidence shows the full stack works with real runtime dependencies.
- No secret values appear in logs or artifacts.

### Phase 12: Legacy Decommission

Actions:

- Measure legacy traffic for a fixed safety window.
- Disable old paths behind feature flags.
- Remove compatibility layers only after zero traffic and rollback plan.
- Update contracts, route registry, docs, and memory.

Exit criteria:

- No live traffic reaches retired paths.
- No zombie modules remain in active import paths.
- Runtime truth and CI lock agree.

## 17. Required Tests And Checks

Minimum pre-merge checks for implementation PRs:

- `ruff check .`
- `ruff format --check .`
- `mypy app/ microservices/`
- `pytest`
- Contract tests under `tests/contracts/`
- Architecture guardrails under `tests/architecture/` and `scripts/fitness/*`
- Runtime truth drift check when capability statuses change
- Frontend build/test when frontend files change
- E2E full-stack verification for route/control-plane changes

## 17b. Implementation Trace (which phases have actually landed)

This section exists so the spec cannot drift into aspiration. It records only what
is backed by evidence; anything absent here is **not** claimed.

| Phase | Status | Evidence |
|-------|--------|----------|
| **0 — Safety and baseline** | ✅ | Secrets live only in the process environment; none in the repo. Baseline recorded as-is, including pre-existing failures. |
| **1 — Truth audit and catalog** | ✅ (partial) | `config/microservice_catalog.json` + `docs/architecture/PORTS_SOURCE_OF_TRUTH.json` under `check_ports_consistency` / `check_service_catalog_parity`; drift checkable in CI via `runtime_truth.py --check`. |
| **2 — Documentation coherence** | ✅ **D-188** | `CLAUDE.md` 1,127 → 943 lines, dated narrative archived verbatim; the contradicting 2026-05-09 truth table replaced by a pointer to `.memory/runtime_truth.md`; `spec.md` registered in both indexes as the *program spec*, not a third constitution. Enforced by `check_memory_coherence.py` in `doc-integrity`. |
| **3 — Single chat control plane** | 🚧 | Orchestrator is the mandatory generation core (D-112, `REQUIRE_ORCHESTRATOR`); local fallbacks measured, not silent. Full S2–S4 migration outstanding (`.memory/roadmap.md` M10). |
| **4 — Large file decomposition** | ✅ | D-163→D-172 manifests; verbatim moves; gates read the composed source. |
| **5–6 — Contracts and skills** | ✅ | 13 committed OpenAPI contracts under `check_openapi_parity`; unified `BaseSkill` (D-179); no ZOMBIE skills (gate). |
| **9 — Observability and failure** | 🚧 | Outbound correlation now single-sourced (**D-189**, `check_correlated_http`, shrink-only debt). Per-request injection for long-lived clients and vendored copies for services remain. |
| **11 — Full-stack runtime verification** | 🚧 | Live E2E on 2026-07-30 (`docs/archive/e2e/`): monolith + orchestrator + foundations + notation + real OpenRouter over WebSocket, 9/10 categories answered relevantly (**D-190** closed two hijack defects). **Not** exercised: Postgres/Supabase, the container path, the frontend — environment limits, recorded as limits. |
| **10 — Frontend** | 🚧 **D-199** | Token layer (`frontend/app/styles/tokens.css`) is the single source; warm-paper palette with WCAG AA **computed** by `check_design_tokens`; both render-blocking `@import`s removed (fonts via `next/font`, verified zero external refs in built CSS); reduced-motion universal; PWA shell + offline page; `next build` and a shrink-only bundle budget now run in CI (1007KB JS). **Not** done: 43 Font Awesome icons → SVG (`docs/frontend/ICON_MIGRATION.md`), `globals.css` decomposition, message-list virtualization, Lighthouse on a throttled profile. |
| **7 — Retrieval** | 🚧 **D-200** | Live search stopped being `LIKE '%q%'`: ranking is deterministic and explained (`shared/retrieval`, 100%), word-boundary matching kills the D-193 defect class, Arabic normalization applied both sides, and every result carries `relevance` + `matched_terms`. Wiring it exposed that `content_items` was queried in four places with **no boot path creating it** — a clean database returned 500. **Not** done: vector recall at request time (`embedding`/HNSW/CrossEncoder stay DORMANT, honestly marked) and the standalone retrieval service on :8013. |
| **8 — Events and workflows** | 🚧 **D-201/D-204** (ADR-007, ADR-008) | Delivery discipline is dep-free and fully tested without a broker, and **now proven with one**: CI job `event-stack-live` boots Redpanda + Temporal on every PR and asserts 10 checks, 0 failures (2026-08-01) — topics carry the partitions and retention `TOPIC_SPECS` declares, a round trip preserves `event_id`/`correlation_id`/partition key, a redelivered id is skipped, and a poisoned record is dead-lettered while the partition keeps moving. Booting it exposed a missing Kafka consumer, a `|| true` that swallowed every topic-creation failure, and an advertised address no host client could resolve. **Not** proven: any Temporal workflow actually executing (the server is reachable, the worker has never connected), and two of three workflow plans still have no activities — asserted by test, not hidden. |
| **12 — Decommission** | 📋 | Not started. |

### Product layer (outside the original 0–12 phases)

The spec was written for an API-first simplification program; the learner-lifecycle product
did not exist in it. Recorded here so the trace stays complete:

| Capability | Status | Evidence |
|---|---|---|
| **Curriculum single source** | ✅ **D-193** | `shared/curriculum/` — 37 concepts across maths/physics/natural sciences replacing three incompatible taxonomies. Physics and sciences questions now classify instead of falling to `"general"`. 100% line+branch. |
| **Spaced repetition** | ✅ **D-194** | `shared/scheduling/fsrs.py` + `ReviewSchedulerSkill` + `student_review_schedule` (append-only) + live wiring from the BKT outcome + `GET /api/v1/review/due`. Support shortens the interval (1.2d scaffolded vs 15.7d unaided). 100%. |
| **Streaks** | ✅ **D-195** | `shared/habit/streak.py`, local-day computation in `Africa/Algiers` (naive UTC breaks a late-night student's streak — proven in test). 100%. |
| **Guardian dashboard** | ✅ **D-196** | Consent-based linking, `is_linked` on every read, deterministic weekly report that never queries message `content`. 100% on services. |
| **Product analytics** | ✅ **D-197** | `product_events` + closed event registry + deterministic retention/funnel, wired at signup, login, chat turn, review queue and guardian invite/accept/report. Admin-only endpoints. 100%. |
| **Ranked content search** | ✅ **D-200** | Deterministic lexical ranking with word-boundary matching and Arabic normalization; results carry their reason; browsing declares itself `unranked`. Both content tables registered in `REQUIRED_SCHEMA` after the endpoint was found to query a table nothing created. 100%. |
| **Event bus + durable workflow plans** | ✅ **D-201** | `shared/messaging` + `shared/workflows` + the in-process consumer and its database effect, all at 100% line+branch. Broker-dependent drivers honestly DORMANT. |
| **Model capability registry** | ✅ **D-202** | ISS-079's "no reasoning-only PRIMARY" rule moved from a comment to a CI gate: capabilities are declared data with dated live evidence, outright bans are distinguished from PRIMARY bans, and eligibility is a checked precondition. 100%. |
| **Prepaid vouchers** | ✅ **D-198** | Hashed codes, DB-constraint-enforced single redemption, idempotent for the same actor, entitlement as a single dependency. No payment gateway (SATIM documented as a seam with zero code). 100%. |

**Rule for this table:** a phase is marked ✅ only with the three-leg proof (import +
call chain + runtime evidence). A green test suite alone is not sufficient, and a
structural pass that does not check output *relevance* is not evidence at all — the
2026-07-30 verification proved a structure-only battery reports 8/8 while a physics
question is being answered with a probability menu.

## 18. Success Criteria

The program is successful when all are true:

- Required GitHub Actions show green.
- Every active microservice has contract, health, metrics, tests, and owner.
- No service directly imports another service or another service's database models.
- Chat has one primary control plane; fallback paths are measured and intentionally degraded.
- Large high-risk files are decomposed by responsibility without behavior regression.
- New AI models can be added through configuration/registry plus evaluation, not route rewrites.
- New skills can be added through manifest + contract + tests + metrics.
- RAG, vector search, reranking, and fine-tuning are separated behind API contracts.
- Observability can explain latency, errors, fallbacks, and dependency failures.
- `.memory/` and `CLAUDE.md` reflect runtime truth and contain no secrets.
- Live E2E confirms user/admin login, WebSocket/streaming, retrieval, math LaTeX/UI, persistence, and graceful failure behavior.

## 19. ADRs Required Before Specific Technology Adoption

- ~~Kafka/event streaming production adoption.~~ **ADR-007 (accepted, D-201).**
- ~~Temporal workflow adoption.~~ **ADR-008 (accepted, D-201 — worker DORMANT until a server exists).**
- Vector DB choice beyond pgvector.
- GraphQL public or internal API surface.
- MCP production tool gateway.
- Kagent/Kubernetes operations integration.
- DSPy optimization pipeline.
- LlamaIndex as a standard retrieval implementation.
- Fine-tuning pipeline and model release process.
- TLM/trust layer definition and placement.

## 20. Reference Baseline

Local repository references:

- `docs/architecture/MICROSERVICES_CONSTITUTION.md`
- `docs/architecture/05_monolith_to_microservices_roadmap_ar.md`
- `docs/architecture/ROUTE_OWNERSHIP_REGISTRY.md`
- `.memory/runtime_truth.md`
- `.memory/ci-gates.md`
- `.memory/runbooks/supabase-bridge.md`
- `docs/ai_skills/microservices-live-verification.md`
- `docs/ai_skills/langgraph-agent-patterns.md`

External technical references for implementation ADRs:

- OpenAPI Specification: `https://spec.openapis.org/oas/latest.html`
- AsyncAPI Specification: `https://www.asyncapi.com/docs/reference/specification/latest`
- CloudEvents Specification: `https://cloudevents.io/`
- OpenTelemetry Documentation: `https://opentelemetry.io/docs/`
- FastAPI Documentation: `https://fastapi.tiangolo.com/`
- LangGraph Documentation: `https://langchain-ai.github.io/langgraph/`
- LlamaIndex Documentation: `https://docs.llamaindex.ai/`
- DSPy Documentation: `https://dspy.ai/`
- Model Context Protocol Specification: `https://modelcontextprotocol.io/specification`
- Apache Kafka Documentation: `https://kafka.apache.org/documentation/`
- Temporal Documentation: `https://docs.temporal.io/`
- Redis Documentation: `https://redis.io/docs/latest/`
- PostgreSQL Documentation: `https://www.postgresql.org/docs/`
- pgvector: `https://github.com/pgvector/pgvector`
- Qdrant Documentation: `https://qdrant.tech/documentation/`
- Supabase Edge Functions: `https://supabase.com/docs/guides/functions`
- Next.js Documentation: `https://nextjs.org/docs`
- RAG paper: `https://arxiv.org/abs/2005.11401`
- Self-RAG paper: `https://arxiv.org/abs/2310.11511`
- DSPy paper: `https://arxiv.org/abs/2310.03714`

