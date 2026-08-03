> **Note: Architectural Lens (companion to the Cognitive Lab doctrine)**
> This file reframes CogniForge as an **Agentic Cognitive Runtime** — a model→tool→append
> loop whose power lives in the *layers around it*. It is the architectural complement to
> `cognitive_lab_philosophy.md` (the pedagogical doctrine) and `roadmap.md` (the north star).
> **Governing law:** every layer below is graded by `CLAUDE.md §6.6` — ACTIVE only with
> *import + call chain + runtime evidence*. Aspirational layers stay PLANNED/DORMANT.
> Decisions of record: **D-146** (the 13-layer lens) · **D-209** (the 9 orchestration layers
> that absorb them, and the gate that makes this file unable to lie).
> Last verified: **2026-08-03** (D-209 sweep). Previous sweep: 2026-06-29 (D-146).
>
> **الحالة تعيش هنا؛ القانون يعيش في**
> [`../docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md`](../docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md).
> تحرس الملفَّين بوّابة `scripts/fitness/check_agentic_orchestration.py`: حالةٌ أمام ملفٍّ
> غير موجود ⇒ CI أحمر، وخانةُ فجوةٍ فارغة ⇒ CI أحمر، وحذفُ طبقةٍ بصمت ⇒ CI أحمر.

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

**P5 — Orchestration > prompting (D-209).** The four above describe the *surface*; this one
describes the *shape*. Value has moved from "what do I ask the model?" to "who does what,
when does it start, what context does it need, how do results travel, when is it re-run,
and who reviews before merge?" A prompt is temporary, contextual and losable; a production
system needs specs, skills, agents, context management, evaluation, orchestration and
memory. The nine layers in §2 name that shape so new work targets the right layer instead
of bolting logic onto the chat path.

## 2. Layer × Reality map (graded by §6.6)

Status taxonomy is verbatim from `CLAUDE.md §6.6`:
**ACTIVE** (import + call chain + runtime evidence) · **PARTIAL** (live only via fallback /
conditional / non-default branch) · **PLANNED** (designed, not built) · **DORMANT** (code
real, no live call chain / gated behind something not started) · **ZOMBIE** (no live call
chain from any production entrypoint) — plus **SEAM** (a documented extension seat with
zero code) and **ABSENT** (written explicitly rather than left blank), both inherited from
D-207. ⛔ **No second ladder** — these are the only tokens either map may use.

### 2.a — The nine orchestration layers (canonical, D-209)

