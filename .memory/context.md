# Context Snapshot
> Last updated: 2026-05-05

## Product
- CogniForge: AI tutoring platform for Algerian BAC students.

## Runtime Truth
- `app/` remains the control shell and integration boundary.
- `microservices/` hosts independent capabilities (user/observability/reasoning/research/gateway and others per environment).
- WebSocket chat streaming operationally prefers API Gateway ingress, while compatibility paths in monolith still indicate transitional state.

## Architectural State
- Official interpretation: **Controlled Hybrid** using strangler migration.
- Decision pressure area: chat WebSocket ownership and event-contract unification.

## Documentation Contract
- Any architectural change requires synchronized updates across:
  - `CLAUDE.md`
  - `.memory/architecture.md`
  - `.memory/decisions.md`
  - `.memory/context.md`
