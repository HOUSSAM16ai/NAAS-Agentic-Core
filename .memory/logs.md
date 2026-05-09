# Session Logs
> Last updated: 2026-05-09

---

## Session: 2026-05-09 · Full Live Runtime Investigation (Ona Agent)

**Branch**: `main` → `docs/live-runtime-audit-2026-05-09` (PR created)
**Mode**: Deep live runtime diagnosis + memory/CLAUDE.md update. No application code changed.

### Live runtime evidence collected
- **DB**: Connected to PostgreSQL 17.6 Supabase PgBouncer `:6543`. 19 users, 2098 customer_messages, 3038 admin_messages, 79 missions. alembic_version: `f2b3c4d5e6f7`.
- **OpenRouter**: 367 models available. Primary: `nvidia/nemotron-3-super-120b-a12b:free`. API key valid.
- **local_graph**: Live invocation confirmed — `run_local_graph('مرحبا', 9999)` → `'مرحبا! كيف يمكنني مساعدتك اليوم؟'`
- **FastAPI**: 62 routes registered with real DATABASE_URL. Crashes without it.
- **Next.js**: Port **3000** confirmed (supervisor.sh `--port 3000` overrides package.json `--port 5000`).
- **Grafana**: Port **3001** confirmed (`grafana.ini` says 3000 but provisioning CLI overrides). `GET /api/health → {"database":"ok"}`.
- **Prometheus**: Port **9090** confirmed. `GET /-/healthy → "Prometheus Server is Healthy."`.
- **Redis**: Process running on 6379, `ping()` responds. BUT `REDIS_URL` not set → app uses `InMemoryCache`.
- **OTEL**: `OTEL_EXPORTER_OTLP_ENDPOINT=http` is an invalid URL → no spans exported (confirmed no-op).
- **ZOMBIE verification**: `create_multi_agent_graph` only importer is `tests/verify_graph_manual.py`. KagentMesh: 7 importers, none on live chain from kernel/main.
- **AI Gateway**: `SimpleAIClient` with 5 fallback models. Live call confirmed.
- **Cache**: `get_cache()` returns `InMemoryCache` (no `REDIS_URL`).

### New findings vs previous audit (2026-05-06)
1. **Grafana port corrected**: was documented as 3000, actually 3001 (provisioning CLI override).
2. **Next.js port mechanism clarified**: supervisor.sh passes `--port 3000` as extra arg, overriding package.json. Process shows both flags; last wins.
3. **OTEL endpoint clarified**: `OTEL_EXPORTER_OTLP_ENDPOINT=http` (bare string) is invalid — previously noted as "unset", now confirmed as "set but invalid".
4. **Redis confirmed running but unused**: process active, but `REDIS_URL` not set → InMemoryCache.
5. **AI Gateway model confirmed**: `nvidia/nemotron-3-super-120b-a12b:free` as primary (not previously documented).
6. **local_graph live call confirmed**: actual OpenRouter response received in this session.
7. **DB row counts updated**: 2098 customer_messages, 3038 admin_messages, 79 missions, 19 users.

### Memory files updated
- **UPDATED**: `.memory/runtime_truth.md` — 34 rows, full rewrite with live evidence
- **UPDATED**: `.memory/context.md` — stack table with live status, DB state, AI gateway details
- **UPDATED**: `.memory/architecture_truth.md` — port map, component inventory, transformation gap
- **UPDATED**: `.memory/observability_truth.md` — Grafana port corrected to 3001
- **UPDATED**: `.memory/logs.md` — this entry
- **UPDATED**: `CLAUDE.md` — §6.6 truth table rewritten (34 rows), §3 architecture diagram updated, §1 port table clarified

### What was NOT changed
- No application source code
- No test files
- No microservice code


---

## Session: 2026-05-09 · Architectural Intelligence Enrichment

**Branch**: (memory-only — no application code changed)
**Mode**: Diagnosis + memory evolution. Strict task boundary: no runtime code changes.

