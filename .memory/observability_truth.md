# Observability Truth Table and Runtime Realities

## System Reality
The following component status represents strictly what is proven by import + call chain + runtime evidence. Do not hallucinate capabilities beyond what is listed as `ACTIVE` or `PARTIAL`.

| Component | Status | Proof |
|---|---|---|
| In-Process Metrics (Prometheus) | ACTIVE | Exposes `/api/v1/observability/prometheus`. Read by native Prometheus binary. |
| Native Grafana Dashboards | ACTIVE | Runs on port 3001 via `supervisor.sh` in devcontainer. |
| Telemetry Evidence Log | ACTIVE | Path functions append raw state to `telemetry_evidence.txt`. |
| GitHub Actions validation | ACTIVE | `observability_validation.yml` asserts imports and YAML validity. |
| `WsTurnSpan` & `path_observer` | PARTIAL | Captures turn metrics. Lacks per-frame tracing (ISS-005). |
| UnifiedObservabilityService | PARTIAL | Memory queues hold traces/metrics. Drops metrics silently if AIOps microservice is down. |
| AIOps (observability_service) | PARTIAL | Accessible but ephemeral (`InMemoryTelemetryRepository`). Resets completely on reboot. |
| OpenTelemetry Traces & Logs | DORMANT | `otel_setup.py` bypasses load without `OTEL_EXPORTER_OTLP_ENDPOINT`. |
| Docker-based Grafana/Tempo/Loki | DORMANT | Unused unless `docker compose -f docker-compose.yml up -d` is run. |
| LangGraph Tracing | DORMANT | Falls back to internal `_NoOpSpan` without active OTel setup. |

## Deep Diagnostic Realities
1. **Trace Split-Brain**: The API Gateway passes W3C `traceparent` headers to Orchestrator Service, but Orchestrator and downstream LangGraph nodes ignore them. Distributed tracing is structurally broken at this boundary.
2. **Volatile Data**: All complex logic in `observability_service` (Z-scores, trend lines) is purely in-memory and therefore volatile.

## Observability Principles
* **Diagnosis over Decoration:** Observability is for diagnosis, not decoration.
* **Metric Evidence:** Metrics require runtime evidence to be trusted.
* **Separation of Concerns:** Traces and metrics are separate disciplines.
* **Cardinality Constraints:** High-cardinality labels are dangerous and strictly forbidden.
* **Semantic Contracts:** Semantic meaning must exist before a metric is accepted.

## Rules for AI Sessions
* **Do NOT assume traces or correlated logs exist.** Unless you manually boot the Docker Compose observability stack, Tempo/Loki are dead.
* **Use Native Metrics.** If you need evidence, use Prometheus metrics surfaced via native Grafana on port 3001, or manual stdout logs.
* **Do not remove structural hooks.** CI checks enforce the *presence* of hooks like `open_ws_turn` or `TraceContextMiddleware`. Deleting dormant observability code will break the CI gate.
* **Require Runtime Evidence:** If there is no runtime evidence (logs, Prometheus counters, DB writes) for an observability capability, treat it as ZOMBIE/DORMANT. Do not hallucinate capabilities.
