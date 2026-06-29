> **Note: Architectural Lens (companion to the Cognitive Lab doctrine)**
> This file reframes CogniForge as an **Agentic Cognitive Runtime** — a model→tool→append
> loop whose power lives in the *layers around it*. It is the architectural complement to
> `cognitive_lab_philosophy.md` (the pedagogical doctrine) and `roadmap.md` (the north star).
> **Governing law:** every layer below is graded by `CLAUDE.md §6.6` — ACTIVE only with
> *import + call chain + runtime evidence*. Aspirational layers stay PLANNED/DORMANT.
> Decision of record: **D-146**. Last verified: **2026-06-29** (status sweep over `app/`).

# Agentic Cognitive Runtime — Doctrine

## 1. Thesis (fact-checked)

An agentic system is **not** "a smarter chatbot." It is a runtime that repeatedly gathers
context, calls a model, executes tools, appends results to state, and continues until a
text answer is produced. The loop is simple; **the engineering value is in the layers
around it** — configuration contract, skills, hooks, memory, verification, safety.

Four claims drive every design decision here. They are stated as *principles*, not as
finished features:

- **P1 — Context engineering > prompting.** The control surface is a persistent system of
  files, skills, and policies (`CLAUDE.md`, `.memory/`, `app/services/skills/`), not a
  single clever prompt.
- **P2 — Capability ≠ safety.** A more capable tool surface is a larger attack/error
  surface. Safety-critical invariants must be enforced by **deterministic gates** (hooks,
  CI, redaction skills), never by prose instructions a model "should" follow.
- **P3 — Curated memory, not bloat.** Memory stores **stable invariants and verified
  facts**, not raw conversational exhaust. Stale memory is a defect (`DOC-DEBT-001`).
- **P4 — Separate the roles.** Configuration / Procedure / Verification / Safety are
  distinct layers; a writer must never silently grade its own work (see §3).

## 2. Layer × Reality map (graded by §6.6)

Status taxonomy is verbatim from `CLAUDE.md §6.6`:
**ACTIVE** (import + call chain + runtime evidence) · **PARTIAL** (live only via fallback /
conditional / non-default branch) · **PLANNED** (designed, not built) · **DORMANT** (code
real, no live call chain / gated behind something not started) · **ZOMBIE** (no live call
chain from any production entrypoint).

| # | Layer | Realization in this repo | Status | Evidence / ref |
|---|-------|--------------------------|--------|----------------|
| 1 | Configuration / Contract | `CLAUDE.md` + `AGENTS.md` + `.memory/` | **ACTIVE** (bloated → `DOC-DEBT-001`) | loaded every session |
| 2 | Skills Engine | `app/services/skills/*` — 27 registered descriptors + `registry.py` + `/api/v1/skills` | **ACTIVE** | §0.5, D-100; `app/api/routers/skills.py` |
| 3 | Subagents / Multi-agent | Claude Code subagents (tooling); microservices as service-skills | **PARTIAL** | in-app `app/services/chat/graph/workflow.py` is **ZOMBIE** (KAgent-blocked, §6.6) |
| 4 | Hooks / Policy gate | `.claude/settings.json` hooks + CI gates (ruff / runtime_truth / skills-doctrine / guardrails) + `PedagogicalPolicyEngine` | **ACTIVE** | `app/services/skills/pedagogical_policy_engine.py` (D-144) |
| 5 | Memory | `.memory/` + BKT `student_bkt_analytics` + `tutor_state` + InMemoryCache | **ACTIVE** | D-074, D-142; `db_schema_config.py` |
| 6 | Knowledge / Retrieval | `knowledge_base/` + `knowledge_index` + Supabase `bac_exercises` (vector) | **PARTIAL** | retrieval ACTIVE; true *graph* only in DORMANT microservices (`*_retriever.py`) |
| 7 | Planner | `PedagogicalPolicyEngine` + `LearningPathSkill` (ACTIVE); planning-agent DSPy (DORMANT by default) | **PARTIAL** | D-111, D-144 |
| 8 | Reasoning | orchestrator 13-node graph + Socratic policy (ACTIVE when orchestrator up); reasoning-agent MCTS (DORMANT default) | **PARTIAL** | D-112, D-129 |
| 9 | Verification / Guardrails | `AnswerRedactionSkill` · `OutputFirewall` · `ContentIntegritySkill` · `arabic_stream_guard` · `TopicLock` | **ACTIVE** | D-086, D-113; CritiqueNode (D-109) = **PLANNED** |
| 10 | Observability | UnifiedObservability + Prometheus + Grafana + `tutor_metrics` | **ACTIVE** (in-process); OTEL export **NO-OP** | `context.md`; `observability_truth.md` |
| 11 | Context engine | harness compaction + question-aware budget (D-053) + history guards | **PARTIAL** | D-053; D-102/D-137 history guards |
| 12 | Plugin system | `app/core/registry/plugin_loader.py` + `plugin_registry.py` | **DORMANT (ZOMBIE)** | code present, **no live import** from kernel/main/routers (verified 2026-06-29) |
| 13 | Evolution engine | self-improvement / architecture intelligence | **PLANNED** | no code; aspirational only |

> **Honesty rule (do not soften):** rows 12–13 and the CritiqueNode are **not** "almost
> done." Row 12's loader exists but is a ZOMBIE until a production entrypoint imports it.
> Promoting any PARTIAL/PLANNED/DORMANT row to ACTIVE requires the full three-leg proof.

## 3. The four enforced separations

1. **Configuration** (what must never change, where the entrypoints are, how to verify) →
   `CLAUDE.md` as a *contract*, detail pushed to `.memory/` and skills.
2. **Procedure** (repeatable workflows) → Skills with one responsibility, Pydantic
   contracts, Prometheus metrics, tests, and a **live consumer** (no ZOMBIE — D-073).
3. **Verification** (deterministic) → redaction / firewall / integrity skills + CI gates.
   For tutoring: did the answer leak a final result? did the turn advance learner state?
4. **Safety** (enforced, not requested) → hooks + CI + sandbox. A model error must not be
   able to bypass a safety-critical invariant just because the prose "told it not to."

## 4. Why this matters for CogniForge

The pedagogical core already *is* an agentic runtime: state-aware progression
(`tutor_state`, D-144), honest mastery (BKT two-signal, D-126), deterministic verification
(answer redaction, D-113), and a microservices spine (D-112). This doctrine names those as
**layers** so future work targets the right layer instead of bolting logic onto the chat
path. The win condition is unchanged: shrink the **illusion gap** (`roadmap.md` §7), never
optimize session length or momentary "satisfaction."

## 5. Debt & forward pointers

- **`DOC-DEBT-001`** — CLAUDE.md is ~700 KB (encyclopedia), violating P1's "contract not
  encyclopedia." *Logged, deliberately not acted on here* (slimming a CI-gated canonical
  file is a separate, higher-risk task).
- Aspirational layers (Knowledge Graph as a true graph, Evolution engine, in-app Plugin
  activation, CritiqueNode) are the **next architectural frontier** — they enter the table
  as ACTIVE only when proven live in Codespaces with real secrets (§6.6).

**References:** thesis & evidence framing = owner research dossier (Claude Code as agentic
runtime). Pedagogical sibling = `cognitive_lab_philosophy.md`. North star = `roadmap.md`.
Skills law = `CLAUDE.md §0.5` + `app/services/skills/doctrine.py`. Runtime-truth law = §6.6.
