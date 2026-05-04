# Open Issues & Bugs
> Last updated: 2026-05-04 (runtime verification session)
> Format: [SEVERITY] ID · Title · [CONFIRMED LIVE / INFERRED]

---

## 🔴 Critical

### ISS-001 · SECRET_KEY Ephemeral — All Users Logged Out on Restart
- **Status**: OPEN
- **Evidence**: INFERRED (not tested live — requires Replit restart)
- **Root cause**: `SECRET_KEY: str = Field(default_factory=lambda: secrets.token_hex(32))` in `app/core/settings/base.py`
- **Fix**: Add `SECRET_KEY` as a permanent Replit secret

---

### ISS-002 · 162 GitHub Security Vulnerabilities (15 Critical)
- **Status**: OPEN
- **Evidence**: GitHub Dependabot alert shown on every `git push` to this branch
- **Message**: "GitHub found 181 vulnerabilities on HOUSSAM16AI/NAAS-Agentic-Core's default branch (15 critical, 100 high, 63 moderate, 3 low)"
- **Files**: `requirements-prod.txt`, `frontend/package.json`

---

### ISS-003 · `full_name` Returns `null` in Login Response ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**:
  ```json
  POST /api/security/register → { "full_name": "Runtime Tester" }  ← OK
  POST /api/security/login    → { "full_name": null }              ← BUG
  ```
- **Root cause**: Login fetches user from DB but does not populate `full_name` into JWT claims or response schema
- **Files**: `app/services/security/auth_persistence.py`, auth response schema

---

### ISS-004 · Hardcoded Admin Credentials in bootstrap.py
- **Status**: OPEN
- **Evidence**: INFERRED
- **Fix**: Validate at startup — refuse to boot in production if env vars missing

---

### ISS-013 · All Free OpenRouter Models Return 403 ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Severity**: Critical — CHAT IS BROKEN in current environment
- **Evidence** (from server log):
  ```
  Model nvidia/nemotron-3-super-120b-a12b:free failed: Status 403. Trying next...
  Model google/gemini-2.0-flash-exp:free failed: Status 403. Trying next...
  Model qwen/qwen3-coder:free failed: Status 403. Trying next...
  Model kwaipilot/kat-coder-pro:free failed: Status 403. Trying next...
  Model microsoft/phi-3-mini-128k-instruct:free failed: Status 403. Trying next...
  All models exhausted. Engaging Safety Net.
  ```
- **Effect**: Entire chat pipeline fails → WS sends `assistant_error` + `error` events
- **Root cause**: OPENROUTER_API_KEY exists but the account has no access to these free models
- **Fix**: Use paid OpenRouter models, or add a valid OPENAI_API_KEY as backup

---

## 🟡 Medium

### ISS-005 · WebSocket Events Not Traced ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**: Live WS session generated events [conversation_init, assistant_error, error] but ZERO WS spans appeared in `/api/v1/observability/traces`
- **Effect**: Can see orchestrator + LangGraph spans but blind to WS-layer timing (auth, message parse, event dispatch)
- **Fix**: Extract `traceparent` from WS query params or first message payload, create root WS span

---

### ISS-006 · OpenAPI Contract Mismatch — 13 Missing Paths ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at startup 2026-05-04
- **Evidence**: Server prints on startup:
  ```
  ❌ مسارات العقد غير موجودة في التشغيل: ['/api/missions', '/api/observability/aiops', ...]
  ```
- **Root cause**: Contract file expects prefix `/api/observability/*` but actual routes are at `/api/v1/observability/*` (prefix mismatch)
- **Missing paths** (13):
  `/api/missions`, `/api/missions/{id}`, `/api/observability/aiops`, `/api/observability/alerts`,
  `/api/observability/analytics/{path}`, `/api/observability/gitops`, `/api/observability/health`,
  `/api/observability/metrics`, `/api/observability/performance`, `/api/v1/agents/langgraph/run`,
  `/api/v1/agents/plan`, `/api/v1/overmind/missions`, `/api/v1/overmind/missions/{id}`
- **Fix**: Update contract YAML to use `/api/v1/observability/*` prefix

---

### ISS-007 · Database Writes Not Instrumented in Tracing
- **Status**: OPEN
- **Evidence**: INFERRED — confirmed no DB spans in collected traces
- **Fix**: SQLAlchemy async event listeners on `before_cursor_execute` / `after_cursor_execute`

---

### ISS-008 · OTLP / Jaeger Export Not Activated ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**: Server log repeatedly:
  ```
  Failed to send telemetry: [Errno -2] Name or service not known
  ```
- **Root cause**: `TelemetryBridge` is trying to connect to an external telemetry host that doesn't resolve in this environment
- **Fix**: Gate telemetry export behind env var check: `OTEL_EXPORTER_OTLP_ENDPOINT`

---

### ISS-009 · Dormant Microservices Pinged on Login/Register ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**:
  ```
  User Service unreachable for registration ([Errno -2] Name or service not known), using local fallback.
  User Service unreachable for login ([Errno -2] Name or service not known), using local fallback.
  ```
- **Effect**: Every auth request has extra DNS lookup latency before falling back to local DB
- **Fix**: Disable external service calls entirely in non-Docker environments

---

### ISS-012 · `/api/v1/observability/performance` Crashes — Pydantic Schema Mismatch ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**:
  ```
  pydantic_core.ValidationError: 3 validation errors for PerformanceSnapshotResponse
  cpu_usage: Field required [type=missing]
  memory_usage: Field required [type=missing]
  active_requests: Field required [type=missing]
  ```
- **Root cause**: `PerformanceSnapshotResponse` schema requires `cpu_usage`, `memory_usage`, `active_requests` but the underlying `TelemetryAnalyzer` returns a dict without these fields
- **File**: `app/api/routers/observability.py` + `app/api/schemas/observability.py`

---

## 🟢 Minor / Tracked

### ISS-010 · Prometheus Metrics Endpoint Not Exposed
- **Status**: OPEN — blocked by ISS-008
- **Note**: `GET /api/v1/observability/metrics` returns JSON golden signals (latency/traffic/errors/saturation), not Prometheus text format

### ISS-011 · Memory System PostToolUse Hook — Pending
- **Status**: OPEN — in progress

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

---

## 📊 Runtime Metrics (Measured 2026-05-04)

| Metric | Value | Source |
|--------|-------|--------|
| WS connect time | 26ms | measured |
| Auth register | 125ms | trace `8b1f0f95` |
| Auth login | 75ms | trace `0af1ec03` |
| LangGraph full run | 757ms | trace `80c2b5d7` |
| Orchestrator (all fail) | 1506ms | trace `bd4d2974` |
| Latency p50 | 3.5ms | `/observability/metrics` |
| Latency p95 | 1057ms | `/observability/metrics` |
| Latency p99 | 1416ms | `/observability/metrics` |
| Error rate | 7.69% | `/observability/metrics` |
| Total requests | 13 | `/observability/metrics` |
