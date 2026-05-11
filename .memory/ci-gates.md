# CI Gates — Pre-merge Required Checks
> Last updated: 2026-05-06 | Branch: `claude/autonomous-runtime-observability-pjzY9`

## Required jobs (must be green)
| Workflow | Job | What it enforces |
|---|---|---|
| `ci.yml` | `lint` | `ruff check .` + `ruff format --check .` |
| `ci.yml` | `contracts` | gateway/provider parity (`scripts/fitness/check_gateway_provider_contracts.py` + `tests/contracts/`) |
| `ci.yml` | `guardrails` | `ci_guardrails.py` + `check_no_app_imports_in_microservices.py --strict` + `check_route_registry_parity.py` + `check_tracing_gate.py` |
| `ci.yml` | `test` | full pytest suite (`tests/`) |
| `ci.yml` | `required-ci` | aggregator — fails if any required job fails |
| `structure-validation.yml` | structure-validation | `scripts/validate_structure.py` |
| `doc_integrity.yml` | doc-integrity | `CLAUDE.md` + `.memory/*` integrity, root scratch artifacts |
| **`runtime_truth.yml`** | **runtime-truth-drift-check** | `scripts/runtime_truth.py --check` matches `.runtime/truth_table.lock.json` |
| `microservices-step6-planning-agent.yml` | step6-gate | prometheus-client + prom_metrics.py + /metrics + supervisor.sh + automations.yaml + prometheus.yml + dashboard + 61 tests |
| `microservices-step7-research-agent.yml` | step7-gate | prometheus-client + tavily-python + prom_metrics.py + /metrics + supervisor.sh + automations.yaml + prometheus.yml + dashboard + 68 tests |
| `microservices-step8-reasoning-agent.yml` | `step8-gate` | prometheus-client + prom_metrics.py (11 metrics) + /metrics + ISS-039-B check + supervisor.sh (STEP 4H) + automations.yaml + prometheus.yml (step=8) + dashboard (UID cogniforge-ms-step8-reasoning-agent) + 79 tests |
| **`microservices-step11-full-skills.yml`** | **step11-gate** | **7 jobs: lint + 63 content-retrieval-skill tests + ISS-038 regression (13 cases) + intent classifier contract + 7 Prometheus metrics + ISS-042 Service Token JWT + DSPy 3.x fix (dspy.LM) (NEW — 2026-05-11)** |
| **`microservices-step12-conversation-service.yml`** | **step12-gate** | **7 jobs: static-checks (Skill contract + isolation) + metrics-gate (11 metrics) + graph-gate (LangGraph StateGraph) + lint + step12-tests (117 tests) + regression-steps-4-11 + pr-summary (NEW — 2026-05-11)** |

## What the runtime-truth gate catches
- A new importer of a `ZOMBIE` / `DORMANT` module from a live anchor (`app/api/`, `app/main.py`, `app/kernel.py`, `app/middleware/`) without an accompanying lock-file update.
- Removing a tracked capability without removing it from `CATALOG`.
- Changing an `expected_status` without regenerating the lock.

## What CI still does NOT catch (tracked as ISS-025, partial mitigation only)
1. WS frame tracing per-frame (still ISS-005). The `path_observer` covers the per-turn span; per-frame WS spans are out of scope here.
2. Persistence authority round-trip with the orchestrator awake (cannot run in CI; requires `docker compose up`).
3. Frontend Next.js build — still not in CI.

## Updating the gate intentionally
```
python scripts/runtime_truth.py --update   # rewrites .runtime/truth_table.lock.json
git add .runtime/truth_table.lock.json scripts/runtime_truth.py
git commit -m "runtime-truth: <reason>"
```
