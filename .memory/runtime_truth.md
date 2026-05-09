# Runtime Truth Lock
> Last updated: **2026-05-09** | Full live runtime investigation (Ona agent — second pass with real DB + OpenRouter + WebSocket + all components).
> Authority: this file overrides any contradictory aspirational doc in `docs/` or root markdown.

## Golden rule
A capability counts as real ONLY when proven by **all three** of:
1. **import** — the module is imported by code reachable from `app/main.py`.
2. **call chain** — there is a live caller that flows from a router/middleware/startup hook.
3. **runtime evidence** — the code actually executes on the production path (logs, traces, DB writes).

Missing any of the three → DORMANT, ZOMBIE, or UNKNOWN. Not ACTIVE.

## Status legend
| Status | Meaning |
|---|---|
| `ACTIVE` | All three present: import + call chain + runtime evidence. |
| `ACTIVE (no-op without ENV_VAR)` | Import + call chain present, but runtime effect absent when env var unset/invalid. |
| `CONDITIONAL` | Requires external config to function. Process existing ≠ health. |
| `PARTIAL` | On a live chain but only via fallback / conditional / non-default branch. |
| `PARTIAL (loaded-not-invoked)` | Imported and instantiated on live path, but work methods never called for a real turn. |
| `DORMANT` | Code real, gated behind external service not started by default. |
| `ZOMBIE` | Exists with no live call chain from any production entrypoint. |
| `UNKNOWN` | Insufficient evidence. |

---

## Infrastructure (verified live 2026-05-09 — second pass)

| Service | Port | Status | Live Evidence |
|---|---|---|---|
| **Next.js** | **3000** | **ACTIVE** | `supervisor.sh:256` passes `--port 3000` overriding `package.json --port 5000`. Process: `node next dev --port 5000 --port 3000` — last flag wins. HTML confirmed. |
| **FastAPI** | **8000** | **ACTIVE** | `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`. 62 routes. Requires `DATABASE_URL`. |
| **Grafana** | **3001** | **ACTIVE** | `grafana.ini` says `http_port=3000` but provisioning CLI overrides to 3001. `GET /api/health → {"database":"ok"}`. |
| **Prometheus** | **9090** | **ACTIVE** | `GET /-/healthy → "Prometheus Server is Healthy."` |
| **Redis** | **6379** | **ACTIVE (process only)** | `ping() → True`. `REDIS_URL` not set → app uses `InMemoryCache`. Model: `BAAI/bge-reranker-base` cached at `~/.cache/huggingface/hub/`. |
| **PostgreSQL** (Supabase) | **6543** | **ACTIVE** | PostgreSQL 17.6. Read latency ~2ms. 19 users, 2098 customer_messages, 3038 admin_messages, 79 missions. INSERT+DELETE confirmed. |
| **OpenRouter** | external | **ACTIVE** | 367 models. Primary: `nvidia/nemotron-3-super-120b-a12b:free`. Live WS response confirmed. |
| **Microservices** | various | **DORMANT** | `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` — Docker DNS, not running. |

---

## Capability table (verified live 2026-05-09 — second pass, all components tested)

