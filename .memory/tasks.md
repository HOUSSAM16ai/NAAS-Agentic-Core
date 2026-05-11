# Tasks — What Comes Next
> Last updated: 2026-05-11 | Branch: `feat/microservices-step8-reasoning-agent`
> Priority: 🔴 Critical → 🟡 Medium → 🟢 Nice-to-have

---

## ✅ Resolved — Microservices Step 8: Reasoning Agent Live Activation (2026-05-11)

### Step 8 — reasoning-agent on :8008 ✅ DONE
- `microservices/reasoning_agent/prom_metrics.py` — 11 Prometheus metrics, independent CollectorRegistry
- `microservices/reasoning_agent/main.py` — /metrics + enhanced /health (step=8, llm_backend, mcts_enabled)
- `microservices/reasoning_agent/src/api/routes.py` — prom_metrics integration in /execute
- `supervisor.sh:launch_reasoning_agent()` — STEP 4H, auto-starts on :8008
- `.ona/automations.yaml` — service + 3 tasks (verify/restart/test)
- `observability/native/prometheus.yml` — scrape target :8008, step="8"
- `observability/grafana/dashboards/110-microservices-step8-reasoning-agent.json` — 20+ panels
- `.github/workflows/microservices-step8-reasoning-agent.yml` — 7-job CI gate
- `tests/microservices/reasoning_agent/test_step8_reasoning_agent_metrics.py` — 79 tests pass
- **Live verified**: /health → step=8, llm_backend=openrouter | /metrics → startup_info 1.0

### Step 9 — Candidate options (OPEN)
1. **Cross-service HTTP call**: reasoning-agent → research-agent (real inter-service communication)
2. **Redis activation**: `CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0` (Redis process already running)
3. **PostgresCheckpointer**: upgrade LangGraph from MemorySaver → PostgresCheckpointer (ISS-020)
4. **conversation-service**: activate on :8003 (next dormant microservice)

---

---

## ✅ Resolved — Microservices Step 3: Live Activation (2026-05-10, branch: feat/microservices-step3-live-activation)

### Step 3 — Activate orchestrator-service as Ona service ✅ DONE
- `docker-compose.step3.yml` — 3-service compose (postgres-orchestrator:5441 + redis-orchestrator:6380 + orchestrator-service:8006)
- `.ona/automations.yaml` — service `orchestrator-stack` + tasks `health-probe`, `verify-stack`, `run-step3-tests`
- `observability/grafana/dashboards/60-microservices-step3-live.json` — 20-panel dashboard (UID: cogniforge-ms-step3-live)
- `.github/workflows/microservices-step3-live.yml` — 7-job CI gate with PR comment

### Step 4 — Next (OPEN — الخطوة التالية)
**Scope**: End-to-end persistence verification + outbox relay activation.
1. Run `gitpod automations service start orchestrator-stack` → verify `/health` returns `startup_state: ready`.
2. Send WS message to monolith → verify `persisted: true` event reaches client (orchestrator persisted, monolith skipped fail-safe write).
3. Check DB: exactly one row in `customer_messages` for the turn (no dual-write — D-006).
4. Enable `OUTBOX_RELAY_ENABLED=true` in `docker-compose.step3.yml` after persistence verified.
5. Check telemetry: `retrieval_source` is `"internal_exact"` or `"web"` (not `"web_skipped_missing_tavily"`).
6. Update `.memory/runtime_truth.md` entry #36 from `DORMANT→ACTIVE (on demand)` to `ACTIVE`.
**Why**: Validates the full revival path end-to-end before declaring Step 3 complete in production.

---

## ✅ Resolved — Orchestrator Revival Step 1 (2026-05-10, branch: feat/orchestrator-revival-step1)

### H1 — Add `TAVILY_API_KEY` to `docker-compose.yml` ✅ DONE
- `TAVILY_API_KEY=${TAVILY_API_KEY:-}` أُضيف في `orchestrator-service` و`research-agent`
- `TAVILY_API_KEY=` أُضيف في `.env.docker` مع تعليق توضيحي
- 4 اختبارات تمر في `test_orchestrator_revival.py`

