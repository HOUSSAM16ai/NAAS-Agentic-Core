SUPER AGENT RUNTIME TRUTH FINAL

1. Executive Summary

- **CONFIRMED**: The modern live WebSocket control plane is `frontend -> API Gateway (/api/chat/ws or /admin/api/chat/ws) -> orchestrator-service` by default, with optional canary diversion to `conversation-service` controlled by `ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT` (default `0`).
- **CONFIRMED**: Ordinary chat and Super Agent diverge inside `orchestrator_service.src.api.routes` at `_is_mission_complex(incoming)`.
- **CONFIRMED**: Ordinary chat emits `{status,response,run_id,timeline,graph_mode,route_id}`; Super Agent emits event-envelope messages `{type,payload}`. Frontend consumer is type-driven and does not render ordinary chat responses because it ignores `{status,response}` messages.
- **CONFIRMED**: Super Agent persistence writes happen in orchestrator-service (`_ensure_conversation`, `_persist_assistant_message`) against `admin/customer_*` tables; mission records/events are separate orchestrator mission tables.
- **HIGH-CONFIDENCE**: History read endpoints used by frontend (`/api/chat/conversations*`, `/admin/api/conversations*`) are not owned by the same runtime component that writes Super Agent data in orchestrator-service, causing practical read/write split-brain risk.
- **PRIMARY DIAGNOSIS**: Contract drift + persistence/control-plane split are jointly present; highest-confidence dominant failure is WS contract mismatch for ordinary chat plus unresolved ownership split for history/persistence.

2. Live Control-Plane Truth

### Active ingress and routing

- **CONFIRMED**: Frontend opens WS to `/api/chat/ws` (customer) or `/admin/api/chat/ws` (admin). `CogniForgeApp` sets endpoint by role; `useAgentSocket` constructs URL from `NEXT_PUBLIC_WS_URL` or API origin.
- **CONFIRMED**: API Gateway owns those WS routes and proxies them with `_resolve_chat_ws_target`.
- **CONFIRMED**: Default routing goes to orchestrator-service (`ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT=0`), with environment-dependent canary to conversation-service if rollout > 0.

### Monolith WS reachability

- **HIGH-CONFIDENCE**: Monolith WS routes exist (`app/api/routers/customer_chat.py`, `app/api/routers/admin.py`) but are not on the default production ingress path in docker-compose, where frontend depends on api-gateway and gateway points chat WS to orchestrator/conversation services only.

### First divergence point (ordinary vs Super Agent)

- **CONFIRMED**: In orchestrator WS handlers (`chat_ws_stategraph`, `admin_chat_ws_stategraph`), divergence happens at `_is_mission_complex(incoming)`.
  - false -> `_run_chat_langgraph` and one-shot JSON result.
  - true -> `_stream_mission_complex_events` and typed event stream.

### Route truth table

- **Customer ordinary chat**
  - ingress: `/api/chat/ws` (gateway)
  - router: gateway websocket proxy
  - execution owner: orchestrator `chat_ws_stategraph`
  - persistence owner: none for ordinary path in orchestrator WS
  - emitter: one JSON object with `status/response/...`

- **Admin ordinary chat**
  - ingress: `/admin/api/chat/ws` (gateway)
  - router: gateway websocket proxy
  - execution owner: orchestrator `admin_chat_ws_stategraph`
  - persistence owner: none for ordinary path in orchestrator WS
  - emitter: one JSON object with `status/response/...`

- **Customer Super Agent**
  - ingress: `/api/chat/ws` (gateway)
  - router: gateway websocket proxy
  - execution owner: orchestrator `_stream_mission_complex_events` -> `handle_mission_complex_stream`
  - persistence owner: orchestrator `_ensure_conversation` + `_persist_assistant_message`
  - emitter: typed envelope events `{type,payload}`

- **Admin Super Agent**
  - ingress: `/admin/api/chat/ws` (gateway)
  - router: gateway websocket proxy
  - execution owner: orchestrator `_stream_mission_complex_events` -> `handle_mission_complex_stream`
  - persistence owner: orchestrator `_ensure_conversation` + `_persist_assistant_message` (+ `linked_mission_id` update only for admin)
  - emitter: typed envelope events `{type,payload}`

3. Persistence Ownership Truth

### Ordinary chat

- **CONFIRMED**: In live orchestrator WS ordinary path, no conversation/message DB write is executed. `_run_chat_langgraph` returns run payload only.
- **CONFIRMED**: Legacy monolith path does persist (boundary services + persistence classes), but that persistence belongs to dormant/non-primary control plane under current gateway topology.

### Super Agent

- **CONFIRMED**: Super Agent path in orchestrator explicitly writes:
  - conversation create/verify (`admin_conversations` or `customer_conversations`) in `_ensure_conversation`
  - user message insert in `_ensure_conversation`
  - assistant message insert in `_persist_assistant_message`
  - `linked_mission_id` update only for admin conversations in `_persist_assistant_message`
