# Architecture: Unified Control Plane & Source of Truth

## Core Principle: Single Control Plane (Microservices)
This system enforces a **Single Control Plane** architecture to prevent "Split-Brain" orchestration.
The **`microservices/orchestrator_service`** is the designated Control Plane and Authority.
The legacy `app/services/overmind` (Monolith Orchestrator) logic has been **removed**.

## Single Source of Truth
The **`orchestrator_db`** (accessed via the Orchestrator Service) is the **Single Source of Truth** for:
- Mission State (Status, Context)
- Mission Events (Log)
- Execution Plans

Any external service attempting to manage mission state independently is a violation of this architecture.

## Execution Flow: Command -> Event -> State
All mission executions must follow the **Command Pattern**:
1.  Client (API/Chat/Monolith) sends a `StartMission` command via `OrchestratorClient` or direct API call to the Orchestrator Service.
2.  The Orchestrator Service enforces **Idempotency** and **Locking**.
3.  The Orchestrator Service persists `MissionStarted` event to its DB.
4.  The Orchestrator Service triggers execution (background task or worker).
5.  Execution Logic updates state and logs events in the Orchestrator DB.

## Strict Boundaries
- **No Local Execution in Monolith**: The Monolith (`core-kernel`) acts strictly as a **Client**. It must never instantiate an Orchestrator locally.
- **No Dual Writes**: State changes must occur within the Orchestrator Service transaction boundary.
