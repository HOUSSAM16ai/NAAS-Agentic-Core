# Streaming Architecture — Live Fixes Log

## ISS-054 Fix Summary (2026-05-13)

### Root causes identified via live testing:
1. **Machine-gun rendering**: `useRealtimeConnection.js` dispatched one `CustomEvent` per WebSocket message → 400+ `setMessages` calls in 4s → React re-render storm.
   - **Fix**: `requestAnimationFrame` batching — buffer all `delta`/`assistant_delta` events, merge content, dispatch once per ~16ms frame.
2. **Explanation timeout**: exercise context (13650 chars) + large system prompt → free model freezes. `BASE_TIMEOUT=30s` killed request before first token.
   - **Fix**: `_MAX_EXERCISE_CONTEXT_CHARS=6000`, `_MAX_EXPLANATION_TOKENS=1200`, `BASE_TIMEOUT=45s`, `max_tokens` param in `stream_chat()`.
3. **Broken LaTeX `$ $`**: `$$g(x)=...$$` single-line blocks fell through to `_split_preserving_latex()` which split on spaces → `$ $g(x)` in output.
   - **Fix**: Added explicit single-line `$$...$$` guard before multi-line handler in `_stream_local_retrieval_response`.

### Verified live results:
- Exercise retrieval: TTFT=0.85s, 392 chunks, 2939 chars, LaTeX intact ✅
- Explanation: TTFT=3.81s, 306 chunks, 1860 chars, no hallucination ✅
- Frontend: 400 re-renders → ~60fps batches via rAF ✅

---

# Architectural Diagnosis: Streaming Event Bottleneck (2026-05-10)

## Overview
A severe data contract mismatch was identified across the full stack concerning WebSocket chat streaming. Users reported that words did not appear "word-by-word" (typing effect), but rather as large chunks or single final messages.

A hyper-detailed forensic diagnosis was performed **without modifying any code**, enforcing strict observational boundaries.

## Root Cause Analysis

The root cause is a "Streaming Event Bottleneck" caused by structural buffer-and-wait patterns in both backend routing implementations, combined with a mismatch in the frontend client logic.

### 1. Legacy Monolith (`app/services/chat/local_graph.py`)
- **Mechanism:** The legacy monolith powers default interactions.
- **The Bug:** It utilizes `ainvoke()` on the compiled LangGraph object instead of `astream_events()`.
- **Impact:** `ainvoke()` blocks execution until the entire LLM response is fully generated, completely defeating the `stream=True` configuration sent to OpenRouter. No token-level deltas are ever emitted to the routing layer.

### 2. Orchestrator Microservice (`microservices/orchestrator_service/src/api/routes.py`)
- **Mechanism:** The target architecture microservice proxy.
- **The Bug:** It successfully utilizes `astream_events(..., version="v2")`, which *does* capture token-level streaming events from LangChain (`on_chat_model_stream`). However, the implementation explicitly ignores these events:
  ```python
  if event["event"] == "on_chat_model_stream":
      # Token deltas are received but explicitly ignored/discarded here
      pass
  ```
- **Impact:** The router waits for the `on_chain_end` event and sends the entire aggregated response chunk via a single `assistant_final` event.

### 3. Frontend Client (`frontend/app/hooks/useAgentSocket.js`)
- **Mechanism:** Listens for WebSocket events via `useRealtimeConnection`.
- **The Bug:** The client relies on `mergeAssistantContent()` to incrementally build the UI based on `assistant_delta` events.
- **Impact:** Because the backend only sends a massive `assistant_final` event (or delayed chunk), the "typing effect" is mathematically impossible. The frontend correctly parses the event but renders the full string instantly.

## Architecture & Data Contract Rules for Streaming

To resolve this issue and prevent regressions, the following strict Data Contract rules must be enforced across all streaming implementations:

1. **Graph Execution Contract:** All LangGraph executions intended for real-time user interaction must use `astream_events(..., version="v2")` (or equivalent asynchronous generator), **never** `ainvoke()`.
2. **Delta Routing Contract:** API routing layers (FastAPI WebSocket routes, REST streaming proxies) must actively yield or dispatch `on_chat_model_stream` events as granular `assistant_delta` payloads. They must not buffer tokens into a final string before transmission.
3. **Frontend Resilience Contract:** The frontend `mergeAssistantContent` function must remain purely functional and resilient. It currently correctly handles overlapping chunk boundaries, but it depends completely on the backend honoring the delta contract.

## Roadmap to Resolution (For Future Implementation)

When code modifications are authorized, the following targeted fixes must be applied:

1. **Step 1 (Monolith):** Refactor `local_graph.py` execution within the routing layer (`customer_chat.py`) to replace `ainvoke` with an asynchronous generator looping over `graph.astream_events()`, formatting and yielding `assistant_delta` chunks over the WebSocket.
2. **Step 2 (Microservice):** Update `microservices/orchestrator_service/src/api/routes.py` to capture `on_chat_model_stream` events, extract the `chunk.content`, and immediately `yield` or `send` an `assistant_delta` payload.
3. **Step 3 (Verification):** Use network protocol analysis to confirm that WebSocket frames are small, continuous chunks containing single words/tokens, and visually verify the typing effect in the Next.js UI.

