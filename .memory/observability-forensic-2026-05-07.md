# Observability Forensic Snapshot — 2026-05-07

## Evidence grading
- CONFIRMED: import + call chain + runtime proof in repo/CI artifacts.
- LIKELY: import + call chain, runtime depends on env not executed in this audit.
- SUSPECTED: partial clues only.
- UNKNOWN: no sufficient proof.

## Active/partial/dormant/zombie map
- ACTIVE: HTTP observability middleware path; WS turn observer hooks; Prometheus scrape endpoint; observability-validation workflow; runtime-truth drift workflow.
- PARTIAL: OTel exporters/instrumentors (enabled only when OTLP endpoint exists); fallback-specific counters.
- DORMANT: microservices observability service in default monolith runtime unless separately deployed.
- ZOMBIE: any dashboard/collector claim without runtime signal in current environment.

## Do-not-assume rules
- No live signal => capability is UNKNOWN.
- CI green != collector/dashboard healthy.
- Port forwarding != service alive.
- Docs statements are non-authoritative without runtime artifact.
