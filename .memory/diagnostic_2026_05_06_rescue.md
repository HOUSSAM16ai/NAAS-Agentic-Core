# Architecture Rescue Diagnostic — 2026-05-06
> Branch: `claude/architecture-rescue-diagnostic-wUfbE` (third independent audit).
> Mode: READ-ONLY on application source code. Only `CLAUDE.md`, `.memory/`, and CI workflow files were modified. No application code touched.
> Companion docs: `CLAUDE.md` §6.9 (verdict + corrections), `.memory/runtime_truth.md` (rows + branch ledger).

---

## 1. Capability reality (one-line answer)
**The system uses ~10% of its advertised agentic capability surface in default Codespaces deployment.** This number is unchanged across three audits (2026-05-05, 2026-05-06×2). Movement requires an explicit wiring PR with a new three-part proof in the truth table.

## 2. What is actually live (production WS request)
1. FastAPI app + `ObservabilityMiddleware` on every HTTP request.
2. Auth + `/api/security/*`, `/api/v1/*`, `/v1/content/*`, admin REST.
3. WS endpoints `/api/chat/ws` (customer) and `/admin/api/chat/ws` (admin).
4. `OrchestratorClient.chat_with_agent` (sole chat boundary).
5. Fallback chain inside `OrchestratorClient`: file-intelligence → exercise-retrieval → `local_graph.run_local_graph` (2 nodes) → general-chat.
6. Persistence: Monolith writes both USER and (fail-safe) ASSISTANT to `customer_messages` / `admin_messages`. D-006 handshake awaits a live orchestrator.
7. `_emit_terminal_frames` (single emitter, single-frame guarantee per turn).
8. Frontend: Next.js → `/api/*` rewrites → `localhost:8000` (port 3000 Codespaces / 5000 Replit).
9. WebSocket: `frontend/app/hooks/useRealtimeConnection.js:56` → subprotocol `["jwt", token]`.
10. Cache: `app/caching/factory.py:71` falls back to `InMemoryCache` when Redis unset.
11. Pre-warm: `app/kernel.py:239` imports `local_graph`; `app/kernel.py:58, 208` wires `UnifiedObservability`.

## 3. What is dead, dormant, or loaded-not-invoked
- **ZOMBIE**: `app/services/chat/graph/workflow.py` + `graph/nodes/{super_reasoner,planner,researcher,writer,procedural_auditor,reviewer}.py`, `graph/components/*`, `graph/nodes/supervisor.py`, `app/services/chat/memory_engine.py`, `app/drivers/*`, `app/services/kagent/*`, `app/services/chat/agents/{orchestrator,education_council,admin,curriculum,analytics,refactor,testing_agent,…}.py`.
- **DORMANT**: `microservices/*` (all 10), `app/services/mcp/*`, `app/core/integration_kernel/*` (class is `IntegrationKernel`, not `RealityKernel`), `microservices/research_agent/.../{reranker,strategies,hybrid,llama_retriever}.py`, DSPy under `microservices/orchestrator_service/.../graph/{main,search,supervisor}.py` and `microservices/research_agent/src/search_engine/query_refiner.py`, dual-Redis design.
- **PARTIAL (loaded-not-invoked)** — new tier: `intent_detector.py`, `tool_router.py`, `tool_access.py`, `dispatcher.py`, `intent_registry.py`, `education_policy_gate.py`, `orchestration_rollout.py`, `ChatOrchestrator`, `CustomerChatStreamer`, `AdminChatStreamer`. Imported and instantiated through `CustomerChatBoundaryService` / `AdminChatBoundaryService`, but their `detect()` / `authorize_intent()` / `stream_response()` methods are never reached from a real WS turn.
- **PARTIAL (split)**: `CustomerChatBoundaryService` / `AdminChatBoundaryService` — persistence methods ACTIVE; streaming methods unreachable.
- **PARTIAL (fallback)**: `local_graph.py` — runs on every turn in default Codespaces because the orchestrator URL is unset; uses `ainvoke` (ISS-023).
- **ACTIVE**: FastAPI bootstrap, `RealityKernel` (`app/kernel.py:103`, instantiated `app/main.py:22, 49`), `UnifiedObservability`, `OrchestratorClient.chat_with_agent`, `_emit_terminal_frames`, 9 routers in `app/api/routers/registry.py:21-35`.

