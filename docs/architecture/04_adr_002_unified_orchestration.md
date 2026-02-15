# ADR-002: Unified Control Plane & Orchestration Sovereignty

**Status:** Accepted
**Date:** 2024-05-25
**Context:**
The system previously suffered from a "Split-Brain Orchestration Authority" risk. Two components claimed ownership of mission execution:
1.  **`app/services/overmind` (Core Kernel):** The monolithic implementation handling complex state, locking, and execution.
2.  **`microservices/orchestrator_service` (Microservice):** A standalone service that exposed parallel endpoints for mission creation.

This duality led to ambiguity in ownership, potential data inconsistencies, and confusion regarding the "Source of Truth" for mission states.

**Decision:**
We are enforcing a **Strict Single Control Plane** architecture.

1.  **Sole Authority:** The `app/services/overmind` module is the **only** authorized orchestrator. It is the "Brain" of the system.
2.  **Decommissioning:** The `microservices/orchestrator_service` is officially **deprecated and removed**. It must not be reintroduced.
3.  **Routing:** All mission-related API traffic must be routed to the Core Kernel via the API Gateway's catch-all or specific `overmind` routes, never to a standalone orchestrator service.
4.  **State Management:** The `cogniforge.db` accessed via the Core Kernel's `MissionStateManager` is the single source of truth for all mission lifecycles.

**Consequences:**
*   **Positive:** Eliminates race conditions and "split-brain" scenarios. Centralizes logic for easier debugging and observability.
*   **Negative:** Increases load on the Core Kernel (Monolith), which must be managed via horizontal scaling of the kernel workers if necessary.
*   **Compliance:** Any future "Orchestrator" functionality must be implemented as a module within `app/services/overmind` or as a dumb worker controlled *by* the Overmind, not as a sovereign peer.
