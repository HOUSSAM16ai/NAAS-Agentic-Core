# Architecture Memory (Full Dissection)
> Last updated: 2026-05-05

## System Shape
- Hybrid runtime: composition shell in `app/` + independently deployable services in `microservices/`.
- Architectural control point: `app/kernel.py`.
- Streaming edge authority (target): `microservices/api_gateway` as single WS ingress.

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

## WebSocket Streaming Topology (Current)
- Primary ingress:
  - `microservices/api_gateway/main.py` (`/api/chat/ws`, `/admin/api/chat/ws`)
- Relay engine:
  - `microservices/api_gateway/websockets.py::websocket_proxy`
- Compatibility fallback:
  - Legacy/compatibility WS facades still exist in monolith routes pending full purge.

## Monolith vs Microservices Status
- Current mode: **Hybrid Transitional**.
- Not a pure monolith; not yet full microservices completion.
- Main migration gap: eliminate split ownership for chat streaming + enforce one event envelope contract.

## Integration Contracts
- Service-to-service communication strictly over HTTP/gRPC style APIs.
- No cross-service database access.
- Correlation header propagation required for tracing.