| # | Component | File(s) | Status | Live Evidence |
|---|---|---|---|---|
| 1 | **WebSocket customer chat** | `app/api/routers/customer_chat.py:244` | **ACTIVE** | Live test: `subprotocols=['jwt', TOKEN]` → `conversation_init` (conv_id=394) → `assistant_delta` (391 chars) → `assistant_final`. Time: 6.79s. Event format: `{"type":"...", "payload":{"content":"...", "conversation_id":394}}`. |
| 2 | **WebSocket admin chat** | `app/api/routers/admin.py` | **ACTIVE** | Live test: admin token → `conversation_init` (conv_id=391) → streaming. Timeout at 20s (model slow), but connection and init confirmed. |
| 3 | **WS auth** | `app/api/routers/ws_auth.py:extract_websocket_auth` | **ACTIVE** | `subprotocol='jwt'` selected. Token extracted from subprotocols list. |
| 4 | **WS payload format** | `app/api/routers/customer_chat.py:300` | **ACTIVE** | Correct key is `question` (not `content`/`message`). `{"question": "..."}` → works. `{"type":"message","content":"..."}` → `"Question is required."` error. |
| 5 | **LangGraph local engine** | `app/services/chat/local_graph.py` | **PARTIAL** | Fallback tier 3. Live: `run_local_graph('ما هو تكامل x^2')` → 391-char LaTeX response in 10.13s. Nodes: `['__start__', 'supervisor', 'chat']`. Intent classification: educational✓ general✓ chat✗(misclassifies 'مرحبا' as 'general'). |
| 6 | **OrchestratorClient fallback chain** | `app/infrastructure/clients/orchestrator_client.py` | **ACTIVE** | `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` → ConnectError → fallback. `_build_local_file_count_response`: ACTIVE (499ms, returns "22064 ملف"). `_build_local_retrieval_response`: returns None (no BAC content). `_build_local_graph_response`: ACTIVE (10s, full response). `_build_local_general_chat_response`: ACTIVE. |
| 7 | **FastAPI app + kernel** | `app/main.py`, `app/kernel.py:RealityKernel` | **ACTIVE** | `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`. 62 routes. `RealityKernel` instantiated at `app/main.py:22`. |
| 8 | **DB via SQLAlchemy** | `app/core/database.py:async_session_factory` | **ACTIVE** | `SELECT 1` via `async_session_factory` → 1. Read latency ~2ms. INSERT+DELETE confirmed. PgBouncer transaction mode — `statement_cache_size=0` required. |
| 9 | **AI Gateway (SimpleAIClient)** | `app/core/gateway/simple_client.py` | **ACTIVE** | `get_ai_client()` → `SimpleAIClient`. Primary: `nvidia/nemotron-3-super-120b-a12b:free`. 5 fallbacks. Live call confirmed via WS. |
| 10 | **Cache (InMemoryCache)** | `app/caching/factory.py:get_cache()` | **ACTIVE (InMemoryCache)** | `REDIS_URL` not set → `InMemoryCache`. `set/get/delete` all confirmed. Redis process on 6379 runs but unused. |
| 11 | **Redis process** | `redis://localhost:6379` | **ACTIVE (process, unused by app)** | `ping() → True`. SET/GET confirmed. App does not use it (`REDIS_URL` unset). |
| 12 | **UnifiedObservabilityService** | `app/telemetry/unified_observability.py` | **ACTIVE** | `app/kernel.py:58,208`. Every HTTP request traced. WS frames NOT traced per-frame (ISS-005). |
| 13 | **WS path observer** | `app/telemetry/path_observer.py` | **ACTIVE** | `open_ws_turn`, `close_ws_turn`, `mark_fallback_used` called on live WS path. |
| 14 | **OTEL SDK** | `app/telemetry/otel_setup.py` | **ACTIVE (no-op)** | `OTEL_EXPORTER_OTLP_ENDPOINT=http` (invalid URL) → no spans exported. Code runs, effect absent. |
| 15 | **DSPy** | `dspy` package | **ACTIVE (package, DORMANT in app)** | `dspy==3.2.1` installed. `dspy.LM('openrouter/nvidia/...')` + `dspy.Predict` work. BUT: only used in `microservices/orchestrator_service` and `microservices/research_agent` — both DORMANT. No live call chain from `app/`. |
| 16 | **LlamaIndex** | `llama_index.core==0.14.13` | **ACTIVE (package, ZOMBIE in app)** | Installed. `VectorStoreIndex` works with HuggingFace embeddings (`BAAI/bge-small-en-v1.5`). Retrieval score 0.8152 confirmed. BUT: requires `OPENAI_API_KEY` for default embeddings (fails without it). App driver `app/drivers/llamaindex_driver.py` exports `LlamaIndexDriver(RetrievalEngine)` — no live consumer. |
| 17 | **Reranker (CrossEncoder)** | `BAAI/bge-reranker-base` | **ACTIVE (package, DORMANT in app)** | Model cached at `~/.cache/huggingface/hub/models--BAAI--bge-reranker-base`. `CrossEncoder` loads in <1s from cache. Reranking works. BUT: only used in `microservices/research_agent/src/search_engine/reranker.py` — DORMANT. `app/drivers/reranker_driver.py` has no `RerankDriver` export (import fails). |
| 18 | **KAgent mesh** | `app/services/kagent/interface.py:KagentMesh` | **ZOMBIE (instantiable, security-blocked)** | `KagentMesh()` instantiates. `execute_action(AgentRequest(...))` → `"⛔ Security Alert: Invalid token"` → `status='error'`. Methods: `execute_action`, `register_service`. No live consumer from `app/api/`. |
| 19 | **MCP server** | `app/services/mcp/server.py:MCPServer` | **DORMANT (instantiable, not wired)** | `MCPServer()` instantiates. `initialize()` → OK. `get_tools_for_llm()` → 8 tools. `get_project_metrics()` → `{"success":..., "result":...}`. `call_tool('get_project_metrics', {})` → works. BUT: zero imports from `app/api/`, `app/main.py`, `app/kernel.py`. Not on live chat path. |
| 20 | **MCP tools (8 tools)** | `app/services/mcp/server.py` | **DORMANT** | `analyze_file`, `call_tool`, `get_complete_project_knowledge`, `get_project_metrics`, `get_resource`, `get_tools_for_llm`, `initialize`, `list_resources`. All callable but not wired to live path. |
| 21 | **TLM (Trustworthy LM)** | — | **NOT INSTALLED** | `cleanlab` not installed. No `tlm` package. Zero references to TLM in `app/`. Not part of this codebase. |
| 22 | **Multi-agent workflow** | `app/services/chat/graph/workflow.py` | **ZOMBIE (compilable, KAgent-blocked)** | `create_multi_agent_graph(ai_client, tools=[])` → `CompiledStateGraph`. Nodes: `['__start__', 'planner', 'researcher', 'writer', 'super_reasoner', 'procedural_auditor', 'reviewer', 'supervisor']`. Invocation → `"⛔ Security Alert: Invalid token from planner_node"` → KAgent security blocks all nodes. Only consumer: `tests/verify_graph_manual.py`. |
| 23 | **Multi-agent nodes** | `app/services/chat/graph/nodes/` | **ZOMBIE** | `ReviewerNode` importable. `SuperReasonerNode`, `PlannerNode`, `ResearcherNode`, `WriterNode` — class names differ from expected (import fails with wrong name). All blocked by KAgent security in practice. |
| 24 | **Orchestrator microservice StateGraph** | `microservices/orchestrator_service/src/services/overmind/graph/main.py` | **DORMANT** | 13-node graph: `supervisor, query_rewriter, query_analyzer, retriever, reranker, web_fallback, admin_agent, tool_executor, chat_fallback, general_knowledge, synthesizer, validator`. `create_unified_graph()` compiles without error. `graph.ainvoke(state)` with `OPENROUTER_API_KEY` → valid Arabic response in ~10s. NOT on live call chain. Requires `docker compose -f docker-compose.yml up -d`. `cognitive_engine.memorize` bug on primary model (non-blocking). `FlagEmbeddingReranker` not installed → simple sort fallback. Postgres checkpointer absent → compiled without checkpointer. |
| 24a | **Tavily (WebSearchFallbackNode)** | `microservices/orchestrator_service/src/services/overmind/graph/search.py:WebSearchFallbackNode` | **DORMANT** | `tavily-python==0.7.24` installed. `TavilyClient` importable. Live search confirmed: `TavilyClient(api_key='tvly-dev-...').search('بكالوريا جزائر رياضيات')` → 2 results. Key must start with `tvly-`. MCP URL format auto-sanitized. `TAVILY_API_KEY` absent from `docker-compose.yml`. Silent skip when key missing (`used_web=False`, no exception). Calls `research_client.deep_research()` → HTTP to `research-agent:8007` → ConnectError (DORMANT). |
| 24b | **SuperSearchOrchestrator** | `microservices/research_agent/src/search_engine/super_search.py` | **DORMANT** | Uses `TavilyClient` when `TAVILY_API_KEY` present (key format `tvly-*`). Falls back to `DuckDuckGoSearchAPIWrapper` when absent — but `ddgs` package NOT installed → `ImportError` on init. `SimpleWebScraper` (httpx + BeautifulSoup) is scraper fallback. Not running. |
| 25 | **DSPy in orchestrator** | `microservices/orchestrator_service/src/services/overmind/graph/` | **DORMANT** | `IntentClassifier` (4-intent: educational/general_knowledge/admin/chat), `QueryRewriterSignature`, `ChatFallbackSignature`, `AnalyzeQuery`, `EducationalSynthesizer` all use DSPy. Configured via `_configure_dspy()` using `OPENROUTER_API_KEY`. Importable. Not running. |
| 26 | **Research agent reranker** | `microservices/research_agent/src/search_engine/reranker.py` | **DORMANT** | Importable (without sys.path conflict). Uses `BAAI/bge-reranker-base` (cached). Not running. |
| 27 | **LlamaIndex driver (app)** | `app/drivers/llamaindex_driver.py` | **ZOMBIE** | Exports `LlamaIndexDriver(RetrievalEngine)`. No `LlamaIndexRetrievalEngine` (wrong import name). No live consumer. |
| 28 | **Reranker driver (app)** | `app/drivers/reranker_driver.py` | **ZOMBIE** | No `RerankDriver` export (import fails). No live consumer. |
| 29 | **IntegrationKernel** | `app/core/integration_kernel/runtime.py` | **ZOMBIE** | Only instantiated from `app/services/mcp/integrations.py:49`. MCPIntegrations has zero live consumers. ≠ `RealityKernel` (which IS active). |
| 30 | **CustomerChatBoundaryService** | `app/services/boundaries/customer_chat_boundary_service.py` | **PARTIAL (split)** | Persistence methods ACTIVE (called by live router). `stream_chat`/`orchestrate_chat_stream` NEVER called from `app/api/`. |
| 31 | **ChatOrchestrator + streamers** | `app/services/chat/orchestrator.py`, `app/services/customer/chat_streamer.py` | **PARTIAL (loaded-not-invoked)** | Instantiated at boundary service `__init__`. `stream_response()` never called from `app/api/`. |
| 32 | **All other microservices** | `microservices/{planning,memory,user,research,reasoning,auditor,conversation,api_gateway,observability}_*` | **DORMANT** | Not started by `.devcontainer/docker-compose.host.yml`. |
| 33 | **Grafana + Prometheus** | native binaries | **ACTIVE** | Grafana port 3001 (`/api/health → {"database":"ok"}`). Prometheus port 9090 (`/-/healthy → healthy`). |
| 34 | **Runtime truth CI gate** | `scripts/runtime_truth.py` | **ACTIVE** | Enforced in `.github/workflows/runtime_truth.yml`. Blocking on PR/main push. |

