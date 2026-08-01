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
- **Dual-Mode Routing is immutable (D-085 — 2026-05-23 · معدَّل بـD-116)**: `_build_calculated_ui` stamps every UI event with `routing_mode: "MODE_A" | "MODE_B"`. MODE_A = direct question, MODE_B = confusion («لم أفهم», «مفهمتش», «كيفاش», «اشرح لي»). The routing decision is made **inside** `_build_calculated_ui` — never re-computed in `chat_with_agent`; `routing_mode` is consumed downstream as `ctx.is_mode_b` (`turn_preempts_delivery.py`) to steer the fallback chain, and `_effective_question` in MODE_B prepends the Socratic instruction. ⚠️ **شرط `terminate_pipeline=False` لـMODE_B ألغاه D-116 (2026-06-16 · ISS-116)**: كل مكوّنات الاحتمالات تُنهي المسار (`True` في البُناة الأربعة) لأن سرد الـLLM بعد البصري كان مصدر غارباج حيّ. المُلغى لا يُعاد بلا ADR — وكان الدستور يحمل القاعدتين معاً حتى 2026-07-31 (D-192).
- **التمرين قيد النقاش مصدره واحد، وأوّلُه نصّ الطالب (D-191 — 2026-07-31 · ISS-140 د/د-2)**: `app/services/skills/exercise_context.py:ExerciseContextSkill` هو **الحاسم الوحيد**؛ ترتيبه: نصّ الطالب الحاضر ⇒ تمرينه في التاريخ (رسائل `user` فقط، D-102) ⇒ التمرين المرجعي **بتصريح منطوق** ⇒ `None`. الحرفية `CANONICAL_EXERCISE_QUERY` لها **موطن واحد** (كانت مكرَّرة في ٧ مواضع تُغذّي ١٢ موضع استدعاء، و`_load_canonical_combinations` تستقبل `question` و**ترميه** — فتعلّم الطالبُ مسألةً ليست مسألته). ⛔ **لا يُطبَع رقمٌ ولا كيانٌ لم يذكره الطالب دون تصريح** — ويشمل ذلك النصوص التعليمية الثابتة (`semantic_property_skill` · `understanding_state_skill` كانت تحمل تركيبة التمرين المرجعي حرفياً). السقوط إلى المرجعي يتطلّب **إشارة احتمالية موجبة**؛ «غياب موضوعٍ آخر» ليس دليلاً (ISS-140 أ). تحرسه `check_exercise_context_single_source` بدَينٍ مُجمَّد **فارغ**.
- **الكيانات المهيكلة نوعٌ لا شعار (D-191)**: `ParsedEntities`/`ParsedEntityComponent` (`probability_models.py`) هي عملة التركيبة، تُنتَج مرّةً واحدة (`extract_parsed_entities` من نصّ الطالب · `from_mapping` من بيانات مهيكلة مُلتزَمة في `knowledge_base/entities/*.json` — نفس شكل عمود `parsed_entities`) وتُستهلَك في كل مكان. **عمود `parsed_entities` في قاعدة البيانات ما زال بلا قارئ حيّ** ويُوثَّق كذلك (`.memory/runtime_truth.md`) — لا يُدَّعى وصلُه.
- **الكمّامة يبرّرها المكوّن المُسلَّم (D-191 · ISS-140 ج)**: `_stage_calculated_ui` يقرأ **حكم** `_normalize_stream_event`؛ سقوط الحمولة إلى `noop` (props > 16KB أو رفض تحقّق) ⇒ **لا `companion_text` ولا إطار نهائي**، وسجلّ `ui_component_dropped_promise_suppressed`، والمسار يبقى حيّاً. وعدٌ بشرحٍ لا يصل أسوأ من خطأ صريح (§0).
- **تعريف المفهوم واحد (D-193 — 2026-08-01)**: `shared/curriculum/registry.py` هو المصدر القانوني الوحيد لكل `concept_id` يُخزَّن أو يُصنَّف أو يُعرَض (٣٧ مفهوماً · رياضيات + فيزياء + علوم الطبيعة). كانت ثلاثة تعاريف متنافرة لا تتّفق أيّ اثنين (BKT · learning_path · memory_agent بمُعرَّفات مختلفة)، ونتيجتها أنّ أسئلة الفيزياء والعلوم كلّها تسقط إلى `"general"` — أي أنّ الطبقة المعرفية لا تقيس شيئاً في مادة معاملها **٦**. ⛔ **المُعرَّفات لا تُغيَّر** (مُخزَّنة في `student_bkt_analytics`)؛ الصيغ الأخرى `aliases`. `classify` تُرجِع `None` لا `"general"`. أداة التعريف تكسر العلامات المركّبة (ISS-109/112/114) فتُجرَّب صورة بلا أدوات تعريف؛ والعلامة القصيرة تختبئ داخل كلمة أخرى («شعاع» خطفت «الإشعاعي») فيحرسها اختبار بنيوي؛ والأولوية تُصرَّح بـ`specificity` لا تُصادَف.
- **القياس يصير جدولاً، والدعمُ يُقصِّر الفاصل (D-194 — 2026-08-01)**: `shared/scheduling/fsrs.py` (FSRS-5 حتمي، يرفع `SchedulingError` لا صفراً مضلِّلاً) + `ReviewSchedulerSkill` + `student_review_schedule` **مُلحَق-فقط**. إجابةٌ صحيحة بسقالةٍ كاملة ⇒ `HARD` لا `GOOD`، و`EASY` تتطلّب `support_level ≥ 5` **و** `durable ≥ 0.85` معاً — وإلّا أتمتنا وَهْم الطلاقة بدل محاربته (§0.6). غياب `support_level` = دعمٌ ثقيل (الغياب ليس دليل استقلال)، و`correctness_signal="unknown"` ⇒ **لا صفّ**. الجدولة معزولة ولا تكسر دور طالب.
- **الوليّ يرى ولا يقرأ الحلّ (D-195/D-196 — 2026-08-01)**: الربط **برضا الطالب بنيوياً** (`guardian_user_id` يبدأ `NULL`؛ لا مسار يربط حساب قاصر بلا فعلٍ منه)، ورمزٌ عشوائي تعمويّاً يُستبدَل مرّة، و`is_linked` بوّابة كلّ قراءة (مُعرَّف المسار ليس تفويضاً)، وغير المرتبط **404 لا 403**. ⛔ **تقرير الوليّ لا يستعلم عن `content` إطلاقاً** — حمايةٌ بنيوية لا مُرشِّح: مقتطفٌ واحد يجعله باباً خلفياً إلى الحلّ الممنوع (D-113). وفجوة الوهم تُعرَض له لا تُخفى. والمواظبة تُحسَب بتقويم الطالب (`Africa/Algiers`) لا UTC — ٠٠:٣٠ محلّياً هي اليوم السابق في UTC، فالحساب على UTC يكسر مواظبة كلّ من يدرس ليلاً.
- **الأرقام تعترف بجهلها (D-197/D-198 — 2026-08-01)**: أسماء أحداث المنتج قائمة مغلقة (`shared/analytics/events.py`) تُرفَض خارجها **عند الكتابة**؛ وتعريف الاحتفاظ يعيش في `shared/analytics/retention.py` لا في SQL (المحرّكان يختلفان، ونسختان = رقمان لنفس السؤال)؛ و**الفوج غير الناضج يُرجِع `null` لا صفراً** (صفرٌ يقرأ «فقدناهم» والحقيقة «لم يحن الوقت»)؛ والقُمع يتقاطع فلا يتجاوز ١٠٠٪. التحليلات لا تكسر دوراً أبداً. وفي التحصيل: **الحقّ (`entitlements`) هو العملة والقسيمة مصدر**، وبوّابة الاشتراك **اعتمادٌ واحد** (`app/deps/billing.py`)، والرمز يُخزَّن مُجزَّأً (سندٌ لحامله)، و**الحَكَم قيدٌ فريد في قاعدة البيانات لا فحصٌ في التطبيق** («افحص ثمّ اكتب» نافذة سباق تمنح شهرين بقسيمة). لا بوّابة دفع: SATIM مقعد موثَّق بصفر كود (`EXTENSION_SEAMS.md §8`).
- **الواجهة تُحكَم كما يُحكَم الخادم (D-199 — 2026-08-01)**: كلّ قيمة بصرية من `frontend/app/styles/tokens.css` (مدّتان وتسهيلٌ واحد)، تحرسها `check_design_tokens` بدَينٍ يتقلّص فقط + **حساب** تباين WCAG AA لكل زوج (رقمٌ في تعليق ليس تحقّقاً — تقديراتي الأولى كانت خاطئة). ⛔ **لا `@import` من نطاقٍ ثالث** (يحجب أوّل رسم؛ الخطّ عبر `next/font` مُستضافاً ذاتياً). ورقٌ دافئ لا أبيض صرف (القراءة ساعات). تقليل الحركة **شامل** (`*`) لا قائمة تنسى المُضاف غداً. أوّل رسمٍ ليس فارغاً. وميزانية حجم (`check_bundle_budget`) تُترجَم إلى ثوانٍ على 3G — والبناء الغائب **يُفشِل** البوّابة لا يمرّ بصفر.
- **الدستور يساوي الواقع ولا يناقض نفسه (D-192 — 2026-07-31)**: أيّ عددٍ قابل للتغيّر (المهارات · العقود) **يُشتَقّ** من مصدره ولا يُكتب في النثر؛ والكمّية الواحدة لا تحمل قيمتين في قسمين؛ وكل قاعدة تسمّي رمزاً تُختبَر على المصدر. تحرسه `check_constitution_reality` (بوّابة `doc-integrity`) — وُلِد من تناقضَين حقيقيَّين في هذا الملفّ نفسه: عددُ المهارات مكتوباً بقيمتين مختلفتين في §0.5 و§0.7، ونسبةُ API-first بقيمتين في §3 و§6.7.ط — وكل القيم الأربع كانت خاطئة. تفصيلها في `.memory/decisions.md` D-192.
- **Math Pipeline is 4 nodes, not 3 (D-080 — 2026-05-23)**: `enrich_node` (Node 4 — deterministic, no LLM) was added after `normalize_node`. It builds `ui_component` payload from the completed solution text. Topology: `classify → solve → normalize → enrich → END`. `MathPipelineState` and `invoke_math_pipeline` now return `ui_component: dict | None`. Removing `enrich_node` breaks Generative UI for all math questions.
- **ui_component flows through the full stack (D-080)**: `ConversationState` carries `ui_component`. `invoke_graph` returns it. `ChatResponse` (HTTP) and WebSocket payload both include it. `useAgentSocket.js` extracts it from the `assistant_final` payload and attaches it to the message; `ChatInterface.jsx` renders `GenerativeUIRenderer` **after** the text, only on `isComplete` — never during streaming. ⚠️ **المصدر المشروع للبطاقة هو المخرَج المُهيكَل وحده**: `_try_build_math_ui_component` (المونوليث) **مُعطَّلة دائماً** (`return None` — D-097/ISS-108) لأنها كانت تُقطّع نثر LLM حرّاً إلى «خطوات» بلا معنى؛ فموضعا الحقن في `_emit_terminal_frames` كودٌ ميت مقصود. المسار الحيّ هو `enrich_node` الحتمي (Node 4).
- **MathExplanationCard is the canonical math Generative UI component (D-080)**: مُسجَّلة في **الطرفين** — `GenerativeUIRenderer` (الواجهة) و`KNOWN_UI_COMPONENTS` (`app/contracts/streaming.py`). كانت في الواجهة فقط حتى 2026-07-31، فكان المُطبِّع يرفضها ولا تصل الطالب أبداً — **عقدٌ مُعلَن بنصفه** (D-192). Props: `{ math_type, label, intuition, steps[], hint, visual_metaphor }`. Any new math type must be added to `_MATH_TYPES` (math_pipeline.py), `_TYPE_LABELS`, `_MATH_HINTS`, `visual_metaphors` in `_build_ui_component`, and `TYPE_COLORS` in `MathExplanationCard.jsx`.
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

