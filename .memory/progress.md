# Progress — What Has Been Done
> Last updated: 2026-05-04

## ✅ Session: 2026-05-04 — Runtime Truth Extraction

**Branch**: `claude/add-distributed-tracing-T9Q8z`
**Goal**: Live system observation — measure real behavior

### What Was Confirmed/Discovered

1. **Live Auth Flow Measured**
   - Register: 125ms (`POST /api/security/register`)
   - Login: 75ms (`POST /api/security/login`)
   - ISS-003 CONFIRMED LIVE: `full_name: null` in login response
   - ISS-009 CONFIRMED: Auth microservice DNS failures on every login/register

2. **WebSocket Connection Measured**
   - Connect time: 26ms (ws://localhost:8000/api/chat/ws?token=JWT)
   - WS protocol: token via query param works in development mode
   - conversation_id must be numeric (or omitted for auto-create)
   - conversation_init event fires with auto-assigned id (id=1)

3. **8 Real Traces Captured** — Tracing system works end-to-end:
   - HTTP traces: register, login, health, openapi.json
   - LangGraph trace: 3 spans, 757ms, intent=educational detected correctly
   - Orchestrator trace: 5 spans, 1506ms, all_fallback_paths_exhausted

4. **Root Cause of Chat Failure Identified**
   - OPENROUTER_API_KEY set but all 5 free models return 403
   - LangGraph runs correctly but LLM call fails → Safety Net engaged → also fails
   - Both langgraph AND general_chat fallbacks run (potential double-run bug)
   - WS sends: conversation_init → assistant_error → error

5. **ISS-012 DISCOVERED**: `/api/v1/observability/performance` → 500 (Pydantic schema mismatch)
   - Missing: `cpu_usage`, `memory_usage`, `active_requests` in response
   
6. **ISS-008 CONFIRMED**: TelemetryBridge DNS failures logged on every request
   - "Failed to send telemetry: [Errno -2] Name or service not known"

7. **ISS-006 CONFIRMED**: OpenAPI contract 13 missing paths (wrong prefix in contract file)

8. **ISS-005 CONFIRMED**: Zero WS spans in traces despite full WS session
   - All 8 traces are HTTP or internal LangGraph/orchestrator spans
   - WebSocket layer is completely invisible to the tracing system

9. **Observability Endpoints Status**:
   - ✅ `/health` — `{"status": "ok", "components": null}`
   - ✅ `/metrics` — p50=3.5ms, p95=1057ms, p99=1416ms, error_rate=7.69%
   - ✅ `/aiops` — anomaly_score=0.0
   - ✅ `/gitops` — sync_rate=100.0
   - ❌ `/performance` — 500 (Pydantic ValidationError)
   - ✅ `/alerts` — `[]`

---

## ✅ Session: 2026-05-04 — Distributed Tracing

**Branch**: `claude/add-distributed-tracing-T9Q8z`
**Commit**: `e320e45` → memory system `3bb45a6`
**Tests**: 30 new (all pass) + 1628 existing (all pass) = 1658 total

### What was built
1. **ObservabilityMiddleware wired into middleware stack** (`app/core/app_blueprint.py`)
   - Position: TrustedHost → CORS → **Observability** → Security → RateLimit → ...

2. **LangGraph nodes instrumented** (`app/services/chat/local_graph.py`)
   - `_graph_trace_context: ContextVar` propagates parent context to nodes
   - `run_local_graph()`: root span `langgraph.run`
   - `_supervisor_node()`: child span `langgraph.supervisor`
   - `_chat_node()`: child span `langgraph.chat_node`

3. **Orchestrator fallback chain instrumented** (`app/infrastructure/clients/orchestrator_client.py`)
   - Root span + 4 child spans for each fallback step

4. **Trace API endpoints** (`app/api/routers/observability.py`)
   - `GET /api/v1/observability/traces`
   - `GET /api/v1/observability/traces/{trace_id}`

5. **New schemas** (`app/api/schemas/observability.py`)
   - `TraceSpanResponse`, `TraceResponse`

6. **Observability router registered** (`app/api/routers/registry.py`)

7. **30 new tests** (`tests/telemetry/test_distributed_tracing.py`)

8. **Permission fix** (`.claude/settings.json`)

9. **Superhuman Memory System** (`.memory/` — 7 files)
   - `context.md`, `progress.md`, `tasks.md`, `decisions.md`, `issues.md`, `architecture.md`, `logs.md`
   - SessionStart hook + Stop hook

---

## ✅ Previous Sessions (from git log)

| Commit | Summary |
|--------|---------|
| `9899bf9` | Dual-write immunity guard + conditional persistence |
| `62330f7` | Write guard + hardened fallback persistence path |
| `cba83e2` | Persistence signal in stream + skip redundant user writes |
| `bc8995d` | Resilience + context guard contracts |
| `6dc82af` | Admin websocket auth integration fix |
| `f957d8f` | Lint + format failures in CI |
| `7599b7a` | Legendary Claude Code setup (8 files) |
| `76b67cc` | Forensic analysis report |
| `9a307c3` | LangGraph initialization during system startup |
