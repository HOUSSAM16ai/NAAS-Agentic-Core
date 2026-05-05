# Architecture Notes (Executable Reality)
> Last updated: 2026-05-05

## 1) Kernel Composition Pipeline
- `RealityKernel._construct_app()` applies:
  1. Base app creation
  2. Kernel spec build
  3. Middleware stack application
  4. Router mounting
  5. Optional static files setup
  6. Contract alignment validation

## 2) Middleware Strategy
- Middleware definitions are produced by `build_middleware_stack()` in `app/core/app_blueprint.py`.
- Application order is controlled by reversed insertion in `_apply_middleware()`.
- This keeps ordering declarative and deterministic.

## 3) Hybrid Boundary Pattern
- `app/` is a control-plane shell.
- Domain execution is split:
  - local services (DB-backed, in-process)
  - remote services over HTTP (orchestrator/planning/memory clients)
- Boundary discipline is explicit in `app/infrastructure/clients/*`.

## 4) Memory Agent Structure
- Entry app + lifespan + router wiring in `microservices/memory_agent/main.py`.
- Protected memory and knowledge routes depend on service-token verification.
- Data access strategy:
  - query search: `ilike` over content and tags
  - filtered search: optional tag constraints
  - eager loading: `selectinload(Memory.tags)`

## 5) Operational Inference
- This is neither pure monolith nor full decomposition.
- It is a staged migration model with API shell continuity and service extraction.