### الخدمات المصغرة كـ Skills

كل خدمة = Skill بعقد OpenAPI مُلتزَم. **الطوبولوجيا والمنافذ في §3** (طوبولوجيتان، منافذ
مختلفة لخمس خدمات) — لا تُنسَخ هنا (قاعدة D-188: لا حالةَ في العقد). المسار المُركَّب
`orchestrator → compose([PlanningSkill, ResearchSkill, ReasoningSkill])` هو **القلب الإلزامي
للتوليد** (D-112)، لا هدفٌ مؤجَّل.

### القاعدة الموحَّدة `BaseSkill` (D-179 — 2026-07-22)

المصدر الكائني الموحَّد لكل مهارة في المونوليث هو `app/services/skills/base.py:BaseSkill[InT, OutT]`
(ABC). كل مهارة (العدد **مُشتَقّ** من `app/services/skills/registry.py` — لا يُكتب هنا يدوياً،
D-192) تَرِث منه فتحصل على: هوية موحَّدة (`name`/`version`)، singleton كسول
لكل-صنف (`instance()` يُعيد `Self` — يستبدل نمط `_x_singleton` + `get_x_skill()`)، ونقطة دخول
polymorphic `run()` تُفوِّض لطريقة المهارة الأصلية (`invoke`/`align`/`decide`/`evaluate`/…). ومساعدا
`skill_counter`/`skill_histogram` يُوحِّدان حارس Prometheus المُعاد على `REGISTRY` العام (**بلا
`CollectorRegistry` جديد** — القاعدة «لا تشارك registry» تخصّ الخدمات المصغرة لا المونوليث). المحرك
الاحتمالي الحتمي (`probability_brain/*`) + `gateway`/model-chain **مُستثناة عمداً** (حماية مسار
الإجابة). أي مهارة جديدة يجب أن تَرِث `BaseSkill`.

