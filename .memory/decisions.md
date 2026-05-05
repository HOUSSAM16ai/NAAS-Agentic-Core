# Architecture Decisions Ledger
> Last updated: 2026-05-05

## D-001
Hybrid architecture is canonical until full decomposition is complete.

## D-002
`app/kernel.py` is the authoritative composition root.

## D-003
Routers are delivery adapters only; business logic stays in services/domain layers.

## D-004
Cross-boundary communication is API-first only; direct DB coupling is forbidden.

## D-005
Architecture documentation must be code-evidenced and updated in the same PR.
