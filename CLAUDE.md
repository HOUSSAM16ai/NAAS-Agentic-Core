# CogniForge — Claude Code Context

> **The system is not a Chat Tutor. It is a Cognitive Lab / Thinking Engine that models, tests, and improves student reasoning.**
> Chat is an assistive interface only. The platform core is: Interactive Object UI, Cognitive Modeling, Error Memory, Adaptive Generation, and Simulation.
> **AI tutor for Algerian students** | FastAPI 8000 + Next.js 5000 + LangGraph 1.1.10
> Arabic / French / Darija | BAC preparation platform

---

## 0. Core System Doctrine: The Cognitive Lab

**Single writer. Single terminal frame. No silent failure.** These are operational laws, not aspirations.

The system must preserve the following principles permanently. Every future agent must inherit and obey these rules automatically:

- **Platform is a Pedagogical Engine, NOT an Answer Engine**: Long exercises or educational questions must trigger the pedagogical tutoring flow. The platform must first diagnose the initial cognitive gap, ask one short diagnostic question, and provide only the next missing hint. It must **never** default to dumping the full solution.
- **Strict Intent Routing Safeguards**: Analytical or educational inputs must strictly route to the `educational` pipeline (which engages the Socratic Tutor / Synthesizer). They must **never** fall back to `general_knowledge`.
- **Cognitive Lab Authority**: The platform is an engine that makes human reasoning observable, diagnosable, testable, and continuously improvable. Any future feature that improves chat while weakening the core pillars (Interactive Object UI, Cognitive Modeling, Error Memory, Adaptive Generation, Simulation) is architecturally incorrect.
- **Runtime truth over synthetic certainty**: Code presence ≠ runtime usage. A capability is real ONLY when proven by import + call chain + runtime evidence. Anything missing one of those three is treated as DORMANT or ZOMBIE until proven otherwise.
- **Instrumentation before visualization**: Dashboards must never outpace instrumentation.
- **Observability is for diagnosis, not decoration**: Every visualization must support debugging.
- **Unknown is better than fake certainty**: Dormant systems must not be presented as healthy.
- **Metrics require runtime evidence**: Every metric must have a semantic contract.
- **Traces and metrics are separate disciplines**: Treat them as such in architecture and implementation.
- **Forbidden anti-patterns**: High-cardinality labels are dangerous and strictly forbidden. Dual-writes to the database are forbidden.
- **CI truth-gate philosophy**: The project enforces architectural capability truths via static analysis in CI (`scripts/runtime_truth.py --check`), which strictly validates the codebase against `.runtime/truth_table.lock.json`. Do not bypass or break this gate.
- **Repository memory coherence**: Repository memory (`.memory/` and `CLAUDE.md`) must remain coherent, curated, and durable over time. It must reflect the actual runtime reality, not aspirational architecture.
- **ACTIVE (no-op) is not ACTIVE**: A component that is imported and called but produces no observable output due to missing configuration (e.g., `otel_setup.py` without `OTEL_EXPORTER_OTLP_ENDPOINT`) is not truly ACTIVE at runtime. Mark it `ACTIVE (no-op without ENV_VAR)` in the truth table.
- **No DATABASE_URL = no FastAPI**: The application cannot start without `DATABASE_URL` or `APP_DATABASE_URL`. A running uvicorn process is not proof of a healthy server — check `/health` response, not just the process list.
- **Process env wins over `.env` at module import time**: `app/core/settings/base.py:23` reads `os.environ.get("APP_DATABASE_URL")` before pydantic-settings reads `.env`. Secrets must be exported into the process environment before uvicorn starts, not just written to `.env`.
- **Stale state files are a finding**: `.devcontainer/state/app_healthy` from a previous run does NOT mean the current uvicorn is healthy. Always re-probe the live `/health` endpoint — never trust a state file timestamp.
- **Lifespan warmup must be timeout-guarded**: Any `ainvoke()` in an ASGI `lifespan()` context must use `asyncio.wait_for(..., timeout=30.0)`. Unbounded awaits block ASGI startup indefinitely, creating a "process alive, service dead" partial state.
- **Degraded ≠ Dead**: A microservice that passes `/health` but has a failed graph warmup is DEGRADED, not healthy. The `/health` endpoint must expose `startup_state` so operators can diagnose without restarting.
- **Zombie metrics are worse than no metrics**: A dashboard panel that always shows zero is indistinguishable from "system not running". Every dashboard metric must have a verified emitter in the application source (D-016).
- **Lock file staleness is a finding**: `.runtime/truth_table.lock.json` records the branch and timestamp it was generated on. Always check `generated_at_utc` before trusting it. A stale lock file means the CI drift gate may pass on false grounds.
- **PRIMARY model invariants (D-067 — 2026-05-17)**: ⛔ `nvidia/nemotron-3-nano-30b-a3b:free` MUST NEVER be PRIMARY. Live benchmark proved it returns `content=None` (English reasoning only) with system prompts > 1500 chars — caused real-user "pepepe aaaa" garbage catastrophe (ISS-079). ✅ `openai/gpt-oss-20b:free` is the verified PRIMARY (2102 chunks, 4762 chars Arabic + LaTeX, finish=stop).
- **System prompt sanity (D-067)**: System prompts > 1500 chars are FORBIDDEN — they trigger reasoning-mode in free OpenRouter models. Box-drawing chars (U+2500–U+257F) like `━━━` are FORBIDDEN in prompts — they confuse tokenizers and cause degenerate output. Keep prompts < 1000 chars, use simple punctuation (`---`, `##`).
- **No reasoning→content leak (D-067)**: Gateway MUST NEVER redirect `delta.reasoning` to `delta.content`. The reverse of ISS-069 caused English thinking text ("We need to respond as a brilliant Algerian professor...") to be displayed to students as Arabic answers. If `content=None`, let the fallback chain trigger.
- **Greeting fastpath is mandatory (D-067)**: Every chat entry point (monolith `local_graph.py`, orchestrator's `ChatFallbackNode`, `chat_with_agent` preempt) MUST check `_greeting_fastpath_response` / `GreetingSkill` BEFORE calling LLM. Without this, free models return etymology for "السلام عليكم" (verified live ISS-079).
- **Stateful Pedagogical Progression is Mandatory**: The AI tutor must never rely purely on stateless chat history or naive string inference for its decisions. `TutorState` is the single source of truth for the student's pedagogical journey (e.g., `learning_stage`, `dead_ends`, `interventions_used`). The Monolith uses `PedagogicalPolicyEngine` linked to this state to strictly forbid loops and intent hijacking.
- **E-TAALEEM Zero Cognitive Overload (D-074 — Protocol V6.0)**: The platform serves 800,000+ Algerian Baccalaureate students. Abstract math symbols (`A`, `B|A`, `Ā`, `B̄`) are **permanently banned** from every generative-UI node label. This is an immutable pedagogical law, not a styling preference.
- **Abstraction Ban — Hybrid Extraction (D-074)**: Every generative-UI component MUST produce concrete, human-readable labels via the Hybrid Extraction Model — deterministic entity extraction first (`OrchestratorClient._extract_concrete_events`), LLM enrichment only when no concrete entity is found (`_enrich_tree_labels_with_llm`, timeout-guarded, A/B output rejected), and even the final fallback is concrete (`"الحدث الأول"`, never `"A"`). The orchestrator `_normalize_ui_component_event` + frontend `GenerativeUIRenderer` whitelist are the only render paths.
- **BKT is the foundational cognitive layer (D-074)**: Bayesian Knowledge Tracing (`app/services/skills/bkt_engine.py:BKTEngine`) is the cognitive substrate for ALL future autonomous pedagogical skills (adaptive difficulty, hints, learning paths). Any adaptive capability MUST build on `student_mastery_probability`, never re-invent mastery tracking. Governed by `BKT_COGNITIVE_DOCTRINE` (versioned in `app/services/skills/doctrine.py`, CI-validated by `scripts/fitness/check_skills_doctrine.py`).
- **BKT is append-only (D-074)**: `student_bkt_analytics` is strictly an **append-only interaction log** for time-series analytics. Each evaluation inserts ONE new row; prior mastery is read from the most-recent row per `(user_id, concept_id)`. No in-place updates, no upserts — the full temporal sequence is preserved. Mandatory schema: `concept_id`, `cognitive_load_estimate` (low/medium/high), `student_mastery_probability ∈ [0,1]`, `interaction_timestamp`.
- **BKT never breaks chat (D-074)**: Every BKT evaluation/persist/emit call (`customer_chat._evaluate_and_emit_bkt`) is isolated in `try/except` with its own DB session. A BKT failure is logged and swallowed — it must NEVER abort a student's chat turn.
- **Dual-Mode Routing is immutable (D-085 — 2026-05-23)**: `_build_calculated_ui` stamps every UI event with `routing_mode: "MODE_A" | "MODE_B"`. MODE_A (direct question) → `terminate_pipeline=True`, companion_text only. MODE_B (confusion: «لم أفهم», «مفهمتش», «كيفاش», «اشرح لي») → `terminate_pipeline=False`, LLM narrative continues after UI. The routing decision is made **inside** `_build_calculated_ui` — never re-computed in `chat_with_agent`. `_effective_question` in MODE_B prepends the Socratic instruction before reaching LangGraph/fallback. V28.0/V30.0 Text-Wall Muzzle contracts remain valid for MODE_A. Removing `routing_mode` or collapsing the two modes breaks deep pedagogy for confused students.
- **Math Pipeline is 4 nodes, not 3 (D-080 — 2026-05-23)**: `enrich_node` (Node 4 — deterministic, no LLM) was added after `normalize_node`. It builds `ui_component` payload from the completed solution text. Topology: `classify → solve → normalize → enrich → END`. `MathPipelineState` and `invoke_math_pipeline` now return `ui_component: dict | None`. Removing `enrich_node` breaks Generative UI for all math questions.
- **ui_component flows through the full stack (D-080)**: `ConversationState` carries `ui_component`. `invoke_graph` returns it. `ChatResponse` (HTTP) and WebSocket payload both include it. `_try_build_math_ui_component` in `customer_chat.py` injects it into `assistant_final` for the monolith path. `useAgentSocket.js` extracts it from `assistant_final` payload and attaches it to the message. `ChatInterface.jsx` renders `GenerativeUIRenderer` **after** the text, only on `isComplete` — never during streaming.
- **MathExplanationCard is the canonical math Generative UI component (D-080)**: Registered as `math_explanation_card` in `GenerativeUIRenderer` whitelist. Props contract: `{ math_type, label, intuition, steps[], hint, visual_metaphor }`. 11 math types supported, each with a distinct color and visual metaphor. Any new math type must be added to `_MATH_TYPES` (math_pipeline.py), `_TYPE_LABELS`, `_MATH_HINTS`, `visual_metaphors` dict inside `_build_ui_component`, and `TYPE_COLORS` in `MathExplanationCard.jsx`.
- **_try_build_math_ui_component is non-breaking (D-080)**: Wrapped in `try/except` in `customer_chat.py`. Returns `None` for non-math responses (`general_math` type). Never raises — a failure produces `ui_component=None` and only text is shown. Do not remove the guard.
- **Supabase schema = boot auto-creation, not sandbox migrations (D-074)**: The Codespaces/sandbox network firewall blocks Postgres egress (ports **6543/5432**). Schema changes are applied by the boot hook `app/kernel.py:233 → validate_schema_on_startup() → validate_and_fix_schema(auto_fix=True)`, driven by `app/core/db_schema_config.py:REQUIRED_SCHEMA`. Agents MUST register new tables there (never rely on running SQL from the sandbox). The standalone `.sql` under `scripts/migrations/` is for manual operator use only.

---

## 0.5. Skills Philosophy — The Architectural North Star

**قانون لا يُخرق:** كل قدرة ذكاء اصطناعي في هذا النظام يجب أن تكون **Skill** — وحدة مستقلة قابلة للقياس والاختبار والاستبدال. لا يوجد "Prompt Spaghetti".

### لماذا Skills وليس Prompts؟

| | Prompt Spaghetti | Skill Architecture |
|--|--|--|
| الجودة | متوسطة في كل شيء | ممتازة في شيء واحد |
| الاختبار | مستحيل | `pytest` عادي |
| القياس | لا شيء | Prometheus metrics |
| التحسين | يكسر كل شيء | مستقل تماماً |
| التوسع | copy-paste | `compose([skill1, skill2])` |
| عمر النظام | يموت مع النموذج | يعيش مع المنطق |

### تعريف الـ Skill في هذا المشروع

Skill = microservice يملك:
1. **مسؤولية واحدة** — يفعل شيئاً واحداً فقط بشكل ممتاز
2. **مدخلات ومخرجات محددة** — contract واضح عبر HTTP/JSON
3. **مقاييس Prometheus** — `cogniforge_{skill}_invocations_total` + `duration_seconds`
4. **اختبارات قابلة للتشغيل** — `pytest tests/microservices/{skill}/`
5. **استقلالية كاملة** — لا يستورد من microservice آخر

### الخدمات المصغرة كـ Skills (الحالة الراهنة)

```
orchestrator-service  :8006  ← Skill: التركيب والتوجيه (Composition)
planning-agent        :8002  ← Skill: التخطيط (Planning)
research-agent        :8007  ← Skill: البحث والاسترجاع (Retrieval)
reasoning-agent       :8008  ← Skill: التفكير العميق MCTS (Reasoning)
user-service          :8001  ← Skill: إدارة المستخدمين (Identity)
```

### مسار الطلب المستهدف (Skills Pipeline)

```
الآن (Prompt Spaghetti):
  Browser → FastAPI monolith → LangGraph local (prompt واحد كبير)

الهدف (Skills Architecture):
  Browser → FastAPI → orchestrator → compose([
      PlanningSkill.plan(query),        # ما الخطة؟
      ResearchSkill.retrieve(context),  # ما المعلومات المتاحة؟
      ReasoningSkill.reason(problem),   # ما الحل؟
  ]) → إجابة مُركَّبة من skills متخصصة
```

### قواعد إلزامية لكل Skill جديد

1. **Skill يجب أن يملك `/metrics` endpoint** — بدونه لا يُعتبر Skill حقيقياً
2. **Skill يجب أن يملك اختبارات** — minimum: happy path + error path
3. **Skill لا يستدعي Skill آخر مباشرة** — يمر عبر orchestrator فقط
4. **Skill يُسجِّل كل invocation** — `record_{skill}_invocation(action, status, duration)`
5. **Skill يعمل بدون الـ Skills الأخرى** — fallback mode إلزامي

### قانون التحقق (Skill Reality Check)

Skill حقيقي = **import + call chain + runtime evidence + metrics + tests**

أي Skill يفتقد واحداً من هذه الخمسة → يُصنَّف DORMANT حتى يُثبت العكس.

---

## 0.6. The Cognitive Lab Vision & Execution Roadmap

> **The system is not a Chat Tutor. It is a Cognitive Lab / Thinking Engine.**
> The chat interface is merely a delivery mechanism. The true core consists of an Interactive Object UI, Cognitive Modeling, Error Memory, Adaptive Generation, and a Simulation Engine.

### 7-Phase Cognitive Lab Architecture

**Phase 1: Interactive Object UI (World Building)**
- **Concept:** Students do not read a text wall. They interact with a canvas.
- **Mapping:** `ExerciseRenderer` (or equivalent generative UI layer) creates a manipulable object map (e.g., a bag, balls, colors) instead of text. The student drags, drops, and interacts.

**Phase 2: Cognitive Modeling (The AI doesn't know the answer, it knows the mind)**
- **Concept:** The system measures *how* the student thinks (e.g., What did they click first? Did they ignore numbers? How many seconds did it take?).
- **Mapping:** `TutorStateService` stores the "Digital Twin of the Mind," capturing interaction latency, choice patterns, and cognitive focus.

**Phase 3: Building the Mind (Diagnostic Socratic Feedback)**
- **Concept:** Instead of "wrong answer," the system identifies the cognitive flaw (e.g., "You think order matters").
- **Mapping:** `SocraticEvaluatorSkill` and `ConceptDiagnosisSkill` explain mental errors, not just calculation errors.

**Phase 4: Digital Twin of the Mind**
- **Concept:** Every student has a dynamic cognitive map covering Logic, Probability, Deduction, and Model Selection.
- **Mapping:** `BKTEngine` (Bayesian Knowledge Tracing) evolves into tracking specific cognitive vulnerabilities and conceptual fragility rather than static scores.

**Phase 5: Dynamic Generation Engine**
- **Concept:** No static question bank. The system generates new exercises targeting the exact cognitive weakness (e.g., confusing arrangements vs. combinations) with 85% similarity but a different context.
- **Mapping:** `PedagogicalPolicyEngine` orchestrates the generation of adaptive exercises based on the digital twin's error memory.

**Phase 6: Simulation Engine**
- **Concept:** The student can run "Million Trials" inside the canvas to see empirical convergence towards theoretical probability.
- **Mapping:** The platform provides a `SimulationEngine` capability (to be implemented as a dedicated microservice/tool) allowing "what if" constraint modification and behavioral observation.

**Phase 7: Error Memory & Predictive Tutoring**
- **Concept:** The system remembers mastered concepts, fragile understandings, and frequent errors to predict mistakes before they happen.
- **Mapping:** Extended `TutorStateService` and `BKTAnalyticsService` track and predict conceptual fragility.

**Execution Rule:** Any PR that degrades this vision into a standard text-based Q&A bot must be rejected.

**خريطة المراحل (جدول الحالة — التفصيل في `roadmap.md`):**

| المرحلة | الحالة | القرار |
|---------|--------|--------|
| M0 أساس BKT · M1 بيداغوجيا تكيفية · M2 العمود الفقري الإلزامي · M3 مسار تعلّمي | ✅ | D-074/104/112/111 |
| **M4 سقراطية ج1** (doctrine + أسئلة-فقط + AnswerRedactionSkill) | ✅ | D-113 ج1 |
| **M5 سقراطية ج2** (حجب orchestrator + SynthesizerNode + سُلّم الدعم الخماسي) | ✅ | D-113 ج2 |
| **M6 صدق BKT** (assisted vs unaided-delayed + scaffold_leak + بوّابة الإتقان) | 📋 | — |
| **M7 واجهات بلا أرقام** (تدرّج بصري سقراطي) | 📋 | — |
| **M8 وضع التحقق المنفصل** («تحقق من حلي») | 📋 | — |
| **M9 مقياس فجوة الوهم** (Prometheus/Grafana) | 📋 | — |
| **M10 هجرة الرسم S2–S4** (port المهارات + CritiqueNode + Mastery-Aware + Real Synthesis) | 📋 | D-108/109/110 |
| M11 الصوت | ⏸️ مؤجَّل | D-107 |

**مقياس النجاح الوحيد:** `فجوة الوهم = الأداء المدعوم − القدرة غير المدعومة المؤجَّلة`
→ نُحسّن على تقليصها، **ممنوع** التحسين على مدة الجلسة/عدد الرسائل/«الرضا» اللحظي.

---

## 0.7. Agentic Cognitive Runtime Doctrine

> **Detailed source: `.memory/agentic_runtime_doctrine.md` (D-146).** This is a pointer,
> not a copy — kept short on purpose (`DOC-DEBT-001`: CLAUDE.md is a contract, not an
> encyclopedia).

CogniForge is an **agentic runtime**: a simple model→tool→append loop whose power lives in
the *layers around it*. Four principles govern every architectural decision:

- **Context engineering > prompting** — the control surface is `CLAUDE.md` + `.memory/` +
  `app/services/skills/`, not one big prompt.
- **Capability ≠ safety** — safety-critical invariants are enforced by deterministic gates
  (hooks, CI, redaction skills), never by prose a model "should" obey.
- **Curated memory, not bloat** — memory holds stable invariants + verified facts only.
- **Separate the roles** — Configuration / Procedure (Skills) / Verification / Safety are
  distinct; a writer never silently grades its own work.

**13 runtime layers, each graded by §6.6** (ACTIVE only with import + call chain + runtime
evidence). ACTIVE: Configuration, Skills Engine (27 skills, D-100), Hooks/Policy
(`PedagogicalPolicyEngine`, D-144), Memory (BKT + `tutor_state`, D-074/D-142),
Verification (redaction/firewall/integrity, D-086/D-113), Observability (in-process).
PARTIAL: Subagents, Knowledge/Retrieval, Planner, Reasoning, Context engine.
**DORMANT/ZOMBIE:** Plugin loader (`app/core/registry/plugin_loader.py` — exists, **no live
import**). **PLANNED:** CritiqueNode (D-109), Evolution engine. *Promoting any non-ACTIVE
layer requires the full three-leg proof — do not soften the status.*

---

## 0.8. Pedagogical OS Constitution (D-153)

> **الدستور الكامل: `.memory/pedagogical_os.md`** — هذا مؤشر فقط (العقد لا الموسوعة).
> تحرسه بوّابة CI إلزامية: `scripts/fitness/check_pedagogical_os.py`.

**الجملة الدستورية:** «الطالب لا يرسل سؤالاً إلى النظام؛ الطالب يدخل مسار تعلّم حيّ،
والنظام مسؤول عن حفظ هذا المسار من الانهيار.»

**السلسلة القانونية للدور:** `Routing/Intent → Diagnosis → TutorState → Pedagogical
Policy → Symbolic Truth → Micro-Example → Response Guard → Learning Update →
Hooks/Extensibility → Verification`.

**القوانين السبعة:** التعليم قبل الإجابة · الحالة قبل الرد · التشخيص قبل الشرح ·
التلميح قبل الحل · الحقيقة الرمزية قبل اللغة · التقدّم قبل الإطناب · التوسعة تخدم العقل.

**قاعدة الفصل:** Core = Teaching Intelligence (يقرّر) · Runtime Shell = Claude Code /
MCP / hooks / subagents / compaction (يخدم العقل ولا يصير عقلاً موازياً) · Truth =
Symbolic Engine · Memory = TutorState · Law = Pedagogical Policy · Safety = Response Guard.

**قاعدة المليارات:** تركيبة التمرين من الكيانات المهيكلة (`parsed_entities`) لا من
استخراج النثر؛ والاستخراج **لا يرى نثر الحل النموذجي أبداً** (ISS-120 هو البرهان).

---

## 1. What This Project Does

CogniForge is an educational AI platform for Algerian high-school students preparing for the Baccalaureate exam. Students chat in Arabic, French, or Darija and receive tutoring in math, physics, and sciences. The backend is a FastAPI monolith.

**Supported runtime environments**: the project is environment-agnostic and runs on both:

| Environment | Frontend port | How it picks the port |
|---|---|---|
| **GitHub Codespaces** (primary) | **5000** | `supervisor.sh` sets `FRONTEND_PORT=5000` (default). `server.js` reads `PORT \|\| FRONTEND_PORT \|\| 3000`. `devcontainer.json` sets `onAutoForward: openBrowser` for port 5000 — browser tab opens automatically. |
| **Replit** | **5000** | `frontend/package.json` script `"dev": "next dev --hostname 0.0.0.0 --port 5000"` is used directly |

In both environments the backend is on **8000** and microservices in `microservices/` are **dormant by default** — neither environment starts them. The Codespaces devcontainer (`.devcontainer/docker-compose.host.yml`) launches a single `web` container; the full microservices stack only comes up when you explicitly run `docker compose -f docker-compose.yml up -d`.

**Additional infrastructure (Codespaces only, verified 2026-05-09):**
- Grafana: port **3001** (`grafana.ini` says 3000 but provisioning CLI overrides — `GET /api/health → {"database":"ok"}`)
- Prometheus: port **9090** (`GET /-/healthy → "Prometheus Server is Healthy."`)
- Redis: port **6379** (process running but app uses `InMemoryCache` — `REDIS_URL` not set)

**Known fix applied 2026-05-09 (ISS-036):** `frontend/next.config.js` `allowedDevOrigins` was missing `*.app.github.dev` — Next.js 15+ rejects Codespaces proxy requests with `ERR_HTTP_RESPONSE_CODE_FAILURE` without it. Fixed by adding `*.app.github.dev` and `*.preview.app.github.dev` to the list.

**Known fix applied 2026-05-09 (ISS-037):** commit `3fd78247` introduced `local stale_pid` at top-level scope in `supervisor.sh` (outside any function). bash rejects `local` outside functions → supervisor crashes at Step 4 with `local: can only be used in a function` → uvicorn never starts → all ports dead. Fixed by removing the `local` keyword (`stale_pid=...` instead of `local stale_pid`). Also added `.devcontainer/secrets.env` fallback so supervisor injects DB credentials even when Codespaces Secrets are not configured.

**Known fix applied 2026-05-25 (D-WS-FLAP-001 — WebSocket Flapping):** Forensic diagnosis of "works → breaks → works" flapping pattern revealed 4 root causes: **(1)** `_emit_terminal_frames` called inside `finally` block without `try/except` — when client disconnects mid-stream, `send_json` raises `RuntimeError`/`WebSocketDisconnect` that escapes `finally`, corrupts the `while True` loop, and causes the next `receive_json` to fail on a dead socket. Client reconnects immediately → works → same pattern repeats. Fixed: wrapped `_emit_terminal_frames` in `try/except (WebSocketDisconnect, RuntimeError)` in both `customer_chat.py` and `admin.py`. **(2)** `stream_and_forward` inner function did not check WebSocket state before each `send_json` — continued sending on a closed socket after client disconnect. Fixed: added `_ws_is_connected()` guard at the top of each iteration. **(3)** `NullPool` for Supabase opened a new TCP connection per `async_session_factory()` call — each WS turn opens 3-4 sessions, exhausting Supabase's ~60 connection limit under concurrent load. Fixed: replaced `NullPool` with `pool_size=5, max_overflow=5, pool_recycle=300` while keeping `statement_cache_size=0`. **(4)** `_evaluate_and_emit_bkt` called with `await` before streaming started — Supabase latency (>500ms) blocked the event loop, causing client timeout before first `assistant_delta`. Fixed: converted to `asyncio.create_task()` with `add_done_callback` for error logging. **Live verified 2026-05-25:** 6 scenarios — Customer 3 consecutive turns (0.7s/37.7s/3.3s) + mid-stream disconnect → reconnect (4.8s) + Admin full turn (56.9s) + Admin disconnect → reconnect (0.4s) → **6/6 PASS, no flapping**. 115 unit tests pass.

**Known fix applied 2026-05-28 (ISS-093 — ASGI crash + SECRET_KEY rotation → kick-to-login):** Two additional root causes of the kick-to-login loop: **(1)** `receive_json()` in the `while True` loop raises `RuntimeError: WebSocket is not connected` when Codespaces proxy drops the connection abruptly. The outer `except WebSocketDisconnect` did not catch `RuntimeError` → exception escaped to ASGI layer → uvicorn logged `Exception in ASGI application` → frontend saw non-clean close → reconnect loop. Fixed: outer `except` in both `customer_chat.py` and `admin.py` changed to `except (WebSocketDisconnect, RuntimeError)`, plus inner `try/except` guard on `receive_json()` itself. **(2)** `_ensure_stable_secret_key` in `supervisor.sh` was giving priority to `current_key` (from process env / `.env`) over the on-disk state file. If `.env` or Codespaces Secrets changed between restarts, `SECRET_KEY` rotated → all existing JWTs invalidated → `4401` on every WS connect → `useRealtimeConnection` exhausted `MAX_FATAL_RETRIES=3` → `agent:auth_error` → `logout()` → login screen → logs back in → same cycle. Fixed: disk-wins logic — on-disk `dev_secret_key` always takes priority. Also added explicit `SECRET_KEY` write to `.env` after `_ensure_stable_secret_key` runs.

**Known fix applied 2026-05-28 (ISS-092 — System Not Responding + Kick-to-Login Loop on GitHub Codespaces):** Three catastrophic failures in Codespaces when Codespaces Secrets are not configured: **(1)** `OPENROUTER_API_KEY` injected as empty string by `devcontainer.json` → LLM calls fail silently → no answers to any question. **(2)** `DATABASE_URL` not set → `supervisor.sh` sets `ENVIRONMENT=testing` in `.env` → `crypto.py` reads `ENVIRONMENT` at import time → `ACCESS_EXPIRE_MINUTES=30` → tokens expire after 30 minutes → WebSocket returns `4401` → frontend calls `logout()` → kick to login page → user logs back in → same cycle repeats catastrophically. **(3)** `app/services/chat/agents/orchestrator.py:453` hardcoded `nvidia/nemotron-3-nano-30b-a3b:free` for search param extraction — this banned model (ISS-079) returns `content=None` → search fails → no answers. **Fixes:** Created `.devcontainer/secrets.env` with real keys (OPENROUTER, TAVILY, DATABASE_URL, SECRET_KEY, ENVIRONMENT=development). Rewrote `.env` with `ENVIRONMENT=development` + all real keys. Fixed `orchestrator.py:453` to use `ActiveModels.PRIMARY`. Added D-ISS-092 guard in `supervisor.sh`: when `DATABASE_URL` is real (non-sqlite), always set `ENVIRONMENT=development` in `.env`. **Live verified 2026-05-28:** `:8007 tavily=true`, `:8008 llm_backend=openrouter`, `:8002 database=postgresql`. Greeting: 0.7s. Physics question ("قانون أوم"): 5.3s, 96 chunks, 250 chars Arabic+LaTeX. Token lifetime: 1440 min (was 30 min).

**Known fix applied 2026-05-28 (D-ISS-092 — secrets.env mandatory for Codespaces):** `.devcontainer/secrets.env` MUST exist when Codespaces Secrets are not configured. Copy from `secrets.env.example` and fill real values. Without it: all API keys are empty strings, `ENVIRONMENT=testing`, tokens expire in 30 min, LLM returns nothing. The supervisor reads `secrets.env` only when the process env variable is empty/unset — if `devcontainer.json` injects an empty string, `secrets.env` IS read (D-WS-004 fix). The file is git-ignored and never committed.

**Known fix applied 2026-05-26 (D-WS-CODESPACES-001 — WebSocket "Reconnecting" on GitHub Codespaces):** Frontend loaded on `*-5000.app.github.dev` but WebSocket stayed in "reconnecting" state. Three root causes: **(1)** `wsUrl.js` `getCloudBackendHost()` rewrote port 5000→8000 for `*.app.github.dev` hosts, sending the browser to `wss://*-8000.app.github.dev/api/chat/ws`. GitHub Codespaces proxy does not reliably forward WebSocket upgrade headers for non-primary ports. Fixed: `getCloudBackendHost()` now returns `null` for `*.app.github.dev` — `getWsBase()` falls back to `window.location.host` (port 5000), and `server.js` proxies the WS upgrade to `ws://127.0.0.1:8000` internally. **(2)** `CORSMiddleware` does not support wildcard subdomain patterns (`https://*.app.github.dev`) — Starlette treats them as literal strings, so `is_allowed_origin()` never matched. Fixed: `build_cors_options()` in `app_blueprint.py` now auto-converts wildcard patterns to `allow_origin_regex`. **(3)** `server.js` WS error handler called `res.writeHead()` on a raw socket (not an HTTP response), causing a silent crash. Fixed: replaced with `socket.end('HTTP/1.1 502 Bad Gateway\r\n\r\n')`. **Live verified 2026-05-26:** `ws://localhost:5000/api/chat/ws` with Codespaces host → `WS_AUTH_MISSING` (connected). CORS regex matches `https://myworkspace-5000.app.github.dev` ✅, rejects `https://evil.com` ❌.

**Known fix applied 2026-05-26 (D-WS-GITPOD-001 — WebSocket "Disconnected" on Gitpod Flex/Ona):** Frontend showed permanent "Disconnected" state in Gitpod Flex/Ona environments despite backend WS working on localhost. Three root causes: **(1)** `TrustedHostMiddleware` rejected Gitpod Flex host header — Gitpod Flex/Ona uses `*.gitpod.dev` domain (not `*.gitpod.io`), pattern `<PORT>--<ENV_ID>.<cluster>.gitpod.dev` (double-dash). `ALLOWED_HOSTS` in `settings/base.py`, `.env`, and `supervisor.sh` all lacked `*.gitpod.dev`. Fixed: added `*.gitpod.dev`, `*.eu-central-1-01.gitpod.dev`, `*.eu-central-1-02.gitpod.dev`, `*.us-east-1-01.gitpod.dev` to all three locations; `supervisor.sh` now always overwrites `ALLOWED_HOSTS` (not skip-if-present) to ensure updates propagate. **(2)** `isCloudWorkspace()` in `wsUrl.js` did not explicitly document `.gitpod.dev` detection — added `host.endsWith('.gitpod.dev')` with D-WS-GITPOD-001 comment. **(3)** Port 8000 was not registered in Gitpod port registry — Gitpod proxy returned HTTP 401 for all requests. Fixed by ensuring `devcontainer.json` `forwardPorts` includes 8000 (already present). **Live verified 2026-05-26:** `curl -H "Host: 8000--<ENV_ID>.eu-central-1-01.gitpod.dev" http://localhost:8000/health → {"application":"ok"}` | `wss://8000--<ENV_ID>.eu-central-1-01.gitpod.dev/api/chat/ws` (no token) → `WS_AUTH_MISSING` | (with token) → `"Question is required"` — full stack reachable.

**Known fix applied 2026-05-25 (D-WS-004 — WebSocket Unified Architecture):** Full architectural audit of all WebSocket clients revealed four additional issues after D-WS-002: **(1)** `app/static/js/admin_chat.js` connected to `/ws/chat` (non-existent endpoint) without any auth token — always produced HTTP 403. Fixed: endpoint changed to `/admin/api/chat/ws`, token injected via `?token=` query param from `localStorage`, event handling updated for `assistant_delta`/`assistant_final`. **(2)** `wsUrl.js` local dev path hardcoded port `8000` — now reads `NEXT_PUBLIC_BACKEND_PORT` env var with `8000` as default. **(3)** `supervisor.sh` `_inject_env_secrets` and `_export_env_file` both used `[ -z "${!key:-}" ]` which correctly treats empty strings as "unset" — but `devcontainer.json` injects empty strings for unconfigured secrets, so the check was correct but `.env` was already written with `sqlite+aiosqlite:///:memory:` before `secrets.env` was read. Fixed: `.env` is now written with real DB URL when `secrets.env` is present. **(4)** `ws_proxy.py` `_proxy_websocket` used `subprotocols[1]` as `selected_protocol` — this passed the JWT token itself as the subprotocol name instead of `"jwt"`. Fixed: `selected_protocol = "jwt" if "jwt" in subprotocols else ...`. **(5)** `legacy-app.jsx` (both `frontend/public/js/` and `app/static/js/`) `API_ORIGIN` only handled port 3000 → 8000 mapping, missing Gitpod/Ona subdomain rewriting. Fixed: added `5000-<id>.ws-eu.gitpod.io → 8000-<id>.ws-eu.gitpod.io` and Codespaces `-5000.` → `-8000.` rewrites. **(6)** `useRealtimeConnection.js` `auth_error` state did not dispatch a global event — `CogniForgeApp` had no way to trigger logout. Fixed: dispatches `agent:auth_error` CustomEvent; `App` component listens and calls `logout()`. **(7)** `CogniForgeApp.jsx` `getStatusText` had no case for `auth_error`, `reconnecting`, `degraded`, `recovered` states. Fixed: all states mapped to Arabic labels. 34 regression tests in `tests/unit/test_ws_unified_architecture.py`. **Live verified 2026-05-25:** admin WS handshake 264ms | customer WS streaming 48 deltas | no-token → JSON `{code:WS_AUTH_MISSING}` + close 4401 | admin-on-customer → close 4403 | reconnect without storm | 3 concurrent connections all succeed.

**Known fix applied 2026-05-25 (D-WS-002 — WebSocket 403 in Codespaces/Gitpod/Ona):** Four root causes produced HTTP 403 on every WebSocket connection attempt: **(1)** `BACKEND_CORS_ORIGINS` default was `["http://localhost:3000"]` — frontend on port 5000 could not complete login (no CORS header returned), so no token was ever obtained. **(2)** `ALLOWED_HOSTS` default did not include `*.gitpod.io`, `*.app.github.dev`, or `*.replit.dev` — `TrustedHostMiddleware` rejected all cloud workspace hosts with HTTP 400. **(3)** `customer_chat.py` and `admin.py` called `websocket.close(code=4401)` **before** `websocket.accept()` — uvicorn translates a pre-accept close into HTTP 403, producing a silent rejection with no error message visible to the client. **(4)** `wsUrl.js` `getWsBase()` fell back to `window.location.host` (port 5000) in cloud workspaces instead of the backend host (port 8000), which has a different subdomain in Gitpod/Ona. Fixes: `BACKEND_CORS_ORIGINS` default now includes `http://localhost:5000` and `http://127.0.0.1:5000`; `ALLOWED_HOSTS` default now includes all cloud workspace wildcards; both WS handlers now call `accept()` first then `send_json(error)` then `close(4401)`; `wsUrl.js` adds `getCloudBackendHost()` which rewrites `5000-<id>.ws-eu.gitpod.io` → `8000-<id>.ws-eu.gitpod.io`; `FRONTEND_URL` default changed from port 3000 to port 5000; `supervisor.sh` injects `BACKEND_CORS_ORIGINS` and `ALLOWED_HOSTS` at boot if not already set; `next.config.js` cleaned up to use a single `backendUrl` constant. 19 regression tests in `tests/unit/test_ws_cors_hosts_settings.py`. **Live verified 2026-05-25:** `CORS: Origin: http://localhost:5000 → access-control-allow-origin: http://localhost:5000` | `TrustedHost: *.ws-eu.gitpod.io → HTTP 200` | `WS no token → JSON {type:error, code:WS_AUTH_MISSING}` (not HTTP 403) | `WS valid token → conversation_init received`.

**Known fix applied 2026-05-10 (ISS-038):** `detect_exercise_retrieval` in `app/services/capabilities/exercise_retrieval.py` used a flat keyword list (`"تمرين"`, `"احتمالات"`, `"درس"`, …) with no context awareness. Any question containing these words — regardless of intent — triggered `_build_local_retrieval_response`, which always returned the single file in `knowledge_base/` (the probability BAC exercise). A student asking "اشرح الجزء أ من هذا التمرين" received a probability exercise instead of an explanation. Fixed by replacing the flat keyword list with a two-phase intent classifier: (1) explanation/help intent patterns cancel retrieval even when "تمرين" is present; (2) only explicit retrieval patterns (BAC, numbered exercises, year+exercise combos) trigger retrieval. 25 regression tests added to `tests/contracts/test_exercise_retrieval_contracts.py`.

**Known fix applied 2026-05-10 (Orchestrator Revival Step 1 — H1/H2/H3):** Three technical blockers preventing `orchestrator_service` from running were removed. H1: `TAVILY_API_KEY` added to `docker-compose.yml` for both `orchestrator-service` and `research-agent` — `WebSearchFallbackNode` was silently skipping web search. H2: `ddgs>=6.0` added to `microservices/research_agent/requirements.txt` — `SuperSearchOrchestrator` raised `ImportError` without it. H3: null guard added before `cognitive_engine.memorize()` in `simple_client.py:116` — `get_cognitive_engine()` returns `None` by default, causing `AttributeError` on every successful LLM response. The 13-node StateGraph compiles and runs with real `OPENROUTER_API_KEY` (verified live). 9 regression tests added to `tests/microservices/orchestrator_service/test_orchestrator_revival.py`.

**Microservices Step 2 applied 2026-05-10 (D-025 — StateGraph Routing):** `ChatRoutingPolicy` default changed from `/agent/chat` (OrchestratorAgent) to `/api/chat/messages` (StateGraph 13 nodes). Controlled by `ORCHESTRATOR_CHAT_ENDPOINT` env var (`"state_graph"` default | `"agent"` rollback). Routing metrics added: `cogniforge_routing_mode_state_graph` gauge + `cogniforge_routing_target_total{target=...}` counter emitted per request. New Grafana dashboard `50-microservices-transition.json` (15 panels, UID `cogniforge-ms-transition-step2`) visible at :3001. Prometheus scrape targets added for orchestrator-service:8006, research-agent:8007, user-service:8001, planning-agent:8002 (all DOWN until `docker compose up`). CI gate `.github/workflows/microservices-transition.yml` (5 jobs) enforces default mode on every PR. 16 regression tests in `tests/infrastructure/test_routing_policy.py`.

**Microservices Step 3 applied 2026-05-10 (D-029/D-030/D-031 — Live Activation in Codespaces):** `orchestrator-service` activated as a **uvicorn process** (no Docker — Codespaces constraint). Runs on :8006 alongside the monolith, exactly like Grafana/Prometheus. Four artefacts: (1) `supervisor.sh:launch_orchestrator_service()` — STEP 4D, starts uvicorn automatically at Codespace boot when `OPENROUTER_API_KEY` is set, uses Supabase (`DATABASE_URL`) as `ORCHESTRATOR_DATABASE_URL`; (2) `.ona/automations.yaml` — service `orchestrator-service` (uvicorn start/ready/stop) + tasks `health-probe`, `verify-stack`, `restart-orchestrator`, `run-step3-tests`; (3) `observability/native/prometheus.yml` — `orchestrator-service` scrape target added at `localhost:8006` (DOWN until process starts); (4) `observability/grafana/dashboards/60-microservices-step3-live.json` — 20-panel live dashboard (UID `cogniforge-ms-step3-live`, 10s refresh) at Grafana :3001. CI gate `.github/workflows/microservices-step3-live.yml` (7 jobs). `OUTBOX_RELAY_ENABLED=false` — enabled in Step 4 after persistence verification.

**Microservices Step 4 applied 2026-05-10 (D-032/D-033 — Persistence Relay + Prometheus Metrics):** `OUTBOX_RELAY_ENABLED=true` activated in both `supervisor.sh` and `.ona/automations.yaml` (D-031 fulfilled). `prometheus_client>=0.20.0` added to `microservices/orchestrator_service/requirements.txt`. New module `microservices/orchestrator_service/src/core/prom_metrics.py` — independent `CollectorRegistry`, 11 metrics: `cogniforge_outbox_relay_cycles_total`, `cogniforge_outbox_relay_processed_total`, `cogniforge_outbox_relay_failed_total`, `cogniforge_outbox_relay_skipped_total`, `cogniforge_outbox_pending_gauge`, `cogniforge_stategraph_invocations_total`, `cogniforge_stategraph_duration_seconds`, `cogniforge_stategraph_errors_total`, `cogniforge_orchestrator_requests_total`, `cogniforge_orchestrator_request_duration_seconds`, `cogniforge_orchestrator_startup_info`. `/metrics` endpoint added to `main.py` — Prometheus scrapes it at `localhost:8006/metrics`. Prometheus scrape label updated to `step="4"`. Grafana dashboard `70-microservices-step4-persistence.json` (24 panels, UID `cogniforge-ms-step4-persistence`, 10s refresh) at :3001. CI gate `.github/workflows/microservices-step4.yml` (5 jobs). 44 regression tests in `tests/microservices/orchestrator_service/test_step4_persistence_relay.py`.

**Microservices Step 5 applied 2026-05-10 (D-034 — User Service Live Activation):** `user-service` activated as a **uvicorn process** on `:8001` (no Docker — Codespaces constraint). Second microservice to go ACTIVE alongside `orchestrator-service`. Five artefacts: (1) `microservices/user_service/src/core/prom_metrics.py` — independent `CollectorRegistry`, 11 metrics: `cogniforge_user_requests_total`, `cogniforge_user_request_duration_seconds`, `cogniforge_user_active_connections`, `cogniforge_user_auth_operations_total`, `cogniforge_user_auth_duration_seconds`, `cogniforge_user_registrations_total`, `cogniforge_user_logins_total`, `cogniforge_user_token_verifications_total`, `cogniforge_user_db_operations_total`, `cogniforge_user_db_duration_seconds`, `cogniforge_user_startup_info{step="5"}`; (2) `microservices/user_service/main.py` — `/metrics` endpoint + `set_startup_info()` in lifespan; (3) `supervisor.sh:launch_user_service()` — STEP 4E, starts uvicorn on `:8001` at Codespace boot when `DATABASE_URL` is set; (4) `.ona/automations.yaml` — service `user-service` + tasks `verify-step5-user-service`, `restart-user-service`, `run-step5-tests`; (5) `observability/native/prometheus.yml` — `user-service` scrape target at `localhost:8001` with `step="5"` label. Grafana dashboard `80-microservices-step5-user-service.json` (17 panels, UID `cogniforge-ms-step5-user-service`, 10s refresh) at :3001. CI gate `.github/workflows/microservices-step5-user-service.yml` (6 jobs). 36 regression tests in `tests/microservices/user_service/test_step5_user_service_metrics.py`.

**Live verification fix applied 2026-05-10 (ISS-040 — orchestrator PgBouncer port fix):** `orchestrator-service` failed to start with `DuplicatePreparedStatementError` even with `statement_cache_size=0` in `connect_args`. Root cause: Supabase PgBouncer on port **6543** (transaction mode) intercepts and rejects prepared statements at the protocol level before asyncpg's cache setting takes effect. Fix: `supervisor.sh` and `automations.yaml` now substitute port `6543→5432` (direct PostgreSQL) for `ORCHESTRATOR_DATABASE_URL` only. `database.py` refactored: `create_engine()` is now a lazy singleton via `get_engine()` + `_LazySessionFactory` proxy — prevents import-time DB connection errors. `init_db()` updated to call `get_engine()` instead of module-level `engine`. **Live verified:** `GET /health → {"status":"ok","graph_ready":true,"startup_state":"ready"}` | `GET /metrics → cogniforge_orchestrator_startup_info{graph_ready="true",outbox_relay_enabled="true"} 1.0`.

**Live verification fix applied 2026-05-10 (ISS-038-B — asyncpg URL conversion):** `orchestrator-service` and `planning-agent` both failed to start with `sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver to be used. The loaded 'psycopg2' is not async.` Root cause: `DATABASE_URL` from Supabase uses `postgresql://` scheme which SQLAlchemy maps to psycopg2 (sync). `create_async_engine` requires `postgresql+asyncpg://`. Fix applied in `supervisor.sh` (both `launch_orchestrator_service()` and `launch_planning_agent()`) and `.ona/automations.yaml` (all start/restart commands): inline bash substitution converts the scheme and strips `sslmode` query param (asyncpg handles SSL via `connect_args`, not query string). Verified live: both services start and respond on `:8006` and `:8002`.

**LaTeX Normalization + LangGraph Node Fix Applied 2026-05-15 (ISS-071/072 — Math Pipeline):** تجريب حي كشف أن `nvidia/nemotron-3-nano-30b-a3b:free` يستخدم `\[...\]` بدلاً من `$$...$$` رغم التعليمات الصريحة في system prompt (ISS-071). كما أن `temperature=0.7` يُسبب تشتتاً في الإجابات الرياضية (ISS-072). **التغييرات:** `math_pipeline.py` — `normalize_node` (Node 3 deterministic) مُضاف لتحويل `\[...\]` → `$$...$$` بعد كل استجابة LLM، `_normalize_latex()` دالة post-processing، `_FALLBACK_MODELS` قائمة بدلاً من نموذج واحد، `temperature=0.2`. `conversation_graph.py` — `_normalize_latex_response()` مُضافة، `temperature=0.3` بدلاً من `0.7`، system prompt مُحسَّن مع قاعدة LaTeX صارمة. **قاعدة لا تُخرق:** كل إجابة LLM تمر عبر `_normalize_latex()` قبل إرسالها للمستخدم — `\[...\]` ممنوع في الواجهة. **نتائج حية:** 4 مسائل رياضية مُختبَرة حياً ✅ | LaTeX موحَّد ✅ | 18 اختبار جديد ✅.

**Model Benchmark + TTFT Fix Applied 2026-05-13 (ISS-055 — Explanation TTFT 44s→1.78s):** تجربة حية كاملة كشفت أن TTFT الشرح = 44.13s (النموذج `inclusionai/ring-2.6-1t:free` يتجمد مع context 9670 حرف). بنشمارك حي لـ 15 نموذجاً مجانياً على OpenRouter كشف أن `nvidia/nemotron-3-nano-30b-a3b:free` هو الأسرع مع context كبير (TTFT=2.06s، عربية صحيحة). **التغييرات:** `ai_config.py` — PRIMARY تغيَّر من `inclusionai/ring-2.6-1t:free` إلى `nvidia/nemotron-3-nano-30b-a3b:free`، fallback chain مُحدَّث. `local_graph.py` — system prompt مُقلَّص (أقل tokens = استجابة أسرع). `exercise_retrieval.py` — `requested_part` hint + `_detect_requested_part_from_question()`. **قاعدة لا تُخرق:** المحتوى يُرسَل كاملاً للـ LLM (9670 حرف) — لا ضغط، لا اختصار — البث حرف وراء حرف. **نتائج حية:** استدعاء التمرين TTFT=0.85s ✅ | شرح الإجابة TTFT=1.78s (كان 44.13s) ✅ | التمرين كامل 12/12 ✅.

**Math Pipeline + LangGraph Overhaul Applied 2026-05-15 (ISS-070 — Catastrophic Math Responses):** تجريب حي كشف 3 مشاكل كارثية: (1) system prompts ضعيفة تُسبب خلط اللغات (روسية + إنجليزية في الإجابات). (2) fallback chain يستخدم نماذج غير متاحة (`gemini-2.0-flash-exp:free`، `llama-3.2-11b-vision:free`). (3) conversation_service يستخدم system prompt بسيط جداً بدون LaTeX أو منهجية. **الإصلاحات:** (1) `conversation_service/src/conversation_graph.py` — بنية جديدة: `intent_node → context_node → response_node` + system prompts متخصصة لكل نية (educational/general/chat) + `subject` detection (math/physics/chemistry) + `enriched_question`. (2) `conversation_service/src/math_pipeline.py` — **LangGraph Math Pipeline جديد** بـ 4 nodes: `problem_analysis_node → solution_strategy_node → step_by_step_node → verification_node` — يُوجَّه إليه كل سؤال رياضي تعليمي. (3) `app/services/chat/local_graph.py` — system prompt مُحسَّن بـ 6 مراحل إلزامية + قواعد اللغة الصارمة. (4) `microservices/reasoning_agent/src/services/strategies/mcts.py` — system prompts MCTS مُحسَّنة. (5) `microservices/reasoning_agent/src/services/reasoning_service.py` — system prompt النتيجة النهائية مُحسَّن. (6) fallback chain مُصلَّح في `app/core/ai_config.py` و `microservices/orchestrator_service/src/core/ai_config.py` — استبدال النماذج غير المتاحة بـ `google/gemma-4-26b-a4b-it:free`، `openai/gpt-oss-120b:free`، `openai/gpt-oss-20b:free`، `z-ai/glm-4.5-air:free`. **نتائج حية:** Math Pipeline يُجيب بـ LaTeX صحيح + `$$\boxed{}$$` + عربية نقية في 8.4s ✅ | 36 اختبار ناجح ✅ | تصنيف 11 نوع مسألة رياضية ✅. **قاعدة جديدة:** كل سؤال رياضي تعليمي يمر عبر Math Pipeline (4 nodes) لا LLM مباشر.

**ISS-069 Fix Applied 2026-05-15 (Catastrophic AI Responses — content=None):** تجريب حي كشف السبب الجذري للإجابات الكارثية: `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` يضع الإجابة في `delta.reasoning` / `message.reasoning` لا `delta.content` / `message.content` عند وجود system prompt → `content=None` → إجابات فارغة أو مشوهة للطلاب. **بنشمارك حي 2026-05-15:** 25 نموذجاً مجانياً اختُبرت — فقط `nvidia/nemotron-3-nano-30b-a3b:free` يُعطي جودة 4/4 مع TTFT=3.1s وعربية صحيحة وLaTeX سليم. **التغييرات:** (1) PRIMARY في جميع الخدمات تغيَّر من `nemotron-3-nano-omni-30b-a3b-reasoning:free` إلى `nemotron-3-nano-30b-a3b:free` — 15 ملف مُصلَّح. (2) `simple_client.py` — `_stream_model()` يُعيد توجيه `delta.reasoning` → `delta.content` كـ fallback لنماذج reasoning-only. (3) `send_message()` يستخرج `reasoning` عند `content=None`. (4) `reasoning_agent/src/ai_client.py` — نفس الإصلاح. (5) fallback chain مُحدَّث: `trinity-large-thinking:free` → `nemotron-3-super-120b:free` → `gpt-oss-120b:free` → `gpt-oss-20b:free` → `glm-4.5-air:free`. **قاعدة جديدة:** أي نموذج reasoning-only (ينتهي بـ `:reasoning:free` أو يضع الإجابة في `reasoning` لا `content`) يُعامَل كـ BROKEN للاستخدام التعليمي — يجب اختباره قبل تعيينه PRIMARY. **نتائج حية:** Pipeline mode=full، skills_active=['planning','research','reasoning']، جودة الإجابات 3/3 في 4 اختبارات (تكامل، فيزياء، احتمالات، كهرباء).

**Streaming Quality Fix Applied 2026-05-13 (ISS-054 — Machine-gun + Explanation Timeout):** تجربة حية كاملة كشفت ثلاث مشاكل حرجة وأُصلحت. **(1) Machine-gun rendering**: `useRealtimeConnection.js` كان يُطلق `dispatchEvent` لكل chunk فوراً → 400+ React re-render في 4 ثوانٍ → حروف تظهر كمدفع رشاش. الإصلاح: `requestAnimationFrame` batching — يُجمِّع كل delta chunks في frame واحدة (~16ms) ويُدمج محتواها قبل dispatch واحد. **(2) Explanation timeout**: context التمرين (13650 حرف) + system prompt كبير → النموذج المجاني يتجمد. `BASE_TIMEOUT=30s` يُلغي الطلب. الإصلاح: `_MAX_EXERCISE_CONTEXT_CHARS=6000` + `_MAX_EXPLANATION_TOKENS=1200` + `BASE_TIMEOUT=45s` + `max_tokens` param في `stream_chat()`. **(3) Broken LaTeX `$ $`**: `$$g(x)=...$$` أحادي السطر كان يسقط في `_split_preserving_latex()` فيُكسَر إلى `$ $g(x)`. الإصلاح: guard صريح للـ single-line `$$...$$` في `_stream_local_retrieval_response`. **نتائج حية مُتحقَّق منها:** طلب التمرين: TTFT=0.85s، 392 chunk، 2939 حرف، LaTeX سليم ✅ | شرح الإجابة: TTFT=3.81s، 306 chunk، 1860 حرف، لا هلوسة ✅. **الملفات المُعدَّلة:** `frontend/app/hooks/useRealtimeConnection.js` (rAF batching) | `app/core/gateway/simple_client.py` (asyncio.sleep(0) + max_tokens) | `app/core/gateway/connection.py` (BASE_TIMEOUT 30→45) | `app/services/chat/local_graph.py` (_MAX_EXERCISE_CONTEXT_CHARS + _MAX_EXPLANATION_TOKENS) | `app/infrastructure/clients/orchestrator_client.py` (LaTeX single-line guard).

**BAC 2016 Explanation Hallucination Fix Applied 2026-05-13 (ISS-053 — Explain with Context):** تمرين الدوال العددية 2016 كان يُهلوس عند طلب الشرح. السبب الجذري: `detect_exercise_retrieval` تُلغي الاسترجاع عند وجود "اشرح" → يذهب الطلب إلى LangGraph بدون محتوى التمرين → LLM يُهلوس تمريناً خاطئاً أو يقول "لا أملك التفاصيل". الحل: مسار ثالث جديد **"شرح مع سياق"** يجلب المحتوى الكامل (نص + إجابة نموذجية) ويمرره للـ LLM. 4 تعديلات: **(1)** `exercise_retrieval.py` — دالة `detect_explanation_with_context()` + `ExplanationWithContextDecision` + 15 نمط `_BAC_EXERCISE_EXPLANATION_PATTERNS` + 20 نمط `_BAC_SPECIFICITY_PATTERNS`. تُرجع `full_content` (9670 حرف، نص + إجابة نموذجية) و `display_content` (2913 حرف، نص فقط). **(2)** `local_graph.py` — دالة `run_local_graph_with_exercise_context()` + `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` (منهجية شرح الإجابة النموذجية خطوة بخطوة، LaTeX إلزامي، قاعدة 2016 الاستثنائية). **(3)** `orchestrator_client.py` — `_stream_exercise_explanation_response()` + إدراجه في fallback chain بين exercise_retrieval (2.0) و LangGraph (3.0) بـ `fallback_path=2.5`. **(4)** `ai_config.py` — تحديث 5 نماذج احتياطية بنماذج مُتحقَّق منها حياً: `nvidia/nemotron-3-super-120b-a12b:free`, `arcee-ai/trinity-large-thinking:free`, `openai/gpt-oss-120b:free`, `nvidia/nemotron-3-nano-30b-a3b:free`, `z-ai/glm-4.5-air:free`. **Fallback chain المحدَّث:** `file_intelligence → exercise_retrieval(2.0) → exercise_explanation_with_context(2.5) → LangGraph(3.0) → general_chat(4.0)`. **تحقق حي:** شرح g(x) 2016 يعمل بدون هلوسة، LaTeX صحيح، الإجابة النموذجية مُدرجة في السياق.

**BAC 2016 Ex4 Ultra Display Applied 2026-05-13 (ISS-052 — Semantic Retrieval + Streaming + UI):** تمرين الدوال العددية 2016 الدورة الأولى الموضوع الثاني التمرين الرابع يُعرض الآن بشكل احترافي فائق الجودة. 5 إصلاحات: **(1)** `exercise_retrieval.py` — إضافة 20+ نمط استدعاء جديد (دلالي + صريح): `اعطني`, `هات`, `g(x)`, `الدالة g`, `دوال 2016` — 10/10 طرق استدعاء تعمل. **(2)** `orchestrator_client.py` — streaming ذكي word-by-word: أسطر فارغة فورية، عناوين كوحدة، LaTeX محمي من الكسر، تأخيرات ذكية (6-25ms). **(3)** `ChatInterface.jsx` — إعادة كتابة كاملة: ExamBadge، TypingIndicator، MessageBubble، شاشة ترحيب مع quick prompts، textarea ذكي. **(4)** `globals.css` — CSS فائق الجودة: KaTeX احترافي، جداول رياضية، بطاقة امتحان، streaming cursor، RTL كامل. **(5)** `bac-exercise-explanation.md` — skill محدَّث بجميع طرق الاستدعاء + منهجية الشرح + قواعد LaTeX.

**Streaming Fix Applied 2026-05-12 (ISS-STREAM-001 — Word-by-Word Typing Effect):** Catastrophic streaming failure fixed surgically across full stack. 4 root causes identified and resolved: **(1)** `_normalize_stream_event` in `orchestrator_client.py` was converting control events (`phase_start`, `RUN_STARTED`, `context_missing`) to `assistant_delta` — causing garbled text in UI. Fixed by adding `_PASSTHROUGH_EVENT_TYPES` + `_TEXT_EVENT_TYPES` frozensets; unknown types return `{"type": "noop"}` filtered in `customer_chat.py` + `admin.py`. **(2)** `_generator_with_persistence` in `routes.py` only collected `assistant_final.content` for DB persistence — but streaming mode sends `content: ""` → nothing saved. Fixed by adding `delta_parts: list[str]` accumulator that collects all `assistant_delta` chunks. **(3)** `mergeAssistantContent` in `useAgentSocket.js` had wrong logic: `current.startsWith(incoming)` returned `current` (dropped new chunk). Fixed: `current.endsWith(incoming)` detects stale late-arriving chunks; direct append for true deltas. **(4)** `print()` debug statements in `SupervisorNode`, `ChatFallbackNode`, `QueryRewriterNode`, `ToolExecutorNode`, `ValidatorNode`, `GeneralKnowledgeNode` replaced with `logger.debug()`. New artefacts: CI gate `.github/workflows/streaming-fix-gate.yml` (4 jobs) + Grafana dashboard `160-streaming-metrics.json` (11 panels, UID `cogniforge-streaming-metrics`). **Verified:** `ruff check . ✅ | ruff format --check . ✅ | runtime_truth ✅ | guardrails ✅ | 18 Grafana dashboards | 12 Prometheus targets`.

**End-to-End User Routing Verified 2026-05-11 (D-045 — Microservices Answer Users):** All 8 microservices confirmed ACTIVE and answering real user requests end-to-end. Chat path verified live: `User WebSocket (jwt subprotocol) → Monolith :8000/api/chat/ws → OrchestratorClient.chat_with_agent() → http://localhost:8006/api/chat/messages (StateGraph mode) → LangGraph 13-node → Planning:8002 + Research:8007 + Reasoning:8008 → streaming NDJSON to user`. WS events: `[conversation_init, assistant_delta×6, assistant_final]`. Real Arabic LLM answer confirmed. Key fixes: **(ISS-048)** `supervisor.sh` missing `ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR=true` — `AppSettings.validate_orchestrator_service_discovery()` blocked localhost URL when `_is_container_runtime()=True` and `CODESPACES` not yet set. Added alongside existing `CODESPACES=true`. **(ISS-049)** `conversation-service` crashed at boot: `ModuleNotFoundError: No module named 'prometheus_client'` — not installed in base Python env. Fixed: `pip install prometheus_client` + added to `microservices/conversation_service/requirements.txt`. **(ISS-050)** End-to-end WS chat verified with real user JWT token. **Verified 2026-05-11:** `pipeline_mode=full | skills_active=['planning','research','reasoning'] | duration=28.5s` | 12/12 Prometheus UP | 17 Grafana dashboards | WS chat → real LLM answer.

**Live Surgical Verification 2026-05-11 (D-044 — Full Stack + Real Secrets):** All 8 microservices started with real `OPENROUTER_API_KEY` + `TAVILY_API_KEY` + `DATABASE_URL` (Supabase). Skills Pipeline confirmed `pipeline_mode="full"` with real LLM responses. Key fixes: **(ISS-047)** `reasoning-agent` failed with OpenRouter 402 — `gpt-4o` requested 16384 tokens but account had ~3980 credits. Fix: `DEFAULT_MODEL = "openai/gpt-4o-mini"` + `MAX_TOKENS = 1024` in `microservices/reasoning_agent/src/core/config.py` + `max_tokens` param in `ai_service.py`. **(content-retrieval-skill)** `:8009` was DOWN in Prometheus — started as uvicorn process, now 12/12 targets UP. **(ruff)** 113 lint errors fixed (auto-fix + manual). **(tests)** 10 test failures fixed: WS mock DB sessions (sync vs async SQLAlchemy methods), `test_conversation_service_envelope.py` rewritten to match actual conversation-service WS contract, `test_settings_base.py` + `test_db_factory_guardrails.py` isolated from `.env` file via `model_config = SettingsConfigDict(env_file=None)`, `test_dual_write_immunity.py` fixed with `pytest_asyncio.fixture` + `expire_on_commit=False`, `chat_persistence.py` added `await db.refresh(message)` after commit. **Verified 2026-05-11:** `pipeline_mode=full | skills_active=['planning','research','reasoning'] | duration=23s` | 12/12 Prometheus UP | 17 Grafana dashboards | ruff 0 errors.

**Live Runtime Audit 2026-05-11 (D-043 — Full Stack Verified):** Complete live health probe of all 8 services confirmed. All Prometheus scrape targets UP. Skills Pipeline in `fallback` mode by default (LLM calls require `OPENROUTER_API_KEY` in process env). Key findings: (1) `/agent/chat` requires `question` field (not `message`) + integer `user_id` + JWT `Authorization` header — 401 without auth; (2) `/chat/message` on conversation-service requires `question` field (not `message`); (3) planning-agent `/plans` requires `X-Service-Token` JWT header; (4) research-agent `/execute` requires `caller_id` + `action` fields; (5) reasoning-agent `/execute` requires `caller_id` + `action` + `query` fields; (6) `/compose` on orchestrator works without auth and returns `pipeline_mode="fallback"` when skills unreachable. Grafana :3001 → 16 dashboards active. Prometheus :9090 → 12 scrape targets all UP. All 8 uvicorn processes confirmed live via `ps aux`. **Verified service matrix 2026-05-11:**

**Live Surgical Fixes 2026-05-11 (ISS-046 — Full Pipeline `full` mode verified):** Three root causes prevented Skills Pipeline from reaching `pipeline_mode="full"` with real LLM responses. **(ISS-046-A)** `orchestrator-service` launched by supervisor.sh without `CODESPACES=true` → `config.py` `resolve_service_urls()` used Docker hostnames (`planning-agent:8002`, `research-agent:8007`, `reasoning-agent:8008`) instead of `localhost` → `[Errno -2] Name or service not known` on every skill call. Fix: `supervisor.sh:launch_orchestrator_service()` already sets `CODESPACES=true` — the running instance (PID 3209) was started manually without it. Restarted with correct env. **(ISS-046-B)** `research-agent` and `reasoning-agent` launched by supervisor.sh at devcontainer boot before `OPENROUTER_API_KEY`/`TAVILY_API_KEY` were available in process env → `tavily_available=false`, `llm_backend=mock`. Fix: `supervisor.sh` `launch_research_agent()` and `launch_reasoning_agent()` changed from bare `uvicorn` to `nohup python -m uvicorn` to ensure proper env inheritance; port 6543→5432 substitution added for research_agent DB URL (ISS-040 parity). **(ISS-046-C)** `planning-agent` used `sqlite+aiosqlite:///:memory:` because `PLANNING_DATABASE_URL` was not set and `DATABASE_URL` port 6543 was not converted to 5432. Fix: `supervisor.sh:launch_planning_agent()` now applies `sed 's/:6543\//:5432\//'` before passing to asyncpg. **(ISS-046-D)** `secrets.env.example` was missing `TAVILY_API_KEY` entry — developers copying the template would not know to add it. Fix: added `TAVILY_API_KEY=tvly-dev-your-key-here` to the example. **Live verified 2026-05-11:** `POST /compose → pipeline_mode="full", skills_active=["planning","research","reasoning"], composed_answer=<real OpenRouter LLM response in Arabic>, total_ms=39590` | `cogniforge_pipeline_invocations_total{mode="full"} 2.0` | `research-agent /health → tavily_available="true"` | `reasoning-agent /health → llm_backend="openrouter"` | `planning-agent /health → database="postgresql+asyncpg://..."` | Prometheus 12/12 targets UP | 79 cogniforge metrics active.**

| Service | Port | Health | Metrics | Pipeline Mode |
|---------|------|--------|---------|---------------|
| monolith (FastAPI) | 8000 | `{"application":"ok","database":"ok","version":"v4.1-root"}` | UP | N/A |
| user-service | 8001 | `{"service":"user-service","status":"ok"}` | UP (step=5) | N/A |
| planning-agent | 8002 | `{"service":"planning-agent","status":"ok","database":"postgresql+asyncpg://..."}` | UP (step=6) | **full** (DSPy+LLM) |
| conversation-service | 8003 | `{"status":"healthy","graph_ready":true,"step":"12"}` | UP (step=12) | LangGraph |
| orchestrator-service | 8006 | `{"status":"ok","graph_ready":true,"startup_state":"ready"}` | UP (step=10) | **full** (compose) |
| research-agent | 8007 | `{"status":"healthy","tavily_available":"true","step":"7"}` | UP (step=7) | **full** (Tavily) |
| reasoning-agent | 8008 | `{"status":"healthy","llm_backend":"openrouter","mcts_enabled":"true","step":"8"}` | UP (step=8) | **full** (MCTS+LLM) |
| content-retrieval-skill | 8009 | `{"status":"healthy","kb_files":2,"step":"11"}` | UP (step=11) | active |

**ISS-046 fix (2026-05-11):** All services above verified with real API keys. `pipeline_mode="full"` confirmed live. 79 cogniforge Prometheus metrics active. 12/12 scrape targets UP.

**BAC 2016 Numerical Functions + Knowledge Index applied 2026-05-13 (D-047):** Three improvements to the educational content system: **(1)** New knowledge base file `knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md` — complete BAC 2016 Session 1 Subject 2 Exercise 4 (Numerical Functions) with full model answer explanation. Historical note: 2016 is the only year in Algerian BAC history with two exam sessions. **(2)** New central knowledge index `app/services/capabilities/knowledge_index.py` — declarative registry of all available exercises with structured metadata (year, session, subject, exercise number, topics, tags). Replaces ad-hoc file scanning with `search_exercises()` (multi-criteria) + `find_best_match()` (tag-based). **(3)** `exercise_retrieval.py` upgraded: now extracts year/session/subject/exercise-number from query text and looks up the correct file via the index — eliminates the "always returns probability exercise" bug. New patterns added: numerical functions, complex numbers, session 1/2, exercise 4. New skill `docs/ai_skills/bac-exercise-explanation.md` — covers 2016 dual-session rule, LaTeX math rendering standards, model answer explanation methodology. `AGENTS.md` updated with new skill trigger rule.

**Microservices Step 12 applied 2026-05-11 (D-042 — Conversation Service Live Activation):** `conversation-service` activated as a **uvicorn process** on `:8003` — the sixth microservice in the Skills Architecture. Replaces the stub `main.py` (capability_level="stub") with a full Skill: LangGraph StateGraph (`intent_node → response_node`), Prometheus `/metrics` (11 metrics: `cogniforge_conversation_*`), HTTP `POST /chat/message`, WebSocket `/chat/ws` + `/admin/chat/ws`, lazy DB singleton with asyncpg URL normalization (ISS-038-B + ISS-040 fixes). Four artefacts: (1) `microservices/conversation_service/prom_metrics.py` — independent `CollectorRegistry`, 11 metrics; (2) `microservices/conversation_service/src/conversation_graph.py` — LangGraph StateGraph with `ConversationState` TypedDict, `_classify_intent()` (deterministic, no LLM), `_build_fallback_response()` (works without OPENROUTER_API_KEY), `asyncio.wait_for` timeout guard (30s); (3) `microservices/conversation_service/main.py` — FastAPI Skill v2.0.0 with lifespan warmup, `/health` + `/metrics` + `/chat/message` + `/chat/ws` + `/admin/chat/ws`; (4) `microservices/conversation_service/database.py` — lazy engine singleton, `_normalize_db_url()` converts `postgresql://` → `postgresql+asyncpg://`, strips `sslmode`. Supervisor STEP 4J launches it automatically. Prometheus scrape target at `localhost:8003` with `step="12"`. Grafana dashboard `140-microservices-step12-conversation-service.json` (15 panels, UID `cogniforge-ms-step12-conversation`, 10s refresh). CI gate `.github/workflows/microservices-step12-conversation-service.yml` (7 jobs). 117 tests in `tests/microservices/conversation_service/test_step12_conversation_service.py`. **pytest.ini** updated: added `ignore::UserWarning` + `ignore:.*allowed_objects.*` to suppress LangGraph internal deprecation warnings. `tests/microservices/conversation_service/conftest.py` added to suppress `LangChainPendingDeprecationWarning` at fixture-import level.

**Microservices Step 11 applied 2026-05-11 (D-041 — Full Skills Pipeline Live):** Skills Pipeline upgraded from `pipeline_mode="partial"` to `pipeline_mode="full"` — all 3 Skills (planning+research+reasoning) now execute concurrently with real LLM. Four fixes: **(ISS-042-A)** `_generate_service_token()` added to `skills_pipeline.py` — generates JWT HS256 (`sub="api-gateway"`, exp=5min) sent as `X-Service-Token` header to planning-agent (which requires it); **(ISS-042-B)** `dspy.OpenAI` → `dspy.LM` with `openrouter/` prefix in `planning_agent/main.py` — DSPy 3.x removed `dspy.OpenAI`; **(ISS-042-C)** `asyncio.gather` 3-way parallel (planning+research+reasoning simultaneously, not sequential); **(ISS-042-D)** timeout raised 10s→55s for LLM latency (~30-45s). `SECRET_KEY` unified to `super_secret_key_change_in_production` across orchestrator+planning-agent. New microservice **content-retrieval-skill** on `:8009` — converts exercise retrieval from keyword matching to a proper Skill: `intent_classifier.py` (explanation/retrieval/unknown, 3-phase logic, ISS-038 fix), `retrieval_engine.py` (score-based retrieval from `knowledge_base/`), `main.py` (POST /retrieve + GET /health + GET /metrics), `prom_metrics.py` (7 metrics: `cogniforge_retrieval_*`). Supervisor STEP 4I launches it automatically. Prometheus scrape target at `localhost:8009` with `step="11"`. Grafana dashboard `120-microservices-step11-full-skills.json` (15 panels, UID `cogniforge-ms-step11-full-skills`, 10s refresh). CI gate `.github/workflows/microservices-step11-full-skills.yml` (7 jobs). 63 tests in `tests/microservices/content_retrieval_skill/test_step11_content_retrieval_skill.py`. **Live verified 2026-05-11:** `POST /compose → pipeline_mode="full", skills_active=["planning","research","reasoning"], total_ms=32069` | `cogniforge_pipeline_invocations_total{mode="full"} 1.0` | `GET /health (8009) → {"status":"healthy","step":"11","kb_files":2}` | `POST /retrieve (BAC) → intent="retrieval" total=1` | `POST /retrieve (explanation) → intent="explanation" total=0 (ISS-038 FIXED)`.

**Microservices Step 10 applied 2026-05-11 (D-040 — Postgres Checkpointer):** `AsyncPostgresSaver` activated as the LangGraph checkpointer — LangGraph state now persisted to PostgreSQL (durable across restarts). `_InstrumentedCheckpointer` is a **subclass** of `AsyncPostgresSaver` (not a wrapper) because LangGraph validates `isinstance(checkpointer, BaseCheckpointSaver)` in `ensure_valid_checkpointer()` — ISS-041. `_make_instrumented_class(AsyncPostgresSaver)` factory creates the subclass at module load time. `AsyncConnectionPool` (psycopg, max_size=5) uses port 5432 (direct PG, not PgBouncer 6543). `_build_psycopg_conninfo()` converts `postgresql+asyncpg://` → `postgresql://` for psycopg. Six artefacts: (1) `prom_metrics.py` — 6 new metrics: `cogniforge_checkpointer_writes_total{thread_id_prefix,status}`, `cogniforge_checkpointer_reads_total{thread_id_prefix,status}`, `cogniforge_checkpointer_duration_seconds{operation}`, `cogniforge_checkpointer_errors_total{error_type}`, `cogniforge_checkpointer_active_threads`, `cogniforge_checkpointer_backend_info{backend,step,pool_size,tables_ready}` + `startup_info{checkpointer_backend}`; (2) `database.py` — `_make_instrumented_class`, `_InstrumentedCheckpointer`, `_build_psycopg_conninfo`, `init_db` with pool + setup + Prometheus registration, non-fatal fallback to MemorySaver; (3) `routes.py` — `GET /checkpointer/status` endpoint; (4) `main.py` — `checkpointer_backend` detection + `set_startup_info(..., checkpointer_backend=...)`; (5) `observability/native/prometheus.yml` — `postgres-checkpointer` scrape job at `localhost:8006` with `step="10"`; (6) Grafana dashboard `130-microservices-step10-postgres-checkpointer.json` (13 panels, UID `cogniforge-ms-step10-checkpointer`, 10s refresh). CI gate `.github/workflows/microservices-step10-postgres-checkpointer.yml` (7 jobs). 101 tests in `tests/microservices/orchestrator_service/test_step10_postgres_checkpointer.py`. **Live verified 2026-05-11:** `GET /checkpointer/status → {"backend":"postgres","step":"10","active":true,"tables_ready":true,"active_threads":1}` | `cogniforge_checkpointer_writes_total{status="success",thread_id_prefix="warmup"} 7.0` | `cogniforge_checkpointer_backend_info{backend="postgres",step="10",tables_ready="true"} 1.0` | `cogniforge_orchestrator_startup_info{checkpointer_backend="postgres",graph_ready="true"} 1.0`.

**Microservices Step 9 applied 2026-05-11 (D-039 — Skills Composition Pipeline):** `orchestrator-service` upgraded from isolated service to **Composition Engine** — first real cross-service HTTP calls in the system. New `/compose` endpoint calls `planning-agent:8002` + `research-agent:8007` in parallel via `asyncio.gather`, then `reasoning-agent:8008` with composed context. `X-Correlation-ID` on every inter-service call. Automatic fallback: `ConnectError`/`TimeoutException` → `SkillResult(status="fallback")` — pipeline continues. Six artefacts: (1) `microservices/orchestrator_service/src/services/skills_pipeline.py` — `run_skills_pipeline()`, `_call_planning_skill()`, `_call_research_skill()`, `_call_reasoning_skill()`, `_compose_answer()`, `_determine_pipeline_mode()`; (2) `prom_metrics.py` — 6 new metrics: `cogniforge_pipeline_invocations_total{mode}`, `cogniforge_pipeline_duration_seconds`, `cogniforge_pipeline_skill_calls_total{skill,status}`, `cogniforge_pipeline_skill_duration_seconds`, `cogniforge_pipeline_errors_total`, `cogniforge_pipeline_active_gauge` + `startup_info{pipeline_enabled="true"}`; (3) `routes.py` — `/compose` endpoint with `ComposeRequest`/`ComposeResponse` Pydantic models; (4) `config.py` — port fix: planning-agent 8001→8002, user-service 8003→8001; (5) `supervisor.sh` + `.ona/automations.yaml` — `CODESPACES=true` + `PLANNING_AGENT_URL/RESEARCH_AGENT_URL/REASONING_AGENT_URL` added to orchestrator launch; (6) `observability/native/prometheus.yml` — `skills-pipeline` scrape job at `localhost:8006` with `step="9"`. Grafana dashboard `120-microservices-step9-skills-pipeline.json` (12 panels, UID `cogniforge-ms-step9-pipeline`, 10s refresh) at :3001. CI gate `.github/workflows/microservices-step9-skills-pipeline.yml` (7 jobs). 87 tests in `tests/microservices/orchestrator_service/test_step9_skills_pipeline.py`. **Live verified:** `POST /compose → {"pipeline_mode":"partial","skills_active":["research","reasoning"],"total_duration_ms":41.4}` | `GET /metrics → cogniforge_pipeline_invocations_total{mode="partial"} 1.0` | `cogniforge_orchestrator_startup_info{pipeline_enabled="true"} 1.0`.

**Microservices Step 8 applied 2026-05-11 (D-037 — Reasoning Agent Live Activation):** `reasoning-agent` activated as a **uvicorn process** on `:8008` (no Docker — Codespaces constraint). Fifth microservice to go ACTIVE. MCTS (Monte Carlo Tree Search) always enabled; LLM (OpenRouter/OpenAI) active when key present, mock mode otherwise. ISS-039-B applied: `AIService` is NOT instantiated at import time in `main.py` — lazy singleton pattern prevents `OpenAIError` at startup without API key. Six artefacts: (1) `microservices/reasoning_agent/requirements.txt` — `prometheus-client>=0.20.0` added; (2) `microservices/reasoning_agent/prom_metrics.py` — independent `CollectorRegistry`, 11 metrics: `cogniforge_reasoning_requests_total`, `cogniforge_reasoning_request_duration_seconds`, `cogniforge_reasoning_active_connections`, `cogniforge_reasoning_invocations_total`, `cogniforge_reasoning_invocation_duration_seconds`, `cogniforge_reasoning_mcts_expansions_total`, `cogniforge_reasoning_mcts_errors_total`, `cogniforge_reasoning_llm_calls_total`, `cogniforge_reasoning_llm_errors_total`, `cogniforge_reasoning_fallback_responses_total`, `cogniforge_reasoning_startup_info{step="8",llm_backend=...,mcts_enabled="true"}`; (3) `microservices/reasoning_agent/main.py` — `/metrics` endpoint + enhanced `/health` (returns step/llm_backend/mcts_enabled) + `set_startup_info()` in lifespan; (4) `supervisor.sh:launch_reasoning_agent()` — STEP 4H, starts uvicorn on `:8008` at Codespace boot when `DATABASE_URL` set, injects `OPENROUTER_API_KEY`; (5) `.ona/automations.yaml` — service `reasoning-agent` + tasks `verify-step8-reasoning-agent`, `restart-reasoning-agent`, `run-step8-tests`; (6) `observability/native/prometheus.yml` — `reasoning-agent` scrape target at `localhost:8008` with `step="8"` label. Grafana dashboard `110-microservices-step8-reasoning-agent.json` (20+ panels, UID `cogniforge-ms-step8-reasoning-agent`, 10s refresh) at :3001. CI gate `.github/workflows/microservices-step8-reasoning-agent.yml` (7 jobs). 79 regression tests in `tests/microservices/reasoning_agent/test_step8_reasoning_agent_metrics.py`. **Live verified:** `GET /health → {"status":"healthy","service":"reasoning-agent","step":"8","llm_backend":"openrouter","mcts_enabled":"true"}` | `GET /metrics → cogniforge_reasoning_startup_info{...,step="8",...} 1.0`.

**Microservices Step 6 applied 2026-05-10 (D-035 — Planning Agent Live Activation + Docker Compose Stack):** `planning-agent` activated as a **uvicorn process** on `:8002` (no Docker — Codespaces constraint). Third microservice to go ACTIVE. DSPy + LangGraph with fallback chain when `OPENROUTER_API_KEY` absent. Eight artefacts: (1) `microservices/planning_agent/prom_metrics.py` — independent `CollectorRegistry`, 11 metrics: `cogniforge_planning_requests_total`, `cogniforge_planning_request_duration_seconds`, `cogniforge_planning_active_connections`, `cogniforge_planning_plans_total`, `cogniforge_planning_plan_duration_seconds`, `cogniforge_planning_dspy_invocations_total`, `cogniforge_planning_dspy_errors_total`, `cogniforge_planning_fallback_plans_total`, `cogniforge_planning_db_operations_total`, `cogniforge_planning_db_duration_seconds`, `cogniforge_planning_startup_info{step="6",dspy_available=...}`; (2) `microservices/planning_agent/main.py` — `/metrics` endpoint + `set_startup_info()` in lifespan; (3) `supervisor.sh:launch_planning_agent()` — STEP 4F, starts uvicorn on `:8002` at Codespace boot when `DATABASE_URL` is set; (4) `.ona/automations.yaml` — service `planning-agent` + tasks `verify-step6-planning-agent`, `restart-planning-agent`, `run-step6-tests`, `docker-compose-stack`; (5) `observability/native/prometheus.yml` — `planning-agent` scrape target at `localhost:8002` with `step="6"` label; (6) `docker-compose.step6.yml` — Docker Compose stack with orchestrator-service + user-service + planning-agent (for non-Codespaces Docker environments); (7) Grafana dashboard `90-microservices-step6-planning-agent.json` (20 panels, UID `cogniforge-ms-step6-planning-agent`, 10s refresh) at :3001; (8) CI gate `.github/workflows/microservices-step6-planning-agent.yml` (7 jobs). 61 regression tests in `tests/microservices/planning_agent/test_step6_planning_agent_metrics.py`.


---

## 2) خريطة التنفيذ (Execution Topology)

# Frontend
# - Codespaces: supervisor.sh launches `npm run dev -- --port 3000` automatically
# - Replit:     `cd frontend && npm run dev`  (uses port 5000 from package.json)
# - Manual:     `cd frontend && npm run dev -- --port <PORT>`
cd frontend && npm run dev

# Health check
curl -s http://localhost:8000/health | python -m json.tool
```

---

## 3. Architecture at a Glance

```
Browser
  └── Next.js (port 5000 — supervisor.sh FRONTEND_PORT=5000, server.js binds 0.0.0.0:5000)
        └── next.config.js rewrites /api/* → localhost:8000
              └── FastAPI monolith (port 8000) — requires DATABASE_URL
                    ├── /api/security/login, /register
                    ├── /api/chat/ws  (WebSocket)
                    │     └── OrchestratorClient (fallback chain)
                    │           ├── [1] File count detection
                    │           ├── [2] content-retrieval-skill:8009 (ISS-038 fixed)
                    │           ├── [3] HTTP → orchestrator:8006/agent/chat (requires JWT auth)
                    │           └── [4] LangGraph local_graph.py ← PRIMARY HANDLER
                    │                   supervisor_node (intent: educational/chat/general)
                    │                   └── chat_node → OpenRouter (nvidia/nemotron-3-super-120b-a12b:free)
                    ├── /api/v1/auth/*, /api/v1/users/*
                    ├── /v1/content/*
                    └── /api/v1/data-mesh/*

Skills Pipeline (ACTIVE — verified live 2026-05-11):
  orchestrator:8006/compose
    ├── planning-agent:8002/plans  (requires X-Service-Token JWT)
    ├── research-agent:8007/execute  (requires caller_id + action fields)
    └── reasoning-agent:8008/execute  (requires caller_id + action + query fields)
  conversation-service:8003/chat/message  (requires "question" field, not "message")
  content-retrieval-skill:8009/retrieve  (intent classifier — ISS-038 fixed)

Infrastructure (verified live 2026-05-11):
  Grafana    → port 3001  — 16 dashboards active, GET /api/health → {"database":"ok"}
  Prometheus → port 9090  — 12 scrape targets ALL UP (verified via /api/v1/targets)
  Redis      → port 6379  (process running but app uses InMemoryCache — REDIS_URL not set)
  PostgreSQL → Supabase PgBouncer :6543 / Direct :5432 (asyncpg uses :5432)

Step 3/4 (uvicorn process — auto-starts via supervisor.sh when OPENROUTER_API_KEY set):
  orchestrator-service  → port 8006  (uvicorn process, OUTBOX_RELAY_ENABLED=true)
  DB: Supabase shared (ORCHESTRATOR_DATABASE_URL = DATABASE_URL)
  Prometheus scrape: localhost:8006/metrics (native/prometheus.yml, step="4")

Step 5 (uvicorn process — auto-starts via supervisor.sh when DATABASE_URL set):
  user-service          → port 8001  (uvicorn process, /metrics active)
  DB: Supabase shared (USER_DATABASE_URL = DATABASE_URL)
  Prometheus scrape: localhost:8001/metrics (native/prometheus.yml, step="5")

Step 6 (uvicorn process — auto-starts via supervisor.sh when DATABASE_URL set):
  planning-agent        → port 8002  (uvicorn process, /metrics active, DSPy+LangGraph)
  DB: Supabase shared (PLANNING_DATABASE_URL = DATABASE_URL)
  Prometheus scrape: localhost:8002/metrics (native/prometheus.yml, step="6")
  Docker Compose stack: docker-compose.step6.yml (orchestrator + user-service + planning-agent)

Step 7 (uvicorn process — auto-starts via supervisor.sh when DATABASE_URL set):
  research-agent        → port 8007  (uvicorn process, /metrics active, Tavily web search)
  Tavily: ACTIVE when TAVILY_API_KEY set — disabled otherwise (no crash)
  Prometheus scrape: localhost:8007/metrics (native/prometheus.yml, step="7")

Step 8 (uvicorn process — auto-starts via supervisor.sh when DATABASE_URL set):
  reasoning-agent       → port 8008  (uvicorn process, /metrics active, MCTS+LLM)
  LLM: openrouter when OPENROUTER_API_KEY set | openai when OPENAI_API_KEY set | mock otherwise
  MCTS: ALWAYS enabled (no external dependency)
  Prometheus scrape: localhost:8008/metrics (native/prometheus.yml, step="8")
  Live verified 2026-05-11: GET /health → {"status":"healthy","step":"8","llm_backend":"openrouter","mcts_enabled":"true"}

Step 9 (Skills Composition Pipeline — /compose endpoint in orchestrator-service):
  orchestrator-service  → port 8006/compose  (first real cross-service HTTP calls)
  Pipeline: planning:8002 + research:8007 (parallel) → reasoning:8008 (with context)
  Fallback: ConnectError/TimeoutException → SkillResult(status="fallback") — pipeline continues
  X-Correlation-ID: injected on every inter-service HTTP call
  6 new Prometheus metrics: cogniforge_pipeline_* (invocations, duration, skill_calls, errors, active)
  startup_info{pipeline_enabled="true"} — confirmed in /metrics
  Prometheus scrape: localhost:8006/metrics (job: skills-pipeline, step="9")
  Grafana: cogniforge-ms-step9-pipeline (12 panels, 10s refresh)
  Live verified 2026-05-11: POST /compose → {"pipeline_mode":"partial","skills_active":["research","reasoning"],"total_duration_ms":41.4}
  Config fix: planning-agent port 8001→8002, user-service port 8003→8001 in config.py
  supervisor.sh fix: CODESPACES=true + PLANNING_AGENT_URL/RESEARCH_AGENT_URL/REASONING_AGENT_URL added

Step 7 (uvicorn process — auto-starts via supervisor.sh when DATABASE_URL set):
  research-agent        → port 8007  (uvicorn process, /metrics active, Tavily web search)
  DB: Supabase shared (RESEARCH_DATABASE_URL = DATABASE_URL)
  Prometheus scrape: localhost:8007/metrics (native/prometheus.yml, step="7")
  Tavily: ACTIVE when TAVILY_API_KEY set | DISABLED (graceful) without key
  ISS-039: SuperSearchOrchestrator lazy singleton — no import-time credential errors
```

1. `app/*` = بوابة التركيب والتنسيق العام (Control Plane).
2. `microservices/*` = وحدات أعمال مستقلة (Execution Plane).
3. `docs/architecture/*` = الدستور المعماري وقرارات التصميم.
4. `.memory/*` = ذاكرة تشغيلية مختصرة يجب أن تعكس الواقع التنفيذي الفعلي.

---

## 4) مخاطر معمارية حالية

1. **Drift بين الوثائق والكود** عند تطور الخدمات بسرعة.
2. **Coupling خفي** إذا تم تمرير نماذج داخلية بين خدمات بدل عقود API صريحة.
3. **اختلاط أدوار app shell** إذا زاد منطق الأعمال داخل route handlers.
4. **تباين جاهزية الخدمات** بين local/dev/prod بدون health contracts موحدة.

---

## 5. Safe Areas to Modify

```
app/services/chat/local_graph.py    — add LangGraph nodes/edges
app/api/routers/content.py          — content endpoints
app/core/prompts.py                 — system prompts
app/services/system/                — system utilities
frontend/app/components/ChatInterface.jsx
frontend/app/components/AgentTimeline.jsx
tests/                              — add tests freely
scripts/                            — helper scripts
docs/                               — documentation
```

---

## 6. Common Pitfalls

### NEVER use `os.environ` directly in app code
```python
# ❌ Wrong
import os
db_url = os.environ["DATABASE_URL"]

# ✅ Correct
from app.core.config import get_settings
db_url = get_settings().DATABASE_URL
```

### NEVER use synchronous SQLAlchemy
```python
# ❌ Wrong — blocks the event loop
user = db.query(User).filter_by(email=email).first()

# ✅ Correct
from sqlalchemy import select
result = await db.execute(select(User).where(User.email == email))
user = result.scalar_one_or_none()
```

### NEVER omit Codespaces origins from `allowedDevOrigins`
```javascript
// ❌ Wrong — Next.js 15+ blocks Codespaces proxy with ERR_HTTP_RESPONSE_CODE_FAILURE
allowedDevOrigins: ['*.replit.dev']

// ✅ Correct — include all hosting environments
allowedDevOrigins: [
    '*.replit.dev', '*.replit.app',
    '*.app.github.dev', '*.preview.app.github.dev',  // GitHub Codespaces
    '*.gitpod.io',                                    // Gitpod / Ona
]
```

### NEVER assume microservices are reachable
```python
# In Codespaces (default devcontainer), ALL of these fail with ConnectError:
# http://orchestrator-service:8006  → Docker DNS — not running
# http://user-service:8000          → not running
# http://research-agent:8007        → not running

# Only the `web` container runs by default (see .devcontainer/docker-compose.host.yml).
# LangGraph (local_graph.py) is the REAL handler — always falls through to it.
# To wake the microservices: `docker compose -f docker-compose.yml up -d` (separate stack).
```

### NEVER change the auth_persistence.py RETURNING pattern
```python
# ❌ Wrong — lastrowid doesn't work reliably with asyncpg/PostgreSQL
cursor = await conn.execute(insert_query)
user_id = cursor.lastrowid

# ✅ Correct — what's already there
result = await conn.execute(
    text("INSERT INTO users (...) VALUES (...) RETURNING id")
)
user_id = result.scalar()
```

### Port quirk
```python
# settings auto-converts PgBouncer port 6543 → 5432
# Don't override this behavior in database.py
```

### NEVER call `cognitive_engine.memorize()` without a None guard

```python
# ❌ Wrong — ISS-H3: get_cognitive_engine() returns None by default.
# Raises AttributeError on every successful LLM response.
self.cognitive_engine.memorize(prompt, context_hash, chunks)

# ✅ Correct — null guard required (simple_client.py:116)
if last_message.get("role") == "user" and self.cognitive_engine is not None:
    self.cognitive_engine.memorize(prompt, context_hash, chunks)
```

**Rule**: `CognitiveResonanceEngine` is a stub (`cognitive_cache.py` returns `None`). Until a real implementation is wired, every call site must guard against `None`. Do not remove the guard when implementing the real engine — make `get_cognitive_engine()` return a real instance instead.

### NEVER pass `postgresql://` to `create_async_engine` — use `postgresql+asyncpg://`

```python
# ❌ Wrong — SQLAlchemy maps postgresql:// to psycopg2 (sync driver)
# Raises: InvalidRequestError: The asyncio extension requires an async driver
create_async_engine("postgresql://user:pass@host/db")

# ✅ Correct — explicit asyncpg driver + strip sslmode (asyncpg uses connect_args for SSL)
create_async_engine("postgresql+asyncpg://user:pass@host/db")
```

**In supervisor.sh / automations.yaml** — convert at launch time:
```bash
_url="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg://}"
_url=$(echo "$_url" | sed 's/[?&]sslmode=[^&]*//')
```

This affects `orchestrator-service` and `planning-agent`. The monolith uses `aiosqlite`/`asyncpg` correctly via `app/core/database.py`. The microservices receive `DATABASE_URL` from the environment which always has the bare `postgresql://` scheme from Supabase.

### NEVER omit `TAVILY_API_KEY` from `docker-compose.yml` services that use web search

```yaml
# ❌ Wrong — WebSearchFallbackNode silently skips search; SuperSearchOrchestrator raises ImportError
environment:
  - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}

# ✅ Correct — safe default (empty string) prevents docker compose failure when key absent
environment:
  - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
  - TAVILY_API_KEY=${TAVILY_API_KEY:-}
```

**Affected services**: `orchestrator-service` (port 8006) and `research-agent` (port 8007). Key format must start with `tvly-`. MCP URL format (`https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-...`) is auto-sanitized in `readiness.py` and `super_search.py`.

### NEVER share a CollectorRegistry between microservices

```python
# ❌ Wrong — يُسبب تعارضاً إذا عملت الخدمتان في نفس الـ process (اختبارات)
from prometheus_client import Counter
requests = Counter("cogniforge_user_requests_total", "...")  # يستخدم REGISTRY الافتراضي

# ✅ Correct — registry مستقل لكل خدمة (نمط prom_metrics.py)
from prometheus_client import CollectorRegistry, Counter
_REGISTRY = CollectorRegistry()
requests = Counter("cogniforge_user_requests_total", "...", registry=_REGISTRY)
```

**Rule**: كل microservice يجب أن يستخدم `CollectorRegistry()` مستقلاً. استخدام `REGISTRY` الافتراضي يُسبب `ValueError: Duplicated timeseries` عند تشغيل اختبارات متعددة في نفس الـ process.

### NEVER add `dependsOn` to Ona automation services

```yaml
# ❌ Wrong — schema rejects it: additionalProperties: false
services:
  orchestrator-stack:
    dependsOn:
      - some-other-service  # FORBIDDEN in services

# ✅ Correct — use `ready` command to gate startup
services:
  orchestrator-stack:
    commands:
      ready: curl -sf http://localhost:8006/health
```

**Rule**: Only `tasks` support `dependsOn`. Services use the `ready` command as a readiness gate. A service stays in "Starting" phase until `ready` passes — this naturally gates any dependent workflow.

### NEVER try to use Docker in the default Codespaces devcontainer

```bash
# ❌ Wrong — Docker CLI not available in this devcontainer
docker compose -f docker-compose.step3.yml up -d
# Error: docker: not found

# ✅ Correct — orchestrator-service runs as a uvicorn process (Step 3)
# supervisor.sh starts it automatically at boot when OPENROUTER_API_KEY is set
# Manual restart:
gitpod automations service start orchestrator-service
# Or:
gitpod automations task start restart-orchestrator
```

**Why no Docker**: `devcontainer.json` intentionally omits `docker-in-docker` — it fails on `python:3.12-slim` + `network_mode: host` (Codespaces error 1302). The `docker-compose.step3.yml` file exists for future environments that support Docker (local dev, CI with DinD). In Codespaces, `supervisor.sh:launch_orchestrator_service()` is the canonical activation path.

### NEVER use a shared prometheus_client REGISTRY across monolith and orchestrator

```python
# ❌ Wrong — Step 4 lesson: using the default REGISTRY causes metric name collisions
# when both monolith and orchestrator run in the same process (tests, CI).
from prometheus_client import Counter
REQUESTS = Counter("cogniforge_requests_total", "...")  # registers in default REGISTRY

# ✅ Correct — use an independent CollectorRegistry per service
from prometheus_client import Counter, CollectorRegistry
_REGISTRY = CollectorRegistry()
REQUESTS = Counter("cogniforge_orchestrator_requests_total", "...", registry=_REGISTRY)
```

**Rule**: Every microservice that exposes `/metrics` must use its own `CollectorRegistry()`. Never import from `prometheus_client` without passing `registry=`. The monolith uses its own registry in `app/telemetry/`. The orchestrator uses `prom_metrics._REGISTRY`. They must never share.

### NEVER set OUTBOX_RELAY_ENABLED=false in production supervisor.sh after Step 4

```bash
# ❌ Wrong — Step 3 default, now obsolete after D-031 fulfilled in Step 4
OUTBOX_RELAY_ENABLED="false" \
nohup python -m uvicorn microservices.orchestrator_service.main:app ...

# ✅ Correct — Step 4 default (supervisor.sh and .ona/automations.yaml)
OUTBOX_RELAY_ENABLED="true" \
OUTBOX_RELAY_INTERVAL_SECONDS="15" \
OUTBOX_RELAY_BATCH_SIZE="50" \
nohup python -m uvicorn microservices.orchestrator_service.main:app ...
```

**Rule**: `OUTBOX_RELAY_ENABLED=false` was a Step 3 safety guard (D-031). Step 4 verified the persistence path — relay is now the default. Reverting to `false` silently disables event propagation without any error.

### NEVER use flat keyword matching for exercise retrieval intent detection

```python
# ❌ Wrong — ISS-038: triggers retrieval for ANY question containing "تمرين"
# regardless of context. "اشرح الجزء أ من هذا التمرين" → returns probability exercise.
retrieval_hints = ("تمرين", "تمارين", "درس", "احتمالات", "بكالوريا", ...)
recognized = any(hint in normalized for hint in retrieval_hints)

# ✅ Correct — two-phase intent classifier in exercise_retrieval.py:
# Phase 1: explanation/help intent → cancel retrieval (highest priority)
# Phase 2: explicit retrieval patterns (BAC, numbered, year+exercise) → trigger
# Default: no retrieval → fall through to LangGraph
from app.services.capabilities.exercise_retrieval import detect_exercise_retrieval, ExerciseRetrievalRequest
decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
# decision.recognized is True ONLY for explicit retrieval requests
# decision.reason explains why: "explanation_intent_detected" | "retrieval_intent_detected" | "no_clear_retrieval_intent"
```

**Rule**: When adding new retrieval trigger keywords, always add corresponding explanation-intent negation patterns. The explanation-intent list takes priority. When in doubt, do NOT trigger retrieval — LangGraph handles ambiguous questions better than a static knowledge base lookup.

---

## 6.5 Architecture Truth and Persistence Rules

**Single writer. Single terminal frame. No silent failure.** These are operational laws, not aspirations.

### Persistence authority (D-006)
- **Monolith owns `customer_messages` and `admin_messages`.** The Orchestrator microservice MUST NOT write unless the Monolith explicitly delegates via `compatibility_facade=True` and the Orchestrator signals back `persisted: true` on its terminal event.
- **User message** is always written by the Monolith at the WS entry point (`app/api/routers/customer_chat.py:save_message(USER)` / `app/api/routers/admin.py`). One write, no exceptions.
- **Assistant message** write is conditional:
  - `orchestrator_persisted == True` → Monolith **SKIPS** the local write and treats the turn as persisted.
  - `orchestrator_persisted == False` (signal absent or explicitly false) → Monolith does a **fail-safe write** with up to 2 retries. Absence of signal = failure.
  - If the fail-safe write also fails after retries → log `[CRITICAL_DATA_LOSS]` and surface a single terminal `error` to the client. Never claim success.

### How `persisted` is interpreted
- Source of truth: `app/infrastructure/clients/orchestrator_client.py:_normalize_stream_event` preserves `event["persisted"]` through the envelope so the Monolith router can read it on the terminal event (`complete` or `assistant_final`).
- Detection point: `app/api/routers/customer_chat.py` and `app/api/routers/admin.py` check `normalized_event.get("persisted") is True` while trapping the terminal event into `pending_terminal_event`.

### Terminal event guarantee (ISS-016 / ISS-017)
- Each turn emits **exactly one** terminal frame: either `assistant_final` (success) or `error` (failure). The helper `_emit_terminal_frames()` in both routers is the single emitter.
- `persisted` event is emitted **only after** a successful save (orchestrator-side or Monolith fail-safe).
- `shared/chat_protocol/event_protocol.py:normalize_streaming_event` passes `complete`, `persisted`, and `conversation_init` through unchanged. Do not add type coercion for these — it breaks terminal-event detection.

### Fallback path (`OrchestratorClient.chat_with_agent`)
- The fallback chain in `app/infrastructure/clients/orchestrator_client.py` (file-intelligence → exercise-retrieval → LangGraph → general-chat) **does not persist**. It returns content; the Monolith router persists.
- Each fallback emits `assistant_delta` followed by `assistant_final`. None of them set `persisted: true` — that flag is reserved for the real Orchestrator microservice after a confirmed `INSERT … COMMIT`.
- A failed fallback returns `None`; the chain advances. The terminal `error` is emitted once, by `_emit_terminal_frames` in the router, never silently.

### Things that MUST NOT change without an ADR
- The user message is written by the Monolith at the WS entry. Do not move this write into a service or into the Orchestrator.
- The `compatibility_facade=True` context flag is the handshake. Removing it re-enables Orchestrator user-message writes → dual-write.
- `_emit_terminal_frames()` is the only place that emits `assistant_final`/`error` and `persisted`. Do not duplicate this logic inline.
- The `persisted` key on terminal events is the single source of truth for write coordination. Do not rename, type-cast, or normalize it away.

### What to test before any merge that touches chat persistence
1. Normal path: orchestrator persists → Monolith skips → exactly one terminal `assistant_final` + one `persisted` event reach the client.
2. Fallback path: orchestrator unreachable → fallback runs → Monolith fail-safe writes → exactly one terminal frame + one `persisted` event.
3. Dual-write protection: with orchestrator awake AND `persisted=True`, only one row exists in `customer_messages` for that turn.
4. Terminal event guarantee: any failure path (DB error, empty response, stream interruption) ends with a single `error` frame — never a hang.
5. No silent failure: fail-safe write failure produces `[CRITICAL_DATA_LOSS]` log AND a terminal `error` to the client.

---

## 6.6 Architecture Truth and Runtime Rules (Truth Table)

> **The golden rule:** code presence ≠ runtime usage. A capability is real ONLY when proven by **import + call chain + runtime evidence**. Anything missing one of those three is treated as DORMANT or ZOMBIE until proven otherwise.
> **Last verified: 2026-05-09 — fifth pass. Live fixes applied: env injection, lifespan timeout, LangGraph metrics. See `.memory/runtime_truth.md` for the authoritative table.**

### Status legend
- **ACTIVE** — import + call chain + runtime evidence all present.
- **ACTIVE (no-op without ENV_VAR)** — import + call chain present; runtime effect absent without a specific env var.
- **PARTIAL** — on a live chain but only via fallback, conditional, or non-default branch.
- **DORMANT** — code real, gated behind an external service not started by default.
- **ZOMBIE** — no live call chain from any production entrypoint.
- **UNKNOWN** — insufficient evidence.

### Infrastructure truth (verified live 2026-05-09 — fifth pass)

| Service | Port | Status | Evidence |
|---|---|---|---|
| **Next.js** | **5000** | **ACTIVE** | `supervisor.sh` default `FRONTEND_PORT=5000`. `server.js` binds `0.0.0.0:5000`. `devcontainer.json` `onAutoForward: openBrowser` opens browser tab automatically. |
| **FastAPI** | **8000** | **ACTIVE** | `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`. 62 routes. Requires `DATABASE_URL` in **process env** (not just `.env` — see §6.8). |
| **Grafana** | **3001** | **ACTIVE** | `GET /api/health → {"database":"ok"}`. 5 dashboards. Prometheus datasource UP. All 3 targets scraping. |
| **Prometheus** | **9090** | **ACTIVE** | `GET /-/healthy → "Prometheus Server is Healthy."` Targets: fastapi UP, grafana UP, prometheus UP. |
| **Redis** | **6379** | **ACTIVE (process only)** | `ping() → True`. `REDIS_URL` not set in process env → app uses `InMemoryCache`. |
| **PostgreSQL** | **6543** | **ACTIVE** | PostgreSQL 17.6 Supabase PgBouncer. `database:ok` confirmed. |
| **OpenRouter** | external | **ACTIVE** | Primary: `nvidia/nemotron-3-super-120b-a12b:free`. Live graph call confirmed. |

### WebSocket protocol (confirmed live 2026-05-09)

```
# Auth
subprotocols=['jwt', TOKEN]  →  server selects 'jwt'

# Client → Server
{"question": "..."}          ← key is 'question', NOT 'content' or 'message'

# Server → Client stream
{"type": "conversation_init", "payload": {"conversation_id": 394, "request_id": "..."}}
{"type": "assistant_delta",   "payload": {"content": "...", "conversation_id": 394}}
{"type": "assistant_final",   "payload": {"content": "", "conversation_id": 394}}
```
Typical latency: 6–18s (OpenRouter free tier). `persisted` event only when orchestrator microservice active.

### Fallback chain timing (confirmed live 2026-05-09)

| Tier | Method | Result | Latency |
|---|---|---|---|
| 1 | `_build_local_file_count_response` | Returns file count string | ~499ms |
| 2 | `_build_local_retrieval_response` | Returns `None` (no BAC content match) | ~0ms |
| 3 | `_build_local_graph_response` | **PRIMARY** — full LangGraph response | ~10s |
| 4 | `_build_local_general_chat_response` | Fallback general response | ~10s |

### Truth table — last verified 2026-05-09 (second pass — all components live-tested)

| Component | Status | Live Evidence |
|---|---|---|
| **WebSocket customer chat** `/api/chat/ws` | **ACTIVE** | `conversation_init` → `assistant_delta` (391 chars) → `assistant_final`. Time: 6.79s. Conv_id=394 written to DB. |
| **WebSocket admin chat** `/admin/api/chat/ws` | **ACTIVE** | Admin token → `conversation_init` (conv_id=391) → streaming confirmed. |
| **LangGraph local engine** `local_graph.py` | **PARTIAL** | Fallback tier 3. `run_local_graph('ما هو تكامل x^2')` → LaTeX response 10.13s. Nodes: `['__start__', 'supervisor', 'chat']`. Intent bug: 'مرحبا' → 'general' (should be 'chat'). |
| **OrchestratorClient fallback chain** | **ACTIVE** | `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` → ConnectError → 4 local fallbacks. |
| **FastAPI + RealityKernel** | **ACTIVE** | `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`. |
| **DB via SQLAlchemy** | **ACTIVE** | `SELECT 1` → 1. Read ~2ms. INSERT+DELETE confirmed. |
| **AI Gateway (SimpleAIClient)** | **ACTIVE** | Primary: `nvidia/nemotron-3-super-120b-a12b:free`. 5 fallbacks. Live call confirmed. |
| **Cache (InMemoryCache)** | **ACTIVE (InMemoryCache only)** | `REDIS_URL` not set → `InMemoryCache`. SET/GET/DELETE confirmed. |
| **DSPy 3.2.1** | **ACTIVE (package) / DORMANT (in app)** | `dspy.LM` + `dspy.Predict` work. Only used in dormant microservices. No live call chain from `app/`. |
| **LlamaIndex 0.14.13** | **ACTIVE (package) / ZOMBIE (in app)** | `VectorStoreIndex` works with HuggingFace embeddings (score 0.8152). Requires explicit embed model — fails with default (needs `OPENAI_API_KEY`). `app/drivers/llamaindex_driver.py` exports `LlamaIndexDriver` — no live consumer. |
| **Reranker (CrossEncoder BAAI/bge-reranker-base)** | **ACTIVE (package) / DORMANT (in app)** | Model cached. Reranking works. Only in `microservices/research_agent` (DORMANT). `app/drivers/reranker_driver.py` has no `RerankDriver` export. |
| **KAgent mesh** | **ZOMBIE (security-blocked)** | `KagentMesh()` instantiates. `execute_action()` → `"⛔ Security Alert: Invalid token"`. No live consumer from `app/api/`. |
| **MCP server (8 tools)** | **DORMANT (instantiable, not wired)** | `MCPServer().initialize()` → OK. `get_tools_for_llm()` → 8 tools. `call_tool('get_project_metrics')` → works. Zero imports from live path. |
| **TLM (Trustworthy LM)** | **NOT INSTALLED** | `cleanlab` not installed. Zero references in `app/`. Not part of this codebase. |
| **Multi-agent workflow** (8 nodes) | **ZOMBIE (KAgent-blocked)** | `create_multi_agent_graph(ai_client, tools=[])` compiles. Nodes: `planner, researcher, writer, super_reasoner, procedural_auditor, reviewer, supervisor`. Invocation → `"⛔ Security Alert: Invalid token from planner_node"`. Only consumer: `tests/verify_graph_manual.py`. |
| **Orchestrator microservice StateGraph** | **DORMANT** | 13-node graph: `supervisor, query_rewriter, query_analyzer, retriever, reranker, web_fallback, admin_agent, tool_executor, chat_fallback, general_knowledge, synthesizer, validator`. Compiles and runs in isolation with `OPENROUTER_API_KEY`. NOT on live call chain — requires `docker compose -f docker-compose.yml up -d`. `cognitive_engine.memorize` bug on primary model (non-blocking, fallback models handle). |
| **Tavily (WebSearchFallbackNode)** | **DORMANT** | `tavily-python==0.7.24` installed. `TavilyClient` importable. Live search confirmed (2 results for BAC query). Only called from `orchestrator_service/src/services/overmind/graph/search.py:WebSearchFallbackNode` — which is DORMANT. `TAVILY_API_KEY` absent from `docker-compose.yml`. Silent skip when key missing. |
| **DSPy in orchestrator** | **DORMANT** | `QueryRewriterSignature`, `ChatFallbackSignature`, `IntentClassifier`, `AnalyzeQuery`, `EducationalSynthesizer` use DSPy. Importable. Not running. |
| **Research agent / SuperSearchOrchestrator** | **DORMANT** | `super_search.py` uses `TavilyClient` when key present, `DuckDuckGoSearchAPIWrapper` otherwise. `ddgs` package NOT installed — DuckDuckGo fallback broken. Not running. |
| **Research agent reranker** | **DORMANT** | `microservices/research_agent/src/search_engine/reranker.py` importable. Uses cached `BAAI/bge-reranker-base`. Not running. |
| **UnifiedObservabilityService** | **ACTIVE** | Every HTTP request traced. WS frames NOT traced per-frame (ISS-005). |
| **OTEL SDK** | **ACTIVE (no-op)** | `OTEL_EXPORTER_OTLP_ENDPOINT=http` (invalid URL) → no spans exported. |
| **Grafana + Prometheus** | **ACTIVE (infrastructure)** | Grafana port 3001. Prometheus port 9090. Both healthy. |
| **All other microservices** | **DORMANT** | Not started by `.devcontainer/docker-compose.host.yml`. |

### What this means for daily work

1. **The live stack is**: FastAPI + WS router + OrchestratorClient fallback → `local_graph.py` (2 nodes) → OpenRouter + PostgreSQL persistence.
2. **DSPy, LlamaIndex, Reranker are installed and work** — but none are wired to the live chat path. Adding them requires a wiring change in `local_graph.py` or `orchestrator_client.py`.
3. **KAgent security blocks the multi-agent graph** — all 8 nodes fail with "Invalid token". The graph compiles but cannot run without a valid internal KAgent token.
4. **MCP has 8 working tools** — but zero imports from live path. Easiest to activate: add `MCPServer` to `local_graph.py` chat node.
5. **TLM is not part of this codebase** — do not reference it.
6. **WS payload key is `question`** — not `content`, not `message`. Wrong key → `"Question is required."` error.
7. **Intent classification has bugs**: Arabic greetings ('مرحبا') → 'general' (should be 'chat'). English 'hello' → 'chat' (should be 'general').
8. **The advanced orchestrator graph (13 nodes) is DORMANT** — it compiles and runs in isolation but requires the full Docker Compose stack. See §6.7 for the complete revival roadmap.
9. **Tavily is installed and works** — but is only called from the DORMANT `WebSearchFallbackNode` inside the orchestrator microservice. The monolith fallback chain has no web search step. `TAVILY_API_KEY` is absent from `docker-compose.yml` and must be added before the full stack can use it.
10. **DuckDuckGo fallback is broken** — `ddgs` package not installed. If Tavily key is absent and the orchestrator is running, `SuperSearchOrchestrator` will raise `ImportError` on initialization.

### First-check protocol before any change to the chat / agent stack

1. Open `.memory/runtime_truth.md` (authoritative — 34 rows, verified 2026-05-09 second pass).
2. Ask: is the component I'm touching ACTIVE, PARTIAL, DORMANT, or ZOMBIE?
3. If **DORMANT/ZOMBIE** → editing dead code unless also wiring it into a live path.
4. If **ACTIVE/PARTIAL** → confirm call chain still holds after change.
5. Status updates require: file:line evidence + import path + call-chain trace.

---

*Closing rule:* **Any component without all three of `import` + `call chain` + `runtime evidence` from `app/main.py` is DORMANT or ZOMBIE. "Loaded but never invoked" is PARTIAL, not ACTIVE.**

---

## 6.7 Consolidated Permanent Rules (D-173 — full §6.x narrative archived)

> **جراحة التوثيق (D-173 Stage 6):** الأقسام §6.7 → §6.144 (السرد التفصيلي الكامل لكل قرار
> D-006 → D-172، ~11,250 سطراً) نُقلت حرفياً إلى
> **`docs/archive/constitution-history/CLAUDE-SECTIONS-6x-FULL.md`** (لقطة مُجمَّدة، تُقرأ
> للتاريخ لا تُحدَّث). هذا القسم يوحّدها في **قواعد دائمة مصنّفة بالمجال** — العقد لا الموسوعة
> (DOC-DEBT-001). كل قاعدة تحمل رقم قرارها للرجوع إلى الأرشيف. تعليقات الكود التي تستشهد بـ§6.xx
> تظل صالحة (لا إعادة ترقيم — الأرشيف يحفظها).

### أ) قانون التفكيك والمانيفستات (D-163→D-172)
- **كل نقل verbatim** (سلوك مطابق بالبايت)؛ **كل استخراج = سطر واحد** في المانيفست المناسب،
  والبوّابات/الاختبارات تقرأ **المصدر المُركَّب** عبر قارئ المانيفست. المانيفستات الستة:
  `TUTOR_SOURCE_FILES` · `BRAIN_SOURCE_FILES` · `API_SOURCE_FILES` · `DOCTRINE_SOURCE_FILES` ·
  `CUSTOMER_CHAT_SOURCE_FILES` · `GRAPH_SOURCE_FILES` (+ `BRAIN ⊆ TUTOR` مفروض CI).
- **ممنوع إعادة أي دالة/مرحلة مُستخرَجة** إلى ملفها الأصلي (عودة الـ God-file). العقل وحدة واحدة
  (`probability_tutor_brain.py` جذر تركيب + 5 mixins)؛ الملفات المُفكَّكة لا تستورد أصلها أبداً؛
  إعادة التصدير بـ `# noqa: F401`.
- الفحوص **السلبية** (حظر وجود نصّ) تقرأ المصدر المُركَّب أيضاً — الفحص السلبي على ملف تقلّص محتواه
  يمرّ زوراً.

### ب) قانون الإقامة + late-binding (D-168)
- **قواعد إقامة FastAPI**: الـ `@router` handlers بمسارات literal تبقى في ملفها (بوّابة AST تقرأه
  وحده) — `routes.py` + `customer_chat.py:chat_stream_ws` لا تُستخرَج.
- **قاعدة late-binding**: رقِّع الوحدة التي **يعيش فيها المستدعي** — دالة مُنقولة تقرأ globals وحدتها
  الجديدة لا وحدة إعادة التصدير. أي monkeypatch على اسم مُعاد تصديره يستهدف وحدة موقع النداء.

### ج) قاعدة المرآة D-013 + فلتر D-102
- **D-013 (المرآة الثنائية)**: `_GREETING_PATTERNS`/`_EDUCATIONAL_PATTERNS` مُكرَّرة في
  `local_graph.py` **و** `path_observer.py`؛ سلسلة النماذج مُكرَّرة في العقلين (monolith + orchestrator).
  أي تعديل يُطبَّق في النسختين في نفس الـ PR.
- **D-102 (فلتر التاريخ)**: أي كاشف يقرأ `history` يُرشِّح `role in (user, assistant)` — رسالة
  system (برومبت النظام) ليست دليلاً من المحادثة أبداً (وإلا تسمّم التوجيه).

### د) قانون العقل التربوي (D-006 → D-160 — النظام ليس مُجيباً بل معلّماً)
- **الخدمات المصغرة + LangGraph + Skills = القلب الإلزامي للتوليد** (D-112): تعذّرها ⇒ `ORCHESTRATOR_REQUIRED`
  صريح، صفر سقوط صامت للتوليد المحلي (`REQUIRE_ORCHESTRATOR=1` افتراضي، `=0` rollback).
- **صفر LLM في مسار الأرقام**: كل الأرقام/الصحّة الاحتمالية من المحرك الرمزي الحتمي حصراً
  (`probability_skill` + `probability_tutor_brain`) — الـ LLM يُنتج **الفهم** (السرد السقراطي) لا **الحقيقة**.
- **القاعدة الذهبية السقراطية (D-113→D-155)**: لا تكشف نتيجةً أو خطوةً يستطيع الطالب توليدها؛ الشرح
  يستقبل **أسئلة-فقط** (`display_content`)؛ الإجابة النموذجية لوضع التحقق حصراً؛ كل مخرَج نهائي يمرّ
  عبر `sanitize_final_text`/`redact_final_answers`. «لم أفهم» = تشخيص + أدنى تلميح، لا إعادة اشتقاق.
- **الاعتراف والتقدّم (D-155/D-158/D-162)**: إجابة الطالب الصحيحة تُحكَم بالمحرك الرمزي وتُعترَف
  صراحةً وتُقدِّم؛ السؤال ليس إجابةً (بوّابة الفعل الكلامي، «هل» مستثناة)؛ `tutor_state.kc_progress`
  هو المصدر الوحيد لقرار الدور (evidence×ability×difficulty) — لا مسح نصّ التاريخ.
- **صفر تكرار حرفي** (`_recently_emitted` + مرساة `last_step_emitted`)؛ **لا تسرّب تفكير النظام**
  للطالب (D-117: ممنوع prepend «[توجيه تربوي]»، العمق يصل عبر `support_level`)؛ **فجوة الوهم**
  (assisted − durable) هي مقياس النجاح الوحيد (D-126/D-157).
- **البصري الحتمي للاحتمالات** (D-116): كل مكوّنات الاحتمالات `terminate_pipeline=True` (صفر سرد LLM)؛
  الكيانات من `parsed_entities` لا نثر الحل (ISS-120)؛ ممنوع `C_n^k=0` مضلِّل (رسالة تربوية بدله).

### هـ) قانون WebSocket (D-WS-* — من التأرجح إلى الاستقرار)
- **الاتصال خالٍ من قاعدة البيانات** (D-WS-CONN-001): الهوية من الـ JWT (`WsActor` +
  `decode_token_payload`)؛ عمل الـ DB لكل-دور في جلسته. دور الإدمن من `roles` ضمن الـ JWT (D-WS-CONN-002).
- **الرفض عند الاتصال 4401/4403 فقط**؛ الفشل العابر ⇒ `1013` (WS) / retry (HTTP `/me`)، لا طرد
  (D-WS-KICK-001/002). `/me` (401/403) هو الحَكَم الوحيد للطرد.
- **قفل إرسال متزامن** (`_locked_send_json` + `send_lock`) على كل `send_json` مشترك (D-096)؛
  **heartbeat/keepalive** أثناء الدور + liveness على أي رسالة واردة (D-WS-FLAP-002/005)؛ الواجهة
  honest-debounce (≤15s) لا كذب طويل (D-WS-FLAP-004).
- **البروكسي**: `server.js` يُمرِّر WS بمكتبة `ws` + طابور رسائل مبكرة + مستمع `upgrade` وحيد
  (يمنع 101 مزدوج من Next HMR — D-WS-PROXY-001/004). كل الأطر النهائية تُنهي الرسالة (D-WS-FINAL-001).

### و) قانون CI (الأخضر الإلزامي)
- **قوائم deselect تتقلّص فقط** (D-105): مواءمة الاختبارات لا تعطيلها؛ أي إدخال جديد يتطلّب إثبات
  «أحمر على main» + تعليق الجذر. **`required-ci` يَعُدّ skipped نجاحاً** (D-141#4) — لا تكسره.
- **نظافة الاختبارات** (D-105): ممنوع كتابة `sys.modules`/`os.environ` وقت الجمع (بوّابة
  `check_test_hygiene`)؛ `testpaths` صريح؛ subprocess يستخدم `sys.executable`.
- **صفر warning** (D-141): لا gitlink بلا `.gitmodules`؛ كل إجراء GitHub Actions على node24
  (`upload-artifact@v6+`)؛ `push:` مُقيَّد على `[main]` للفروع الميزة.
- **صدق runtime (§6.6)**: لا تُعلَن قدرة ACTIVE قبل البرهان الثلاثي (import + call chain + runtime
  evidence)؛ حتى ذلك FLAGGED/DORMANT. `runtime_truth.py --update` بعد أي تغيير قدرة.

### ز) جسر قاعدة البيانات + الأسرار + compose (D-DB-BRIDGE-001 · D-172)
- **جسر Supabase** (`scripts/db_bridge.py`): SQL عبر HTTPS:443 حين تُحجَب منافذ Postgres (5432/6543).
  للقراءة/التشخيص/DDL اليدوي فقط — لا كتابة مزدوجة (D-006). الأسرار من البيئة حصراً (git-ignored).
- **Docker full-stack قابل لإعادة الإنتاج** (D-172): الشبكة compose-managed؛ جسر أسرار تلقائي
  (`compose_env_from_secrets.sh`)؛ **الصحة لا تكذب** — خدمة على sqlite/mock تحت الإنتاج تُبلِّغ
  `degraded`؛ checkpointer=postgres مُثبَت (`verify_full_stack_docker.py`).

### ح) قانون التوليد الآمن (النماذج + الحُرّاس)
- **سلسلة النماذج** (D-067/D-167): PRIMARY = `openai/gpt-oss-20b:free`؛ نموذج أزاله OpenRouter من
  الطبقة المجانية (404) يُنزَل من PRIMARY فوراً ويُترَك بذيل السلسلة (تعافٍ آلي). نماذج reasoning-only
  (content=None) محظورة كـ PRIMARY. system prompts < 1500 حرف؛ box-drawing ممنوع.
- **حُرّاس المخرَج**: `arabic_stream_guard` (عربي فقط على البثّ)؛ `content_integrity`/`response_sanitizer`
  (حذف garbage لاتيني/CJK/⟦⟧/تعليمات مُسرَّبة)؛ `output_firewall`+`topic_lock` (V46) — كلها fail-open.

### ط) API-first + المهارات (D-100 · D-173 Stage 4/5)
- **كل خدمة (10/10) لها عقد OpenAPI** يغطّي مساراتها الفعلية، مفروض ببوّابة **دلالية**
  (`check_openapi_parity` — endpoints لا bytes، robust عبر إصدارات pydantic). المولِّد
  `scripts/contracts/export_openapi.py` هو SSOT.
- **منصّة Skills موحَّدة** (D-100): registry + `compose_text_refinement` + `/api/v1/skills`؛
  كل مهارة `import + call chain + runtime evidence` أو FLAGGED؛ لا ZOMBIE (بوّابة).
- **Kagent محذوف** (D-173 Stage 5): كان ZOMBIE محظوراً أمنياً — القدرة بلا مستهلك حي تُحذَف لا تُترَك stub.

---

## 6.8 الرؤية الثورية (أهداف جلسة D-173)

> **المصدر الحيّ لخارطة الطريق:** `.memory/roadmap.md` (ملخّص §0.6). المقاعد الملموسة لإضافة
> التقنيات: `docs/architecture/EXTENSION_SEAMS.md`.

النظام **مختبر معرفي / محرّك تفكير** لا مُجيب — يُنمذج تفكير الطالب ويشخّصه ويحسّنه. أهداف D-173:
- **API-first 100%** — عقود صريحة تحكم حدود الخدمات (10/10)، مفروضة ببوّابة تكافؤ دلالية.
- **قتل التعقيد** (SOLID/KISS/DRY/YAGNI) — God-files قُتلت، الملفات الضخمة فُكِّكت عبر مانيفستات DRY
  (استخراج = سطر واحد، البوّابات تقرأ المصدر المُركَّب، النقل verbatim).
- **إغلاق split-brain** — عقل حتمي واحد + port مستقل محروس بـ20 عقد تكافؤ؛ الانتقال التدريجي للخدمات
  المصغرة برافعة رجوع فوري (D-025).
- **جاهزية إضافة التقنيات المُتحقَّقة** — Kafka/VectorDB/RAG/LlamaIndex/DSPy/Reranker/MCP عبر **مقعد
  موجود** بشرط تبنّي صريح وبلا كود ميت (EXTENSION_SEAMS.md). RAG الحيّ يمتدّ فعلياً
  (`scripts/backfill_exercise_embeddings.py`).
- **مقياس النجاح الوحيد** — فجوة الوهم (الأداء المدعوم − القدرة غير المدعومة المؤجَّلة). ممنوع
  التحسين على مدة الجلسة/عدد الرسائل/الرضا اللحظي.

**قاعدة الإغلاق:** أي قدرة تُضاف تُثبَّت بالبرهان الثلاثي (import + call chain + runtime evidence)
قبل ACTIVE؛ حتى ذلك FLAGGED أو موثّقة كمقعد — لا ZOMBIE أبداً.

---

## 6.9 خريطة الإحالة إلى الأرشيف (§6.x → التاريخ الكامل)

كل قرار D-XXX له سرده الحرفي الكامل (النطاق، الأدلة، الملفات، التحقق الحي) في
**`docs/archive/constitution-history/CLAUDE-SECTIONS-6x-FULL.md`** (لقطة CLAUDE.md قبل جراحة D-173).
للتفاصيل التشغيلية الحيّة: `.memory/` (فهرسها `.memory/README.md` — `decisions.md` · `issues.md` ·
`runtime_truth.md` · `roadmap.md` · `architecture.md` · `pedagogical_os.md`). خريطة السلطة الكاملة:
`docs/DOCUMENTATION_INDEX.md`.

| المجال | القرارات (تفصيلها في الأرشيف + `.memory/decisions.md`) |
|--------|------------------------------------------------------|
| الاستمرارية والبثّ | D-006 · D-047 · D-048 · ISS-016/017 |
| العقل التربوي السقراطي | D-074 · D-104 · D-113 → D-160 |
| الاحتمالات الحتمية | D-075 → D-085 · D-116 · D-152/153 |
| WebSocket | D-WS-001 → D-WS-PROXY-004 · D-096 · ISS-092→101 |
| الواجهة/الثيم | D-049 → D-059 |
| تفكيك التعقيد | D-163 → D-172 |
| النماذج | D-060 · D-067 · D-088 · D-167 |
| التوثيق/CI | D-105 · D-141 · D-156 · **D-173** |
| البنية التحتية (Docker/Observability) | §6.10 → §6.18 · D-172 |