### النواة المعرفية للتفكير (D-181 — 2026-07-22)

طبقة الاستدلال العامة المُتحقَّقة هي **`app/core/reasoning/`** (dep-free، stdlib، تستهلك
`app/core/foundations` فترفعها من DORMANT إلى ACTIVE بالبرهان الثلاثي): `arguments` (شجرة قضوية +
استلزام مُتحقَّق عبر `foundations.logic.entails` + كشف المغالطة الشكلية + مثال مضادّ + parser نصّي) ·
`causal` (رسم سبب→أثر + **سببية مقابل ارتباط** + مضادّ للواقع + كشف الدورة) · `decomposition` (بوليا +
فرز طوبولوجي) · `abstraction` (نمط + قاعدة متتالية بـ `Fraction` + تماثل بنيوي) · `mental_model`
(كيانات/علاقات/ديناميات + فحص تماسك). كل بدائية ترفع `ReasoningError` (لا صفر مضلِّل — §0).

فوقها **٦ مهارات على `BaseSkill`** (حتمية 100%، بلا LLM في المسار الأساسي، مقاييس + doctrine +
اختبارات): `LogicReasoningSkill` (المنطق/الاستدلال) · `CriticalThinkingSkill` (التفكير النقدي) ·
`ProblemDecompositionSkill` (حل المشكلات) · `CausalReasoningSkill` (فهم العلاقات السببية) ·
`AbstractionSkill` (التجريد) · `MentalModelSkill` (بناء النماذج الذهنية). المُوحِّد `compose_reasoning`
(registry، مرآة `compose_text_refinement`) يُركِّب مسار تفكير مُهيكَل لأي سؤال حرّ (تدهور رشيق).
مكشوفة API-first عبر `POST /api/v1/skills/reason`. **قاعدة دائمة:** الحقيقة (صحّة الاستدلال، السببية،
الترتيب، النمط) من `app/core/reasoning` + `foundations` حصراً — لا يُقرّرها الـ LLM؛ الـ LLM للسرد فقط.

### إكمال الجذور الأولى + النواة الحاسوبية (D-183 — 2026-07-23)

طبقة `app/core/foundations/` اكتملت لتغطّي **الجذور الأولى ما قبل البرمجة** الثلاث (المنطق/الفكر ·
الرياضيات · نظرية الحساب). أُضيفت ٩ وحدات حتمية dep-free (stdlib، ترفع `FoundationsError` لا صفراً
مضلِّلاً): **رياضيات** — `linear_algebra` (حلّ `Ax=b` بحذف غاوس + محدّد + رتبة) · `calculus` (اشتقاق
مركزي + تكامل سيمبسون + نهاية + جذر نيوتن + تايلور) · `statistics` (ارتباط + انحدار OLS + مجال ثقة +
t-stat + مئين) · `optimization` (نزول متدرّج + قطع ذهبي + تنصيف + برمجة خطّية ثنائية) · `graph_theory`
(مركّبات + دورات + فرز طوبولوجي + MST كروسكال + ثنائية التلوين + شجرة) · **نظرية الحساب** —
`data_structures` (Stack/Queue/MinHeap/LinkedList/BST) · `formal_languages` (DFA + محرّك regex مصغّر +
Dyck + اشتقاق نحوي) · `computability` (أكرمان + قابلية تقرير منتهية + اختزال + حدود Halting/Busy-Beaver
مُوثَّقة) · `complexity` (ترتيب النموّ + كتالوج P/NP/NP-complete + «P مقابل NP» بصدق).

مكشوفة كـ **Skill** (`FoundationsComputeSkill` على `BaseSkill` — `foundations_compute`) عبر
`POST /api/v1/skills/compute` (المونوليث) وفرع `compute` في `compose_reasoning`، و**كخدمة مصغّرة
API-first** `foundations-service` على `:8010` (contract ملتزَم؛ محرّكات مُوَرَّدة،
بلا استيراد `app`). دوالّ التفاضل/التحسين تُمرَّر كمعاملات كثير حدود (`[c0,c1,c2] → c0+c1x+c2x²`)
فيبقى السطح آمناً على JSON بلا `eval`. كل الكود الجديد مُغطّى اختبارياً 100%. **قاعدة دائمة:** الأرقام
والبنى من محرّكات `foundations` الحتمية حصراً — لا يُقرّرها الـ LLM (§0: الحقيقة الرمزية قبل اللغة).

### طبقة الرموز الرياضية (D-185 — 2026-07-28)

`shared/notation/registry.py` (dep-free، stdlib) هو **المصدر القانوني الوحيد** لمعنى كل رمز
يطبعه النظام (`C(n,k)` · `A(n,k)` · `n!` · `P(A)` · `P_A(B)` · `X` · `E(X)` · `Ω` · `∩` · `∪` ·
`Ā`)، بعلامات تُغطّي صيغ الطالب الحقيقية (فصحى/دارجة/فرنسية) وحارسَي التباس: الحروف المفردة
تتطلّب إشارة «حرف/رمز» صريحة ولا تُطابَق في سياق «الحادثة C»، والنيّة الحسابية تُلغي التعريف
فلا يُخطَف دورٌ حسابي. مكشوف كـ **Skill** (`NotationSkill` على `BaseSkill` — `notation`) عبر
`POST /api/v1/skills/notation` وفرع `notation` في `compose_reasoning`، و**كخدمة مصغّرة API-first**
`notation-service` على `:8011` (contract ملتزَم → **API-first 13/13**؛ نسخة مُوَرَّدة محروسة
بـ`check_notation_parity`، بلا استيراد `app`). الدور التعليمي يستعمل الفرع الحتمي **المحلّي**
(بلا شبكة، صفر زمن إضافي على الطالب) والخدمة للـAPI والوكلاء بتدهور رشيق. القواعد الدائمة في §6.7 (د).

### قواعد إلزامية لكل Skill جديد

1. **Skill يجب أن يرث `BaseSkill`** ويملك `/metrics` (أو `skill_counter`) — بدونه لا يُعتبر Skill حقيقياً
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

السرد الكامل لكل مرحلة في `.memory/cognitive_lab_philosophy.md` — هنا العقد فقط:

