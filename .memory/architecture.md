# Architecture Memory (Full Dissection)
> Last updated: 2026-05-05

## System Shape
- Hybrid runtime: composition shell in `app/` + independently deployable services in `microservices/`.
- Architectural control point: `app/kernel.py`.

## Layered Decomposition
1. Ingress/UI layer
2. API composition layer (`app/api/*`)
3. Core/service layer (`app/core/*`, `app/services/*`)
4. Remote-integration layer (`app/infrastructure/clients/*`)
5. Microservice execution layer (`microservices/*`)

## Kernel Pipeline
- Build FastAPI app.
- Build declarative blueprint.
- Apply middleware in deterministic order.
- Mount routers from registry.
- Validate contract alignment.

## Integration Contracts
- Service-to-service communication strictly over HTTP/gRPC style APIs.
- No cross-service database access.
- Correlation header propagation required for tracing.