---

## WS event protocol (confirmed live 2026-05-09)

```
Client → Server: {"question": "..."}          ← key is 'question', NOT 'content'
Server → Client: {"type": "conversation_init", "payload": {"conversation_id": 394, "request_id": "..."}}
Server → Client: {"type": "assistant_delta",   "payload": {"content": "...", "conversation_id": 394, "request_id": "..."}}
Server → Client: {"type": "assistant_final",   "payload": {"content": "", "conversation_id": 394, "request_id": "..."}}
```
- Auth: `subprotocols=['jwt', TOKEN]` — server selects `'jwt'` as subprotocol.
- `persisted` event: only emitted when orchestrator microservice is active and confirms DB write.
- Typical latency: 6–18s (OpenRouter free tier).

## Fallback chain timing (confirmed live 2026-05-09)

| Tier | Method | Result | Latency |
|---|---|---|---|
| 1 | `_build_local_file_count_response` | Returns file count string | ~499ms |
| 2 | `_build_local_retrieval_response` | Returns `None` (no BAC content match) | ~0ms |
| 3 | `_build_local_graph_response` | **PRIMARY** — full LangGraph response | ~10s |
| 4 | `_build_local_general_chat_response` | Fallback general response | ~10s |

## Intent classification bugs (confirmed live 2026-05-09)

