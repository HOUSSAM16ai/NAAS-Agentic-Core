# Runtime Truth Lock
> Last updated: 2026-05-06 | Re-verified on branch: `claude/autonomous-runtime-observability-pjzY9` (fourth pass — wires runtime observability OS).
> Authority: this file overrides any contradictory aspirational doc in `docs/` or root markdown.
> **Re-verification (2026-05-06, branch `claude/architecture-rescue-diagnostic-wUfbE`): 23 of 25 prior rows CONFIRMED verbatim, 2 corrections applied (rows 12 + 21), 1 PARTIAL promotion ("loaded-not-invoked" tier added — rows 21, 26, 27). No DORMANT/ZOMBIE promoted to ACTIVE. CI gap newly tracked as ISS-025.**
> **Update (2026-05-06, branch `claude/autonomous-runtime-observability-pjzY9`): two new rows — 28 (WS path observer, ACTIVE) and 29 (runtime truth generator, ACTIVE & CI-enforced). New CI gate `runtime-truth-drift-check` blocks any future ZOMBIE-to-live-anchor importer drift. Static enforcement of the closing rule.**

## Golden rule
A capability counts as real ONLY when proven by **all three** of:
1. **import** — the module is imported by code reachable from `app/main.py`.
2. **call chain** — there is a live caller that flows from a router/middleware/startup hook.
3. **runtime evidence** — the code actually executes on the production path (logs, traces, DB writes).

Missing any of the three → DORMANT, ZOMBIE, or UNKNOWN. Not ACTIVE.

