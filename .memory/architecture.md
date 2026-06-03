# Architecture Deep-Dive
> Last updated: 2026-05-11 | Branch: `feat/microservices-step12-conversation-service`
> **Authoritative runtime status of every capability lives in `.memory/runtime_truth.md`.**
> This file describes the live request flow and middleware stack only.
> Anything documented here must be backed by import + call chain + runtime evidence (see CLAUDE.md §6.6).
> **Skills Philosophy (D-038):** كل قدرة AI = Skill مستقل. انظر CLAUDE.md §0.5 و `.memory/decisions.md#D-038`.

---

## 0. Skills Architecture — الرؤية المعمارية (D-038)

```
الحالة الراهنة (2026-05-11):
═══════════════════════════════════════════════════════════════
Browser → Next.js :3000
    └── /api/* → FastAPI :8000 (monolith)
          └── OrchestratorClient fallback chain
                ├── [1] File Intelligence
                ├── [2] Exercise Retrieval (BAC)
                ├── [3] HTTP → orchestrator:8006 ← ACTIVE لكن غير مُوجَّه إليه
                └── [4] LangGraph local ← DE-FACTO HANDLER (Prompt Spaghetti)

الخدمات المصغرة (Skills) — حية ومتصلة:
  orchestrator-service  :8006  ← Composition Skill      ✅ ACTIVE (Steps 4+9+10)
  user-service          :8001  ← Identity Skill          ✅ ACTIVE (Step 5)
  planning-agent        :8002  ← Planning Skill          ✅ ACTIVE (Step 6)
  conversation-service  :8003  ← Conversation Skill      ✅ ACTIVE (Step 12)
  research-agent        :8007  ← Retrieval Skill         ✅ ACTIVE (Step 7)
  reasoning-agent       :8008  ← Reasoning Skill         ✅ ACTIVE (Step 8)
  content-retrieval     :8009  ← Content Retrieval Skill ✅ ACTIVE (Step 11)
  Skills Pipeline       :8006/compose ← Composition Engine ✅ ACTIVE (Step 9)
  Postgres Checkpointer :8006/checkpointer/status ← Durable Memory ✅ ACTIVE (Step 10)

الهدف (Skills Pipeline — Steps 9-12 مُنجَزة):
═══════════════════════════════════════════════════════════════
Browser → Next.js :3000
    └── /api/* → FastAPI :8000
          └── orchestrator :8006
                └── compose([
                      PlanningSkill  :8002 → خطة الإجابة
                      ResearchSkill  :8007 → المعلومات المتاحة
                      ReasoningSkill :8008 → التفكير العميق
                    ])
                      └── إجابة مُركَّبة من skills متخصصة
```

### الفرق الجوهري

```python
# الآن — Prompt Spaghetti (LangGraph local):
prompt = """أنت مساعد تعليمي خبير في الرياضيات والفيزياء
            وتتحدث العربية والفرنسية والدارجة..."""
response = llm(prompt + question)  # كل شيء في مكان واحد

# الهدف — Skills Architecture:
plan     = await planning_skill.plan(question)        # ماذا نحتاج؟
context  = await research_skill.retrieve(plan)        # ما المعلومات؟
answer   = await reasoning_skill.reason(question, context)  # ما الحل؟
response = orchestrator.compose(plan, context, answer)  # التركيب النهائي
```

---

---

## 1. Middleware Stack (Execution Order)

Starlette's `add_middleware` uses LIFO wrapping — the LAST added wraps outermost.
`_apply_middleware` in `app_blueprint.py` reverses the list before adding.

