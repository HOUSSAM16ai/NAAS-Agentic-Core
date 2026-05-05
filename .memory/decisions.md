# Architectural Decisions (Current)
> Last updated: 2026-05-05

## D-001 Hybrid Runtime Is Canonical
**Decision**: Treat architecture as hybrid transitional.
**Evidence**: Kernel composition in `app/` + network delegation in microservice clients.

## D-002 Code-First Documentation
**Decision**: `.memory` files must reflect executable code paths, not environment folklore.
**Reason**: Prevent stale guidance and incorrect assumptions.

## D-003 Memory Agent Is a First-Class Service
**Decision**: Preserve memory agent documentation around lifecycle, Zero Trust route protection, and layered design.
**Evidence**: `microservices/memory_agent/main.py` + `src/*` layering.

## D-004 Boundary Integrity
**Decision**: Keep monolith-to-service integration through HTTP clients with local DTO definitions where needed.
**Reason**: Avoid tight coupling and cross-package schema leakage.

## D-005 Environment-Conditional Reachability
**Decision**: Document microservice reachability as environment-dependent.
**Reason**: Compose/dev/prod topologies differ.