### H2 — Fix DuckDuckGo Fallback ✅ DONE
- `ddgs>=6.0` أُضيف إلى `microservices/research_agent/requirements.txt`
- 2 اختبارات تمر في `test_orchestrator_revival.py`

### H3 — Fix `cognitive_engine.memorize` NullPointerError ✅ DONE
- `simple_client.py:116` — حارس `and self.cognitive_engine is not None` مُضاف
- 3 اختبارات تمر في `test_orchestrator_revival.py`

### H4 — Verify Orchestrator Warmup After Stack Activation (OPEN — الخطوة التالية)
**Scope**: Integration test only — no code changes.
After running `docker compose -f docker-compose.yml up -d`:
1. `curl http://localhost:8006/health` → must return `{"status": "ok"}`.
2. Send WS message to monolith → verify `persisted: true` event reaches client (orchestrator persisted, monolith skipped fail-safe write).
3. Check DB: exactly one row in `customer_messages` for the turn (no dual-write).
4. Check telemetry: `retrieval_source` is `"internal_exact"` or `"web"` (not `"web_skipped_missing_tavily"`).
**Why**: Validates the full revival path end-to-end before updating `.memory/runtime_truth.md` to ACTIVE.

---

## 🟡 Medium — Fragility Pattern Fixes (NEW — Session 2026-05-09)

### G1 — Fix Intent Routing Semantic Hijacking (ISS-027)
**Minimum viable fix** (no architecture change):
1. Add semantic context guards to `_EDUCATIONAL_PATTERNS`: require a subject name near `تمرين` (e.g., `رياضيات|فيزياء|كيمياء` within 3 words) before classifying as educational.
2. Fix greeting anchor brittleness: change `^(السلام|...)[\s\W]*$` to `^(السلام عليكم?|السلام|مرحبا|...)[\s\W]*$` to catch common Islamic greeting variants.
3. Apply the same changes to `app/telemetry/path_observer.py:_EDUCATIONAL_PATTERNS` and `_GREETING_PATTERNS` in the same PR (D-013).
4. Add a test: `test_intent_classifier_non_academic_keywords.py` — assert that yoga exercise, conflict resolution, and social network questions are NOT classified `educational`.

**Proper fix** (requires ADR):
- Replace lexical classifier with embedding-based or LLM-based classification.
- Write ADR in `docs/architecture/adr/` before implementation.

### G2 — Fix Hidden DOM Leakage (ISS-028)
1. Add `inert={!isSidebarOpen || undefined}` to the `.sidebar` div in `CogniForgeApp.jsx`.
2. Add `inert={!isAgentSidebarOpen || undefined}` to the `.agent-sidebar` div.
3. Verify: screen reader no longer announces sidebar content when closed.
4. Verify: Tab key no longer cycles into off-screen sidebar elements.
5. Note: `inert` is supported in all modern browsers (Chrome 102+, Firefox 112+, Safari 15.5+). Add a polyfill comment if IE11 support is needed (it is not, for this project).

### G3 — Fix Zombie Metrics in LangGraph Dashboard (ISS-029)
**Option A — Add emitters** (preferred):
1. In `app/services/chat/local_graph.py:_supervisor_node`, after intent classification, emit:
   - `cogniforge_langgraph_intent_total` counter with label `intent=<value>`
   - `cogniforge_langgraph_node_count_total` counter with label `node=supervisor`
2. In `app/services/chat/local_graph.py:_chat_node`, after LLM call, emit:
   - `cogniforge_langgraph_node_count_total` counter with label `node=chat`
   - `cogniforge_langgraph_node_duration_seconds` histogram
3. After `MemorySaver` checkpoint write, emit `cogniforge_langgraph_checkpointer_writes_total`.
4. Use the OTel SDK path (`_emit_to_otel` pattern from `path_observer.py`) for consistency.

**Option B — Remove zombie panels** (faster):
1. Delete the 4 zombie panels from `20-langgraph.json`.
2. Replace with panels querying `/api/v1/observability/traces` for LangGraph span data.

### G4 — Add Dashboard-Metric Contract CI Gate (ISS-031)
1. Create `scripts/check_dashboard_metric_contracts.py`:
   - Parse all `observability/grafana/dashboards/*.json`
   - Extract Prometheus query expressions (all `"expr"` fields)
   - Extract metric names from expressions (strip functions, labels, operators)
   - Grep application source for each metric name in emit calls
   - Exit 1 if any dashboard metric has no emitter