## 4. Confirmed corrections to prior truth table
- **Row 12** (`app/core/integration_kernel/runtime.py`): the class name in the existing table (`RealityKernel`) is wrong — the actual class is `IntegrationKernel` (`runtime.py:13`). The verdict (ZOMBIE) still holds. `RealityKernel` (the live one) is in `app/kernel.py:103`. Updated in `runtime_truth.md`.
- **Row 21** (top-level chat helpers): updated from `ZOMBIE/UNKNOWN` → `PARTIAL (loaded-not-invoked)` because the boundary service imports them on the live path. They run `__init__` but their core methods are never called.
- **Rows 26 and 27** (new): boundary services and chat streamers added with explicit "split active" / "loaded-not-invoked" classifications.

## 5. CI as a quality gate — current state and gaps
### What CI enforces today (HARD gates, blocks merge)
- `.github/workflows/ci.yml` → `required-ci` aggregator: ruff (format + check), pydantic / provider parity contracts, AST guardrails (`scripts/ci_guardrails.py`, `check_no_app_imports_in_microservices.py --strict`, `check_route_registry_parity.py`, `check_tracing_gate.py`), pytest with coverage.
- `.github/workflows/structure-validation.yml` → `python scripts/validate_structure.py`.
- `.github/workflows/doc_integrity.yml` (added in this branch) → `CLAUDE.md` and `.memory/*.md` exist + non-empty, no scratch artifacts in repo root, no dated diagnostic patterns outside `docs/archive/`.

### What CI does NOT enforce (ISS-025)
1. **D-006 round-trip integration** — `compatibility_facade=True` + `persisted=true` echo, exactly-once row write under load. Static contract test exists; no live round-trip. Cannot run without microservice stack up.
2. **Terminal-frame integrity contract** — exactly one `assistant_final` OR one `error` per turn, plus exactly one `persisted` event. Single-emitter helper exists; no test pins it.
3. **Truth-table sync gate** — should fail when a ZOMBIE acquires a new importer in `app/api/`, `app/main.py`, `app/kernel.py`, or `local_graph.py` without a matching `runtime_truth.md` row update.
4. **Frontend build / type check** — Next.js never compiles in CI; UI regressions only surface at runtime.
5. **Microservices smoke test** — no `docker compose up` + health-curl in CI.

### Manual-only workflows (not gating)
- `.github/workflows/comprehensive_testing.yml` (`workflow_dispatch` only).
- `.github/workflows/omega_pipeline.yml` (`workflow_dispatch` only).
- `.github/workflows/knowledge_ingestion.yml` (path-scoped on `knowledge_base/**`; dry-run when `MEMORY_AGENT_API_URL` unset).

## 6. Markdown debt — inventory (no deletions performed)
> Policy is in CLAUDE.md §15. Ground truth diverges: `docs/archive/` does not exist; old reports were never moved.

### Repo-root scratch artifacts (delete in a follow-up PR)
`api_coverage.txt`, `api_coverage_final.txt`, `api_coverage_final_v2.txt`, `proof_output.txt`, `app_imports.txt`, `commit_message.txt`, `telemetry_evidence.txt`, `collection_errors.txt`, `core_errors.txt`, `services_errors.txt`, `services_errors_2.txt`, `services_errors_3.txt`, `err_data_mesh.txt`, `err_system.txt`, `patch_lint.diff`, `patch_context.diff`, `ruff_output.txt`, `ruff_output_2.txt`, `ruff_check_verify.txt`, `ruff_format_verify.txt`, `Screenshot_20260307-055153.png`, `Screenshot_20260307-055230.png`, `verification_mission_selector.png`, `verification_admin_mission_selector.png`. Total: ~24 files. None are referenced from any live `.md`.

### Aspirational / target-state markdown (consolidate or move)
- `ARCHITECTURE.md` (root, 1.8K) — duplicates `docs/architecture/MICROSERVICES_CONSTITUTION.md`. Merge into CLAUDE.md as a callout or delete; do not maintain a second copy.
- `LangGraph_Architectural_Blueprint.md` (root, 12K) — describes DORMANT orchestrator-side multi-agent graph. Superseded by §6.6 / §6.8 / §6.9. Move to `docs/archive/` or delete.
- `AGENTS-IMPROVEMENT-SPEC.md` (root, 14K) — unapplied audit of `AGENTS.md` (2026-04-28). Either apply its recommendations and delete, or archive.
- `replit.md`, `README_MIGRATIONS.md`, `SCIENTIFIC_RESEARCH_APPLICATIONS.md`, `REPO_READINESS_CHECKLIST.md` — re-evaluate; consolidate into the canonical operational docs or move to `application/` / `docs/archive/`.