### Investigation performed
- Full audit of `.memory/` structure (18 files, ~150KB of institutional memory)
- Deep read of `app/services/chat/local_graph.py` — intent classifier patterns
- Runtime test of `_classify_intent()` against 12 non-academic Arabic/English questions
- Confirmed: 10/10 misclassified as `educational` due to keyword overlap
- Discovered zombie `IntentDetector` (13-intent taxonomy) incompatible with live 3-intent taxonomy
- Confirmed intentional duplication between `local_graph.py` and `path_observer.py`
- CSS inspection of `frontend/app/globals.css` — both sidebars use `transform: translateX(±100%)`
- Confirmed no `aria-hidden`, `inert`, or `tabindex="-1"` on closed sidebars
- Confirmed `AgentTimeline` renders agent state into DOM regardless of sidebar visibility
- Parsed `observability/grafana/dashboards/20-langgraph.json` — extracted 4 Prometheus queries
- Grepped entire codebase for all 4 metric names — zero emitters found
- Confirmed `local_graph.py` uses UnifiedObs spans (in-process), not OTel/Prometheus metrics
- Identified dual-emission risk: `path_observer.py` emits WS turn metrics through both OTel SDK and UnifiedObs
- Analyzed `scripts/runtime_truth.py` — confirmed static-only analysis, leg 3 never verified in CI
- Confirmed lock file branch is stale (`jules-5513332666705839536-7e7df21b`)

### Memory files created/updated
- **NEW**: `.memory/fragility-patterns.md` — 4 deep root-cause analyses (~5KB)
- **UPDATED**: `.memory/issues.md` — ISS-027 through ISS-031 added
- **UPDATED**: `.memory/decisions.md` — D-013 through D-017 added
- **UPDATED**: `.memory/observability-topology.md` — zombie metric inventory + dual-emission risk
- **UPDATED**: `.memory/context.md` — session note + documentation pointer
- **UPDATED**: `.memory/progress.md` — session record
- **UPDATED**: `.memory/tasks.md` — G1–G5 follow-up tasks
- **UPDATED**: `.memory/logs.md` — this entry
- **UPDATED**: `CLAUDE.md` — §6.14–§6.17 governance doctrine

### What was NOT changed
- No application source code
- No test files
- No CI workflows
- No runtime behavior

---

## Session: 2026-05-05 · Persistence Consolidation + Terminal-Event Guarantee

**Branch**: `claude/fix-persistence-consolidate-8X8LT`
**Goal**: Surgical fix for dual-write + silent fallback + terminal-event corruption,
plus consolidation of legacy markdown into CLAUDE.md / .memory/.

### Investigation
- Mapped persistence paths (Explore agent + direct reads):
  - `app/api/routers/customer_chat.py:276` (Monolith user write, always)
  - `app/api/routers/customer_chat.py:387-461` (orchestrator_persisted detection + fail-safe)
  - `app/api/routers/admin.py:494-520` (same pattern, weaker logging, single retry)
  - `app/infrastructure/clients/orchestrator_client.py:281-282` (preserve `persisted`)
  - `microservices/orchestrator_service/src/api/routes.py:1314-1325, 2580, 2696`
    (skip user write under facade; signal `persisted` after assistant write)
  - `shared/chat_protocol/event_protocol.py:34-76` (unified envelope normalizer)

### Root causes confirmed
- ISS-014/015 already mitigated; needed codification + regression test.
- ISS-016: finally block had paths emitting NO terminal event (no content, no error,
  no pending_terminal_event) → UI hang.
- ISS-017: when `CHAT_USE_UNIFIED_EVENT_ENVELOPE=1`, `complete`/`persisted`/
  `conversation_init` were coerced to `assistant_delta` → terminal detection broke.

### Surgical fixes
1. `_emit_terminal_frames()` helper (customer_chat.py + admin.py) — single emitter
   for terminal frames + `persisted`. Synthesizes a frame when upstream omitted one.
2. `normalize_streaming_event` — pass-through for control event types.
3. Admin router brought to parity with customer router (WRITE_DECISION logs,
   `[CRITICAL_DATA_LOSS]` log on retry exhaustion).
4. New architecture test enforcing single-writer rule.

### Markdown consolidation
- Deleted ~38 legacy diagnosis/forensic root-level Markdown files. Their content was
  already captured in `.memory/issues.md` and `.memory/architecture.md`; standalone
  files drift from reality and confuse Claude in future sessions.
