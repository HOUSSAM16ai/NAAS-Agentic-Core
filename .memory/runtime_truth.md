# Runtime Truth Lock
> Last updated: 2026-05-06 | Branch: claude/runtime-truth-audit-65iVU
> Authority: this file overrides any contradictory aspirational doc in `docs/` or root markdown.

## Golden rule
A capability counts as real ONLY when proven by **all three** of:
1. **import** — the module is imported by code reachable from `app/main.py`.
2. **call chain** — there is a live caller that flows from a router/middleware/startup hook.
3. **runtime evidence** — the code actually executes on the production path (logs, traces, DB writes).

Missing any of the three → DORMANT, ZOMBIE, or UNKNOWN. Not ACTIVE.

## Status legend
- `ACTIVE` — all three present.
- `PARTIAL` — on a live chain but only via fallback / conditional / non-default branch.
- `DORMANT` — code real, gated behind an external service that does not start by default.
- `ZOMBIE` — exists with no live call chain from a production entrypoint.
- `UNKNOWN` — insufficient evidence.

---

## Capability table (verified by audit, 2026-05-06)

| # | Component | File(s) | Status | Proof |
|---|---|---|---|---|
| 1 | LangGraph local engine | `app/services/chat/local_graph.py` | PARTIAL | imported `app/kernel.py:239` (pre-warm) + `app/infrastructure/clients/orchestrator_client.py:170` (fallback tier 3); runs on every turn in default Codespaces because orchestrator URL unset. Uses `ainvoke` (ISS-023). MemorySaver only (ISS-020, D-002, D-008). |
| 2 | LangGraph multi-agent workflow | `app/services/chat/graph/workflow.py` + `graph/nodes/*.py` | ZOMBIE | only importer is `tests/verify_graph_manual.py`. Zero references from `app/api/`, `app/main.py`, `app/kernel.py`, or `orchestrator_client.py`. |
| 3 | LlamaIndex memory engine | `app/services/chat/memory_engine.py` | ZOMBIE | only consumed by `reviewer.py` inside the dead workflow. Not on live chat path. |
| 4 | LlamaIndex driver | `app/drivers/llamaindex_driver.py` | ZOMBIE | no `from app.drivers` imports in live chain. |
| 5 | Reranker driver (monolith) | `app/drivers/reranker_driver.py` | ZOMBIE | same as 4. Driver registered only via `MCPIntegrations`, which is dormant. |
| 6 | DSPy (orchestrator side) | `microservices/orchestrator_service/.../graph/{main,search,supervisor}.py` | DORMANT | real code, gated behind orchestrator-service that doesn't start by default. |
| 7 | DSPy query refiner | `microservices/research_agent/src/search_engine/query_refiner.py` | DORMANT | gated behind dormant `research-agent:8007`. |
| 8 | Reranker (microservice) | `microservices/research_agent/src/search_engine/{reranker,strategies,hybrid,llama_retriever}.py` | DORMANT | gated behind dormant `research-agent:8007`. |
| 9 | KAgent mesh | `app/services/kagent/{interface,registry,adapters}.py` | ZOMBIE | DI-registered at `app/core/di.py:145` but the only consumer (`workflow.py`) is itself ZOMBIE. |
| 10 | KAgent driver | `app/drivers/kagent_driver.py` | ZOMBIE | not imported by any live entrypoint. |
| 11 | MCP server / integrations | `app/services/mcp/{server,integrations,tools,resources,protocols}.py` | DORMANT | zero imports in `app/main.py`, `app/kernel.py`, `app/api/`. Lazy-imported only by side-path agents (`socratic_tutor`, `admin` agent module, `collaboration/session`, `core/prompts`) which the live chat router does not touch. |
| 12 | Integration micro-kernel | `app/core/integration_kernel/runtime.py` | ZOMBIE | singleton designed but never instantiated from live startup. |
| 13 | Unified Observability | `app/telemetry/unified_observability.py` | ACTIVE | `app/kernel.py:58,208` startup; `app/middleware/fastapi_observability.py` + `app/middleware/observability/observability_middleware.py` on every HTTP request. WS frames NOT traced (ISS-005). |
| 14 | Orchestrator HTTP client | `app/infrastructure/clients/orchestrator_client.py:chat_with_agent` | ACTIVE | sole entrypoint called by `customer_chat.py:422` and `admin.py:490`. Wraps the entire fallback chain. Does not require URL to function — falls through to local engines on `ConnectError`. |
| 15 | Orchestrator microservice (HTTP target) | `microservices/orchestrator_service` | DORMANT | requires `$ORCHESTRATOR_SERVICE_URL` set AND `docker compose -f docker-compose.yml up -d`. Default devcontainer satisfies neither. |
| 16 | All other microservices | `microservices/{planning,memory,user,research,reasoning,auditor,conversation,api_gateway,observability}_*` | DORMANT | not started by `.devcontainer/docker-compose.host.yml`. |