| المرحلة | القانون | الحامل اليوم |
|---------|---------|--------------|
| 1 · Interactive Object UI | الطالب يتفاعل مع كائنات لا يقرأ جداراً نصّياً | طبقة الـGenerative UI |
| 2 · Cognitive Modeling | النظام يقيس **كيف** يفكّر الطالب لا ماذا أجاب | `TutorStateService` |
| 3 · Diagnostic Socratic Feedback | «خطأ» ليست إجابة — يُسمّى العطب الذهني | `SocraticEvaluatorSkill` · `ConceptDiagnosisSkill` |
| 4 · Digital Twin of the Mind | خريطة معرفية حيّة لا درجة ساكنة | `BKTEngine` (قناتان + فجوة الوهم) |
| 5 · Dynamic Generation | لا بنك أسئلة ثابت — تمرين يستهدف الضعف بعينه | `PedagogicalPolicyEngine` |
| 6 · Simulation Engine | «مليون تجربة» داخل الكانفس (مقعد موثّق، لا كود) | `.memory/simulation_engine.md` |
| 7 · Error Memory | يتذكّر الهشّ ويتوقّع الخطأ قبل وقوعه | `TutorState` + `BKTAnalyticsService` + **جدولة FSRS (D-194)** |

**Execution Rule:** Any PR that degrades this vision into a standard text-based Q&A bot must be rejected.

**خريطة المراحل M0→M11 وحالتها:** `.memory/roadmap.md §4` هو **المصدر الوحيد**. جدول الحالة
لا يُنسَخ هنا — نسخةٌ ثانية من حالةٍ متحرّكة تتقادم ثم تكذب (قاعدة D-188، وهو بالضبط ما حدث
لجدول §6.6 بين 2026-05 و2026-07). والدَّين الهندسي D1→D7 وخارطة الوكيل M0→M4 في `§6.5` منه.

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
evidence). ACTIVE: Configuration, Skills Engine (D-100 — count derived from the registry), Hooks/Policy
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

في الحالتين الواجهةُ الخلفية على **8000**. أمّا الخدمات المصغّرة فلها **مساران حقيقيان**:
`.devcontainer/supervisor.sh` يُقلعها كعمليات uvicorn (STEP 4D→4L) عند توفّر الأسرار،
و`docker compose -f docker-compose.yml up -d` يُقلع الحزمة الكاملة (12 حاوية صحّية —
إثبات حيّ في D-182). **ليست dormant افتراضياً** — هذا ادّعاء مؤرَّخ سقط.

**البنية التحتية المصاحبة:** Grafana :3001 · Prometheus :9090 · Redis :6379 (العملية تعمل
لكن التطبيق يستعمل `InMemoryCache` ما لم يُضبَط `REDIS_URL`) · PostgreSQL عبر Supabase
(PgBouncer :6543 / مباشر :5432 — asyncpg يستعمل :5432).

**سجلّ الكوارث المُصلَحة ليس هنا.** كل «Known fix applied» مؤرَّخ (ISS-036 → ISS-093 ·
D-WS-\*) يعيش في [`.memory/issues.md`](.memory/issues.md) مع الجذر والدليل الحيّ، وكل قرار
معماري في [`.memory/decisions.md`](.memory/decisions.md). اللقطة المؤرَّخة التي كانت هنا:
`docs/archive/constitution-history/CLAUDE-SECTIONS-1-3-6.6-FULL.md §أ`.

> **قاعدة D-188:** الدستور يحمل **القوانين الدائمة** فقط. أي فقرة تبدأ بـ«Known fix applied
> <تاريخ>» أو «Step N applied <تاريخ>» تخصّ `.memory/`، لا هذا الملف — سردٌ مؤرَّخ في عقدٍ
> دائم يتحوّل حتماً إلى كذبٍ بمرور الوقت (هذا بالضبط ما حدث بين 2026-05-09 و2026-07-29).

---

## 2) خريطة التنفيذ (Execution Topology)

```bash
# Frontend
# - Codespaces: supervisor.sh launches the Next.js dev server on FRONTEND_PORT=5000
# - Replit:     cd frontend && npm run dev   (port 5000 from package.json)
# - Manual:     cd frontend && npm run dev -- --port <PORT>
cd frontend && npm run dev

# Health check
curl -s http://localhost:8000/health | python -m json.tool
```

---

## 3. Architecture at a Glance

```text
Runtime topology — **طوبولوجيتان حقيقيتان، لا واحدة** (وثِّق أيّهما تقصد):

  (أ) Codespaces / uvicorn (`.devcontainer/supervisor.sh` — الافتراضي في التطوير)
      frontend :5000 · monolith :8000 · user :8001 · planning :8002 · conversation :8003
      orchestrator :8006 · research :8007 · reasoning :8008 · content-retrieval :8009
      foundations :8010 · notation :8011 · Prometheus :9090 · Grafana :3001

  (ب) Docker Compose (`docker-compose.yml` — الهدف المعماري؛ 12 حاوية، D-182)
      api-gateway :8000 · planning :8001 · memory :8002 · user :8003 · observability :8005
      orchestrator :8006 · research :8007 · reasoning :8008 · auditor :8009
      conversation :8010 · notation :8011 · frontend :3000 · Postgres مستقلّة لكل خدمة

  ⚠️ المنافذ تختلف بين (أ) و(ب) لخمس خدمات (planning · memory · user · conversation ·
     auditor). المصدر القانوني للمنافذ المحكومة ببوّابة:
     `docs/architecture/PORTS_SOURCE_OF_TRUTH.json` + `config/microservice_catalog.json`.

مسار دور الطالب (كلتا الطوبولوجيتين):

  Browser → Next.js → /api/* → FastAPI monolith :8000
    └── /api/chat/ws  (WebSocket — المفتاح `question`)
          └── OrchestratorClient.chat_with_agent()
                ├── preempts حتمية (تحية · رموز · احتمالات — بلا LLM)
                ├── orchestrator-service :8006  ← القلب الإلزامي للتوليد (D-112)
                └── سلسلة سقوط محلية (تُقاس، لا تُخفى)

العقود: 13 عقد OpenAPI في `docs/contracts/openapi/` تحرسها `check_openapi_parity` (13/13).
التفصيل الحيّ: `.memory/architecture.md` · `.memory/runtime_truth.md`.
الطوبولوجيا المؤرَّخة 2026-05-11: `docs/archive/constitution-history/CLAUDE-SECTIONS-1-3-6.6-FULL.md §ب`.
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
# ❌ Wrong — a test / DI seam may inject cognitive_engine=None.
self.cognitive_engine.memorize(prompt, context_hash, chunks)

# ✅ Correct — defensive null guard (simple_client.py)
if last_message.get("role") == "user" and self.cognitive_engine is not None:
    self.cognitive_engine.memorize(prompt, context_hash, chunks)
```

