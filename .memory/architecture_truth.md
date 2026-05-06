# Architectural Diagnostic: NAAS-Agentic-Core

## Executive Summary
The system is currently in a transitional "strangler fig" phase, moving from a monolithic FastAPI application (`app/`) to a microservices architecture (`microservices/`). However, in the default development environment (Codespaces/Replit without explicitly launching `docker-compose.yml`), the system relies almost entirely on the legacy monolith and a rudimentary local fallback graph. The advertised "Agentic" capabilities (Kagent, MCP, DSPy, Reranker, LlamaIndex, Multi-agent workflows) are either fully DORMANT (gated behind microservices that aren't running) or ZOMBIE (code exists, registered in DI, but has no live consumers in the active execution paths).

## Component Inventory & Truth Table

| Component | Status | Proof |
|---|---|---|
| **API Gateway** (`microservices/api_gateway/main.py`) | **ACTIVE/PARTIAL** | Defines route proxies (`@app.api_route`), but relies on microservices being up. |
| **Monolith API** (`app/api/routers/customer_chat.py` & others) | **ACTIVE** | `chat_stream_ws` is the live entrypoint for standard chat interactions. Frontend directly fetches `/api/security/login`, `/api/chat/conversations` via monolith routes. |
| **Frontend Next.js** (`frontend/`) | **ACTIVE** | Uses `fetch` to legacy routes and `new WebSocket` to `/api/chat/ws`. Relies on Next.js proxying (`API_URL`). |
| **LangGraph (Monolith)** (`app/services/chat/local_graph.py`) | **ACTIVE (Fallback)** | Used by `OrchestratorClient` when microservice fails (`_build_local_graph_response`). Only 2 nodes (Supervisor + Chat). |
| **LangGraph (Microservice)** (`microservices/orchestrator_service/src/services/overmind/graph/main.py`) | **DORMANT** | Contains advanced reasoning, multi-agent workflows, and search nodes. Never executed unless `orchestrator-service` container is explicitly started. |
| **Kagent Mesh** (`app/services/kagent/`) | **ZOMBIE** | DI-registered in `app/core/di.py:145` but only consumed by dead `workflow.py` graph nodes. No live consumer. |
| **MCP** (`app/services/mcp/`) | **DORMANT** | Not referenced by live APIs or the micro-kernel. Lazy-imported only in dormant agents (`admin.py`, `socratic_tutor.py`). |
| **Reranker / LlamaIndex / DSPy** | **DORMANT** | Implemented in `microservices/research_agent` and `orchestrator_service`. Blocked by microservice boundaries that are inactive by default. |
| **Database** (`app/core/database.py`) | **ACTIVE** | Monolith directly accesses DB via `async_session_factory`. Microservices have their own decoupled configs but are dormant. |
| **Redis Cache** (`app/caching/redis_cache.py`, `app/core/redis_bus.py`) | **ACTIVE** | Used for rate limiting, distributed caching, and pub/sub. |
| **Microservices Stack** (`planning_agent`, `memory_agent`, `user_service`, etc.) | **DORMANT** | Configured in `docker-compose.yml`, but not part of default boot process. |

## Execution Paths
- **HTTP Requests**: Frontend -> Next.js Proxy -> (If legacy: monolith `app/api/routers/`) OR (If microservice: `api-gateway` -> respective service). Currently, frontend makes direct legacy calls.
- **WebSocket Streaming**: Frontend `new WebSocket('/api/chat/ws')` -> Monolith `app/api/routers/customer_chat.py:chat_stream_ws`.
- **Chat Processing**: `chat_stream_ws` -> `orchestrator_client.chat_with_agent` -> Fails connecting to `$ORCHESTRATOR_SERVICE_URL` -> Local Fallbacks (File Intelligence -> Exercise Retrieval -> Local LangGraph -> General Chat).

## Runtime Findings
- The system advertises advanced multi-agent interactions, but in reality, runs a simple fallback chain with `local_graph.py` serving the bulk of conversational logic.
- Kagent, MCP, and complex DSPy-based retrieval are technically present but functionally dead weight in the default runtime.
- The Next.js frontend is heavily entangled with the legacy monolith API, making REST calls (`fetch`) to endpoints like `/api/security/login`.

## Architecture Diagnosis
- **API-First?**: No, transitional hybrid. Direct fetches to legacy monolith coupled with gateway proxies.
- **Microservices?**: Transitional. Gated behind a `docker-compose` that is often off by default. True microservices are dormant.
- **StateGraph Reasoning?**: Yes, but partial/fallback only in production. The advanced graph is dormant.
- **Multi-Agent?**: Zombie. Coordination is mock or dormant.
- **Split-Brain?**: Yes. Both monolith and microservices attempt to manage routes (e.g., `/api/chat/ws`). Capability fragmentation is extremely high.

## Remaining Unknowns
- How much of the monolith logic is 1:1 replicable in the currently dormant microservices?
- Can the frontend fully operate exclusively through `api-gateway` without legacy route assumptions?

## Final Verdict
The system is heavily fragmented. To move to a mature, highly-capable architecture, we must stop building inside the zombie/dormant monolithic folders (`app/services/kagent`, `app/services/mcp`) and fully commit to the microservices routing, or explicitly rip them out. The `api-gateway` must become the true BFF, and the default runtime must either boot the microservices or gracefully downgrade to a unified monolith instead of split-brain fallback chains.