```
Incoming Request
      │
      ▼
┌─────────────────────┐  [1] TrustedHostMiddleware
│  Host validation    │      Rejects unknown hosts
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐  [2] CORSMiddleware
│  CORS preflight     │      Handles OPTIONS, sets Access-Control-* headers
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐  [3] ObservabilityMiddleware  ← TRACING ENTRY POINT
│  W3C Trace Context  │      Reads traceparent/tracestate → creates root span
│  Metrics recording  │      Records request_duration_ms, status_code
│  Error hook         │      Marks span ERROR on 5xx
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐  [4] SecurityHeadersMiddleware
│  Security headers   │      X-Frame-Options, X-Content-Type, CSP, etc.
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐  [5] RateLimitMiddleware (non-testing only)
│  Rate limiting      │      Per-IP sliding window
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐  [6] RemoveBlockingHeadersMiddleware
│  Header cleanup     │      Strips headers that block streaming
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐  [7] GZipMiddleware
│  Compression        │      minimum_size=1000 bytes
└──────────┬──────────┘
           │
           ▼
      FastAPI Router
```

---

## 2. Request → Chat Flow (Complete)

```
Browser (Next.js :3000 Codespaces / :5000 Replit)
  │
  │  /api/* → rewrites to http://localhost:8000
  │
  ▼
FastAPI :8000
  │
  ├── POST /api/security/login
  │     └── AuthService → PostgreSQL (asyncpg via SQLAlchemy async)
  │
  └── GET/WS /api/chat/ws
        │
        │  WebSocket upgrade (HTTP → WS)
        │  [ISSUE: WS frames not traced — ISS-005]
        │
        ▼
     OrchestratorClient.chat_with_agent()
        │   span: orchestrator.chat_with_agent
        │
        ├── [Fallback 1] File Intelligence
        │     span: orchestrator.fallback.file_intelligence
        │     Detects large file payloads → local shell analysis
        │     status: SKIP if no files, OK if processed
        │
        ├── [Fallback 2] Exercise Retrieval
        │     span: orchestrator.fallback.exercise_retrieval
        │     Searches BAC exercise SQLite database
        │     status: SKIP if no match, OK if found
        │
        ├── [Fallback 3] HTTP → orchestrator:8006
        │     span: orchestrator.fallback.langgraph (confusingly named)
        │     Always fails: ConnectError (microservice DORMANT — Codespaces devcontainer
        │     only starts the `web` container; full stack at docker-compose.yml is not run)
        │     status: ERROR → continues to fallback 4
        │
        └── [Fallback 4] LangGraph run_local_graph()  ← DE-FACTO HANDLER (PARTIAL — fallback only)
              span: langgraph.run
              │
              ├── supervisor_node()
              │     span: langgraph.supervisor
              │     Intent classification: "educational" | "general" | "chat"
              │
              └── chat_node()
                    span: langgraph.chat_node
                    LLM: OpenRouter → openai/gpt-4o-mini (primary)
                         OpenAI → gpt-3.5-turbo (fallback)
                    Memory: MemorySaver(thread_id=conversation_id)
                    Response streamed back via WebSocket
```

---

## 3. Observability Pipeline

```
Any instrumented code
    │
    │  obs.start_trace("operation.name", tags={}, parent_context=ctx)
    │  obs.end_span(span_id, status="OK", metrics={...})
    │
    ▼
UnifiedObservabilityService  (app/telemetry/unified_observability.py)
    │  Singleton via get_unified_observability()
    │
    ├── TracingManager         — span CRUD, active_traces, completed_traces deque
    │     active_traces: dict[trace_id, TraceContext]
    │     active_spans: dict[span_id, SpanContext]
    │     completed_traces: collections.deque(maxlen=1000)
    │
    ├── MetricsManager         — counters, histograms, gauges
    │     Prometheus-format export via export_prometheus_metrics()
    │     [ISSUE: endpoint not exposed — ISS-010]
    │
    ├── LoggingManager         — structured logs with trace_id correlation
    │
    ├── TelemetryAnalyzer      — golden signals (latency, traffic, errors, saturation)
    │
    ├── TelemetryAggregator    — trace ↔ log correlation
    │     get_trace_with_correlation(trace_id) → {trace, correlated_logs}
    │
    └── TelemetryBridge        — export stubs for Jaeger/OTLP
          [ISSUE: stubs not activated — ISS-008]

API Exposure:
    GET /api/v1/observability/traces          → list last 50 completed traces
    GET /api/v1/observability/traces/{id}    → specific trace (in-flight or completed)
    GET /api/v1/observability/health         → system health
    GET /api/v1/observability/metrics        → [NOT YET EXPOSED — ISS-010]
    GET /api/v1/observability/aiops          → AI ops signals
    GET /api/v1/observability/alerts         → alert conditions
```