---

## ISS-STREAM-001 Fix Report (2026-05-12 — branch `fix/streaming-iss-stream-001`)

**Status: FULLY RESOLVED.** جميع مسارات البث مُصلَحة جراحياً. تفاصيل:

### الأسباب الجذرية المكتشفة (إضافة إلى D-047)

**السبب 4 — `_normalize_stream_event` يُحوّل أحداث التحكم إلى `assistant_delta`:**
- `phase_start`, `phase_completed`, `RUN_STARTED`, `context_missing` كانت تُحوَّل إلى `assistant_delta` لأنها ليست في `event_type_map`.
- النتيجة: نصوص غريبة تظهر في الواجهة مثل `{"type": "phase_start", "payload": {...}}`.
- الإصلاح: أضفنا `_PASSTHROUGH_EVENT_TYPES` و `_TEXT_EVENT_TYPES` — الأحداث غير المعروفة تُرجع `{"type": "noop"}` وتُصفَّى في `customer_chat.py` و `admin.py`.

**السبب 5 — `_generator_with_persistence` لا يجمع الـ deltas للحفظ:**
- عند streaming، `assistant_final.content = ""` → `final_content = ""` → لا يُحفظ شيء في DB.
- الإصلاح: أضفنا `delta_parts: list[str]` يجمع كل `assistant_delta` chunks، ويُستخدم عند `assistant_final.content == ""`.

**السبب 6 — `mergeAssistantContent` منطق خاطئ:**
- `current.startsWith(incoming)` كان يُرجع `current` (يتجاهل الـ chunk الجديد).
- الإصلاح: استبدلنا بـ `current.endsWith(incoming)` للكشف عن chunks قديمة وصلت متأخرة.

**السبب 7 — `print()` statements في graph nodes تُلوّث stdout:**
- `SupervisorNode`, `ChatFallbackNode`, `QueryRewriterNode`, `ToolExecutorNode`, `ValidatorNode`, `GeneralKnowledgeNode` كانت تطبع debug info.
- الإصلاح: استبدلنا بـ `logger.debug()`.

### الملفات المُعدَّلة

| الملف | التغيير |
|-------|---------|
| `app/infrastructure/clients/orchestrator_client.py` | `_PASSTHROUGH_EVENT_TYPES` + `_TEXT_EVENT_TYPES` + noop return |
| `app/api/routers/customer_chat.py` | تصفية `noop` events |
| `app/api/routers/admin.py` | تصفية `noop` events |
| `microservices/orchestrator_service/src/api/routes.py` | `delta_parts` accumulator في `_generator_with_persistence` |
| `microservices/orchestrator_service/src/services/overmind/graph/main.py` | إزالة `print()` → `logger.debug()` |
| `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py` | إزالة `print()` → `logger.debug()` |
| `frontend/app/hooks/useAgentSocket.js` | إصلاح `mergeAssistantContent` + `assistant_final` handler |
| `.runtime/truth_table.lock.json` | تحديث بعد تغيير `customer_chat_router` |

### الملفات الجديدة

| الملف | الغرض |
|-------|-------|
| `.github/workflows/streaming-fix-gate.yml` | CI gate للتحقق من صحة الإصلاح |
| `observability/grafana/dashboards/160-streaming-metrics.json` | Dashboard مقاييس البث (11 panels) |

---

## D-047 Implementation Report (2026-05-12 — branch `claude/setup-microservices-monitoring-ralbR`)

**Status: RESOLVED at code level.** All three steps of the roadmap above are now applied. Pending only live verification in a Codespaces session.

### Step 1 — Monolith (`app/`) [DONE]

**Why we did NOT use `astream_events()` here**: the local graph's `_chat_node` uses `OpenRouterClient.send_message()` — a thin async wrapper that aggregates SSE chunks before returning. `OpenRouterClient` is NOT a LangChain `BaseChatModel`, so `astream_events()` does not emit `on_chat_model_stream` for it. We chose the more direct path that preserves identical observability semantics.

**What we did instead**:

1. Added `app/services/chat/local_graph.py::run_local_graph_stream()` — an `AsyncGenerator[str, None]` that:
   - Classifies intent in-process (same `_classify_intent` used by the graph supervisor) so the system prompt selection is identical to the non-streaming path.
   - Skips the graph wrapping and calls `OpenRouterClient.stream_chat()` directly with the same message construction.
   - Yields each non-empty `delta.content` as it arrives from OpenRouter SSE.
   - Emits the same Prometheus metrics as the non-streaming path (`langgraph.intent.total`, `langgraph.node.count.total`, `langgraph.node.duration_seconds`) plus a new `ws.chat.delta.total{path="local_graph_stream"}` counter for delta throughput tracking.