2. Add to `.github/workflows/ci.yml` as a new `guardrails` step.
3. This is a static check — no runtime required.

### G5 — Fix Dual-Emission of WS Turn Metrics (ISS-030)
1. In `app/telemetry/path_observer.py:close_ws_turn`, remove the redundant `obs.record_metric(...)` calls for `ws.chat.turn.duration_seconds`, `ws.chat.terminal_events.total`, `ws.chat.fallback.total`.
2. Keep `_emit_to_otel(handle)` as the single emission path.
3. Keep `obs.record_metric(...)` only for metrics that are NOT emitted via OTel (golden signals, internal diagnostics).
4. Verify: Prometheus scrape shows each metric once, not twice.

---

## 🟢 Nice-to-have — Follow-ups from third audit (READ-ONLY this branch)

> These are NOT executed in `claude/architecture-rescue-diagnostic-wUfbE`. They are
> recorded so a future PR can pick them up.

### F1 — CI quality-gate hardening (ISS-025)
1. Add `tests/architecture/test_terminal_frame_integrity.py` — assert `_emit_terminal_frames`
   is the only emitter of `assistant_final` / `error` / `persisted`; assert exactly-one
   frame per turn for both success and error paths.
2. Add a truth-table-sync test: parse `.memory/runtime_truth.md` for `app/...` paths,
   fail if any path classified ZOMBIE/DORMANT is imported by `app/api/`, `app/main.py`,
   `app/kernel.py`, or `local_graph.py` without a status update in the same PR.
3. Add a `frontend-build` job to `.github/workflows/ci.yml` (`cd frontend && npm ci && npm run build`).
4. Promote `doc-integrity` workflow to a required status check in branch protection for `main`.
5. Flip `doc_integrity.yml` scratch-artifact step from advisory (`exit 0`) to blocking
   (`exit $fail`) once the cleanup PR lands.

### F2 — Markdown consolidation (separate PR, user must approve)
1. Delete repo-root scratch files: `*_errors.txt`, `*_coverage*.txt`, `proof_output.txt`,
   `app_imports.txt`, `commit_message.txt`, `telemetry_evidence.txt`, `patch_*.diff`,
   `ruff_*.txt`, `err_*.txt`, `Screenshot_*.png`, `verification_*.png`, `services_errors*.txt`.
   ~24 files.
2. Decide on `ARCHITECTURE.md` (root) — merge as callout in CLAUDE.md or delete.
3. Decide on `LangGraph_Architectural_Blueprint.md` (root) — move to `docs/archive/` or delete.
4. Decide on `AGENTS-IMPROVEMENT-SPEC.md` — apply audit findings to `AGENTS.md`, then delete the spec.
5. Create `docs/archive/` and move dated diagnostics from `docs/diagnostics/` and `docs/PHASE_*.md`.
6. Add `.gitignore` rules for `Screenshot_*.png`, `verification_*.png`, `*_errors.txt`,
   `*_coverage*.txt`, `proof_output.txt`, `patch_*.diff`, `ruff_output*.txt` to prevent
   re-introduction.

### F3 — Loaded-not-invoked decisions (ISS-026, separate PRs)
> Per file in `app/services/chat/{intent_detector,intent_registry,tool_router,tool_access,
> dispatcher,education_policy_gate,orchestration_rollout}.py`, plus `chat/orchestrator.py`
> and the two `chat_streamer.py` modules: choose **one** of three explicit outcomes:
> 1. Promote — wire into the live router; add runtime evidence to `runtime_truth.md`.
> 2. Stop instantiating — delete the `__init__` construction in the boundary service; mark file ZOMBIE.
> 3. Document and isolate — header comment "PARTIAL (loaded-not-invoked) — see CLAUDE.md §6.9".
> Do NOT leave half-alive.

---

## ✅ Resolved — `claude/fix-persistence-consolidate-8X8LT`

- **A1 / ISS-014 / ISS-015** — Single persistence owner enforced (D-006).
  Architecture test `tests/architecture/test_persistence_authority.py` prevents
  regression. Monolith owns user + assistant writes; Orchestrator participates
  only when delegated and signals `persisted: true`.