| Input | Expected | Got | Bug? |
|---|---|---|---|
| `'شرح لي قانون نيوتن الثاني'` | educational | educational | ✓ |
| `'مرحبا كيف حالك'` | chat | general | ✗ BUG — Arabic greeting misclassified |
| `'hello'` | general | chat | ✗ BUG — English greeting misclassified |
| `'ما هو الذكاء الاصطناعي'` | general | general | ✓ |
| `'حل لي هذه المسألة في الرياضيات'` | educational | educational | ✓ |

## Architectural verdict (2026-05-09 — third pass)

**Live stack (what actually runs on every chat turn):**
1. FastAPI `customer_chat.py` WS endpoint
2. `extract_websocket_auth` → JWT validation
3. `save_message(USER)` → PostgreSQL
4. `OrchestratorClient.chat_with_agent()` → ConnectError → fallback chain
5. `_build_local_graph_response()` → `run_local_graph()` → LangGraph 2-node graph → OpenRouter API
6. `_emit_terminal_frames()` → `assistant_final`
7. `save_message(ASSISTANT)` → PostgreSQL (fail-safe write, `persisted=False`)

**What is installed but NOT wired to live path:**
- DSPy 3.2.1 ✓ installed, ✗ not on live path (only in dormant orchestrator microservice)
- LlamaIndex 0.14.13 ✓ installed, ✗ requires OpenAI key for default embeddings, ✗ not on live path
- CrossEncoder BAAI/bge-reranker-base ✓ cached, ✗ not on live path
- KAgent ✓ instantiable, ✗ security-blocked (invalid token), ✗ not on live path
- MCP ✓ 8 tools callable, ✗ not on live path
- Multi-agent workflow ✓ compiles (8 nodes), ✗ KAgent security blocks all nodes, ✗ not on live path
- TLM ✗ NOT INSTALLED, ✗ not referenced in codebase
- **Tavily** ✓ `tavily-python==0.7.24` installed, ✓ live search confirmed, ✗ only called from DORMANT `WebSearchFallbackNode`, ✗ `TAVILY_API_KEY` absent from `docker-compose.yml`
- **Advanced orchestrator graph (13 nodes)** ✓ compiles, ✓ runs in isolation, ✗ NOT on live call chain, ✗ requires full Docker Compose stack
- **DuckDuckGo fallback** ✗ `ddgs` package NOT installed → `ImportError` if Tavily absent and orchestrator running

