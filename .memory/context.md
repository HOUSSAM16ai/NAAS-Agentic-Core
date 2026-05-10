# CogniForge — Project Context
> Last updated: **2026-05-10** | Branch: `feat/microservices-step2-stategraph-routing`.
> **Runtime capability status:** see `.memory/runtime_truth.md` (authoritative — verified live 2026-05-10).
> **CI gates today:** ruff/contracts/guardrails/tests + structure-validation + `doc-integrity` + `runtime-truth-drift-check` + `microservices-transition` (NEW).

## Identity
- **Name**: NAAS-Agentic-Core (CogniForge)
- **Purpose**: AI tutor for Algerian high-school students preparing for the Baccalaureate exam
- **Languages**: Arabic (MSA) / French / Darija — all three simultaneously
- **Subjects**: Math, Physics, Chemistry, History, Geography, Languages
- **Supported environments**: GitHub Codespaces (primary dev) **and** Replit — the app is environment-agnostic. In both, microservices are DORMANT by default.
- **Codespaces**: `.devcontainer/devcontainer.json` → `docker-compose.host.yml` (web container only) → `supervisor.sh` launches `uvicorn app.main:app` + Next.js
- **Replit**: `package.json` script runs Next.js on port **5000**; backend started manually with uvicorn on 8000
- **Microservices wake-up** (either environment): `docker compose -f docker-compose.yml up -d`

## Stack (verified live 2026-05-10)
| Layer | Tech | Port | Status |
|-------|------|------|--------|
| Frontend | Next.js 15 | **3000** | ACTIVE — supervisor.sh passes `--port 3000` overriding package.json `--port 5000` |
| Backend | FastAPI (Python 3.12) | **8000** | CONDITIONAL — requires `DATABASE_URL` |
| AI Graph | LangGraph 1.1.10 | in-process | PARTIAL — 2 nodes (supervisor + chat) via fallback |
| DB | PostgreSQL 17.6 (Supabase PgBouncer) | **6543** | ACTIVE — 19 users, 2098 customer_messages, 3038 admin_messages |
| LLM | OpenRouter (primary: `nvidia/nemotron-3-super-120b-a12b:free`) | cloud | ACTIVE — 367 models, live call confirmed |
| Cache | InMemoryCache (Redis process runs but unused — no `REDIS_URL`) | 6379 | ACTIVE (in-memory only) |
| Tracing | UnifiedObservabilityService (in-process) | — | ACTIVE |
| OTEL export | otel_setup.py | — | NO-OP — `OTEL_EXPORTER_OTLP_ENDPOINT=http` is invalid |
| Grafana | native binary | **3001** | ACTIVE — 6 dashboards (NEW: 50-microservices-transition.json) |
| Prometheus | native binary | **9090** | ACTIVE — 11 scrape jobs (NEW: orchestrator-service, research-agent, user-service, planning-agent) |
| Routing Policy | ChatRoutingPolicy | — | ACTIVE — default: state_graph → /api/chat/messages (Step 2) |

## Database state (live 2026-05-09)
- **Users**: 19 total (admin: `benmerahhoussam16@gmail.com`, user: `houssamannaba963@gmail.com`)
- **customer_messages**: 2098 rows
- **admin_messages**: 3038 rows
- **missions**: 79 rows
- **alembic_version**: `f2b3c4d5e6f7`
- **PgBouncer quirk**: transaction mode — always use `statement_cache_size=0` with asyncpg

## AI Gateway (live 2026-05-09)
- **Client**: `SimpleAIClient` (`app/core/gateway/simple_client.py`)
- **Primary model**: `nvidia/nemotron-3-super-120b-a12b:free`
- **Fallback models**: `google/gemini-2.0-flash-exp:free`, `qwen/qwen3-coder:free`, `kwaipilot/kat-coder-pro:free`, `microsoft/phi-3-mini-128k-instruct:free`, `meta-llama/llama-3.2-11b-vision-instruct:free`

## Start Commands
```bash
# Backend (requires DATABASE_URL)
DATABASE_URL="..." OPENROUTER_API_KEY="..." uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (supervisor.sh overrides to port 3000)
cd frontend && npm run dev -- --port 3000

# Tests
DATABASE_URL="sqlite+aiosqlite:///:memory:" SECRET_KEY="test-secret-key-for-ci-pipeline-secure-length" \
ENVIRONMENT="testing" LLM_MOCK_MODE="1" SUPABASE_URL="https://dummy.supabase.co" SUPABASE_ROLE_KEY="dummy" \
pytest tests/ -v

# Lint
ruff check . && ruff format --check .
```

## Request Flow (verified live 2026-05-09)
```
Student browser
  └─ Next.js (:3000)
        └─ /api/* → rewrites → FastAPI :8000
              └─ ObservabilityMiddleware ← traces every HTTP request
                    └─ /api/chat/ws (WebSocket)
                          │  Auth: ?token= query param
                          │  ⚠️ WS layer NOT traced per-frame (ISS-005)
                          │
                          └─ OrchestratorClient.chat_with_agent()
                                │
                                ├─ [1] File intelligence → SKIP (no files)
                                ├─ [2] Exercise retrieval → SKIP (no BAC match)
                                ├─ [3] HTTP → orchestrator:8006 → ConnectError (DORMANT)
                                └─ [4] LangGraph local_graph.py ← DE-FACTO HANDLER
                                          supervisor_node (intent: educational/chat/general)
                                          └─ chat_node → OpenRouter API → response
```

## 25 Database Tables
```
Auth:     users, roles, permissions, user_roles, role_permissions, refresh_tokens, password_resets
Audit:    audit_log
Chat:     customer_conversations, customer_messages, admin_conversations, admin_messages
Missions: missions, mission_plans, tasks, mission_events, mission_outbox
AI:       prompt_templates, generated_prompts, knowledge_nodes, knowledge_edges
Content:  content_items, content_search, content_solutions
System:   alembic_version
```

## Critical environment facts
- `DATABASE_URL` or `APP_DATABASE_URL` **must** be set — app crashes without it
- `OPENROUTER_API_KEY` **must** be set — all LLM calls fail without it
- `OTEL_EXPORTER_OTLP_ENDPOINT=http` is currently set but is an **invalid URL** — OTEL is a no-op
- `REDIS_URL` is **not set** — cache falls back to `InMemoryCache`
- `ORCHESTRATOR_SERVICE_URL` is **not set** — orchestrator HTTP path always fails → fallback chain runs
