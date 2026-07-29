# CI Gates — Pre-merge Required Checks
> Last updated: 2026-07-22 | Branch: `claude/oop-claude-md-update-e2ziez`
> **D-179 note:** the `guardrails` job now also runs `check_test_hygiene.py`,
> `check_legacy_invariants.py` (D-173), `check_model_chain_parity.py` (D-174),
> `check_no_cross_service_imports.py`, `check_ports_consistency.py`,
> `check_single_brain_control_plane.py`, `check_core_kernel_acl.py`,
> `check_abstraction_consumed.py` (D-176). The Skills Doctrine gate
> (`skills-doctrine-gate.yml` → `check_skills_doctrine.py`) and the Pedagogical-OS gate
> (`check_pedagogical_os.py`) both stay green after the BaseSkill adoption (23 skills).

## Required jobs (must be green)
| Workflow | Job | What it enforces |
|---|---|---|
| `ci.yml` | `lint` | `ruff check .` + `ruff format --check .` |
| `ci.yml` | `contracts` | gateway/provider parity (`scripts/fitness/check_gateway_provider_contracts.py` + `tests/contracts/`) |
| `ci.yml` | `guardrails` | `ci_guardrails.py` + `check_no_app_imports_in_microservices.py --strict` + `check_route_registry_parity.py` + `check_tracing_gate.py` + `check_test_hygiene.py` + `check_legacy_invariants.py` + `check_model_chain_parity.py` + `check_no_cross_service_imports.py` + `check_ports_consistency.py` + `check_single_brain_control_plane.py` + `check_core_kernel_acl.py` + `check_abstraction_consumed.py` + `check_notation_definable.py` + `check_notation_parity.py` |
| `ci.yml` | `frontend-tests` | node tests + `server.js` syntax + lockfile sync + **D-185:** OpenAPI-generated TS types are current (`generate_frontend_types.py --check`) + `npm run typecheck` |
| `skills-doctrine-gate.yml` | `check_skills_doctrine` | every skill imports from `doctrine.py`; ~15 `check_*_wired` token-assertions (BaseSkill adoption preserves all) |
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

## D-185 — the two notation gates (added 2026-07-28)

| Gate | What it enforces | Why it exists |
|---|---|---|
| `check_notation_definable.py` | Every math symbol the probability brain emits (scanned through the `BRAIN_SOURCE_FILES` manifest) has an entry in `shared/notation/registry.py`; every entry is complete; **every example is neutral** (must not contain `14`/`165`/`56`) | ISS-138: a student asked what a symbol the tutor itself printed meant, and the system could not define it. An emitted-but-undefinable symbol is a knowledge debt that becomes a catastrophe on first contact. The neutrality check stops "definition" from becoming a back door that leaks the exercise answer (D-113). |
| `check_notation_parity.py` | `shared/notation/registry.py` and the vendored `microservices/notation_service/src/notation/registry.py` are byte-identical, and **no third copy** defines `NOTATION_REGISTRY` | Constitution rules 97/98 forbid a shared business-logic library, so the service vendors the registry. Duplication without a guard is silent drift — the same class of defect ISS-138 came from. Mirrors `check_model_chain_parity.py` (D-174). |

Both are proven by a negative test: injecting drift / removing a symbol turns CI red.

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
