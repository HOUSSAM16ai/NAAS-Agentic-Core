# Observability Truth Table and Architectural Summary

## Architectural Summary
The system possesses a sophisticated observability surface designed around OpenTelemetry, Unified Observability (Monolith Facade), and a dedicated Observability Microservice. However, in default developer environments (Codespaces), most of this system acts as a hollow shell (NoOp) due to missing environment variables and infrastructure.

## Truth Table

| Component | Status | Proof |
| :--- | :--- | :--- |
| **OpenTelemetry Bootstrap** (`app/telemetry/otel_setup.py`) | DORMANT (Default) | Called by `kernel.py`, but `is_enabled()` returns false without `OTEL_EXPORTER_OTLP_ENDPOINT`. |
| **LangGraph Telemetry** (`microservices/.../telemetry.py`) | ZOMBIE / DORMANT | Imports `opentelemetry.trace`, falls back to `_NoOpSpan` when missing/inactive. |
| **API Gateway Telemetry** (`microservices/api_gateway/main.py`) | PARTIAL / DORMANT | Uses `_NoOpTracer` if `opentelemetry` missing. `log_telemetry` just writes to console logs. |
| **UnifiedObservabilityService** (`app/telemetry/unified_observability.py`) | PARTIAL | Actively buffers metrics in-memory (`_flush_metrics_to_microservice`), but lacks actual backing storage or downstream dashboard in Codespaces. |
| **Telemetry Evidence Log** (`telemetry_evidence.txt`) | ACTIVE | Hardcoded `_append_telemetry_line` used in `routes.py` for raw runtime signal captures. |
| **Observability Service** (`microservices/observability_service`) | ACTIVE (Runtime) / VOLATILE | Service boots up, accepts payloads via HTTP, but uses `InMemoryTelemetryRepository` losing data on restart. |
| **CI Guardrails** (`scripts/ci_guardrails.py`, `check_tracing_gate.py`) | ACTIVE | Actively blocks PRs if expected tokens (`TraceContextMiddleware`) are missing, but doesn't guarantee functional trace flow. |
| **Database Telemetry** | UNKNOWN / MISSING | `core/database.py` establishes asyncpg connection pools but lacks explicit query latency spans. |

## Signal Origins and Destinations
*   **Customer Chat / WS:** Signals originate in `path_observer.py` (`open_ws_turn`, `close_ws_turn`), handed to `UnifiedObservabilityService`.
*   **LangGraph Nodes:** Emit telemetry via `emit_telemetry` in `telemetry.py`, landing in stdout logs and `_NoOpSpan`.
*   **Fallback Paths:** Monitored via explicit `mark_fallback_used()` calls, aggregating into in-memory counters.

## Rules & Facts
*   Never assume metrics reach a dashboard in local dev.
*   Do not delete dormant code; CI structural checks will fail.
*   For live troubleshooting, read raw logs or `telemetry_evidence.txt`.

## Deep Systemic Vulnerabilities & Truths
*   **Trace Split-Brain:** API Gateway injects W3C `traceparent`, but `orchestrator_service` completely ignores it. Traces are severed at the HTTP boundary.
*   **AIOps Reality:** The math is real (Z-scores, trend forecasting), but the data store is an in-memory mock. It is structurally sound but operationally volatile.
*   **Async Context Safety:** `path_observer.py` uses `contextvars.ContextVar` securely. `asyncio` tasks (like WS connections) do not bleed state.
*   **Background Degradation:** The Monolith's background telemetry sync catches all errors. A dead observability microservice won't crash the monolith, but will silently drop metrics while logging errors.