---

## 4. W3C Trace Context (traceparent)

```
Header format: traceparent: 00-{trace_id}-{parent_span_id}-{flags}
                             ^^  ^^^^^^^^   ^^^^^^^^^^^^^^  ^^^^
                             ver  32 hex     16 hex          01=sampled

Example: traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01

Implementation:
    TraceContext.from_headers(headers)   → parses traceparent + tracestate
    TraceContext.to_headers()            → generates traceparent string
    File: app/telemetry/models.py
```

---

## 5. Database Schema

```
PostgreSQL (Supabase, auto-created by app/core/db_schema.py on startup)

Authentication tables:
  users              — id, email, full_name, hashed_password, is_active, role_id
  roles              — id, name, description
  permissions        — id, name, resource, action
  user_roles         — user_id FK, role_id FK
  role_permissions   — role_id FK, permission_id FK
  refresh_tokens     — id, token, user_id FK, expires_at

Audit:
  audit_log          — id, user_id, action, resource, timestamp, details (JSONB)

Chat:
  customer_conversations — id, user_id FK, created_at, metadata
  customer_messages      — id, conversation_id FK, role, content, timestamp
  admin_conversations    — id, admin_id FK, created_at

Missions/Tasks:
  missions           — id, title, description, status, user_id FK
  mission_plans      — id, mission_id FK, plan_data (JSONB)
  tasks              — id, mission_id FK, title, status, order
  mission_events     — id, mission_id FK, event_type, payload (JSONB), timestamp

AI/Learning:
  prompt_templates   — id, name, template, variables (JSONB), version
  generated_prompts  — id, template_id FK, rendered, user_id FK, timestamp
  knowledge_nodes    — id, subject, content, embedding (vector — requires pgvector)
  knowledge_edges    — id, source_id FK, target_id FK, relation_type, weight
```

### DB access path for operators / Claude Code (D-DB-BRIDGE-001)

```
Two ways to reach the DB:
  1. App runtime → asyncpg → Supabase PgBouncer :6543 / direct :5432
     (only works where Postgres ports are open; blocked in sandbox/Codespaces)

  2. scripts/db_bridge.py → HTTPS :443 → Supabase Edge Function "claude-admin"
     → executes SQL, returns JSON   (works everywhere; 443 is never firewalled)
        config: SUPABASE_EDGE_FUNCTION_URL (public) + SUPABASE_EDGE_FUNCTION_KEY (secret, env-only)
        scope:  read / diagnose / manual DDL — NOT live-path writes (D-006)
        verified live 2026-06-03: PostgreSQL 17.6, current_user=postgres
```

---

## 6. Config System

```
Settings class: app/core/settings/base.py (DO NOT MODIFY — see deny list)
Access pattern: from app.core.config import get_settings; s = get_settings()

Config resolution order (Pydantic v2 BaseSettings):
  1. Environment variables (highest priority)
  2. .env file (if present)
  3. Field defaults

Critical auto-transforms:
  - APP_DATABASE_URL takes priority over DATABASE_URL
  - PgBouncer port 6543 → 5432 auto-rewrite (asyncpg compatibility)
  - SECRET_KEY: auto-generates if not set (EPHEMERAL — see ISS-001)

Singleton:
  @lru_cache(maxsize=1)
  def get_settings() -> Settings: return Settings()
  Test override: monkeypatch.setattr("app.core.config.get_settings", lambda: MockSettings())
```

---

## 7. LangGraph State Machine

