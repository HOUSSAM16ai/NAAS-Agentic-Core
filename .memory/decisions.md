# Architectural Decisions
> Last updated: 2026-05-05 (environment: GitHub Codespaces)

## D-001 · LangGraph as Primary Chat Handler
**Decision**: `app/services/chat/local_graph.py` is the real handler. The orchestrator microservice is DORMANT in the default development environment.
**Reason**: GitHub Codespaces devcontainer (`.devcontainer/docker-compose.host.yml`) only spins up the `web` container; it does NOT start the microservices stack from `docker-compose.yml`. The orchestrator at `orchestrator:8006` always fails with ConnectError.
**Consequence**: All chat goes through the fallback chain → LangGraph `run_local_graph()`. This holds for both Codespaces and Replit-style single-process deployments.
**Rule**: NEVER assume the orchestrator microservice is reachable. LangGraph is the truth — unless you explicitly run `docker compose -f docker-compose.yml up -d` to wake the full stack.

## D-002
`app/kernel.py` is the authoritative composition root.

## D-002 · MemorySaver for Conversation Persistence
**Decision**: LangGraph uses `MemorySaver(thread_id=conversation_id)` for per-conversation state.
**Reason**: Simple, in-process, no Redis/Postgres needed. Works in any single-process deployment (Codespaces devcontainer, Replit, bare uvicorn).
**Consequence**: Conversation memory is lost on process restart.
**Alternative considered**: `langgraph-checkpoint-postgres` — too heavy for current setup.

## D-004
Cross-boundary communication is API-first only; direct DB coupling is forbidden.

## D-005
Architecture documentation must be code-evidenced and updated in the same PR.

## D-006 · Single Persistence Owner — Monolith Owns Message Writes
**Decision**: The Monolith (`app/api/routers/customer_chat.py`) is the sole owner of
writes to `customer_messages` and `admin_messages`. The Orchestrator microservice MUST
NOT write to these tables.
**Reason**: Dual-write (ISS-014) corrupts conversation history and inflates LLM context.
The Orchestrator is DORMANT in the default Codespaces setup, making Monolith ownership
the only live path anyway.
**Consequence**: Any re-activation of the Orchestrator microservice requires an
explicit write-guard check (`if not already_persisted: skip`) before any DB INSERT.
**Status**: DECIDED — implementation pending (ISS-015 open)

## D-007 · thread_id Must Equal conversation_id — No Re-derivation
**Decision**: LangGraph `thread_id` (MemorySaver key) is always derived as
`str(conversation_id)` at the OrchestratorClient entry point and passed explicitly.
It is NEVER re-derived inside graph nodes or fallback handlers.
**Reason**: Re-derivation caused context identity fragmentation (ISS-019) where
fallback paths opened a fresh LangGraph thread for a continuing conversation.
**Status**: DECIDED — implementation pending (ISS-019 open)

## D-008 · Postgres Checkpointer as Opt-In (Not Default)
**Decision**: MemorySaver remains the default checkpointer (D-002). Postgres-backed
checkpointing (`langgraph-checkpoint-postgres`) is opt-in via
`LANGGRAPH_CHECKPOINTER=postgres` env var.
**Reason**: MemorySaver is sufficient for development. The trade-off (state lost on
restart) is acceptable in Codespaces but documented explicitly as ISS-020.
**Consequence**: Production deployment MUST set `LANGGRAPH_CHECKPOINTER=postgres`
to preserve conversation continuity across restarts.
**Status**: DECIDED — implementation pending (ISS-020 open)
