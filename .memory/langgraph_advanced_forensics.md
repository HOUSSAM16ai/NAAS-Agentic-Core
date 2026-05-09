# Advanced LangGraph Forensic Audit — Durable Memory
> Created: **2026-05-09** | Live forensic investigation (Ona agent — fourth pass).
> Authority: this file documents verified runtime truth for the advanced LangGraph stack.
> Do NOT update this file with aspirational claims. Every entry requires evidence.

---

## The Three LangGraph Stacks — Never Conflate

| Stack | Location | Status | Nodes | Invoked by |
|---|---|---|---|---|
| **Local fallback graph** | `app/services/chat/local_graph.py` | **PARTIAL** | 2: `supervisor`, `chat` | `OrchestratorClient._build_local_graph_response()` |
| **Advanced orchestrator StateGraph** | `microservices/orchestrator_service/src/services/overmind/graph/main.py` | **DORMANT** | 13: see topology | `/api/chat/messages` (HTTP) and `/api/chat/ws` (WS) on the orchestrator service — NOT by the monolith's `/agent/chat` call |
| **App-level multi-agent workflow** | `app/services/chat/graph/workflow.py` | **ZOMBIE** | 7: planner, researcher, writer, super_reasoner, procedural_auditor, reviewer, supervisor | Only `tests/verify_graph_manual.py` — never production |

---

## Critical Finding: Monolith → Orchestrator Does NOT Use the StateGraph

The monolith calls `/agent/chat` via `ChatRoutingPolicy.candidate_urls()`:
```python
# app/infrastructure/clients/routing_policy.py:45
return [f"{base}/agent/chat" for base in self.candidate_bases]
```

The `/agent/chat` endpoint routes to `OrchestratorAgent.run()` — an intent-based dispatch system — **NOT** the 13-node `StateGraph`. The StateGraph is only invoked by:
- `/api/chat/messages` (HTTP) → `_run_chat_langgraph()` → `app_graph.astream_events()`
- `/api/chat/ws` (WS) → `_stream_chat_langgraph()` → `app_graph.astream_events()`
- `/admin/api/chat/ws` (WS) → `admin_app.astream_events()`

**Consequence**: Even when the orchestrator microservice is running, the 13-node StateGraph is NOT invoked by the monolith's chat path. The monolith hits `OrchestratorAgent` (intent-based dispatch) instead.

---

## thread_id Propagation — Verified Call Chain

### Local fallback graph (PARTIAL — runs every turn in default Codespaces)
```
customer_chat.py → OrchestratorClient.chat_with_agent(conversation_id=lc_id)
  → [ConnectError] → run_local_graph(conversation_id=conversation_id)
    → thread_id = str(conversation_id)   # e.g. "394"
    → config = {"configurable": {"thread_id": thread_id}}
    → graph.ainvoke(initial_state, config=config)
    → MemorySaver (module-level singleton in local_graph.py)
```

### Advanced orchestrator StateGraph (DORMANT)
```
customer_chat.py → OrchestratorClient.chat_with_agent(context={...})
  → HTTP POST /agent/chat → OrchestratorAgent.run()  ← NOT StateGraph
  
# StateGraph path (only via /api/chat/messages or /api/chat/ws on orchestrator):
_stream_chat_langgraph() or _run_chat_langgraph()
  → thread_id = _resolve_thread_id(context, conversation_id)
    # = f"u{user_id}:c{conversation_id}"  e.g. "u7:c394"
  → config = {"configurable": {"thread_id": thread_id}}
  → app_graph.astream_events(inputs, config=config, version="v2")
```

### thread_id format mismatch

| Stack | Format | Example | Checkpointer |
|---|---|---|---|
| Local fallback graph | `str(conversation_id)` | `"394"` | `MemorySaver` (in-process, lost on restart) |
| Orchestrator StateGraph | `f"u{user_id}:c{conversation_id}"` | `"u7:c394"` | `AsyncPostgresSaver` (if DB) or `MemorySaver` singleton |
| OrchestratorAgent (HTTP) | `f"u{user_id}:c{conversation_id}"` | `"u7:c394"` | Not used — no LangGraph checkpointing |

**These namespaces are incompatible.** A conversation that starts on the local fallback graph (`"394"`) and later routes to the orchestrator StateGraph (`"u7:c394"`) has no shared checkpoint state. This is ISS-019.

---

## session_id Propagation — Verified

- Monolith sends `context={"chat_scope":"customer","metadata":...,"compatibility_facade":True}` — **no `thread_id`, no `session_id`**.
- Orchestrator `/agent/chat` builds `thread_id` internally from `user_id + conversation_id`.
- `session_id` is extracted from `context.get("session_id")` — always `None` on the HTTP path from the monolith.
- On orchestrator's own WS endpoints: `sticky_thread_id = _build_conversation_thread_id(user_id, conversation_id)` is set per-turn.

