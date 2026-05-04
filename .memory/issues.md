# Open Issues & Bugs
> Last updated: 2026-05-04 | Format: [SEVERITY] ID · Title

---

## 🔴 Critical

### ISS-001 · SECRET_KEY Ephemeral — All Users Logged Out on Restart
- **Status**: OPEN
- **Severity**: Critical / Auth broken
- **Symptom**: Every Replit restart invalidates all JWT tokens — all users forced to re-login
- **Root cause**: `SECRET_KEY` generated dynamically at startup if not set as a Replit secret
- **File**: `app/core/settings/base.py` — `SECRET_KEY: str = Field(default_factory=lambda: secrets.token_hex(32))`
- **Fix**: Add `SECRET_KEY` as a permanent Replit secret (not just env var)
- **Validation**: After fix, restart backend → existing JWT should still authenticate

---

### ISS-002 · 162 GitHub Security Vulnerabilities (15 Critical)
- **Status**: OPEN
- **Severity**: Critical / Security
- **Symptom**: `pip audit` and `npm audit` report 162 known CVEs
- **Files**: `requirements-prod.txt`, `frontend/package.json`
- **Fix approach**: Pin affected packages to safe versions, update in groups by dependency
- **Commands**:
  ```bash
  .venv/bin/pip-audit
  cd frontend && npm audit
  ```

---

### ISS-003 · `full_name` Returns `null` in Login Response
- **Status**: OPEN
- **Severity**: Critical / UX broken
- **Symptom**: After login, the frontend receives `full_name: null` — user name never shown
- **Root cause**: Schema mismatch between DB column name and Pydantic response model field
- **Files**: `app/services/security/auth_persistence.py`, auth response schema
- **Fix**: Align DB fetch with Pydantic field name, or add alias

---

### ISS-004 · Hardcoded Admin Credentials in bootstrap.py
- **Status**: OPEN
- **Severity**: Critical / Security
- **Symptom**: If `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars not set, default credentials are used silently
- **File**: `app/services/bootstrap.py`
- **Fix**: Validate at startup — refuse to boot in production if env vars missing
- **Guard**:
  ```python
  if settings.ENVIRONMENT == "production":
      if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
          raise RuntimeError("ADMIN_EMAIL and ADMIN_PASSWORD must be set in production")
  ```

---

## 🟡 Medium

### ISS-005 · WebSocket Events Not Traced
- **Status**: OPEN
- **Severity**: Medium / Observability gap
- **Symptom**: HTTP requests get W3C trace spans; WebSocket messages do NOT
- **File**: `app/api/routers/customer_chat.py` (WS handler)
- **Fix**: Extract `traceparent` from WS query params or first message payload, create root WS span
- **Note**: WS doesn't have HTTP headers after upgrade — must use query param or first message JSON

---

### ISS-006 · OpenAPI Contract Warnings on Startup
- **Status**: OPEN
- **Severity**: Medium / DX / Noise
- **Symptom**: Multiple `UserWarning: Route X not found in contract` on startup
- **File**: `app/core/openapi_contracts.py` + contract YAML/JSON
- **Fix**: Add missing routes to contract file, or relax validation to INFO-level

---

### ISS-007 · Database Writes Not Instrumented in Tracing
- **Status**: OPEN
- **Severity**: Medium / Observability
- **Symptom**: Trace spans show HTTP + LangGraph + orchestrator activity but ZERO DB write spans
- **File**: `app/core/database.py`
- **Fix**: SQLAlchemy async event listeners on `before_cursor_execute` / `after_cursor_execute`
  ```python
  @event.listens_for(engine.sync_engine, "before_cursor_execute")
  def before_execute(conn, cursor, statement, ...):
      conn.info["query_start_time"] = time.perf_counter()
  ```

---

### ISS-008 · OTLP / Jaeger Export Stubs Not Activated
- **Status**: OPEN
- **Severity**: Medium / Observability
- **Symptom**: `TelemetryBridge` has export stubs; nothing actually ships spans to Jaeger/Zipkin
- **File**: `app/middleware/observability/telemetry_bridge.py`
- **Fix**: Read `OTEL_EXPORTER_OTLP_ENDPOINT` env var → enable gRPC or HTTP export

---

### ISS-009 · Dormant Microservices Health Check Still Pings Dead Services
- **Status**: OPEN
- **Severity**: Low / UX
- **Symptom**: Health endpoint tries to contact all 8 dormant Docker services → all timeout
- **File**: `app/api/routers/system/`
- **Fix**: Mark dormant services as `INACTIVE` / `DORMANT` in health response, skip ping

---

## 🟢 Minor / Tracked

### ISS-010 · Prometheus Metrics Endpoint Not Exposed
- **Status**: OPEN — blocked by ISS-008
- **Severity**: Minor
- **Note**: `obs.export_prometheus_metrics()` exists but `GET /api/v1/observability/metrics` not registered
- **File**: `app/api/routers/observability.py`

---

### ISS-011 · Memory System Not Auto-Updating (No PostToolUse Hook Yet)
- **Status**: OPEN — in progress
- **Severity**: Minor / DX
- **Note**: `.memory/` files are updated manually; SessionStart hook pending

---

## ✅ Resolved

| ID | Title | Resolved In |
|----|-------|-------------|
| ISS-R001 | ObservabilityMiddleware not wired into stack | commit `e320e45` |
| ISS-R002 | LangGraph nodes not instrumented | commit `e320e45` |
| ISS-R003 | No trace propagation to LangGraph (ContextVar) | commit `e320e45` |
| ISS-R004 | No trace API endpoints `/traces`, `/traces/{id}` | commit `e320e45` |
| ISS-R005 | `git commit*` in deny list — blocked CI | `.claude/settings.json` fix |
| ISS-R006 | Python 3.11 system pytest can't parse 3.12 syntax | `.venv/` with Python 3.12 |
