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


## D-006 Platform-Specific Frontend Port
**Decision**: Treat frontend port as platform-specific (`5000` Replit, `3000` Codespaces) instead of a single global invariant.
**Reason**: Devcontainer supervisor and Replit workflow encode different operational defaults.
**Constraint**: Keep CORS and docs in sync with both to prevent runtime confusion.
