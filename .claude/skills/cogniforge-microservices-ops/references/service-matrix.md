# Service Matrix — Ports, Env Vars, Health Expectations

## Port Map

| Port | Service | Process pattern |
|------|---------|----------------|
| 8000 | monolith (FastAPI) | `app.main:app` |
| 8001 | user-service | `microservices.user_service.main:app` |
| 8002 | planning-agent | `microservices.planning_agent.main:app` |
| 8003 | conversation-service | `microservices.conversation_service.main:app` |
| 8006 | orchestrator-service | `microservices.orchestrator_service.main:app` |
| 8007 | research-agent | `microservices.research_agent.main:app` |
| 8008 | reasoning-agent | `microservices.reasoning_agent.main:app` |
| 8009 | content-retrieval-skill | `microservices.content_retrieval_skill.main:app` |
| 3001 | Grafana | `grafana server` |
| 9090 | Prometheus | `prometheus` |

---

## Required Env Vars Per Service

| Service | Critical env vars | Notes |
|---------|------------------|-------|
| orchestrator | `ORCHESTRATOR_DATABASE_URL` (asyncpg, port 5432), `OPENROUTER_API_KEY`, `CODESPACES=true`, `PLANNING_AGENT_URL`, `RESEARCH_AGENT_URL`, `REASONING_AGENT_URL`, `SECRET_KEY`, `OUTBOX_RELAY_ENABLED=true` | Must have CODESPACES=true in non-Docker |
| planning-agent | `PLANNING_DATABASE_URL` (asyncpg, port 5432), `OPENROUTER_API_KEY`, `SECRET_KEY` | SECRET_KEY must match orchestrator |
| research-agent | `TAVILY_API_KEY`, `OPENROUTER_API_KEY` | No DB required for core function |
| reasoning-agent | `OPENROUTER_API_KEY` | Falls back to mock without key |
| user-service | `USER_DATABASE_URL` (asyncpg, port 5432) | |
| conversation-service | `CONVERSATION_DATABASE_URL` (asyncpg, port 5432) | |
| content-retrieval-skill | None required | Reads from `knowledge_base/` directory |
| monolith | `DATABASE_URL` or `APP_DATABASE_URL` | Can use port 6543 (psycopg2 sync) |

---

## Health Field Expectations

| Service | Field | Expected value | Failure value |
|---------|-------|---------------|---------------|
| planning-agent | `database` | `postgresql+asyncpg://...` | `sqlite+aiosqlite:///:memory:` |
| research-agent | `tavily_available` | `"true"` | `"false"` |
| reasoning-agent | `llm_backend` | `"openrouter"` | `"mock"` |
| orchestrator | `graph_ready` | `true` | `false` |
| orchestrator | `startup_state` | `"ready"` | `"degraded"` |
| conversation-service | `graph_ready` | `true` | `false` |
| content-retrieval-skill | `kb_files` | `2` | `0` |

---

## Prometheus Scrape Targets (12 total)

| Job | URL | Step label |
|-----|-----|-----------|
| cogniforge-fastapi | `localhost:8000/api/v1/observability/prometheus` | — |
| user-service | `localhost:8001/metrics` | step=5 |
| planning-agent | `localhost:8002/metrics` | step=6 |
| conversation-service | `localhost:8003/metrics` | step=12 |
| orchestrator-service | `localhost:8006/metrics` | step=4 |
| postgres-checkpointer | `localhost:8006/metrics` | step=10 |
| skills-pipeline | `localhost:8006/metrics` | step=9 |
| research-agent | `localhost:8007/metrics` | step=7 |
| reasoning-agent | `localhost:8008/metrics` | step=8 |
| content-retrieval-skill | `localhost:8009/metrics` | step=11 |
| prometheus | `localhost:9090/metrics` | — |
| grafana | `localhost:3001/metrics` | — |

---

## Grafana Dashboards (17 total)

| UID | Title |
|-----|-------|
| `cogniforge-master-overview` | Master Overview (All Services) — **new** |
| `cogniforge-ms-step12-conversation` | Step 12 — Conversation Service |
| `cogniforge-ms-step11-full-skills` | Step 11 — Full Skills Pipeline |
| `cogniforge-ms-step10-checkpointer` | Step 10 — Postgres Checkpointer |
| `cogniforge-ms-step9-pipeline` | Step 9 — Skills Composition Pipeline |
| `cogniforge-ms-step8-reasoning-agent` | Step 8 — Reasoning Agent |
| `cogniforge-ms-step7-research-agent` | Step 7 — Research Agent |
| `cogniforge-ms-step6-planning-agent` | Step 6 — Planning Agent |
| `cogniforge-ms-step5-user-service` | Step 5 — User Service |
| `cogniforge-ms-step4-persistence` | Step 4 — Persistence Relay |
| `cogniforge-ms-step3-live` | Step 3 — Live Activation |
| `cogniforge-ms-transition-step2` | Step 2 — StateGraph Routing |
| `cogniforge-mission-control` | Mission Control |
| `cogniforge-langgraph` | LangGraph Runtime |
| `cogniforge-http-api` | HTTP API Surface |
| `cogniforge-stack-health` | Stack Self-Monitoring |
| `cogniforge-paths-deep` | Path Deep Dive |

---

## cogniforge Prometheus Metrics (79 active)

Key metrics by service:

| Prefix | Service | Key metrics |
|--------|---------|------------|
| `cogniforge_pipeline_*` | orchestrator | `invocations_total{mode}`, `duration_seconds`, `skill_calls_total{skill,status}` |
| `cogniforge_orchestrator_*` | orchestrator | `requests_total`, `request_duration_seconds`, `startup_info` |
| `cogniforge_outbox_relay_*` | orchestrator | `cycles_total{result}`, `processed_total`, `failed_total`, `pending_gauge` |
| `cogniforge_checkpointer_*` | orchestrator | `writes_total`, `reads_total`, `duration_seconds`, `backend_info` |
| `cogniforge_planning_*` | planning-agent | `requests_total`, `plans_total`, `dspy_invocations_total`, `startup_info` |
| `cogniforge_research_*` | research-agent | `searches_total`, `search_duration_seconds`, `startup_info{tavily_available}` |
| `cogniforge_reasoning_*` | reasoning-agent | `invocations_total`, `invocation_duration_seconds`, `startup_info{llm_backend}` |
| `cogniforge_conversation_*` | conversation-service | `requests_total`, `startup_info{graph_ready}` |
| `cogniforge_retrieval_*` | content-retrieval | `hits_total`, `misses_total`, `knowledge_base_size` |
| `cogniforge_user_*` | user-service | `requests_total`, `auth_operations_total`, `startup_info` |