- Kept all governance/operational/canonical docs.

---

## Session: 2026-05-05 · Environment Documentation Correction

**Branch**: `claude/fix-duplicate-messages-nTEBj`
**Goal**: Verify dual-write fix status and correct environment documentation

### Trigger
User asked (in Arabic) whether the dual-write problem (messages written twice — once by Monolith and once by Orchestrator into `customer_messages` / `admin_messages`) is still present.

### Investigation
Read the dual-write defense layers:
- `app/services/customer/chat_persistence.py:81-112` — Duplicate Guard (10s window, content match) suppresses redundant writes
- `app/api/routers/customer_chat.py:276` — Monolith writes user message, sends `compatibility_facade=True`
- `app/api/routers/customer_chat.py:387-461` — Detects orchestrator `persisted: True` signal → skips local write; Fail-Safe writes if signal absent
- `app/infrastructure/clients/orchestrator_client.py:281-282` — Preserves `persisted` flag through normalization
- `microservices/orchestrator_service/src/api/routes.py:1314-1325, 2680, 2696` — Skips user INSERT under `compatibility_facade`; emits `persisted: True` after assistant write

### Conclusion on Dual-Write
**Resolved with three-layer protection**:
1. `compatibility_facade` handshake → orchestrator skips user write
2. `persisted` signal → Monolith skips assistant write
3. Duplicate Guard at persistence layer (10s window) → catches anything that slips through

In default Codespaces devcontainer the orchestrator microservice is dormant, so **only the Monolith writes** — dual-write physically impossible.

### Environment Correction
User clarified they run on **GitHub Codespaces**, not Replit. Verified by inspecting `.devcontainer/`:
- `devcontainer.json` uses `docker-compose.host.yml` (not full `docker-compose.yml`)
- Only `web` container starts; `supervisor.sh` runs `uvicorn app.main:app`
- Microservices remain dormant exactly as previously described for Replit

### Files Updated
- `CLAUDE.md` (sections 1, 6, 10, 13, 14)
- `.memory/context.md`, `architecture.md`, `decisions.md`, `issues.md`, `tasks.md`, `progress.md`, `logs.md`

All "Replit" references corrected to "Codespaces (devcontainer)" with concrete paths to `.devcontainer/devcontainer.json` and `.devcontainer/docker-compose.host.yml`.

---

## Session: 2026-05-04 · Runtime Truth Extraction (Live Testing)

**Branch**: `claude/add-distributed-tracing-T9Q8z`
**Commit**: pending (this session)
**Goal**: Observe the system while it is alive — measure real behavior, not static code

### What Was Done

**Phase 1 — Server Startup**
- Started backend with `.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Health check: `{"application": "ok", "database": "ok", "version": "v4.1-root"}`
- OpenAPI contract warnings printed on startup (ISS-006 confirmed)
- Startup time: ~8 seconds

**Phase 2 — Auth Flow (Measured)**
- `POST /api/security/register` → 125ms — created user id=2 `runtime@test.com`
- `POST /api/security/login` → 75ms — ISS-003 CONFIRMED: `full_name: null` in response
- Also logged: "User Service unreachable for registration/login" → ISS-009 CONFIRMED

**Phase 3 — WebSocket Chat (Measured)**
- WS connect: 26ms → `ws://localhost:8000/api/chat/ws?token=<JWT>`
- First attempt: wrong field name (`message` → should be `question`) → error
- Second attempt with `question` field but string conversation_id → "Invalid conversation ID"
- Third attempt without conversation_id → auto-creation triggered

**Phase 4 — Trace Collection**

8 real traces captured from `/api/v1/observability/traces`:

```
trace  GET /health              →  7.3ms   [OK]   1 span
trace  POST /api/security/register → 125ms  [OK]   1 span
trace  POST /api/security/login → 75ms    [OK]   1 span
trace  GET /openapi.json        →  3.0ms   [OK]   1 span
trace  GET /openapi.json        →  3.5ms   [OK]   1 span
trace  langgraph.run            → 757ms   [OK]   3 spans
trace  orchestrator.chat_with_agent → 1506ms [ERROR] 5 spans
```