### Phase / forensic dumps in `docs/` and `docs/diagnostics/`
- `docs/PHASE_18_*.md` (2 files), `docs/PHASE_19_*.md` (5 files) — phases concluded; findings codified in CLAUDE.md.
- `docs/diagnostics/*` (14+ files including `MULTI_AGENT_CATASTROPHIC_DIAGNOSIS_2026-02-11.md`, `architectural_deep_diagnosis_2026-02-24.md`, `FORENSIC_BASELINE_2026-02-27.md`, `ULTRA_FORENSIC_*.md`, `ULTRA_SURGICAL_DIAGNOSTIC_REPORT_V7.md`).
- `docs/CS51_*`, `docs/CS61_*`, `docs/CS73_*` (5 files) — appear to be course notes (CS50/CS61/CS73) not project docs.
- `docs/architecture/CONTEXT_BLINDNESS_*.md` (4 files), `docs/architecture/MONOLITH_*.md`, `docs/architecture/*_RUNBOOK.md` (5 files) — historical migration runbooks.

### What MUST stay (canonical / operational)
`CLAUDE.md`, `.memory/*` (10 files), `README.md`, `AGENTS.md`, `CHANGELOG.md`, `SECURITY.md`, `CONTRIBUTING.md`, `LICENSE`, `CODE_OF_CONDUCT.md`, `GOVERNANCE.md`, `ROADMAP.md`, `DATA_POLICY.md`, `DATA_PROTECTION.md`, `SAFEGUARDING.md`, `docs/architecture/MICROSERVICES_CONSTITUTION.md`, `docs/ARCH_MICROSERVICES_CONSTITUTION.md`, `docs/architecture/PRINCIPLES.md`, `docs/architecture/adr/004_*` and `005_*`, `docs/contracts/*`, `docs/guides/*`, `docs/ai_skills/*`, `docs/quality/*`, `docs/core/*`, `docs/config/*`, `docs/db/*`, `docs/cli/*`, `docs/gateways/*`, `docs/governance/*`, `docs/migration/*`, `docs/API_FIRST_*`, `docs/MICROSERVICES_DEPLOYMENT_GUIDE.md`, `docs/DEPLOYMENT_GUIDE.md`.

## 7. Rules Claude must apply in future sessions (re-affirmed)
1. Open `CLAUDE.md` §6.5, §6.6, §6.8, §6.9, plus `.memory/runtime_truth.md` before any change to chat / agent / persistence / WS layers.
2. Classify the touched component using the truth table. Missing → UNKNOWN until proved.
3. Adding a new importer of a ZOMBIE/DORMANT module from `app/api/`, `app/main.py`, `app/kernel.py`, or `local_graph.py` requires updating the truth table in the **same** PR. The new doc-integrity workflow flags drift.
4. Never duplicate `_emit_terminal_frames`. Never silence the `persisted` flag. Never re-introduce dual-write.
5. Never assume the microservice stack is up. New code that requires it must be gated on `ORCHESTRATOR_SERVICE_URL` and marked DORMANT until proven.
6. "Loaded but never invoked" is `PARTIAL (loaded-not-invoked)`, not ACTIVE. Use that exact label.
7. Do not delete a ZOMBIE/DORMANT file on sight — promote (with proof), archive (with note), or delete with ADR.

## 8. Remaining unknowns (do not guess)
- Real GitHub branch-protection state for `main` — local git cannot read it; needs a `gh api` round-trip from a privileged context.
- Whether any pull request currently sits in the `main` queue with red checks blocked by something other than the workflows enumerated above — not visible from the local repo.
- Frontend type-checking status — Next.js never compiles in CI; UI may have type errors that runtime hasn't surfaced.
- Whether `tests/architecture/test_persistence_authority.py` actually exercises the round-trip when CI runs without a microservice stack — believed to be a static-only contract test.

## 9. Closing rule
> Any component that does not have all three of `import` + `call chain` + `runtime evidence` reaching from `app/main.py` is treated as DORMANT or ZOMBIE until the contrary is proven. **"Loaded but never invoked" is PARTIAL, not ACTIVE.**