- **CONFIRMED**: Mission lifecycle/events are persisted via mission state manager in orchestrator mission tables (separate from chat history tables).

### History/read ownership

- **HIGH-CONFIDENCE**: Frontend reads history from `/api/chat/conversations*` (customer) and `/admin/api/conversations*` (admin). Gateway routes `/api/chat/*` to orchestrator/conversation service by rollout (not monolith), while `/admin/*` routes to user-service. This does not guarantee reads from the same store that orchestrator Super Agent writes to.
- **CONFIRMED (customer risk)**: orchestrator routes file does not expose `/api/chat/conversations*`; conversation-service provides only minimal `/api/chat/{path}` placeholder and no persistence logic. Therefore customer history ownership is ambiguous/non-authoritative in modern path.
- **HIGH-CONFIDENCE (admin risk)**: gateway admin proxy forwards to user-service path rewrite (`/admin/{path} -> /api/v1/admin/{path}`), while Super Agent writes occur in orchestrator DB/session; shared-storage assumption is unproven here => potential split-brain.

4. WebSocket Contract Truth

### Emitted shapes

- **CONFIRMED (ordinary chat, orchestrator WS)**:
  - envelope: `{ "status": "ok", "response": "...", "run_id": "...", "timeline": [...], "graph_mode": "stategraph", "route_id": "chat_ws_*" }`
- **CONFIRMED (Super Agent, orchestrator WS)**:
  - envelope stream: `{type,payload}` events such as `conversation_init`, `assistant_delta`, `mission_created`, `RUN_STARTED`, `assistant_final`, `assistant_error`, etc.
- **CONFIRMED (gateway proxy)**:
  - text frames only (`receive_text` / `send_text`) with JSON serialized by upstream; no binary/NDJSON framing support in gateway WS proxy.

### Frontend consumer compatibility

- **CONFIRMED**: Frontend handler is event-type driven and only reacts to messages containing `type` (`conversation_init`, `delta`, `assistant_delta`, `assistant_final`, `complete`, `error`, `assistant_error`, etc.).
- **CONFIRMED**: Frontend ignores ordinary orchestrator message shape (`status/response`) because no `type` branch handles it.
- **CONFIRMED**: UI currently behaves like it expects a single FSM-ish `{type,payload}` stream contract, but backend ordinary chat provides a separate one-shot contract.

### Contract mismatch classification

- **CONFIRMED**: This is a protocol/contract drift between ordinary and Super Agent WS paths (mixed contract families on same socket endpoint).

5. Payload and Mission Contract Truth

- **CONFIRMED**: Frontend sends `mission_type` at root (`{ question, mission_type, conversation_id? }`) from `ChatInterface -> useAgentSocket`.
- **CONFIRMED**: Orchestrator mission detection accepts `mission_type` in both root and `metadata.mission_type` (`_is_mission_complex`).
- **CONFIRMED**: `conversation_id` is expected at root on WS input; for outgoing, Super Agent emits `conversation_init.payload.conversation_id` and forwards mission_created payload containing conversation id.
- **CONFIRMED**: In frontend send path, existing `conversationId` is stringified (`payload.conversation_id = String(conversationId)`), while orchestrator `_extract_mission_context` copies only integer `conversation_id`; non-int input is dropped from context and replaced only after `_ensure_conversation`.
- **CONFIRMED**: For admin Super Agent, `mission_id` is written back to `admin_conversations.linked_mission_id`. For customer Super Agent, no equivalent mission link field update exists.
- **UNKNOWN**: Whether all deployed clients always send numeric `conversation_id` (not string) for mission continuation cannot be proven statically.

6. End-to-End Runtime Reality

- **ordinary chat renders correctly**: **CONFIRMED FALSE** in modern path due to contract mismatch (`status/response` not consumed by UI type router).
- **ordinary chat persists correctly**: **CONFIRMED FALSE** in orchestrator WS ordinary path (no persistence writes).
- **Super Agent dispatches correctly**: **CONFIRMED** (mission branch triggered by mission_type in root or metadata).
- **Super Agent streams correctly**: **CONFIRMED** for typed events from orchestrator; frontend has handlers for these event types.
- **Super Agent persists correctly**: **HIGH-CONFIDENCE PARTIAL**: writes occur in orchestrator tables, but read-side ownership exposed to UI is not proven aligned (especially customer history path).
- **history endpoint reads same source as runtime writes**: **HIGH-CONFIDENCE FALSE** (or at minimum unproven) because gateway path ownership and available route implementations do not line up with orchestrator Super Agent write ownership.

7. False-Confidence Test Audit

- **FALSE CONFIDENCE**: `tests/regressions/test_streaming_event_type_bug.py`
  - Uses monolith `/admin/api/chat/ws` with mocked orchestrator (`get_chat_orchestrator`) and validates only delta emission.
  - Does not validate modern gateway->orchestrator control plane nor ordinary `status/response` contract compatibility.

