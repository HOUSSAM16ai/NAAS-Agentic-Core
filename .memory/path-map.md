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
   - **fallback chain (in order, first non-None wins):**
     - `_build_file_count_response`        (file-intelligence)
     - `_build_local_retrieval_response`   (exercise-retrieval)
     - `_build_local_graph_response`       (LangGraph local — `mark_fallback_used("local_graph")`)
     - `_build_local_general_chat_response` (general LLM — `mark_fallback_used("local_general_chat")`)
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