| # | الطبقة | الحامل في CogniForge | دليل | الحالة | الفجوة الصادقة |
|---|--------|----------------------|------|--------|----------------|
| 1 | Knowledge — المعرفة | مناهج (٣٧ مفهوماً) · رموز · أسس حتمية · قاعدة معرفة | `shared/curriculum/registry.py` | `ACTIVE` | الاسترجاع المتّجهي (`embedding`/HNSW/CrossEncoder) `DORMANT` بصفر نداء وقت الطلب؛ و«الرسم المعرفي» رسمٌ بالاسم لا بالبنية |
| 2 | Skills — الخبرة القابلة للتشغيل | `BaseSkill` + سجلّ المهارات + `POST /api/v1/skills` | `app/services/skills/registry.py` | `ACTIVE` | العدد مُشتَقّ من السجلّ لا مكتوباً (D-192)؛ المحرّك الاحتمالي و`gateway` مُستثنيان عمداً من التوحيد (حماية مسار الإجابة) |
| 3 | Agents — من ينفّذ | رسم المُنسِّق + `local_graph` + الخدمات-كمهارات | `app/services/chat/local_graph.py` | `PARTIAL` | تعدّد الوكلاء عبر الخدمات فقط؛ `plugin_loader` **ZOMBIE** (بلا استيراد حيّ)؛ CritiqueNode `PLANNED` (D-109) |
| 4 | Orchestration — التنسيق | مراحل الدور + سلسلة السقوط المقيسة + `compose_*` | `app/infrastructure/clients/orchestrator_client.py` | `ACTIVE` | مرحلةٌ واحدة من اثنتي عشرة خارج مرمى عقود الترانسكريبت، مُستثناةٌ بسببٍ منطوق (ISS-148) |
| 5 | Memory — الذاكرة | `TutorState` · BKT مُلحَق-فقط · FSRS · `.memory/` | `app/services/skills/bkt_engine.py` | `ACTIVE` | عمود `parsed_entities` **بلا قارئ حيّ** ويُوثَّق كذلك (D-191)؛ الكاش المعرفي طبقةُ صمود لا مسارٌ عادي |
| 6 | Evaluation — التقييم | عقود الترانسكريبت + المُقيِّم السقراطي + حُرّاس المخرَج | `tests/test_transcript_contracts.py` | `PARTIAL` | **فجوة الوهم مقياسُ النجاح الوحيد ولم تُحسَب حيّاً بعد** (M9)؛ CritiqueNode `PLANNED`؛ لا محرّك تجريب A/B |
| 7 | Governance — الحوكمة | بوّابات اللياقة + محرّك السياسة التربوية + ADRs | `.github/workflows/ci.yml` | `ACTIVE` | حماية الفرع تعيش خارج المستودع فلا يفرضها كود؛ ودَينان مُجمَّدان (`no_new_any` · `router_domain`) يتقلّصان فقط |
| 8 | Infrastructure — البنية التحتية | FastAPI · Next · Postgres · Prometheus/Grafana · `shared/messaging` | `docker-compose.yml` | `PARTIAL` | الطوبولوجيتان تختلفان في خمسة منافذ؛ عامل Temporal **لم يتّصل قطّ**؛ OTLP بلا `OTEL_EXPORTER_OTLP_ENDPOINT` = بلا أثر |
| 9 | Humans — البشر | شرط الـADR · قرار المالك · لوحة الوليّ | `docs/adr/ADR-TEMPLATE.md` | `PARTIAL` | **بلا فارضٍ آلي كامل عمداً** — جودة الحكم الهندسي لا تُفرَض بآلة؛ الفوارض الجزئية: `check_abstraction_consumed` + `check_memory_coherence` |

### 2.b — الآفاق الثلاثة (طموحٌ مُصان، لا مُنجَزٌ مُدَّعى)

| # | الأفق | ما يعنيه | دليل | الحالة | الفجوة الصادقة |
|---|-------|----------|------|--------|----------------|
| 10 | Evolution — التطوّر | النظام يتعلّم من كل عطبٍ ومراجعةٍ ضمن حوكمة | `.memory/roadmap.md` | `PLANNED` | صفر كود. شرط الترقية: محرّك يقترح تغييراً **ويُقيَّم قبل تطبيقه**، لا تعديلٌ ذاتي بلا بوّابة |
| 11 | Organization — المؤسسة | Knowledge→Skills→Agents→Humans→Customers بدل Departments→Employees | `docs/architecture/EXTENSION_SEAMS.md` | `SEAM` | مقعدٌ موثَّق بصفر كود؛ المستودع اليوم فريقٌ واحد ومالكٌ واحد |
| 12 | Civilization — الحضارة | امتداد النموذج إلى التعليم والطبّ والبحث والصناعة | `docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md` | `ABSENT` | **رؤية استشرافية وتُكتب رؤيةً** — المقالة المصدر تُميّزها صراحةً عن الواقع الحالي. تُذكَر لئلّا تُنسى، ولا تُدَّعى |

### 2.c — العدسة الأصلية: الطبقات الثلاث عشرة (D-146) — محفوظة بنصّها داخل التسع

الجدول الأصلي يبقى كما هو، مع عمودٍ يربط كل صفٍّ بطبقته في §2.a — فلا سُلَّم ثانٍ ولا فقدان
تفصيل. **تصحيحٌ واحد (D-209/D-192):** الصفّ 2 كان يكتب عددَ الواصفات يدوياً (27)
بينما المُشتَقّ من `registry.py` أكبر — استُبدل الرقمُ بمصدره.