```python
# State TypedDict (app/services/chat/local_graph.py)
class LocalChatState(TypedDict):
    question: str
    intent: str                    # "educational" | "general" | "chat"
    history_messages: list[dict]   # [{role, content}, ...]
    final_response: str

# Graph topology
START → supervisor_node → chat_node → END

# Checkpointing
MemorySaver(thread_id=conversation_id)  # in-process, lost on restart

# Context propagation (D-004)
_graph_trace_context: ContextVar[TraceContext | None]
  └── set before ainvoke() → read inside supervisor_node / chat_node
  └── reset (token) in finally block after ainvoke()
```

---

## 8. Test Architecture

```
tests/
  conftest.py                    — async fixtures (Python 3.12 syntax: def f[T])
  api/                           — HTTP endpoint tests (TestClient)
  architecture/                  — architectural constraint tests
  integration/                   — end-to-end with real DB (SQLite in-memory)
  telemetry/
    test_distributed_tracing.py  — 30 tests, all passing (added 2026-05-04)
  middleware/                    — middleware unit tests
  services/                      — service layer tests

Test env:
  DATABASE_URL=sqlite+aiosqlite:///:memory:
  SECRET_KEY=test-secret-key-for-ci-pipeline-secure-length
  ENVIRONMENT=testing
  LLM_MOCK_MODE=1
  SUPABASE_URL=https://dummy.supabase.co
  SUPABASE_ROLE_KEY=dummy

Runner: .venv/bin/pytest (Python 3.12 — NOT system pytest which is 3.11)
Count: 1658 tests collected total
```

---

## 9. Capability Reality (one-line summary — full table in `.memory/runtime_truth.md`)

- ACTIVE: FastAPI app, ObservabilityMiddleware + UnifiedObservabilityService, customer_chat / admin routers, OrchestratorClient.chat_with_agent (entrypoint), persistence layer, auth.
- PARTIAL: `local_graph.py` (runs on every turn in default Codespaces, but only because orchestrator HTTP fails — formally a fallback).
- DORMANT: orchestrator-service + all microservices, MCP server, DSPy, reranker microservice.
- ZOMBIE: `app/services/chat/graph/workflow.py` and all its nodes (super_reasoner, planner, researcher, writer, procedural_auditor, reviewer), `app/services/chat/memory_engine.py`, all `app/drivers/*`, `app/core/integration_kernel/runtime.py`, `KagentMesh` consumers.

If a doc here ever says a ZOMBIE/DORMANT component is "the primary handler", that doc has drifted — re-verify against `.memory/runtime_truth.md`.


## Update 2026-05-06 — Chat Stream Safety
- Admin boundary now returns sanitized stream error payloads (no raw exception echo to client).


## Update 2026-05-20 — BKT Cognitive Layer (D-074, E-TAALEEM Protocol V6.0)
- **BKT is the foundational cognitive layer.** `app/services/skills/bkt_engine.py:BKTEngine` (deterministic Bayesian Knowledge Tracing) is the substrate for every future autonomous pedagogical skill (adaptive difficulty, hints, learning paths). New adaptive skills build on `student_mastery_probability` — they MUST NOT re-invent mastery tracking. Governed by the versioned `BKT_COGNITIVE_DOCTRINE` (CI-validated in `scripts/fitness/check_skills_doctrine.py`).
- **Persistence**: append-only `student_bkt_analytics` (time-series log). Auto-created on boot; never upserted.
- **Abstraction Ban (Zero Cognitive Overload)**: generative-UI node labels are concrete human-readable Arabic (e.g., "كرة حمراء"), never abstract symbols (A/B|A/Ā). Hybrid extraction in `OrchestratorClient` (deterministic → LLM → concrete fallback).
- **Honest status**: BKT engine/persistence/emit = ACTIVE; the `bkt_hint_display` frontend portal = PARTIAL (stub renders fallback text; rich visualization pending).
- **DB egress**: Codespaces blocks Postgres ports 6543/5432 — schema changes via boot auto-creation (`validate_schema_on_startup`), not sandbox SQL.
