# Runtime Rules (Observability Truth)

- Required proof triplet for any observability claim:
  1) Import anchor.
  2) Live call chain from kernel/router.
  3) Runtime evidence (metric/log/trace/CI artifact).
- Missing any leg => UNKNOWN.
- Classify each component: ACTIVE / PARTIAL / DORMANT / ZOMBIE / UNKNOWN.
- Treat OTel stack as PARTIAL by default unless OTLP endpoint + collector + backend signals are observed.
- Before merge: verify workflows `ci.yml`, `observability_validation.yml`, `runtime_truth.yml` are green and relevant telemetry fields still emitted.
- **Reasoning about Truth:** Future agents must inherit the discipline of verifying capabilities via the truth table (`.runtime/truth_table.lock.json`) rather than assuming aspirational architecture docs are real.
- **Uncertainty vs Evidence:** When there is uncertainty, do not synthesize or assume positive state. Default to UNKNOWN or DORMANT until explicit runtime evidence (logs, DB writes, metrics) proves otherwise. Always favor runtime evidence over documented claims.