## Status legend
- `ACTIVE` — all three present (import + call chain + runtime evidence).
- `ACTIVE (no-op without ENV_VAR)` — import + call chain present, but runtime effect is absent when a required environment variable is unset. The code executes but produces no observable output. Do not treat as fully ACTIVE. Example: `otel_setup.py` without `OTEL_EXPORTER_OTLP_ENDPOINT`.
- `CONDITIONAL` — the component itself may start, but requires external configuration (e.g., `DATABASE_URL`) to function. A process existing is not proof of health.
- `PARTIAL` — on a live chain but only via fallback / conditional / non-default branch.
- `PARTIAL (loaded-not-invoked)` — module imported and class instantiated on the live path, but the methods that perform actual work are never called for a real user turn. Stronger than ZOMBIE (it executes `__init__`) but weaker than ACTIVE (it produces no observable behavior).
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
| 12 | Integration micro-kernel (`IntegrationKernel`, NOT `RealityKernel`) | `app/core/integration_kernel/runtime.py:13` | ZOMBIE | actual class is `IntegrationKernel`. Only instantiated at `app/services/mcp/integrations.py:49` (`self.kernel = IntegrationKernel()`); MCPIntegrations has zero live consumers. **Naming clarification (2026-05-06)**: `RealityKernel` is a different class at `app/kernel.py:103`, instantiated at `app/main.py:22` (`_kernel = RealityKernel(...)`) and `app/main.py:49` — that one IS ACTIVE and is implicitly covered by the live FastAPI bootstrap (do not conflate). |
| 13 | Unified Observability | `app/telemetry/unified_observability.py` | ACTIVE | `app/kernel.py:58,208` startup; `app/middleware/fastapi_observability.py` + `app/middleware/observability/observability_middleware.py` on every HTTP request. WS frames NOT traced (ISS-005). |
| 14 | Orchestrator HTTP client | `app/infrastructure/clients/orchestrator_client.py:chat_with_agent` | ACTIVE | sole entrypoint called by `customer_chat.py:422` and `admin.py:490`. Wraps the entire fallback chain. Does not require URL to function — falls through to local engines on `ConnectError`. |
| 15 | Orchestrator microservice (HTTP target) | `microservices/orchestrator_service` | DORMANT | requires `$ORCHESTRATOR_SERVICE_URL` set AND `docker compose -f docker-compose.yml up -d`. Default devcontainer satisfies neither. |
| 16 | All other microservices | `microservices/{planning,memory,user,research,reasoning,auditor,conversation,api_gateway,observability}_*` | DORMANT | not started by `.devcontainer/docker-compose.host.yml`. |
| 17 | Chat agents orchestrator (parallel "MultiAgent" path) | `app/services/chat/agents/orchestrator.py:11,83,647` | ZOMBIE | imports `EducationCouncil`; nothing imports `agents.orchestrator` from `app/api/`, `app/main.py`, `app/kernel.py`, `local_graph.py`, or `orchestrator_client.py`. Sits parallel to the live chat path. |
| 18 | EducationCouncil | `app/services/chat/agents/education_council.py:96` | ZOMBIE | only consumer is row 17 (also ZOMBIE). |
| 19 | Graph components subdir | `app/services/chat/graph/components/{context_composer,intent_detector,prompt_strategist}.py` | ZOMBIE | only referenced from `graph/workflow.py` (already ZOMBIE — row 2). |
| 20 | Graph nodes/supervisor | `app/services/chat/graph/nodes/supervisor.py` | ZOMBIE | sibling of dead nodes in row 2; not reachable. |
| 21 | Top-level chat orchestration helpers | `app/services/chat/{dispatcher,intent_detector,intent_registry,tool_router,tool_access,education_policy_gate,orchestration_rollout}.py` | PARTIAL (loaded-not-invoked) | **Correction 2026-05-06 (third audit)**: `customer_chat_boundary_service.py:22-23` imports `IntentDetector` + `ToolRouter`; lines 40-41 instantiate them at `__init__`. The boundary service IS instantiated by the live router (`customer_chat.py:329, 522`). However, `intent_detector.detect()` (line 131) and `tool_router.authorize_intent()` (line 150) only execute inside `orchestrate_chat_stream` / `stream_chat`, which are **never called** by `app/api/` (grep returns zero hits). So: code-loaded + class-instantiated on live path, but functionally never invoked for an actual WS turn. Not pure ZOMBIE; not ACTIVE either. |
| 22 | Side-path chat agents | `app/services/chat/agents/{admin,curriculum,socratic_tutor,testing_agent,refactor,analytics,...}.py` | ZOMBIE | not invoked by live customer/admin chat WS routers. |
| 23 | Frontend WS client | `frontend/app/hooks/useRealtimeConnection.js:56` (consumer: `useAgentSocket.js:180`) | ACTIVE | sole `new WebSocket(...)` factory; uses subprotocol `["jwt", token]`. Connects to `/api/chat/ws` and `/admin/api/chat/ws` proxied via `frontend/next.config.js`. |
| 24 | Orchestrator microservice DB writers | `microservices/orchestrator_service/src/api/routes.py:1211,1216,1361,1366` | DORMANT | real INSERTs into `customer_messages` / `admin_messages` exist; the microservice just doesn't run by default. When awoken, D-006 (`compatibility_facade=True` + `persisted: true` echo) is the only thing preventing dual-write — load-bearing. |
| 25 | Dual Redis design | `docker-compose.yml` services `redis:6379` and `redis-orchestrator:6380` | DORMANT | only `redis-orchestrator` is wired to the orchestrator microservice; in default devcontainer neither runs and `app/caching/factory.py:71` falls back to `InMemoryCache(...)`. |
| 26 | `CustomerChatBoundaryService` / `AdminChatBoundaryService` | `app/services/boundaries/customer_chat_boundary_service.py:30`, `admin_chat_boundary_service.py:21` | PARTIAL (split) | Persistence methods (`get_or_create_conversation`, `save_message`, `get_chat_history`, `list_user_conversations`, `get_latest_conversation_details`, `get_conversation_details`) are **ACTIVE** — called by live router (`customer_chat.py:330, 340, 345, 523, 573, 588, 604`). Streaming methods (`stream_chat:95-110`, `orchestrate_chat_stream:112-260`) are **never invoked** from `app/api/` — they instantiate `intent_detector`, `tool_router`, `streamer` but the actual streaming path goes via `OrchestratorClient.chat_with_agent` (`customer_chat.py:422`, `admin.py:490`) instead. |
| 27 | `ChatOrchestrator` + chat streamers | `app/services/chat/orchestrator.py`, `app/services/customer/chat_streamer.py`, `app/services/admin/chat_streamer.py` | PARTIAL (loaded-not-invoked) | `CustomerChatStreamer` instantiated at `customer_chat_boundary_service.py:38`; `AdminChatStreamer` at `admin_chat_boundary_service.py:49`. `streamer.stream_response(...)` is called only from inside `orchestrate_chat_stream` (boundary service line 106 / 132) — and that method has zero callers in `app/api/`. So the streamer modules load and instantiate, but never reach `stream_response`. `ChatOrchestrator` is consumed only by these two streamer modules, transitively unreachable. |
| 28 | **WS path observer** (`WsTurnSpan`, `open_ws_turn`, `close_ws_turn`, `mark_fallback_used`) | `app/telemetry/path_observer.py` | **ACTIVE** | Imported by `app/api/routers/customer_chat.py:31` and `app/api/routers/admin.py:39`. `open_ws_turn(...)` is called once per WS turn (`customer_chat.py` after question validation; `admin.py` likewise). `close_ws_turn(...)` is called once per turn from the per-turn `finally:` next to `_emit_terminal_frames`. `mark_fallback_used(...)` is invoked from `orchestrator_client.py:170, 196` whenever the local fallback chain runs. Emits `ws.chat.turn.duration_seconds`, `ws.chat.terminal_events.total`, `ws.chat.fallback.total`. Closes the per-turn slice of ISS-005 (the WS chat turn now has a top-level span); per-frame WS spans remain TODO. |
| 29 | **Runtime truth generator** | `scripts/runtime_truth.py` | **ACTIVE** (CI-enforced) | Invoked by `.devcontainer/snapshot_runtime.sh` at every Codespace attach (informational, non-blocking) AND by `.github/workflows/runtime_truth.yml:runtime-truth-drift-check` (blocking on PR/main push). Compares regenerated `.runtime/truth_table.json` against committed `.runtime/truth_table.lock.json`. New importer of any tracked ZOMBIE/DORMANT module from a live anchor → CI fails until lock is updated AND review accepts the promotion. |
| 30 | **OpenTelemetry SDK bootstrap** | `app/telemetry/otel_setup.py` | **ACTIVE (no-op without `OTEL_EXPORTER_OTLP_ENDPOINT`)** | Imported and called by `app/kernel.py:157` (`setup_otel`) and `app/kernel.py:184` (`instrument_fastapi_app`). When `OTEL_EXPORTER_OTLP_ENDPOINT` is unset (default Codespaces), both functions execute but produce no observable output — no spans exported, no traces collected. This is the **ACTIVE (no-op)** tier: import + call chain present, runtime effect absent due to missing configuration. Do not classify as fully ACTIVE. Confirmed 2026-05-09 by live inspection. |
| 31 | **Grafana + Prometheus native binaries** | `/opt/grafana/bin/grafana-server`, `/opt/prometheus/prometheus` | **ACTIVE (infrastructure)** | Launched by `supervisor.sh:launch_mission_control()` (Step 4C) as background processes. Binaries baked into the Docker image at `/opt/grafana` and `/opt/prometheus`. Confirmed running 2026-05-09: `pgrep` + `GET /api/health → {"database":"ok"}` + `Prometheus Server is Healthy.` Prometheus scrapes FastAPI at `:8000/api/v1/observability/prometheus` — shows `cogniforge-fastapi=0` when FastAPI is down. **Note**: these are infrastructure processes, not FastAPI components. They run independently of the application. |
| 32 | **FastAPI application** | `app/main.py` | **CONDITIONAL** | Requires `DATABASE_URL` or `APP_DATABASE_URL` to start. Without it, uvicorn spawns but crashes immediately at `AppSettings()` validation (`pydantic_core.ValidationError: DATABASE_URL is missing`). Confirmed 2026-05-09: uvicorn PID present, `ss -tlnp | grep 8000` empty, `.superhuman_bootstrap.log` shows validation error. A running uvicorn process is NOT proof of a healthy server. |

