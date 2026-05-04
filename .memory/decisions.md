# Architectural Decisions
> Last updated: 2026-05-04

## D-001 · LangGraph as Primary Chat Handler
**Decision**: `app/services/chat/local_graph.py` is the real handler. The orchestrator microservice is DORMANT.
**Reason**: Replit cannot run Docker. The orchestrator at `orchestrator:8006` always fails with ConnectError.
**Consequence**: All chat goes through the fallback chain → LangGraph `run_local_graph()`.
**Rule**: NEVER assume the orchestrator microservice is reachable. LangGraph is the truth.

---

## D-002 · MemorySaver for Conversation Persistence
**Decision**: LangGraph uses `MemorySaver(thread_id=conversation_id)` for per-conversation state.
**Reason**: Simple, in-process, no Redis/Postgres needed. Works in Replit.
**Consequence**: Conversation memory is lost on process restart.
**Alternative considered**: `langgraph-checkpoint-postgres` — too heavy for current setup.

---

## D-003 · W3C Trace Context (traceparent / tracestate)
**Decision**: Distributed tracing uses W3C standard headers, not proprietary format.
**Reason**: Interoperability with Jaeger, Zipkin, OTLP exporters without lock-in.
**Implementation**: `TraceContext.from_headers()` / `to_headers()` in `app/telemetry/models.py`.

---

## D-004 · ContextVar for LangGraph Trace Propagation
**Decision**: `_graph_trace_context: contextvars.ContextVar` passes parent trace to LangGraph nodes.
**Reason**: LangGraph calls nodes via `await node_fn(state)` in the same async task — ContextVars propagate automatically across await boundaries.
**Alternative rejected**: Adding `trace_id` to `LocalChatState` TypedDict — would change the state schema and could conflict with LangGraph's checkpointing.

---

## D-005 · Non-Fatal Tracing
**Decision**: All tracing code is wrapped in `try/except Exception: pass`. Tracing errors NEVER break chat.
**Reason**: Observability is a side-effect — the primary contract is chat reliability.
**Rule**: If tracing fails, log nothing, do nothing, continue chat normally.

---

## D-006 · RETURNING id Pattern for PostgreSQL
**Decision**: Use `INSERT ... RETURNING id` instead of `cursor.lastrowid`.
**Reason**: `asyncpg` with PostgreSQL doesn't support `lastrowid` reliably.
**File**: `app/services/security/auth_persistence.py` — DO NOT revert this.

---

## D-007 · Async-First Database Access
**Decision**: Zero synchronous SQLAlchemy. All DB calls use `await db.execute(select(...))`.
**Reason**: FastAPI is async — synchronous DB blocks the event loop.
**Pattern**: `result = await db.execute(select(Model).where(...))` → `result.scalar_one_or_none()`

---

## D-008 · get_settings() Singleton — Never os.environ
**Decision**: All config access via `from app.core.config import get_settings` → `get_settings().FIELD`.
**Reason**: Pydantic v2 validation, type safety, testability (can monkeypatch).
**Rule**: `import os; os.environ["KEY"]` is BANNED in app code.

---

## D-009 · Port 6543 → 5432 Rewrite for Supabase/PgBouncer
**Decision**: Settings auto-convert PgBouncer port 6543 → 5432 for asyncpg compatibility.
**File**: `app/core/settings/base.py` — DO NOT override this in `app/core/database.py`.

---

## D-010 · ObservabilityMiddleware Position in Stack
**Decision**: ObservabilityMiddleware is 3rd in the stack (index 2), after TrustedHost and CORS.
**Reason**: Runs before SecurityHeaders and RateLimit so ALL requests (including rate-limited ones) are traced.
**Execution order**: TrustedHost → CORS → **Observability** → Security → RateLimit → RemoveBlocking → GZip

---

## D-011 · Observability Router at /api/v1/observability
**Decision**: Traces, metrics, health, alerts exposed at `/api/v1/observability/*`.
**Endpoints**: `/health`, `/metrics`, `/traces`, `/traces/{id}`, `/aiops`, `/gitops`, `/performance`, `/analytics/{path}`, `/alerts`
**Auth**: Currently unauthenticated — should be secured in production.

---

## D-012 · .venv with Python 3.12 via uv
**Decision**: Project uses `.venv/` created with `uv venv --python 3.12`.
**Reason**: System pytest uses Python 3.11 which can't parse `def f[T]` (Python 3.12 syntax) in tests/conftest.py.
**Rule**: Always run tests with `.venv/bin/pytest`, never `/root/.local/bin/pytest`.