- **A2 / ISS-016** — `_emit_terminal_frames()` helper in both routers guarantees
  exactly one terminal frame per turn; `[CRITICAL_DATA_LOSS]` logging on retry
  exhaustion. Silent failure path eliminated.
- **A3 / ISS-017** — `normalize_streaming_event` passes `complete`, `persisted`,
  and `conversation_init` through unchanged when the unified envelope flag is on.

## 🔴 Critical — Remaining Architectural Debt

---

### A4. Fix Context Identity — Unify conversation_id = thread_id (ISS-019)
- **Steps**:
  1. In `orchestrator_client.py` entry point, set `thread_id = str(conversation_id)`.
  2. Pass `thread_id` explicitly into `run_local_graph()`.
  3. Remove any re-derivation of `thread_id` inside the graph itself.
  4. Add a test: same conversation_id across two turns hits the same MemorySaver checkpoint.
- **Files**: `app/services/chat/orchestrator_client.py`, `app/services/chat/local_graph.py`

---

### A5. Add Postgres-backed Checkpointer Option (ISS-020)
- **Steps**:
  1. Add `langgraph-checkpoint-postgres` to `requirements.txt`.
  2. In `local_graph.py`, check `get_settings().LANGGRAPH_CHECKPOINTER`:
     - `"postgres"` → `AsyncPostgresSaver(conn_string=APP_DATABASE_URL)`
     - default → `MemorySaver()` (current behavior)
  3. Add `LANGGRAPH_CHECKPOINTER` to `.devcontainer/devcontainer.json` env vars (optional).
- **Files**: `app/services/chat/local_graph.py`, `app/core/settings/base.py`

---

### A6. Switch Graph Invocation to astream_events — Real Streaming (ISS-023)
- **Steps**:
  1. Replace `graph.ainvoke(state, config)` with `graph.astream_events(state, config, version="v2")`.
  2. In the event loop, filter `on_chat_model_stream` events → emit `stream_token` WS event.
  3. Keep `complete` terminal event at end of stream.
- **Files**: `app/services/chat/local_graph.py`

---

## 🔴 Critical (Broken in Production)
- **Status**: CONFIRMED at runtime (ISS-013)
- **Problem**: All 5 free OpenRouter models return 403 — no LLM response ever succeeds
- **Confirmed models failing**: nvidia/nemotron, google/gemini-2.0-flash-exp, qwen/qwen3-coder, kwaipilot/kat-coder-pro, microsoft/phi-3-mini-128k-instruct
- **Fix options**:
  a. Upgrade OPENROUTER_API_KEY credits (if expired/rate-limited)
  b. Switch to paid OpenRouter model (openai/gpt-4o-mini costs ~$0.15/1M tokens)
  c. Add working OPENAI_API_KEY or ANTHROPIC_API_KEY as fallback
- **File**: `app/services/chat/local_graph.py` → LLM provider config

### 2. Fix SECRET_KEY ephemeral issue
- **Status**: INFERRED (ISS-001)
- **Fix**: Add `SECRET_KEY` as a permanent Codespaces secret (already forwarded via `.devcontainer/devcontainer.json` → `remoteEnv.SECRET_KEY: ${localEnv:SECRET_KEY}`)

### 3. Fix `full_name` null in login response ✅ CONFIRMED LIVE
- **Status**: CONFIRMED (ISS-003)
- **Problem**: Login returns `full_name: null` even though DB has the value
- **File**: `app/services/security/auth_persistence.py` + auth response schema
- **Debug**: The register endpoint correctly returns `full_name: "Runtime Tester"` but login response does not

### 4. Resolve 181 GitHub security vulnerabilities (15 critical)
- **Status**: CONFIRMED via git push output
- **Files**: `requirements-prod.txt`, `frontend/package.json`

### 5. Replace hardcoded admin credentials
- **Status**: INFERRED (ISS-004)
- **File**: `app/services/bootstrap.py`

---

## 🟡 Medium (Quality / Stability)

