# Architectural Diagnostic — 2026-05-06
> Branch: `claude/diagnostic-system-architecture-aRSuW`
> Mode: READ-ONLY (no source code changed)
> Authority for capability status: `.memory/runtime_truth.md` (this file references it).

## Verdict (one sentence)
A FastAPI Monolith with a clean WS chat boundary, sitting on top of a parallel microservice mesh that is fully **DORMANT** by default and a parallel multi-agent / reasoning / RAG / KAgent / MCP layer that is fully **ZOMBIE** — ~10% of the advertised stack runs in production.

## Live (ACTIVE) — only these execute on every request
- FastAPI app (`app/main.py` → `app/kernel.py`).
- Middleware: TrustedHost → CORS → **ObservabilityMiddleware** → SecurityHeaders → RemoveBlockingHeaders → RateLimit → GZip (`app/core/app_blueprint.py:167-177`).
- 9 routers mounted at `app/api/routers/registry.py:21-35`.
- 2 WS endpoints: `customer_chat.py:244` (`/api/chat/ws`), `admin.py:316` (`/admin/api/chat/ws`).
- `OrchestratorClient.chat_with_agent` (single chat boundary) — `customer_chat.py:422`, `admin.py:490`.
- `_emit_terminal_frames` (single terminal-frame emitter) — `customer_chat.py:180`, `admin.py:159`.
- `CustomerChatBoundaryService.save_message` (sole writer in default env) for both `customer_messages` and `admin_messages`.
- `UnifiedObservabilityService` (HTTP traces only — WS untraced, ISS-005).
- Frontend: `frontend/app/hooks/useRealtimeConnection.js:56` is the sole WS factory; `frontend/next.config.js` proxies `/api/*` and `/admin/api/*` to `:8000`.

## Live with caveat (PARTIAL)
- **`app/services/chat/local_graph.py`** — runs every turn (because the orchestrator is dormant), but uses `ainvoke` not `astream_events` (ISS-023). MemorySaver only (volatile, ISS-020). 2 nodes only (supervisor + chat).

## Dormant (real code, gated by external infra)
- All 10 microservices in `microservices/*` (orchestrator, planning, memory, user, research, reasoning, auditor, conversation, api_gateway, observability). Wake via `docker compose -f docker-compose.yml up -d` + matching env vars.
- Orchestrator's DSPy graph (`microservices/orchestrator_service/.../graph/*`).
- Research agent's reranker + DSPy query refiner.
- MCP server / integrations (`app/services/mcp/*`) — lazy-imported only on side paths the live router never touches.
- Dual Redis (`redis:6379`, `redis-orchestrator:6380`) — neither runs in default devcontainer.
- Orchestrator's direct DB writers (`microservices/orchestrator_service/src/api/routes.py:1211,1216,1361,1366`) — load-bearing only when awoken; D-006 contract is the only thing preventing dual-write.

## Zombie (no live call chain)
- `app/services/chat/graph/workflow.py` + all `graph/nodes/*` (super_reasoner, planner, researcher, writer, procedural_auditor, reviewer, supervisor) — only importer is `tests/verify_graph_manual.py`.
- `app/services/chat/graph/components/*` (context_composer, intent_detector, prompt_strategist) — only used by `workflow.py` (zombie).
- `app/services/chat/agents/orchestrator.py` + `education_council.py` — parallel "MultiAgent" path with no live importer.
- `app/services/chat/agents/{admin,curriculum,socratic_tutor,testing_agent,refactor,analytics,...}.py` — not invoked by live WS routers.
- `app/services/chat/{dispatcher,intent_detector,intent_registry,tool_router,tool_access,education_policy_gate,orchestration_rollout}.py` — zero importers in `app/api/`, `app/main.py`, `app/kernel.py`.
- `app/services/chat/memory_engine.py` (LlamaIndex) — only consumed by zombie reviewer.
- `app/drivers/{llamaindex_driver, reranker_driver, kagent_driver}.py` — only referenced by dormant MCP integrations.
- `app/services/kagent/*` — DI-registered (`app/core/di.py:145`) but only consumer is zombie workflow.
- `app/core/integration_kernel/runtime.py` — singleton designed but never instantiated from live startup.

## Persistence boundary (must not regress)
- D-006: Monolith is **sole writer** to `customer_messages` / `admin_messages` in the default env.
- `compatibility_facade=True` flag (set at `customer_chat.py:430`) is the handshake that disables orchestrator user-message writes when the mesh is awake.
- `persisted: true` echo on the terminal event is the handshake that disables Monolith assistant-message writes when the orchestrator successfully wrote.
- Architecture test enforcing this: `tests/architecture/test_persistence_authority.py`.
- Duplicate-guard at `app/services/customer/chat_persistence.py:81-112` is the third safety net.

## Hard "do not assume" list
1. Do not assume any microservice is reachable. Default behavior is `ConnectError`.
2. Do not assume Redis is up. The cache transparently falls back to memory; treat hot-path performance accordingly.
3. Do not assume the multi-agent graph runs. It does not — `local_graph.py` does.
4. Do not assume MCP, KAgent, LlamaIndex, DSPy, or the reranker contribute to a chat reply. They do not.
5. Do not duplicate `_emit_terminal_frames` or skip the `persisted` flag. Single-emitter / single-writer rules are §6.5 invariants.
6. Do not move user-message writes out of the WS entry. They belong in the Monolith — period.
7. Do not promote any DORMANT/ZOMBIE row in `runtime_truth.md` to ACTIVE without `import + call chain + runtime evidence` triple in the same PR.

## Path to "professional, multi-service, scalable" (sequence, not menu)
1. **Wake the mesh** (infra-only, no code): `docker compose -f docker-compose.yml up -d` + `ORCHESTRATOR_SERVICE_URL` set. Prove the persistence handshake under load.
2. **Promote ONE agentic layer to ACTIVE per PR.** Wire it into the live router (or a `local_graph` node), add runtime evidence, update the truth table. No batch promotions.
3. **Decide every ZOMBIE/DORMANT row explicitly** — promote, gate behind env+ADR, or delete with ADR.
4. **Close ISS-005 (WS tracing) and ISS-023 (token streaming).** Production-grade chat needs both.
5. **Add CI architecture tests** that fail when a ZOMBIE acquires a live importer without a matching truth-table update.
6. **Replace MemorySaver** (D-002) with `langgraph-checkpoint-postgres` once persistence story is consolidated (ISS-020).
7. **Define real service contracts** between microservices (OpenAPI per service + contract tests in CI). Today there is no inter-service contract test running between live processes.

## File inventory pointers (for next session)
- Routers: `app/api/routers/{system/, admin.py, security.py, data_mesh.py, ums.py, customer_chat.py, content.py, observability.py}` (679 + 605 + 500 + … lines).
- Live chat WS: `customer_chat.py` (605 L) and `admin.py` (679 L).
- Live boundary client: `app/infrastructure/clients/orchestrator_client.py` — fallback chain at `:486` (file-intel), `:527` (exercise-retrieval), `:569` (LangGraph), `:605` (general-chat).
- Live graph: `app/services/chat/local_graph.py` — pre-warmed at `app/kernel.py:239-241`.
- Frontend WS: `frontend/app/hooks/useRealtimeConnection.js:56` (factory), `useAgentSocket.js:180` (consumer).

## Closing rule (non-negotiable)
Any component without all three of `import` + `call chain` + `runtime evidence` reaching from `app/main.py` is **DORMANT** or **ZOMBIE** until the contrary is proven. Treat every "the system supports X" claim with this filter — including claims in `docs/`, `README.md`, and this file's own future revisions.
