# Observability Truth Table and Runtime Realities

## System Reality
The following component status represents strictly what is proven by import + call chain + runtime evidence. Do not hallucinate capabilities beyond what is listed as `ACTIVE` or `PARTIAL`.

| Component | Status | Proof |
|---|---|---|
| In-Process Metrics (Prometheus) | ACTIVE | Exposes `/api/v1/observability/prometheus`. Read by native Prometheus binary. Only active when FastAPI is running (requires `DATABASE_URL`). |
| Native Grafana Dashboards | ACTIVE (infrastructure) | Runs on port 3001 via `supervisor.sh:launch_mission_control()` as native binary `/opt/grafana/bin/grafana-server`. Confirmed 2026-05-09: health check passes. Runs independently of FastAPI. |
| Native Prometheus | ACTIVE (infrastructure) | Runs on port 9090 via `supervisor.sh:launch_mission_control()` as native binary `/opt/prometheus/prometheus`. Confirmed 2026-05-09: health check passes. Shows `cogniforge-fastapi=0` when FastAPI is down. |
| Telemetry Evidence Log | ACTIVE | Path functions append raw state to `telemetry_evidence.txt`. |
| GitHub Actions validation | ACTIVE | `observability_validation.yml` asserts imports and YAML validity. |
| `WsTurnSpan` & `path_observer` | PARTIAL | Captures turn metrics. Lacks per-frame tracing (ISS-005). |
| UnifiedObservabilityService | PARTIAL | Memory queues hold traces/metrics. Drops metrics silently if AIOps microservice is down. |
| AIOps (observability_service) | PARTIAL | Accessible but ephemeral (`InMemoryTelemetryRepository`). Resets completely on reboot. |
| OpenTelemetry SDK (`otel_setup.py`) | ACTIVE (no-op without `OTEL_EXPORTER_OTLP_ENDPOINT`) | Imported and called at `app/kernel.py:157,184`. Executes but produces no spans/traces when endpoint unset. Confirmed 2026-05-09. See runtime_truth.md row 30. |
| Docker-based Grafana/Tempo/Loki | DORMANT | Unused unless `docker compose -f docker-compose.yml up -d` is run. The native binary path (above) replaced this for default Codespaces. |
| LangGraph Tracing | DORMANT | Falls back to internal `_NoOpSpan` without active OTel setup. |

## Deep Diagnostic Realities
1. **Trace Split-Brain**: The API Gateway passes W3C `traceparent` headers to Orchestrator Service, but Orchestrator and downstream LangGraph nodes ignore them. Distributed tracing is structurally broken at this boundary.
2. **Volatile Data**: All complex logic in `observability_service` (Z-scores, trend lines) is purely in-memory and therefore volatile.

## Observability Principles
* **Runtime Truth over Synthetic Dashboards:** Always prioritize actual runtime evidence over what a synthetic or aspirational dashboard claims.
* **Instrumentation First, Visualization Second:** Never build dashboards that outpace actual code instrumentation. The underlying data source must be solid first.
* **Diagnosis over Decoration:** Observability is for debugging and investigation, not just for show. Every dashboard must support active debugging.
* **Unknown is Better than Fake Certainty:** Do not present dormant systems as healthy. If a system is not actively emitting data, it should be marked as unknown or dormant.
* **Metric Evidence:** Metrics require real runtime evidence to be trusted. Do not hallucinate or mock metric data in production.
* **Separation of Concerns:** Traces and metrics are different disciplines. Treat them independently when instrumenting and debugging.
* **Cardinality Constraints:** High-cardinality labels are dangerous and strictly forbidden as they can crash the metrics backend.
* **Semantic Contracts:** Semantic meaning must exist before a metric is accepted. You must know what a metric means before emitting it.

## Rules for AI Sessions
* **Do NOT assume traces or correlated logs exist.** Unless you manually boot the Docker Compose observability stack, Tempo/Loki are dead.
* **Use Native Metrics.** If you need evidence, use Prometheus metrics surfaced via native Grafana on port 3001, or manual stdout logs.
* **Do not remove structural hooks.** CI checks enforce the *presence* of hooks like `open_ws_turn` or `TraceContextMiddleware`. Deleting dormant observability code will break the CI gate.
* **Require Runtime Evidence:** If there is no runtime evidence (logs, Prometheus counters, DB writes) for an observability capability, treat it as ZOMBIE/DORMANT. Do not hallucinate capabilities.