### 6. Fix `/api/v1/observability/performance` → 500 error ✅ CONFIRMED LIVE
- **Status**: CONFIRMED (ISS-012)
- **Error**: Pydantic ValidationError — `PerformanceSnapshotResponse` missing: `cpu_usage`, `memory_usage`, `active_requests`
- **File**: `app/api/routers/observability.py` + `app/api/schemas/observability.py`
- **Fix**: Either add `Optional` fields with defaults to the schema, or fix the `TelemetryAnalyzer` to return them

### 7. Disable TelemetryBridge when no endpoint configured ✅ CONFIRMED LIVE
- **Status**: CONFIRMED (ISS-008)
- **Problem**: Every request triggers "Failed to send telemetry: [Errno -2]" DNS failure
- **File**: `app/middleware/observability/telemetry_bridge.py`
- **Fix**: Skip telemetry export if `OTEL_EXPORTER_OTLP_ENDPOINT` is not set

### 8. Disable User/Auth microservice calls when stack not running ✅ CONFIRMED LIVE
- **Status**: CONFIRMED (ISS-009)
- **Problem**: Every auth request triggers DNS lookup for dormant microservices → timeout → local fallback. In Codespaces default devcontainer the microservices are not started, so this fails on every request.
- **Effect**: Adds latency to every login/register
- **Fix**: Check if microservice URL is configured before attempting connection (or skip when `ORCHESTRATOR_SERVICE_URL` is unset)

### 9. Fix OpenAPI contract prefix mismatch ✅ CONFIRMED LIVE
- **Status**: CONFIRMED (ISS-006)
- **Problem**: Contract expects `/api/observability/*`, actual routes at `/api/v1/observability/*`
- **Effect**: 13 missing paths warning every startup
- **Fix**: Update the contract YAML/JSON file prefix

### 10. Wire tracing into WebSocket layer ✅ CONFIRMED MISSING
- **Status**: CONFIRMED gap (ISS-005)
- **Problem**: 8 real traces captured — zero WS spans, despite full WS session
- **Approach**: Extract `traceparent` from WS query params, create root WS span at `connect`, child spans at each message
- **File**: `app/api/routers/customer_chat.py`

### 11. Add database write instrumentation to tracing
- **Status**: INFERRED (ISS-007)
- **Approach**: SQLAlchemy async event listeners on `before_cursor_execute` / `after_cursor_execute`
- **File**: `app/core/database.py`

### B1. Audit and Mark Zombie Components (ISS-021)
- **Status**: OPEN — investigation needed
- **Steps**:
  1. `grep -rn "ConversationService\|supervisor\.py" app/ microservices/ --include="*.py"`
  2. For each zombie: add `# DORMANT` comment or delete after confirming no callers.
  3. Update `.memory/architecture.md` to reflect only live components.
- **File**: Multiple — requires audit first

### B2. Audit Educational vs General Pipeline Capability (ISS-022)
- **Status**: OPEN — requires LangGraph node comparison
- **Steps**:
  1. Compare `supervisor_node` routing for `educational` vs `general` intents.
  2. Verify both paths use same LLM quality, same context window, same retrieval.
  3. If not: unify or document intentional differences.
- **File**: `app/services/chat/local_graph.py`

### 12. Fix health endpoint `/observability/health` returning null components
- **Status**: CONFIRMED LIVE
- **Response**: `{"status": "ok", "components": null}` — components is always null
- **File**: `app/api/routers/observability.py`

---

## 🟢 Nice-to-have (Polish / DX)

### 13. Activate tail-based sampling export to Jaeger/OTLP
- **Blocked by**: ISS-008 must be fixed first
- **File**: `app/middleware/observability/telemetry_bridge.py`
- **Approach**: Add `OTEL_EXPORTER_OTLP_ENDPOINT` env var → enable bridge

### 14. Add Prometheus metrics format to `/metrics` endpoint
- **Current**: Returns JSON golden signals, not Prometheus text format
- **File**: `app/api/routers/observability.py`

### 15. Memory system auto-update hook
- **Current**: Memory updated manually at end of each session

### 16. Frontend: real-time trace viewer
- **File**: `frontend/app/components/TraceViewer.jsx` (new)

### 17. Refactor microservices health check
- **Current**: Health endpoint still tries to ping 8 dormant services
- **File**: `app/api/routers/system/`

### 18. Add BAC exercise search integration test
- **File**: `tests/integration/` (new)
