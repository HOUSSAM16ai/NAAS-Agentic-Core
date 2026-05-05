# Project Context (Code-Verified)
> Last updated: 2026-05-05

## Identity
- Repo: `NAAS-Agentic-Core`
- Product: CogniForge educational AI platform
- Architecture reality: **Hybrid transitional runtime**
  - API composition shell in `app/`
  - Selected capabilities delegated over HTTP to microservices clients

## Runtime Topology (from code)
1. `app/kernel.py` builds FastAPI through a pipeline (middleware + routers + optional static).  
2. `app/core/app_blueprint.py` declares middleware stack and router registry as data.  
3. Routers call service/infrastructure layers; cross-service calls use HTTP clients.  
4. Examples of remote delegation from monolith shell:
   - Orchestrator: `app/infrastructure/clients/orchestrator_client.py`
   - Planning: `app/infrastructure/clients/planning_client.py`
   - Memory: `app/infrastructure/clients/memory_client.py`

## Memory Service Context
- Service app: `microservices/memory_agent/main.py`
- Protected routes enforce token verification using `verify_service_token`.
- Layering:
  - API: `microservices/memory_agent/src/api/knowledge.py`
  - Service: `microservices/memory_agent/src/services/memory_service.py`
  - Repository: `microservices/memory_agent/src/repositories/memory_repository.py`

## Guardrails
- Avoid claims tied to one hosting platform only.
- Document architecture from executable code paths, not environment assumptions.