**Project = ~15% live, ~85% scaffolding in default Codespaces.**

**Advanced stack revival requires (in order):**
1. Add `TAVILY_API_KEY` to `docker-compose.yml` (orchestrator-service + research-agent)
2. `docker compose -f docker-compose.yml up -d` (orchestrator-service, research-agent, postgres-orchestrator, redis-orchestrator)
3. Set `ORCHESTRATOR_SERVICE_URL=http://localhost:8006` in monolith (or use Docker network)
4. Verify orchestrator warmup passes (admin tool invocation in lifespan)
5. Update this file: promote orchestrator StateGraph and Tavily to ACTIVE

---

## Rules for future sessions
1. WS payload key is `question`, not `content` or `message`.
2. WS auth: `subprotocols=['jwt', TOKEN]`.
3. `OTEL_EXPORTER_OTLP_ENDPOINT=http` is invalid — OTEL is a no-op.
4. `REDIS_URL` not set — cache is InMemoryCache.
5. `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` — Docker DNS, always ConnectError in default Codespaces.
6. KAgent security blocks all calls without a valid internal token — multi-agent graph cannot run.
7. LlamaIndex requires `OPENAI_API_KEY` for default embeddings — use HuggingFace explicitly.
8. TLM is NOT part of this codebase.
9. Grafana is on port 3001 (not 3000).
10. FastAPI version: `v4.1-root`.
11. **Tavily**: `tavily-python==0.7.24` installed, `TavilyClient` importable, live search confirmed. Key must start with `tvly-`. NOT on live call chain — only in DORMANT `WebSearchFallbackNode`. `TAVILY_API_KEY` absent from `docker-compose.yml`.
12. **Advanced orchestrator graph**: 13 nodes, compiles and runs in isolation with `OPENROUTER_API_KEY`. NOT on live call chain. `cognitive_engine.memorize` bug on primary model (non-blocking). `FlagEmbeddingReranker` not installed. Postgres checkpointer absent.
13. **DuckDuckGo fallback broken**: `ddgs` package not installed. If Tavily absent and orchestrator running, `SuperSearchOrchestrator` raises `ImportError`.
14. **`TAVILY_API_KEY` absent from `docker-compose.yml`**: must be added to both `orchestrator-service` and `research-agent` environment sections before the full stack can use web search.
15. The advanced orchestrator graph uses a **4-intent taxonomy** (educational/general_knowledge/admin/chat) — different from the local `local_graph.py` 3-intent taxonomy (educational/general/chat). Do not conflate them.
16. **The monolith calls `/agent/chat`, NOT `/api/chat/messages`**: `ChatRoutingPolicy.candidate_urls()` returns `[f"{base}/agent/chat"]`. The `/agent/chat` endpoint routes to `OrchestratorAgent.run()` (intent-based dispatch, 13-intent taxonomy) — NOT the 13-node StateGraph. The StateGraph is only invoked by `/api/chat/messages` and `/api/chat/ws` on the orchestrator service itself.
17. **thread_id format mismatch**: Local fallback graph uses `str(conversation_id)` (e.g. `"394"`). Orchestrator StateGraph uses `f"u{user_id}:c{conversation_id}"` (e.g. `"u7:c394"`). These namespaces are incompatible — no shared checkpoint state between stacks (ISS-019).
18. **AdminAgentNode is stateless**: Inside the 13-node StateGraph, `AdminAgentNode` invokes the admin sub-graph with `thread_id=str(uuid.uuid4())` — a fresh UUID per invocation. No checkpoint continuity even when the parent graph has a Postgres checkpointer.
19. **Truth table lock is stale**: `.runtime/truth_table.lock.json` was generated 2026-05-08T09:54:43Z on branch `jules-5513332666705839536-7e7df21b`. Missing entries: orchestrator StateGraph, Tavily, DSPy, research_agent, OrchestratorAgent. Run `python scripts/runtime_truth.py --update` to regenerate.
20. **Full advanced LangGraph forensic details**: `.memory/langgraph_advanced_forensics.md` (created 2026-05-09, fourth pass).