**Rule (corrected D-180 — the old "stub returns None" claim was false):**
`get_cognitive_engine()` returns a **real Arabic-aware `CognitiveResonanceEngine`
singleton** (`cognitive_cache.py`), not `None`. The None-guard stays as **defensive
code** (a test or DI seam may inject `None`) — do not remove it. The engine is now
ACTIVE: `memorize()` stores every successful user turn and `recall()` is wired as a
resilience fallback in the gateway (see the D-180 cache rule in §6.7).

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
> **الحالات لا تُكتب هنا.** الجدول المرجعي الوحيد هو `.memory/runtime_truth.md` — يُحدَّث
> مع كل تغيير قدرة في نفس الـ PR (`python scripts/runtime_truth.py --update`).

### Status legend
- **ACTIVE** — import + call chain + runtime evidence all present.
- **ACTIVE (no-op without ENV_VAR)** — import + call chain present; runtime effect absent without a specific env var.
- **PARTIAL** — on a live chain but only via fallback, conditional, or non-default branch.
- **DORMANT** — code real, gated behind an external service not started by default.
- **ZOMBIE** — no live call chain from any production entrypoint.
- **UNKNOWN** — insufficient evidence.

### طوبولوجيا الحقيقة الجارية — **المصدر الوحيد: `.memory/runtime_truth.md`**

> ⚠️ **قاعدة D-188 (2026-07-29):** كان هنا جدول حقيقة مؤرَّخ بـ**2026-05-09** بقي مُجمَّداً
> بينما تحرّك النظام شهرين ونصف — فصار **يكذب** على كل وكيل يقرأ الدستور (نموذج PRIMARY
> محظور أمنياً، Kagent المحذوف يُذكر كمكوّن حيّ، رسم الأوركستريتور يُوصَف DORMANT وهو
> ACTIVE افتراضياً منذ D-163). **لا يُعاد جدولُ حالاتٍ إلى هذا الملف أبداً.**
>
> **الجدول الحيّ:** [`.memory/runtime_truth.md`](.memory/runtime_truth.md) — تحرسه بوّابة
> `doc-integrity` (تماسك المراجع) وبوّابة `runtime-truth`
> (`scripts/runtime_truth.py --check` مقابل `.runtime/truth_table.lock.json`).
> **اللقطة المؤرَّخة 2026-05-09:** `docs/archive/constitution-history/CLAUDE-SECTIONS-1-3-6.6-FULL.md §ج`.

### الثوابت التي لا تتقادم (تبقى هنا لأنها عقد لا حالة)

**بروتوكول WebSocket (ISS-052 — قانون دائم)** — المحادثة تعمل عبر WebSocket **حصراً**:
لا وجود لـ`POST /api/chat/messages` (يُرجع 404). المفتاح `question` (لا `content` ولا
`message`؛ الخطأ ⇒ `"Question is required."`)؛ المصادقة `subprotocols=['jwt', TOKEN]`
(ترويسة `Authorization` ⇒ `NegotiationError`)؛ التدفّق
`conversation_init → assistant_delta* → assistant_final`؛ **إطار نهائي واحد لكل دور**
(`_emit_terminal_frames` — §6.5).

**سلسلة السقوط في `OrchestratorClient`** — `file_intelligence → exercise_retrieval(2.0) →
exercise_explanation_with_context(2.5) → LangGraph(3.0) → general_chat(4.0)`. لا طبقة منها
تكتب في قاعدة البيانات (§6.5: الكاتب واحد).


### First-check protocol before any change to the chat / agent stack

1. Open `.memory/runtime_truth.md` (authoritative — read its own header for the last verification date; never trust a date pasted anywhere else).
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
  `local_graph.py` **و** `path_observer.py`؛ أي تعديل يُطبَّق في النسختين في نفس الـ PR.
- **D-013 لسلسلة النماذج (D-174 — مصدر واحد + بوّابة حتمية)**: المصدر القانوني الوحيد للسلسلة هو
  `shared/ai_models/model_chain.py` (dep-free، مشترك بين العقلين). الحرفيات المُثبَّتة أمنياً تبقى
  في `app/core/ai_config.py` + `microservices/orchestrator_service/src/core/ai_config.py`
  (دفاع عميق ISS-079)، وبوّابة `scripts/fitness/check_model_chain_parity.py` (AST، تُشغَّل في
  guardrails) تُثبت أن العقلين == السلسلة القانونية — تكافؤ محروس آلياً بدل «حرّر النسختين يدوياً».
- **D-102 (فلتر التاريخ)**: أي كاشف يقرأ `history` يُرشِّح `role in (user, assistant)` — رسالة
  system (برومبت النظام) ليست دليلاً من المحادثة أبداً (وإلا تسمّم التوجيه).

### د) قانون العقل التربوي (D-006 → D-160 — النظام ليس مُجيباً بل معلّماً)
- **الخدمات المصغرة + LangGraph + Skills = القلب الإلزامي للتوليد** (D-112): تعذّرها ⇒ `ORCHESTRATOR_REQUIRED`
  صريح، صفر سقوط صامت للتوليد المحلي (`REQUIRE_ORCHESTRATOR=1` افتراضي، `=0` rollback).
- **صفر LLM في مسار الأرقام**: كل الأرقام/الصحّة الاحتمالية من المحرك الرمزي الحتمي حصراً
  (`probability_skill` + `probability_tutor_brain`) — الـ LLM يُنتج **الفهم** (السرد السقراطي) لا **الحقيقة**.
- **طبقة الأسس النظرية (D-175)**: `app/core/foundations/` (dep-free، stdlib فقط) هي الركيزة الحسابية
  المُتحقَّقة — combinatorics · number_theory · logic · probability · information_theory · algorithms.
  كل بدائية ترفع `FoundationsError` عند خرق المجال (لا `0` مضلِّل). المصدر الموحّد للأعداد المُتحقَّقة
  (بدل `math.comb` المبعثر)؛ مكتبة خارج `skills/` جاهزة للاستهلاك — تُرقّى ACTIVE بالتوصيل الحيّ + البرهان الثلاثي.
- **القاعدة الذهبية السقراطية (D-113→D-155)**: لا تكشف نتيجةً أو خطوةً يستطيع الطالب توليدها؛ الشرح
  يستقبل **أسئلة-فقط** (`display_content`)؛ الإجابة النموذجية لوضع التحقق حصراً؛ كل مخرَج نهائي يمرّ
  عبر `sanitize_final_text`/`redact_final_answers`. «لم أفهم» = تشخيص + أدنى تلميح، لا إعادة اشتقاق.
