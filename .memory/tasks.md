# Tasks — What Comes Next
> Last updated: 2026-05-04 | Priority: 🔴 Critical → 🟡 Medium → 🟢 Nice-to-have

## 🔴 Critical (Security / Stability)

### 1. Fix SECRET_KEY ephemeral issue
- **Problem**: SECRET_KEY not set as permanent Replit secret → all users logged out on restart
- **Fix**: Add `SECRET_KEY` as a persistent Replit secret (not env var)
- **File**: `app/core/settings/base.py` — validate that SECRET_KEY is set at startup
- **Impact**: AUTH BROKEN on every restart

### 2. Resolve 162 GitHub vulnerabilities (15 critical)
- **Command**: `pip audit` + `npm audit`
- **Files**: `requirements-prod.txt`, `frontend/package.json`
- **Approach**: Pin to safe versions, open PRs per dependency group

### 3. Fix full_name null in login response
- **Problem**: `full_name` field returns null after login (schema mismatch)
- **File**: `app/services/security/auth_persistence.py` + auth response schema
- **Symptom**: Frontend shows empty name after login

### 4. Replace hardcoded admin credentials
- **Problem**: Admin uses default credentials if `ADMIN_EMAIL`/`ADMIN_PASSWORD` not set
- **Fix**: Validate these env vars at startup, refuse to boot if missing in production
- **File**: `app/services/bootstrap.py`

---

## 🟡 Medium (Quality / Features)

### 5. Wire tracing into WebSocket layer
- **Current**: HTTP requests are traced, WebSocket events are NOT
- **File**: `app/api/routers/customer_chat.py` (or wherever WS handler is)
- **Approach**: Extract `traceparent` from WS query params or first message, create WS root span

### 6. Add Prometheus metrics export endpoint
- **Current**: `obs.export_prometheus_metrics()` exists but is not exposed as HTTP endpoint
- **File**: `app/api/routers/observability.py`
- **Endpoint**: `GET /api/v1/observability/metrics` → text/plain Prometheus format

### 7. Fix OpenAPI contract warnings on startup
- **Problem**: Missing route definitions cause warnings
- **File**: `app/core/openapi_contracts.py` + the contract YAML/JSON file
- **Approach**: Add missing routes to contract, or update contract to match runtime

### 8. Add database write instrumentation to tracing
- **Current**: HTTP + LangGraph + orchestrator traced, DB writes are NOT
- **Approach**: SQLAlchemy event listeners on `before_execute` / `after_execute`
- **Files**: `app/core/database.py`

### 9. Activate tail-based sampling export to Jaeger/OTLP
- **Current**: `TelemetryBridge` exporter stubs exist, nothing actually sends
- **File**: `app/middleware/observability/telemetry_bridge.py`
- **Approach**: Add `OTEL_EXPORTER_OTLP_ENDPOINT` env var → enable bridge

---

## 🟢 Nice-to-have (Polish / DX)

### 10. Memory system auto-update hook
- **Idea**: After each Claude session, auto-update `.memory/progress.md` + `.memory/tasks.md`
- **Current**: This memory system was just created — hook needs implementation
- **File**: `.claude/settings.json` (Stop hook)

### 11. Add BAC exercise search integration test
- **Current**: Exercise retrieval tested in unit, not integration
- **File**: `tests/integration/` (new)

### 12. Frontend: real-time trace viewer
- **Idea**: A debug panel that polls `GET /api/v1/observability/traces` and renders trace graph
- **File**: `frontend/app/components/TraceViewer.jsx` (new)

### 13. Refactor microservices health check
- **Current**: All 8 microservices are DORMANT — health endpoint still tries to ping them
- **File**: `app/api/routers/system/` → mark dormant services as INACTIVE explicitly
