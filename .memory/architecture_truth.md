# Architectural Diagnostic: NAAS-Agentic-Core
> Last updated: **2026-05-09** | Live audit (Ona agent — full runtime investigation).

## Executive Summary
The system is in a "strangler fig" migration phase from monolith to microservices. In the default Codespaces environment (without explicitly launching `docker-compose.yml`), the system relies entirely on the FastAPI monolith and a 2-node local LangGraph fallback. The advertised "Agentic" capabilities (KAgent, MCP, DSPy, Reranker, LlamaIndex, Multi-agent workflows) are either DORMANT (gated behind microservices that aren't running) or ZOMBIE (code exists but has no live consumers).

## Component Inventory & Truth Table (2026-05-09)

| Component | Status | Proof |
|---|---|---|
| **Monolith API** (`app/api/routers/customer_chat.py` & others) | **ACTIVE** | `chat_stream_ws` is the live entrypoint. 62 routes registered. Frontend directly fetches `/api/security/login`, `/api/chat/conversations` via monolith routes. |
| **Frontend Next.js** (`frontend/`) | **ACTIVE** | Running on port **3000** (supervisor.sh overrides package.json port 5000). Uses `fetch` to legacy routes and `new WebSocket` to `/api/chat/ws`. |
| **LangGraph local engine** (`app/services/chat/local_graph.py`) | **PARTIAL** | Used by `OrchestratorClient` fallback tier 3. 2 nodes: supervisor (intent) + chat (OpenRouter). Live confirmed: `run_local_graph('مرحبا')` → response. |
| **LangGraph multi-agent workflow** (`app/services/chat/graph/workflow.py`) | **ZOMBIE** | Only importer: `tests/verify_graph_manual.py`. Never executed in production. |
| **KAgent Mesh** (`app/services/kagent/`) | **ZOMBIE** | DI-registered in `app/core/di.py:145` but only consumed by dead `workflow.py` graph nodes. No live consumer. |
| **MCP** (`app/services/mcp/`) | **DORMANT** | Not referenced by live APIs or kernel. Lazy-imported only in dormant agents. |
| **Reranker / LlamaIndex / DSPy** | **DORMANT** | Implemented in `microservices/research_agent` and `orchestrator_service`. Blocked by microservice boundaries that are inactive by default. |
| **Database** (`app/core/database.py`) | **ACTIVE** | Monolith directly accesses DB via `async_session_factory`. PostgreSQL 17.6 Supabase. PgBouncer transaction mode. |
| **Cache** (`app/caching/factory.py`) | **ACTIVE (InMemoryCache)** | `REDIS_URL` not set → `get_cache()` returns `InMemoryCache`. Redis process runs on 6379 but unused. |
| **AI Gateway** (`app/core/gateway/simple_client.py`) | **ACTIVE** | `SimpleAIClient` with OpenRouter. Primary: `nvidia/nemotron-3-super-120b-a12b:free`. 5 fallback models. |
| **Microservices Stack** (`planning_agent`, `memory_agent`, `user_service`, etc.) | **DORMANT** | Configured in `docker-compose.yml`, not part of default boot process. |
| **Grafana** | **ACTIVE** | Port **3001** (provisioning CLI overrides `grafana.ini` `http_port=3000`). |
| **Prometheus** | **ACTIVE** | Port **9090**. Scrapes FastAPI at `:8000/api/v1/observability/prometheus`. |
| **OTEL export** | **NO-OP** | `OTEL_EXPORTER_OTLP_ENDPOINT=http` is an invalid URL. No spans exported. |

## Port Map (verified 2026-05-09)
| Service | Port | Note |
|---|---|---|
| Next.js | 3000 | supervisor.sh `--port 3000` overrides package.json `--port 5000` |
| FastAPI | 8000 | requires `DATABASE_URL` |
| Grafana | 3001 | provisioning CLI overrides `grafana.ini` `http_port=3000` |
| Prometheus | 9090 | |
| Redis | 6379 | process running but app uses InMemoryCache |
| PostgreSQL | 6543 | Supabase PgBouncer |

## Current Architectural Risks
1. **Drift between docs and code** — docs describe the target architecture, not runtime. Always check `.memory/runtime_truth.md`.
2. **Hidden coupling** — if internal models are passed between services instead of explicit API contracts.
3. **Role confusion in app shell** — business logic creeping into route handlers.
4. **Service readiness variance** — no unified health contracts across local/dev/prod.
5. **OTEL misconfiguration** — `OTEL_EXPORTER_OTLP_ENDPOINT=http` is set but invalid. Traces are silently dropped.
6. **Cache inconsistency** — `REDIS_URL` not set means InMemoryCache is used. State is not shared across workers/restarts.

## Transformation Gap
To move from "transitional/zombie" to "production-grade multi-service":
1. **Wake the mesh** — `docker compose -f docker-compose.yml up -d` + set `ORCHESTRATOR_SERVICE_URL`. Prove `compatibility_facade=True` round-trip writes exactly one row per turn. No code change required.
2. **Fix OTEL** — set `OTEL_EXPORTER_OTLP_ENDPOINT` to a valid collector URL.
3. **Activate Redis** — set `REDIS_URL=redis://localhost:6379/0`.
4. **Promote ONE agentic layer** — pick exactly one of (multi-agent workflow, MCP, KAgent, LlamaIndex, reranker, DSPy) and wire it into the live router or a `local_graph` node. Add runtime trace assertion. Update `.memory/runtime_truth.md`.