- **الاعتراف والتقدّم (D-155/D-158/D-162)**: إجابة الطالب الصحيحة تُحكَم بالمحرك الرمزي وتُعترَف
  صراحةً وتُقدِّم؛ السؤال ليس إجابةً (بوّابة الفعل الكلامي، «هل» مستثناة)؛ `tutor_state.kc_progress`
  هو المصدر الوحيد لقرار الدور (evidence×ability×difficulty) — لا مسح نصّ التاريخ.
- **صفر تكرار حرفي** (`_recently_emitted` + مرساة `last_step_emitted`)؛ **لا تسرّب تفكير النظام**
  للطالب (D-117: ممنوع prepend «[توجيه تربوي]»، العمق يصل عبر `support_level`)؛ **فجوة الوهم**
  (assisted − durable) هي مقياس النجاح الوحيد (D-126/D-157).
- **النظام يعرّف كل رمز يطبعه (D-185 — 2026-07-28 · ISS-138)**: طالب سأل «ماذا نقصد بحرف C» عن
  رمزٍ طبعه المعلّم نفسه، فتُجوهِل سؤاله وأُعيد عليه الاشتقاق مع تسريب `14`/`165` — لأن كل نقاط
  المطابقة كانت مفتاحها **اسم المفهوم** لا **الرمز** (دائرة مغلقة: من لا يعرف الاسم لا يسأل).
  المصدر القانوني للرموز هو `shared/notation/registry.py` (dep-free)، مكشوفاً كخدمة **API-first**
  `notation-service :8011` وكمهارة `NotationSkill` بتدهور رشيق (الدور التعليمي يستعمل الفرع
  الحتمي المحلّي — بلا شبكة). **القواعد الدائمة:** (1) رمز يُبَثّ بلا إدخال في السجلّ ⇒ CI أحمر
  (`check_notation_definable`)؛ (2) **التعريف ليس إجابة** — أمثلة السجلّ محايدة وممنوع أن تحمل
  أرقام التمرين الجاري؛ (3) **الرمز قبل الكاشفات** — أي مسار شرح احتمالي يفحص طبقة الرموز أولاً،
  والتباس «الحرف C» بـ«الحادثة C» تسريبٌ كارثي؛ (4) حارس التكرار **متماثل** (القسمة على الأصغر)
  فـ«تكرار + إضافة» تكرارٌ حقاً؛ (5) نسخة الخدمة مُوَرَّدة ومحروسة بـ`check_notation_parity`
  (مصدر واحد + مرآة، لا نسخة ثالثة).
- **البصري الحتمي للاحتمالات** (D-116): كل مكوّنات الاحتمالات `terminate_pipeline=True` (صفر سرد LLM)؛
  الكيانات من `parsed_entities` لا نثر الحل (ISS-120)؛ ممنوع `C_n^k=0` مضلِّل (رسالة تربوية بدله).
- **البؤرة لاصقة، والتغطية كاملة، ولا بؤرة معلّقة (D-184 — 2026-07-28)**: «لم أفهم» تعني «لم أفهم ما
  شرحتَه للتوّ» ⇒ `_recover_recent_focus` يسترجع بؤرة الحوار **قبل** أي سقوط افتراضي؛ إعادة الضبط
  القسرية إلى `same_color_event` (التي جعلت المعلّم يقفز للألوان مهما سأل الطالب) **ممنوعة** كسلوك أوّل.
  وكل مُعرَّف تُرجعه `_detect_focus_step` **يجب** أن يقابل `step_id` حقيقياً في القصّة المُولَّدة
  (بوّابة في `tests/services/test_d184_full_exercise_coverage.py` — تمنع البؤر المعلّقة كصنف).
  ومتغيّر عشوائي يُعرّفه التمرين بتكافؤ الأرقام لا يجوز نمذجته على اللون (كان يعرض توزيعاً لمتغيّر
  آخر). الخطوات المعتمدة على الأرقام تُنبَعث فقط حين تُرجِع `number_parity_*` قيمةً — التعميم محفوظ (D-076).
- **الموضوع لا يُختطَف، و«التكرار» يعني تكراراً (D-190 · ISS-140)**: «اشرح لي قانون أوم» كان
  يتلقّى **قائمة تشخيص الاحتمالات** (مُبرهَن حياً، ومتكرّر على «أرخميدس»). **القواعد الدائمة:**
  (1) **الفعل العامّ لا يملك المادة** — `full_solution` يحتاج سياق موضوع (`_is_prob_context`)
  وإلّا حُيِّد إلى `unknown`؛ والحرس **عند نقطة الاستخدام** لا عند التشخيص. (2) **كل عدّاد يقرأ
  `question` و`history` يتجاوز نسخة الدور الحاضر** — المونوليث يحفظ الرسالة قبل بناء الدور
  (§6.5)، فبلا ذلك يُعَدّ سؤالٌ واحد **2** ويجتاز «الحيرة المتكررة» في أوّل رسالة. (3) **التدوين
  ليس نيّة** — `f(x)` تُحتسَب مع قرينة استرجاع فقط، و«احسب/أوجد/برهن» تُلغي جلب تمرين مخزَّن
  (ISS-038 بمفتاح جديد). (4) **بطارية لا تفحص الصلة تُصادق على كارثة** — البنيوية أعطت 8/8
  كاذبة حيث الصلة 7/9.
- **نيّة الطالب مصدرٌ واحد، والتعريف قبل المثال (D-186 — 2026-07-29 · ISS-139)**: ثلاث كوارث متتالية
  (ISS-128 · ISS-138 · ISS-139) جذرها **واحد**: كاشفات متعدّدة لنفس النيّة تتفرّق. في ISS-139 كانت
  ثلاث قوائم للنيّة التعريفية (23·13·27 علامة) لا تتّفق أيّ اثنتين، فسؤال «ماذا يقصد بالحرف C»
  صُنِّف `unknown` وأُجيب الطالب بمثالٍ عارٍ، ثم «لم أفهم» صفّرت الموضوع إلى سؤال الألوان.
  **القواعد الدائمة:** (1) **المصدر الوحيد لعلامات النيّة هو `shared/intent/registry.py`** —
  أي قائمة أخرى تُفشِل `check_intent_single_source` (AST، ضمن guardrails)، والدَّين المُجمَّد في
  `_FROZEN_DEBT` **يتقلّص فقط** (سابقة D-105؛ `tests/` مُستثنى لأن تعداد الصيغ فيه حارسٌ لا نسخة).
  (2) **سؤال نيّته `definition` لا يُجاب أبداً بنصٍّ يخلو من التعريف**، وإعادةُ السؤال إشارةُ
  «لم يصل» لا «تقدَّم» ⇒ التعريف + الرُّتبة التالية غير المُسلَّمة (صفر تكرار حرفي). (3) **ما سُلِّم
  لا يُعاد**: `_render` لا ينزل إلى رُتبة مُسلَّمة — التنزّل الأعمى كان يُفجّر حارس التكرار فيستبدل
  الردّ بـ«الحل الكامل» (تسريب 165·14). (4) **حقلا التعريف والمثال منفصلان** — حشو أحدهما في الآخر
  يُسمّم كشف الرُّتب المُسلَّمة. (5) **الحيرة المجرّدة + مفهوم نشط ⇒ مصفوفة التصعيد** لا probe
  الافتتاح (تمديد D-184). (6) **لا يُغلَق بلاغ كارثة بلا عقد ترانسكريبت** في `tests/transcripts/`
  يُعيد التمثيل على **مراحل الدور الحقيقية**، ويجب إثبات أنه **أحمر قبل الإصلاح**.

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
- **التجريد الصادق المفروض (D-176)**: كل port سداسي (`integration_kernel/contracts.py`) إمّا ACTIVE
  (driver مُسجَّل في `mcp/integrations.py`) أو ضمن `KNOWN_DORMANT` المُجمَّدة — تفرضه بوّابة
  `check_abstraction_consumed.py` (port جديد بلا مستهلك ⇒ فشل CI). حدود الخدمات مفروضة آلياً في
  guardrails (`check_no_cross_service_imports` · `check_ports_consistency` ·
  `check_single_brain_control_plane` · `check_core_kernel_acl`). الخريطة الصادقة: `.memory/architecture.md §10`.
