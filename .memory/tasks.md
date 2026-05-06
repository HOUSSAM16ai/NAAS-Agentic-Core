# Tasks — What Comes Next
> Last updated: 2026-05-06 | Branch: `claude/architecture-rescue-diagnostic-wUfbE` (third audit).
> Priority: 🔴 Critical → 🟡 Medium → 🟢 Nice-to-have

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