| # | Layer | Realization in this repo | Status | Evidence / ref | ↳ §2.a |
|---|-------|--------------------------|--------|----------------|--------|
| 1 | Configuration / Contract | `CLAUDE.md` + `AGENTS.md` + `.memory/` | **ACTIVE** (bloated → `DOC-DEBT-001`) | loaded every session | 7 |
| 2 | Skills Engine | `app/services/skills/*` — descriptors registered in `registry.py` (**count derived, never hand-written** — D-192) + `/api/v1/skills` | **ACTIVE** | §0.5, D-100; `app/api/routers/skills.py` | 2 |
| 3 | Subagents / Multi-agent | Claude Code subagents (tooling); microservices as service-skills | **PARTIAL** | in-app `app/services/chat/graph/workflow.py` is **ZOMBIE** (KAgent-blocked, §6.6) | 3 |
| 4 | Hooks / Policy gate | `.claude/settings.json` hooks + CI gates (ruff / runtime_truth / skills-doctrine / guardrails) + `PedagogicalPolicyEngine` | **ACTIVE** | `app/services/skills/pedagogical_policy_engine.py` (D-144) | 7 |
| 5 | Memory | `.memory/` + BKT `student_bkt_analytics` + `tutor_state` + InMemoryCache | **ACTIVE** | D-074, D-142; `db_schema_config.py` | 5 |
| 6 | Knowledge / Retrieval | `knowledge_base/` + `knowledge_index` + Supabase `bac_exercises` (vector) | **PARTIAL** | retrieval ACTIVE; true *graph* only in DORMANT microservices (`*_retriever.py`) | 1 |
| 7 | Planner | `PedagogicalPolicyEngine` + `LearningPathSkill` (ACTIVE); planning-agent DSPy (DORMANT by default) | **PARTIAL** | D-111, D-144 | 4 |
| 8 | Reasoning | orchestrator 12-node graph + Socratic policy (ACTIVE when orchestrator up); reasoning-agent MCTS (DORMANT default) | **PARTIAL** | D-112, D-129 | 3 |
| 9 | Verification / Guardrails | `AnswerRedactionSkill` · `OutputFirewall` · `ContentIntegritySkill` · `arabic_stream_guard` · `TopicLock` | **ACTIVE** | D-086, D-113; CritiqueNode (D-109) = **PLANNED** | 6 |
| 10 | Observability | UnifiedObservability + Prometheus + Grafana + `tutor_metrics` | **ACTIVE** (in-process); OTEL export **NO-OP** | `context.md`; `observability_truth.md` | 8 |
| 11 | Context engine | harness compaction + question-aware budget (D-053) + history guards | **PARTIAL** | D-053; D-102/D-137 history guards | 4 |
| 12 | Plugin system | `app/core/registry/plugin_loader.py` + `plugin_registry.py` | **DORMANT (ZOMBIE)** | code present, **no live import** from kernel/main/routers (verified 2026-06-29) | 3 |
| 13 | Evolution engine | self-improvement / architecture intelligence | **PLANNED** | no code; aspirational only | 10 |

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

- **`DOC-DEBT-001`** — CLAUDE.md is an encyclopedia rather than a contract, violating P1.
  *Partially acted on:* D-173 moved ~11,250 lines verbatim to
  `docs/archive/constitution-history/`, D-188 moved the dated narrative out, and a
  shrink-only line ratchet now guards it (`check_memory_coherence`). The remaining debt is
  §0 and §6.7, which are permanent law rather than narrative — they stay.
- Aspirational layers (Knowledge Graph as a true graph, Evolution engine, in-app Plugin
  activation, CritiqueNode) are the **next architectural frontier** — they enter the table
  as ACTIVE only when proven live with real secrets (§6.6). Each now carries a numbered
  roadmap row so the ambition is tracked rather than merely labelled (D-209).

**References:** thesis & evidence framing = owner research dossier (Claude Code as agentic
runtime) + the "AI Agentic Developer → AI Orchestration Engineer" dossier (D-209).
Pedagogical sibling = `cognitive_lab_philosophy.md`. North star = `roadmap.md`.
Skills law = `CLAUDE.md §0.5` + `app/services/skills/doctrine.py`. Runtime-truth law = §6.6.
Orchestration law = `docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md`.
