# ADR-001: Orchestration Authority

## Status
Superseded (by Microservice Migration) -> **Active**

## Date
2026-02-10 (Updated: 2026-10-27)

## Decision
The **`microservices/orchestrator_service`** is the **sole coordinator and authority** for mission execution and state management.

The legacy Monolith orchestration logic (formerly in `app/services/overmind/orchestrator.py` and related modules) is **deprecated and removed**.

## Context
The system suffered from a "Split-Brain" architecture where both the Monolith and the Microservice attempted to manage mission state, leading to data inconsistencies and operational confusion.

To resolve this, we strictly enforce the following:
1.  **Single Source of Truth**: The `orchestrator_db` (managed by `orchestrator-service`) is the authoritative store for active mission execution state. The Monolith's `core_db` may store historical records or be synced eventually, but it does NOT drive execution.
2.  **No Local Execution**: The Monolith (`core-kernel`) MUST NOT execute missions locally. All mission requests must be routed to the `orchestrator-service` via `OrchestratorClient` or direct API calls.
3.  **Client-Only Role**: The `app/services/overmind` module in the Monolith is reduced to a **Client Proxy** and Type Definition library. It provides the interface for the rest of the Monolith to request work from the Orchestrator.

## Implementation

### Frontend Authority
The frontend operates on a strict **Command -> Event** pattern:
- **Command**: User sends a message or action (e.g., "Start Mission") -> API Gateway -> Orchestrator Service.
- **Event**: The frontend listens for `agent:event` (via WebSocket from Orchestrator or Gateway Proxy).
- The frontend **never** predicts the next state. It only renders what the backend reports.

### Backend Authority
- The `orchestrator-service` (Microservice) is the single source of truth.
- It emits specific events (`phase_start`, `phase_completed`, `loop_start`) that consumers (Monolith, Frontend) subscribe to.

## Consequences
- **Positive**:
    - **Eliminated Split-Brain**: Only one service decides what happens next.
    - **Decoupling**: The Monolith is no longer burdened with complex agent orchestration logic.
    - **Scalability**: The Orchestrator can be scaled independently of the Monolith.
- **Negative**:
    - **Network Dependency**: The Monolith now depends on the Orchestrator Service availability to start missions.
