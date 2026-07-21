# Live Path Map — WS chat
> Last updated: 2026-05-06 | Branch: `claude/autonomous-runtime-observability-pjzY9`
> Auto-regenerated as `.runtime/path_map.json` on every Codespace attach + every CI run.
> This file is the human-readable summary for new contributors.

## Customer chat — `/api/chat/ws`
Live anchor: `app/api/routers/customer_chat.py:244` (`@router.websocket("/ws")`)

Per-turn chain:
1. `extract_websocket_auth` + `decode_user_id` — auth
2. `open_ws_turn(...)` → `app/telemetry/path_observer.py` — opens `WsTurnSpan` (path_type classified at entry)
3. `CustomerChatBoundaryService.get_or_create_conversation` + `save_message(USER)` — Monolith writes the user message (single-writer)
4. `OrchestratorClient.chat_with_agent(...)` → `app/infrastructure/clients/orchestrator_client.py:chat_with_agent`
   - HTTP attempt to `$ORCHESTRATOR_SERVICE_URL` → ConnectError in default Codespaces
   - **fallback chain (in order, first non-None wins) — ISS-053 updated 2026-05-13:**
     - `_build_file_count_response`              (1.0 — file-intelligence)
     - `_stream_local_retrieval_response`        (2.0 — exercise-retrieval: جلب نص التمرين بدون إجابة)
     - `_stream_exercise_explanation_response`   (2.5 — ISS-053: شرح تمرين بكالوريا مع سياق كامل)
       → `detect_explanation_with_context()` → `run_local_graph_with_exercise_context()`
       → LLM يحصل على نص التمرين + الإجابة النموذجية كـ context → لا هلوسة
     - `_stream_local_graph_response`            (3.0 — LangGraph local — `mark_fallback_used("local_graph")`)
     - `_stream_local_general_chat_response`     (4.0 — general LLM — `mark_fallback_used("local_general_chat")`)
5. Persistence decision (`persisted=True`? skip : fail-safe write with 2 retries)
6. `_emit_terminal_frames(...)` — single terminal `assistant_final` or `error` + one `persisted` event after save
7. `close_ws_turn(...)` — closes span + emits metrics

## Admin chat — `/admin/api/chat/ws`
Live anchor: `app/api/routers/admin.py:316`. Identical structure; different table (`admin_messages`); `path_type` is always `admin`.

## Path types — closed taxonomy
| Value | Meaning |
|---|---|
| `educational` | Supervisor classified the question as exam/subject content |
| `general_chat` | Small-talk / general knowledge (default for non-admin) |
| `fallback` | Orchestrator HTTP failed; a local engine produced the reply |
| `admin` | Admin chat WS endpoint, regardless of intent |
| `unknown` | Turn ended before classification was possible |

## Metrics (live, recorded by `path_observer`)
- `ws.chat.turn.duration_seconds` — histogram, labels `path_type`, `terminal`, `is_admin`
- `ws.chat.terminal_events.total` — counter, labels as above; `terminal ∈ {assistant_final, error, unknown}`
- `ws.chat.fallback.total` — counter, labels `path_type`, `is_admin`

## What is NOT on this map (and stays off until proven)
- The multi-agent workflow (`app/services/chat/graph/workflow.py`) — ZOMBIE.
- `ChatOrchestrator` + `CustomerChatStreamer` / `AdminChatStreamer` — PARTIAL (loaded-not-invoked).
- KAgent mesh, MCP integrations, LlamaIndex driver, Reranker driver — ZOMBIE / DORMANT.
- The microservice mesh (`microservices/*`) — DORMANT in default Codespaces.

---

## Orchestrator Microservice Paths (DORMANT — requires `docker compose -f docker-compose.yml up -d`)

### `/agent/chat` — OrchestratorAgent (intent-based dispatch)
This is what the monolith calls via `ChatRoutingPolicy.candidate_urls()`.
```
POST /agent/chat → chat_with_agent_endpoint(ChatRequest)
  → OrchestratorAgent.run(question, context)
    → IntentDetector.detect() → 13-intent taxonomy
    → dispatch: AdminAgent | AnalyticsAgent | CurriculumAgent | chat_fallback | ...
    → NOT the 12-node StateGraph
```

### `/api/chat/messages` — 12-node StateGraph (HTTP)
NOT called by the monolith. Only reachable directly or via orchestrator's own clients.
```
POST /api/chat/messages → chat_messages_endpoint(payload)
  → context["thread_id"] = f"u{user_id}:c{conversation_id}"
  → _run_chat_langgraph() → app_graph.astream_events(inputs, config, version="v2")
    → 12-node StateGraph: supervisor → [routing] → ... → validator → END
```

### `/api/chat/ws` — 12-node StateGraph (WebSocket)
NOT called by the monolith. Direct WebSocket connection to orchestrator.
```
WS /api/chat/ws → chat_ws_stategraph(websocket)
  → sticky_thread_id = f"u{user_id}:c{conversation_id}"
  → _stream_chat_langgraph() → app_graph.astream_events(inputs, config, version="v2")
    → emits: phase_start, phase_completed, assistant_delta, assistant_final
```

### thread_id formats (do not mix)
| Path | thread_id | Checkpointer |
|---|---|---|
| Monolith → local_graph.py | `str(conversation_id)` e.g. `"394"` | MemorySaver (in-process) |
| Orchestrator → StateGraph | `f"u{user_id}:c{conversation_id}"` e.g. `"u7:c394"` | AsyncPostgresSaver or MemorySaver singleton |
| AdminAgentNode (inside StateGraph) | `str(uuid.uuid4())` | None — stateless |
