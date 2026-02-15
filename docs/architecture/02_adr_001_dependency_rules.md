# ADR-001: Architectural Dependency Rules

**Status:** Accepted
**See Also:** [ADR-002: Unified Control Plane](04_adr_002_unified_orchestration.md) (Clarifies Orchestration Authority)
**Date:** 2024-05-22
**Context:** The codebase currently suffers from circular dependencies and "God Objects" that mix HTTP, Database, and Business logic.
**Decision:** We are adopting strict Dependency Injection and Layered Architecture rules.

## 1. Intra-Domain Rules (Vertical)

Rules for dependencies *within* a single Domain (e.g., inside `Identity`):

1.  **API Layer**
    *   **Can import:** `Application`, `Domain`.
    *   **Cannot import:** `Infrastructure` (direct concrete classes).

2.  **Application Layer**
    *   **Can import:** `Domain`, `Interfaces` (defined in Domain/App).
    *   **Cannot import:** `API`, `Infrastructure` (concrete classes), `FastAPI` (HTTP context).

3.  **Domain Layer**
    *   **Can import:** *Nothing* (only Standard Lib + Pydantic/Data classes).
    *   **Cannot import:** `API`, `Application`, `Infrastructure`, `SQLAlchemy` (unless strictly typed via protocol).

4.  **Infrastructure Layer**
    *   **Can import:** `Domain` (to map data), `Application` (to implement interfaces).
    *   **Cannot import:** `API`.

## 2. Inter-Domain Rules (Horizontal)

Rules for dependencies *between* Domains:

*   **Direction:** `Core` depends on `Identity`. `Core` depends on `Overmind`.
*   **Prohibition:** `Identity` must NEVER depend on `Core` or `Overmind` (Circular Dependency Prevention).
*   **Mechanism:** Inter-domain communication should happen via **Application Layer Interfaces** or Event Bus, not direct Database joins across domains.

## 3. Enforcement

*   **Linter:** Future implementation of `import-linter` in CI.
*   **Code Review:** Reviewers must reject PRs that violate these import directions.

## 4. Exceptions

*   **Shared Kernel (`app/kernel.py`):** May bind components together (Composition Root).
*   **Utils:** Pure utility functions can be imported anywhere.
