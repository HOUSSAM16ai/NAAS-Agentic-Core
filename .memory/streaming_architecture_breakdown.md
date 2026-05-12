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