---

## AdminAgentNode — Stateless thread_id (by design)

Inside the 13-node StateGraph, `AdminAgentNode.__call__()` invokes the admin sub-graph with:
```python
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
```
A fresh UUID per invocation → admin sub-graph is **stateless** — no checkpoint continuity even when the parent graph has a Postgres checkpointer. Intentional (admin queries are stateless) but undocumented.

---

## 13-Node StateGraph Topology

```
supervisor → [route_intent]
  "educational"       → query_rewriter → query_analyzer → retriever → reranker
                          → [check_results]
                            "found"             → synthesizer
                            "web_fallback"      → web_fallback → synthesizer
                            "general_knowledge" → general_knowledge
  "admin"             → admin_agent → validator
  "tool"              → tool_executor → validator
  "chat"              → chat_fallback → validator
  "general_knowledge" → general_knowledge → validator
validator → [check_quality]
  "pass" → END
  "fail" → supervisor  (retry loop via retry_count in AgentState)
```

### DSPy usage per node (all DORMANT — require orchestrator running)

| Node | DSPy component | Purpose |
|---|---|---|
| `SupervisorNode` | `dspy.ChainOfThought(IntentClassifier)` | 4-intent classification: educational/general_knowledge/admin/chat |
| `QueryRewriterNode` | `dspy.ChainOfThought(QueryRewriterSignature)` | Pronoun resolution, query clarification |
| `QueryAnalyzerNode` | `dspy.Predict(AnalyzeQuery)` | BAC filter extraction (year, subject, branch, exercise_num) |
| `SynthesizerNode` | `dspy.Predict(EducationalSynthesizer)` | Arabic educational response synthesis |
| `ChatFallbackNode` | `dspy.Predict(ChatFallbackSignature)` | Conversational Arabic response |

All DSPy calls require `OPENROUTER_API_KEY` and are configured via `_configure_dspy()` at graph startup.

### 4-intent vs 3-intent taxonomy — do not conflate

| Stack | Intents | `general` routes to |
|---|---|---|
| Orchestrator StateGraph | `educational`, `general_knowledge`, `admin`, `chat` | `GeneralKnowledgeNode` (dedicated LLM handler) |
| Local fallback graph | `educational`, `general`, `chat` | Same `chat_node` as `chat` intent |

---

## Postgres Checkpointer — Conditional Availability

```python
# microservices/orchestrator_service/src/core/database.py
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None  # → graph compiled without checkpointer

# Checkpointer available only when ALL of:
# 1. AsyncPostgresSaver importable (langgraph-checkpoint-postgres installed)
# 2. ORCHESTRATOR_DATABASE_URL set and reachable
# 3. AsyncConnectionPool opens successfully
# 4. postgres_checkpointer.setup() succeeds

# Fallback: module-level MemorySaver singleton in main.py
_memory_saver = _MemorySaver()
active_checkpointer = get_checkpointer() or _memory_saver
```

In default Codespaces: `ORCHESTRATOR_DATABASE_URL` not set → `get_checkpointer()` returns `None` → graph compiled with `_memory_saver`. State is in-process only.

---

## WebSearchFallbackNode — Tavily Call Chain

```
WebSearchFallbackNode.__call__(state)
  → tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
  → if not tavily_key:
      emit_telemetry(retrieval_source="web_skipped_missing_tavily")
      return {"reranked_docs": [], "used_web": False}  # silent skip, no exception
  → research_client.deep_research(query_str)  # HTTP to research-agent:8007
    → research-agent: SuperSearchOrchestrator
      → TavilyClient(api_key=tavily_key).search(query, search_depth="basic", max_results=3)
```

**`TAVILY_API_KEY` absent from `docker-compose.yml`** — neither `orchestrator-service` nor `research-agent` environment sections include it. Must be added as `- TAVILY_API_KEY=${TAVILY_API_KEY:-}`.

**DuckDuckGo fallback broken**: `ddgs` package NOT installed → `ImportError` if Tavily absent and orchestrator running.

**Silent degradation**: when key absent, `SynthesizerNode` receives empty docs → response: `"لا توجد تفاصيل متاحة."`. No exception, no ERROR log — only telemetry event `retrieval_source="web_skipped_missing_tavily"`.

---

## Admin Sub-Graph (5 nodes)

```
detect → validate → resolve → execute → render → END
```

Compiled at lifespan startup with the same checkpointer as the main graph. Invoked by `AdminAgentNode` inside the main graph (with a fresh `uuid4()` thread_id — stateless).