2. Added `app/infrastructure/clients/orchestrator_client.py::_stream_local_graph_response()` and `::_stream_local_general_chat_response()` — both `AsyncGenerator[str, None]`, both register `mark_fallback_used("local_graph_stream" | "local_general_chat_stream")` on entry.

3. Rewrote the fallback chain in `OrchestratorClient.chat_with_agent()` to:
   - Replace the `_build_local_graph_response → single assistant_delta + assistant_final` pair with a `async for chunk in self._stream_local_graph_response(...)` loop that yields one `assistant_delta` per chunk, then a final `assistant_final` with empty payload.
   - Replace the same pattern for the general-chat safety net.
   - Track `streamed_any` and `streamed_chars` per turn for observability and to skip the path cleanly if the upstream produced zero chunks (fall through to next fallback).

The router (`app/api/routers/customer_chat.py`) was **not** modified — it already forwards each event from `chat_with_agent` to the WebSocket via `await websocket.send_json(...)` without buffering. The bug was upstream of the router, not in it.

### Step 2 — Orchestrator Microservice (`microservices/orchestrator_service/src/api/routes.py`) [DONE]

The diagnostic correctly identified that this file calls `astream_events(..., version="v2")` but explicitly ignored `on_chat_model_stream` events (treated as `pass`). Patched in three call sites:

1. **HTTP path** (`/api/chat/messages` streaming response generator, ~line 1810) — captures `on_chat_model_stream`, extracts `chunk.content`, and yields `{"type": "assistant_delta", "payload": {"content": <str>}}` immediately.
2. **Customer WS path** (`/api/chat/ws` worker task, ~line 1532) — same pattern, dispatched via `_safe_put` to the consumer queue. Tracks `ws_streamed_chars` and attaches it to the `__DONE__` envelope so the consumer can suppress duplicate text in the final `assistant_final`.
3. **Admin WS path** (`/admin/api/chat/ws` streaming response, ~line 2562) — same pattern, tracks `admin_streamed_chars`, suppresses duplicate `response_text` in the persisted `assistant_final` after `[DB SAVED]`.

### Step 3 — Duplicate-Suppression Contract (NEW)

A subtle but critical addition: when token-level deltas are streamed, the trailing `assistant_final.payload.content` must be **empty** (not the full text) — otherwise the frontend's `mergeAssistantContent` would render the entire response twice (once incrementally during streaming, once on terminal frame).

Implementation:
- HTTP `/api/chat/messages`: if `streamed_chars > 0` → `content: ""`, else → `content: response_text` (fallback for non-streaming-aware models).
- Customer WS `/api/chat/ws`: same rule, driven by `run_data["__streamed_chars"]`.
- Admin WS `/admin/api/chat/ws`: same rule, driven by `admin_streamed_chars`.
- Local fallback chain in `orchestrator_client.py`: terminal `assistant_final.payload.content` is always `""` because the chunks were already sent.

The `streamed_chars` value is also attached to the `assistant_final.payload` for client-side observability.

### Verification commands (run in a Codespaces session with the secrets)

```bash
# 1. Confirm orchestrator emits on_chat_model_stream
curl -N -X POST http://localhost:8006/api/chat/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{"question":"اشرح لي قانون أوم","user_id":7,"conversation_id":1}' | head -20
# Expected: many small NDJSON lines, each one {"type":"assistant_delta","payload":{"content":"<word/fragment>"}}

# 2. Confirm monolith forwards chunks unbuffered
wscat -c "ws://localhost:8000/api/chat/ws?token=$JWT" -s jwt
# Send: {"question":"اشرح لي قانون أوم"}
# Expected: tens of small assistant_delta frames flowing within ~1s of send, NOT a single big frame after 30s.

# 3. Confirm fallback path also streams (orchestrator down)
sudo pkill -f orchestrator_service
# Then send the same WS message — same word-by-word effect should appear via local_graph_stream.

# 4. Confirm no double-rendering
# In the browser, watch the chat panel: the typing animation should produce the response exactly ONCE.
# If you see the response duplicate after streaming completes, the duplicate-suppression contract was bypassed somewhere.
```

### What this PR does NOT change

- `frontend/app/hooks/useAgentSocket.js` and `frontend/app/lib/streaming/mergeAssistantContent.ts` — they already handle delta accumulation correctly. The bug was 100% backend.
- `microservices/conversation_service/src/conversation_graph.py` — this skill still uses `ainvoke()` because it is not on the live user-facing chat path today. When it goes live (Step 13+), the same patch applies: replace `ainvoke()` with `astream_events()` + emit `on_chat_model_stream`.
- Persistence semantics (D-006) — the `persisted` flag protocol is unchanged. The Monolith still owns the write decision; the suppression of duplicate content in `assistant_final` does not affect the database row.
