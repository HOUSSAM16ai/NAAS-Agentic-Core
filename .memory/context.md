# CogniForge — Project Context
> Last updated: 2026-05-04 | Branch: claude/add-distributed-tracing-T9Q8z

## Identity
- **Name**: NAAS-Agentic-Core (CogniForge)
- **Purpose**: AI tutor for Algerian high-school students preparing for the Baccalaureate exam
- **Languages**: Arabic (MSA) / French / Darija — all three simultaneously
- **Subjects**: Math, Physics, Chemistry, History, Geography, Languages
- **Environment**: Replit (single-process) — Docker/microservices are DORMANT

## Stack
| Layer | Tech | Port |
|-------|------|------|
| Frontend | Next.js 15 | 5000 |
| Backend | FastAPI (Python 3.12) | 8000 |
| AI Graph | LangGraph 1.1.10 | in-process |
| DB | PostgreSQL (Supabase) + aiosqlite (tests) | 5432 |
| LLM | OpenRouter (primary) → OpenAI (fallback) | cloud |
| Cache | Redis (optional, falls back to memory) | 6379 |
| Tracing | UnifiedObservabilityService (in-process) | — |

## Start Commands
```bash
# Backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm run dev

# Tests
DATABASE_URL="sqlite+aiosqlite:///:memory:" SECRET_KEY="test-secret-key-for-ci-pipeline-secure-length" \
ENVIRONMENT="testing" LLM_MOCK_MODE="1" SUPABASE_URL="https://dummy.supabase.co" SUPABASE_ROLE_KEY="dummy" \
.venv/bin/pytest tests/ -v

# Lint
ruff check . && isort --check-only .
```

## Request Flow (The Reality)
```
Student browser
  └─ Next.js :5000
        └─ /api/* → rewrites → FastAPI :8000
              └─ ObservabilityMiddleware  ← traces every request (W3C Trace Context)
                    └─ /api/chat/ws  (WebSocket)
                          └─ OrchestratorClient.chat_with_agent()
                                ├─ [1] File intelligence (local shell)
                                ├─ [2] Exercise retrieval (local BAC DB)
                                ├─ [3] HTTP → orchestrator:8006 → ConnectError (DORMANT)
                                └─ [4] LangGraph local_graph.py  ← PRIMARY HANDLER
                                          supervisor_node (intent) → chat_node (LLM) → END
```

## 18 Database Tables
```
Auth:     users, roles, permissions, user_roles, role_permissions, refresh_tokens
Audit:    audit_log
Chat:     customer_conversations, customer_messages, admin_conversations
Missions: missions, mission_plans, tasks, mission_events
AI:       prompt_templates, generated_prompts, knowledge_nodes, knowledge_edges
```

## Environment Variables (Critical)
| Variable | Status | Notes |
|----------|--------|-------|
| APP_DATABASE_URL | ✅ Replit secret | Supabase PostgreSQL |
| SECRET_KEY | ⚠️ Ephemeral | Restart = all users logged out |
| OPENROUTER_API_KEY | ✅ Set | Primary LLM |
| OPENAI_API_KEY | ✅ Set | Secondary |
| ENVIRONMENT | ✅ development | |
| ORCHESTRATOR_SERVICE_URL | ❌ Not set | Always ConnectError in Replit |
| REDIS_URL | ❌ Not set | Falls back to in-memory |

## Python Environment
- Python 3.12 (`.python-version`)
- Virtual env: `.venv/` (created with `uv venv`)
- Test runner: `.venv/bin/pytest` (NOT the system pytest which is 3.11)
- 1658 tests collected total