---

## Live execution paths (only these are real)

### Customer chat — `/api/chat/ws`
1. `app/api/routers/customer_chat.py:244` — WS endpoint
2. `customer_chat.py:340` — Monolith writes USER message (`save_message`)
3. `customer_chat.py` — `open_ws_turn(...)` opens `WsTurnSpan` and tags `path_type` (`educational | general_chat | unknown` — `admin` is reserved for the admin endpoint)
4. `customer_chat.py:422` — `OrchestratorClient.chat_with_agent()`
5. `orchestrator_client.py:422` — HTTP attempt → ConnectError (default)
6. fallback chain (in order, each may short-circuit and yield; each calls `mark_fallback_used` so the span's `path_type` is promoted to `fallback`):
   - file-intelligence (`orchestrator_client.py:486`)
   - exercise-retrieval (`orchestrator_client.py:527`)
   - **LangGraph `run_local_graph`** (`orchestrator_client.py:569` → `local_graph.py:227`)
   - general-chat (`orchestrator_client.py:605`)
7. `customer_chat.py:496-546` — assistant write decision (`persisted=True`? skip : fail-safe write)
8. `customer_chat.py:_emit_terminal_frames()` — single terminal frame guarantee
9. `close_ws_turn(...)` — closes the span and emits per-turn metrics

### Admin chat — `/admin/api/chat/ws`
- Identical structure in `app/api/routers/admin.py` (different table: `admin_messages`). `path_type` is always `admin`.

### Everything else
- All HTTP requests pass through ObservabilityMiddleware → traces are recorded.
- WebSocket frames are NOT traced PER FRAME (ISS-005 — partially closed: per-turn `WsTurnSpan` now exists; per-frame remains TODO).

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

---

## Transformation gap (diagnostic only — no execution in this audit)

To move from "transitional/zombie" to "production-grade multi-service":
1. **Wake the mesh** — `docker compose -f docker-compose.yml up -d` + set `ORCHESTRATOR_SERVICE_URL`. Prove `compatibility_facade=True` round-trip writes exactly one row per turn under load. **No code change required for this step** — only infra + env.
2. **Promote ONE agentic layer to ACTIVE** — pick exactly one of (multi-agent workflow, MCP, KAgent, LlamaIndex retriever, reranker, DSPy refiner) and wire it into the live router or into a `local_graph` node. Add a runtime trace assertion. Update this table with the three-part proof. Do NOT promote two layers in one PR.
3. **Per ZOMBIE/DORMANT layer, decide explicitly**: promote (with proof), archive (mark DORMANT and gate behind env), or delete with ADR. No "leave it half-alive."
4. **Close ISS-005 (WS tracing) and ISS-023 (token streaming)** before claiming the chat path is production-grade. Both are blockers for honest observability and UX.
5. **Architecture tests** must enforce truth-table classifications; a CI step should fail if a ZOMBIE acquires an importer in `app/api/` or `app/kernel.py` without a matching truth-table update.

---

## Branch ledger (audits performed)
| Audit date | Branch | Outcome |
|---|---|---|
| 2026-05-05 | `claude/runtime-truth-audit-65iVU` | First truth-table publication (16 rows). |
| 2026-05-06 | `claude/diagnostic-system-architecture-aRSuW` | Re-verification + 9 new ZOMBIE rows (17–25). No promotions. |
| 2026-05-06 | `claude/architecture-rescue-diagnostic-wUfbE` | Third audit. 23/25 rows confirmed. 2 corrections (rows 12 + 21). New `PARTIAL (loaded-not-invoked)` tier introduced (rows 21, 26, 27). CI doc-integrity gap → ISS-025. No promotions. |
| 2026-05-06 | `claude/autonomous-runtime-observability-pjzY9` | Fourth audit. Rows 28–29 added (WS path observer ACTIVE, runtime truth generator ACTIVE+CI-enforced). |
| 2026-05-09 | `docs/architecture-memory-audit-2026-05-09` | Fifth audit (this session). Rows 30–32 added. New `ACTIVE (no-op)` tier formalised. FastAPI startup failure confirmed (no DATABASE_URL). Grafana+Prometheus native binaries confirmed running. Truth table lock drift documented (ISS-032). `context_utils.py.orig` scratch artifact documented (ISS-033). No capability status promotions. |

## What did NOT change in the third audit
- §6.5 persistence rules (D-006) — intact.
- `_emit_terminal_frames` single-emitter rule — intact.
- `local_graph.py` is still the de-facto handler in default devcontainer.
- All 10 microservices still DORMANT in default devcontainer.
- ISS-005 (no WS tracing), ISS-023 (`ainvoke` instead of `astream_events`), ISS-020 (in-memory checkpointer) — all still open.

## What is new in the third audit
- §6.6 row 12 class name corrected (`IntegrationKernel`, not `RealityKernel`).
- `PARTIAL (loaded-not-invoked)` tier for boundary-service-resident helpers.
- `.github/workflows/doc_integrity.yml` (new) gates: CLAUDE.md / `.memory/*` non-empty, no scratch artifacts in repo root, no resurrected dated diagnostics in `docs/` outside `docs/archive/`.
- ISS-025: persistence + terminal-frame + truth-table-sync + frontend-build CI gates remain TODO.
- Markdown-debt inventory captured in `.memory/diagnostic_2026_05_06_rescue.md`. Deletion deferred to an explicit follow-up PR.