**LangGraph trace (3 spans)**:
```
┌ [OK]   langgraph.run           (757ms)  thread_id=1, question_len=33
└─ [OK]  langgraph.supervisor    (0.0ms)  intent=educational
└─ [OK]  langgraph.chat_node     (747ms)  intent=educational, history_turns=2
```

**Orchestrator trace (5 spans)**:
```
┌ [ERROR] orchestrator.chat_with_agent  (1506ms) ERROR: all_fallback_paths_exhausted
└─ [SKIP] orchestrator.fallback.file_intelligence  (0.1ms)   — no files
└─ [SKIP] orchestrator.fallback.exercise_retrieval (0.0ms)   — no BAC match
└─ [OK]   orchestrator.fallback.langgraph          (757ms)   — ran successfully
└─ [OK]   orchestrator.fallback.general_chat       (720ms)   — ran UNEXPECTEDLY
```

**Phase 5 — Observability Endpoints**

| Endpoint | Status | Key Finding |
|----------|--------|-------------|
| `/health` | ✅ OK | `{"status": "ok", "components": null}` |
| `/metrics` | ✅ OK | p50=3.5ms, p95=1057ms, error_rate=7.69% |
| `/aiops` | ✅ OK | anomaly_score=0.0, no predictions |
| `/gitops` | ✅ OK | sync_rate=100.0, last_sync=null |
| `/performance` | ❌ 500 | Pydantic ValidationError: missing cpu_usage, memory_usage, active_requests |
| `/alerts` | ✅ OK | `[]` empty |

### Key Findings (New Issues Discovered)

1. **ISS-013 NEW**: All 5 free OpenRouter models return 403 — chat is broken in this env
2. **ISS-012 NEW**: `/performance` endpoint has Pydantic schema mismatch → 500 error
3. **ISS-008 CONFIRMED**: TelemetryBridge DNS failures on every telemetry attempt
4. **ISS-009 CONFIRMED**: User/Auth microservices pinged on every login/register (DNS failure → local fallback)
5. **ISS-003 CONFIRMED**: full_name=null in login response (bug visible in live response)
6. **ISS-006 CONFIRMED**: 13 missing paths in OpenAPI contract
7. **ISS-005 CONFIRMED**: Zero WS spans in traces despite active WebSocket session

### Root Cause of Chat Failure (Definitively Traced)
```
LangGraph runs OK (supervisor → intent=educational → chat_node)
  ↓
chat_node calls LLM (OpenRouter free models)
  ↓
All 5 models: 403 Forbidden
  ↓
"All models exhausted. Engaging Safety Net."
  ↓
Safety Net also fails (no valid model)
  ↓
orchestrator marks response as failed
  ↓
orchestrator.fallback.general_chat ALSO runs (redundant retry)
  ↓
all_fallback_paths_exhausted → root span ERROR
  ↓
WS: assistant_error → error → "Failed to confirm assistant persistence before completion."
```

---

## Session: 2026-05-04 · Distributed Tracing + Memory System

**Branch**: `claude/add-distributed-tracing-T9Q8z`
**Final commit**: `e320e45` / `3bb45a6`
**Tests**: 30 new (all pass) + 1628 existing (all pass) = 1658 total

### What Was Built
1. ObservabilityMiddleware wired into middleware stack (position 3)
2. LangGraph nodes instrumented (ContextVar, 3 spans)
3. Orchestrator fallback chain instrumented (1 root + 4 child spans)
4. Trace API endpoints (`GET /traces`, `GET /traces/{id}`)
5. New Pydantic schemas (`TraceSpanResponse`, `TraceResponse`)
6. 30 new tests in `tests/telemetry/test_distributed_tracing.py`
7. `.memory/` system created (7 files)
8. SessionStart + Stop hooks added to `.claude/settings.json`

---

## Session: Prior Sessions (from git log)