- **تنفيذ الأوامر بـ`argv` لا بصدفة (D-187 · M0)**: كان `agent_tools` ينفّذ
  `subprocess.run(..., shell=True)` في ثلاثة مواضع خلف **قائمة منع**، بينما `ALLOWED_COMMANDS`
  مُعرَّفة **ولا يُشير إليها شيء** — قائمة سماح ميتة. مسبار حيّ أثبت مرور الثمانية، و`echo
  $(id -u)` **أعاد `0`**. **القواعد الدائمة:** (1) كل تنفيذ عملية فرعية في `app/`·
  `microservices/`·`shared/` يمرّ من `agent_tools/sandbox.run_sandboxed(argv, …)` — تفرضه
  بوّابة `check_no_shell_true` (دَينها المُجمَّد **فارغ**، ويتقلّص فقط). (2) **قائمة سماح
  مفروضة لا مُعلَنة**: قائمة المنع ناقصة دائماً بطبيعتها؛ الأمان بأن يكون الحقن **غير
  مُمثَّل** (`shell=False`) لا مُرشَّحاً. (3) **بلا شبكة افتراضاً** — `curl`/`wget` خارج
  القائمة؛ الشبكة قدرة تُمنَح صراحةً. (4) **سجن مسارات بـ`resolve()`** (يتبع الروابط) على
  `cwd` **ووسائط المسارات**. (5) **محتوى حرّ مشروع** (رسالة commit) يُمرَّر وسيطاً حرفياً
  (`args_list`) لا يُحشى في سلسلة. (6) **ممنوع توصيل أي مُخطِّط/LLM بالأدوات** قبل استكمال
  M1→M4 — القدرة ≠ الأمان.
- **الأثر الصادر يُمَدّ لا يُخترَع (D-189 · D4)**: كان **31** بناءً مباشراً لـ
  `httpx.AsyncClient(` مقابل **21** حقناً لـ`X-Correlation-ID` في **9** ملفّات — أي أن أكثر
  من ثلثي النداءات تعبر حدود الخدمات بلا هوية تتبّع. والأسوأ أن مواضع الحقن «الصحيحة» كانت
  تُولِّد `uuid4()` **جديداً** لكل نداء (`notation_skill.resolve_via_service`) فتقطع السلسلة
  بدل مدّها — ترويسةٌ موجودة وبلا قيمة. **القواعد الدائمة:** (1) كل نداء صادر يمرّ من
  `shared/http_client.correlated_client` (أو نسخة مُوَرَّدة محروسة بتكافؤ داخل الخدمة — نمط
  D-185)؛ تفرضه بوّابة `check_correlated_http` بـ**AST** لا grep، ودَينها المُجمَّد يتقلّص فقط
  في **الاتجاهين** (بناءٌ جديد أحمر، ودَينٌ أُغلق بلا تحديث الرقم أحمر أيضاً). (2) **المُعرَّف
  يُمَدّ**: الصريح ⇒ المحيط ⇒ التوليد **ملاذاً أخيراً**؛ وترويسة واردة لا تُطمس. (3) **الوجود
  ليس صحّة** — بوّابة تبحث عن نصّ الترويسة لا تكفي، لأن المُعرَّف المُخترَع يجتازها.
  (4) **مهلة صريحة دائماً**: `timeout=None` تعني الافتراضي لا انتظاراً مفتوحاً — الانتظار
  المفتوح على حدّ خدمة يحوّل البطء إلى تعليق. (5) `shared/` **لا يستورد `app`** ولا خدمةً
  شقيقة: المُعرَّف المحيط يُقرأ عبر **مُزوِّد مُسجَّل** (المونوليث يُسجِّل `ContextVar` القائم
  في `app/core/logging.py` — بلا مصدر سادس)، ومُزوِّد يفشل لا يُسقط النداء.

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
- **صمود الـ rate-limit — «يجيب على كل سؤال» (D-177 — 2026-07-22)**: عند 429 من الطبقة المجانية،
  `SimpleAIClient.stream_chat` لا يسقط فوراً إلى `safety_net`. البوّابة تُصنِّف 429 كـ `AIRateLimitError`
  (مع `retry_after`)، وتُشغِّل **مروراً ثانياً محدوداً** على النماذج المحدودة فقط بعد backoff قصير
  (`RATE_LIMIT_BACKOFF_MAX=5s`) — فالحدّ اللحظي العام يتعافى قبل الاستسلام. حارس **زمن أول محتوى**
  (`FIRST_TOKEN_TIMEOUT=30s`) يتخلّى عن نموذج بطيء/فارغ (قِيس `nemotron-nano-9b` 62s بمحتوى=0) بدل
  تجميد الدور. `cognitive_engine.memorize` محروس بـ None (بند CLAUDE.md). السلسلة المُثبَّتة أمنياً
  **لا تتغيّر** (ISS-107 يُبقي `nemotron-3-super-120b` محظوراً — تسرّب إنجليزي). جاهزية مفتاح مدفوع:
  `OPENROUTER_EXTRA_MODELS` (CSV) يُلحِق نماذج إضافية بذيل السلسلة runtime بلا مسّ الحرفيات المحروسة
  بالتكافؤ. مُتحقَّق حياً E2E (postgres محلي + WS): سؤال رياضي يفشل فيه PRIMARY (reasoning-only) ثم
  يجيب gemma بعربي+LaTeX سليم، والرسالة تُحفَظ. الحارس مشترك عبر `get_ai_client()` فيفيد **كل** وكيل ومهارة.