---

## OrchestratorAgent Intent Dispatch (HTTP /agent/chat path)

`OrchestratorAgent.run()` uses `IntentDetector` (13-intent taxonomy: FILE_READ, CONTENT_RETRIEVAL, ADMIN_QUERY, MISSION_COMPLEX, etc.) — completely different from both the local graph's 3-intent and the StateGraph's 4-intent taxonomies.

Dispatch table:
- `ADMIN_QUERY / CODE_SEARCH / PROJECT_INDEX` → `AdminAgent.run()`
- `MISSION_COMPLEX` → `handle_mission_complex_stream()`
- `ANALYTICS_REPORT / LEARNING_SUMMARY` → `AnalyticsAgent.process()`
- `CURRICULUM_PLAN` → `CurriculumAgent.process()`
- `CONTENT_RETRIEVAL` → `_handle_content_retrieval()`
- everything else → `_handle_chat_fallback()`

None of these paths use the 13-node StateGraph.

---

## App-Level Multi-Agent Workflow — ZOMBIE

`app/services/chat/graph/workflow.py:create_multi_agent_graph()`:
- 7 nodes: planner, researcher, writer, super_reasoner, procedural_auditor, reviewer, supervisor
- All nodes call `kagent.execute_action()` → `"⛔ Security Alert: Invalid token"` (KAgent security blocks all calls)
- Only consumer: `tests/verify_graph_manual.py` — never production
- No `thread_id` or checkpointer — compiled without `MemorySaver`
- Status: **ZOMBIE** — compiles but cannot execute

---

## Truth Table Lock Staleness

`.runtime/truth_table.lock.json`:
- `generated_at_utc`: `2026-05-08T09:54:43Z`
- `branch`: `jules-5513332666705839536-7e7df21b`
- **Stale by ≥1 day, generated on a different branch**
- Missing entries: orchestrator StateGraph, Tavily, DSPy, research_agent, OrchestratorAgent
- CI drift check fails: `customer_chat_router: importer_count 6→5` (`.orig` file counting artifact)
- **Action**: `python scripts/runtime_truth.py --update` then commit

---

## Revival Roadmap (Documentation Only — Do Not Implement)

### To bring the 13-node StateGraph to ACTIVE on the live call chain:

1. Add `TAVILY_API_KEY=${TAVILY_API_KEY:-}` to `docker-compose.yml` (orchestrator-service + research-agent)
2. `docker compose -f docker-compose.yml up -d orchestrator-service research-agent postgres-orchestrator redis-orchestrator`
3. Verify `curl http://localhost:8006/health` — warmup must pass
4. **Change `ChatRoutingPolicy.candidate_urls()`** to return `/api/chat/messages` instead of `/agent/chat` — this is the only way to route the monolith through the StateGraph instead of `OrchestratorAgent`
5. Set `ORCHESTRATOR_SERVICE_URL=http://localhost:8006` in monolith env
6. Verify telemetry: `retrieval_source="web"` (not `"web_skipped_missing_tavily"`) for educational queries
7. Update `.memory/runtime_truth.md` rows 24, 24a, 24b to ACTIVE

### To fix DuckDuckGo fallback:
- `pip install ddgs` in the research-agent container

### To enable Postgres checkpointer:
- Set `ORCHESTRATOR_DATABASE_URL` in orchestrator-service env
- Verify `AsyncPostgresSaver` is importable (`langgraph-checkpoint-postgres` installed)

---

## Debugging Heuristics

1. **"Is the advanced LangGraph running?"** → Check if `orchestrator-service:8006` is reachable. If not, the monolith is using `local_graph.py` (2 nodes, not 13).
2. **"Which thread_id is being used?"** → If `thread_id` looks like `"394"` (bare number), it's the local graph. If it looks like `"u7:c394"`, it's the orchestrator.
3. **"Is Tavily being called?"** → Check telemetry for `retrieval_source`. `"web_skipped_missing_tavily"` = key absent. `"web"` = Tavily called. `"local"` = internal retriever found results.
4. **"Is the StateGraph running?"** → Look for `phase_start` events in the WS stream. These are emitted by `_stream_chat_langgraph()` for each node. If absent, `OrchestratorAgent` is handling the request.
5. **"Is the Postgres checkpointer active?"** → Look for `[CHECKPOINTER]` log lines in orchestrator logs. `"compiled without checkpointer"` = MemorySaver. `"compiled with Postgres checkpointer"` = persistent.
6. **"Why is the admin sub-graph stateless?"** → `AdminAgentNode` uses `uuid4()` for thread_id. This is intentional — admin queries are stateless by design.