---

## Live execution paths (only these are real)

### Customer chat — `/api/chat/ws`
1. `app/api/routers/customer_chat.py:244` — WS endpoint
2. `customer_chat.py:340` — Monolith writes USER message (`save_message`)
3. `customer_chat.py:422` — `OrchestratorClient.chat_with_agent()`
4. `orchestrator_client.py:422` — HTTP attempt → ConnectError (default)
5. fallback chain (in order, each may short-circuit and yield):
   - file-intelligence (`orchestrator_client.py:486`)
   - exercise-retrieval (`orchestrator_client.py:527`)
   - **LangGraph `run_local_graph`** (`orchestrator_client.py:569` → `local_graph.py:227`)
   - general-chat (`orchestrator_client.py:605`)
6. `customer_chat.py:496-546` — assistant write decision (`persisted=True`? skip : fail-safe write)
7. `customer_chat.py:_emit_terminal_frames()` — single terminal frame guarantee

### Admin chat — `/admin/api/chat/ws`
- Identical structure in `app/api/routers/admin.py` (different table: `admin_messages`).

### Everything else
- All HTTP requests pass through ObservabilityMiddleware → traces are recorded.
- WebSocket frames are NOT traced (ISS-005 — known gap).

---

## Architectural verdict

**Q: Does the project use the full agentic capability stack it advertises?**

**A: NO.** In default runtime:
- Only `local_graph.py` (2 nodes) + 4 simple fallback functions in `OrchestratorClient` actually serve chat traffic.
- The advertised multi-agent graph (super_reasoner, planner, researcher, writer, procedural_auditor, reviewer) never runs in production — it's only invoked by `tests/verify_graph_manual.py`.
- LlamaIndex, DSPy, KAgent mesh, MCP server, reranker, and the integration kernel are all unreachable from the live chat path.
- The "control plane" described in `ARCHITECTURE.md` (orchestrator-service + api-gateway) is dormant scaffolding.

**Project = ~10% live, ~90% scaffolding/dead-code in default Codespaces deployment.**

The live 10%: FastAPI app + ObservabilityMiddleware + auth + customer/admin chat router + OrchestratorClient fallback chain + `local_graph.py` + database persistence layer.

---

## Rules for future sessions
1. Never claim a capability is ACTIVE without proof in this table.
2. Adding a feature that depends on a ZOMBIE/DORMANT layer requires a wiring change first — and a status update here.
3. If you change the fallback order in `orchestrator_client.py` or pre-warm in `kernel.py`, update this file in the same PR.
4. Do not delete a ZOMBIE on sight — first decide whether it's planned scaffolding (keep + mark DORMANT) or genuinely abandoned (delete with ADR).
5. Truth-table updates require: file:line evidence + a 1–3 line snippet + import path + call-chain trace.


## Strategic note — learning path vs general chat
- Current runtime can classify intent in the local graph supervisor, but the advanced educational stack (multi-agent + deep retrieval/reranking orchestration) remains mostly ZOMBIE/DORMANT by default environment.
- Therefore, educational-path quality currently depends heavily on the fallback local graph and available external model quality, not on the full intended microservice mesh.