| Date | Commit | Summary |
|------|--------|---------|
| ~2026-04 | `9899bf9` | Dual-write immunity guard + conditional persistence |
| ~2026-04 | `62330f7` | Write guard + hardened fallback persistence path |
| ~2026-04 | `cba83e2` | Persistence signal in stream + skip redundant user writes |
| ~2026-04 | `bc8995d` | Resilience + context guard contracts |
| ~2026-04 | `6dc82af` | Admin websocket auth integration fix |
| ~2026-04 | `f957d8f` | Lint + format failures in CI |
| ~2026-04 | `7599b7a` | Legendary Claude Code setup (8 files) |
| ~2026-04 | `76b67cc` | Forensic analysis report |
| ~2026-04 | `9a307c3` | LangGraph initialization during system startup |

---

## Session: 2026-05-09 · Full Live Component Testing (Ona Agent — Second Pass)

**Branch**: `docs/live-runtime-audit-2026-05-09`
**Mode**: Live invocation of every advertised component. No application code changed.

### Components tested live

| Component | Test | Result |
|---|---|---|
| FastAPI | `GET /health` | `{"application":"ok","database":"ok","version":"v4.1-root"}` |
| WebSocket customer | `subprotocols=['jwt',TOKEN]` + `{"question":"..."}` | `conversation_init` → `assistant_delta` (391 chars) → `assistant_final` in 6.79s |
| WebSocket admin | Admin token + question | `conversation_init` (conv_id=391) confirmed |
| LangGraph local | `run_local_graph('ما هو تكامل x^2')` | LaTeX response in 10.13s |
| OrchestratorClient | `_build_local_file_count_response` | "22064 ملف" in 499ms |
| OrchestratorClient | `_build_local_retrieval_response` | None (no BAC match) |
| PostgreSQL | INSERT+DELETE test user | OK, ~2ms latency |
| Redis | `ping()` + SET/GET | OK (but app uses InMemoryCache) |
| InMemoryCache | SET/GET/DELETE | OK |
| DSPy 3.2.1 | `dspy.LM` + `dspy.Predict` | Importable + configurable |
| LlamaIndex 0.14.13 | `VectorStoreIndex` + HuggingFace embed | Score 0.8152 |
| CrossEncoder BAAI/bge-reranker-base | `model.predict(pairs)` | Cached, loads <1s |
| KAgent | `KagentMesh().execute_action(AgentRequest(...))` | `"⛔ Security Alert: Invalid token"` |
| MCP | `MCPServer().initialize()` + `get_tools_for_llm()` | 8 tools returned |
| Multi-agent graph | `create_multi_agent_graph(ai_client, [])` | Compiles (8 nodes), KAgent blocks invocation |
| Orchestrator microservice StateGraph | Import `SupervisorNode`, `AgentState` | Importable, not running |
| TLM | Package check | NOT INSTALLED, not referenced |
| DSPy live call | `dspy.Predict(ArabicQA)(question='...')` | Response received (truncated by free tier) |

### New findings vs first pass (2026-05-09 morning)
1. **WS payload key confirmed**: `question` (not `content`). Wrong key → `"Question is required."`.
2. **WS event format confirmed**: `{"type":"...", "payload":{"content":"...", "conversation_id":...}}`.
3. **KAgent security blocks multi-agent graph**: all 8 nodes fail with "Invalid token from planner_node".
4. **MCP has 8 working tools**: callable but not wired to live path.
5. **TLM confirmed NOT INSTALLED**: not part of this codebase.
6. **Intent classification bugs confirmed**: 'مرحبا' → 'general' (should be 'chat'), 'hello' → 'chat' (should be 'general').
7. **FastAPI version**: `v4.1-root`.
8. **Reranker driver export bug**: `app/drivers/reranker_driver.py` has no `RerankDriver` class (import fails).
9. **LlamaIndex driver export bug**: `app/drivers/llamaindex_driver.py` exports `LlamaIndexDriver` not `LlamaIndexRetrievalEngine`.
10. **Orchestrator StateGraph fields**: `messages, query, intent, filters, retrieved_docs, reranked_docs, used_web, final_response`.
11. **DSPy live call works**: `dspy.Predict(ArabicQA)` returns answer (truncated by free tier token limit).

### Memory files updated
- **UPDATED**: `.memory/runtime_truth.md` — 34 rows, full rewrite with second-pass live evidence
- **UPDATED**: `.memory/logs.md` — this entry
- **UPDATED**: `CLAUDE.md` — §6.6 truth table rewritten with WS protocol, fallback timing, all components
