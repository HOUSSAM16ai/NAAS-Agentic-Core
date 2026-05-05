# Tasks — What Comes Next
> Last updated: 2026-05-05 (environment: Codespaces) | Priority: 🔴 Critical → 🟡 Medium → 🟢 Nice-to-have

---

## 🔴 Critical (Broken in Production)

### 1. Fix OpenRouter 403 — Chat Is Completely Broken
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