- **FALSE CONFIDENCE**: `tests/api/test_customer_chat_persistence.py`
  - Patches monolith `ChatOrchestrator.dispatch/process` and validates monolith persistence/history coherence.
  - Does not prove live gateway/orchestrator-service runtime ownership.

- **FALSE CONFIDENCE**: `tests/microservices/test_api_gateway_ws_routing.py`
  - Verifies target routing with fake ws_proxy and `ok` text only.
  - Does not validate event envelope compatibility or persistence/read-model alignment.

- **FALSE CONFIDENCE**: `tests/microservices/test_orchestrator_chat_stategraph.py`
  - Good for internal orchestrator branching, but mission tests monkeypatch critical persistence/stream helpers in places, so they do not fully prove production persistence + history read coherence.

8. Evidence Index

- **Gateway WS ingress and canary target resolution**
  - `microservices/api_gateway/main.py`
    - `_resolve_chat_ws_target`
    - `chat_ws_proxy`
    - `admin_chat_ws_proxy`
    - `chat_http_proxy`

- **Gateway WS transport behavior**
  - `microservices/api_gateway/websockets.py`
    - `websocket_proxy` (text frame pass-through)

- **Orchestrator chat and Super Agent fork**
  - `microservices/orchestrator_service/src/api/routes.py`
    - `_is_mission_complex`
    - `chat_ws_stategraph`
    - `admin_chat_ws_stategraph`
    - `_stream_mission_complex_events`
    - `_ensure_conversation`
    - `_persist_assistant_message`

- **Super Agent event stream semantics**
  - `microservices/orchestrator_service/src/services/overmind/utils/mission_complex.py`
    - `handle_mission_complex_stream`

- **Conversation service canary behavior**
  - `microservices/conversation_service/main.py`
    - `_chat_ws_loop`
    - `_response_envelope`

- **Frontend WS send/receive contract**
  - `frontend/app/components/CogniForgeApp.jsx`
  - `frontend/app/components/ChatInterface.jsx`
  - `frontend/app/hooks/useAgentSocket.js`
  - `frontend/app/hooks/useRealtimeConnection.js`

- **Legacy/monolith chat persistence path (non-primary control plane)**
  - `app/api/routers/customer_chat.py`
  - `app/api/routers/admin.py`
  - `app/services/boundaries/customer_chat_boundary_service.py`
  - `app/services/boundaries/admin_chat_boundary_service.py`
  - `app/services/customer/chat_streamer.py`
  - `app/services/admin/chat_streamer.py`
  - `app/services/customer/chat_persistence.py`
  - `app/services/admin/chat_persistence.py`
  - `app/services/chat/handlers/strategy_handlers.py` (legacy MissionComplexHandler)

- **Schema ownership clues**
  - `app/core/domain/chat.py`
  - `microservices/orchestrator_service/src/core/domain/chat.py`

- **Runtime topology**
  - `docker-compose.yml`

- **Runtime-targeted verification executed**
  - `pytest -q tests/microservices/test_api_gateway_ws_routing.py tests/microservices/test_orchestrator_chat_stategraph.py`

9. Primary Root Cause Verdict

**PRIMARY ROOT CAUSE HIGH-CONFIDENCE**

- Root cause: **contract drift on shared WS endpoint** — ordinary chat emits `{status,response}` while frontend consumes `{type,payload}` events, causing ordinary responses to be effectively dropped in UI; simultaneously, persistence/read ownership is fragmented across gateway targets and services, amplifying Super Agent/history confusion.
- Secondary contributing factors:
  1. Environment-dependent gateway canary to conversation-service introduces additional contract/ownership variability.
  2. Customer/admin history read endpoints are not clearly co-owned by orchestrator Super Agent write path.
  3. Legacy monolith routes/tests continue to pass and mask modern control-plane behavior.

10. Remaining Unknowns

- **UNKNOWN**: Whether deployed environments share a single physical DB/schema between user-service and orchestrator-service for chat tables.
- **UNKNOWN**: Effective production values of `ROUTE_CHAT_HTTP_CONVERSATION_ROLLOUT_PERCENT` and `ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT`.
- **UNKNOWN**: Whether external clients always send numeric `conversation_id` (integer) vs string in mission continuation payloads.

11. Minimal Safe Fix Boundary

- **CONFIRMED boundary (diagnosis-only statement, not implementation roadmap):**
  1. One WS contract authority must be enforced per endpoint (`{type,payload}` or an adapter layer).
  2. One persistence owner and one read-model owner must be explicitly bound for `/api/chat/*` and `/admin/api/*` history routes.
  3. Mission linkage semantics (`mission_id <-> conversation`) must be consistently defined for both admin and customer scopes.

- **Instrumentation added**: None.