- **الكاش المعرفي عربيّ-أولاً + استرجاع الصمود (D-180 — 2026-07-22 · ISS-133)**: `CognitiveResonanceEngine`
  (`app/core/cognitive_cache.py`) هو كاش دلالي ضبابي. `_normalize` **يجب** أن يبقى مُدرِكاً لليونيكود
  (تجريد التشكيل + التطويل، توحيد الألف/التاء المربوطة/الألف المقصورة، `\w`) — النسخة القديمة
  `[^a-z0-9\s]` كانت تمسح **كل** حرف عربي فتُحوِّل recall/memorize إلى لا-عملية صامتة لكل مستخدمي
  المنصّة (ممنوع الرجوع إليها). `get_cognitive_engine()` يُعيد نسخة حقيقية (لا `None`). `recall()`
  مُفعَّل كطبقة **صمود** عند نقطة استنفاد سلسلة النماذج فقط في `simple_client.stream_chat` (قبل
  `SafetyNetService`): إجابة سابقة عالية الرنين بنفس `context_hash` أفضل من «لا يجيب» — يخدم
  «يجيب على كل سؤال» بلا التفاف على المسار العادي ولا على المحرك الرمزي. مقيَّد بعلم
  `COGNITIVE_CACHE_RESILIENCE_ENABLED` (افتراض on، رجوع فوري `=0`). مقاييس Prometheus:
  `cogniforge_cognitive_cache_{recall_total{result},memorize_total,resonance_score,size}` (بلا labels
  عالية الكاردينالية). ملاحظة: `SemanticCache` (`app/caching/semantic.py`، تطابق-hash عربيّ-آمن،
  ACTIVE في `ChatOrchestrator`) و`CognitiveResonanceEngine` (ضبابي، صمود gateway) دوران متمايزان.

### ط) API-first + المهارات (D-100 · D-173 Stage 4/5 · D-174)
- **كل خدمة لها عقد OpenAPI** يغطّي مساراتها الفعلية، مفروض ببوّابة **دلالية**
  (`check_openapi_parity` — endpoints لا bytes، robust عبر إصدارات pydantic). المولِّد
  `scripts/contracts/export_openapi.py` هو SSOT. **العدد مُشتَقّ** من
  `docs/contracts/openapi/*-openapi.json` — كان مكتوباً هنا يدوياً «11/11» بينما §3 يقول
  «13/13»، فناقض الدستورُ نفسه حتى 2026-07-31 (D-192).
- **منصّة Skills موحَّدة** (D-100): registry + `compose_text_refinement` + `/api/v1/skills`؛
  كل مهارة `import + call chain + runtime evidence` أو FLAGGED؛ لا ZOMBIE (بوّابة).
- **Kagent محذوف** (D-173 Stage 5): كان ZOMBIE محظوراً أمنياً — القدرة بلا مستهلك حي تُحذَف لا تُترَك stub.

### ي) Observability and Runtime Governance (الرصد وحوكمة التشغيل)
> **المصدر الحيّ الكامل:** `.memory/observability-topology.md` (طوبولوجيا الرصد + العقود الدلالية).
> بوّابة CI `observability-validation` تفرض بقاء هذا القسم + ذاك الملف (documentation lock).
- **Grafana Observability Stack** (منفذ 3001) + Prometheus (9090) هما لوحة الرصد؛ لكن **الأجهزة قبل
  التصوير** (Instrumentation before visualization): كل مقياس له عقد دلالي ومُصدِر مُتحقَّق في المصدر
  (D-016)، لا لوحات zombie تعرض صفراً دائماً. **الرصد للتشخيص لا الزينة**.
- **صدق runtime فوق اليقين الاصطناعي** (§6.6): لا قدرة تُعلَن ACTIVE قبل البرهان الثلاثي
  (import + call chain + runtime evidence)؛ حتى ذلك DORMANT/FLAGGED. `runtime_truth.py --check` بوّابة.
- **Degraded ≠ Dead**: خدمة تمرّ `/health` لكن warmup الرسم فشل = DEGRADED؛ يجب أن يكشفه `startup_state`.
  الأثر والمقاييس تخصّصان منفصلان؛ labels عالية الكاردينالية ممنوعة؛ الكتابة المزدوجة للـ DB ممنوعة.

---

## 6.8 الرؤية الثورية — القواعد الدائمة

> **المصدر الحيّ:** `.memory/roadmap.md` (ملخّص §0.6) · مقاعد التوسّع:
> `docs/architecture/EXTENSION_SEAMS.md`. أهداف الجلسات المؤرَّخة (D-173 وما بعدها) تعيش في
> `.memory/decisions.md` — لا في العقد (قاعدة D-188).

- النظام **مختبر معرفي / محرّك تفكير** لا مُجيب — يُنمذج تفكير الطالب ويشخّصه ويحسّنه.
- **API-first**: حدّ الخدمة هو **العقد لا اللغة**؛ كل خدمة لها عقد OpenAPI مفروض ببوّابة تكافؤ دلالية.
- **قتل التعقيد** (SOLID/KISS/DRY/YAGNI): لا God-files؛ الاستخراج سطرٌ واحد في مانيفست، والنقل verbatim.
- **إضافة أي تقنية عبر مقعد موجود** بشرط تبنٍّ صريح وبلا كود ميت (EXTENSION_SEAMS.md).
- **مقياس النجاح الوحيد**: فجوة الوهم (المدعوم − غير المدعوم المؤجَّل). **ممنوع** التحسين على
  مدة الجلسة/عدد الرسائل/الرضا اللحظي.

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
| الاحتمالات الحتمية | D-075 → D-085 · D-116 · D-152/153 · **D-182** · **D-184** |
| WebSocket | D-WS-001 → D-WS-PROXY-004 · D-096 · ISS-092→101 |
| الواجهة/الثيم | D-049 → D-059 |
| تفكيك التعقيد | D-163 → D-172 · **D-182** |
| النماذج | D-060 · D-067 · D-088 · D-167 · D-177 · D-178 |
| الكاش (Cache) | D-180 |
| Skills / OOP / الاستدلال | §0.5 · D-069 · D-100 · **D-179** · **D-181** · **D-183** |
| الرموز والنيّة واللغات | **D-185** · **D-186** · **ADR-006** |
| التوثيق/CI | D-105 · D-141 · D-156 · **D-173** · **D-179** · **D-182** · **D-184** · **D-192** |
| البنية التحتية (Docker/Observability) | §6.10 → §6.18 · D-172 · **D-182** |
| الأثر · الذاكرة · الموضوع · التمرين | **D-188** · **D-189** · **D-190** · **D-191** |
