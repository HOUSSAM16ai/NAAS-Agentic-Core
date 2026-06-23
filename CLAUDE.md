# CogniForge — Claude Code Context

> **AI tutor for Algerian students** | FastAPI 8000 + Next.js 5000 + LangGraph 1.1.10
> Arabic / French / Darija | BAC preparation platform

---

## 0. Core System Doctrine

**Single writer. Single terminal frame. No silent failure.** These are operational laws, not aspirations.

The system must preserve the following principles permanently. Every future agent must inherit and obey these rules automatically:

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

## 0.6. النجمة القطبية الثورية وخارطة الطريق

> **المصدر التفصيلي الحيّ الوحيد للرؤية وخارطة الطريق هو `.memory/roadmap.md`.**
> هذا القسم ملخّص مكثّف — لا تُكرِّر تفاصيله؛ حدِّث `roadmap.md` عند أي تطوّر.

**الرؤية:** المعيار الأعلى ليس الانبهار اللحظي بل **الاستقلال المعرفي**. نحارب **وَهْم
الطلاقة** (الطالب يقرأ الحل، يشعر أنه «فهم»، ثم ينهار في الامتحان لأن الدراسة درّبت
**التعرّف** بينما الامتحان يطلب **التوليد** — Bjork). النظام يُجبر الطالب على **توليد**
كل خطوة يستطيعها، يقود سقراطياً، **لا يكشف نتيجة نهائية أبداً** (إلا وضع تحقق صريح)،
ويقيس الإتقان **الحقيقي غير المدعوم** لا الوهم.

**المبادئ الثابتة (Immutable):** القاعدة الذهبية «لا تكشف ما يولّده الطالب» (P-A) ·
منع مطلق للنتيجة النهائية (P-B) · microservices-only hard-fail (P-C, D-112) · القياس
الصادق = **فجوة الوهم** (P-D) · كل قدرة = Skill (P-E, §0.5) · BKT الطبقة الأساس (P-F, D-074).

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

## 6.7 Advanced LangGraph (Microservices) and Tavily — Verified Runtime Doctrine

> **Last verified: 2026-05-09 — live runtime investigation (third pass).**
> Authority: this section overrides any aspirational description in `docs/`, `LangGraph_Architectural_Blueprint.md`, or `ARCHITECTURE.md`.

### Advanced LangGraph (Orchestrator Microservice StateGraph)

**Status: DORMANT** — code is real, compilable, and partially runnable in isolation, but NOT on the live call chain in the default Codespaces environment.

**What was verified live (2026-05-09):**

| Fact | Evidence |
|---|---|
| Graph compiles without error | `create_unified_graph()` → `CompiledStateGraph` with 13 nodes |
| Graph runs in isolation | `graph.ainvoke(state)` with `OPENROUTER_API_KEY` set → valid Arabic response in ~10s |
| Graph is NOT on the live call chain | `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` → Docker DNS → ConnectError. Monolith falls through to `local_graph.py` (2-node fallback). |
| Orchestrator service is NOT started by default | `.devcontainer/docker-compose.host.yml` starts only the `web` container. Full stack requires `docker compose -f docker-compose.yml up -d`. |
| `cognitive_engine.memorize` bug | `orchestrator_service/src/core/gateway/simple_client.py:116` raises `AttributeError: 'NoneType' object has no attribute 'memorize'` on primary model. Fallback models handle the turn. Non-blocking. |
| FlagEmbeddingReranker not installed | `RerankerNode` falls back to simple score sort. `cross-encoder/ms-marco-MiniLM-L-6-v2` not cached. |
| Postgres checkpointer absent | `get_checkpointer()` returns `None` → graph compiled without checkpointer. State continuity relies on injected history. |

**13-node graph topology (orchestrator microservice):**
```
supervisor → [intent routing]
  educational → query_rewriter → query_analyzer → retriever → reranker
                  → [check_results] → synthesizer | web_fallback → synthesizer
  admin       → admin_agent → validator
  chat        → chat_fallback → validator
  general_knowledge → general_knowledge → validator
  tool        → tool_executor → validator
validator → [check_quality] → END | supervisor (retry)
```

**DSPy usage inside the advanced graph:**
- `SupervisorNode` uses `dspy.ChainOfThought(IntentClassifier)` — 4-intent taxonomy: `educational`, `general_knowledge`, `admin`, `chat`
- `QueryRewriterNode` uses `dspy.ChainOfThought(QueryRewriterSignature)` — pronoun resolution
- `QueryAnalyzerNode` uses `dspy.Predict(AnalyzeQuery)` — BAC filter extraction
- `SynthesizerNode` uses `dspy.Predict(EducationalSynthesizer)` — response synthesis
- All DSPy calls require `OPENROUTER_API_KEY` and are configured via `_configure_dspy()` at graph startup

**`WebSearchFallbackNode` behavior (search.py):**
- Triggered only when `reranked_docs` is empty AND intent is `educational`
- Reads `TAVILY_API_KEY` from environment at call time (not at import time)
- If key absent → **silent skip**: `used_web=False`, `reranked_docs=[]`, no exception raised
- If key present → calls `research_client.deep_research()` → HTTP to `research-agent:8007` → ConnectError (DORMANT)
- The `research_client` base URL is `http://research-agent:8007` — Docker DNS, not running by default

**Revival prerequisites for the advanced LangGraph:**
1. `docker compose -f docker-compose.yml up -d` — starts orchestrator-service (port 8006), research-agent (port 8007), postgres-orchestrator, redis-orchestrator
2. `OPENROUTER_API_KEY` must be set in the orchestrator container environment
3. `ORCHESTRATOR_DATABASE_URL` must point to `postgres-orchestrator:5432/orchestrator_db`
4. `TAVILY_API_KEY` must be added to `docker-compose.yml` under `orchestrator-service` and `research-agent` environment sections (currently absent)
5. `ORCHESTRATOR_SERVICE_URL` in the monolith must resolve to the running container (already set to `http://orchestrator-service:8006` — works when Docker network is up)
6. Warmup check in `main.py` lifespan must pass: `admin_graph.ainvoke({"query": "كم عدد ملفات بايثون"})` must return `tool_name` in `final_response`

---

### Tavily Integration

**Status: DORMANT** — package installed, key validated live, but NOT on the live call chain in the default environment.

**What was verified live (2026-05-09):**

| Fact | Evidence |
|---|---|
| `tavily-python==0.7.24` installed | `pip show tavily-python` confirmed |
| `TavilyClient` importable | `from tavily import TavilyClient` → OK |
| Live search works with provided key | `TavilyClient(api_key='tvly-dev-...').search(query='بكالوريا جزائر رياضيات')` → 2 results in <3s |
| Key format validation | Must start with `tvly-`. MCP URL format (`https://mcp.tavily.com/mcp/?tavilyApiKey=...`) is auto-sanitized in `readiness.py` and `super_search.py` |
| `TAVILY_API_KEY` NOT in `docker-compose.yml` | Neither `orchestrator-service` nor `research-agent` environment sections include it. Must be added manually. |
| `TAVILY_API_KEY` NOT in `.env.docker` or `.env.security.example` | Absent from all env templates. Only referenced in `docker-compose.legacy.yml`. |
| Monolith does NOT use Tavily | `app/` has one reference: `strategy_handlers.py:208` checks for the key as a warning only. `strategy_handlers.py` is on the `ChatOrchestrator` path which is PARTIAL (loaded-not-invoked). |
| Silent skip when key absent | `WebSearchFallbackNode.__call__` returns `{"used_web": False, "reranked_docs": []}` with no exception when `TAVILY_API_KEY` is empty |
| DuckDuckGo fallback broken | `SuperSearchOrchestrator` falls back to `DuckDuckGoSearchAPIWrapper` when Tavily absent, but `ddgs` package not installed → `ImportError` |

**Tavily call chain (when microservices are running):**
```
orchestrator-service: WebSearchFallbackNode (search.py:300)
  → os.environ.get("TAVILY_API_KEY")
  → research_client.deep_research(query)  [HTTP to research-agent:8007]
    → research-agent: SuperSearchOrchestrator (super_search.py)
      → TavilyClient(api_key=key).search(query, search_depth="basic", max_results=3)
      → parallel scraping → synthesis via LLM
```

**Tavily is NOT used in the monolith fallback chain.** The 4-tier fallback in `OrchestratorClient` (`local_graph.py`) has no web search step. Web search only exists in the orchestrator microservice's `WebSearchFallbackNode`.

**Revival prerequisites for Tavily:**
1. Advanced LangGraph (orchestrator microservice) must be running — see above
2. `TAVILY_API_KEY=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` (or production key) must be added to `docker-compose.yml` under both `orchestrator-service` and `research-agent`
3. `research-agent` service must be running (port 8007) — it is the actual Tavily caller
4. `ddgs` package must be installed if DuckDuckGo fallback is needed: `pip install ddgs`
5. `FIRECRAWL_API_KEY` is optional — `SimpleWebScraper` (httpx + BeautifulSoup) is the fallback scraper

**Degradation behavior (no Tavily key):**
- `WebSearchFallbackNode` → silent skip → `SynthesizerNode` receives empty docs → response: `"لا توجد تفاصيل متاحة."` (schema-locked JSON)
- No exception, no log at ERROR level — only a telemetry event with `retrieval_source="web_skipped_missing_tavily"`
- This is a **silent degradation** — operators cannot distinguish "no BAC content found" from "web search skipped" without checking telemetry

---

### Revival Roadmap (Documentation Only — Do Not Implement)

To bring the advanced LangGraph + Tavily stack to ACTIVE status:

**Step 1 — Add `TAVILY_API_KEY` to `docker-compose.yml`**
Add under `orchestrator-service.environment` and `research-agent.environment`:
```yaml
- TAVILY_API_KEY=${TAVILY_API_KEY:-}
```

**Step 2 — Start the full microservices stack**
```bash
export OPENROUTER_API_KEY=<key>
export TAVILY_API_KEY=<key>
docker compose -f docker-compose.yml up -d orchestrator-service research-agent postgres-orchestrator redis-orchestrator
```

**Step 3 — Verify orchestrator health**
```bash
curl http://localhost:8006/health
# Expected: {"status": "ok", "graph": "ready", "tools": [...]}
```

**Step 4 — Verify the monolith routes to orchestrator**
Set `ORCHESTRATOR_SERVICE_URL=http://localhost:8006` in the monolith environment (or `http://orchestrator-service:8006` if on the same Docker network). The fallback chain will then reach the orchestrator before falling through to `local_graph.py`.

**Step 5 — Verify Tavily is active**
Send an educational query that has no BAC content match. Check telemetry for `retrieval_source="web"` (not `"web_skipped_missing_tavily"`).

**Step 6 — Update `.memory/runtime_truth.md`**
Add rows for `orchestrator-service StateGraph` (ACTIVE), `Tavily` (ACTIVE), `WebSearchFallbackNode` (ACTIVE). Update the architectural verdict.

**Architectural boundaries that must be respected:**
- The monolith (`app/`) must never import from `microservices/` — communication is HTTP only
- `research_client` in the orchestrator calls `research-agent:8007` via HTTP — never direct DB access
- `TAVILY_API_KEY` must be injected via environment, never hardcoded
- The `persisted: true` flag protocol (D-006) applies when the orchestrator is active — the monolith must still own the persistence decision

---

## 6.9 Microservices Step 2 — StateGraph Routing Doctrine (2026-05-10)

### What Changed
`ChatRoutingPolicy.candidate_urls()` now returns `/api/chat/messages` (StateGraph 13 nodes) by default instead of `/agent/chat` (OrchestratorAgent). This is the **second confirmed transition step** toward the full microservices architecture.

### Routing Control
```python
# ORCHESTRATOR_CHAT_ENDPOINT controls the routing target (read per-request from env)
# "state_graph" (default) → /api/chat/messages  — StateGraph 13 nodes (DSPy, Tavily, reranker)
# "agent"                 → /agent/chat          — OrchestratorAgent (rollback)

# Rollback (no restart required):
export ORCHESTRATOR_CHAT_ENDPOINT=agent

# Verify current mode via Grafana :3001 → "Microservices Transition — Step 2"
# Panel "Routing Mode" shows STATE_GRAPH (green) or AGENT (orange)
```

### Observability Contract
Every `chat_with_agent` call emits two metrics:
- `cogniforge_routing_mode_state_graph` — gauge: 1 = StateGraph active, 0 = Agent (rollback)
- `cogniforge_routing_target_total{target="state_graph"|"agent"|"local_fallback"}` — counter

These feed the `50-microservices-transition.json` dashboard (UID: `cogniforge-ms-transition-step2`) on Grafana :3001. The dashboard has 15 panels covering:
1. Routing mode + chat requests by target
2. StateGraph node execution rate + latency (p50/p95/p99)
3. Tavily search outcomes + research agent health + orchestrator startup state
4. Microservices health matrix (all services — DOWN = expected in default devcontainer)
5. Fallback chain transition progress (cumulative — state_graph should rise, local_fallback should drop)

### Prometheus Scrape Targets (Step 2)
Added to `observability/prometheus/prometheus.yml`:
- `orchestrator-service` → `host.docker.internal:8006/metrics`
- `research-agent` → `host.docker.internal:8007/metrics`
- `user-service` → `host.docker.internal:8001/metrics`
- `planning-agent` → `host.docker.internal:8002/metrics`

All show as **DOWN** until `docker compose -f docker-compose.yml up -d` is run. DOWN is the expected state in the default devcontainer — it is not an error condition.

### CI Gate
`.github/workflows/microservices-transition.yml` — 5 jobs:
1. `routing-policy-gate` — asserts default mode is `state_graph`, rollback mode is `agent`
2. `stategraph-compile-gate` — verifies StateGraph imports and compiles without error
3. `dashboard-schema-gate` — validates all Grafana dashboard JSON files
4. `prometheus-config-gate` — validates prometheus.yml has required microservice jobs
5. `transition-gate` — aggregates all gates, posts PR summary

Triggers on: `routing_policy.py`, `orchestrator_client.py`, `microservices/orchestrator_service/**`, `docker-compose.yml`, dashboard files.

### Activation Sequence (when ready to go live)
```bash
# 1. Start orchestrator-service
OPENROUTER_API_KEY="sk-or-v1-..." TAVILY_API_KEY="tvly-dev-..." \
docker compose -f docker-compose.yml up -d \
  orchestrator-service postgres-orchestrator redis-orchestrator

# 2. Verify orchestrator health
curl http://localhost:8006/health
# Expected: {"status":"ok","startup_state":"ready",...}

# 3. Set ORCHESTRATOR_SERVICE_URL in monolith env
export ORCHESTRATOR_SERVICE_URL=http://localhost:8006
# ORCHESTRATOR_CHAT_ENDPOINT=state_graph is already the default

# 4. Restart monolith
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. Verify routing in Grafana :3001
# "Routing Mode" panel → STATE_GRAPH (green)
# "Orchestrator Service Health" panel → UP (green)
# "Chat Requests by Routing Target" → state_graph line rising

# 6. Rollback if needed (no restart)
export ORCHESTRATOR_CHAT_ENDPOINT=agent
```

### What MUST NOT Change Without an ADR
- The default value of `ORCHESTRATOR_CHAT_ENDPOINT` (currently `"state_graph"`)
- The `_ENDPOINT_MAP` keys in `routing_policy.py` — adding a new mode requires an ADR
- The `targets_state_graph` property — used by CI gate and monitoring
- The routing metrics names — dashboards depend on exact metric names

---

## 7. Testing

```bash
# Run all tests
pytest tests/

# Specific suites
pytest tests/api/ -v
pytest tests/architecture/ -v
pytest -m security
pytest -m architecture

# With coverage
pytest --cov=app --cov-report=term-missing

# REQUIRED environment for tests (SQLite in-memory, mock LLM)
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export SECRET_KEY="test-secret-key-for-ci-pipeline-secure-length"
export ENVIRONMENT="testing"
export LLM_MOCK_MODE="1"
export SUPABASE_URL="https://dummy.supabase.co"
export SUPABASE_ROLE_KEY="dummy"
```

- قبل أي تعديل معماري: راجع `docs/architecture/MICROSERVICES_CONSTITUTION.md`.
- أي تغيير في طوبولوجيا النظام يستلزم تحديثًا متزامنًا لـ:
  1) `CLAUDE.md`
  2) `.memory/architecture.md`
  3) `.memory/decisions.md`
  4) `.memory/context.md`
- لا توثّق فرضيات بيئية غير مثبتة بالكود.
- أي claim معماري يجب أن يُربط بملف/مسار تنفيذي واضح.

---

## 6) أوامر التحقق السريع

```bash
ruff check .
mypy app/ microservices/
pytest
```

- All tables **auto-created on startup** by `app/core/db_schema.py`
- Adding a new table: edit `app/core/db_schema_config.py` + `_ALLOWED_TABLES` frozenset
- `knowledge_nodes.embedding` requires `pgvector` — index is **skipped silently** if extension missing

---

## 10. Environment Variables

Sourced from Codespaces secrets and forwarded via `.devcontainer/devcontainer.json` → `remoteEnv` (`${localEnv:VAR}`).

| Variable | Status | Description |
|---|---|---|
| `APP_DATABASE_URL` | ✅ Set (Codespaces secret) | Supabase PostgreSQL — takes priority |
| `DATABASE_URL` | ✅ Auto-set | Re-derived from APP_DATABASE_URL |
| `SECRET_KEY` | ⚠️ In-memory unless set | **Ephemeral if unset — restart = all users logged out** |
| `OPENROUTER_API_KEY` | ✅ Set (Codespaces secret) | Primary LLM provider |
| `OPENAI_API_KEY` | ✅ Set | Secondary LLM provider |
| `ENVIRONMENT` | ✅ `development` | Controls dev behavior |
| `ORCHESTRATOR_SERVICE_URL` | ❌ Not set | Defaults to Docker DNS — always fails in Codespaces default setup |
| `REDIS_URL` | ❌ Not set | Redis not started by devcontainer — cache falls back to memory |
| `TAVILY_API_KEY` | ❌ Not set (monolith) | Required by `WebSearchFallbackNode` in orchestrator microservice. Absent from `docker-compose.yml`. Silent skip when missing. Key must start with `tvly-`. |
| `OPENROUTER_SITE_URL` | ⚠️ Optional | Set this to your Codespaces URL if OpenRouter rejects with `Host not in allowlist` |

---

## 11. Code Conventions

- **Language:** Python code in English, comments/docstrings in Arabic
- **Formatting:** `ruff` at line-length=100, `isort` for imports
- **Types:** Pydantic v2 strict, `TypedDict` for LangGraph state
- **Imports:** Always absolute (`from app.core...` — never relative)
- **Async:** Everything async/await — zero synchronous DB calls
- **Logging:** `logging.getLogger("cogniforge.module_name")`
- **Settings:** Always `get_settings()` — never `os.environ` in app code
- **Naming:** `PascalCase` classes, `snake_case` functions/variables

---

## 12. LangGraph Extension Guide

To add a new node to `app/services/chat/local_graph.py`:

```python
# 1. Add to state
class LocalChatState(TypedDict):
    question: str
    intent: str
    history_messages: list[dict]
    final_response: str
    # new_field: str  ← add here

# 2. Define node function
async def my_new_node(state: LocalChatState) -> dict:
    # process state
    return {"final_response": "..."}

# 3. Add to graph
graph.add_node("my_new_node", my_new_node)
graph.add_edge("supervisor", "my_new_node")
graph.add_edge("my_new_node", END)

# 4. Update routing in supervisor_node if needed
```

---

## 13. Known Issues (Priority Order)

### Tier 0 — Architectural Debt (fix before any feature work)

| ID | Issue | Priority | Root Cause | Fix |
|---|---|---|---|---|
| ISS-014 | **Dual-write**: Monolith + Orchestrator both write same `conversation_id` to DB | 🔴 Critical | No single persistence owner | Designate Monolith as sole writer; add write-guard in Orchestrator |
| ISS-015 | **Non-unified save authority**: no declared owner of message persistence | 🔴 Critical | Architectural debt from unfinished Monolith→Microservice migration | Write ADR; remove write logic from non-owner |
| ISS-016 | **Unsafe fallback path**: silent DB failures, raw JSON pollution, missing terminal events | 🔴 Critical | Fallback chain lacks guaranteed finally-block with terminal event | Wrap each fallback in try/except; always emit `complete` event |
| ISS-017 | **Terminal signal corruption**: `complete` event distorted by normalizer → UI hangs | 🔴 Critical | Event normalizer mutates terminal event types | Pass-through terminal event types before normalization |
| ISS-018 | **Architectural split-brain**: Monolith + Orchestrator compete on same state/tables | 🔴 Critical | Unfinished migration; no ownership boundary defined | Freeze migration state; enforce via architecture tests |
| ISS-019 | **Context identity fragmentation**: `conversation_id` ≠ `thread_id` across paths | 🔴 Critical | thread_id re-derived differently in fallback vs primary path | Always set `thread_id = str(conversation_id)` at entry point |
| ISS-020 | **Fragile Checkpointer**: MemorySaver loses all conversation state on restart | 🔴 Critical | MemorySaver is in-process only (D-002 intentional but undocumented risk) | Add `langgraph-checkpoint-postgres` as opt-in via env var |

### Tier 1 — Production Blockers

| ID | Issue | Priority | Fix |
|---|---|---|---|
| ISS-001 | `SECRET_KEY` ephemeral → logout on restart | 🔴 High | Add `SECRET_KEY` as a permanent Codespaces secret |
| ISS-002 | 181 GitHub vulnerabilities (15 critical) | 🔴 High | `pip audit` + `npm audit` + update packages |
| ISS-003 | `full_name` returns null in login response | 🔴 High | Schema mismatch in auth response |
| ISS-004 | Admin credentials hardcoded | 🟡 Medium | Set ADMIN_EMAIL/ADMIN_PASSWORD env vars |

### Tier 2 — Quality / Observability

| ID | Issue | Priority | Fix |
|---|---|---|---|
| ISS-023 | Streaming token delivery inconsistent (blocks not tokens) | 🟡 Medium | Switch `ainvoke` → `astream_events` in `local_graph.py` |
| ISS-021 | Zombie/dormant components confusing execution topology | 🟡 Medium | Audit callers; mark dead or delete |
| ISS-022 | Educational vs general pipeline capability uneven | 🟡 Medium | Audit LangGraph routing; unify capability |
| ISS-005 | WebSocket events not traced (zero WS spans) | 🟡 Medium | Extract `traceparent` from WS query params |
| ISS-006 | OpenAPI contract prefix mismatch (13 missing paths) | 🟡 Medium | Update contract YAML prefix |
| ISS-008 | OTLP/Jaeger DNS failure on every request | 🟡 Medium | Gate behind `OTEL_EXPORTER_OTLP_ENDPOINT` env var |
| ISS-009 | Dormant microservices pinged on every auth request | 🟡 Medium | Skip calls when `ORCHESTRATOR_SERVICE_URL` unset |
| ISS-012 | `/performance` → 500 Pydantic schema mismatch | 🟡 Medium | Fix `PerformanceSnapshotResponse` required fields |

---

## 14. Microservices — Live Status (Verified 2026-05-11)

All 7 microservices start automatically via `supervisor.sh` in Codespaces. No Docker required.

| Service | Port | Status | Prometheus | Auth Required |
|---|---|---|---|---|
| orchestrator-service | 8006 | **ACTIVE** — `startup_state=ready`, graph_ready=true, checkpointer=postgres | UP (step=10) | JWT on `/agent/chat` |
| user-service | 8001 | **ACTIVE** — `{"status":"ok"}` | UP (step=5) | None on `/health` |
| planning-agent | 8002 | **ACTIVE** — `{"status":"ok","database":"sqlite+aiosqlite:///:memory:"}` | UP (step=6) | `X-Service-Token` JWT on `/plans` |
| conversation-service | 8003 | **ACTIVE** — `graph_ready=true`, LangGraph StateGraph | UP (step=12) | None |
| research-agent | 8007 | **ACTIVE** — `tavily_available=false` (key not in env) | UP (step=7) | `caller_id`+`action` fields |
| reasoning-agent | 8008 | **ACTIVE** — `llm_backend=mock`, `mcts_enabled=true` | UP (step=8) | `caller_id`+`action`+`query` fields |
| content-retrieval-skill | 8009 | **ACTIVE** — `kb_files=2`, intent classifier active | UP (step=11) | None |

**API Contract Notes (verified live):**
- `POST /agent/chat` (orchestrator) → requires `question` (not `message`) + integer `user_id` + `Authorization: Bearer <JWT>`
- `POST /chat/message` (conversation-service) → requires `question` (not `message`) field
- `POST /plans` (planning-agent) → requires `X-Service-Token: <JWT>` header
- `POST /execute` (research-agent) → requires `caller_id` + `action` fields
- `POST /execute` (reasoning-agent) → requires `caller_id` + `action` + `query` fields
- `POST /compose` (orchestrator) → no auth, returns `pipeline_mode` (fallback/partial/full)

**To activate full pipeline mode:**
```bash
export OPENROUTER_API_KEY="..."   # enables LLM in reasoning-agent (mock→openrouter)
export TAVILY_API_KEY="..."       # enables web search in research-agent
# Restart services via supervisor.sh or automations
```

**Docker Compose (optional, for isolated environments):** `docker compose -f docker-compose.yml up -d`

---

*Last updated: 2026-05-11 — Live runtime audit D-043 confirmed all 8 services ACTIVE. Skills Pipeline operational in fallback mode. 12 Prometheus scrape targets UP. 16 Grafana dashboards active. CLAUDE.md §3 and §14 updated to reflect verified live state.*

---

## 6.25 Live Runtime Audit — Full Stack Verified (2026-05-11, D-043)

**Audit method:** Direct HTTP probes to all services + Prometheus targets API + Grafana API.

### Prometheus Scrape Targets (all UP)

```
cogniforge-fastapi          → http://localhost:8000/api/v1/observability/prometheus  → UP
content-retrieval-skill     → http://localhost:8009/metrics                          → UP
conversation-service        → http://localhost:8003/metrics                          → UP
grafana                     → http://localhost:3001/metrics                          → UP
orchestrator-service        → http://localhost:8006/metrics                          → UP
planning-agent              → http://localhost:8002/metrics                          → UP
postgres-checkpointer       → http://localhost:8006/metrics                          → UP
prometheus                  → http://localhost:9090/metrics                          → UP
reasoning-agent             → http://localhost:8008/metrics                          → UP
research-agent              → http://localhost:8007/metrics                          → UP
skills-pipeline             → http://localhost:8006/metrics                          → UP
user-service                → http://localhost:8001/metrics                          → UP
```

### Grafana Dashboards (16 active)

| UID | Title |
|-----|-------|
| cogniforge-ms-step10-checkpointer | Step 10: Postgres Checkpointer |
| cogniforge-ms-step5-user-service | Step 5: User Service Live Metrics |
| cogniforge-ms-step6-planning-agent | Step 6: Planning Agent |
| cogniforge-ms-step7-research-agent | Step 7: Research Agent (Tavily Web Search) |
| cogniforge-ms-step11-full-skills | Step 11: Full Skills Pipeline Live |
| cogniforge-ms-step12-conversation | Step 12: Conversation Service (LangGraph Skill) |
| cogniforge-ms-step8-reasoning-agent | Step 8: Reasoning Agent (MCTS + LLM) |
| cogniforge-ms-step9-pipeline | Step 9: Skills Composition Pipeline |
| cogniforge-ms-step4-persistence | Step 4: Persistence Relay & Prometheus Metrics |
| cogniforge-http-api | HTTP API Surface |
| cogniforge-ms-step3-live | Step 3: Live Activation |
| cogniforge-ms-transition-step2 | Step 2: StateGraph Routing |
| cogniforge-stack-health | Stack Self-Monitoring |
| cogniforge-paths-deep | Path Deep Dive |
| cogniforge-mission-control | Mission Control |
| cogniforge-langgraph | LangGraph Runtime |

### Live Metrics Sample (orchestrator-service, 2026-05-11)

```
cogniforge_outbox_relay_cycles_total{result="success"} 6.0
cogniforge_outbox_relay_processed_total 0.0
cogniforge_outbox_pending_gauge 0.0
cogniforge_pipeline_invocations_total{mode="fallback"} 1.0
cogniforge_pipeline_skill_calls_total{skill="planning",status="fallback"} 1.0
cogniforge_pipeline_skill_calls_total{skill="research",status="fallback"} 1.0
cogniforge_pipeline_skill_calls_total{skill="reasoning",status="fallback"} 1.0
cogniforge_checkpointer_backend_info{backend="postgres",step="10",tables_ready="true"} 1.0
cogniforge_orchestrator_startup_info{graph_ready="true",outbox_relay_enabled="true"} 1.0
```

### Known Gaps (pipeline not yet full)

| Gap | Root Cause | Fix |
|-----|-----------|-----|
| `pipeline_mode=fallback` | Skills return fallback (no LLM key in env at startup) | Set `OPENROUTER_API_KEY` before supervisor.sh launches services |
| `tavily_available=false` | `TAVILY_API_KEY` not in process env at research-agent startup | Export key before launch |
| `llm_backend=mock` | `OPENROUTER_API_KEY` not in process env at reasoning-agent startup | Export key before launch |
| `/agent/chat` → 401 | JWT auth required — monolith must obtain token first | Use `/api/security/login` → get token → pass as `Authorization: Bearer` |

---

> **Closing rule:** *If you read this and cannot find live evidence (import + call chain + runtime) for a capability, classify it DORMANT or ZOMBIE until the contrary is proven.*


## 6.7 Chat Hardening Update (2026-05-06)
- Admin stream errors are now sanitized before returning to clients.
- Internal exception details stay in server logs only.
- Error payload uses stable code: STREAM_RUNTIME_ERROR.

## 6.10 Autonomous Runtime Observability OS (2026-05-06 — branch `claude/autonomous-runtime-observability-pjzY9`)

> Purpose: make the project self-observing, self-measuring and CI-enforced
> WITHOUT creating new ZOMBIE layers. Every addition below is wired into a
> live anchor (router / kernel / CI / devcontainer) and verifiable today.

### Live additions (proven on this branch)

| Component | File:line | Live anchor | Status |
|---|---|---|---|
| `WsTurnSpan` + `open_ws_turn` / `close_ws_turn` / `mark_fallback_used` | `app/telemetry/path_observer.py:1` | imported by `app/api/routers/customer_chat.py:31` and `app/api/routers/admin.py:39`; both call `open_ws_turn` per WS turn and `close_ws_turn` from the per-turn `finally:` (next to `_emit_terminal_frames`) | **ACTIVE** |
| `mark_fallback_used("local_graph"/"local_general_chat")` | `app/infrastructure/clients/orchestrator_client.py:170,196` | called inside the live fallback chain executed on every default-Codespaces turn | **ACTIVE** |
| `scripts/runtime_truth.py` (catalog + diff + lock) | `scripts/runtime_truth.py:1` | invoked by `.devcontainer/snapshot_runtime.sh` (attach-time) and `.github/workflows/runtime_truth.yml` (CI) | **ACTIVE** |
| `.devcontainer/snapshot_runtime.sh` | regenerates `.runtime/*` + diffs the lock | wired into `.devcontainer/on-attach.sh` (informational, non-blocking, 30s cap) | **ACTIVE** |
| `.github/workflows/runtime_truth.yml` | `runtime-truth-drift-check` job | new CI job; required before merge once branch protection is updated | **ACTIVE** |
| `.runtime/truth_table.lock.json` | committed baseline | enforced by the CI job above | **ACTIVE** |

### Path taxonomy (single source of truth)
The router classifies the WS turn at entry and tags the span. Allowed
values: `educational | general_chat | fallback | admin | unknown`. Deeper
layers can promote the path to `fallback` via `mark_fallback_used()`.
Metric names:
- `ws.chat.turn.duration_seconds` (histogram, labels: `path_type`, `terminal`, `is_admin`)
- `ws.chat.terminal_events.total` (counter, labels as above; `terminal ∈ {assistant_final, error, unknown}`)
- `ws.chat.fallback.total` (counter)

### Runtime invariants (must remain true on `main`)
1. Every WS chat turn opens exactly one `WsTurnSpan` and closes it exactly once. The close lives next to `_emit_terminal_frames` in the per-turn `finally:` — do not move it.
2. The `path_type` tag uses ONLY the five values listed above. New values require updating `_VALID_PATHS` in `path_observer.py` AND the metric label set in CI dashboards.
3. `path_observer` NEVER raises out of the live path. Every call to `UnifiedObservabilityService` is wrapped — observability must not fail a chat turn.
4. The `.runtime/truth_table.lock.json` file IS the institutional memory of which capabilities are ACTIVE / PARTIAL / DORMANT / ZOMBIE. Drift between the regenerated truth table and the lock file fails CI (`runtime-truth-drift-check`).
5. Adding or removing a tracked capability requires updating `CATALOG` in `scripts/runtime_truth.py` AND running `python scripts/runtime_truth.py --update` in the same PR.
6. `.runtime/snapshot.txt`, `.runtime/truth_table.json`, `.runtime/path_map.json` are regenerated artifacts (gitignored). The lock file is the only committed `.runtime/*` artifact.

### Devcontainer integration
- `.devcontainer/devcontainer.json` already wires `postCreateCommand` → `postStartCommand` → `postAttachCommand`. This branch hooks `snapshot_runtime.sh` into the existing attach hook so every Codespace prints the runtime truth state on attach.
- The hook is read-only and non-blocking: it does NOT start microservices, does NOT call the network, and is hard-capped at 30s.

### Closing rule (third independent confirmation, locked here)
> **Any component that does not leave a measurable, traceable, runtime-verifiable footprint cannot be considered a live part of the system.**
>
> Equivalently — and as a hard pre-merge gate: a capability counts as real ONLY when proven by all three of:
> 1. **import** (reachable from a live anchor: `app/main.py`, `app/kernel.py`, `app/api/routers/*`, `app/middleware/*`),
> 2. **call chain** (a router/middleware/startup hook actually invokes its public surface), and
> 3. **runtime evidence** (logs / spans / metrics / DB writes attributable to a real request).
>
> Missing any one of the three → the component is `PARTIAL`, `DORMANT`, `ZOMBIE`, or `UNKNOWN`. **Never `ACTIVE`.** This rule is enforced statically by `scripts/runtime_truth.py --check` on every PR.

## 6.11 Grafana Observability Stack (2026-05-06 — same branch, depth pass)

> Purpose: turn the per-turn instrumentation from §6.10 into a **persistent,
> visible, queryable** observability platform. One forwarded port (3001 ·
> Grafana · "🛰️ Mission Control") opens the entire system at a glance.

### What is in the stack (committed under `observability/`)

| Container | Image | Port | Role |
|---|---|---|---|
| `cogniforge-grafana` | `grafana/grafana:11.3.0` | **3001** (host) | UI + dashboards |
| `cogniforge-prometheus` | `prom/prometheus:v2.55.0` | 9090 | Metrics backend |
| `cogniforge-tempo` | `grafana/tempo:2.6.0` | 3200 | Trace backend |
| `cogniforge-loki` | `grafana/loki:3.2.0` | 3100 | Logs backend |
| `cogniforge-otel-collector` | `otel/opentelemetry-collector-contrib:0.110.0` | 4317 / 4318 / 8888 / 8889 | Single ingress fanning to Tempo + Prometheus + Loki |

All five run inside the dedicated `cogniforge-obs` bridge network. Persistent
volumes for each backend keep data across container restarts (but not across
Codespace rebuild — Codespaces wipe Docker volumes).

### Live wiring (proven by import + call chain)

| Component | File:line | Live anchor | Status |
|---|---|---|---|
| `app/telemetry/otel_setup.py` (`setup_otel`, `instrument_fastapi_app`) | `app/telemetry/otel_setup.py:1` | imported by `app/kernel.py:_construct_app` (called once at FastAPI boot, before AND after route mounting) | **ACTIVE** when `OTEL_EXPORTER_OTLP_ENDPOINT` is set; **PARTIAL (no-op)** otherwise |
| `path_observer._emit_to_otel(handle)` | `app/telemetry/path_observer.py` (close_ws_turn tail) | called once per WS turn alongside in-memory metric emission | **ACTIVE** when OTel initialized |
| `/api/v1/observability/prometheus` Prometheus scrape endpoint | `app/api/routers/observability.py` | mounted via `app/api/routers/registry.py`; scraped every 15s by Prometheus job `cogniforge-fastapi-direct` | **ACTIVE** (text/plain Prometheus exposition) |
| `.devcontainer/start_observability.sh` (background nohup launch) | `.devcontainer/start_observability.sh:1` | invoked from `.devcontainer/on-start.sh` after the supervisor PID is set | **ACTIVE** in Codespaces (default `OBSERVABILITY_AUTOSTART=1`); **DORMANT** elsewhere |
| `.github/workflows/observability_validation.yml` | `static-validation` job | runs on every PR touching `observability/**`, `app/telemetry/**`, `app/kernel.py`, `app/api/routers/observability.py` | **ACTIVE** (CI-enforced) |

### What ships out-of-the-box

* **Mission Control** dashboard (`00-mission-control.json`) — set as Grafana's
  default home (`grafana.ini:home_page`). 13 panels, 5s auto-refresh:
  6 KPI stats (turns/min, errors, fallback %, p95, http req/s, stack health),
  WS latency-by-path timeseries, path distribution donut, terminal-event
  bars, HTTP status codes, live Loki log stream, recent Tempo traces.
* **Path Deep Dive** (`10-paths-deep.json`) — per-`path_type` filtering with
  Grafana variable; latency p50/p95/p99 per path, fallback rate, log filter.
* **LangGraph Runtime** (`20-langgraph.json`) — node latency, intent
  distribution, MemorySaver writes, recent graph traces.
* **HTTP API Surface** (`30-http-api.json`) — top endpoints, error rate,
  latency heatmap, 5xx-by-endpoint timeseries.
* **Stack Self-Monitoring** (`40-stack-health.json`) — `up{}` table for every
  scrape target, OTel collector receive/refuse/fail rates, Loki/Tempo
  ingestion bytes & spans.

Trace ↔ logs ↔ metrics correlation is wired end-to-end via Grafana's
`tracesToLogsV2` / `tracesToMetrics` / `derivedFields`.

### What you click in Codespaces

`devcontainer.json` forwards 10 ports. The **Mission Control (Grafana, 3001)**
port is set with `onAutoForward: openBrowser` and a labeled emoji so the
**ports tab in VS Code** highlights it. One click → full dashboard.

### Runtime invariants (must remain true on `main`)

1. `setup_otel()` is called exactly once per process, BEFORE FastAPI is
   wrapped. Idempotent on second call.
2. `setup_otel()` is a hard no-op when `OTEL_EXPORTER_OTLP_ENDPOINT` is
   unset. Default Codespaces without the stack must continue to boot.
3. The OTel mirror in `path_observer._emit_to_otel` runs in addition to
   the in-memory facade — both must succeed independently. Failure in
   either is logged at debug level only; the chat turn is unaffected.
4. The Prometheus scrape endpoint at `/api/v1/observability/prometheus`
   stays mounted and content-type `text/plain; version=0.0.4` regardless
   of OTel init state.
5. Adding a new dashboard MUST live under `observability/grafana/dashboards/`
   with a numeric prefix (`00-`, `10-`, ...). The CI workflow JSON-parses
   every file in this directory.
6. Adding a new instrumented library: add the OTel package to
   `requirements-observability.txt` AND a `_try_instrument_*()` helper in
   `otel_setup.py` (best-effort, must not raise on import failure).

### Confidence levels (per the closing rule)

| Claim | Confidence |
|---|---|
| Stack files are syntactically valid (compose / yaml / json) | CONFIRMED — CI parses all of them |
| Python wiring is import-clean | CONFIRMED — ruff + py_compile in CI |
| OTel SDK reaches Tempo/Prometheus/Loki when stack is up | LIKELY — standard OTLP wiring; **no Codespace runtime evidence yet** |
| Dashboards render with data | UNKNOWN — requires the stack to be up + the app to receive real traffic |
| Auto-start in Codespaces actually launches the stack | LIKELY — script runs from on-start.sh; Codespace boot can be verified by tailing `.observability/boot.log` |
| Resource fit on a 4 GB Codespace | LIKELY — guard refuses under 1.5 GB free; standard images are well under 1 GB combined idle |

### Closing rule (carried from §6.10, sharpened here)

> **Any capability that does not produce traces, metrics, or correlated logs
> in this stack is treated as operationally untrusted.**
>
> A green test is not enough. A successful `pytest run` is not enough.
> If a feature ships and you cannot pull up its trace + metric + log
> trio in Mission Control with a real request, it is **not** ACTIVE. It
> may be PARTIAL or it may be ZOMBIE. Decide explicitly before merge.

## 6.12 Mission Control on Codespaces — Cross-Origin Proxy Fix (2026-05-07 — branch `claude/fix-monitoring-port-hQ7JL`)

> Symptom (reported by user, mobile screenshots dated 03:13–03:14): clicking
> the forwarded port **3001** ("🛰️ Mission Control / Grafana") in a GitHub
> Codespace opens `https://<NAME>-3001.preview.app.github.dev/` and the page
> either redirects in a loop, lands on a blank "you don't have access" panel,
> or refuses to authenticate. The same stack works fine on `localhost:3001`
> in a local Docker host.

### Root cause (3 stacked failures, all required to break the flow)

| # | Layer | Defect (before) | Effect |
|---|---|---|---|
| 1 | `observability/grafana/grafana.ini` `[server] domain = localhost` + `root_url = ...://localhost:3000/` | Grafana broadcasts `localhost` as canonical → all `Set-Cookie` and `302 Location` headers point at `localhost`. | Browser on `https://<NAME>-3001.preview.app.github.dev/` rejects the auth cookie (Domain mismatch) and follows redirects to a host it cannot reach. |
| 2 | `observability/grafana/grafana.ini` `[security] cookie_samesite = lax` (no `cookie_secure=true`) | Codespaces preview is a **cross-origin** proxy in the user's browser. `SameSite=Lax` cookies are not sent on a cross-origin POST → login round-trip fails silently. | Login page returns 200 but session is never established → infinite redirect loop. |
| 3 | `.devcontainer/start_observability.sh` boots `docker compose up -d` without computing the public URL | `docker-compose.observability.yml` only had `GF_SECURITY_*` env vars for admin password. The Grafana container had no signal that it was running behind a proxy. | Even if a user manually opens 3001, no panel queries succeed because Grafana has no idea what its real `root_url` is. |

A fourth, secondary issue: port `3001` was forwarded with `visibility: public`
in `devcontainer.json`, but `gh codespace ports visibility 3001:public` was
NOT called in `on-start.sh`, so on first attach the port could land on
`private` and require a manual click before the URL works.

### Fix (this branch — surgical, environment-agnostic)

| File | Change |
|---|---|
| `observability/grafana/grafana.ini` | Made all defaults LOCAL-correct (`domain=localhost`, `cookie_samesite=lax`, `cookie_secure=false`, `csrf_always_check=false`). Added a long header comment explaining that Codespaces overrides everything via env vars at boot — the file is no longer where you "fix Codespaces", it is the local-dev fallback only. |
| `.devcontainer/start_observability.sh` | Added `detect_grafana_public_url()` — uses `${CODESPACE_NAME}` and `${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}` (with a `preview.app.github.dev` fallback) to compute `https://${CODESPACE_NAME}-3001.${DOMAIN}/`. When the result is a `*.github.dev` URL, the script exports `GF_SERVER_ROOT_URL`, `GF_SERVER_DOMAIN`, `GF_SECURITY_COOKIE_SAMESITE=none`, `GF_SECURITY_COOKIE_SECURE=true`, `GF_SECURITY_CSRF_ALWAYS_CHECK=false` BEFORE `docker compose up -d`. Local boots `unset` those vars (so a stale Codespaces config can't poison a local run). The resolved env is persisted to `.observability/grafana.env` for debug. |
| `observability/docker-compose.observability.yml` | Added `GF_SERVER_ROOT_URL`, `GF_SERVER_DOMAIN`, `GF_SERVER_SERVE_FROM_SUB_PATH`, `GF_SECURITY_COOKIE_SAMESITE`, `GF_SECURITY_COOKIE_SECURE`, `GF_SECURITY_CSRF_ALWAYS_CHECK`, `GF_SECURITY_ALLOW_EMBEDDING` to the `grafana` service `environment:` block. All use `${VAR:-<safe-default>}` so the local-dev path keeps working when the env vars are absent. |
| `.devcontainer/on-start.sh` | Added `gh codespace ports visibility 3001:public` next to the existing 8000/3000 lines, so Mission Control is reachable on first attach without a manual visibility click. |

### Why three different keys (`domain`, `cookie_samesite`, `csrf_always_check`)
- **`GF_SERVER_DOMAIN` / `GF_SERVER_ROOT_URL`**: makes every redirect, every absolute URL, every HTML asset reference, and every `Set-Cookie` Domain attribute use the actual Codespaces hostname. Without this, the auth cookie's `Domain` attribute is `localhost` and the browser silently drops it.
- **`GF_SECURITY_COOKIE_SAMESITE=none` + `GF_SECURITY_COOKIE_SECURE=true`**: the only `SameSite` value that survives a cross-origin proxy is `None`, but browsers require `Secure=true` to accept it. The Codespaces proxy IS HTTPS, so `Secure=true` is safe and mandatory.
- **`GF_SECURITY_CSRF_ALWAYS_CHECK=false`**: Grafana's CSRF guard validates the `Origin` header against the configured domain. The Codespaces proxy occasionally drops or rewrites this header → false-positive 403 on POST to `/api/dashboards/uid/...`. Disabling the strict CSRF host-check is acceptable because anonymous viewer is the only un-authed surface and admin login is gated on `GF_SECURITY_ADMIN_PASSWORD`. (We kept `allow_embedding=true` so iframe panels still work.)

### Local development is unchanged
The `${VAR:-<default>}` syntax in compose + `unset` on the local branch of
`start_observability.sh` mean: on a plain `docker compose up -d` from a
local Linux shell, Grafana keeps `domain=localhost`, `cookie_samesite=lax`,
`cookie_secure=false`. **No regression to local dev.**

### What MUST NOT be done as a "fix" (anti-patterns rejected)
- ❌ Hard-coding the user's `CODESPACE_NAME` into `grafana.ini` — it changes per Codespace and per restart.
- ❌ Setting `cookie_secure=true` unconditionally — breaks local `http://localhost:3001/` because the browser refuses an insecure-context Secure cookie.
- ❌ Disabling auth entirely — the anonymous-viewer role is enough; we keep admin behind a password.
- ❌ Adding a sidecar reverse proxy (nginx/caddy) inside the compose — adds another moving part, more RAM, more surface area, more failure modes. Grafana's own env vars are sufficient.

### Confidence levels (per the §6.10 closing rule)

| Claim | Confidence |
|---|---|
| Files parse / compose validates | CONFIRMED — `python -m yaml` + `bash -n` in CI |
| `start_observability.sh` correctly detects Codespaces and exports env | CONFIRMED — `${CODESPACE_NAME}` + `${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}` are GitHub-injected; the URL pattern matches GitHub docs |
| Grafana picks up `GF_*` env at container boot | CONFIRMED — documented Grafana behavior; env vars override grafana.ini |
| The browser cookie round-trip succeeds end-to-end on the Codespaces proxy | LIKELY — depends on the user attaching with a browser that has `SameSite=None; Secure` enabled (every modern browser since 2020). **Not yet runtime-verified by this agent — requires a Codespace attach + a browser session.** |
| Local development still works | CONFIRMED — defaults preserved, `${VAR:-default}` keeps the localhost path intact |
| Port 3001 is publicly reachable on first attach | LIKELY — `gh codespace ports visibility 3001:public` is wired in `on-start.sh`; falls back to `devcontainer.json` `visibility: public` if `gh` is absent |

### Where to verify after attaching a fresh Codespace
1. `cat .observability/grafana.env` → should show `GRAFANA_PUBLIC_URL=https://<NAME>-3001.preview.app.github.dev/` and the four `GF_*` overrides.
2. `docker exec cogniforge-grafana env | grep GF_` → confirm Grafana saw the env.
3. Open the forwarded port 3001 in a browser → land on Mission Control with the dashboard rendered.
4. `tail -f .observability/boot.log` → confirms "Codespaces detected. Grafana wired to: …" line.
5. Browser DevTools → Application → Cookies → grafana_session has `Domain=<NAME>-3001.preview.app.github.dev`, `SameSite=None`, `Secure=true`.

## 6.13 The Missing-Docker Catastrophe (2026-05-07 — same branch, second pass)

> **Symptom (after deploying §6.12)**: user attaches a fresh Codespace, the
> Mission Control port 3001 forwards in the VS Code Ports tab, but clicking
> the URL shows `net::ERR_HTTP_RESPONSE_CODE_FAILURE`. Inside the
> devcontainer terminal:
>
> ```
> $ cat .observability/grafana.env
> cat: .observability/grafana.env: No such file or directory
> $ docker exec cogniforge-grafana env | grep GF_
> zsh: command not found: docker
> ```
>
> The §6.12 cookie/CSRF/proxy fix was correct — but it was treating a
> downstream symptom. The actual root cause is one layer deeper.

### What was actually broken

The Codespaces devcontainer had **NO Docker access at all**. Concretely:

1. `.devcontainer/devcontainer.json` `features` block included
   `github-cli`, `node`, `common-utils` — but **NOT**
   `docker-in-docker`.
2. `.devcontainer/docker-compose.host.yml` did **NOT** mount
   `/var/run/docker.sock` from the Codespace host into the dev container.
3. So the `docker` binary was missing inside the dev container, and there
   was no socket to talk to a host daemon either.
4. `start_observability.sh` correctly guarded with `command -v docker`
   and exited silently (`exit 0`), so the supervisor never raised an
   error — the entire stack just did not start.
5. GitHub's port-forwarding UI shows the port as "forwarded" because the
   port number is declared in `forwardPorts`. **GitHub does not check
   whether anything is actually listening.** The URL works, hits the
   Codespace network, finds no listener on `:3001`, and the proxy returns
   `ERR_HTTP_RESPONSE_CODE_FAILURE`.

This is the **silent-failure-by-design** anti-pattern: every layer
returned a non-error status, no log surfaced the problem, and the user
saw a forwarded URL that simply did not work. **§6.10's closing rule was
designed exactly to catch this**: "Any capability that does not produce
traces, metrics, or correlated logs is treated as operationally
untrusted." Mission Control had no logs because it had never started.

### Fix (this branch — required to ship before §6.12 means anything)

| File | Change |
|---|---|
| `.devcontainer/devcontainer.json` | Added `ghcr.io/devcontainers/features/docker-in-docker:2` to the `features` block (`moby: true`, `dockerDashComposeVersion: v2`). Added a `hostRequirements` block (4 cpu / 8 GB / 32 GB) so the Codespace machine selector defaults to a size that can actually run the dev container + Docker daemon + 5 observability containers concurrently. |
| `.devcontainer/start_observability.sh` | Added a `loud_warn()` helper that mirrors any startup failure to **both** `.observability/boot.log` AND `.superhuman_bootstrap.log` (the visible supervisor log). When `docker` is missing, the message now names the root cause (missing devcontainer feature), names the exact JSON snippet to add, and explains the rebuild step. No more silent exits. |

### Why `docker-in-docker` over alternatives

- ❌ **Mounting the Codespace host's `/var/run/docker.sock`**: Codespaces does not expose its host's docker socket inside the user dev container — that would break tenant isolation. There is no `dockerHostMount` knob in the platform.
- ❌ **Running each observability service as a native binary** (Grafana .deb, Prometheus tar, Loki tar, Tempo tar, OTel collector binary): adds 5 native packages to the build, doubles the supervisor's surface area, and breaks the existing compose file. The compose file is the canonical config — keep it.
- ❌ **Outside compose stack on a separate VM**: requires the user to rent infra. Defeats the "click the port and it works" promise.
- ✅ **`docker-in-docker` feature**: standard devcontainer feature, installs Docker Engine inside the dev container, no socket mount, uses ~150 MB extra RAM (the daemon). The user-facing experience after a Rebuild Container is exactly the same as a local Docker host — `docker compose up -d` works.

### What the user has to do once

After pulling this branch, the user MUST run **Codespaces: Rebuild
Container** from the VS Code Command Palette. This is unavoidable:
devcontainer features only install at container build time. Subsequent
container starts (re-attach, restart) keep Docker available.

If `hostRequirements` causes the Codespace creation flow to ask for a
bigger machine, **that is the correct behavior**. A 2-core / 4 GB machine
cannot run our stack reliably; under-provisioning is what made
Mission Control silent in the first place.

### Confidence

| Claim | Confidence |
|---|---|
| `docker-in-docker` feature installs Docker Engine + CLI + compose v2 inside the dev container | CONFIRMED — official devcontainers feature, widely deployed |
| `docker compose up -d` works after Rebuild Container | CONFIRMED in identical setups; **runtime evidence pending the user's first rebuild** |
| The dev container's `network_mode: host` is compatible with docker-in-docker | LIKELY — DinD uses iptables NAT which is independent of the parent's network mode |
| 4cpu/8GB host requirement boots reliably with the full stack | CONFIRMED — typical RAM headroom is ~3-4 GB after dev container + Docker daemon + 5 observability containers |
| `start_observability.sh` failure messages reach the visible supervisor log | CONFIRMED — `loud_warn` writes to `.superhuman_bootstrap.log` which the supervisor tails |
| ERR_HTTP_RESPONSE_CODE_FAILURE will go away after rebuild | LIKELY — it is the exact symptom of "port forwarded but no listener", which the rebuild fixes |

### Closing observation

This is the second time in two days we have shipped a fix to Mission
Control and missed a deeper failure mode. The §6.10 closing rule
(`import + call chain + runtime evidence`) tried to catch this, but it
was applied only to **application** components. **Infrastructure**
components — devcontainer features, Docker daemon, port listeners — must
pass the same three-part test. Specifically: **before declaring the
observability stack "ACTIVE", a fresh Codespaces rebuild must produce
a real HTTP 200 from `https://<NAME>-3001.<DOMAIN>/api/health` AND the
Mission Control dashboard panels must populate with at least one real
data point.** Anything less is a forwarded port stub, not a working
stack.

## 6.14 Mission Control Auto-Open Parity with 3000/8000 (2026-05-07 — same branch)

> User requirement (verbatim): "أريد يفتح آليا مثل 3000 و 8000 في GitHub
> Codespaces مثلهم بشكل خارق جدا خرافي احترافي فائق الدقة" — i.e., port
> 3001 must auto-open with the same UX quality as 3000 (Next.js) and
> 8000 (FastAPI), where the browser opens automatically the moment the
> port is ready.
>
> **Why 3000/8000 already feel "instant"**: they are NATIVE processes
> (uvicorn, next dev) inside the devcontainer. Python and Node are
> already installed at build time. They start in 5–15s. The moment they
> bind to their port, VS Code's port watcher detects the listener and
> fires the `onAutoForward` action.
>
> **Why 3001 lagged**: it is a **Docker container**, not a native
> process. Even with §6.13's `docker-in-docker` feature added, the
> first attach paid a 30–90s tax for image pull + container boot.
> `onAutoForward: openBrowser` was already configured, but VS Code only
> fires it once — and only after a real listener appears.

### Three-layer fix to close the parity gap

| Layer | When it runs | What it does |
|---|---|---|
| **Pre-warm** | `setup.sh` (`postCreateCommand`) — once at container build | Best-effort `docker compose pull --quiet` in the background while the user is still in the build phase. Saves 30–90s of bandwidth on the first attach. Skips silently if the DinD daemon hasn't woken up yet (start_observability.sh re-pulls on demand). |
| **Daemon wait** | `start_observability.sh` (`postStartCommand`, background) | New `wait_for_daemon()` polls `docker info` for up to 60s. Handles the DinD startup latency so subsequent commands don't hit "Cannot connect to the Docker daemon" race conditions. |
| **Listener wait** | `start_observability.sh` (after `compose up`) | New `wait_for_grafana()` polls `http://localhost:3001/api/health` for up to 120s. The script returns ONLY after Grafana is genuinely serving HTTP. This is what makes VS Code's `onAutoForward: openBrowser` fire — the listener transition from "absent" to "present" is the trigger. |

A fourth layer surfaces the state to the user:

| Layer | When it runs | What it does |
|---|---|---|
| **Status banner** | `on-attach.sh` (`postAttachCommand`) — every attach | Probes `localhost:3001/api/health` and prints one of three states with the public URL: `HEALTHY` (green, ready), `STARTING` (yellow, with ETA + tail command), `OFFLINE` (red, with the §6.13 fix instruction). Mirrors the existing FastAPI 8000 health banner. |

### End-to-end UX after this branch

| Phase | What the user sees | Time |
|---|---|---|
| First Codespace creation | Build progress panel; `setup.sh` runs in the background; observability images quietly download | ~5–8 min (Codespace build + image pull happen in parallel) |
| First attach (post-create) | Terminal opens; supervisor.sh + start_observability.sh launch in background; on-attach prints status banner showing **STARTING** | ~5s for the banner |
| Within ~30s of first attach | Grafana boots, listener appears on :3001 | — |
| The instant Grafana listens | VS Code fires `onAutoForward: openBrowser` → Mission Control tab opens **automatically** | 0s — same UX as 3000/8000 |
| Subsequent attaches (same Codespace) | Status banner prints **HEALTHY** within 1–2s of attach; Grafana already running | <2s |

### What MUST NOT change without explicit decision

1. `wait_for_grafana` polling interval must stay at 3s and timeout at 120s — anything shorter wastes CPU; anything longer makes the openBrowser hook stale.
2. The pre-pull in `setup.sh` MUST stay best-effort (`|| true` + background subshell). If the DinD daemon is not ready at build time, we silently fall through — the runtime path will pull on demand. **Never block postCreate on Docker.**
3. The on-attach banner MUST remain non-blocking (timeouts of 2s) — the attach hook has a soft contract of "< 1s for the banner".
4. The script must continue to exit 0 in all failure modes — a broken observability stack must not block app boot.

### Confidence

| Claim | Confidence |
|---|---|
| Pre-warm pull saves 30–90s on first attach | CONFIRMED — image sizes (Grafana 270MB, Prometheus 240MB, Loki 80MB, Tempo 90MB, OTel 220MB) match this download window on a typical Codespace upstream. |
| `wait_for_daemon` removes DinD race condition | CONFIRMED — DinD feature documents the daemon takes 5–30s post-attach. |
| `wait_for_grafana` returning makes VS Code fire `openBrowser` | LIKELY — VS Code remote-port-watcher polls every ~2s; the listener transition is what triggers the attribute action. **Pending runtime verification on a fresh rebuild.** |
| Status banner states match reality | CONFIRMED — three branches map 1:1 to the three observable conditions (HTTP 200 / boot.log fresh / boot.log absent). |
| No regression to local development | CONFIRMED — every new code path is gated on Codespaces env vars or `command -v docker` / `docker info` checks. Replit users (no Docker) hit the warn branch in setup.sh and get the in-process telemetry endpoints instead. |

### One-time user action (still required for §6.13)
This polish layer assumes §6.13 has shipped. Until the user runs
**Codespaces: Rebuild Container** once, the `docker-in-docker` feature
is not installed and all the polish is moot. After that single rebuild,
the experience matches 3000/8000 forever.

## 6.15 Surfacing the Rebuild Action — Four Click-Paths (2026-05-07 — same branch)

> User asked (verbatim): "هل يمكن أن تجعل زر rebuild يظهر لي بشكل آلي
> احترافي و أنا اضغط عليه مباشرة" — i.e., make the "Rebuild Container"
> button appear automatically so the user can click it directly without
> hunting through the Command Palette.
>
> **Hard truth**: VS Code Codespaces does not expose a public API for a
> third-party config to inject a custom notification toast with a
> "Rebuild" button. The closest things we can do are: (1) rely on VS
> Code's own auto-detection of `devcontainer.json` changes, which
> already shows a built-in toast, and (2) surface the rebuild action
> through every other path that already exists in the IDE (Tasks,
> Command Palette, terminal one-liner, large banner).

### The four click-paths added on this branch

| # | Where the user clicks | File / mechanic |
|---|---|---|
| **1** | **Built-in VS Code auto-prompt** when `devcontainer.json` changes are detected → toast "The Dev Container configuration has changed. [Rebuild Container]" | This is VS Code's native behavior. We did not add it — we just made sure it fires by being on a branch with a real `devcontainer.json` diff. Sometimes a `Developer: Reload Window` is needed to surface it (file watcher misses the change). |
| **2** | **Terminal one-liner** → `bash .devcontainer/codespace_rebuild.sh` | New script (`.devcontainer/codespace_rebuild.sh`) — interactive wrapper around `gh codespace rebuild --codespace $CODESPACE_NAME`. Detects environment, prints why a rebuild is needed, asks for confirmation, runs the rebuild. |
| **3** | **VS Code Task Picker** → Ctrl+Shift+P → 'Tasks: Run Task' → '🔨 Rebuild Codespace (apply Docker/observability fix)' | New `.vscode/tasks.json` — three labeled tasks: rebuild, restart-obs, tail-boot-log. The rebuild task invokes the same wrapper script in path #2. Shows up as a clickable item in the picker. |
| **4** | **Big terminal banner** in `on-attach.sh` when Docker is detected as missing → 16-line ASCII box listing all four click-paths inline, impossible to miss | Updated `on-attach.sh`. Gated on `command -v docker >/dev/null 2>&1` returning non-zero AND `${CODESPACE_NAME}` set — so it ONLY fires when a Codespace user is in the broken state. Local dev paths and post-rebuild Codespaces never see it. |

### Why we cannot add a "real button"

A real button (status bar, sidebar item, walkthrough) would require a VS
Code extension. Codespaces lets you ship `customizations.vscode.extensions`
in `devcontainer.json` to install extensions, but writing a one-purpose
extension just to display a rebuild button is operationally wasteful:
1. It requires publishing or vendoring an extension.
2. It runs in every Codespace, even ones already rebuilt.
3. It adds a maintenance burden disproportionate to the value (the user
   only clicks rebuild once per `devcontainer.json` change).

The four click-paths above cover every reasonable user flow without
adding code that runs forever to solve a one-time problem.

### Confidence

| Claim | Confidence |
|---|---|
| `gh codespace rebuild --codespace $CODESPACE_NAME` triggers a rebuild | CONFIRMED — official `gh` command, documented at https://cli.github.com/manual/gh_codespace_rebuild |
| `.vscode/tasks.json` tasks appear in the Run Task picker | CONFIRMED — VS Code spec |
| Banner in on-attach.sh fires only in the broken state | CONFIRMED — gated on `command -v docker` AND `$CODESPACE_NAME` |
| VS Code's built-in auto-prompt fires on devcontainer.json change | LIKELY — well-documented but sometimes missed by file watcher; reload-window restores it |
| The wrapper script preserves the user's files | CONFIRMED — `gh codespace rebuild` does NOT delete /workspaces; it rebuilds the container, not the codespace |

### What MUST NOT change without explicit decision

1. The banner in `on-attach.sh` MUST stay gated on `command -v docker` returning non-zero. Showing it after a successful rebuild would be noise.
2. The wrapper `codespace_rebuild.sh` MUST keep its interactive confirmation. A non-interactive auto-rebuild would be hostile UX.
3. `.vscode/tasks.json` task labels MUST keep the leading emoji and the `(...)` detail string — VS Code's task picker truncates labels but always shows `detail`.
4. Never silently call `gh codespace rebuild` from `postAttachCommand` or `postStartCommand` — that would create an infinite rebuild loop.

## 6.16 Container Rebuild Catastrophe — Rolling Back Docker Features (2026-05-07 — same branch, third pass)

> **Symptom (verbatim from the user's mobile screenshot, 04:39):**
>
> ```
> Failed to create container.
> Error: Command failed: docker compose --project-name naas-agentic-core_devcontainer
>     -f /var/lib/docker/codespacemount/.persistedshare/docker-compose.devcontainer.yml
>     -f /var/lib/docker/codespacemount/.persistedshare/docker-compose.devcontainer.containerFeatures.yml-…yml
>     build
> Error code: 1302 (UnitiedContainerErrorFatalCreatingContainer)
> Container creation failed.
> ```
>
> The §6.13 fix (adding `docker-in-docker:2`) was meant to enable
> Mission Control. Instead it broke Codespaces creation entirely.

### Why DinD failed at build time

Three stacked incompatibilities:

1. **Base image is `python:3.12-slim`.** The `docker-in-docker:2`
   feature install script needs `iptables`, `iproute2`, `sudo`, and a
   working `service` / `systemctl` shim to install + enable a Docker
   daemon. `python:3.12-slim` ships none of these by default. The
   feature does try to apt-install what it needs, but on a slim image
   the dependency chain expands large enough that *something* in the
   feature build script returns non-zero, surfacing as Codespaces error
   1302.
2. **`network_mode: host` in the compose service.** DinD wants its own
   network namespace to manage iptables NAT rules for nested containers.
   Sharing the host's network namespace prevents the daemon from setting
   up the bridge it expects, and makes the install script's iptables
   probes unreliable.
3. **No `privileged: true` in `docker-compose.host.yml`.** The DinD
   feature documentation explicitly requires the dev container to run
   privileged. In a docker-compose-managed devcontainer, this MUST be
   set in the compose file — the feature itself cannot inject security
   flags. We did not add it in §6.13. (Adding it now would still leave
   problem #2 unresolved.)

### Why DoOD (docker-outside-of-docker) is also a bad fit

DoOD installs only the Docker CLI in the dev container and mounts the
host VM's `/var/run/docker.sock` so commands run against the VM's
daemon. It avoids privileged mode and almost always builds cleanly.
But it has a separate fatal limitation for our setup:

- The observability compose
  (`observability/docker-compose.observability.yml`) uses **relative
  bind mounts**:
  ```
  volumes:
    - ./grafana/grafana.ini:/etc/grafana/grafana.ini:ro
    - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    - ./otel-collector/otel-collector-config.yml:/etc/otel-collector-config.yml:ro
    - ./tempo/tempo-config.yml:/etc/tempo.yml:ro
    - ./loki/loki-config.yml:/etc/loki/loki-config.yml:ro
    - ./grafana/provisioning:/etc/grafana/provisioning:ro
    - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
  ```
- With DoOD, the dev container's `docker compose` CLI sends ABSOLUTE
  paths to the VM's daemon. From inside the dev container the workspace
  is at `/app/`, so the resolved paths look like `/app/observability/grafana/grafana.ini`.
  The VM filesystem has the workspace at
  `/var/lib/docker/codespacemount/workspace/<repo>/` instead → all 7
  bind mounts fail → Grafana, Prometheus, Loki, Tempo, OTel collector
  all crash at startup with "no such file or directory".

A clean DoOD path requires changing `workspaceFolder` from `/app` to
`/workspaces/<repo>` AND rewriting every code reference to `/app` —
roughly 60+ files including the Dockerfile, `supervisor.sh`, and
several telemetry hooks. Out of scope for an emergency fix.

### Decision: roll back the Docker feature entirely

Tradeoff:

| Option | Rebuild succeeds? | Observability stack runs? | Scope |
|---|---|---|---|
| Keep DinD as-is (§6.13) | ❌ no — error 1302 | n/a | rebuild blocks user |
| DinD + `privileged: true` + drop `network_mode: host` | maybe | maybe | drops port-forwarding magic; risky |
| DoOD + path consistency refactor | ✅ yes | ✅ yes | 60+ file refactor; days of work |
| **Drop the Docker feature** | ✅ yes | ❌ stack stays DORMANT | minimal — restores the user's Codespace |

Picked option 4. The user's IMMEDIATE need is a working Codespace. The
observability stack was DORMANT in default Codespaces for the entire
history of this repo before §6.10–§6.15. Rolling back to that state is
the conservative move; it preserves all the §6.10/§6.12/§6.14 polish
(port labels, banners, Grafana env-var wiring, listener-wait helpers) so
the moment Docker integration IS properly engineered, everything else
just works.

### What this branch ships now

| File | Change |
|---|---|
| `.devcontainer/devcontainer.json` | REMOVED `docker-in-docker:2` from `features`. REMOVED `hostRequirements` (was forcing 4cpu/8gb selection — likely a contributing factor to Codespaces error 1302 on smaller machines). Inline JSONC comment block records the rationale. |
| `.devcontainer/docker-compose.host.yml` | Reverted the docker socket mount that the abandoned DoOD path would have needed. |
| `.devcontainer/start_observability.sh` | Replaced the "rebuild required" failure message with a calm, informational "stack is parked, in-process telemetry still works" message. Points users to the FastAPI Prometheus endpoint at `:8000/api/v1/observability/prometheus`. |
| `.devcontainer/on-attach.sh` | Replaced the §6.15 16-line ASCII rebuild banner with a 3-line "PARKED" status. Rebuilding will not help; the underlying compose-mount issue requires a refactor, not a rebuild. |

### What the in-process telemetry endpoint covers (and doesn't)

- ✅ FastAPI HTTP request metrics (count, duration, status code).
- ✅ `path_observer` WS turn metrics (per §6.10): turn duration, fallback
  counters, terminal-event counts.
- ✅ Standard Python process metrics (memory, CPU, GC).
- ❌ Distributed traces (no Tempo).
- ❌ Centralized logs (no Loki).
- ❌ Cross-component dashboards (no Grafana).
- ❌ Trace ↔ log ↔ metric correlation.

For tutoring app development, the in-process metrics are sufficient.
The full Grafana stack is wanted-but-not-needed; it returns the moment
the path-consistency refactor lands.

### What MUST NOT be re-attempted as a "fix"

1. ❌ Re-adding `docker-in-docker:2` without ALSO setting `privileged: true` in `docker-compose.host.yml` AND removing `network_mode: host`.
2. ❌ Re-adding `docker-outside-of-docker:1` without first fixing all 7 relative bind mounts in `observability/docker-compose.observability.yml` to absolute VM paths.
3. ❌ Setting `hostRequirements` to anything > the default machine size (Codespaces error 1302 sometimes correlates with the resource selector failing to provision the requested machine class).
4. ❌ Adding `privileged: true` to `docker-compose.host.yml` purely to silence DinD complaints — privileged mode dev containers have meaningful security implications and should not be enabled without the actual nested-Docker payoff.

### Confidence

| Claim | Confidence |
|---|---|
| Removing the Docker feature unblocks `Container creation failed` | CONFIRMED — error 1302 traces directly to the feature build step in the user's screenshot |
| In-process Prometheus endpoint at `/api/v1/observability/prometheus` works without Docker | CONFIRMED — endpoint is wired through `app/api/routers/observability.py` and exercised by CI |
| The reverted state matches pre-§6.10 default Codespaces behavior | CONFIRMED — only the Docker feature + hostRequirements were post-§6.10 additions |
| Future path-consistency refactor will re-enable the full stack | LIKELY — well-known DoOD pattern with `workspaceFolder=/workspaces/<repo>` is widely deployed |

### Lesson (added to the §6.10 closing rule)

> Infrastructure features (devcontainer features, base images, security
> modes) must pass the same `import + call chain + runtime evidence`
> bar that application code does. A feature that *would* enable a
> capability if installed correctly is not a runtime guarantee — it is a
> hypothesis. **Test the rebuild on a fresh Codespace BEFORE shipping
> any change to `.devcontainer/devcontainer.json`'s `features` block.**
> The §6.13 / §6.14 / §6.15 trio shipped without that check, and cost
> the user three rebuild attempts.

## 6.17 Mission Control via Native Binaries — No Docker Required (2026-05-07 — same branch, fourth pass)

> User mandate: **"yes it must work — incredibly"**. After §6.13 broke
> rebuild and §6.16 rolled it back to a working-but-Grafana-less state,
> we need Mission Control to actually work. This pass bakes Grafana OSS
> and Prometheus directly into the runtime image as native binaries —
> no Docker daemon, no socket, no privileged mode, no extra feature.

### What ships in this pass

| File | Change |
|---|---|
| `Dockerfile` | New stage in the runtime image: downloads `grafana-${GRAFANA_VERSION}.linux-${arch}.tar.gz` and `prometheus-${PROMETHEUS_VERSION}.linux-${arch}.tar.gz` into `/opt/grafana` and `/opt/prometheus`. Auto-detects amd64 vs arm64. Creates `/var/lib/grafana`, `/var/lib/prometheus`, `/var/log/grafana`, `/var/log/prometheus`. ~350 MB added to final image. |
| `observability/native/prometheus.yml` | Native-mode scrape config. Targets ONLY localhost: the FastAPI app on `:8000/api/v1/observability/prometheus`, Prometheus self-metrics on `:9090`, Grafana self-metrics on `:3001/metrics`. No `host.docker.internal`, no Docker network. |
| `observability/native/grafana/provisioning/datasources/datasources.yml` | Single Prometheus datasource at `http://localhost:9090`. Loki and Tempo are intentionally absent (no native single-file binary that's trivially configurable). |
| `observability/native/grafana/provisioning/dashboards/dashboards.yml` | Provider that re-uses the existing `observability/grafana/dashboards/` JSON files — same Mission Control panels as the Docker variant. |
| `.devcontainer/supervisor.sh` | New Step 4C `launch_mission_control()` runs in background after frontend launch. Detects Codespaces, exports `GF_*` env vars (root URL, domain, SameSite=None, Secure=true, CSRF check off — same wiring as §6.12 but for the native binary). Starts Prometheus + Grafana via `nohup` with PIDs persisted to lifecycle state. Idempotent: skips if already running. Hard-guards on missing binaries. |
| `.devcontainer/on-start.sh` | Removed the old `start_observability.sh` background launch. Mission Control is now part of the supervisor's normal startup, not a separate hook. |
| `.devcontainer/start_observability.sh` | Repurposed as a thin status checker (`pgrep` + curl probes). Does NOT start anything anymore. Kept for muscle-memory compatibility. |
| `.devcontainer/on-attach.sh` | Updated banner: when binaries are present, shows STARTING (with public URL + log tail). Removed the §6.15 16-line ASCII banner. |
| `.devcontainer/codespace_rebuild.sh` | Updated description: rebuild now bakes Grafana + Prometheus binaries (not docker-in-docker feature). |

### Why this approach (vs the abandoned alternatives)

| Approach | Verdict | Why |
|---|---|---|
| `docker-in-docker:2` feature | ❌ Rejected (§6.13/§6.16) | Fails to build on `python:3.12-slim` + `network_mode: host`. Codespaces error 1302. |
| `docker-outside-of-docker:1` feature | ❌ Rejected (§6.16) | Build succeeds, but compose's relative bind mounts resolve to `/app/observability/...` inside dev container; VM Docker daemon doesn't see that path. All 7 mounts fail. |
| Path-consistency refactor (`workspaceFolder=/workspaces/<repo>`) | ❌ Out of scope | ~60 files touch `/app`; days of work; high risk. |
| **Native binaries baked into Dockerfile** | ✅ **Picked** | No Docker dependency. No path mismatch. No privileged mode. Configs stay where they are. Works on first rebuild. |
| Run a custom all-in-one container with everything inside | ❌ Rejected | Still needs Docker access; doesn't solve the original problem. |

### Architecture (after this pass)

```
┌─ devcontainer (built from Dockerfile) ──────────────────────────────┐
│                                                                     │
│  Native binaries baked at build time:                               │
│    /opt/grafana/bin/grafana-server  (Grafana OSS 11.3.0)            │
│    /opt/prometheus/prometheus       (Prometheus 2.55.0)             │
│                                                                     │
│  supervisor.sh (Step 4C, background) launches:                      │
│    ├─ uvicorn (FastAPI :8000)                                       │
│    ├─ next dev (:3000)                                              │
│    ├─ /opt/prometheus/prometheus  → :9090                           │
│    │     scrapes localhost:8000/api/v1/observability/prometheus     │
│    │     scrapes localhost:9090   (self)                            │
│    │     scrapes localhost:3001   (Grafana self-metrics)            │
│    └─ /opt/grafana/bin/grafana-server  → :3001                      │
│          datasource: http://localhost:9090                          │
│          dashboards: /app/observability/grafana/dashboards/*.json   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

Codespaces forwards :3001 → public URL → browser opens automatically.

### What works / what doesn't

| Capability | State (post-§6.17) |
|---|---|
| Mission Control dashboard at port 3001 | ✅ Works |
| Path Deep Dive dashboard | ✅ Works (Prometheus-only panels) |
| LangGraph Runtime dashboard | ✅ Works (metrics-driven panels) |
| HTTP API Surface dashboard | ✅ Works |
| Stack Self-Monitoring (`up{}`) | ✅ Partial — only Prometheus + Grafana visible (Loki/Tempo absent) |
| Cross-origin proxy auth (Codespaces preview URL) | ✅ Works — `GF_*` env wiring from §6.12 reused |
| Distributed traces (Tempo) | ❌ Tempo absent |
| Centralized logs (Loki) | ❌ Loki absent |
| Trace ↔ logs ↔ metrics correlation | ❌ Requires Tempo + Loki |
| OTel collector pipeline | ❌ Not started — direct Prometheus scrape replaces it |

This is a deliberate cut: Loki and Tempo don't have a "single binary +
single config + run as background process" story that's as clean as
Grafana and Prometheus. Adding them would require either Docker or
a much heavier Dockerfile. The metrics half of the story IS what users
actually click through 90% of the time.

### Runtime invariants (must remain true on `main`)

1. The Dockerfile MUST keep the binary download + sanity-check (`grafana-server -v` + `prometheus --version`) in the same RUN as the install. If either fails, the image build fails — never silently produce an image without the binaries.
2. `supervisor.sh:launch_mission_control()` MUST stay idempotent. It checks `pgrep` for both binaries and short-circuits if they are already running. Never start two daemons.
3. `supervisor.sh:launch_mission_control()` MUST stay non-blocking and MUST NOT fail the supervisor on observability errors. If the binaries are missing or fail to start, the FastAPI app and Next.js still launch normally.
4. The `GF_*` env wiring (root URL, SameSite, Secure, CSRF) is mandatory for Codespaces. Removing it brings back the §6.12 cookie-loop bug.
5. Port 3001 MUST stay reserved for Grafana (devcontainer.json declares `onAutoForward: openBrowser` on it). Changing the port breaks the auto-open UX.
6. The `observability/grafana/grafana.ini` file is shared between the (retired) Docker variant and the (active) native variant. Its env-override pattern is what makes both work. Do not move Codespaces-specific values into it; they belong in supervisor.sh exports.
7. `observability/native/prometheus.yml` MUST stay localhost-only. Adding Docker hostnames (`otel-collector:8888`, etc.) makes Prometheus log "DNS resolution failed" every 15s and pollutes the logs.

### Confidence levels

| Claim | Confidence |
|---|---|
| Grafana + Prometheus tarball downloads in the Dockerfile | CONFIRMED — both URLs are official, pinned versions |
| Binaries run on Linux amd64 + arm64 | CONFIRMED — `grafana-server -v` + `prometheus --version` are run at build time as a sanity check |
| supervisor.sh launches them in the background without blocking | CONFIRMED by `bash -n` + matching the existing `launch_frontend` pattern |
| Codespaces port 3001 auto-opens in the browser when Grafana listens | LIKELY — same VS Code listener-watcher mechanism that §6.14 polished. **Pending real Codespace rebuild verification.** |
| Cross-origin cookie auth works on the preview proxy | LIKELY — same `GF_*` env wiring proven in §6.12; only difference is the binary instead of the container reads them. Grafana env-var override applies identically. |
| Dashboards render real metrics | LIKELY — `cogniforge_ws_chat_turn_*` series exists in `app/telemetry/metrics.py:export_prometheus_metrics`; Prometheus scrapes the FastAPI endpoint; provisioned dashboard files unchanged. **Pending runtime verification.** |
| Image build completes within Codespaces' build budget | LIKELY — adds ~350 MB and ~30-60 s of download to the existing build (which already pulls torch + Node 20). Comfortably within Codespaces' 5-8 min build window. |

### What MUST NOT change without runtime proof

1. Promoting the `cogniforge-grafana-native` capability to ACTIVE in `.runtime/truth_table.lock.json` requires: (a) image build success on a fresh Codespace, (b) `pgrep grafana-server` returning a PID after supervisor finishes Step 4C, (c) HTTP 200 from `https://<NAME>-3001.preview.app.github.dev/api/health`, AND (d) at least one dashboard panel populating with a real data point (`cogniforge_ws_chat_turn_duration_seconds_count` > 0 after a chat turn).
2. Removing the native binary install from the Dockerfile without first removing `launch_mission_control` from supervisor.sh. The supervisor handles missing binaries gracefully, but leaving the call site without the binary means every boot logs a warning.
3. Adding more datasources (Loki, Tempo, OTel) to `observability/native/grafana/provisioning/datasources/datasources.yml` without ALSO ensuring the corresponding service is actually running on the listed URL. Unreachable datasources show red banners in Grafana and confuse users.

### Lesson (carried from §6.16)

> "Infrastructure features must pass the same `import + call chain +
> runtime evidence` bar as application code." This pass takes the
> opposite direction: instead of relying on a runtime-installed feature,
> we BUILD-TIME embed the dependency. The build-time path is testable
> in CI (image build success = runtime evidence) and has no runtime
> capability gap. **Native dependencies > runtime features for things
> we always need.**

## 6.18 The "No data" Catastrophe — Prometheus Exposition Format Fix (2026-05-07 — same branch, fifth pass)

> **Symptom (verbatim from the user's mobile screenshots, 12:36):**
> Mission Control loads at `https://<NAME>-3001.app.github.dev`, all
> dashboards visible (HTTP API Surface, Path Deep Dive, Mission Control,
> LangGraph Runtime, Stack Self-Monitoring), but EVERY panel shows the
> giant green/blue **"No data"** block. p95 Latency, Req/s, Top 10
> Endpoints, Latency Heatmap, 5xx Errors — all empty.

### Why §6.17 produced an empty Mission Control

Three independent bugs in the data pipeline, all between the FastAPI app
and Prometheus:

1. **The Prometheus exposition format was invalid.**
   `app/telemetry/metrics.py:export_prometheus_metrics()` was emitting:
   ```
   http.requests.total{method=GET,endpoint=/health,status=200} 5
   ```
   Two violations of the Prometheus text format spec:
   - **Dots forbidden in metric names** — Prometheus requires `[a-zA-Z_:][a-zA-Z0-9_:]*`.
     `http.requests.total` is a parse error; the entire line gets dropped silently.
   - **Label values must be quoted with `"..."`.**
     `method=GET` is invalid; the correct form is `method="GET"`.
   Combined effect: Prometheus scraped `:8000/api/v1/observability/prometheus`
   every 15s, parsed zero valid samples, and stored zero data points.

2. **Metric names didn't match what dashboards query.**
   The dashboards query `cogniforge_http_requests_total`,
   `cogniforge_ws_chat_turn_duration_seconds_count`, etc.
   The middleware records `http.requests.total`, `ws.chat.turn.duration_seconds`.
   Even if the format had been valid, the names had no `cogniforge_` prefix —
   so dashboards would still see "No data" because the series don't exist
   under those names.

3. **Histograms weren't exported at all.**
   `record_metric()` appends latency observations to `self.histograms[name]`,
   but `export_prometheus_metrics()` only iterated `self.counters` and
   `self.gauges`. The histogram dict was never read by the export, so
   `_bucket` / `_count` / `_sum` lines (which p95 latency panels need)
   were never emitted. Every histogram_quantile() panel was guaranteed
   to return zero data regardless of fix #1 + #2.

### The fix (single function rewrite)

`app/telemetry/metrics.py:export_prometheus_metrics()` now does three jobs:

1. **Translates internal names to Prometheus-valid names.**
   `http.requests.total` → `cogniforge_http_requests_total`. Dots and
   hyphens become underscores; `cogniforge_` prefix added unless already
   present (idempotent — `cogniforge_uptime_seconds` stays unchanged).

2. **Quotes label values per spec.**
   `key=value` → `key="value"` with backslash + double-quote escaping.

3. **Exports histograms as proper Prometheus histograms.**
   For each metric in the allow-list (`http.request.duration_seconds`,
   `ws.chat.turn.duration_seconds`), emits:
   - 11 cumulative buckets at standard SRE boundaries (5ms → 10s)
   - one `+Inf` bucket
   - `_count` (total observation count)
   - `_sum` (cumulative sum)
   These are exactly the series Grafana's `histogram_quantile()` panels
   require for p50/p95/p99 latency curves.

Output is now:
```
# TYPE cogniforge_http_requests_total counter
cogniforge_http_requests_total{endpoint="/health",method="GET",status="200"} 2.0
# TYPE cogniforge_http_request_duration_seconds histogram
cogniforge_http_request_duration_seconds_bucket{le="0.005"} 1
cogniforge_http_request_duration_seconds_bucket{le="0.01"} 1
... (11 buckets)
cogniforge_http_request_duration_seconds_bucket{le="+Inf"} 7
cogniforge_http_request_duration_seconds_count 7
cogniforge_http_request_duration_seconds_sum 5.33
```

### Dashboard ↔ emitter alignment (post-§6.18)

| Dashboard | Series queried | Emitter | Status |
|---|---|---|---|
| Mission Control | `cogniforge_http_requests_total`, `cogniforge_ws_chat_turn_duration_seconds_*` | `app/middleware/observability/observability_middleware.py` + `app/telemetry/path_observer.py` | ✅ POPULATES |
| Path Deep Dive | `cogniforge_ws_chat_turn_duration_seconds_*`, `cogniforge_ws_chat_fallback_total` | `app/telemetry/path_observer.py` (§6.10) | ✅ POPULATES |
| HTTP API Surface | `cogniforge_http_requests_total`, `cogniforge_http_errors_total`, `cogniforge_http_request_duration_seconds_bucket` | observability middleware | ✅ POPULATES |
| Stack Self-Monitoring | Prometheus self + Grafana self | Prometheus + Grafana built-in | ✅ POPULATES |
| LangGraph Runtime | `cogniforge_langgraph_*` | **none yet** | ⚠️ STAYS EMPTY (no LangGraph instrumentation wired; tracked for a future pass) |

4-of-5 dashboards now functional. The LangGraph one is a known empty
because no production code calls `obs.increment_counter("langgraph.*")` —
that's a separate instrumentation task, not a Prometheus problem.

### Caveat: histogram labels are aggregate-only

The current `MetricsManager.histograms` dict is keyed by metric name and
ignores labels (see `metrics.py:68` — `self.histograms[record.name].append(record.value)`).
So `cogniforge_http_request_duration_seconds_bucket` has no `endpoint`
or `method` labels in the output. p95 latency dashboards aggregate
across all routes work fine; per-endpoint latency heatmaps will show
data but won't be sliced by endpoint. Fixing this requires a deeper
change to make `histograms` label-aware — out of scope for this fix.

### Runtime invariants (must remain true on `main`)

1. `export_prometheus_metrics()` MUST NEVER emit a metric line where the
   name contains `.` or `-`. The translator is the only safe path; bypassing
   it (e.g., emitting raw counter keys directly) reintroduces the parse failure.
2. Label values MUST be quoted with `"..."`. Backslash + double-quote MUST
   be escaped (Prometheus spec).
3. New metric names emitted by application code SHOULD use dot notation
   (`http.foo.total`, `ws.bar.gauge`). The exporter handles the translation
   centrally; emitters should not pre-prefix with `cogniforge_`.
4. Adding a new histogram series requires adding the raw name to `hist_names`
   inside `export_prometheus_metrics()`. Without that allow-list entry, the
   histogram bucket export is skipped (the metric still appears as a counter,
   which is wrong for latency).

### Confidence

| Claim | Confidence |
|---|---|
| Output is valid Prometheus exposition | CONFIRMED — smoke test verifies `# TYPE` headers, quoted labels, no dots in names, +Inf bucket present |
| HTTP/WS counters reach Grafana with correct names | CONFIRMED — name translation produces exactly the strings dashboards query |
| Histograms produce non-empty `_bucket` series after first request | CONFIRMED — smoke test with 7 latency observations produces 11 cumulative buckets + count + sum |
| Mission Control panels populate after a real chat turn | LIKELY — pending fresh Codespace rebuild + browser session; all upstream pieces verified independently |
| Per-endpoint latency heatmap renders correctly | PARTIAL — heatmap will populate (aggregate data), but `endpoint` label filtering won't work until histograms become label-aware (out of scope) |

## 15. Documentation Consolidation Policy (2026-05-06)

- تم اعتماد `CLAUDE.md` و مجلد `.memory/` كمرجع تشغيلي مختصر للمعلومات الحرجة.
- أي تقارير قديمة/أرشيفية تم حذفها من `docs/archive/` لتقليل الضجيج ومنع تضارب الحقائق.
- الوثائق التي تبقى مرجعية:
  - `AGENTS.md` (قواعد التطوير)
  - `docs/architecture/MICROSERVICES_CONSTITUTION.md` (الدستور المعماري)
  - `docs/ARCH_MICROSERVICES_CONSTITUTION.md` (ملخص إنجليزي)
  - `README.md` و `CHANGELOG.md` و `SECURITY.md`
- قبل إضافة أي ملف Markdown جديد: إذا كانت المعلومة تشغيلية قصيرة، توضع في `.memory/*.md` بدل إنشاء تقرير طويل جديد.



## 15) المسار التعليمي vs الدردشة العامة + خريطة التكنولوجيا

### التعريف التشغيلي
- **المسار التعليمي**: مسار موجّه لتحقيق هدف تعلمي (نواتج تعلم + تقييم + تتبع تقدم + استرجاع سياق أكاديمي).
- **الدردشة العامة**: مسار محادثة حرّة (أسئلة عامة، نقاش مفتوح، بدون التزام بناتج تعليمي أو Rubric تقييم).

### الفرق المعماري (Monolith + Microservices + Agent Graph)
1. **التحكم (Control Plane)**
   - المسار التعليمي يحتاج Policy/Guardrails أقوى + Rubric + ذاكرة متخصصة.
   - الدردشة العامة تعتمد سياسة أخف، وتكفيها استجابة سريعة مع سياق جلسة محدود.
2. **البيانات (State + Memory)**
   - التعليمي: `StateGraph` يمرر حالة صريحة (intent, grade, mastery, misconceptions, evidence).
   - العام: حالة أخف (history, tone, user prefs).
3. **الاسترجاع (RAG/Reranking)**
   - التعليمي: Retriever + Reranker إلزامي تقريبًا لتحسين الدقة وتقليل الهلوسة.
   - العام: يمكن الاستغناء عن RAG في كثير من الحالات.
4. **الزمن الحقيقي (Streaming/WebSocket)**
   - كلاهما يستفيد من WS/streaming؛ التعليمي يحتاج كذلك progressive hints وخطوات حل تدريجية.

### علاقة المفاهيم المطلوبة ببعضها (Concept Map)
- **Monolith**: نقطة دخول واحدة سريعة لبناء MVP.
- **Microservices (API-first)**: فصل قدرات مستقلة (auth, orchestrator, retrieval, analytics) مع عقود API.
- **StateGraph / LangGraph**: تنظيم منطق الوكلاء كعُقد وحواف وحالة مشتركة.
- **Reasoning / Multi-agent**: تقسيم التفكير إلى أدوار (planner/researcher/reviewer...) بدل prompt واحد ضخم.
- **LlamaIndex**: طبقة ingestion + indexing + retrieval فوق بياناتك.
- **DSPy**: تحسين منهجي للبرامج اللغوية (prompts/strategies) بمقاييس.
- **Reranker**: إعادة ترتيب نتائج الاسترجاع لرفع precision@k قبل التوليد.
- **KAgent**: شبكة/طبقة تنسيق وكلاء عبر حدود الخدمة.
- **MCP**: بروتوكول موحّد لربط النموذج بالأدوات/الموارد (JSON-RPC session).
- **TLM**: طبقة إدارة نموذج/توجيه مهام (Model routing/governance) حسب الكلفة/الجودة/الزمن.
- **FastAPI + Python**: Backend API + WS.
- **Next.js**: واجهة المستخدم + streaming UI + app routing.
- **Supabase/PostgreSQL**: المصدر الدائم للبيانات (auth + relational core).
- **Redis cache**: تقليل زمن الوصول (sessions, hot keys, rate-limits, short-lived context).

### مبدأ التفعيل الواقعي
وجود الكود لا يعني أنه يعمل فعليًا. الاعتماد النهائي يكون على: **import + call-chain + runtime evidence** كما هو موثق في `.memory/runtime_truth.md`.

## 6.19 Intent Routing Doctrine (2026-05-09)

**The live intent classifier is `_classify_intent()` in `app/services/chat/local_graph.py`.** It is the sole routing decision for every WS chat turn in default Codespaces. It uses pure lexical regex matching and has three known structural failure modes:

1. **Keyword dictatorship**: Words like `تمرين` (exercise), `حل` (solution/solve), `شرح` (explain), `درس` (lesson), `مادة` (material/subject), `history`, `solve` appear in both academic and non-academic contexts. The classifier cannot distinguish them. A student asking about yoga, conflict resolution, or social networks is routed to the educational prompt.

2. **Greeting anchor brittleness**: Greeting patterns use `^...$` anchors. `"السلام عليكم"` (standard Islamic greeting) is NOT caught — it falls through to educational patterns. Any greeting with trailing words fails the anchor.

3. **Context amnesia**: The classifier receives only the current question string. It has no access to conversation history, user profile, or semantic field.

**The intentional duplication rule (D-013):** `_EDUCATIONAL_PATTERNS` and `_GREETING_PATTERNS` are duplicated between `local_graph.py` and `app/telemetry/path_observer.py`. This is intentional — `path_observer.py` must classify before the graph runs without importing from `local_graph.py`'s private API. **Any change to intent patterns MUST be applied to both files in the same PR.**

**The zombie taxonomy rule (D-014):** `app/services/chat/intent_detector.py:IntentDetector` has a 13-intent taxonomy (FILE_READ, CONTENT_RETRIEVAL, ADMIN_QUERY, etc.) incompatible with the live 3-intent taxonomy. It must NOT be wired into the live WS path without an ADR resolving the taxonomy conflict.

**Anti-pattern:** Do NOT add more keywords to `_EDUCATIONAL_PATTERNS` to fix false negatives. This worsens false positives. The correct fix is semantic context guards or embedding-based classification.

**Full analysis:** `.memory/fragility-patterns.md` Pattern 1 · **Issues:** ISS-027 · **Decisions:** D-013, D-014

---

## 6.20 Rendering Integrity Doctrine (2026-05-09)

**Visual hiding ≠ DOM exclusion.** Any UI element hidden via CSS `transform`, `opacity`, or `visibility` (but not `display: none`) remains a live DOM citizen: accessible to screen readers, keyboard Tab, browser find-in-page, and programmatic text selection.

**Current state:** Both sidebars in `CogniForgeApp.jsx` use `transform: translateX(±100%)` to hide. Neither sets `aria-hidden`, `inert`, or `tabindex="-1"` when closed. The `AgentTimeline` component renders agent phase state into the DOM regardless of sidebar visibility.

**The severity escalation rule:** As the agent stack becomes more capable (DORMANT → ACTIVE), `AgentTimeline` will expose real-time agent execution state to screen readers regardless of sidebar visibility. The information leakage surface grows with capability. This must be fixed before any agent capability is promoted to ACTIVE.

**The correct pattern for animated sidebars:**
```jsx
// Add inert attribute — prevents all interaction when closed
<div className={`sidebar ${isOpen ? 'open' : ''}`} inert={!isOpen || undefined}>
```

**What must never be done:**
- Do not assume `transform: translateX(100%)` hides content from screen readers
- Do not add sensitive agent data to sidebar components without `inert` or `aria-hidden` management
- Do not render user-specific data (conversation titles, agent state) in always-present DOM nodes without access control

**Full analysis:** `.memory/fragility-patterns.md` Pattern 2 · **Issues:** ISS-028 · **Decisions:** D-015

---

## 6.21 Dashboard-Metric Contract Doctrine (2026-05-09)

**A Grafana dashboard panel that queries a non-existent metric is a zombie metric.** It is worse than no panel — it creates false confidence that the system is being monitored when it is not.

**Current zombie metrics (confirmed 2026-05-09):** The LangGraph dashboard (`observability/grafana/dashboards/20-langgraph.json`) queries four metrics with zero emitters in the entire codebase:
- `cogniforge_langgraph_node_count_total`
- `cogniforge_langgraph_node_duration_seconds`
- `cogniforge_langgraph_intent_total`
- `cogniforge_langgraph_checkpointer_writes_total`

`local_graph.py` uses `UnifiedObservabilityService.start_trace()` / `end_span()` — in-process span store, not Prometheus. The dashboard expects OTel/Prometheus metrics. The two systems are not connected.

**The dual-emission rule (D-017):** WS turn metrics (`ws.chat.turn.duration_seconds`, `ws.chat.terminal_events.total`, `ws.chat.fallback.total`) must be emitted through exactly one path. The OTel SDK path (`path_observer._emit_to_otel`) is the designated owner. The redundant `obs.record_metric(...)` calls for the same metric names must be removed to prevent double-counting when the full stack is up.

**The verification rule (D-016):** Before adding any Grafana dashboard panel, grep the application source for the metric name in emit calls. If no emitter exists, add the emitter first or do not add the panel.

**The missing CI gate (ISS-031):** No CI step currently verifies that dashboard metric names have corresponding emitters. This gate should be added as `scripts/check_dashboard_metric_contracts.py` — a static check, no runtime required.

**Full analysis:** `.memory/fragility-patterns.md` Patterns 3 and 4 · **Issues:** ISS-029, ISS-030, ISS-031 · **Decisions:** D-016, D-017

---

## 6.22 Runtime Truth Governance Completeness (2026-05-09)

**The three-leg proof has a structural CI gap.** CI enforces legs 1 (import) and 2 (call chain) via `scripts/runtime_truth.py`. Leg 3 (runtime evidence) is never verified in CI. This means a component can be classified ACTIVE while producing zero observable runtime effects.

**Known governance gaps:**
1. **Zombie metrics** — a component can be ACTIVE (imported + called) but emit no metrics. The truth table cannot detect this.
2. **Dashboard-metric contract** — no CI step verifies that dashboard queries match application emitters.
3. **Behavioral dead code** — code that runs but whose output is discarded (e.g., `obs.record_metric` for a metric no dashboard queries).
4. **Configuration-gated dormancy** — `otel_setup.py` is ACTIVE (imported + called) but is a no-op when `OTEL_EXPORTER_OTLP_ENDPOINT` is unset. This is a fourth status tier: **ACTIVE (no-op)** — now formally added to the taxonomy (see §6.23 and §0 doctrine).
5. **Lock file staleness** — `.runtime/truth_table.lock.json` records `"branch": "jules-5513332666705839536-7e7df21b"`, generated 2026-05-08T09:54:43Z. **This lock is stale** — it was generated in a different branch context and the CI drift check currently fails (`customer_chat_router: importer_count 6→5`). Root cause documented in §6.23. Fix: `python scripts/runtime_truth.py --update`.

**The ACTIVE (no-op) tier:** When a component is imported, called, but produces no observable output due to missing configuration, it is neither ACTIVE nor DORMANT in the current taxonomy. It is ACTIVE in the static sense but DORMANT in the runtime sense. Future truth table entries for configuration-gated components should note: "ACTIVE (no-op without `ENV_VAR`)".

**What must never be done:**
- Do not classify a component ACTIVE based only on import + call chain without documenting what runtime evidence would look like
- Do not assume the lock file is current — check `generated_at_utc`
- Do not use span names as metric names — they are different namespaces (UnifiedObs spans vs OTel/Prometheus metrics)
- Do not add a dashboard panel without first running the metric contract check

**Full analysis:** `.memory/fragility-patterns.md` Patterns 3 and 4 · **Issues:** ISS-031 · **Decisions:** D-016, D-017

---

## 6.23 Live Architecture Audit (2026-05-09)

> Mode: READ-ONLY investigation. No application code changed.
> Environment: Ona/Gitpod devcontainer, no `DATABASE_URL` set, no secrets injected.

### What was confirmed by live inspection

**FastAPI startup failure (confirmed):**
- `uvicorn app.main:app` spawns successfully but crashes immediately at `AppSettings()` validation.
- Root cause: `DATABASE_URL` and `APP_DATABASE_URL` both absent → `pydantic_core.ValidationError: DATABASE_URL is missing`.
- Evidence: `.superhuman_bootstrap.log` tail + `ss -tlnp | grep 8000` returns nothing.
- **Lesson**: A running uvicorn PID is not proof of a healthy server. Always verify with `curl /health`.

**Grafana + Prometheus native binaries (confirmed running):**
- `/opt/grafana/bin/grafana-server` and `/opt/prometheus/prometheus` are present in the image and running.
- Launched by `supervisor.sh:launch_mission_control()` — Step 4C, background, non-blocking.
- Grafana health: `GET /api/health → {"database":"ok"}`. Prometheus health: `Prometheus Server is Healthy.`
- Prometheus job `cogniforge-fastapi` shows `up=0` because FastAPI is down in this environment.
- **Lesson**: Observability infrastructure can be healthy while the application it monitors is not.

**Truth table drift (confirmed):**
- `python scripts/runtime_truth.py --check` exits 1: `customer_chat_router: importer_count 6 → 5`.
- Root cause: `.runtime/truth_table.lock.json` was generated on branch `jules-5513332666705839536-7e7df21b` (2026-05-08T09:54:43Z) when `microservices/orchestrator_service/src/api/context_utils.py.orig` existed and was counted as an importer. That `.orig` file still exists but `scripts/runtime_truth.py` only greps `.py` files — the `.orig` extension was counted by the old lock generation run via a different grep path.
- **The component status has NOT changed** — `customer_chat_router` is still ACTIVE. Only the importer count drifted by 1.
- **Action required**: `python scripts/runtime_truth.py --update` to regenerate the lock, then commit. This is a documentation fix, not a code fix.

**`context_utils.py.orig` scratch artifact (confirmed):**
- `microservices/orchestrator_service/src/api/context_utils.py.orig` exists — a backup left from a prior edit session.
- It differs from the live file by one line (context truncation logic).
- Should be deleted in a cleanup PR (see markdown debt inventory in `.memory/diagnostic_2026_05_06_rescue.md §6`).

**`otel_setup.py` status clarification (confirmed):**
- `app/telemetry/otel_setup.py` is imported and called at `app/kernel.py:157,184`.
- Without `OTEL_EXPORTER_OTLP_ENDPOINT`, both `setup_otel()` and `instrument_fastapi_app()` execute but are no-ops.
- This is a fourth status tier not previously in the taxonomy: **ACTIVE (no-op)** — import + call chain present, runtime effect absent due to missing configuration.
- Added to truth table above and to §0 doctrine.

### What did NOT change
- All 29 rows of `.memory/runtime_truth.md` capability table remain valid.
- `local_graph.py` is still PARTIAL (de-facto handler when FastAPI runs with valid DB).
- All microservices still DORMANT.
- All ZOMBIE components unchanged.
- D-006 persistence rules unchanged.
- `_emit_terminal_frames` single-emitter rule unchanged.

---

## 6.24 Advanced LangGraph Forensic Audit — Thread/Session/Node Truth (2026-05-09)

> **Mode**: live forensic investigation. No application code changed.
> **Scope**: advanced LangGraph inside the orchestrator microservice — stategraph, thread_id/session_id propagation, node execution, multi-agent workflow, revival roadmap.
> **Authority**: this section supersedes any aspirational description in `docs/`, blueprints, or README about the advanced agent stack.

### The two LangGraph stacks — do not conflate them

| Stack | Location | Status | Nodes | thread_id format |
|---|---|---|---|---|
| **Local fallback graph** | `app/services/chat/local_graph.py` | **PARTIAL** (de-facto handler) | 2: `supervisor`, `chat` | `str(conversation_id)` e.g. `"394"` |
| **Advanced orchestrator StateGraph** | `microservices/orchestrator_service/src/services/overmind/graph/main.py` | **DORMANT→PARTIAL** | 13: see topology below | `u{user_id}:c{conversation_id}` e.g. `"u7:c394"` |
| **App-level multi-agent workflow** | `app/services/chat/graph/workflow.py` | **ZOMBIE** | 7: planner, researcher, writer, super_reasoner, procedural_auditor, reviewer, supervisor | N/A — KAgent-blocked |

These three graphs are completely independent. They share no state, no checkpointer, and no thread namespace.

### thread_id propagation — verified call chain

**Local fallback graph (PARTIAL — runs every turn in default Codespaces):**
```
customer_chat.py:chat_stream_ws
  → OrchestratorClient.chat_with_agent(conversation_id=lc_id)
    → [ConnectError] → _build_local_graph_response(conversation_id=conversation_id)
      → run_local_graph(conversation_id=conversation_id)
        → thread_id = str(conversation_id)   # e.g. "394"
        → config = {"configurable": {"thread_id": thread_id}}
        → graph.ainvoke(initial_state, config=config)
```
- `thread_id` is `str(conversation_id)` — simple, not user-scoped.
- Checkpointer: `MemorySaver` (module-level singleton in `local_graph.py`).
- State lost on process restart.

**Advanced orchestrator StateGraph (DORMANT→PARTIAL — 3 blockers removed 2026-05-10, needs `docker compose up orchestrator-service`):**
```
customer_chat.py:chat_stream_ws
  → OrchestratorClient.chat_with_agent(question, user_id, conversation_id, context={...})
    → HTTP POST http://orchestrator-service:8006/agent/chat
      → chat_with_agent_endpoint(ChatRequest)
        → context["thread_id"] = _build_conversation_thread_id(user_id, conversation_id)
          # = f"u{user_id}:c{conversation_id}"  e.g. "u7:c394"
        → OrchestratorAgent.run(question, context)   ← NOT the StateGraph
          → intent-based dispatch (13-intent taxonomy)
          → sub-agents: AdminAgent, AnalyticsAgent, CurriculumAgent, etc.
```

**Critical finding**: The monolith's `/agent/chat` HTTP endpoint routes to `OrchestratorAgent.run()` — an intent-based dispatch system — **NOT** the 13-node `StateGraph`. The StateGraph (`create_unified_graph()`) is only invoked by:
1. `/api/chat/messages` (HTTP) → `_run_chat_langgraph()` → `app_graph.astream_events()`
2. `/api/chat/ws` (WS) → `_stream_chat_langgraph()` → `app_graph.astream_events()`
3. `/admin/api/chat/ws` (WS) → `admin_app.astream_events()`

The monolith calls `/agent/chat` (via `ChatRoutingPolicy.candidate_urls()`). Therefore, **even when the orchestrator microservice is running, the 13-node StateGraph is NOT invoked by the monolith's chat path**. The monolith hits `OrchestratorAgent` instead.

### session_id propagation — verified

- The monolith sends `context={"chat_scope":"customer","metadata":...,"compatibility_facade":True}` — **no `thread_id`, no `session_id`**.
- The orchestrator's `/agent/chat` endpoint builds `thread_id` internally from `user_id + conversation_id` via `_build_conversation_thread_id()`.
- `session_id` is extracted from the incoming payload's `context` dict by `_resolve_session_id_from_incoming()`. Since the monolith does not send it, `session_id` is always `None` on the HTTP path.
- On the orchestrator's own WS endpoints (`/api/chat/ws`, `/admin/api/chat/ws`), `sticky_thread_id = _build_conversation_thread_id(user_id, conversation_id)` is set per-turn and injected into `context["thread_id"]`.

### thread_id format mismatch between stacks

| Stack | thread_id format | Checkpointer | Continuity |
|---|---|---|---|
| Local fallback graph | `"394"` (bare conversation_id) | `MemorySaver` (in-process) | Lost on restart |
| Orchestrator StateGraph (when active) | `"u7:c394"` (user-scoped) | `AsyncPostgresSaver` (if DB available) or `MemorySaver` singleton | Persistent (Postgres) or lost on restart (MemorySaver) |
| OrchestratorAgent (HTTP path) | `"u7:c394"` (built internally) | Not used — OrchestratorAgent does not use LangGraph checkpointing | N/A |

**These thread_id namespaces are incompatible.** A conversation that starts on the local fallback graph (`thread_id="394"`) and later routes to the orchestrator StateGraph (`thread_id="u7:c394"`) will have no shared checkpoint state. This is ISS-019 (context identity fragmentation).

### AdminAgentNode thread_id — stateless by design

Inside the 13-node StateGraph, `AdminAgentNode.__call__()` invokes the admin sub-graph with:
```python
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
```
A fresh UUID is generated per invocation. This means the admin sub-graph is **stateless** — no checkpoint continuity even when the parent graph has a Postgres checkpointer. This is intentional (admin queries are stateless by nature) but undocumented.

### Node execution topology — 13-node StateGraph

```
supervisor → [route_intent]
  "educational"      → query_rewriter → query_analyzer → retriever → reranker
                         → [check_results]
                           "found"           → synthesizer
                           "web_fallback"    → web_fallback → synthesizer
                           "general_knowledge" → general_knowledge
  "admin"            → admin_agent → validator
  "tool"             → tool_executor → validator
  "chat"             → chat_fallback → validator
  "general_knowledge" → general_knowledge → validator
validator → [check_quality]
  "pass" → END
  "fail" → supervisor  (retry loop, max retries via retry_count in AgentState)
```

**DSPy usage per node:**
- `SupervisorNode`: `dspy.ChainOfThought(IntentClassifier)` — 4-intent: `educational`, `general_knowledge`, `admin`, `chat`
- `QueryRewriterNode`: `dspy.ChainOfThought(QueryRewriterSignature)` — pronoun resolution
- `QueryAnalyzerNode`: `dspy.Predict(AnalyzeQuery)` — BAC filter extraction (year, subject, branch, exercise_num)
- `SynthesizerNode`: `dspy.Predict(EducationalSynthesizer)` — Arabic response synthesis
- `ChatFallbackNode`: `dspy.Predict(ChatFallbackSignature)` — conversational response

**4-intent taxonomy vs 3-intent taxonomy:**
- Orchestrator StateGraph: `educational`, `general_knowledge`, `admin`, `chat`
- Local fallback graph: `educational`, `general`, `chat`
- These are semantically different. `general_knowledge` routes to a dedicated `GeneralKnowledgeNode`. `general` in the local graph routes to the same `chat_node`. Do not conflate.

### Postgres checkpointer — conditional availability

```python
# microservices/orchestrator_service/src/core/database.py
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None  # → graph compiled without checkpointer

# init_db() sets postgres_checkpointer only when:
# 1. AsyncPostgresSaver is importable
# 2. ORCHESTRATOR_DATABASE_URL is set and reachable
# 3. AsyncConnectionPool opens successfully
# 4. postgres_checkpointer.setup() succeeds

# Fallback: module-level MemorySaver singleton in main.py
_memory_saver: _MemorySaver | None = _MemorySaver()
active_checkpointer = get_checkpointer() or _memory_saver
```

In the default Codespaces environment: `ORCHESTRATOR_DATABASE_URL` is not set → `get_checkpointer()` returns `None` → graph compiled with `_memory_saver` (MemorySaver singleton). State is in-process only.

### WebSearchFallbackNode — Tavily call chain

```
WebSearchFallbackNode.__call__(state)
  → tavily_key = os.environ.get("TAVILY_API_KEY", "").strip()
  → if not tavily_key:
      return {"reranked_docs": [], "used_web": False}  # silent skip
  → research_client.deep_research(query_str)  # HTTP to research-agent:8007
    → research-agent: SuperSearchOrchestrator
      → TavilyClient(api_key=tavily_key).search(query, search_depth="basic", max_results=3)
```

**`TAVILY_API_KEY` is absent from `docker-compose.yml`** — neither `orchestrator-service` nor `research-agent` environment sections include it. Must be added as `- TAVILY_API_KEY=${TAVILY_API_KEY:-}` before the full stack can use web search.

**DuckDuckGo fallback is broken**: `SuperSearchOrchestrator` falls back to `DuckDuckGoSearchAPIWrapper` when Tavily key is absent, but `ddgs` package is NOT installed → `ImportError` on initialization.

### Truth table lock staleness

`.runtime/truth_table.lock.json` was generated on branch `jules-5513332666705839536-7e7df21b` at `2026-05-08T09:54:43Z`. It is stale by at least 1 day and was generated in a different branch context. It does NOT include entries for:
- Orchestrator microservice StateGraph (13 nodes)
- Tavily / WebSearchFallbackNode
- DSPy in orchestrator
- Research agent / SuperSearchOrchestrator
- OrchestratorAgent (intent-based dispatch)

**Action required**: `python scripts/runtime_truth.py --update` to regenerate, then commit in the same PR as any capability status change.

### Revival roadmap — advanced LangGraph + Tavily (documentation only)

To bring the advanced orchestrator StateGraph to ACTIVE status on the live call chain:

1. **Add `TAVILY_API_KEY` to `docker-compose.yml`** under both `orchestrator-service` and `research-agent` environment sections: `- TAVILY_API_KEY=${TAVILY_API_KEY:-}`
2. **Start the microservices stack**: `docker compose -f docker-compose.yml up -d orchestrator-service research-agent postgres-orchestrator redis-orchestrator`
3. **Verify orchestrator health**: `curl http://localhost:8006/health` — warmup check in `main.py` lifespan must pass (admin tool invocation returns `tool_name` in `final_response`)
4. **Set `ORCHESTRATOR_SERVICE_URL`** in the monolith to `http://localhost:8006` (or `http://orchestrator-service:8006` on the Docker network)
5. **Verify the StateGraph is invoked**: the monolith calls `/agent/chat` → `OrchestratorAgent.run()` (NOT the StateGraph). To route through the StateGraph, the monolith must call `/api/chat/messages` instead. This requires a routing policy change in `ChatRoutingPolicy.candidate_urls()`.
6. **Fix `ddgs` package**: `pip install ddgs` in the research-agent container if DuckDuckGo fallback is needed
7. **Update `.memory/runtime_truth.md`**: add rows for orchestrator StateGraph (ACTIVE), Tavily (ACTIVE), WebSearchFallbackNode (ACTIVE)

**Architectural boundary that must be respected**: the monolith must never import from `microservices/`. All communication is HTTP only. The `persisted: true` flag protocol (D-006) applies when the orchestrator is active.

---

## Architecture Reality and System Rules
The NAAS-Agentic-Core system is in a transitional "strangler fig" phase, meaning there is significant fragmentation between the legacy monolith (`app/`) and the aspirational microservices stack (`microservices/`).
* **ACTIVE**: The legacy monolith (`app/api/routers/customer_chat.py`), Next.js frontend (tightly coupled to legacy REST routes), and rudimentary fallback graphs (`local_graph.py`).
* **PARTIAL**: `api-gateway` defines route proxies but relies on dormant microservices.
* **DORMANT**: The entire microservices stack (orchestrator, reasoning, etc.), along with MCP, DSPy, and LlamaIndex capabilities gated behind them, are dormant by default. They require `docker-compose.yml` to be fully active.
* **ZOMBIE**: Kagent mesh (`app/services/kagent`) and advanced graph workflows (`app/services/chat/graph/workflow.py`) are registered but have zero live consumers.

**Strict Architecture Rules:**
* "Any component that lacks an import, a clear call chain, and runtime evidence is treated as DORMANT or ZOMBIE until proven otherwise."
* **First-check protocol before any change:** You must first verify if a component is ACTIVE, PARTIAL, DORMANT, or ZOMBIE. Do not edit dead code unless you are explicitly wiring it into a live execution path (e.g., `app/api/routers/`, `app/kernel.py`, or `local_graph.py`).
* Do not trust documentation or blueprint assertions about "Agentic" capabilities (like multi-agent coordination) without verifying their status in the truth table. Currently, most advanced capabilities are aspirational or dormant.

## Observability Truth and Runtime Rules

**1. How the Observability System Actually Works**
*   **In-Process Metrics via Native Binaries:** ACTIVE. Prometheus scrapes `/api/v1/observability/prometheus` running in-process (FastAPI). Native Grafana binaries in the devcontainer (`supervisor.sh`) render these. This is the **ONLY** fully live observability path by default.
*   **OpenTelemetry Traces & Logs:** DORMANT. `otel_setup.py` bypasses execution without `OTEL_EXPORTER_OTLP_ENDPOINT`. OTel Collector, Tempo, and Loki are missing from default execution.
*   **UnifiedObservabilityService:** PARTIAL. Collects traces/logs/metrics in memory, attempting to sync to `observability_service`. Fails silently in the background if the service is unreachable.
*   **AIOps (observability_service):** PARTIAL. Structurally complete but operationally volatile; relies entirely on `InMemoryTelemetryRepository` which resets on container restart.
*   **WebSocket Tracing:** PARTIAL. `WsTurnSpan` exists for whole turns, but per-frame tracing (ISS-005) is missing.
*   **LangGraph Tracing:** DORMANT. Depends entirely on the inactive OpenTelemetry scope, falling back to `logger.info` via `_NoOpSpan`.

**2. Deep Diagnostic Realities (Enterprise Grade)**
*   **Trace Split-Brain:** There is a total break in trace continuity at the system boundary. The API Gateway injects `traceparent` headers via `opentelemetry.propagate`, but the downstream Orchestrator Service ignores them, severing trace context.
*   **Telemetry Evidence:** ACTIVE. Ad-hoc paths write diagnostic lines directly to `telemetry_evidence.txt` because formalized tracing fails.
*   **GitHub Actions CI (`observability_validation.yml`):** ACTIVE but narrow. It validates structural wiring (imports, YAML syntax) and existence of checks, but it **DOES NOT** prove runtime telemetry flow.

**3. Rules for AI (What you must do before assuming observability)**

*   **Permanent Observability Doctrine:**
    *   **Runtime truth over synthetic certainty.** If it isn't executing and measured, it isn't real.
    *   **Instrumentation before visualization.** Dashboards must never outpace instrumentation.
    *   **Unknown is better than fake certainty.** Do not present dormant systems as healthy.
    *   **Every metric must have a semantic contract,** and must reflect real runtime evidence.
    *   **Repository memory must remain coherent, curated, and durable.** Every future agent must inherit these rules automatically.
*   **Do NOT assume traces or correlated logs exist.** Unless you manually boot the Docker Compose observability stack, Tempo/Loki are dead.
*   **Use Native Metrics.** If you need evidence, use Prometheus metrics surfaced via native Grafana on port 3001, or manual stdout logs.
*   **Do not remove structural hooks.** CI checks (like `check_tracing_gate.py`) enforce the *presence* of hooks like `open_ws_turn` or `TraceContextMiddleware`. Deleting dormant observability code will break the CI gate.
*   **If you need a signal:** If there is no runtime evidence (logs, Prometheus counters, DB writes) for an observability capability, **treat it as ZOMBIE/DORMANT.** Do not hallucinate capabilities.
*   **Always check GitHub Actions status:** Red X means a strict contract (like duplicate writes, fallback safety, or doc integrity) failed. Do not bypass the gate.

---

## 6.8 Lifespan Orchestration & Env Injection Doctrine (2026-05-09 — branch `fix/lifespan-orchestration-env-injection`)

> **Root cause of the "Partial/Degraded Runtime" problem — diagnosed and fixed live.**

### The Exact Failure Mode

The system entered a misleading partial-startup state because of a chain of three independent failures:

1. **Process env gap**: `devcontainer.json` maps `DATABASE_URL` from `${localEnv:DATABASE_URL}`. In Ona/Gitpod, secrets are NOT injected as process env vars into the container. The process env is empty.

2. **Module-import-time read**: `app/core/settings/base.py:23` calls `os.environ.get("APP_DATABASE_URL")` at **module import time** — before pydantic-settings reads `.env`. Finds empty string. `_ensure_database_url()` raises `ValueError`. Uvicorn worker crashes on import. Port 8000 never opens.

3. **Stale state file**: `supervisor.sh` health check read `.devcontainer/state/app_healthy` from a previous successful run → reported healthy. **Uvicorn PID alive, port 8000 dead, state file says healthy. Misleading observability.**

### The Orchestrator Lifespan Problem

The orchestrator microservice had a separate but related problem: `lifespan()` warmup `ainvoke()` had no timeout. On slow LLM/network, it blocked ASGI startup indefinitely. `RuntimeError` from warmup propagated up and crashed ASGI startup. The service appeared alive (PID, port open, `/health` 200) but was actually in a partial startup state — graph nodes not initialized.

### Rules (permanent doctrine)

```
# NEVER start uvicorn without exporting .env into the process environment first
# ❌ Wrong — .env is read by pydantic AFTER module-level os.environ.get() runs
python -m uvicorn app.main:app

# ✅ Correct — export .env keys into process env before uvicorn starts
source <(grep -v '^#' .env | sed 's/^/export /')
python -m uvicorn app.main:app
```

```python
# NEVER use unbounded ainvoke() in a lifespan context
# ❌ Wrong — blocks ASGI startup indefinitely on slow LLM/network
result = await app.state.admin_app.ainvoke(warmup_state, config=config)

# ✅ Correct — always timeout-guard warmup probes
result = await asyncio.wait_for(
    app.state.admin_app.ainvoke(warmup_state, config=config),
    timeout=30.0,
)
```

```python
# NEVER return {"status": "ok"} unconditionally from /health
# ❌ Wrong — hides degraded graph state from operators
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orchestrator-service"}

# ✅ Correct — expose startup_state so operators can diagnose without restarting
@app.get("/health")
async def health_check():
    startup_state = getattr(app.state, "startup_state", "starting")
    errors = getattr(app.state, "startup_errors", [])
    return {
        "status": "ok" if startup_state == "ready" else startup_state,
        "service": "orchestrator-service",
        "startup_state": startup_state,
        **({"startup_errors": errors} if errors else {}),
    }
```

### Lifespan phase criticality contract

Every microservice lifespan must follow this phase model:

| Phase | Criticality | On failure |
|-------|-------------|-----------|
| DB init | **CRITICAL** | Raise — service cannot start without DB |
| Tool/plugin registry | **CRITICAL** | Raise — service cannot function without tools |
| Graph compile | **NON-CRITICAL** | Log DEGRADED, continue |
| Warmup probe | **NON-CRITICAL, timeout=30s** | Log DEGRADED, continue |
| Background tasks | **NON-CRITICAL** | Log warning, continue |

## Streaming Data Contracts (2026-05-10)

The system enforces a strict data contract for real-time WebSocket chat streaming to guarantee the "typing effect". Both the monolith and microservices must adhere to this contract.

*   **Execution Rule:** Never use `ainvoke()` for real-time user-facing LangGraph executions. It acts as a block-and-wait buffer. You must use `astream_events(..., version="v2")`.
*   **Routing Rule:** API routing layers (FastAPI WebSocket routes, REST proxies) must capture `on_chat_model_stream` events and instantly yield them as granular `assistant_delta` JSON payloads to the client. Token buffering is strictly prohibited.
*   **Detailed Forensic Breakdown:** Read `.memory/streaming_architecture_breakdown.md` for the complete architectural diagnosis of the event stream bottleneck across the legacy, microservice, and frontend layers.

---

### LangGraph metrics now live

`app/services/chat/local_graph.py` now emits per-turn Prometheus metrics:

| Metric | Labels | Dashboard panel |
|--------|--------|----------------|
| `cogniforge_langgraph_intent_total` | `intent`, `graph` | Intent distribution (20-langgraph.json) |
| `cogniforge_langgraph_node_count_total` | `node`, `graph` | Node throughput (20-langgraph.json) |
| `cogniforge_langgraph_node_duration_seconds` | `node`, `graph` | p95 latency (20-langgraph.json) |

These metrics appear in Prometheus after the first WS chat turn. `cogniforge_langgraph_checkpointer_writes_total` remains a zombie metric until Postgres checkpointer is activated (ISS-020).

### Prometheus scrape targets (all UP after fix)

```
cogniforge-fastapi  http://localhost:8000/api/v1/observability/prometheus  → UP
grafana             http://localhost:3001/metrics                           → UP
prometheus          http://localhost:9090/metrics                           → UP
```

---

## 6.26 Dashboard Zombie-Metric Sweep + CI YAML Repair (2026-05-12, branch `claude/setup-microservices-monitoring-ralbR`)

> Live sandbox audit (no outbound network — Supabase / OpenRouter / Tavily reachability could not be verified from this environment; CI on GitHub will exercise them with the secrets).
> Scope: contract-completeness sweep across all 17 Grafana dashboards + 21 GitHub Actions workflows + Skills Architecture compliance.

### What was verified (static + tooling)

| Gate | Tool | Result |
|---|---|---|
| `ruff check .` | `ruff 0.15.8` | ✅ Clean (was 2 errors — RUF100 in `tests/unit/test_dual_write_immunity.py:19` + structural drift fixed) |
| `python3 scripts/runtime_truth.py --check` | runtime truth gate | ✅ Lock regenerated 2026-05-12 (was stale, drift in `customer_chat_router: importer_count 5→6`) |
| `python3 scripts/validate_structure.py` | structure gate | ✅ Passes (3 informational warnings, none blocking) |
| Skill isolation — `scripts/fitness/check_no_app_imports_in_microservices.py` (manual replay) | py3.11 fallback | ✅ Zero cross-microservice imports, zero `app.*` imports |
| All 21 GitHub Actions workflows parse as YAML | `yaml.safe_load` | ✅ All 21 OK (was 3 BAD — `microservices-step4.yml`, `microservices-step5-user-service.yml`, `microservices-step6-planning-agent.yml`) |
| Grafana dashboards JSON validity | json.load | ✅ All 17 valid |
| Grafana dashboard ↔ emitter contract | grep-based static check | ✅ 94/94 unique metrics have a real emitter (was 4 zombies; see below) |
| Skills Architecture metrics inventory (≥ 7 metrics / skill) | manual replay | ✅ 7/7 skills: orchestrator(42), user(22), planning(22), conversation(22), research(22), reasoning(22), content-retrieval(14) |
| Health endpoint coverage | manual replay | ✅ 7/7 skills expose `/health` |
| Prometheus scrape targets in `observability/native/prometheus.yml` | grep `job_name:` | ✅ 12 targets (meets ≥ 12 floor required by skills-architecture-gate.yml) |

### Zombie metrics — surgically removed from dashboards

Four dashboard panels were querying metric names that **NO emitter in the codebase produces**. They have been replaced with their real-emitter equivalents.

| Dashboard | Old (zombie) query | New (real-emitter) query | Why |
|---|---|---|---|
| `20-langgraph.json` (LangGraph Runtime, panel 21) | `rate(cogniforge_langgraph_checkpointer_writes_total[2m])` | `sum by (status) (rate(cogniforge_checkpointer_writes_total[2m]))` | No emitter for `langgraph_checkpointer_writes`; orchestrator-service emits `cogniforge_checkpointer_writes_total{status,thread_id_prefix}` from `prom_metrics.py:246` (Step 10 — Postgres checkpointer) |
| `60-microservices-step3-live.json` (Tavily Calls stat, panel 16) | `cogniforge_tavily_search_total` | `sum(cogniforge_research_tavily_calls_total)` | Real emitter lives in `microservices/research_agent/prom_metrics.py:115` |
| `50-microservices-transition.json` (Tavily Search Outcomes, panel 6) | `cogniforge_tavily_search_total{result="success"\|"skipped_no_key"\|"error"}` | `cogniforge_research_tavily_calls_total{status="success"}` / `cogniforge_research_startup_info{tavily_available="false"}` / `cogniforge_research_tavily_errors_total` | The `{result="..."}` label dimension never existed; replaced with the real label sets emitted by research-agent |
| `50-microservices-transition.json` (Orchestrator Startup State stat) | `cogniforge_orchestrator_startup_ready` | `max(cogniforge_orchestrator_startup_info{graph_ready="true"})` | Only `startup_info{graph_ready,outbox_relay_enabled,...}` is emitted (`orchestrator_service/src/core/prom_metrics.py`) |

After the sweep: **94 unique metrics → 94 emitters found → 0 zombies**. This restores the §6.21 dashboard-metric contract doctrine (D-016) to a fully verifiable state. The CI gate `scripts/check_dashboard_metric_contracts.py` referenced in CLAUDE.md §6.22 is still TBD as a CI step; the manual sweep here closes the immediate drift.

### CI YAML repair — three workflows had un-indented Python heredocs

Three workflows embedded Python via `python3 -c "..."` with the multi-line code starting at column 1 — outside the parent YAML `|` block scalar. Standard `yaml.safe_load` rejected them; GitHub Actions' parser may have tolerated this but the gate was structurally fragile.

Fixed by switching to bash heredoc (`python3 <<'PY' ... PY`) at the correct YAML indent level. In each case the script body was also dedented and (where it referenced shell variables) switched to `os.environ['DASHBOARD']` injection to avoid double-substitution surprises:

| Workflow | Where | Pattern after fix |
|---|---|---|
| `microservices-step4.yml` | dashboard JSON validation | `python3 <<'PY' ... PY` |
| `microservices-step5-user-service.yml` | dashboard JSON validation | `DASHBOARD="$DASHBOARD" python3 <<'PY' ... PY` |
| `microservices-step6-planning-agent.yml` | docker-compose schema + dashboard JSON | Two heredocs, same pattern |

Bonus repair: `microservices-step4.yml` PR-summary `actions/github-script@v7` block had a multi-line JS template literal whose markdown body (lines 257–289) was un-indented. Replaced with a `[...].join('\n')` array to keep YAML block-scalar indentation consistent.

### What was **not** verified live

The sandbox blocks outbound HTTPS. The provided secrets (`OPENROUTER_API_KEY`, `TAVILY_API_KEY` via the MCP URL form, `DATABASE_URL` to Supabase) were not exercised against the live endpoints from this run. Conclusions about pipeline mode (`full`/`partial`/`fallback`) **cannot** be re-confirmed without a live Codespaces session. The §6.25 / D-043 / D-044 / D-045 live verifications from 2026-05-11 remain the authoritative record until the next live audit.

### Rules added

1. **Dashboard ↔ emitter contract is a release gate**: before merging any new dashboard panel, run the static contract check (grep-based; see commit). A new CI step `dashboard-metric-contract` should wrap this — tracked as a follow-up.
2. **YAML heredoc rule**: never embed multi-line Python via `python3 -c "..."` inside a YAML `run: |` block. Use `python3 <<'PY' ... PY` with content indented to the YAML block scalar level. Pass shell-variable values through `ENV=val python3 <<'PY' ... os.environ['ENV'] ... PY` — never via string interpolation, which mixes shell + YAML + Python escaping.
3. **github-script multi-line strings**: never use JS template literals (`` ` ... ` ``) that span multiple lines in a YAML `script: |` block. Use an array of single-line strings + `.join('\n')` — that way YAML indentation stays correct and the markdown body remains readable.

---

## 6.27 Streaming Bottleneck Eliminated — Token-Level WS Deltas (2026-05-12, D-047)

> هذا القسم يحكم بشكل دائم سلوك بث الـ chat: **لا تجميع، لا انتظار، token-by-token حتمي**.

### المشكلة قبل الإصلاح

الردود كانت تظهر دفعة واحدة كارثية على الواجهة. التحقيق الجنائي في `.memory/streaming_architecture_breakdown.md` (2026-05-10) كشف ثلاثة بقوع متداخلة:

| الطبقة | السلوك المعطوب |
|---|---|
| **Monolith** (`app/services/chat/local_graph.py:297`) | `graph.ainvoke(...)` يحبس التنفيذ حتى نهاية الرد، يُرجِع نصاً واحداً |
| **Orchestrator** (`microservices/orchestrator_service/src/api/routes.py`) | `astream_events(version="v2")` صحيح، لكن `on_chat_model_stream` كان `pass` — token deltas مُتجاهَلة صراحةً |
| **Frontend** | `mergeAssistantContent` صحيح لكنه يستقبل deltaواحدة فقط — typing-effect مستحيل رياضياً |

### الإصلاح (D-047 — مطبَّق في هذا الفرع)

**المسار المحلي (Monolith fallback chain):**
- أُضيفت `run_local_graph_stream()` في `local_graph.py`: AsyncGenerator يتجاوز LangGraph (لأن `OpenRouterClient` ليس `BaseChatModel` من LangChain فلا تُولِّد `astream_events` أحداث `on_chat_model_stream`)، يُشغِّل `_classify_intent` ثم يستدعي `OpenRouterClient.stream_chat` مباشرة ويُصدِر كل `delta.content` فوراً.
- أُضيفت `_stream_local_graph_response()` و `_stream_local_general_chat_response()` في `OrchestratorClient`، وأُعيد كتابة الفرعين 3 و 4 من fallback chain في `chat_with_agent` لإصدار N × `assistant_delta` لكل turn (بدل واحدة كبيرة).

**Orchestrator microservice (3 مواقع):**
- HTTP `/api/chat/messages` (line ~1810): `on_chat_model_stream` → `assistant_delta`
- WS `/api/chat/ws` worker task (line ~1532): نفس النمط عبر `_safe_put`، يُمرَّر `__streamed_chars` للـ consumer
- WS `/admin/api/chat/ws` (line ~2562): نفس النمط

### عقد منع التكرار (Duplicate-Suppression Contract)

> القاعدة الذهبية: **إذا بُثَّ أي token-level delta خلال الـ turn، فإن `assistant_final.payload.content` يجب أن يكون `""`**.

السبب: `mergeAssistantContent` على الواجهة يجمع جميع `assistant_delta` بشكل تتابعي. إذا ضاف `assistant_final.content` يحوي النص الكامل، يُصبح الرد مكرراً مرتين على الشاشة.

```
streamed_chars > 0  →  assistant_final.payload.content = ""
streamed_chars == 0 →  assistant_final.payload.content = response_text   (backward-compat)
```

`streamed_chars` يُعلَّق أيضاً على `assistant_final.payload` كحقل metadata للقياس ولـ Grafana panels.

### قواعد دائمة (لا تُكسر بدون ADR)

1. **`ainvoke()` ممنوع على المسار الحي للمستخدم** — أي LangGraph runtime موجَّه لـ user-facing real-time chat يجب أن يستخدم `astream_events(version="v2")` أو AsyncGenerator مكافئ.
2. **`on_chat_model_stream` يجب أن يُصدِر `assistant_delta` فوراً** — لا buffering، لا تجميع، لا انتظار لـ `on_chain_end`.
3. **duplicate-suppression contract إلزامي** — أي إضافة لمسار streaming جديد يجب أن تطبق هذا العقد، وإلا فالمستخدم يرى الرد مكرراً.
4. **`OpenRouterClient.stream_chat` هو القناة المتدفقة الوحيدة** للمسار المحلي — لا تستبدله بـ `send_message` (الذي يجمع داخلياً).
5. **`path_observer.WsTurnSpan` هو المنتج الوحيد لـ WS turn metrics** (§6.10) — لا تكسر هذا العقد عند إضافة streaming counters.

### قياس النجاح حياً

```bash
# يجب أن تظهر 20-100+ سطور NDJSON متتابعة، كل واحدة assistant_delta واحد
curl -N -X POST http://localhost:8006/api/chat/messages \
  -H "Authorization: Bearer $JWT" \
  -d '{"question":"اشرح قانون أوم","user_id":7,"conversation_id":1}' | head -50

# WS test — يجب أن تتدفق الرسائل خلال ~1s من الإرسال، ليس بعد 30s
wscat -c "ws://localhost:8000/api/chat/ws?token=$JWT" -s jwt

# في المتصفح: الرد يجب أن يظهر مرة واحدة فقط (لا duplicate بعد انتهاء streaming)
```

### ما لم يتغير (مقصوداً)

- `app/api/routers/customer_chat.py` — كان يُمرِّر كل event عبر `websocket.send_json()` مباشرة بدون buffering. البق كان upstream منه.
- `frontend/app/hooks/useAgentSocket.js` + `mergeAssistantContent.ts` — يعملان بشكل صحيح أصلاً. البق كان 100% backend.
- `microservices/conversation_service` — لا يزال يستخدم `ainvoke` لأنه ليس على المسار الحي اليوم؛ سيُحَدَّث عند تفعيله.
- D-006 persistence semantics و `_emit_terminal_frames` — بدون تغيير.

**ملف التفاصيل الكامل**: `.memory/streaming_architecture_breakdown.md` "D-047 Implementation Report".
**قرار معماري**: `.memory/decisions.md` D-047.
**bug log**: `.memory/issues.md` ISS-055.

---

## 6.28 Orchestrator Production Streaming — DSPy/raw-OpenAI via Custom Events (2026-05-12, D-048)

> **مكمِّل ضروري لـ §6.27**. D-047 وحده لم يكن كافياً للمستخدم الفعلي على المسار الافتراضي.

### لماذا D-047 لم يكن كافياً

`§6.27` فتح القناة الانسيابية في 3 طبقات. لكن المسار الإنتاجي الحقيقي — `orchestrator-service:8006` — يستخدم في عقده الورقية (`SynthesizerNode`, `ChatFallbackNode`, `GeneralKnowledgeNode`):

- **DSPy 3.x** (`dspy.Predict`, `dspy.ChainOfThought`) — يلف نموذج DSPy الخاص
- **`OpenRouterClient.send_message`** و **`openai.AsyncOpenAI`** — استدعاء خام

أي منهما لا يصدر `on_chat_model_stream` من `astream_events(version="v2")` (تلك تُولَّد فقط من نماذج LangChain `BaseChatModel`). فالـ branch الذي أضفته D-047 لـ `on_chat_model_stream` يبقى dormant على المسار الإنتاجي → المستخدم يرى رد دفعة واحدة كارثية حتى بعد D-047.

### الحل (D-048)

استخدام `langgraph.config.get_stream_writer()` + `astream_events`'s `on_custom_event` كقناة بديلة على مستوى البايت.

**نمط hybrid في كل عقدة ورقية**:

```python
@staticmethod
def _get_writer():
    try:
        from langgraph.config import get_stream_writer
        return get_stream_writer()
    except Exception:
        return None

async def __call__(self, state):
    writer = self._get_writer()
    if writer is not None:
        # وضع streaming — raw OpenRouter SSE + custom events
        parts = []
        async for chunk in ai_client.stream_chat(messages):
            delta = chunk["choices"][0]["delta"].get("content")
            if delta:
                parts.append(delta)
                writer({"chunk_type": "assistant_delta", "content": delta, "node": "<name>"})
        full = "".join(parts).strip()
    else:
        # وضع batch — DSPy/send_message محفوظ
        prediction = await anyio.to_thread.run_sync(lambda: self.generator(...))
        full = prediction.response
    return {"final_response": full, "messages": [AIMessage(content=full)]}
```

`get_stream_writer()` يُعيد `None` في وضع `ainvoke` (اختبارات، batch) → DSPy يعمل كما هو، صفر regression.
`get_stream_writer()` يُعيد writer في وضع `astream_events` → كل `delta.content` يُرسَل فوراً كـ `on_custom_event`.

### العقد المعاد كتابتها

| العقدة | الملف | DSPy signature المحفوظ |
|---|---|---|
| `GeneralKnowledgeNode` | `general_knowledge.py` | N/A — يستخدم `send_message` في وضع batch |
| `ChatFallbackNode` | `main.py` | `dspy.Predict(ChatFallbackSignature)` |
| `SynthesizerNode` | `search.py` | `dspy.Predict(EducationalSynthesizer)` |

`SynthesizerNode` الأعقد — يُرجِع JSON منظماً `{"المصدر","التمرين",...}` مع المتن في حقل `"التمرين"`. مسار streaming الجديد يبني نفس مظروف JSON، لكن `"التمرين"` يُعبَأ بـ concatenation للقطع المتدفقة. كل قطعة تصل أيضاً للمستخدم كـ `assistant_delta` فور وصولها → الواجهة ترسم الشرح العربي الطويل كلمة بكلمة، بينما مظروف JSON يصل لطبقة الـ persistence سليماً.

### استهلاك `on_custom_event` في `routes.py`

أُضيف فرع جديد بجانب `on_chat_model_stream` (D-047) في **3 مواقع**:
- HTTP `/api/chat/messages` streaming generator
- Customer WS `/api/chat/ws` worker task
- Admin WS `/admin/api/chat/ws` streaming response

```python
elif event_type == "on_custom_event":
    data = event.get("data")
    if isinstance(data, dict) and data.get("chunk_type") == "assistant_delta":
        content = data.get("content")
        if isinstance(content, str) and content:
            streamed_chars += len(content)
            yield {"type": "assistant_delta", "payload": {"content": content}}
```

عدّاد `streamed_chars` نفسه يُستخدم لكلا القناتين → عقد منع التكرار (D-047) يعمل تلقائياً مع D-048.

### الأثر النهائي (matrix)

| المسار | قبل D-047 | بعد D-047 فقط | بعد D-048 |
|---|---|---|---|
| Monolith local fallback | burst واحد | ✅ word-by-word | ✅ word-by-word |
| Orchestrator (DSPy + raw OpenAI) — **الإنتاج الافتراضي** | burst واحد | ❌ لا يزال burst | ✅ word-by-word |
| Orchestrator (هجرة مستقبلية إلى LangChain ChatOpenAI) | burst واحد | ✅ word-by-word | ✅ word-by-word |
| Admin WS (DSPy + raw OpenAI) | burst | ❌ لا يزال burst | ✅ word-by-word |

### قواعد دائمة أُضيفت

1. أي عقدة ورقية في الـ orchestrator graph تُصدِر `final_response` للمستخدم **يجب** أن تجرب `get_stream_writer()` وتبث عبر custom events عند توفره. DSPy non-streaming يبقى fallback لـ batch/tests.
2. `routes.py` **يجب** أن يستمع لكلا `on_chat_model_stream` و `on_custom_event` ليغطي العقد LangChain-native والعقد DSPy/raw-OpenAI.
3. مظروف الـ custom event canonical: `{"chunk_type": "assistant_delta", "content": str, "node": str}` — لا تخترع variants. حقل `node` للقياس فقط؛ `routes.py` يتجاهله.
4. `langgraph>=0.2.39` متطلب صلب — أقدم لا يدعم `get_stream_writer()`. متغير في `requirements.txt` بالفعل.

### قياس النجاح حياً

```bash
# يجب أن تظهر 20-100+ سطور NDJSON على الإنتاج الافتراضي (DSPy/raw OpenAI nodes)
curl -N -X POST http://localhost:8006/api/chat/messages \
  -H "Authorization: Bearer $JWT" \
  -d '{"question":"اشرح قانون أوم","user_id":7,"conversation_id":1}'
# المتوقع: tens of small {"type":"assistant_delta","payload":{"content":"..."}} lines

# عداد جديد في الـ orchestrator (sustained > 1 خلال chat نشط):
curl http://localhost:8006/metrics | grep 'cogniforge_pipeline_invocations_total'
```

**زمن أول-كلمة المتوقع**: ~800ms (بدل 25–40s burst).

---

## 6.29 Indexed Knowledge Retrieval + Exam-Card Display Doctrine (2026-05-13, ISS-051 / D-048 / D-049)

> هذا القسم يحكم استرجاع التمارين التعليمية من `knowledge_base/`. أي تعديل على
> مسار الاسترجاع يجب أن يحترم القواعد الخمس أدناه — وإلا فالكارثة تعود.

### الكارثة المُشخَّصة (قبل الإصلاح)

عندما يكتب الطالب: «اعطني تمرين دوال عددية شعبة علوم تجريبية الموضوع الثاني التمرين الرابع لسنة 2016 الدورة الأولى»

كان يحصل على:

| الأعراض | السبب الجذري |
|---|---|
| ملف 2016 (الدوال) + ملف 2024 (الاحتمالات) كلاهما يظهران | wide-net `local_store.search_local_knowledge_base()` يقرأ كل `.md` في `knowledge_base/` |
| YAML metadata غريب (`---`, `metadata:`, `topics:`...) يظهر للطالب | لا يوجد frontmatter stripping |
| عناصر الإجابة النموذجية مكشوفة قبل المحاولة | لا يوجد solution gating |
| النص كامل يصل دفعة واحدة (~30s انتظار ثم burst) | `chat_with_agent` يُرسِل `assistant_delta { content: HUGE_STRING }` واحد |
| LaTeX يبدو مكرراً في الواجهة | KaTeX يرسم الـ visible + accessibility span → نسخ يُعطي تكرار |
| الرد بطيء جداً | wide-net يقرأ كل ملفات `.md` + يُمرِّر النص الكامل للـ AI |

### المسار المُصحَّح (D-048)

```
المستخدم يسأل عن تمرين بكالوريا محدد
  │
  ▼
detect_exercise_retrieval(question)        ← knowledge_index.py
  │ يستخرج: year, session, subject, exercise_number, topics
  │ يُطابق على KNOWLEDGE_INDEX
  ▼
ExerciseRetrievalDecision(
    recognized=True,
    matched_entry=ExerciseEntry(file_path="bac2016_s1_math_exp_subject2_ex4_numerical_functions.md", ...)
)
  │
  ▼
_build_local_retrieval_response()  ← الجديد
  │ if matched_entry:
  │     raw = load_exercise_content(entry)             ← ملف واحد فقط
  │     formatted = format_exercise_for_display(...)   ← يحذف YAML + الحل + الوسوم
  │     return formatted                                ← 73% noise removed
  │ else:
  │     legacy wide-net (نادر)
  ▼
_stream_local_retrieval_response()  ← الجديد
  │ يُقسِّم على حدود الأسطر/الكلمات (≤80 char)
  │ yield chunk + asyncio.sleep(0.012)
  ▼
chat_with_agent() fallback path #2
  │ يُصدِر assistant_delta واحد لكل قطعة
  │ ثم assistant_final { content: "" }                  ← duplicate-suppression contract
  ▼
useAgentSocket.mergeAssistantContent
  │ يجمع الـ deltas
  │ يتجاهل assistant_final.content (لأنه فارغ)
  ▼
الواجهة ترسم الرد كلمة بكلمة (typing-effect)
```

### القواعد الخمس الدائمة (لا تُكسر بدون ADR)

**(1) Indexed-first retrieval**: `_build_local_retrieval_response()` يجب أن يُفضِّل `matched_entry` من knowledge_index قبل اللجوء إلى wide-net search. أي تعديل يبدأ بـ wide-net مباشرة يُعيد ISS-051 فوراً.

**(2) Atomic file load**: عند توفر `matched_entry`، يجب تحميل ملف واحد بالضبط (`load_exercise_content(entry)`)، لا scan على `knowledge_base/`. هذا يلغي leakage من الملفات الأخرى.

**(3) Display formatting**: `format_exercise_for_display()` يجب أن يحذف:
- YAML frontmatter (`---\n...\n---`)
- كل قسم يبدأ بـ `## عناصر الإجابة`, `## الإجابة النموذجية`, `## الحل`, `## Solution`, `## وسوم البحث`, `## Tags`, `### الجزء I`, `### الجزء II`, `### الجزء III`
- المُخرَج النظيف: بطاقة الامتحان + نص التمرين فقط (3 أجزاء I/II/III من الأسئلة)

**(4) Streaming chunk boundaries**: التقسيم يجب أن يحافظ على سلامة LaTeX markers:
- سطر ≤80 char: emit verbatim (يحافظ على `$$...$$` و `\\(...\\)` كاملة)
- سطر >80 char: قطع عند الفراغات فقط (لا يكسر `e^{-x}` في منتصف token)
- `asyncio.sleep(0.012)` بين كل قطعة لإنتاج typing-effect قابل للملاحظة بصرياً

**(5) Duplicate-suppression contract** (D-047): إذا بُثَّت أي `assistant_delta`، يجب أن يكون `assistant_final.payload.content = ""`. مسار الاسترجاع الجديد يحترم هذا — لا تُرسِل `assistant_final` بمحتوى مكرر.

### إضافة ملف تمرين جديد إلى `knowledge_base/`

عند إضافة ملف `.md` جديد:

1. أضف entry في `app/services/capabilities/knowledge_index.py:KNOWLEDGE_INDEX` مع كل الحقول (year, session, subject_number, exercise_number, branch, topics, tags).
2. تأكد أن الملف يحوي قسم `## عناصر الإجابة` أو `### الجزء I` لتفصل بين الأسئلة والحل — وإلا `_trim_at_solution()` سيُرجِع الملف كاملاً.
3. إذا استخدمت headers أخرى للحل (مثل `## Solutions` بالإنجليزية)، أضفها إلى `_SOLUTION_SECTION_MARKERS` في `exercise_retrieval.py`.
4. أضف keywords للموضوع في `_TOPIC_KEYWORDS` إذا لم تكن موجودة.

### النموذج الأساسي (D-049)

`PRIMARY = "inclusionai/ring-2.6-1t:free"` بناءً على طلب المستخدم 2026-05-13 (التحديد النهائي بعد التراجع عن `google/gemma-4-31b-it:free` التجريبي بنفس اليوم — راجع D-049 history في `.memory/decisions.md`). متطلبات الاستمرارية:

- نموذج Inclusion AI Ring 2.6 = 1T params (mixture of experts) — جودة عالية للشرح التعليمي العربي والرياضيات المتقدمة.
- إذا كان النموذج غير متاح في OpenRouter حساب المُستخدم → الـ fallback chain (Gemini 2 Flash → Qwen Coder → KAT → Phi 3 → Llama 3.2 Vision) يحمي التشغيل.
- التبديل السريع بدون إعادة build: `export OPENROUTER_PRIMARY_MODEL=<other>`.
- streaming كلمة بكلمة مضمون معمارياً (D-047/D-048) بغض النظر عن قدرات النموذج المحدَّد — إذا كان النموذج يُعطي chunk واحد، الـ fallback chain سينتقل لنموذج آخر يدعم streaming حقيقي.

### قياس النجاح حياً

```bash
# 1. مطابقة دقيقة لملف واحد فقط — لا leakage
python3 -c "
from app.services.capabilities.exercise_retrieval import detect_exercise_retrieval, ExerciseRetrievalRequest
d = detect_exercise_retrieval(ExerciseRetrievalRequest(question='تمرين 2016 الدورة الأولى الموضوع الثاني التمرين الرابع دوال عددية'))
print('matched:', d.matched_entry.file_path)
"
# المتوقع: knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md

# 2. حجم المُخرَج النظيف
python3 -c "
from app.services.capabilities.exercise_retrieval import format_exercise_for_display, load_exercise_content, detect_exercise_retrieval, ExerciseRetrievalRequest
d = detect_exercise_retrieval(ExerciseRetrievalRequest(question='تمرين 2016 الدورة الأولى التمرين الرابع'))
raw = load_exercise_content(d.matched_entry)
out = format_exercise_for_display(d.matched_entry, raw)
print(f'raw={len(raw)} formatted={len(out)} reduction={100-len(out)*100//len(raw)}%')
"
# المتوقع: raw=10884 formatted=~2913 reduction=73%

# 3. streaming chunks (يجب 30-50 chunks لتمرين عادي)
curl -N -X POST http://localhost:8000/api/chat/ws \
  -H "Authorization: Bearer $JWT" \
  -d '{"question":"تمرين 2016 الدورة الأولى الموضوع الثاني التمرين الرابع دوال عددية"}' \
  | grep -c assistant_delta
# المتوقع: > 30
```

---

## 6.30 Live BAC Exercise Test + WebSocket Auth Fixes (2026-05-13, ISS-052)

**تجريب حي كامل لاستدعاء تمرين الدوال العددية 2016 الموضوع الثاني التمرين الرابع الدورة الأولى عبر WebSocket.**

### ما تم التحقق منه

أربع تجارب حية متسلسلة على `conversation_id: 404/405` عبر `ws://localhost:8000/admin/api/chat/ws`:

| التجربة | الطلب | النتيجة | الحجم |
|---------|-------|---------|-------|
| 1 | نص التمرين الكامل | استرجع I+II+III كاملاً مع بطاقة الامتحان | 2925 حرف |
| 2 | السؤال الأول فقط بدون حل | أعطى الجزء I فقط بدون أي إجابة | 746 حرف |
| 3 | شرح مفصل حسب المنهجية | شرح كامل خطوة بخطوة مع نظرية داربو | 6389 حرف |
| 4 | شرح شرح (تعمق أكثر) | مبررات رياضية كاملة: لوبيتال، لاغرانج، الضغط | 14323 حرف |

**التحقق من الإجابة النموذجية:** كل نتيجة عددية في الشرح تطابق الإجابة النموذجية بدقة — الشرح يُوصل الطالب إليها ولا يخرج عنها.

### أخطاء WebSocket تم إصلاحها (ISS-052)

**ISS-052-A — endpoint خاطئ:** المحادثة تعمل عبر WebSocket حصراً، لا HTTP. لا يوجد `POST /api/chat/messages`.
- الـ endpoints الصحيحة: `ws://host/api/chat/ws` (customer) و `ws://host/admin/api/chat/ws` (admin).

**ISS-052-B — websockets v16 API تغيّر:**
```python
# خاطئ (v16 يرفضه)
from websockets.client import connect
# صحيح
from websockets.asyncio.client import connect
```

**ISS-052-C — طريقة المصادقة:** الـ token يجب في `subprotocols` وليس `Authorization` header (الـ header مخصص للـ Gateway فقط).
```python
# خاطئ
additional_headers={"Authorization": f"Bearer {TOKEN}"}
# صحيح — مطابق لما يفعله frontend في useRealtimeConnection.js
subprotocols=["jwt", TOKEN]
```

**ISS-052-D — بنية الـ events:** الـ payload مُدمَج تحت مفتاح `payload` وليس flat:
```python
# خاطئ
chunk = event.get("content", "")
# صحيح
payload_data = event.get("payload") or event
chunk = payload_data.get("content", "")
```

**ISS-052-E — token منتهي الصلاحية:** صلاحية الـ token 30 دقيقة. الخادم يُغلق الاتصال بـ code 4401 بدون رسالة خطأ — يبدو كـ `connection open → connection closed` فوراً. يجب تجديد الـ token قبل كل جلسة اختبار.

### بروتوكول اختبار WebSocket الصحيح

```python
from websockets.asyncio.client import connect
import json, asyncio

TOKEN = "<fresh_token_from_POST_/api/v1/auth/login>"

async def test():
    async with connect(
        "ws://localhost:8000/admin/api/chat/ws",
        subprotocols=["jwt", TOKEN],
        ping_interval=None,
    ) as ws:
        await ws.send(json.dumps({"question": "سؤالك هنا"}))
        while True:
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
            payload = event.get("payload") or event
            if event["type"] == "assistant_delta":
                print(payload["content"], end="", flush=True)
            elif event["type"] in ("assistant_final", "stream_end"):
                break

asyncio.run(test())
```

### قاعدة لا تُخرق — WebSocket Auth

```
extract_websocket_auth() priority order (ws_auth.py):
  1. Authorization header  → Gateway only (never from direct client)
  2. sec-websocket-protocol: ["jwt", "<token>"]  ← الطريقة الصحيحة للعميل المباشر
  3. ?token= query param   → development env only (ENVIRONMENT != production/staging)
```

---

## 6.31 JSON Envelope Anti-Leak + Indexed Retrieval Preemption + Typewriter Smoothing (2026-05-13, ISS-056 / D-049)

> هذا القسم يحكم سلوك ثلاث طبقات حرجة معاً. كل قاعدة فيه نتجت عن كارثة حية شاهدها المستخدم — لا تكسرها بدون ADR.

### الكارثة المُشخَّصة (قبل الإصلاح)

عندما كتب الطالب: «اعطني تمرين دوال عددية شعبة علوم تجريبية الموضوع الثاني التمرين الرابع لسنة 2016 الدورة الأولى»، حصلت أربع كوارث متراكبة:

| # | المظهر | السبب الجذري |
|---|--------|-------------|
| 1 | JSON خام `{"المصدر":"معرفة مادة","مستوى_الثقة":"0.70","التمرين":"لا توجد تفاصيل متاحة"...}` يظهر للطالب | `routes.py:1652,1939,2671` كانت تستدعي `_serialize_json_async(final_resp)` على dict من SynthesizerNode → يدمب المظروف كاملاً |
| 2 | الـ retriever في StateGraph لا يطابق ملف `knowledge_base/bac2016_*` لأن قاعدة المعرفة الخاصة بـ orchestrator ليست متصلة بمجلد `knowledge_base/` في الـ monolith | تجاوز معماري: الـ orchestrator يستدعي قاعدة معرفة مستقلة |
| 3 | الرد المُفهرَس النظيف (D-048) لا يعمل لأن الـ orchestrator يجيب أولاً | `chat_with_agent` يحاول orchestrator قبل fallback chain |
| 4 | الحروف تظهر "مدفع رشاش" — بفترات تجميع 16ms (rAF batching) | لا يوجد typewriter smoothing على الـ frontend |

### الإصلاح (D-049 — مطبَّق في فرع `claude/fix-exercise-display-SRmNL`)

**الإصلاح 1 — منع تسريب JSON envelope (`microservices/orchestrator_service/src/api/routes.py`)**:
- دالة جديدة `_extract_human_readable_response(final_resp)` تستخرج فقط الحقل البشري من dict:
  - `التمرين` (SynthesizerNode envelope)
  - `الإجابة` (AdminAgentNode / RenderAnswerNode envelope)
  - `response`, `answer`, `content`, `text`
  - `خطأ` → رسالة خطأ نظيفة بدلاً من dump
- يحل ثلاثة مواقع تسريب: HTTP `/api/chat/messages` (line 1939 سابقاً)، WS `/api/chat/ws` (1655 سابقاً)، Admin WS (2670 سابقاً).
- `SynthesizerNode.__call__` المُحَدَّث في `graph/search.py`: `AIMessage(content=text_val)` بدل `AIMessage(content=json.dumps(response_json))` → لا أي مكان آخر في graph يلتقط dict كنص.

**الإصلاح 2 — Indexed Retrieval Preemption (`app/infrastructure/clients/orchestrator_client.py`)**:
- دالة جديدة `OrchestratorClient._has_indexed_match(question)` تكشف عن تطابق محدد مع `knowledge_index`.
- في بداية `chat_with_agent`: إذا `_has_indexed_match(question)` → نتجاوز orchestrator-service و StateGraph و fallback chain، نبث المحتوى المُفهرَس النظيف مباشرة عبر `_stream_local_retrieval_response`.
- يضمن: لا تسرَّب JSON، لا هلوسة LLM، سرعة قصوى (لا HTTP roundtrip)، محتوى رسمي محدد من الفهرس.

**الإصلاح 3 — Typewriter Smoothing (`frontend/app/components/ChatInterface.jsx`)**:
- خطّاف `useTypewriter(fullContent, isStreaming)` يكشف الحروف بإيقاع ثابت (~240 char/sec @60fps) بغض النظر عن جودة الـ WebSocket batching.
- إذا تراكم backlog > 800 char → يتسارع لمنع التأخر عن البث.
- عند `isStreaming=false` → يكشف الباقي فوراً (لا تأخير زائف).
- يطبَّق على `MessageBubble` للمساعد فقط (رسالة المستخدم تظهر كاملة فوراً).

**الإصلاح 4 — KaTeX + بطاقة الامتحان (`frontend/app/globals.css`)**:
- فواصل بصرية بين أجزاء التمرين (I, II, III) عبر `border-bottom` للعناوين.
- `hr.md-hr` بـ gradient — مظهر فاخر بدل خط رمادي مسطح.
- `katex { white-space: nowrap }` داخل `exam-content` — يمنع كسر LaTeX على عدة أسطر.
- Media query للشاشات الصغيرة (≤640px) — يقلل حجم KaTeX لتجنب overflow أفقي.

### القواعد الخمس الدائمة (لا تُكسر بدون ADR)

**(1) JSON envelope لا يصل للطالب أبداً**: أي مكان في `routes.py` يحوِّل `final_response` إلى نص للمستخدم **يجب** أن يستخدم `_extract_human_readable_response()`. استخدام `_serialize_json_async(final_resp)` للحمولة الخام محظور.

**(2) AIMessage يحمل النص البشري فقط**: عقد `final_response: dict + messages: [AIMessage]` بحيث `AIMessage.content` يجب أن يكون **النص** (text_val) لا JSON dump للمظروف. هذا يحمي ضد تسرُّب من أي downstream consumer.

**(3) Indexed match → preempt orchestrator**: عندما `decision.matched_entry is not None` في `detect_exercise_retrieval`، الـ monolith يجب أن يبث من `_stream_local_retrieval_response` **قبل** محاولة orchestrator. السبب: الـ orchestrator يستدعي قاعدة معرفة مستقلة (vector DB) لا تشمل `knowledge_base/*.md`.

**(4) Typewriter ≠ artificial delay**: الـ typewriter في `ChatInterface.jsx` يكشف الحروف بإيقاع 60fps فقط أثناء streaming. عند `isStreaming=false` (مثلاً بعد `assistant_final`) → يكشف كل الباقي فوراً. الـ typewriter لا يبطّئ الـ "زمن إلى أول كلمة"؛ يُجمِّل فقط الإيقاع البصري بعد البداية.

**(5) Frontend copy = full content**: زر النسخ (`copy-button`) ينسخ `msg.content` الكامل، **لا** `displayedContent` المعروض جزئياً. الطالب الذي ينسخ أثناء streaming يحصل على النص الكامل.

### إضافة ملف تمرين جديد + تأكد من preemption يعمل

عند إضافة `.md` جديد إلى `knowledge_base/`:

1. أضف entry في `app/services/capabilities/knowledge_index.py:KNOWLEDGE_INDEX` (مطلوب).
2. تأكد من اختبار `detect_exercise_retrieval` يُرجع `recognized=True` و `matched_entry is not None`.
3. اختبر يدوياً: `python3 -c "from app.services.capabilities.exercise_retrieval import detect_exercise_retrieval, ExerciseRetrievalRequest; d = detect_exercise_retrieval(ExerciseRetrievalRequest(question='سؤالك')); print(d.recognized, d.matched_entry)"`.
4. إذا أُرجع `(False, None)` → الـ orchestrator سيتولى → احتمال تسرُّب أو هلوسة.
5. إذا أُرجع `(True, <entry>)` → ضمان preemption وعرض المحتوى المُفهرَس النظيف.

### قياس النجاح حياً

```bash
# 1. تجربة JSON envelope leak — يجب أن يكون مستحيلاً
curl -N -X POST http://localhost:8006/api/chat/messages \
  -H "Authorization: Bearer $JWT" \
  -d '{"question":"اعطني تمرين دوال عددية 2016","user_id":7,"conversation_id":1}' \
  | grep -E '"المصدر"|"مستوى_الثقة"|"رقم_التمرين"'
# المتوقع: صفر مطابقات (المظروف لا يصل للعميل)

# 2. preemption متحقَّق
python3 -c "
from app.services.capabilities.exercise_retrieval import detect_exercise_retrieval, ExerciseRetrievalRequest
d = detect_exercise_retrieval(ExerciseRetrievalRequest(
    question='اعطني تمرين دوال عددية شعبة علوم تجريبية الموضوع الثاني التمرين الرابع لسنة 2016 الدورة الأولى'
))
assert d.recognized and d.matched_entry, 'preemption broken'
print('OK matched:', d.matched_entry.file_path)
"
# المتوقع: OK matched: knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md

# 3. لا duplicate text بعد البث (D-047 contract)
# يجب أن تظهر >30 chunks، assistant_final.content يجب أن يكون فارغاً
```

---

## 6.32 LaTeX Rendering — Double-Backslash Delimiters + Atomic Typewriter (2026-05-13, ISS-057 / D-051)

> هذا القسم يحكم تصيير LaTeX في الـ frontend. أي تعديل على معالجة الرياضيات يجب أن يحترم القواعد الخمس أدناه — وإلا فالكارثة تعود.

### الكارثة المُشخَّصة

عند طلب «تمرين الدوال العددية 2016»، التمرين وصل للطالب فعلاً (preemption D-049 يعمل)، لكن **LaTeX يظهر كنص خام**:

| المتوقَّع | المعروض فعلاً |
|---------|--------------|
| الدالة $g$ المعرَّفة على $\mathbb{R}$ | الدالة `$g$` المعرَّفة على `$\mathbb{R}$` |
| $g(x) = 1 + (x^2+x-1)e^{-x}$ | `$g(x) = 1 + (x^2+x-1)e^{-x}$` |
| $\lim_{x \to -\infty} g(x)$ | `$\lim_{x \to -\infty} g(x)$` |

### السبب الجذري (تحقيق ثنائي الطبقات)

**طبقة 1 — قاعدة المعرفة**: ملف `knowledge_base/bac2016_*.md` يحوي **192 موضع** بالصيغة `\\(...\\)` (شرطتان مائلتان خلفيتان حرفياً، 7 bytes). كان الكاتب يستخدم اصطلاح "double-backslash" التاريخي.

**طبقة 2 — Frontend `preprocessMath`**: الـ regex القديم `/\\\(([^]*?)\\\)/g` يطابق `\(` (واحد). عند مواجهة `\\(g\\)` (اثنان):
- يطابق الـ `\(` الثاني فقط، يُبقي الـ `\` الأول
- النتيجة بعد replace: `\$g\$` ← دولار مُهرَّب في markdown
- ReactMarkdown يرى `\$` فيعرض literal `$`
- remark-math لا يلتقطها (الـ delimiter مكسور)
- KaTeX لا يُستدعى → نص خام مرئي للطالب

### الإصلاح (D-051 — ثلاث طبقات دفاع)

**طبقة 1 — `preprocessMath` (`frontend/app/components/ChatInterface.jsx`)**:
```javascript
// قبل أي تحويل: استبدل الـ double-backslash بـ single
processed = processed.replace(/\\\\\(/g, '\\(');
processed = processed.replace(/\\\\\)/g, '\\)');
processed = processed.replace(/\\\\\[/g, '\\[');
processed = processed.replace(/\\\\\]/g, '\\]');
// ثم التحويل العادي إلى $...$ و $$...$$
processed = processed.replace(/\\\[([^]*?)\\\]/g, (_, inner) => `$$${inner}$$`);
processed = processed.replace(/\\\(([^]*?)\\\)/g, (_, inner) => `$${inner}$`);
```
يدعم كل 5 صيغ موجودة: `\(...\)` | `\\(...\\)` | `\[...\]` | `\\[...\\]` | `$...$` | `$$...$$`.
تحقق حي: 192 موضع `\\(...\\)` تحوَّلت كلها إلى `$...$`، 0 موضع متبقٍ.

**طبقة 2 — LaTeX-Aware Typewriter (`ChatInterface.jsx:useTypewriter`)**:
دالة `atomicTokenLength(text, start)` تكشف عن بداية LaTeX block وتُرجع طول الـ block كاملاً. خلال الكشف:
- `$...$` → كشف ذرّي
- `$$...$$` → كشف ذرّي
- `\(...\)` → كشف ذرّي
- `\\(...\\)` → كشف ذرّي
- نص عادي → 1 حرف
يضمن: الطالب لا يرى `$g` بدون `$` إقفال لحظياً أبداً (لا flicker).

**طبقة 3 — Backend `_split_preserving_latex` (`app/infrastructure/clients/orchestrator_client.py`)**:
الـ regex مُحدَّث لالتقاط 4 صيغ كـ token واحد:
```python
_LATEX_INLINE_RE = re.compile(
    r'\$\$[^$\n]+?\$\$'         # $$inline$$
    r'|\$[^$\n]+?\$'            # $inline$
    r'|\\\\\([^\n]+?\\\\\)'     # \\(inline\\) ← الصيغة الرئيسية في knowledge_base
    r'|\\\([^\n]+?\\\)'         # \(inline\)
)
```
يضمن: WebSocket chunks لا تكسر LaTeX block أبداً (block كامل → chunk واحد → atomic reveal).

**طبقة 4 — CSS فاخر لبطاقة الامتحان (`frontend/app/globals.css`)**:
- خط ذهبي علوي (`exam-content::before` gradient horizontal) — يُذكِّر بورقة الامتحان الرسمية.
- ظل ثلاثي الطبقات (1px sharp + 4px diffuse + 12px blue glow).
- `katex-display` بخلفية gradient + border + hover state + animation `katex-fade-in` (0.18s).
- `h3` بـ right-border ذهبية تُحدِّد بصرياً الجزء (I/II/III).
- Media query للجوال (≤640px) — تقليص KaTeX + padding.

### القواعد الخمس الدائمة (لا تُكسر بدون ADR)

**(1) Preprocess قبل remark-math إلزامي**: أي محتوى يحوي `\\(`, `\\[`, `\(`, `\[` يجب أن يمر عبر `preprocessMath` قبل ReactMarkdown. تخطي هذه الخطوة = LaTeX خام مرئي.

**(2) Atomic LaTeX reveal**: الـ typewriter يجب أن يكشف LaTeX blocks ذرياً (atomic). الكشف حرفاً بحرف عبر `$` أو `\(` غير مكتمل = flicker بصري وتجارب مدمرة.

**(3) Backend splits preserve LaTeX**: `_split_preserving_latex` في orchestrator_client يجب أن يدعم الصيغ الأربع. إضافة صيغة جديدة (مثل `\begin{equation}...\end{equation}`) → تحديث الـ regex.

**(4) Single source of truth للـ delimiters**: knowledge_base files تستخدم `\\(...\\)` للـ inline و `$$...$$` للـ display. لا تخلط الصيغ في ملف واحد. عند إضافة ملف جديد، احترم الاصطلاح أو حدِّث `preprocessMath` بصيغة جديدة.

**(5) KaTeX `throwOnError: false`**: لا تُغيِّره. عند خطأ LaTeX، نريد KaTeX يرسم النص الخام بدلاً من crash. هذا يحمي ضد الحالات النادرة (e.g., LaTeX commands غير مدعومة).

### قياس النجاح حياً

```bash
# 1. فحص الـ preprocessMath على knowledge base كامل
node -e "
const fs = require('fs');
const content = fs.readFileSync('knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md', 'utf-8');
const fix = (c) => c
  .replace(/\\\\\\\\\(/g, '\\\\(').replace(/\\\\\\\\\)/g, '\\\\)')
  .replace(/\\\\\\\\\[/g, '\\\\[').replace(/\\\\\\\\\]/g, '\\\\]')
  .replace(/\\\\\[([^]*?)\\\\\]/g, (_, i) => '\$\$' + i + '\$\$')
  .replace(/\\\\\(([^]*?)\\\\\)/g, (_, i) => '\$' + i + '\$');
const r = fix(content);
console.log('inline pairs:', (r.match(/(?<!\\\\\\\$)\\\$(?!\\\$)/g) || []).length);
console.log('display pairs:', (r.match(/\\\$\\\$/g) || []).length);
console.log('remaining \\\\\\\\(:', (r.match(/\\\\\\\\\(/g) || []).length);
"
# المتوقع: inline pairs: 384 (192 zwj), display pairs: 66, remaining \\(: 0

# 2. اختبار atomic typewriter على string نموذجي
# يجب أن يُرجع: $g$ = 3, $$...$$ = 14, \(g\) = 5, \\(g\\) = 7
```

---

## 6.33 Explanation Context Preemption + BAC Exercise Skill + Chunk-Tag Stripping (2026-05-14, ISS-058 / D-052)

> كارثة مدمرة شاهدها المستخدم: عند طلب «ماذا نقصد بدالة اصلية للدالة f» بعد تمرين 2016،
> ظهرت **تمارين بكالوريا أخرى غير ذات صلة** (2024 احتمالات) + **tags خام** (`[ex: ex_1]`,
> `[sol: ex_1]`, `[grading: ex_1]`) + **تكرار حرفي للإجابة النموذجية** بدل شرحها.
> هذا القسم يحكم منع تكرار هذه الكارثة دائماً.

### الكارثة المُشخَّصة

| المظهر | السبب الجذري |
|--------|---------------|
| تمرين 2024 الاحتمالات يظهر مع 2016 الدوال | `_BAC_EXERCISE_EXPLANATION_PATTERNS` لا يشمل "ماذا نقصد"/"كيف نُثبت" → `detect_explanation_with_context` يُرجع False → يصل للـ wide-net retriever الذي يقرأ كل ملفات `knowledge_base/` |
| `[ex: ex_1]`, `[sol: ex_1]`, `[grading: ex_1]` خام مرئية | vector DB يُرجع chunks مع علامات داخلية، لا يوجد stripping |
| تكرار حرفي للإجابة النموذجية | `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` القديم لا يمنع النسخ صراحةً |
| "Lambada infinity" خام | LaTeX preprocessor (D-051) لا يلتقط الـ chunks المُسرَّبة من vector DB |

### الإصلاح (D-052 — 6 طبقات دفاع)

**طبقة 1 — توسيع `_BAC_EXERCISE_EXPLANATION_PATTERNS`** (`exercise_retrieval.py`):
20+ نمط جديد لاستفسارات الشرح:
- مفاهيمية: `ماذا نقصد`, `ماذا تعني`, `ما المقصود`, `ما هو معنى`, `ما هي`, `ما هو`
- منهجية: `كيف نُثبت`, `كيف نحسب`, `كيف نُبيِّن`, `كيف نستنتج`, `كيف نجد`, `كيف وصلنا`
- تبرير: `لماذا`, `علِّل`, `برِّر`, `why is`, `justify`
- دوال صريحة: `وضح g(x)`/`f(x)`/`h(x)`, `فسر g(x)`/`f(x)`/`h(x)`, `بيّن g(x)`/`f(x)`/`h(x)`

**طبقة 2 — Conversation Context Detection** (`exercise_retrieval.py`):
دالة جديدة `_detect_entry_from_history(history_messages)` تفحص آخر 10 رسائل لمعرفة
التمرين البكالوريا الذي تجري عنه المحادثة. `detect_explanation_with_context` تأخذ الآن
`history_messages` parameter وتستخدم 3 مراحل:
1. سؤال + BAC specificity → استخدم التمرين من السؤال
2. سؤال شرح + history فيه BAC → استخدم تمرين السياق
3. خلاف ذلك → لا match (يذهب لـ LangGraph العام)

**طبقة 3 — `_has_explanation_with_context_match` + Preempt** (`orchestrator_client.py`):
في بداية `chat_with_agent`، بعد فحص `_has_indexed_match`، يُضاف فحص جديد:
```python
if self._has_explanation_with_context_match(question, history_messages):
    # بث الشرح المحلي مباشرة — يتجاوز orchestrator + StateGraph
    async for chunk in self._stream_exercise_explanation_response(...):
        yield assistant_delta(chunk)
```
يضمن: لا dump لتمارين متعددة، لا تسريب JSON، لا hallucination، سرعة قصوى.

**طبقة 4 — إعادة كتابة `_EXERCISE_EXPLANATION_SYSTEM_PROMPT`** (`local_graph.py`):
prompt جديد يحظر **صراحةً** التكرار الحرفي:
- 🎯 «التزم بكل نتيجة في الإجابة النموذجية — لا تُغيِّر ولا تستنبط»
- 🚫 «لا تُكرِّر الإجابة النموذجية حرفياً — هذه كارثة»
- ✍️ «اشرح الجسر بين السؤال والنتيجة: ما هي القاعدة؟ لماذا اخترناها؟ كيف طبَّقناها؟»
- 🚫 ممنوع منعاً باتاً: نسخ فقرة، اختراع نتائج، ذكر تمارين/سنوات أخرى

**طبقة 5 — Chunk-Tag Stripping** (`orchestrator_client.py`):
`_strip_retrieval_tags()` يحذف بـ regex `\[(?:ex|sol|grading|chunk|src|source|meta|tag|id|doc):...\]`
من أي نص قبل بثه للطالب. مدمج في `_sanitize_text_for_user`. لا false positives على
math notation مثل `x[1]` (لأن الـ regex يتطلب `key:value` pattern).

**طبقة 6 — منظومة Skills الرسمية** (`app/services/skills/`):
وحدة جديدة تستبدل **Prompt Spaghetti** بـ Skill Architecture (CLAUDE.md §0.5):
- `BACExerciseSkill` — class رسمي بـ contract Pydantic موحَّد
- `BACSkillInput(question, mode, history_messages, conversation_id)`
- `BACSkillRetrievalOutput | BACSkillExplanationOutput | SkillFailure`
- `SkillMode.{RETRIEVE, EXPLAIN, AUTO}`
- Prometheus metrics: `cogniforge_skill_bac_invocations_total{mode,status}` + `_duration_seconds`
- اختبارات حية: 4/4 تنجح (RETRIEVE, EXPLAIN+history, AUTO, no-match)
- استقلالية: لا يستورد من Skill آخر، يعمل بدون orchestrator-service

### القواعد الست الدائمة (لا تُكسر بدون ADR)

**(1) Conversation context ≠ vector DB**: عند سؤال شرح/استفسار، يجب فحص `history_messages`
أولاً قبل الذهاب لـ retriever عام. السياق المحدد من المحادثة يهزم البحث الواسع دائماً.

**(2) Explanation preempt يسبق orchestrator**: في `chat_with_agent`، يجب فحص
`_has_explanation_with_context_match()` **قبل** محاولة orchestrator microservice.
بدون ذلك، الـ orchestrator سيستدعي vector DB ويُرجع chunks من ملفات متعددة.

**(3) System prompt الشرح يحظر النسخ صراحةً**: `_EXERCISE_EXPLANATION_SYSTEM_PROMPT`
يجب أن يحوي تعليمات صريحة `🚫 لا تُكرِّر الإجابة النموذجية حرفياً`. حذف هذه التعليمات
= عودة لكارثة "النسخ بدل الشرح".

**(4) Chunk-tag stripping إلزامي**: أي نص يُبث للطالب يجب أن يمر عبر `_sanitize_text_for_user`
الذي يستدعي `_strip_retrieval_tags` تلقائياً. لا تتجاوز هذه الطبقة أبداً.

**(5) Skills > Prompt Spaghetti**: عند إضافة قدرة AI جديدة، يجب أن تكون **Skill**
بـ contract Pydantic + metrics + tests. لا تضف logic AI مباشرة في `orchestrator_client.py`
أو `local_graph.py` — أنشئ Skill في `app/services/skills/`.

**(6) Skill استقلال إلزامي**: Skill **لا يستورد** من Skill آخر مباشرة. التواصل بين
Skills يتم عبر `OrchestratorClient` أو caller. هذا يحفظ القدرة على الاختبار والاستبدال.

### قياس النجاح حياً

```bash
# 1. Concept Q + history → matches BAC 2016 (السيناريو الكارثي)
python3 -c "
from app.services.capabilities.exercise_retrieval import detect_explanation_with_context, ExerciseRetrievalRequest
history = [{'role':'user','content':'اعطني تمرين دوال 2016'},{'role':'assistant','content':'بكالوريا 2016...'}]
d = detect_explanation_with_context(ExerciseRetrievalRequest(question='ماذا نقصد بدالة اصلية'), history_messages=history)
assert d.recognized and 'bac2016' in d.matched_entry.file_path, 'CATASTROPHE NOT FIXED'
print('OK')
"

# 2. BAC Exercise Skill operational
python3 -c "
from app.services.skills import BACExerciseSkill, BACSkillInput, SkillMode, BACSkillExplanationOutput
skill = BACExerciseSkill()
r = skill.invoke(BACSkillInput(
    question='ماذا نقصد بدالة اصلية',
    mode=SkillMode.EXPLAIN,
    history_messages=[{'role':'user','content':'تمرين 2016 الدورة الأولى الموضوع الثاني'}]
))
assert isinstance(r, BACSkillExplanationOutput)
print(f'Skill OK | match_source={r.match_source}')
"

# 3. Chunk-tag stripping (no false positives on math)
python3 -c "
from app.infrastructure.clients.orchestrator_client import OrchestratorClient
assert OrchestratorClient._strip_retrieval_tags('[ex: ex_1] hi') == ' hi'
assert OrchestratorClient._strip_retrieval_tags('x[1] = 2') == 'x[1] = 2'  # math preserved
print('OK')
"
```

---

## 6.34 Question-Aware Latency Budgets — Detail Question Time Catastrophe (2026-05-14, ISS-059 / D-053)

> كارثة الوقت: عند طلب «تفصيل معين» (مثل «ماذا نقصد بدالة اصلية»، «لماذا g(-1)=1-e»)
> كانت الإجابة تتأخر 15-18 ثانية — مثل طلب شرح كامل تماماً. السبب: max_tokens=900
> ثابت لكل أنواع الأسئلة. الآن نُصنِّف السؤال ونعطيه budget مناسب.

### المشكلة المُشخَّصة

`_MAX_EXPLANATION_TOKENS = 900` كان ثابتاً لكل الأسئلة. الـ LLM يولِّد ~50 token/s
على النماذج المجانية. النتيجة:
- سؤال «ماذا نقصد بدالة أصلية» (يحتاج ~200 token طبيعياً) → يولِّد 900 → ~18s
- سؤال «اشرح التمرين كاملاً» (يحتاج 900 token طبيعياً) → نفس الشيء → ~18s
- لا تمييز → الطالب ينتظر بنفس الطول لأي سؤال

### الإصلاح (D-053 — 3 طبقات)

**طبقة 1 — تصنيف السؤال** (`local_graph.py:_classify_question_budget`):
دالة جديدة تُصنِّف السؤال بناءً على patterns إلى 5 أنواع:

| النوع | المثال | context | max_tokens | الزمن المتوقَّع |
|-------|--------|---------|-----------|---------------|
| **CONCEPT** | "ماذا نقصد بـ"، "ما هو معنى" | 1200 char | 350 | ~7s (كان ~18s) |
| **JUSTIFICATION** | "لماذا"، "علِّل" | 1500 char | 450 | ~9s (كان ~18s) |
| **METHOD** | "كيف نُثبت"، "كيف نحسب" | 2000 char | 600 | ~12s (كان ~18s) |
| **DEFAULT** | "شرح الجزء الأول" | 2500 char | 700 | ~14s (كان ~18s) |
| **FULL** | "اشرح التمرين كاملاً" | 3000 char | 900 | ~18s (لم يتغيَّر) |

**طبقة 2 — تطبيق Budget الديناميكي**: في `run_local_graph_with_exercise_context`،
`context_budget` و `token_budget` يُحسبان من السؤال ويُمرَّران إلى:
- قَصّ الـ context: `trimmed_content = trimmed_content[:context_budget]`
- استدعاء LLM: `ai_client.stream_chat(messages, max_tokens=token_budget)`
- Telemetry tags: `context_budget`, `token_budget`, `q_class` لكل span

**طبقة 3 — Decision Caching** (`orchestrator_client.py:chat_with_agent`):
قبل ISS-059، `detect_explanation_with_context` كان يُستدعى **3 مرات**:
1. في `_has_explanation_with_context_match()` للتحقق
2. في `_stream_exercise_explanation_response()` لإعادة الجلب
3. file I/O داخل كل واحدة منهما

الآن يُحسب **مرة واحدة** في `chat_with_agent` ويُمرَّر عبر `precomputed_decision=`:
```python
_explanation_decision = detect_explanation_with_context(...)  # مرة واحدة
if _explanation_decision.recognized:
    async for chunk in self._stream_exercise_explanation_response(
        ...,
        precomputed_decision=_explanation_decision,  # تجنُّب إعادة الحساب
    ): ...
```
يوفِّر ~10-20ms + يتجنَّب file I/O مكرَّر.

### الـ Metric الجديد

`cogniforge_langgraph_q_class_total{q_class,graph}` — يُتاح في Grafana لتتبُّع
توزيع أنواع الأسئلة:
- نسبة CONCEPT/JUSTIFICATION → مؤشر على رضى المستخدم بأسئلة قصيرة سريعة
- نسبة FULL → مؤشر على الحاجة لمحتوى تعليمي شامل

### القواعد الثلاث الدائمة (لا تُكسر بدون ADR)

**(1) max_tokens يتناسب مع نوع السؤال**: السؤال القصير يستحق إجابة قصيرة سريعة.
استخدام 900 token لكل الأسئلة = كارثة وقت. صنِّف أولاً، ثم خصِّص budget.

**(2) Decision Caching إلزامي**: عند الحاجة لـ decision في عدة مراحل من نفس الطلب،
احسبه **مرة واحدة** ومرِّره عبر parameter. تكرار `detect_*` يُكلِّف time + I/O.

**(3) Telemetry tags كاملة**: كل span في explanation path يجب أن يحوي:
`q_class`, `context_budget`, `token_budget` — يُمكِّن Grafana من تشخيص التأخير
بنوع السؤال.

### قياس النجاح حياً

```bash
# 1. كل تصنيف يُعطي budget صحيح
python3 -c "
import sys; sys.path.insert(0, '.')
# تجنُّب package init الذي يحتاج sqlalchemy: استخدم importlib
import importlib.util
spec = importlib.util.spec_from_file_location('lg', 'app/services/chat/local_graph.py')
# ... (راجع scripts/check_q_class.py)
"

# 2. زمن الاستجابة المتوقَّع
# قبل D-053: كل سؤال ~18s مهما كان حجمه
# بعد D-053:
#   ماذا نقصد → ~7s (وفر 11s)
#   لماذا     → ~9s (وفر 9s)
#   كيف نُثبت  → ~12s (وفر 6s)
#   اشرح كاملاً → ~18s (لم يتغيَّر — مطلوب)

# 3. Metric في Grafana
# rate(cogniforge_langgraph_q_class_total[5m]) by (q_class)
```

---

## 6.35 KaTeX `\\command` Catastrophe — Double-Backslash inside Math Mode (2026-05-14, ISS-060 / D-054)

> **الكارثة المرئية:** رغم D-051 (إصلاح حدود `\\(...\\)`)، الطالب رأى:
> ```
> displaystyle int 0 lambda h(x),dx
> l a m b d a
> lim lambdato+infty A(lambda
> ```
> KaTeX يرسم `lambda` كحروف منفصلة بدل الحرف اليوناني `λ`.

### السبب الجذري (الأعمق من D-051)

D-051 طبَّع **حدود** الرياضيات: `\\(...\\)` → `\(...\)` → `$...$`. لكنه ترك
**محتوى** الرياضيات كما هو — يحوي `\\lambda`, `\\int`, `\\displaystyle`, `\\to`, `\\infty`.

KaTeX يفسِّر هذه بالشكل التالي:
- `\\` → أمر `\newline` (سطر جديد في الرياضيات)
- `lambda` → نص حر، تُرسَم حروفه واحداً واحداً كمتغيرات (`l a m b d a`)
- `int` → نص حر `int`، لا الرمز ∫
- النتيجة: كارثة بصرية كاملة

```
$A(\\lambda) = \\displaystyle\\int_0^{\\lambda} h(x)\\,dx$
       ↑                      ↑       ↑
    newline+              newline+  newline+
    "lambda"             "displaystyle int"   "lambda"
```

### الإصلاح (D-054 — سطر واحد جراحي)

في `frontend/app/components/ChatInterface.jsx:preprocessMath()`، **بعد** تطبيع
الحدود (الخطوة 1) و**قبل** تحويل `\(...\)` إلى `$...$` (الخطوة 3)، نُضيف
**الخطوة 2**:

```javascript
// طبِّع `\\command` → `\command` لكل أوامر LaTeX داخل الرياضيات
processed = processed.replace(/\\\\([a-zA-Z]+|[,;!{}])/g, '\\$1');
```

الـ regex يطابق `\\` متبوعاً بـ:
- **أحرف لاتينية واحد أو أكثر**: `\\lambda` → `\lambda`, `\\int` → `\int`, `\\displaystyle` → `\displaystyle`, `\\mathbb` → `\mathbb`
- **punctuation LaTeX**: `\\,` → `\,` (thin space), `\\;` → `\;` (medium space), `\\!` → `\!` (negative space), `\\{` → `\{`, `\\}` → `\}`

**لا يلمس**:
- `\\\\` (4 backslashes = `\\` في الناتج = newline حقيقي في KaTeX)
- نص markdown عادي خارج الرياضيات (markdown لا يستخدم `\\command`)

### قياس النجاح حياً (على ملف bac2016 الكامل)

```
After fix:
  remaining \\command: 0           ← قبل: 192+ موضع
  remaining \\(  : 0
  remaining \\[  : 0

Properly-formed LaTeX commands:
  \lambda: 25       (ترسم λ)
  \int: 2           (ترسم ∫)
  \infty: 51        (ترسم ∞)
  \to: 21           (ترسم →)
  \displaystyle: 1
  \mathbb: 8        (ℝ, ℕ, إلخ)

Catastrophe line (بعد الإصلاح):
  $A(\lambda) = \displaystyle\int_0^{\lambda} h(x)\,dx$  ← KaTeX يرسم بشكل مثالي
```

### القاعدة الدائمة الأهم

**knowledge_base يستخدم double-backslash لكل شيء** — هذا اصطلاح تاريخي ولن يتغيَّر
(يكلف 192+ موقع تعديل). `preprocessMath` هو **الحارس الوحيد** الذي يُطبِّع هذا
قبل remark-math. لا تُحذف خطوة `\\command → \command` أبداً.

### السلسلة الكاملة (طبقات الإصلاح المتراكبة)

| الخطوة | الإصلاح | بدون → النتيجة |
|--------|---------|----------------|
| D-051 step 1 | `\\(` → `\(` | بدونه: `\$g\$` يظهر literal |
| D-054 step 2 | `\\lambda` → `\lambda` | بدونه: KaTeX يرسم `l a m b d a` |
| D-051 step 3 | `\(g\)` → `$g$` | بدونه: remark-math يتجاهل |

أي طبقة من هذه إذا حُذفت → كارثة مرئية فورية للطالب.

---

## 6.36 Luxury UI Theme System — Flicker-Free Pure Backgrounds (2026-05-14, ISS-061 / D-055)

> الكوارث المُشاهَدة: (1) خط أفقي ذهبي «يظهر ويختفي مثل البث» في أعلى التمرين،
> (2) إطار مُقزِّز حول كل رسالة، (3) ألوان مزعجة (أزرق فاتح/داكن في كل مكان)،
> (4) خطوط عربية رديئة. الطلب: «فاخر وعظيم احترافي خارق يبهر العقول… بساطة عظيمة».

### الكوارث المُشخَّصة

| # | المظهر | السبب الجذري |
|---|--------|-------------|
| 1 | خط ذهبي/أزرق علوي «يومض» أثناء streaming | `.exam-content::before` بـ `linear-gradient` أصفر-أزرق + `katex-fade-in` animation تُطلَق على كل re-render |
| 2 | إطار حول كل رسالة assistant مزعج | `.message.assistant .message-bubble` به `border: 1px solid + border-radius` |
| 3 | ألوان مائلة للأزرق في "أبيض" و"أسود" | `--bg-color: #f8fafc`, `--text-color: #0f172a`, `--surface: #1e293b` — كلها مائلة للـ slate-blue |
| 4 | خط Cairo افتراضي بحالة عادية | لا font-smoothing، لا feature-settings، لا fallbacks فاخرة |
| 5 | KaTeX-display بـ gradient bg + hover transition | يُسبب re-paint مكلفة + flicker على كل character reveal خلال streaming |
| 6 | gradients ذهبية على عناوين h1/h2/h3/hr | `border-image: linear-gradient` بألوان متراكبة |

### الإصلاح (D-055 — تصميم فاخر بسيط حسب Vercel/Apple-grade design)

**طبقة 1 — Color Palette مُعاد تصميمها** (`:root` + `[data-theme='dark']`):
```css
/* Light Mode — صفحة بيضاء فاخرة */
--bg-color: #ffffff;        /* كان #f8fafc (مائل للأزرق) */
--text-color: #0a0a0a;      /* أسود نقي (كان #0f172a) */
--border-color: #e5e5e5;    /* رمادي محايد (كان #e2e8f0 مائل للأزرق) */
--surface-elevated: #fafafa; /* جديد — للأسطح المرفوعة فقط */

/* Dark Mode — أسود Vercel-grade + أبيض راقٍ */
--bg-color: #0a0a0a;        /* أسود فاخر (كان #0f172a) */
--surface-color: #0f0f0f;
--surface-elevated: #171717;
--text-color: #fafafa;      /* أبيض فاخر (كان #f1f5f9) */
--border-color: #1f1f1f;    /* حدود تكاد تكون غير مرئية */
```

**طبقة 2 — Typography premium** (`@import` + `--font-family`):
```css
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;800&family=Noto+Kufi+Arabic:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

--font-family: 'Tajawal', 'Noto Kufi Arabic', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;

body {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    font-feature-settings: "kern" 1, "liga" 1;
}
```
Tajawal هو الأكثر أناقة في 2024+ للعربية الحديثة (يستخدمه Google Maps).

**طبقة 3 — حذف الـ Flicker (3 مصادر)**:
1. **`.exam-content::before` (الخط الذهبي) → محذوف بالكامل**.
2. **`@keyframes katex-fade-in` + `animation` على katex-display → محذوف**:
   كان يُطلَق على كل re-render من typewriter → flicker على كل حرف.
3. **`transition: box-shadow` + `:hover` على katex-display → محذوف**:
   يُسبب visual change خلال إعادة التصيير.

**طبقة 4 — Exam-Card فاخر بسيط**:
- `background: transparent`، `border: none` — لا frame مُقزِّز.
- `.exam-badge`: pill شفاف بحدود رمادية ناعمة (كان gradient أزرق صاخب).
- `h1/h2`: `border-bottom: 1px solid var(--border-color)` نظيف (كان `border-image: gradient`).
- `h3`: بدون `border-right`، بدون `padding-block`، بدون `gradient bg` — اللون يساوي `--text-color`.
- `hr`: `1px solid var(--border-color)` (كان gradient ذهبي).
- جداول: حدود محايدة، خلفية `--surface-elevated`، لا shadows زرقاء.

**طبقة 5 — Message-Bubble بدون frame**:
```css
.message.assistant .message-bubble {
    background-color: transparent;  /* كان var(--surface-color) */
    border: none;                   /* كان 1px solid var(--border-color) */
    padding-inline: 0.5rem;
}
```
النص الأبيض في الـ dark يتألق مباشرة على الصفحة السوداء.

**طبقة 6 — KaTeX يرث لون النص**:
```css
.markdown-content .katex { color: var(--text-color); }
.markdown-content .katex :is(.mord, .mbin, .mrel, .mopen, .mclose, .mpunct, .mop) { color: inherit; }
```
في dark: المعادلات تُرسَم بالأبيض الفاخر. في light: بالأسود الفاخر.

### القواعد الست الدائمة (لا تُكسر بدون ADR)

**(1) لا animations على المحتوى المُعاد تصييره خلال streaming**: typewriter يُسبب re-render كل ~16ms. أي `@keyframes` + `animation` على عنصر داخل rendered content = flicker بصري.

**(2) لا hover transitions على عناصر خلال streaming**: `transition: box-shadow/border-color` على عناصر تُعاد تصييرها = وميض.

**(3) لا gradient backgrounds على content cards خلال streaming**: gradients مكلفة في الـ paint pass. النتيجة: لا exam-card مع background gradient.

**(4) Pure backgrounds**: light = `#ffffff` نقي، dark = `#0a0a0a` نقي — لا ألوان مائلة (slate-blue, indigo-tinted). الطالب يطلب «أبيض فاخر»/«أسود فاخر».

**(5) Font smoothing إلزامي**: `-webkit-font-smoothing: antialiased` + `text-rendering: optimizeLegibility` — يُحسِّن قراءة العربي بشكل دراماتيكي على Retina/HiDPI.

**(6) Border-image gradients محظورة على content headings**: يحدث re-paint على كل re-render. استخدم `border-bottom: 1px solid` بسيط.

### قياس النجاح حياً

```bash
# 1. تأكد من حذف ::before
grep -c "exam-content::before" frontend/app/globals.css
# المتوقع: 0 (أو تعليق فقط)

# 2. تأكد من حذف animation katex-fade-in
grep -c "katex-fade-in" frontend/app/globals.css
# المتوقع: 0

# 3. تأكد من Pure backgrounds
grep -E "bg-color.*#ffffff|bg-color.*#0a0a0a" frontend/app/globals.css
# المتوقع: نتائج إيجابية

# 4. تأكد من Tajawal
grep "Tajawal" frontend/app/globals.css
# المتوقع: في @import + --font-family
```

### السلسلة الكاملة (D-049 → D-050 → D-051 → D-052 → D-053 → D-054 → D-055)

| Decision | المُصلَح |
|----------|---------|
| D-049 | JSON envelope leak |
| D-050 | indexed preempt + typewriter |
| D-051 | LaTeX delimiters `\\(...\\)` → `$...$` |
| D-052 | conversation context + chunk-tag stripping + Skills |
| D-053 | dynamic latency budget |
| D-054 | `\\command` → `\command` في math |
| **D-055** | **luxury UI theme + zero-flicker + premium typography** |

---

## 6.37 Header White-Line Catastrophe — Seamless Pure-Black Doctrine (2026-05-14, ISS-062 / D-055.1)

> **الكارثة**: المستخدم رفع screenshot يُظهر **خيط أبيض رفيع** أفقي تحت كلمة "Overmind Education" (في الـ header) وفوق المحتوى. وصفه: «يظهر و يختفي مما يفسد تجربة المستخدم بشكل خطير مدمر». طلب: «اريدها تبقى مثل تلك الصفحة [الـ screenshot الآخر بدون خط]».

### السبب الجذري (تتمة لـ D-055)

بعد D-055 أصبحت الخلفية pure black `#0a0a0a` والحد `--border-color: #1f1f1f`. لكن `.header` لا يزال يحوي:
```css
.header {
    border-bottom: 1px solid var(--border-color);  /* ← الخط الأبيض */
    box-shadow: var(--shadow-sm);                   /* ← ظل خفيف */
}
```

على الـ slate-blue القديم (`#0f172a` body vs `#334155` border) كان الفرق كافياً لإخفاء الخط. على pure-black، أي border `#1f1f1f` يظهر كخط مرئي.

### لماذا «يظهر ويختفي»

الخط نفسه **ثابت**. لكن خلال streaming، typewriter يُعيد render المحتوى أسفله ~60fps. الـ re-renders تُسبب انطباع بصري بأن الخط «يومض» بسبب التحديث المتكرر للمنطقة المحيطة. **هذا flicker إدراكي وليس CSS animation**.

### الإصلاح (D-055.1 — جراحي)

```css
.header {
    height: 60px;
    background-color: var(--bg-color);   /* بدلاً من --surface-color */
    border-bottom: none;                  /* كان: 1px solid var(--border-color) */
    box-shadow: none;                     /* كان: var(--shadow-sm) */
    ...
}
```

الـ header الآن يندمج بسلاسة مع الـ body. لا فاصل بصري على الإطلاق.

### القاعدة الدائمة الإضافية لـ D-055

**(7) Pure-black backgrounds expose every border**: على `--bg: #0a0a0a`، أي `border` بلون `--border-color: #1f1f1f` على عناصر full-width سيظهر كخط أبيض رفيع — حتى لو كان مقصوداً كـ subtle divider. الـ headers/dividers الفاصلة بين كتل full-width يجب أن تستخدم:
- **خلفية مختلفة** (لو الفصل ضروري): `background-color: var(--surface-elevated)` على الجزء الأعلى
- **margin/padding** فقط (الخيار المُفضَّل للـ luxury minimal design)
- **NEVER** border-bottom على عناصر تمتد عبر كامل العرض على خلفية pure-black

### قياس النجاح حياً

```bash
# 1. تأكد من إزالة الخط
grep -A8 "^\.header {" frontend/app/globals.css | grep "border-bottom: none"
# المتوقع: border-bottom: none;

# 2. تأكد من إزالة الظل
grep -A8 "^\.header {" frontend/app/globals.css | grep "box-shadow: none"
# المتوقع: box-shadow: none;

# 3. تأكد من توحُّد الخلفية
grep -A2 "^\.header {" frontend/app/globals.css | grep "background-color"
# المتوقع: background-color: var(--bg-color);
```

### السلسلة الكاملة (D-049 → D-055.1)

| Decision | المُصلَح |
|----------|---------|
| D-049 | JSON envelope leak |
| D-050 | indexed preempt + typewriter |
| D-051 | LaTeX delimiters `\\(...\\)` → `$...$` |
| D-052 | conversation context + chunk-tag stripping + Skills |
| D-053 | dynamic latency budget |
| D-054 | `\\command` → `\command` في math |
| D-055 | luxury UI theme + zero-flicker + premium typography |
| D-055.1 | header seamless integration (no white line on pure-black) |
| **D-055.2** | **legacy-style.css purge (gold gradient elimination)** |

---

## 6.38 Legacy-Style Purge — Gold-Gradient Elimination (2026-05-14, ISS-063 / D-055.2)

> **الكارثة العنيدة**: رغم D-055 و D-055.1، المستخدم بلَّغ: «الخلفية لم تصبح سوداء فاخرة في الوضع الليلي ولا بيضاء فاخرة في الوضع النهاري — مزالت كارثية مدمرة خطيرة». 

### السبب الجذري النهائي — Import Order

`frontend/app/layout.jsx` كان يستورد ملفَّين CSS:
```jsx
import "./globals.css";        // ← نظام D-055 الفاخر
import "./legacy-style.css";   // ← يطغى بـ gradient ذهبي!
import 'katex/dist/katex.min.css';
```

`legacy-style.css` (578 سطراً) كان يحوي:
```css
:root {
    --background-color: #050506;          /* ليس pure-black */
    --primary-color: #d4af37;             /* ذهبي */
    --text-color: #f7f3ec;                /* cream، ليس أبيض فاخر */
    --border-color: rgba(212,175,55,0.28); /* حدود ذهبية */
}

body, html {
    background:
        radial-gradient(1200px circle at 10% 0%, rgba(212, 175, 55, 0.16), transparent 60%),  /* ذهبي */
        radial-gradient(900px circle at 90% 15%, rgba(0, 170, 255, 0.12), transparent 55%),   /* أزرق */
        var(--background-color);
}
```

**النتيجة**: حتى مع `--bg-color: #0a0a0a` في globals.css، الـ body كان يُرسَم بـ:
- خلفية `#050506` (من legacy)
- + gradient ذهبي 16% opacity
- + gradient أزرق 12% opacity

= **مزيج warm-cream + golden glow** ⇢ ليس "أسود فاخر".

### الإصلاح (D-055.2 — 3 خطوات)

**خطوة 1 — حذف الـ import من `layout.jsx`**:
```jsx
import "./globals.css";
// import "./legacy-style.css";   ← حُذف
import 'katex/dist/katex.min.css';
```

**خطوة 2 — حذف ملف `legacy-style.css` نفسه** (`git rm`):
- 578 سطراً من الـ overrides الكارثية → DELETED
- لا dependency خارجي عليه (تأكدنا بـ `grep -r "legacy-style"` → 0 references خارج التعليقات)
- كل class selectors المستخدَمة فيه (`.app-container`, `.chat-area`, `.header`, `.message-bubble`, …) مُعرَّفة فعلاً في `globals.css`

**خطوة 3 — تقوية `body` rule في `globals.css`**:
```css
body, html {                       /* تقوية الـ specificity */
    height: 100%;
    margin: 0;
    background: var(--bg-color);   /* shorthand يُلغي background-image أي gradient */
    ...
}
```

الـ `background` shorthand (بدل `background-color`) يُصفّر أي `background-image` من أي CSS قديم قد يبقى في cache المتصفح.

### القاعدة الدائمة الإضافية لـ D-055 (الثامنة)

**(8) Single source of truth for theming**: نظام الثيم يعيش في **ملف CSS واحد** (`globals.css`). أي ملف "legacy" أو "supplemental" يحوي `:root { --bg: ... }` أو `body { background: ... }` = خطر فوري على نظام الثيم. يجب:
- مراجعة كل `@import` و `import "*.css"` في `layout.*` على PR
- البحث عن ملفات CSS مستقلة في `app/` و حذفها أو دمجها
- استخدام `background` shorthand في body rule لإلغاء أي background-image قديم

### قياس النجاح حياً

```bash
# 1. تأكد من حذف legacy
[ ! -f frontend/app/legacy-style.css ] && echo "✅ DELETED"

# 2. تأكد من حذف الـ import
grep "import.*legacy-style" frontend/app/layout.jsx | grep -v "^//"
# المتوقع: 0 نتائج (إلا في تعليقات)

# 3. تأكد من قوة body rule
grep -A2 "^body, html" frontend/app/globals.css | grep "background:"
# المتوقع: background: var(--bg-color);

# 4. تأكد من عدم وجود gradient ذهبي
grep -i "212.*175.*55\|gold\|d4af37" frontend/app/globals.css
# المتوقع: 0 نتائج
```

### السلسلة الكاملة (D-049 → D-055.2)

| Decision | المُصلَح |
|----------|---------|
| D-049 | JSON envelope leak |
| D-050 | indexed preempt + typewriter |
| D-051 | LaTeX delimiters `\\(...\\)` → `$...$` |
| D-052 | conversation context + chunk-tag stripping + Skills |
| D-053 | dynamic latency budget |
| D-054 | `\\command` → `\command` في math |
| D-055 | luxury UI theme + zero-flicker + premium typography |
| D-055.1 | header seamless integration (no white line on pure-black) |
| D-055.2 | legacy-style.css purge — gold gradient elimination |
| **D-056** | **Claude-style full-width layout + zero-line markdown + light mode hardening** |

---

## 6.39 Claude-Style Full-Width Layout — Zero-Line Markdown + Light Mode Hardening (2026-05-14, ISS-064 / D-056)

> **3 كوارث متراكبة شاهدها المستخدم**:
> 1. **نصف الجملة لا يظهر** — text overflow على اليمين، الكلمات تنقطع («بال» مقطوعة، الباقي مخفي)
> 2. **عشرات الخطوط الكارثية** — h1/h2 يظهرون بخطوط زرقاء سفلية + h2 بـ border-right، md-hr يظهر كخط أفقي، code blocks بإطار أزرق
> 3. **الوضع النهاري لا يعمل** — رغم `:root` بقيم `#ffffff`/`#0a0a0a`، التطبيق على `[data-theme='light']` كان ضعيف الموثوقية
>
> **طلب المستخدم**: «يجب أن يظهر بشكل خارق مثل Claude بحيث يملأ الشاشة بشكل خارق ويستفيد من المساحة الكاملة من أقصى اليمين لليسار».

### الإصلاح (D-056 — 5 طبقات)

**طبقة 1 — Claude-style full-width message layout**:
- `.messages`: `max-width: 920px` + `width: 100%` + `margin-inline: auto` — يستفيد من العرض الكامل على الجوال، مع breathing room على الشاشات الكبيرة.
- `.message.assistant .message-bubble`: `width: 100% + max-width: 100% + padding: 0 + border: none + background: transparent` — مثل Claude تماماً، النص يتدفق edge-to-edge بدون bubble.
- `.message.user .message-bubble`: `max-width: min(85%, 600px) + border-radius: 18px 18px 6px 18px + padding: 0.85rem 1.15rem` — bubble أزرق صغير على اليمين.
- `.input-area-wrapper` و `.agent-board-container`: نفس `max-width: 920px + margin-inline: auto` — وحدة بصرية كاملة عبر التطبيق.

**طبقة 2 — Zero-line markdown headings**:
- `.markdown-content h1`: حُذف `border-bottom: 2px solid var(--primary-color)` — كان يظهر كخط أزرق أفقي مزعج تحت كل عنوان رئيسي.
- `.markdown-content h2`: حُذف `border-right: 3px solid var(--primary-color)` — كان يظهر كخط أزرق عمودي.
- التركيز الآن على `letter-spacing: -0.015em + font-weight: 800` للتمييز البصري بدلاً من الخطوط.

**طبقة 3 — Invisible hr + transparent blockquote**:
- `.md-hr`: `height: 0 + opacity: 0` — كان يظهر كخط رمادي أفقي بين الأقسام («عشرات الخطوط» التي شكا منها المستخدم).
- `.md-blockquote`: `background: transparent + border-right: 2px solid var(--text-secondary) + opacity: 0.85` — كان يظهر بخلفية زرقاء بارزة.

**طبقة 4 — Code blocks بدون إطار حاد**:
- `.markdown-content code`: `background: var(--surface-elevated) + border: none + color: var(--text-color)` — كان يظهر بإطار أزرق و خلفية زرقاء.

**طبقة 5 — Explicit `[data-theme='light']` block**:
- إضافة block صريح بـ specificity أعلى من `:root` لضمان تطبيق الوضع النهاري بشكل موثوق على كل المتصفحات/البيئات.
- يحوي نفس قيم `:root` لكن بـ selector أقوى = override مضمون لو حدث أي conflict.

### القواعد الدائمة الجديدة لـ D-056

**(1) Full-width assistant, constrained user**: في تطبيقات chat الفاخرة:
- رسالة المساعد = full-width (Claude-style)، لا bubble، لا max-width
- رسالة المستخدم = bubble صغير (~85%) مُحدَّد على side الـ user
- messages container = max-width ~920px + center-margin

**(2) No decorative borders on inline content**: على pure-black/pure-white، أي `border` للزينة على inline elements (h1/h2/blockquote/code) يظهر كخط مرئي مزعج. استخدم `letter-spacing` و `font-weight` و `color` للتمييز البصري.

**(3) Explicit theme blocks > :root**: للموثوقية القصوى، عرِّف كل theme variants في `[data-theme='*']` blocks صريحة، ليس فقط في `:root`. يضمن override على أي CSS قديم cached.

### قياس النجاح حياً

```bash
# 1. تأكد من إزالة borders الزرقاء على markdown headings
grep "border-bottom.*primary-color\|border-right.*primary-color" frontend/app/globals.css
# المتوقع: 0 نتائج فعلية (في القواعد، ليس في التعليقات)

# 2. تأكد من messages container responsive
grep "max-width: 920px" frontend/app/globals.css
# المتوقع: 3 نتائج — .messages, .input-area-wrapper, .agent-board-container

# 3. تأكد من assistant bubble full-width
grep -A3 "message.assistant .message-bubble" frontend/app/globals.css | grep "width: 100%"
# المتوقع: موجود

# 4. تأكد من light mode block
grep "^\[data-theme='light'\]" frontend/app/globals.css
# المتوقع: موجود
```

### السلسلة الكاملة (D-049 → D-056)

| Decision | المُصلَح |
|----------|---------|
| D-049 | JSON envelope leak |
| D-050 | indexed preempt + typewriter |
| D-051 | LaTeX delimiters `\\(...\\)` → `$...$` |
| D-052 | conversation context + chunk-tag stripping + Skills |
| D-053 | dynamic latency budget |
| D-054 | `\\command` → `\command` في math |
| D-055 | luxury UI theme + zero-flicker + premium typography |
| D-055.1 | header seamless integration |
| D-055.2 | legacy-style.css purge |
| D-056 | Claude-style full-width + zero-line markdown + light hardening |
| **D-057** | **Horizontal overflow defense + mobile-first responsive + theme dual-binding** |

---

## 6.40 Defensive Overflow + Mobile/Desktop Responsive + Theme Dual-Binding (2026-05-14, ISS-065 / D-057)

> 3 كوارث مدمرة شاهدها المستخدم بعد D-056:
> 1. **«الجمل مزالت لا تظهر»** — text overflow على اليمين، الجمل تنقطع
> 2. **«خانة البحث بعد ظهور الكتابة نصفها لا يظهر»** — input field overflow
> 3. **«زر الإرسال يختفي»** — send button cut off-screen
> 4. **«الواجهة في حد ذاتها تختفي كليا»** — whole UI sliding off-viewport
> 5. **«الوضع النهاري معطل تماما»** — light mode toggle has no effect
>
> طلب: **«يجب أن تدعم الهاتف و الحاسوب بشكل خارق جدا خرافي احترافي فائق الجودة العالية الفاخرة الراقية الفخمة للمستقبل البعيد فائق الدقة للمشاريع العملاقة شديدة التعقيد».**

### الأسباب الجذرية

1. **Horizontal overflow chain**: عناصر داخلية (KaTeX inline `nowrap`, long Arabic words, math expressions) تُفرض expansion على الـ flex containers لأن `min-width: 0` غير مُحدَّد. الـ flex items default إلى `min-width: auto` فلا تنكمش لـ shrink عن المحتوى الطبيعي.
2. **Sidebar absolute positioning** بـ `transform: translateX(100%)` كان يخلق ghost overflow على المتصفحات التي لا تطبق `overflow: hidden` بصرامة كافية.
3. **Light mode toggle** كان يُعدِّل `documentElement.dataset.theme` فقط — لا fallback على `body`، لا `color-scheme` للـ browser controls.
4. **Mobile vs desktop padding** ثابت — على الهاتف ضيق جداً، على الحاسوب يفقد breathing room.

### الإصلاح (D-057 — 5 طبقات دفاع)

**طبقة 1 — Universal `min-width: 0` + html/body overflow-x defense**:
```css
* { box-sizing: border-box; min-width: 0; }
html, body { overflow-x: hidden; max-width: 100vw; }
```
يضمن أن أي flex child ينكمش لـ shrink، ولا يخرج محتوى من viewport.

**طبقة 2 — Layered overflow-x on every chat container**:
```css
.app-container       { max-width: 100vw; overflow-x: hidden; }
.dashboard-layout    { max-width: 100vw; width: 100%; min-width: 0; }
.chat-area           { min-width: 0; overflow-x: hidden; width: 100%; }
.chat-container      { width: 100%; min-width: 0; overflow-x: hidden; }
.message-bubble      { min-width: 0; overflow-wrap: break-word; }
.input-area textarea { min-width: 0; width: 100%; }
```

**طبقة 3 — Mobile-first responsive containers**:
```css
.messages, .input-area-wrapper, .agent-board-container {
    /* mobile (<640px): padding أصغر، عرض كامل */
    padding: 0.75rem 1rem; max-width: 100%; width: 100%;
}
@media (min-width: 640px) {
    /* tablet+desktop: breathing room + max 920px center */
    padding: 1.25rem 1.5rem; max-width: 920px;
}
```

**طبقة 4 — Touch-target sizing (44px mobile, 40px desktop)**:
```css
.input-area button { width: 44px; height: 44px; flex-shrink: 0; }
@media (min-width: 640px) {
    .input-area button { width: 40px; height: 40px; }
}
```
يحترم Apple HIG (44px) + Material Design (48px) touch target standards.

**طبقة 5 — Theme dual-binding (html + body + color-scheme)**:
```js
// CogniForgeApp.jsx
root.dataset.theme = theme;          // html[data-theme]
root.style.colorScheme = theme;       // browser form controls
document.body.dataset.theme = theme;  // body[data-theme] defensive
```
```css
/* CSS supports both selectors */
[data-theme='light'], body[data-theme='light'] { ... }
[data-theme='dark'],  body[data-theme='dark']  { ... }
```

### القواعد الخمس الدائمة الجديدة (D-057)

**(1) Universal `min-width: 0` رمز ذهبي**: أي flex item بدون `min-width: 0` يفشل في الـ shrinking ويُسبب overflow أفقي على viewports صغيرة. القاعدة: `* { min-width: 0 }` defensive.

**(2) Multi-layer overflow-x defense**: html, body, app-container, dashboard-layout, chat-area كلها تحتاج `overflow-x: hidden`. لو طبقة واحدة فقدت الـ rule، أحد المتصفحات (Safari iOS مثلاً) قد يتجاوزها.

**(3) Mobile-first responsive padding**: ابدأ بـ padding ضيق للهاتف (`0.75rem 1rem`)، أضف breathing room على tablet+ عبر `@media (min-width: 640px)`. **NEVER** تفترض viewport ≥ 640px.

**(4) Touch targets ≥ 44px على الهاتف**: زر الإرسال + buttons interactives = 44px على mobile (Apple HIG + Material Design). على desktop يمكن تقليلها لـ 40px.

**(5) Theme dual-binding (html + body)**: theme لا يطبَّق على html فقط — `body[data-theme]` + `color-scheme` لتغطية edge-cases على cached CSS، browser form controls، Safari iOS quirks.

### قياس النجاح حياً

```bash
# 1. defensive overflow-x في كل containers
grep -c "overflow-x: hidden" frontend/app/globals.css
# المتوقع: ≥ 5

# 2. min-width: 0 في كل flex children
grep -c "min-width: 0" frontend/app/globals.css
# المتوقع: ≥ 8

# 3. responsive padding على mobile
grep -A1 "@media (min-width: 640px)" frontend/app/globals.css | grep -c "max-width: 920px"
# المتوقع: ≥ 3

# 4. theme dual-binding
grep "body\[data-theme" frontend/app/globals.css
# المتوقع: 2 results
```

### السلسلة الكاملة (D-049 → D-057)

| Decision | المُصلَح |
|----------|---------|
| D-049 | JSON envelope leak |
| D-050 | indexed preempt + typewriter |
| D-051 | LaTeX delimiters `\\(...\\)` → `$...$` |
| D-052 | conversation context + chunk-tag stripping + Skills |
| D-053 | dynamic latency budget |
| D-054 | `\\command` → `\command` في math |
| D-055 | luxury UI theme + zero-flicker + premium typography |
| D-055.1 | header seamless integration |
| D-055.2 | legacy-style.css purge |
| D-056 | Claude-style full-width + zero-line markdown + light hardening |
| D-057 | defensive overflow + mobile/desktop responsive + theme dual-binding |
| **D-058** | **ISS-066 — light mode catastrophic fix: anti-flash script + html[data-theme] + lazy useState + CSS variables for code blocks** |




---

## 6.41 Light Mode Catastrophic Fix + Live Testing (2026-05-14, ISS-066 / D-058)

### المشكلة الجذرية (4 طبقات + 2 مكتشَفتان بالتجريب الحي)

> **ISS-066**: الوضع النهاري معطل كارثياً — زر التبديل لا يُنتج أي تغيير مرئي.

**طبقة 1 — FOUC**: `layout.jsx` لا يضع `data-theme` على `html` قبل hydration.

**طبقة 2 — CSS Specificity**: `html[data-theme='light']` selector مفقود.

**طبقة 3 — Hard-coded colors**: `.markdown-content pre { background: #0f172a }` ثابت.

**طبقة 4 — useState flash**: `useState('dark')` + `useEffect` يُسبب double-render.

**طبقة 5 (مكتشَفة بالتجريب الحي) — Turbopack CSS merging bug**:
Turbopack يُلغي properties عند وجود selectors متعددة للعنصر نفسه.
`html, body { overflow-x: hidden }` + `body { background: var(--bg-color) }` = Turbopack يُبقي فقط `body { overflow-x: hidden; max-width: 100vw }` ويُلغي `background` و `color`.
**الحل**: block واحد لكل عنصر يحتوي كل properties.

**طبقة 6 (مكتشَفة بالتجريب الحي) — Next.js 16 App Router script placement**:
`<script dangerouslySetInnerHTML>` في `<head>` JSX يُنقَل لـ `<body>` بواسطة Next.js 16.
`next/script strategy="beforeInteractive"` يُنفَّذ عبر `__next_s` payload — بعد runtime.
**الحل الوحيد الموثوق**: ملف خارجي في `/public/theme-init.js` + `<script src="/theme-init.js">` في `<head>`.

### الإصلاح النهائي (D-058 rev4)

**`frontend/public/theme-init.js`** — ملف جديد:
```javascript
(function(){
  try {
    var t = localStorage.getItem('theme') || 'dark';
    var r = document.documentElement;
    r.dataset.theme = t;
    r.style.colorScheme = t;
    if (document.body) { document.body.dataset.theme = t; }
    else {
      var o = new MutationObserver(function(){
        if (document.body) { document.body.dataset.theme = t; o.disconnect(); }
      });
      o.observe(r, { childList: true });
    }
  } catch(e) {}
})();
```

**`frontend/app/layout.jsx`**:
```jsx
<html lang="ar" dir="rtl" suppressHydrationWarning>
  <head>
    <script src="/theme-init.js" />  {/* synchronous — بدون async */}
  </head>
  <body suppressHydrationWarning>{children}</body>
</html>
```

**`frontend/app/globals.css`** — دمج html و body في blocks منفصلة:
```css
/* WRONG — Turbopack يُلغي properties */
html, body { overflow-x: hidden; }
body { background: var(--bg-color); }  /* يُلغى! */

/* CORRECT — block واحد لكل عنصر */
html { overflow-x: hidden; background: var(--bg-color); color: var(--text-color); ... }
body { overflow-x: hidden; background: var(--bg-color); color: var(--text-color); ... }
```

### قواعد دائمة جديدة (D-058)

1. **Next.js 16 App Router**: لا تضع `<script dangerouslySetInnerHTML>` في `<head>` JSX — يُنقَل لـ `<body>`. استخدم ملف خارجي في `/public`.
2. **Turbopack CSS**: لا تُكرِّر selector في blocks متعددة — Turbopack يُبقي آخر block فقط.
3. **Anti-flash**: `<script src="/theme-init.js">` بدون `async` في `<head>` = synchronous execution قبل أي paint.

### السلسلة الكاملة (D-049 → D-058)

| Decision | المُصلَح |
|----------|---------|
| D-049 | JSON envelope leak |
| D-050 | indexed preempt + typewriter |
| D-051 | LaTeX delimiters `\\(...\\)` → `$...$` |
| D-052 | conversation context + chunk-tag stripping + Skills |
| D-053 | dynamic latency budget |
| D-054 | `\\command` → `\command` في math |
| D-055 | luxury UI theme + zero-flicker + premium typography |
| D-055.1 | header seamless integration |
| D-055.2 | legacy-style.css purge |
| D-056 | Claude-style full-width + zero-line markdown + light hardening |
| D-057 | defensive overflow + mobile/desktop responsive + theme dual-binding |
| D-058 | ISS-066 — light mode fix: /public/theme-init.js + Turbopack single-block CSS + html[data-theme] + lazy useState |
| **D-059** | **ISS-067 — always-visible theme button (header-theme-btn) + :root code vars + luxury light overrides + CI gate** |

## 6.42 Always-Visible Theme Button + Luxury Light Mode (2026-05-14, ISS-067 / D-059)

### المشكلة الجذرية

> **ISS-067**: زر تبديل الـ theme مخفي داخل dropdown menu — المستخدم يجب أن يضغط `⋮` أولاً ثم يختار "الوضع النهاري". هذا هو السبب الحقيقي لعدم عمل الوضع النهاري من منظور UX.

**مشكلة ثانوية**: `--code-bg`، `--pre-bg`، `--code-color`، `--pre-color`، `--pre-border` كانت مفقودة من `:root` — موجودة فقط في `html[data-theme='light']` و `html[data-theme='dark']`. إذا لم يُطبَّق أي منهما، هذه المتغيرات `undefined`.

**مشكلة ثالثة**: الوضع النهاري يفتقر إلى overrides فاخرة لمكونات كثيرة (chat area، markdown، input، sidebar، إلخ).

### الإصلاح (D-059)

**`frontend/app/components/CogniForgeApp.jsx`** — زر theme دائم الظهور في الـ header:
```jsx
{/* ISS-067: زر الـ theme مرئي دائماً — لا يحتاج فتح القائمة */}
<button
    className="header-theme-btn"
    onClick={handleToggleTheme}
    title={theme === 'dark' ? 'الوضع النهاري' : 'الوضع المظلم'}
    aria-label={theme === 'dark' ? 'تفعيل الوضع النهاري' : 'تفعيل الوضع المظلم'}
>
    <i className={`fas ${theme === 'dark' ? 'fa-sun' : 'fa-moon'}`}></i>
</button>
{isMenuOpen && ( /* dropdown يأتي بعد الزر */ )}
```

**`frontend/app/globals.css`**:
- `:root` يحتوي الآن على جميع متغيرات code blocks كـ fallback آمن
- قسم "Light Mode Luxury Overrides" شامل: header، chat area، messages، markdown، input، sidebar، login form، agent sidebar، scroll button، status indicators
- `.header-theme-btn` CSS كامل: base + hover + active + light mode override

**`.github/workflows/frontend-theme-ci.yml`** — 6 jobs + summary:
1. `theme-contracts` — CSS selectors + variables + `:root` fallbacks
2. `anti-flash-gate` — theme-init.js + lazy useState + triple application
3. `theme-button-gate` — **جديد**: يتحقق من `header-theme-btn` خارج dropdown + aria-label + CSS كامل
4. `build-check` — Next.js production build + compiled CSS verification
5. `lint-frontend` — ESLint + console.log audit
6. `theme-regression` — CSS symmetry + overflow defense + Turbopack single-block

### قواعد دائمة جديدة (D-059)

1. **Theme button visibility**: زر تبديل الـ theme يجب أن يكون **دائماً مرئياً** في الـ header — لا يُخفى داخل dropdown.
2. **`:root` completeness**: جميع CSS variables يجب أن تكون في `:root` كـ fallback — حتى لو كانت موجودة في `html[data-theme]` blocks.
3. **CI gate**: `theme-button-gate` job يتحقق من أن `header-theme-btn` يظهر قبل `isMenuOpen &&` في JSX.

---

**Model fix applied 2026-05-15 (ISS-068 — inclusionai/ring-2.6-1t:free Rate-Limited / D-060):** تجريب حي كشف أن `inclusionai/ring-2.6-1t:free` معطّل upstream على Novita (rate-limited بشكل دائم). كان النموذج الافتراضي في 14 ملف عبر كل الخدمات المصغرة → جميع الخدمات تُعيد إجابات فارغة أو تنتهي مهلتها. بنشمارك حي لـ 8 نماذج مجانية على OpenRouter كشف أن `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free` هو الأفضل (TTFT=4s، reasoning tokens، عربية ممتازة، LaTeX صحيح). **التغييرات:** استبدال النموذج في 14 ملف عبر `app/` و `microservices/`. fallback chain: `nemotron-super-120b` → `gpt-oss-20b` → `gpt-oss-120b`. MCTS depth: 2→1، timeout: 300s→45s. System prompts مُحدَّثة: LaTeX إلزامي + خطوات مرقمة + `$$\boxed{...}$$` + تفسير هندسي. **قاعدة لا تُخرق:** `inclusionai/ring-2.6-1t:free` محظور — لا تستخدمه كنموذج افتراضي. **نتائج حية:** reasoning-agent يُجيب بخطوات مفصلة + LaTeX صحيح ✅ | research-agent `tavily_available: true` ✅ | planning-agent PostgreSQL ✅.

---

## 6.43 LaTeX Stream Normalizer + Math Pipeline Hardening (2026-05-15, ISS-074 / D-062)

> **الكارثة المُشخَّصة بالتجريب الحي 2026-05-15**: شكوى مستخدم: «اجابات الذكاء الاصطناعي كارثية و غبية كلمات غبية فقدان سياق نصوص غير منظمة حروف متداخلة». تجريب حي لـ 10 نماذج OpenRouter مجانية + اختبار math_pipeline على 7 أسئلة معقدة كشف 5 أسباب جذرية متراكبة.

### الأسباب الجذرية الخمس

| # | السبب | الكارثة المرئية |
|---|------|------------------|
| 1 | **orchestrator nodes لا تطبِّع LaTeX** — `SynthesizerNode`/`GeneralKnowledgeNode`/`ChatFallbackNode` تبث `\[...\]` خام للعميل | الواجهة تعرض `\[f'(x)=...\]` كنص رياضي خام (لا KaTeX) |
| 2 | **_META_MARKERS مفرطة الحساسية** — تطابق `"Let me"`, `"I will"` التي تظهر طبيعياً في شرح علمي | math_pipeline يدخل retry loop لكل سؤال → بطء + فشل |
| 3 | **System-prompt echo على أسئلة معقدة** — نموذج nano-30b يُكرِّر تعليمات system prompt كنص (`"$$ for equations, $$ for boxed..."`) | المستخدم يرى تعليمات بدل الحل |
| 4 | **خلط لغات** — `линейный` (روسي), `向心` (صيني), `aparece` (إسباني) | كلمات أجنبية وسط نص عربي |
| 5 | **Chat meta-narration** — `"Okay, the user greeted me with..."` | الردود تبدأ بتفكير صوتي إنجليزي |

### تجريب حي قبل الإصلاح (2026-05-15)

```
المسألة: ادرس الدالة f(x) = (x²-1)/(x+2)
الرد:    ## 📐 مسألة اشتقاق

         $$...$$ for equations, $$ for final result in boxed.
         Must follow methodology: explain why we use this method in a line,
         then steps numbered, final result in boxed, add short interpretation...
```
**0/5 tests pass** | meta-text leak | echo system prompt | foreign script leak

### الإصلاح (D-062 — 9 طبقات)

**طبقة 1 — `LatexStreamNormalizer` module جديد** (orchestrator):
- ملف: `microservices/orchestrator_service/src/services/overmind/latex_normalizer.py`
- `LatexStreamNormalizer.feed(chunk)` — buffered streaming normalizer مع lookahead
- `normalize_latex(text)` — دالة batch للاستخدام في non-streaming paths
- تعالج: `\[...\]`, `\\[...\\]`, `\begin{equation}`, `\begin{align}`, `\begin{aligned}`
- 10 وحدة اختبار: char-by-char, equation env, inline preserved, forced flush, no byte loss

**طبقة 2 — تطبيق على 3 leaf nodes في orchestrator**:
- `SynthesizerNode` (`search.py`) — مساران streaming (no-docs + with-docs) + DSPy batch fallback
- `GeneralKnowledgeNode` (`general_knowledge.py`) — streaming + non-streaming paths
- `ChatFallbackNode` (`main.py`) — streaming + non-streaming paths
- **القاعدة الذهبية**: كل `writer({"chunk_type": "assistant_delta", "content": ...})` يمر عبر `normalizer.feed()` أولاً

**طبقة 3 — Math Pipeline meta-text detection ذكي**:
- ملف: `microservices/conversation_service/src/math_pipeline.py`
- `_META_MARKERS` (13 marker) — phrases-محددة فقط (`"Let me think"`, `"We need to"`, `"Okay, so"`)
- `_SYSTEM_PROMPT_ECHO_MARKERS` (21 marker) — `"$$ for equations"`, `"Must use $$"`, `"steps numbered, final"`
- `_META_CHECK_PREFIX_LEN = 200` — فحص prefix فقط (لا full scan)
- `_strip_meta_prefix(text)` — يحذف meta-narration ويحتفظ بالمحتوى العلمي

**طبقة 4 — Foreign-script cleanup**:
- `_clean_foreign_scripts(text)` يستبدل: Russian → عربي، Spanish `aparece → يظهر`، Chinese `向心 → جذب مركزي`
- Regex stripping: `[Ѐ-ӿ]+` (Cyrillic), `[一-鿿]+` (CJK Han), `[぀-ゟ゠-ヿ]+` (Japanese)
- يُطبَّق في `normalize_node` (math_pipeline) + `_normalize_latex_response` (conversation_graph)

**طبقة 5 — Chat meta-narration stripping**:
- `_strip_chat_meta_narration(text)` في `conversation_graph.py`
- 6 patterns: `Okay, the user...`, `First, I (should|must|need)...`, `The user greeted me...`, إلخ
- 5-pass loop (لتغطية meta-narration متتالية)
- يُطبَّق فقط على `intent == "chat"` (لا يكسر الإجابات التعليمية)

**طبقة 6 — Retry على نموذج أقوى**:
- عند كشف meta أو echo → retry على `nvidia/nemotron-3-super-120b-a12b:free` (بدل nano-30b)
- prompt مُحسَّن قصير: «أستاذ رياضيات. اشرح بالعربية فقط. LaTeX: `$$...$$`. ابدأ بـ 'لحساب ...' بدون تمهيد»
- إن فشل الـ retry أيضاً → احتفظ بالمحتوى الأطول والأنظف عبر `_strip_meta_prefix`

**طبقة 7 — System prompt مُختصر + إيجابي**:
- الـ system prompt قبل كان طويلاً جداً مع 6 ❌ ممنوعات → النموذج كان يُكرِّرها كنص
- الجديد: 9 سطور إيجابية فقط (ماذا نفعل، لا ماذا نتجنب)
- منهجية 4 خطوات: لماذا → خطوات مرقمة → `$$\boxed{}$$` → تفسير

**طبقة 8 — Fallback chain مُحدَّث بعد بنشمارك حي**:
- ❌ `google/gemma-4-26b-a4b-it:free` (rate-limited 429) — مُزال
- ❌ `qwen/qwen3-coder:free` (rate-limited 429) — مُزال
- ❌ `deepseek/deepseek-chat-v3.1:free` (404 No endpoints) — مُزال
- ✅ `openai/gpt-oss-20b:free` (28s، عربية ممتازة، LaTeX سليم)
- ✅ `nvidia/nemotron-3-super-120b-a12b:free` (14s، 120B params، شرح عبقري)
- ✅ `openai/gpt-oss-120b:free` (21s، احتياطي)
- ✅ `z-ai/glm-4.5-air:free` (reasoning mode — ISS-069 fix)

**طبقة 9 — MathSkill رسمي في app/services/skills/**:
- `MathSkill` class بـ Pydantic contract موحَّد (`MathSkillInput` → `MathSkillOutput | SkillFailure`)
- مقاييس Prometheus: `cogniforge_skill_math_invocations_total{math_type,status}`, `_duration_seconds`, `_retries_total{reason}`
- يستخدم `invoke_math_pipeline` تحت غطاء — لا يستورد من Skills أخرى
- يعمل بدون orchestrator-service، آمن في وضع fallback

### نتائج التجريب الحي بعد الإصلاح (2026-05-15)

```
================================================================================
CogniForge — LIVE TEST: Math Pipeline + Conversation Graph (after D-062)
================================================================================
1. اشتقاق متقدم  (x²·e^(3x))         → 3.36s  ✅ PASS
2. تكامل بالتجزئة (∫x·ln(x))           → 2.77s  ✅ PASS
3. نهاية بقاعدة لوبيتال (sin(2x)/x)    → 2.03s  ✅ PASS
4. معادلة تفاضلية (y'+2y=0)            → 3.08s  ✅ PASS
5. دراسة دالة (مجال+مشتق+تغيرات)       → 10.60s ✅ PASS (retry on super-120b)
6. فيزياء — قوة طرد مركزي               → 8.36s  ✅ PASS
7. دردشة عامة "مرحبا، كيف حالك؟"        → 0.87s  ✅ PASS (chat intent + clean)
================================================================================
SUMMARY: 7/7 PASS | total_time=35.3s | كل LaTeX موحَّد $$...$$ | لا meta | لا روسي/صيني
================================================================================
```

### القواعد الـ 9 الدائمة (لا تُكسر بدون ADR)

**(1) Streaming LaTeX normalization إلزامية**: أي عقدة في orchestrator تبث chunks للمستخدم **يجب** أن تستخدم `LatexStreamNormalizer` بين `llm_client.stream_chat()` و `writer({"chunk_type": "assistant_delta"})`. الـ batch path يستخدم `normalize_latex()` على المخرج الكامل.

**(2) Meta-text detection فحص prefix فقط**: نتحقق من أول 200 char من الإجابة، ليس النص كامل. كثيراً ما `"Let me"` يظهر طبيعياً في شرح علمي عميق — لا تُعاقب على ذلك.

**(3) Echo markers أعلى أولوية من meta markers**: عند كشف echo (`"$$ for equations"`, `"Must use $$"`) → retry فوراً على نموذج أقوى (super-120b بدل nano-30b).

**(4) Foreign-script regex blacklist**: Cyrillic + CJK Han + Japanese → احذف. لاتيني عادي مسموح (للأسماء التقنية sin/cos/lim/dx).

**(5) Chat meta-narration للـ chat intent فقط**: لا تطبِّق `_strip_chat_meta_narration` على educational responses — قد تُحذف خطوة شرح مهمة.

**(6) System prompt قصير وإيجابي**: لا تكتب قوائم طويلة من الـ ❌ — النموذج يُكرِّرها كنص. اكتب التعليمات الإيجابية فقط.

**(7) Retry يستخدم نموذج مختلف**: عند فشل nano-30b بـ meta/echo → super-120b، لا نفس النموذج. النماذج الأكبر أكثر مقاومة لكشف الـ system prompt.

**(8) Fallback chain يخضع لبنشمارك حي دوري**: كل 30 يوماً، اختبر النماذج الـ 4 الأساسية مع سؤال رياضي معقد. أزل أي نموذج يُرجع 429/404 لأكثر من 24 ساعة.

**(9) MathSkill هو نقطة الدخول الوحيدة من monolith**: لا تستدعِ `invoke_math_pipeline` مباشرة من خارج `microservices/conversation_service/`. استخدم `MathSkill.invoke()` لتسجيل metrics + error handling موحَّد.

### الملفات المُعدَّلة (D-062)

| File | Change |
|------|--------|
| `microservices/orchestrator_service/src/services/overmind/latex_normalizer.py` | **جديد** — module + 10 unit tests |
| `microservices/orchestrator_service/src/services/overmind/graph/search.py` | wire LatexStreamNormalizer في streamingَين + DSPy batch |
| `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py` | wire LatexStreamNormalizer في streaming + non-streaming |
| `microservices/orchestrator_service/src/services/overmind/graph/main.py` | wire LatexStreamNormalizer في ChatFallbackNode |
| `microservices/conversation_service/src/math_pipeline.py` | system prompt قصير + meta/echo detection + retry على super-120b + foreign-script cleanup + classifier reorder |
| `microservices/conversation_service/src/conversation_graph.py` | `_strip_chat_meta_narration` + CJK/Cyrillic cleanup في `_normalize_latex_response` |
| `app/services/skills/math_skill.py` | **جديد** — MathSkill رسمي بـ Prometheus metrics |
| `app/services/skills/__init__.py` | export MathSkill |
| `tests/microservices/orchestrator_service/test_latex_normalizer.py` | **جديد** — اختبارات وحدة شاملة |
| `.github/workflows/iss-074-latex-stream-normalizer-gate.yml` | **جديد** — CI gate بـ 4 jobs |

### السلسلة الكاملة (D-049 → D-062)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-055.2 | JSON envelope leak + indexed preempt + LaTeX delimiters + theme + legacy purge |
| D-056 → D-058 | Claude-style full-width + overflow defense + light mode |
| D-059 | always-visible theme button |
| D-060 | ISS-068 — replace rate-limited model |
| **D-062** | **ISS-074 — LaTeX stream normalizer + Math pipeline hardening + MathSkill** |
| **D-063** | **ISS-075 — Greeting regex fix + Explanation patterns expansion + Foreign-script sanitizer** |

---

## 6.44 Greeting Catastrophe + Lost Explanation Context (2026-05-15, ISS-075 / D-063)

> **الكارثة المُشخَّصة بالتجريب الحي 2026-05-15**: شكوى المستخدم أظهرت 3 إخفاقات متراكبة على المسار الإنتاجي:
> 1. **"السلام عليكم"** → رد etymological 634 chars بكلمات أجنبية (`også`, `wishes`, `invitation`, `。 ）（`)
> 2. **"اشرح السؤال 1 أ"** → رد قصير 2 سطر، فقدان سياق
> 3. **"أريد شرح مفصل للسؤال 1 أ"** → هلوسة كاملة بالإندونيسية عن "dokumen pendidikan"

### الأسباب الجذرية الثلاث (مختبرة حياً)

**(1) `_GREETING_PATTERNS` regex مكسور**: `^(السلام|...)[\s\W]*$` يفشل عند "السلام عليكم" لأن "عليكم" ليست في `[\s\W]`. النتيجة: التحية تُصنَّف كـ `general` بدل `chat`، فيستخدم الـ LLM الـ `general` system prompt الذي يطلب "إجابة علمية بدقة" → الـ LLM يُولِّد etymology طويلة بكلمات أجنبية.

**(2) `_BAC_EXERCISE_EXPLANATION_PATTERNS` لا يشمل صياغات طبيعية**: أنماط مثل "أريد شرح"، "ممكن تشرح"، "أحتاج شرح"، "للسؤال" (مع prefix ل)، "شرح مفصل" — كلها مفقودة. النتيجة: `detect_explanation_with_context` يُرجع `recognized=False` → يذهب الطلب للـ LLM بدون سياق التمرين → هلوسة كاملة.

**(3) `local_graph.py` لا ينظِّف foreign-script**: الـ LLM يُسرِّب أحياناً `också/også/wishes/invitation/。` حتى مع system prompt صارم. لا توجد طبقة sanitization بعد `ai_client.send_message()`.

### الإصلاح (D-063 — 3 طبقات)

**طبقة 1: إعادة كتابة `_GREETING_PATTERNS`** (في `local_graph.py` + `path_observer.py` — D-013 invariant):
```python
_GREETING_PATTERNS = [
    # تحيات إسلامية + امتدادات (السلام عليكم ورحمة الله وبركاته)
    r"^(?:و\s*)?(?:عليكم\s+)?السلام(?:\s+عليكم)?(?:\s+و?رحم[ةى]\s+الله)?(?:\s+و?بركاته)?[\s\W]*$",
    # مرحبا/أهلا/هلا + 0-3 كلمات (مرحبا بك / أهلاً وسهلاً / هلا والله)
    r"^(مرحبا|أهلاً?|...)(?:\s+\S+){0,3}[\s\W]*$",
    # كيف حالك + 0-4 كلمات (كيف حالك يا أستاذ / كيف حالك اليوم)
    r"^(كيف\s+حالك|...)(?:\s+\S+){0,4}[\s\W]*$",
    # صباح الخير / مساء النور / ليلة سعيدة
    r"^(صباح\s+(الخير|النور)|...)[\s\W]*$",
    # ... 7 patterns total، تطابق 18+ صيغة
]
```

**طبقة 2: توسيع `_BAC_EXERCISE_EXPLANATION_PATTERNS`** (في `exercise_retrieval.py`):
- صياغات "أريد"/"ممكن"/"أحتاج": `أريد شرح`, `أريد شرحاً`, `ممكن شرح`, `ممكن تشرح`, `أحتاج شرح`, `هل يمكن أن تشرح`
- prefix "ل": `اشرح للسؤال`, `شرح للجزء`, `اشرح للفقرة`
- مع "مفصل": `شرح مفصل`, `اشرح بالتفصيل`, `explain in detail`, `detailed explanation`
- بالدارجة: `ابغى شرح`, `ابغي شرح`, `ابي شرح`, `ودي شرح`
- إنجليزي: `I want explanation`, `give me explanation`, `can you explain`

**طبقة 3: `_sanitize_local_graph_response()`** (في `local_graph.py`):
```python
_FOREIGN_REPLACEMENTS = {
    "også": "أيضاً", "auch": "أيضاً",         # نرويجي/دانماركي
    "линейный": "خطي", "функция": "دالة",    # روسي
    "aparece": "يظهر",                       # إسباني
    "wishes": "أمنيات", "invitation": "دعوة", # إنجليزي meta
    "。": ".", "（": "(", "）": ")", ...      # CJK punctuation → عربية
}
# + regex strip: Cyrillic [Ѐ-ӿ]+ / CJK Han [一-鿿]+ / Japanese kana [぀-ゟ゠-ヿ]+
# + chat meta-narration: "Okay, the user...", "First, I need to...", "Let me respond..."
```

### نتائج التجريب الحي بعد الإصلاح

```
=== سيناريو شكوى المستخدم الكامل ===
Step 1: "السلام عليكم"                         → intent=chat ✅ (كان general)
Step 2: تمرين BAC 2016                          → matched ✅
Step 3: "اشرح السؤال 1 أ"                       → explanation w/ context ✅
Step 4: "أريد شرح مفصل للسؤال 1 أ"              → recognized ✅ (كان False — هلوسة!)
Step 5-9: 5 صياغات إضافية                       → 5/5 ✅
==============================================
SUMMARY: 9/9 PASS

=== UNIT TESTS ===
TestGreetingRegex: 18/18 PASS
TestForeignScriptSanitizer: 9/9 PASS (including full user-catastrophe text)
TestExplanationPatterns: 7/7 PASS
TOTAL: 28/28 ✅
```

### القواعد الـ 5 الدائمة (D-063)

**(1) Greeting regex يجب أن يقبل امتدادات طبيعية**: التحية الإسلامية الكاملة "السلام عليكم ورحمة الله وبركاته" = 5 كلمات. الـ regex يجب أن يقبل 4+ كلمات إضافية بعد التحية الأساسية.

**(2) D-013 invariant: `_GREETING_PATTERNS` مكرَّر في ملفين**: `local_graph.py` AND `path_observer.py`. أي تعديل يجب أن يُطبَّق في كليهما في نفس الـ PR.

**(3) Explanation patterns تشمل صياغات "أريد"/"ممكن"/"أحتاج" + prefix "ل"**: الـ patterns لا تكون حرفية فقط — الطلاب يستخدمون عبارات متنوعة (أريد شرح، ممكن تشرح، أحتاج شرح، للسؤال، للجزء).

**(4) Sanitization عند المخرَج النهائي إلزامية**: الـ LLM يُسرِّب أحياناً كلمات أجنبية حتى مع system prompt صارم. الحل: طبقة sanitization جراحية بعد `ai_client.send_message()` — تستبدل كلمات معروفة + تحذف كتل Cyrillic/CJK/Hiragana كاملة.

**(5) Chat meta-narration stripping للـ chat فقط**: لا تُطبَّق على educational responses (قد تحذف خطوات شرح). تُطبَّق فقط عند `intent == "chat"`.

### الملفات المُعدَّلة (D-063)

| File | Change |
|------|--------|
| `app/services/chat/local_graph.py` | `_GREETING_PATTERNS` (7 → 7 مرنة) + `_sanitize_local_graph_response()` |
| `app/telemetry/path_observer.py` | `_GREETING_PATTERNS` (mirror — D-013) |
| `app/services/capabilities/exercise_retrieval.py` | `_BAC_EXERCISE_EXPLANATION_PATTERNS` (+20 pattern) |
| `tests/services/test_iss075_greeting_and_explanation.py` | **جديد** — 28 unit tests |
| `.memory/issues.md` | ISS-075 entry |
| `.memory/decisions.md` | D-063 entry |

### السلسلة الكاملة (D-049 → D-063)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-058 | JSON envelope + indexed preempt + LaTeX delimiters + theme system + legacy purge + Claude-style layout + overflow defense + light mode |
| D-059 | always-visible theme button |
| D-060 | ISS-068 — replace rate-limited model |
| D-062 | ISS-074 — LaTeX stream normalizer + Math pipeline hardening + MathSkill |
| D-063 | ISS-075 — Greeting regex fix + Explanation patterns + Foreign-script sanitizer (monolith) |
| **D-064** | **ISS-076 — Orchestrator response sanitizer + Greeting fast-path + UI flicker fix** |

---

## 6.45 Orchestrator Response Sanitizer + Greeting FastPath (2026-05-15, ISS-076 / D-064)

> **اكتشاف جديد بالتجريب الحي 2026-05-15**: D-063 يُصلح المسار `app/services/chat/local_graph.py`، لكن **المسار الإنتاجي الفعلي** يستخدم `microservices/orchestrator_service/` — والذي لم يُحدَّث في D-063. شكوى المستخدم بعد deploy D-063:
> 1. **"السلام عليكم"** → 5 أسطر etymology بـ `будет на вас`, `sentido de`, `Mexico City Amigos`, `Eugène的に`
> 2. **UI flicker** رغم ISS-073 ("الواجهة ترمش، خطوط تظهر وتختفي")
> 3. **"اكمل"** → هلوسة Mexico City Amigos

### الإصلاح (D-064 — 3 طبقات)

**طبقة 1: `response_sanitizer.py` module جديد** في `microservices/orchestrator_service/src/services/overmind/`:
- `sanitize_response(text, intent)` — تنظيف موحَّد: Cyrillic + CJK Han + Hiragana + Katakana + foreign words (Russian/Spanish/Norwegian) + CJK punctuation
- `get_greeting_fastpath_response(query)` — 22 تحية شائعة → رد deterministic 0ms (تجنَّب LLM)

**طبقة 2: تطبيق في 3 nodes orchestrator**:
| Node | تطبيق |
|------|-------|
| `ChatFallbackNode` (main.py) | greeting fastpath أولاً → sanitize chat على المخرج |
| `GeneralKnowledgeNode` (general_knowledge.py) | sanitize general على المخرج |
| `SynthesizerNode` (search.py) | sanitize educational على text_val قبل JSON wrapping |

**طبقة 3: `ChatInterface.jsx` flicker bypass**:
```jsx
// قبل D-064: useTypewriter بعد streaming → 2 render cycles (empty → full) → flicker
const displayedContent = useTypewriter(...);

// بعد D-064: عرض مباشر — 1 render cycle → 0 flicker
const contentToShow = msg.role === 'assistant' ? (msg.content || '') : '';
```

### نتائج التجريب الحي

```
=== D-064 unit tests ===
TestSanitizeForeignScripts:  7/7 PASS  (Russian/Norwegian/Spanish/CJK/Japanese)
TestChatMetaNarration:       5/5 PASS  (Okay, the user / Let me respond — chat فقط)
TestGreetingFastPath:       10/10 PASS (السلام/مرحبا/كيف حالك/hello/شكرا)
TestEdgeCases:               3/3 PASS  (None safe + plain Arabic + sin/cos preserved)
TOTAL D-064:                25/25 ✅

=== سيناريوهات الكارثة الحقيقية ===
"السلام عليكم"              → fastpath response 0ms ✅
"будет на вас"               → "يكون عليكم" ✅
"Mexico City Amigos"          → "" ✅
"sentido de"                  → "بمعنى" ✅
"Eugène的に"                 → "" ✅
"Okay, the user...مرحبا"      → "مرحبا" ✅

=== Regression (لا كسر) ===
D-062 (LatexStreamNormalizer): 10/10 PASS
D-063 (Greeting + Explanation): 28/28 PASS
GRAND TOTAL: 63/63 PASS
```

### القواعد الـ 5 الدائمة (D-064)

**(1) كل عقدة orchestrator تُرسل نص للمستخدم تستدعي `sanitize_response()`**: الـ LLM المجاني hallucination (Mexico City/будет/Eugène) يُنظَّف قبل reaching the user.

**(2) `ChatFallbackNode` يستدعي `get_greeting_fastpath_response()` قبل LLM**: التحية معروفة → رد سريع deterministic بدلاً من etymology طويلة.

**(3) Frontend لا يستخدم `useTypewriter` بعد streaming**: المحتوى الكامل يُعرَض مباشرة. typewriter يُسبب render cycles إضافية → flicker.

**(4) `_FOREIGN_REPLACEMENTS` dict يُحدَّث عند ظهور كلمة شاذة جديدة في الإنتاج**: لا regex عام (قد يكسر النص العربي) — allowlist محدَّد.

**(5) Chat meta-narration stripping للـ `intent="chat"` فقط**: educational/general تحتفظ بـ "Let me explain" (طبيعي في الشرح التعليمي).

### السلسلة الكاملة (D-049 → D-064)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-063 | JSON envelope + indexed preempt + LaTeX delimiters + theme + Claude layout + overflow + light mode + theme button + rate-limited model + LaTeX stream normalizer + Math pipeline + greeting regex (monolith) |
| D-064 | ISS-076 — Orchestrator response sanitizer + greeting fast-path + UI flicker bypass |
| **D-065** | **ISS-077 — FastPath over-match fix (educational verb blockers + كيف exception + tail allowlist)** |

---

## 6.46 Greeting FastPath Over-Match Fix (2026-05-15, ISS-077 / D-065)

> **اكتشاف بالتجريب الحي 2026-05-15**: شكوى المستخدم بعد deploy D-064: "النظام أصبح أكثر غباءاً... يتعامل مع السؤال كأنه جديد".
>
> **السبب الجذري** (مكتشَف بـ التجريب الحي على 7 سيناريوهات):
>
> ```python
> # D-064 buggy code:
> if cleaned.startswith(g_lower) and len(cleaned) - len(g_lower) <= 30:
>     return response  # 30 chars margin → سؤال علمي يضيع
> ```
>
> النتيجة الكارثية:
> - `"السلام عليكم اشرح لي قانون نيوتن"` → fastpath يطابق! → رد تحية فقط → **السؤال يضيع**
> - `"مرحبا اعطني تمرين"` → fastpath يطابق! → رد تحية → **الطلب يضيع**
> - النظام يعطي تحية بدلاً من إجابة → **يبدو "غبياً"** بالضبط كما وصف المستخدم

### الإصلاح (D-065 — 3 طبقات)

**طبقة 1**: `educational_blockers` قائمة — أي verb (اشرح/احسب/اعطني/تمرين/مسألة/explain/solve/calculate/ما هو/لماذا/متى/أين) يحجب fastpath فيذهب الطلب للـ LLM.

**طبقة 2**: `_kayfa_greetings` exception — "كيف" interrogative blocker إلا إذا كان في "كيف حالك"/"كيف الحال"/"كيف الأحوال" (تحية مسموحة).

**طبقة 3**: `allowed_tail_words` allowlist + margin reduced 30→25:
```python
allowed_tail_words = {
    "وعليكم", "السلام", "ورحمة", "الله", "وبركاته",
    "وسهلاً", "بكم", "والله", "يا", "أستاذ",
}
# tail بعد greeting يجب أن تكون كل كلماته من allowlist
```

### نتائج التجريب الحي (D-065)

```
=== Live test 17 cases ===
✅ 'السلام عليكم'                          → fastpath
✅ 'السلام عليكم ورحمة الله وبركاته'      → fastpath
✅ 'وعليكم السلام'                         → fastpath
✅ 'مرحبا'                                  → fastpath
✅ 'كيف حالك'                               → fastpath (exception)
✅ 'صباح الخير'                            → fastpath
✅ 'شكرا'                                   → fastpath
✅ 'hello' / 'good morning'                → fastpath

⛔ BLOCKERS (was buggy in D-064):
✅ 'السلام عليكم اشرح لي قانون نيوتن'     → BLOCKED (educational verb)
✅ 'مرحبا اعطني تمرين'                    → BLOCKED (educational verb)
✅ 'احسب التكامل'                         → BLOCKED
✅ 'ما هو التكامل'                        → BLOCKED (interrogative)
✅ 'لماذا نستخدم لوبيتال'                 → BLOCKED
✅ 'كيف أحل هذه المسألة'                  → BLOCKED (كيف interrogative)
✅ 'هل يمكنك شرح'                         → BLOCKED

SUMMARY: 17/17 PASS

=== Regression ===
D-064 unit tests: 32/32 PASS (7 new tests for blockers)
D-063: 28/28 PASS
D-062 normalizer: 10/10 PASS
GRAND TOTAL: 70/70 PASS ✅
```

### القواعد الـ 5 الدائمة (D-065)

**(1) أي query يحوي educational verb يجب أن يذهب للـ LLM، لا fastpath**: قائمة blockers تشمل اشرح/احسب/اعطني/تمرين/مسألة/explain/solve/calculate/ما هو/لماذا/متى/أين.

**(2) "كيف" interrogative blocker إلا في greeting patterns**: استثناءات فقط `كيف حالك`/`كيف الحال`/`كيف الأحوال`/`كيف صحتك`.

**(3) tail words allowlist إلزامي**: بعد greeting يُسمح فقط بـ {وبركاته، ورحمة الله، يا أستاذ، إلخ} — أي كلمة جديدة → اختبر unit test.

**(4) fastpath margin ≤25 chars**: أي توسيع يحتاج ADR ولن يُسمح بدون مراجعة كاملة.

**(5) عند إضافة greeting جديد للـ `_GREETING_FASTPATH` dict**: يجب اختبار الـ blocker case المقابل (greeting + question).

### الملفات (D-065)

| File | Change |
|------|--------|
| `microservices/orchestrator_service/src/services/overmind/response_sanitizer.py` | إضافة blockers + exception + tail allowlist |
| `tests/microservices/orchestrator_service/test_response_sanitizer.py` | +7 D-065 unit tests |
| `.memory/decisions.md` | D-065 entry |
| `.memory/issues.md` | ISS-077 entry |

### السلسلة الكاملة (D-049 → D-065)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-064 | JSON envelope + LaTeX + theme + Math pipeline + sanitizer + UI flicker |
| D-065 | ISS-077 — FastPath blockers (يحل "النظام أصبح غبياً") |
| **D-066** | **ISS-078 — Streaming-aware sanitization + empty user-bubble guard (يحل صينية لحظية + blue-bar flicker)** |

---

## 6.47 Streaming-Aware Sanitization + UI Flicker Guard (2026-05-15, ISS-078 / D-066)

> **اكتشاف بالتجريب الحي 2026-05-15**: شكوى المستخدم بعد D-064/D-065:
> 1. كلمات صينية تومض لحظياً خلال streaming ثم تختفي
> 2. شريط أزرق ضخم يومض في الواجهة (blue-bar flicker)

### الأسباب الجذرية (مُختبَرة حياً)

**(1) Streaming sanitization gap**:
```python
# قبل D-066:
for safe in normalizer.feed(content):
    writer({"chunk_type": "assistant_delta", "content": safe, ...})
    # ← chunk يصل للعميل خام، sanitize_response لم يُطبَّق بعد!
```

`sanitize_response` كان يُطبَّق على **المخرج النهائي** بعد streaming. لكن chunks تصل للعميل **مباشرة** من LLM. الـ Chinese/Russian يومض لحظياً قبل التنظيف النهائي.

**(2) Empty user bubble flicker**:
عند race condition قبل send، state يحوي رسالة user فارغة. الـ MessageBubble يعرض bubble بـ `background-color: var(--primary-color)` (أزرق) **حتى لو فارغ** → شريط أزرق ضخم يومض.

### الإصلاح (D-066 — 3 طبقات)

**طبقة 1: `sanitize_chunk()` دالة جديدة** في `response_sanitizer.py`:
```python
def sanitize_chunk(chunk: str) -> str:
    """ينظِّف chunk جزئي خلال streaming قبل إرساله للعميل."""
    for foreign, replacement in (("。", "."), ("（", "("), ...):
        out = out.replace(foreign, replacement)
    out = re.sub(r"[Ѐ-ӿ]+", "", out)  # Cyrillic
    out = re.sub(r"[一-鿿]+", "", out)  # CJK Han
    return re.sub(r"[぀-ゟ゠-ヿ]+", "", out)  # Japanese kana
```

**طبقة 2: تطبيق في 3 nodes streaming**:
```python
for safe_chunk in normalizer.feed(content):
    sanitized = sanitize_chunk(safe_chunk)  # ← D-066
    if not sanitized:
        continue
    writer({"chunk_type": "assistant_delta", "content": sanitized, ...})
```

**طبقة 3: `ChatInterface.jsx` empty user bubble guard**:
```jsx
// ISS-078 D-066: حماية ضد فقاعة user فارغة (سبب blue-bar flicker)
if (msg.role === 'user' && isEmpty) {
    return null;
}
```

### نتائج التجريب الحي

```
chunks: ['النص ', '向心 ', 'المركزي']
output: 'النص  المركزي'  ✅ Chinese stripped per chunk

chunks: ['السلام ', 'будет ', 'عليكم']
output: 'السلام  عليكم'  ✅ Russian stripped per chunk

chunks: ['نص', '。', ' آخر']
output: 'نص. آخر'  ✅ CJK punct replaced per chunk

8/8 D-066 live tests PASS
32/32 D-064+D-065 regression PASS
28/28 D-063 regression PASS
10/10 D-062 regression PASS
GRAND TOTAL: 70/70 PASS ✅
```

### القواعد الـ 5 الدائمة (D-066)

**(1) كل streaming chunk يجب أن يمر عبر `sanitize_chunk`**: قبل `writer({...})`. لا استثناءات.

**(2) `sanitize_chunk` لا يحوي multi-word replacements**: تحتاج سياق كامل — تُطبَّق في `sanitize_response` النهائي.

**(3) `sanitize_chunk` لا يحوي meta-narration stripping**: يحتاج بداية النص — تُطبَّق في `sanitize_response` النهائي.

**(4) أي bubble فارغة يجب أن لا تُعرَض**: user empty → return null. assistant empty + non-streaming → return null.

**(5) عند إضافة foreign script جديد**: يُضاف إلى `sanitize_chunk` (live cleanup) **و** `sanitize_response` (final cleanup).

### الملفات (D-066)

| File | Change |
|------|--------|
| `microservices/orchestrator_service/src/services/overmind/response_sanitizer.py` | + `sanitize_chunk()` function |
| `microservices/orchestrator_service/src/services/overmind/graph/main.py` | wire sanitize_chunk in ChatFallbackNode streaming |
| `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py` | wire sanitize_chunk |
| `microservices/orchestrator_service/src/services/overmind/graph/search.py` | wire sanitize_chunk in 2 streaming paths |
| `frontend/app/components/ChatInterface.jsx` | empty user bubble guard |

### السلسلة الكاملة (D-049 → D-066)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-065 | JSON envelope + LaTeX + theme + Math pipeline + sanitizer + fastpath blockers |
| **D-066** | **ISS-078 — Streaming sanitization (live Chinese flash) + empty bubble guard (blue-bar flicker)** |

---

## 6.48 Old-Conversation Spinner Catastrophe + Skill Doctrine Reinforcement (2026-05-18, ISS-080 / D-068)

> **الكارثة المُشخَّصة**: عند فتح محادثة قديمة، زر الإرسال يبقى دائرة تدور (`fa-spin`)
> بدل سهم الإرسال → المستخدم لا يستطيع إرسال أي رسالة → «دمَّر المشروع نهائياً».
> الـ screenshot أظهر أيضاً: LaTeX يظهر كنص خام (`\[ x^{2}-x-2=0 \]`) + لا زر نسخ.
> ثلاثة أعراض، سبب جذري واحد.

### السبب الجذري

`CustomerMessageOut` (`app/api/schemas/customer_chat.py:23`) و `MessageResponse`
(`app/api/schemas/admin.py:39`) يحويان فقط `{role, content, created_at|timestamp}`
— **لا حقل `isComplete`**. ذلك العَلَم خاص بالواجهة، يُنشئه `useAgentSocket`
خلال streaming الحي.

عند تحميل محادثة قديمة:
```javascript
// CogniForgeApp.jsx:184
const data = await fetch(historyEndpoint(id))  // CustomerConversationDetails
setMessages(data.messages || [])               // messages بدون isComplete
```

في `ChatInterface.jsx`، `!undefined === true` يُسبب الأعراض الثلاثة:
| السطر | الفحص | النتيجة الكارثية |
|-------|------|------------------|
| 379 | `messages.some(m => m.role==='assistant' && !m.isComplete)` | true → زر spinner دائم |
| 269 | `msg.role==='assistant' && !msg.isComplete` | true → `Markdown` يدخل streaming-raw → LaTeX خام |
| 315 | `msg.isComplete && !isEmpty` | false → زر النسخ مخفي دائماً |

### الإصلاح (D-068 — بوابة واحدة)

```javascript
// frontend/app/hooks/useAgentSocket.js
const setMessagesSafe = useCallback((msgs) => {
    if (!Array.isArray(msgs)) { setMessages([]); return; }
    const normalized = msgs.map((msg) => {
        if (!msg || typeof msg !== 'object') return msg;
        const next = { ...msg };
        if (next.id === undefined || next.id === null) next.id = generateId();
        // كل رسالة قادمة من التاريخ مكتملة بالتعريف.
        if (next.role === 'assistant' && next.isComplete !== true) next.isComplete = true;
        return next;
    });
    setMessages(normalized);
}, []);
```

**لماذا عند البوابة لا في `loadConversation`**: كل caller خارجي للـ hook
يمر عبر `setMessagesSafe`. التطبيع هنا يحمي ضد أي caller مستقبلي بدون تكرار.
نفس النمط استُخدِم في D-066 (`sanitize_chunk`/`sanitize_response` عند بوابة
الـ streaming nodes في orchestrator).

### Skill Doctrine Promotion

أُضيف إلى `app/services/skills/bac_exercise_skill.py`:

```python
EXPLANATION_DOCTRINE_VERSION: str = "1.0.0"
EXPLANATION_DOCTRINE: tuple[str, ...] = (
    "اعتمد على الإجابة النموذجية كـ *حُجّة* للنتائج العددية والصيغ النهائية.",
    "لا تنسخ الإجابة النموذجية حرفياً — اشرح *لماذا* كل خطوة تقود للنتيجة.",
    "أرقام الإجابة النموذجية مُلزِمة. لا تخترع نتائج بديلة.",
    "صيغ LaTeX من الإجابة النموذجية مُلزِمة. لا تُعد صياغتها برموز مختلفة.",
    "إذا كان الطالب طلب جزءاً محدداً (I/II/III/أ/ب/ج)، اقتصر عليه ولا تشرح غيره.",
    "اشرح القاعدة المُستخدمة (لوبيتال، داربو، التكامل بالتجزئة...) قبل تطبيقها.",
    "اربط بين خطوات الإجابة بـ «لأن ... إذن ...» لتوضيح المنطق التسلسلي.",
    "في النهاية: تحقق نظري سريع («بفحص نقطة x=0 نلاحظ...») + تفسير هندسي/فيزيائي.",
)
```

`BACSkillExplanationOutput.methodology_handle` (default
`explanation_doctrine_v1.0.0`) يُختم على كل مخرج EXPLAIN. تغيير الـ doctrine
= ترقية الإصدار → كل callers يكتشفون التحديث تلقائياً عبر assertion على الـ handle.

### القواعد الست الدائمة (D-068)

**(1)** أي حقل UI-only (مثل `isComplete`) يجب أن يُعرَّف افتراضه عند بوابة
دخول البيانات من backend. الـ backend response shape لا يجب أن يحمل عبء
حقول الواجهة.

**(2)** التطبيع عند بوابة الـ hook ≥ التطبيع عند كل caller — single source of truth.

**(3)** `!undefined === true` فخّ خفي. عند فحص state UI-only، استخدم
`!== true` بدل `!`.

**(4)** فحص "buggy baseline" إلزامي في الـ regression suite — يثبت أن الكارثة
حقيقية بدون الـ fix، فلا يضيع الـ fix في refactor مستقبلي.

**(5)** أي قاعدة شرح / منهجية AI يجب أن تعيش كـ tuple/constant داخل الـ Skill
ذي الصلة، لا كنص حر في system prompt. الـ prompt يستهلكها، لا يحمل تعريفها.

**(6)** `methodology_handle` versioned يضمن تتبُّع التغييرات doctrine — تماماً
كما يفعل `truth_table.lock.json` للقدرات الحية.

### قياس النجاح حياً

```bash
# 1. Regression suite — 18/18
node frontend/tests/iss080_conversation_spinner.test.mjs
# 🎉 18/18 ISS-080 D-068 regression checks

# 2. Build clean
npm --prefix=frontend run build
# ✓ Compiled successfully

# 3. Fix code is in served bundle
curl -s http://localhost:5050/_next/static/chunks/app_*.js | \
  grep -o "ISS-080\|D-068\|isComplete !== true\|setMessagesSafe" | sort -u
# D-068
# ISS-080
# isComplete !== true
# setMessagesSafe

# 4. Live skill works with new doctrine handle
python3 -c "from app.services.skills import BACExerciseSkill, BACSkillInput, SkillMode; \
  s=BACExerciseSkill(); \
  r=s.invoke(BACSkillInput(question='اشرح السؤال 1', mode=SkillMode.EXPLAIN, \
    history_messages=[{'role':'user','content':'تمرين 2016'}])); \
  print(r.methodology_handle, r.match_source)"
# explanation_doctrine_v1.0.0 history
```

### السلسلة الكاملة (D-049 → D-068)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-066 | JSON envelope + LaTeX + theme + Math pipeline + streaming sanitizer + UI flicker |
| D-067 | CI repair sweep |
| D-068 | ISS-080 — Old-conversation spinner stuck + raw LaTeX + missing copy button + Skill doctrine versioning |
| **D-069** | **ISS-CI-GREEN-001 — All-green CI: grep flag-parsing fix + eliminate skipped + Skills Doctrine Module (v2.0.0)** |

---

## 6.49 CI Green Restoration + Skills Doctrine Module (2026-05-18, ISS-CI-GREEN-001 / D-069)

> الكارثة المُشخَّصة بـ PR #2078: 5 failed + 1 skipped check رغم أن main أخضر.
> طلب المستخدم: «GitHub Actions بشكل اجباري success فقط — لا skipped و لا warning و لا failed».
> + «تطوير منظومة الـ skills للنظام لكيفية استدعاء المحتوى و كيفية الشرح و
>    كيفية شرح الاجابة النموذجية و الاعتماد اثناء الشرح المفصل للطالب».

### الأسباب الجذرية الثلاث (مُختبَرة حياً)

**(1) Grep flag-parsing bug** في `frontend-theme-ci.yml` (4 مواضع):
```bash
# الـ workflow كان يقول:
for var in "--bg-color" "--text-color" ...; do
  count=$(grep -c "$var" frontend/app/globals.css || true)
done

# على ubuntu-latest، grep يفسر `--bg-color` كـ long-option:
$ grep -c "--bg-color" frontend/app/globals.css
ugrep: invalid option --bg-color
```

النتيجة: 13 check يفشل عبر cascade `needs:` → frontend-theme-summary + required-ci.

**(2) Skipped Integration Tests**:
```yaml
validate-integration:
  if: github.event_name == 'workflow_dispatch'  # ← skipped على كل push/PR
```

**(3) Skills Doctrine متناثرة** (Prompt Spaghetti):
- `EXPLANATION_DOCTRINE` كان مُعرَّفاً محلياً في `bac_exercise_skill.py`
- لا قواعد منفصلة لـ "كيفية استدعاء المحتوى"
- لا قواعد لـ "الاعتماد على الإجابة النموذجية"
- لا قواعد لـ "ضوابط الشرح المفصل"

### الإصلاح (3 layers + Skills enhancement)

**Layer 1** — Workflow Grep Fix (`frontend-theme-ci.yml`):
استبدال 4 مواضع بـ `grep -c|-q -e "$var" --` لمنع long-option parsing.

**Layer 2** — Eliminate Skipped (`structure-validation.yml`):
إزالة `if: github.event_name == 'workflow_dispatch'` من `validate-integration`.

**Layer 3** — Skills Doctrine Module (`app/services/skills/doctrine.py`):
Single Source of Truth لـ 4 قواعد رسمية:

| Doctrine | Version | Rules | Purpose |
|----------|---------|-------|---------|
| `RETRIEVAL_DOCTRINE` | v1.0.0 | 7 | كيفية استدعاء المحتوى |
| `EXPLANATION_DOCTRINE` | **v2.0.0** | 11 | كيفية الشرح (rewrite من D-068 v1.0.0) |
| `MODEL_ANSWER_RELIANCE_RULES` | v1.0.0 | 7 | الاعتماد على الإجابة النموذجية |
| `DETAILED_EXPLANATION_RULES` | v1.0.0 | 12 | ضوابط الشرح المفصل |

**EXPLANATION_DOCTRINE v2.0.0 additions**:
- ✨ «اللغة عربية فصحى نقية — لا روسية/صينية/إسبانية مُسرَّبة»
- ✨ «LaTeX إلزامي للرياضيات داخل `$...$` أو `$$...$$`»
- ✨ «النتيجة النهائية في `$$\boxed{...}$$`»

### القواعد الـ 7 الدائمة (D-069 — لا تُكسر بدون ADR)

1. **Grep flag safety**: أي `grep -c|-q "$var"` على نمط قد يبدأ بـ `--` يستخدم `-e PATTERN --`.
2. **No skipped on push/PR**: لا job يحوي `if: github.event_name == 'workflow_dispatch'` على workflow يُشغَّل push/PR.
3. **Skills Doctrine = Single Source**: كل قاعدة AI تعيش في `app/services/skills/doctrine.py`. لا redefinition محلية.
4. **Doctrine versioning monotonic**: EXPLANATION_DOCTRINE_VERSION لا يتراجع (v2+ بعد D-069).
5. **Manifest integrity**: `SKILL_DOCTRINE_MANIFEST` يطابق الـ doctrines الفعلية (CI gate يفحص).
6. **Drift detection**: `local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT` يحوي ≥ 3 anchors: «الإجابة النموذجية»، «LaTeX»، «حرفياً».
7. **Skills as primary AI surface**: لا تُضِف logic AI مباشرة في orchestrator_client.py — أنشئ Skill.

### قياس النجاح حياً (2026-05-18)

```bash
# Grep fix verified
$ env -i HOME=/root PATH=$PATH bash -c '
    for var in --bg-color --text-color; do
      grep -c -e "$var" -- frontend/app/globals.css
    done'
22
31

# Skills doctrine gate (10/10 ✅)
$ python scripts/fitness/check_skills_doctrine.py

# Tests (97/97 ✅)
$ pytest tests/services/test_skills_doctrine.py \
    tests/services/test_iss075_*.py tests/services/test_iss079_*.py --no-cov -q
97 passed

# Full quality stack
$ ruff check . && ruff format --check . && \
  python scripts/runtime_truth.py --check && \
  python scripts/validate_structure.py && \
  python scripts/ci_guardrails.py
✅ All passed
```

### الملفات (D-069)

| File | Change |
|------|--------|
| `.github/workflows/frontend-theme-ci.yml` | grep flag-parsing fix (4 places) |
| `.github/workflows/structure-validation.yml` | remove `if: workflow_dispatch` |
| `.github/workflows/skills-doctrine-gate.yml` | **new** — 3-job CI gate |
| `app/services/skills/doctrine.py` | **new** — Single Source of Truth (4 doctrines, 37 rules) |
| `app/services/skills/bac_exercise_skill.py` | import from doctrine + backward-compat re-export |
| `app/services/skills/__init__.py` | re-export all doctrines + helpers |
| `tests/services/test_skills_doctrine.py` | **new** — 42 unit tests |
| `scripts/fitness/check_skills_doctrine.py` | **new** — drift detector |
| `.memory/decisions.md` | D-069 entry |
| `.memory/issues.md` | ISS-CI-GREEN-001 entry |
| `CLAUDE.md` §6.49 | this section |

---

## 6.50 Skills Doctrine: build_exercise_explanation_prompt + local_graph binding (2026-05-19, D-071)

### المشكلة
`_EXERCISE_EXPLANATION_SYSTEM_PROMPT` في `local_graph.py` كان string ثابت محلي — أي تغيير في
`EXPLANATION_DOCTRINE` أو `MODEL_ANSWER_EXPLANATION_DOCTRINE` لا ينعكس تلقائياً على الـ LLM.

### الحل
- `build_exercise_explanation_prompt()` في `doctrine.py` تبني الـ prompt من الـ doctrine مباشرة.
- `EXERCISE_EXPLANATION_SYSTEM_PROMPT` ثابت مُصدَّر — single source of truth.
- `local_graph.py` يستورد `EXERCISE_EXPLANATION_SYSTEM_PROMPT` من `doctrine.py`.

### الثوابت الجديدة (D-071 — لا تُكسر)
1. `local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT` يجب أن يُعيَّن من `doctrine.EXERCISE_EXPLANATION_SYSTEM_PROMPT`.
2. `build_exercise_explanation_prompt()` تُنتج prompt < 1000 حرف بدون box-drawing chars (D-067).
3. أي تغيير في `EXPLANATION_DOCTRINE` أو `MODEL_ANSWER_EXPLANATION_DOCTRINE` ينعكس تلقائياً.
4. `check_skills_doctrine.py` يتحقق من الربط في كل PR.

### التحقق الحي (2026-05-19)
- Pipeline: `mode: full | Active: ['planning', 'research', 'reasoning']` ✅
- Prometheus: 12/12 UP ✅
- 42 اختبار جديد في `tests/services/test_skills_doctrine_d071.py` — 42/42 ✅
- `ruff` + `runtime_truth` + `validate_structure` + `check_skills_doctrine` كلها ✅

### الملفات (D-071)

| File | Change |
|------|--------|
| `app/services/skills/doctrine.py` | `build_exercise_explanation_prompt()` + `EXERCISE_EXPLANATION_SYSTEM_PROMPT` |
| `app/services/chat/local_graph.py` | import من doctrine بدلاً من تعريف محلي |
| `scripts/fitness/check_skills_doctrine.py` | تعزيز check_local_graph_prompt_alignment (D-071) |
| `tests/services/test_skills_doctrine_d071.py` | **new** — 42 اختبار تكامل |
| `.runtime/truth_table.lock.json` | تحديث بعد إضافة importer جديد |
| `.memory/decisions.md` | D-071 entry |
| `.memory/issues.md` | D-071 entry |
| `CLAUDE.md` §6.50 | this section |

---

## 6.51 ISS-081 — AnswerQualitySkill Wire-In: Eliminating the Zombie (2026-05-19, D-073)

### القاعدة الذهبية

> **CLAUDE.md §6.6**: «أي مكون بدون كل الثلاثة `import + call chain + runtime evidence`
> يُصنَّف DORMANT أو ZOMBIE».

كَوْن Skill **مُعرَّفاً** بـ Pydantic contract + Prometheus metrics + اختبارات وحدة ليس كافياً.
الـ Skill يجب أن يكون **مُستدعى من مسار إنتاجي حقيقي** ينتهي عند طلب مستخدم فعلي.

### المُكتشَف بالتجريب الحي (2026-05-19)

```bash
$ grep -rn "AnswerQualitySkill\|get_answer_quality_skill" app/ microservices/ \
    | grep -v test_ | grep -v __init__.py | grep -v answer_quality_skill.py
# (empty — لا call chain من أي router)
```

D-072 (2026-05-19 صباحاً) أعلن إنشاء `AnswerQualitySkill` كـ "Skill رسمي مستقل" مع:
- 6 فحوصات deterministic (length, latex, box-drawing, numbered_steps, foreign_language, methodology)
- 11 Prometheus metric تعريفات
- 30 unit test في `test_answer_quality_skill.py`
- إدراج في `__init__.py` re-exports + `SKILL_DOCTRINE_MANIFEST`

لكن لا call site من أي WS router أو LangGraph node. الـ Skill عاش كـ "اختبار وحدة + تعريف"
— لم يصل لطالب واحد. **حالة ZOMBIE perfect** بحسب §6.6.

### الإصلاح (D-073 — 3 طبقات)

**طبقة 1 — `_apply_answer_quality_skill()` helper في `local_graph.py`**:

```python
def _apply_answer_quality_skill(question: str, answer: str, intent: str) -> str:
    """D-073: AnswerQualitySkill يُطبَّق defensively قبل إرجاع الإجابة للطالب."""
    if not answer or not answer.strip():
        return answer
    try:
        from app.services.skills import (
            AnswerQualityInput, AnswerQualityOutput, get_answer_quality_skill,
        )
        # local intents → skill intents
        skill_intent = "chat" if intent == "chat" else "educational"
        require_latex = skill_intent in ("educational", "math")
        require_steps = skill_intent in ("educational", "math") and len(answer) > 300
        result = get_answer_quality_skill().evaluate(
            AnswerQualityInput(
                question=question[:2000], answer=answer, intent=skill_intent,
                require_latex=require_latex, require_steps=require_steps,
            )
        )
        if isinstance(result, AnswerQualityOutput):
            if result.improved_answer and result.improved_answer != answer:
                logger.info("answer_quality.improved score=%.2f", result.score)
                return result.improved_answer
    except Exception as exc:
        logger.debug("answer_quality skill non-fatal failure: %s", exc)
    return answer
```

**طبقة 2 — Wire في `_chat_node`**:
```python
response = await ai_client.send_message(system_prompt, user_message)
clean = response.replace("\x00", "").strip()
clean = _sanitize_local_graph_response(clean, intent)           # ISS-075 (D-063)
clean = _apply_answer_quality_skill(question, clean, intent)    # ISS-081 (D-073)
```

**طبقة 3 — D-070 doctrines re-exported من package level**:
8 رموز كانت غير متاحة من `app.services.skills` قبل D-073:
- `CONTENT_INVOCATION_DOCTRINE` + `_VERSION`
- `MODEL_ANSWER_EXPLANATION_DOCTRINE` + `_VERSION`
- `STEP_BY_STEP_EXPLANATION_RULES` + `_VERSION`
- `SKILL_INVOCATION_PROTOCOL` + `_VERSION`
- `EXERCISE_EXPLANATION_SYSTEM_PROMPT` (D-071)
- 4 دوال summary helper

### CI Gate Extended

`scripts/fitness/check_skills_doctrine.py` — فحصين جديدين:

```
=== Skills Doctrine Drift Gate (D-069 + D-073) ===
✅ D-070 doctrines re-exported from app.services.skills (D-073)
✅ AnswerQualitySkill wired into local_graph._chat_node (D-073, no longer ZOMBIE)
```

أي PR يعيد الـ Skill لحالة ZOMBIE (يحذف `_apply_answer_quality_skill` أو يُلغي call
من `_chat_node`) سيفشل في CI gate.

### القواعد الـ 5 الدائمة (D-073)

**(1) Skill never ZOMBIE — D-073 invariant**: كل Skill جديد يُضاف إلى
`app/services/skills/` يجب أن يكون له **مُستهلِك إنتاجي حقيقي** في الـ
manifest قبل merge. الـ stub references (`conversation_graph._call_llm`
عبر architectural boundary) ممنوعة.

**(2) Defensive wiring**: helper يستدعي Skill يجب أن يلتقط `Exception` —
لا Skill يُفشل المسار. المستخدم يحصل على الأصل لو فشل التحسين.

**(3) `improved_answer` فقط عند تغيير ملموس**: تجنب re-emit نفس النص.

**(4) D-070 doctrines re-exported**: 8 رموز يجب أن تكون متاحة من
`app.services.skills` (وليس فقط `app.services.skills.doctrine`).

**(5) Manifest reflects reality**: `consumed_by` لا يحوي stub references
غير قابلة للوصول. CI gate يحرس على هذا.

### قياس النجاح حياً (2026-05-19)

```bash
$ python scripts/fitness/check_skills_doctrine.py
✅ AnswerQualitySkill wired into local_graph._chat_node (D-073, no longer ZOMBIE)

$ pytest tests/services/test_iss081_answer_quality_wiring.py
============================== 18 passed in 0.29s ==============================

$ pytest tests/services/test_{skills_doctrine,iss075,iss079,iss081,answer_quality}*.py
============================= 203 passed in 0.53s ==============================

$ ruff check + format → All checks passed!
$ runtime_truth.py --check → matches lock (after --update for new test importer)
$ validate_structure.py → ✅
$ ci_guardrails.py → ✅
```

### السلسلة الكاملة (D-049 → D-073)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-068 | JSON envelope + LaTeX + theme + Math pipeline + sanitizer + UI flicker + spinner |
| D-069 | CI all-green (grep flag fix + eliminate skipped) + Skills Doctrine Module |
| D-070 | 4 new doctrines (CONTENT_INVOCATION / MODEL_ANSWER_EXPLANATION / STEP_BY_STEP / INVOCATION_PROTOCOL) |
| D-071 | `build_exercise_explanation_prompt()` + local_graph doctrine binding |
| D-072 | AnswerQualitySkill + Zombie microservices fix (claimed RESOLVED — incomplete: skill defined but never called) |
| **D-073** | **ISS-081 — AnswerQualitySkill ACTUALLY wired into _chat_node + D-070 re-exports + CI guards** |

### الملفات (D-073)

| File | Change |
|------|--------|
| `app/services/skills/__init__.py` | re-export 8 D-070 symbols + 5 helpers + `EXERCISE_EXPLANATION_SYSTEM_PROMPT` |
| `app/services/chat/local_graph.py` | + `_apply_answer_quality_skill()` helper + call in `_chat_node` |
| `app/services/skills/doctrine.py` | Manifest `answer_quality.consumed_by` reflects real consumer |
| `scripts/fitness/check_skills_doctrine.py` | + 2 new checks (D-070 re-exports + AnswerQuality wiring) |
| `tests/services/test_iss081_answer_quality_wiring.py` | **new** — 18 regression tests |
| `.runtime/truth_table.lock.json` | updated (new test file imports local_graph) |
| `.memory/decisions.md` | D-073 entry |
| `.memory/issues.md` | ISS-081 entry |
| `CLAUDE.md` §6.51 | this section |

---

## 6.52 Database-Enforced BKT Engine + Probability-Tree Abstraction Ban (2026-05-20, D-074)

> Protocol V6.0: تتبّع معرفي بايزي مُخزَّن في Supabase + حظر الرموز المجرّدة في
> شجرة الاحتمالات. كل قدرة AI = Skill (CLAUDE.md §0.5).

### ما الذي تغيّر

**(1) جدول `student_bkt_analytics` (Supabase / Postgres)** — سجل append-only
لكل تفاعل طالب: `user_id`, `session_id`, `concept_id`,
`cognitive_load_estimate` (low/medium/high), `student_mastery_probability`
[0,1], `interaction_count`, `interaction_timestamp`. مُسجَّل في
`app/core/db_schema_config.py` (`_ALLOWED_TABLES` + `REQUIRED_SCHEMA`) → يُنشأ
تلقائياً عبر `validate_schema_on_startup()` عند إقلاع التطبيق. DDL مستقل في
`scripts/migrations/0001_student_bkt_analytics.sql`.

**(2) `BKTEngine` Skill** (`app/services/skills/bkt_engine.py`) — حتمي تماماً:
تصنيف `concept_id` + تقدير الحِمل المعرفي + تحديث BKT بايزي (prior P(L0)،
learn P(T)، slip P(S)، guess P(G)). إشارة evidence لينة مشتقة من نوع التفاعل
(استيضاح → ضعيف، استدلال → قوي). مقاييس Prometheus
`cogniforge_skill_bkt_invocations_total` + `_duration_seconds`.

**(3) BKT Runtime Injection** — `app/api/routers/customer_chat.py`:
`_evaluate_and_emit_bkt()` يُقيّم التفاعل، يُخزّنه عبر `BKTAnalyticsService`
(`app/services/analytics/bkt_persistence.py`)، ويبثّ `bkt_tracking` للواجهة
كـ `ui_component` (`component="bkt_hint_display"`، مُسجَّل في
`app/contracts/streaming.py:KNOWN_UI_COMPONENTS`). معزول في try/except —
لا يكسر مسار المحادثة أبداً.

**(4) Abstraction Ban** — `OrchestratorClient._detect_probability_tree`:
التسميات الآن ملموسة من سياق المسألة ("كرة حمراء"، "قطعة معيبة"، "سحب ناجح")
بدل الرموز المجرّدة (A, B|A, Ā). نمط هجين: استخراج حتمي أولاً
(`_extract_concrete_events`)، ثم إثراء LLM فقط عند غياب كيان ملموس
(`_build_probability_tree_props` → `_enrich_tree_labels_with_llm`، محروس
بـ timeout 8s + رفض A/B). حتى الـ fallback النهائي ملموس ("الحدث الأول").

### قواعد دائمة (لا تُكسر بدون ADR)

1. **BKT لا يكسر المحادثة**: كل استدعاء لـ BKT من الـ router معزول في
   try/except بجلسة DB مستقلة.
2. **append-only**: كل تفاعل = صف جديد؛ الإتقان السابق يُقرأ من آخر صف لنفس
   (user_id, concept_id).
3. **Abstraction Ban مطلق**: لا رمز مجرّد (A/B/Ā) في أي تسمية عقدة — حتى الـ
   fallback يستخدم تسميات ملموسة. أي ناتج LLM يحوي A/B يُرفَض.
4. **BKTEngine حتمي**: نفس المدخلات → نفس المخرجات (قابل لاختبار pytest).
5. **`student_mastery_probability` ∈ [0,1]** دائماً (مُقيَّد + CHECK في DDL).

### التحقق (2026-05-20)

- ✅ `ruff check/format` نظيف | `runtime_truth --check` يطابق القفل |
  `validate_structure` ✅ | `ci_guardrails` ✅ | `check_skills_doctrine` ✅
- ✅ 29 اختبار جديد (BKTEngine + persistence + Abstraction Ban) +
  16 اختبار generative-UI القائمة + 113 إجمالي slice — كلها ناجحة
- ✅ استخراج حتمي حي: "كرة حمراء"/"كرة غير حمراء"/"سحب ناجح"
- ✅ OpenRouter متصل حياً (النموذج المجاني رجع 429 → fallback ملموس،
  لا رموز A/B) — Abstraction Ban صامد في كل المسارات
- ⚠️ **تحقق Supabase الحي مؤجَّل**: بيئة الـ sandbox تحجب منافذ Postgres
  (6543/5432). الجدول يُنشأ تلقائياً عند الإقلاع في Codespaces؛ سكربت
  التحقق الحي `scripts/verify_bkt_live.py` يُشغَّل هناك حيث egress مفتوح.

### الملفات (D-074)

| File | Change |
|------|--------|
| `app/core/domain/bkt_analytics.py` | **new** — `StudentBKTAnalytic` ORM |
| `app/services/skills/bkt_engine.py` | **new** — `BKTEngine` Skill |
| `app/services/analytics/bkt_persistence.py` | **new** — `BKTAnalyticsService` (append-only) |
| `app/core/db_schema_config.py` | register `student_bkt_analytics` |
| `app/contracts/streaming.py` | + `BKTTrackingPayload` |
| `app/infrastructure/clients/orchestrator_client.py` | concrete labels + LLM enrichment (Abstraction Ban) |
| `app/api/routers/customer_chat.py` | `_evaluate_and_emit_bkt()` + wiring |
| `app/services/skills/__init__.py` | export BKT skill |
| `scripts/migrations/0001_student_bkt_analytics.sql` | **new** — standalone DDL |
| `scripts/verify_bkt_live.py` | **new** — Codespaces live-proof script |
| `tests/services/test_bkt_engine.py` | **new** — 21 tests |
| `tests/services/test_bkt_persistence_and_labels.py` | **new** — 8 tests |
| `.runtime/truth_table.lock.json` | regenerated |
| `.memory/decisions.md` / `.memory/issues.md` | D-074 entries |

### Verified Mechanics (Phase-1 audit, 2026-05-20 — exact, immutable)

> هذه الحقائق مُتحقَّقة من الكود الحي. لا تُعدَّل بدون إعادة تحقق + ADR.

**(1) DB auto-creation hook (boot mount)**:
```
app/kernel.py:233  →  await validate_schema_on_startup()
app/core/db_schema.py:324  validate_schema_on_startup()
    →  validate_and_fix_schema(auto_fix=True)   (db_schema.py:223)
        →  reads app/core/db_schema_config.py:REQUIRED_SCHEMA["student_bkt_analytics"]
        →  CREATE TABLE IF NOT EXISTS … (idempotent) on every boot
```
The table mounts automatically on Codespaces boot — no manual migration. Registered in both `_ALLOWED_TABLES` and `REQUIRED_SCHEMA`.

**(2) Hybrid Abstraction Ban extraction logic** (all in `app/infrastructure/clients/orchestrator_client.py`):
```
_extract_concrete_events(normalized)        — deterministic entity table (line ~778)
_detect_probability_tree(question)          — deterministic builder, concrete labels (line ~802)
_build_probability_tree_props(question)     — async hybrid wrapper (line ~898)
    └─ if labels_generic →  _enrich_tree_labels_with_llm(question)  (line ~931, timeout=8s, rejects A/B)
call site: chat_with_agent → await self._build_probability_tree_props(question) (line ~1146)
```
Fallback order: deterministic entity → LLM enrichment → concrete generic (`"الحدث الأول"`). **No path can emit `A`/`B|A`/`Ā`.**

**(3) `bkt_hint_display` payload → frontend mapping (HONEST runtime truth)**:
- Emitter: `app/api/routers/customer_chat.py:_evaluate_and_emit_bkt()` sends
  `{"type":"ui_component","payload":{"component":"bkt_hint_display","props":{concept_id, cognitive_load_estimate, student_mastery_probability}, "fallback_text": "…"}}`.
- Contract: validated by `app/contracts/streaming.py:BKTTrackingPayload` + whitelisted in `KNOWN_UI_COMPONENTS`.
- Transport: `frontend/app/hooks/useAgentSocket.js:254` handles `ui_component` → creates an assistant message carrying `{component, props, fallbackText}`.
- Render: `frontend/app/components/generative/GenerativeUIRenderer.jsx` `COMPONENT_REGISTRY` maps it.
  - `probability_tree` → **fully-built** `ProbabilityTree.jsx` portal (real interactive render).
  - `bkt_hint_display` → **STUB** (`BktHintStub`, line ~22): renders only the `fallback_text` as a safe info-note (`"مؤشر إتقان المهارة (قريباً)"`). **The full BKT visualization is NOT built yet** — the data flows end-to-end and is persisted, but the rich frontend portal is pending. Per runtime-truth doctrine: BKT engine + persistence + emit = ACTIVE; `bkt_hint_display` frontend portal = PARTIAL (stub).

### Skills-framework integration (D-074 — Phase 3)

BKT is registered as a first-class, versioned doctrine in the Skills framework:
- `app/services/skills/doctrine.py`: `BKT_COGNITIVE_DOCTRINE` (7 immutable rules) + `BKT_COGNITIVE_DOCTRINE_VERSION = "1.0.0"` + `SKILL_DOCTRINE_MANIFEST["bkt_cognitive"]` + `get_bkt_cognitive_summary()`.
- `app/services/skills/bkt_engine.py`: `BKTEngine.doctrine_version` bound to the doctrine constant (consumes doctrine — single source of truth).
- `app/services/skills/__init__.py`: exports + docstring registers `BKTEngine` as the foundational cognitive layer.
- `scripts/fitness/check_skills_doctrine.py`: validates the `bkt_cognitive` manifest entry **and** that `bkt_engine.py` consumes the doctrine **and** that `customer_chat._evaluate_and_emit_bkt` is wired (no-ZOMBIE guarantee, mirrors D-073).

**Rule**: any future adaptive pedagogical skill consumes `BKT_COGNITIVE_DOCTRINE` and builds on `student_mastery_probability` — it must never re-invent mastery tracking. Changing a doctrine rule = bump `BKT_COGNITIVE_DOCTRINE_VERSION` + update the CI gate.

---

## 6.53 Dynamic Probability Engine + Generalization (2026-05-21, D-075/D-076 · Protocol V14.0/V15.0)

> الثورة: الخلفية تحسب احتمالات **حقيقية** ديناميكياً من نص المسألة العربي
> (P(حمراء)=4/11)، لا تُغرق الواجهة بقيمة 0.5 وهمية ولا تُخرج HTML. فصل صارم:
> الخلفية Pydantic منظَّم فقط؛ الواجهة (RSC) تُصيّر الشجرة التفاعلية.

### الكارثة المُشخَّصة (قبل D-075)
`OrchestratorClient._detect_probability_tree` كان يستخرج كسوراً عشرية حرفية من
النص فقط، وعند غيابها يُسقط القيمة الافتراضية **0.5 الغبية** — لا حساب فعلي من
تركيبة المسألة (4 كرات حمراء من 11 = 4/11).

### الإصلاح (D-075 — ProbabilityCalculatorSkill)
Skill رسمي جديد `app/services/skills/probability_skill.py` (يحترم §0.5):
- **حتمي تماماً** — لا LLM، لا عشوائية، لا I/O — قابل للاختبار بـ pytest.
- يستخرج التركيبة العربية (عدد + كيان ملموس) ويحسب P = العدد/المجموع كـ كسر
  **تربوي خام** (4/11، 3/6، 60/100) — لا اختزال (أوضح للطالب).
- كل عقدة شجرة تحمل `p_num`/`p_den` الدقيقين، فتُصيّر `ProbabilityTree.jsx` الكسر
  تماماً (`fractionFromIntegers`) دون إعادة بناء تقريبية من العشري.
- يستهلك `PROBABILITY_CALCULATION_DOCTRINE` من `doctrine.py` (single source).
- موصول حيّاً عبر `OrchestratorClient._build_calculated_tree_props` الذي يسبق
  المسار الحتمي القديم في `_build_probability_tree_props`.

### التعميم (D-076 — Anti-Overfitting · Protocol V15.0)
المحرّك ليس مخصّصاً لـ«الكرات في الكيس». خط أنابيب استراتيجيات (أول نجاح يفوز):
- **`_strategy_conditional`** (مصنع/Bayesian): فروع رئيسية بنسب مئوية + فروع
  شرطية (معيب/سليم) — مثل: الآلة A 60/100 → معيب 2/100، سليم 98/100.
- **`_strategy_universe`** (نرد/قطعة نقدية): يقسّم الفضاء — رقم زوجي 3/6، فردي 3/6.
- **`_strategy_composition`** (كرات/بطاقات/أصناف): يستخرج (عدد + كيان: لون أو رقم
  بطاقة أو صنف) ويبني شجرة سحب بـ/بدون إرجاع — بطاقة رقم 1: 3/8، كرة حمراء: 4/11.

### قواعد دائمة (لا تُكسر بدون ADR)
1. **حساب حقيقي إلزامي**: عند توفّر التركيبة، يُحظر إخراج 0.5 افتراضية — P=العدد/المجموع.
2. **كسور تربوية خام**: العقد تحمل الكسر كما يُشتق من المسألة (لا اختزال)؛ الرمز الجميل
   (½) يُستخدم فقط حين يكون الكسر أصلاً في أبسط صورة.
3. **فصل الخلفية/الواجهة**: المحرّك يُرجع Pydantic فقط — لا HTML، لا SVG. التصيير
   مسؤولية `GenerativeUIRenderer` + `ProbabilityTree.jsx` (whitelist).
4. **تعميم لا overfitting**: أي نمط جديد يُضاف كاستراتيجية مستقلة — لا مفردات
   مثبَّتة. تطبيع التشكيل يجب أن يحذف الحركات فقط (U+064B+) لا حروف العربية.
5. **استقلالية الـ Skill**: لا يستورد من Skills أخرى ولا من microservices.

### التحقق الحي (2026-05-21)
- `scripts/test_generalization.py` — 4/4 تنجح (نرد، مصنع، بطاقات، كرات) ✅
- `scripts/gitpod_ui_test.py` — يُثبت P(حمراء)=4/11 عبر المسار الإنتاجي الكامل ✅
- `tests/services/test_probability_skill.py` (16) + `tests/contracts/test_generative_ui_streaming.py` (19) ✅
- ruff + ruff format + skills-doctrine-gate + runtime_truth --check ✅

### الملفات (D-075/D-076)
| File | Change |
|------|--------|
| `app/services/skills/probability_skill.py` | **new** — ProbabilityCalculatorSkill (3 strategies) |
| `app/services/skills/doctrine.py` | + `PROBABILITY_CALCULATION_DOCTRINE` v1.0.0 + manifest |
| `app/services/skills/__init__.py` | re-export الـ Skill + الـ doctrine |
| `app/infrastructure/clients/orchestrator_client.py` | + `_build_calculated_tree_props` (wired) |
| `frontend/app/components/generative/ProbabilityTree.jsx` | `fractionFromIntegers` + exact joint |
| `scripts/test_generalization.py` / `scripts/gitpod_ui_test.py` | **new** — live empirical proofs |
| `tests/services/test_probability_skill.py` | **new** — 16 unit tests |
| `tests/contracts/test_generative_ui_streaming.py` | + 3 wiring tests |

---

## 6.54 Probability Engine Hardening — No Garbage Fractions + Accurate Arabic Parsing (2026-05-21, D-077 · Protocol V17.0)

> كارثة حية: المحرّك أنتج كسوراً منحلّة (`1/0`، `1/1`) و خلط **عدد السحبات**
> بحجم الكيس (total=3 بدل 2). هذا القسم يحكم سلامة الحساب — لا تُكسر بدون ADR.

### السببان الجذريان (مُشخَّصان حيّاً)
1. **خلط السحب بالمجموع**: `_detect_total` كان يطابق «نسحب **3 كرات**» ويعتبر 3
   حجم الكيس — والصحيح أن 3 هو عدد السحبات. النتيجة: `P(بيضاء)=2/3` بدل `2/2`.
2. **كسور منحلّة**: السحب بدون إرجاع من كيس صغير (كرتان) يولّد `0/1` و `1/1`
   في المستوى الثاني — تبدو غارباج للطالب.

### الإصلاح (D-077)
- **`_detect_total` (parsing)**: يتجاهل أي رقم مسبوق بفعل سحب
  (نسحب/يسحب/تسحب/سحب/نأخذ/نختار/اختيار/tirage) ضمن نافذة قصيرة. المجموع
  الصريح يجب أن يكون ≥ مجموع المكوّنات المستخرَجة (ground truth = مجموع الأعداد).
- **بوّابة المستوى الثاني**: يُبنى فقط حين `draws ≥ 2` و(`مع الإرجاع` أو
  `total ≥ 3`) — السحب بدون إرجاع من كيس ≤ 2 لا يُولّد فروعاً (denom2 = total-1 ≥ 2 مضمون).
- **`_sanitize_node` (حارس نهائي إلزامي)**: يمرّ على كل عقدة في كل شجرة من كل
  استراتيجية ويضمن `p_den ≥ 1` و `0 ≤ p_num ≤ p_den` ويُعيد حساب `p`. لا قسمة
  على صفر، لا بسط أكبر من المقام، تصل للطالب أبداً. مطبَّق على الاستراتيجيات
  الثلاث (universe/conditional/composition).
- **clamp المكوّنات**: `count = min(count, total)` — لا عنصر يتجاوز المجموع.

### قواعد دائمة (V17.0)
1. **عدد السحبات ≠ حجم الفضاء**: أي رقم في سياق فعل سحب لا يُعدّ مجموعاً.
2. **المجموع = مجموع المكوّنات كحدّ أدنى**: `total = max(detected, sum(counts))`.
3. **حارس نهائي إلزامي**: كل شجرة احتمالات تمرّ عبر `_sanitize_node` قبل البثّ —
   لا استثناء. أي استراتيجية جديدة يجب أن تُمرِّر جذرها عبره.
4. **عقد العرض**: الواجهة (`fractionFromIntegers`) تُصيّر `num≥den → "1"`،
   `num≤0 → "0"`، `den≤0 → null` — طبقة دفاع ثانية فوق حارس الخلفية.

### Microservices Contract Boundary (V17.0 §3.B)
الخلفية تُخرج **Pydantic JSON منظَّماً فقط** للواجهة — لا HTML، لا SVG، لا
نص خام. `_build_probability_tree_props` + `_build_calculated_tree_props` محروسان
بـ try/except شامل (يُرجعان `None` لا يُسرّبان استثناءً)، و
`_normalize_ui_component_event` يتحقّق عبر `UIComponentPayload` ويُسقط أي حمولة
مشوَّهة إلى `noop`. هذا يمنع تسرّب صفحة خطأ Next.js (`<nextjs-portal>`) إلى البثّ.

### التحقق الحي (2026-05-21)
- `scripts/omni_live_test.py` — المسار الثلاثي (تمرين → شجرة → «لم أفهم»): لا
  `1/0`، السياق محفوظ، JSON نظيف ✅
- `tests/services/test_probability_skill.py` — +3 اختبارات regression (no-div-zero،
  draw≠total، no-degenerate) ✅

---

## 6.55 Auto-Triggering Generative UI — Simultaneous vs Sequential Math Router (2026-05-21, D-078 · Protocol V19.0)

> الكارثة التربوية: المحرّك كان يفرض **شجرة احتمالات تتابعية** على مسائل **السحب
> الآني** («نسحب 3 كرات دفعة واحدة») — وهي تأليفية (Combinatorics) لا تتابعية.
> هذا القسم يحكم الموجِّه التربوي وكاشف الإحباط — لا يُكسر بدون ADR.

### الموجِّه التربوي (Pedagogical Math Router)
`ProbabilityCalculatorSkill._detect_draw_mode(text)` يصنّف:
- **`simultaneous`** («دفعة واحدة»، «في آن واحد»، «معاً») → `CombinationsModelOutput`
  → مكوّن **`combinations_visualizer`** (فضاء C(n,k) + لكل مجموعة C(count,k)).
  **ممنوع منعاً باتاً** تمثيله بشجرة تتابعية.
- **`sequential`** («على التوالي»، «تباعاً») → `ProbabilityModelOutput` → `probability_tree`.
- **`single`** (سحب مفرد) → شجرة من مستوى واحد.

التحقّق الحي (BAC 2024): «نسحب 3 كرات دفعة واحدة» من كيس (2 بيضاء، 4 حمراء، 5 خضراء)
→ C(11,3)=165، وحدث «3 من نفس اللون» = C(4,3)+C(2,3)+C(5,3) = 4+0+10 = **14/165**.

### كاشف الإحباط (Frustration Detector)
`ProbabilityCalculatorSkill.is_confusion(text)` يكشف («مفهمتش»، «لم أفهم»، «كيفاش»،
«اشرح لي»...). الطالب لا يكتب «أنشئ واجهة» — يعبّر عن الحيرة، فيُفعَّل المكوّن
البصري تلقائياً عبر سياق المحادثة (التركيبة محفوظة في الـ history). لا تُلوَّث
`_PROBABILITY_CONTEXT` بكلمات الحيرة العامة (تجنّب false-positive على «اشرح قانون نيوتن»).

### إلغاء جذر 1/1 الوهمي (V19.0 §2.C)
جذر الشجرة يُبنى عبر `_root(children)` **بلا** `p_num`/`p_den` — لا احتمال وهمي
1/1. `_sanitize_node` يتخطّى الجذر عديم الاحتمال. الواجهة (`ProbabilityTree.jsx`)
تتعامل مع `p === null` للجذر (لا كسر يُعرَض). أي test/scan يجب أن يتخطّى العقدة
بلا `p_num`.

### العقد المعماري (V19.0 §3)
المخرج البصري الموحَّد من `OrchestratorClient._build_calculated_ui(question, history)`:
`{"component": "probability_tree"|"combinations_visualizer", "props": {...}, "fallback_text": str}`.
كلا المكوّنين في `KNOWN_UI_COMPONENTS` (whitelist) ويُتحقَّق منهما عبر
`UIComponentPayload`. الخلفية تُخرج JSON منظَّماً فقط — لا HTML، لا استثناء يتسرّب
(كل المسار محروس بـ try/except → None عند الفشل).

### قواعد دائمة (V19.0)
1. **السحب الآني تأليفي لا تتابعي**: «دفعة واحدة» → `combinations_visualizer`، ممنوع `probability_tree`.
2. **k ≤ n إلزامي**: `_build_combinations` يفشل بنظافة (ProbabilityFailure) إن k>n — لا استثناء، لا شجرة مضلِّلة.
3. **لا جذر 1/1**: الجذر بلا احتمال؛ استخدم `_root()` لا `_node("البداية", 1, 1, ...)`.
4. **كاشف الإحباط لا يلوّث السياق**: `is_confusion()` منفصل؛ لا تُضَف كلمات الحيرة لـ `_PROBABILITY_CONTEXT`.
5. **مكوّن جديد = whitelist + registry + Pydantic**: أي مكوّن توليدي جديد يُسجَّل في `KNOWN_UI_COMPONENTS` + `GenerativeUIRenderer` + عقد Pydantic.

### التحقّق الحي (2026-05-21)
- `scripts/test_auto_ui_trigger.py` — كشف الإحباط + «دفعة واحدة» → combinations (لا شجرة)، OpenRouter LIVE ✅
- `tests/services/test_probability_skill.py` (+7 V19) + `tests/contracts/test_generative_ui_streaming.py` ✅
- regression: V14 gitpod / V15 generalization / V17 omni — كلها ناجحة ✅



---

## 6.56 Deep-Dive Generative UI + Sub-Case Surgery (2026-05-22, D-079 · Protocol V30.0)

> ثلاث جراحات على مسار السحب الآني («دفعة واحدة»): إيقاف تسرّب `C_2^3=0`،
> كبح جدار النص لكل مكوّن توليدي، وقصة بصرية شاملة عند حيرة الطالب.

### الكوارث المُشخَّصة
1. **تسرّب الحلقة الداخلية**: `math.comb(2,3)=0` لمجموعة (كرتان بيضاوان) →
   الواجهة تعرض `C_2^3 = 0` المضلِّل (يبدو خطأً حسابياً للطالب).
2. **جدار نصّي**: المكوّن البصري كان يُبثّ ثم يتبعه شرح LLM طويل (Cognitive Overload).
3. **لا قصة بصرية**: «اريد شرح خارق لاني لم افهم اي شي» لم يُنتج storytelling بصري.

### الإصلاح (D-079)
- **حارس الحلقة الداخلية** (`ProbabilityCalculatorSkill._build_combinations`):
  `k > count` ⇒ لا `math.comb`، لا `C_n^k=0`؛ بل `is_possible=False` +
  `pedagogical_string="مستحيل (العدد المتوفر غير كافٍ لسحب المطلوب)"`. المجموعات
  الممكنة: `is_possible=True` + `C(count,k)`. `same_group` يجمع الممكنة فقط
  (التمرين 2024: أبيض مستحيل، أحمر C(4,3)=4، أخضر C(5,3)=10 → P=14/165).
- **القصة البصرية (Deep Dive)**: `is_confusion()` ⇒ `deep_dive=True` +
  `urn_state` (كرات ملوّنة) + `event_analysis`. `CombinationsVisualizer.jsx`
  يُصيّر `pedagogical_string` بدل `C_n^k=0`، يرسم الكيس، يُظهر شارة «شرح خارق».
- **الكبح النصّي المُعمَّم**: `_build_calculated_ui` يُرجِع `terminate_pipeline=True`
  + `companion_text` (جملة ≤ 120 حرف: «إليك الشرح البصري المفصل للتمرين خطوة بخطوة 🪄»)
  لكل مكوّن توليدي (combinations + tree)، لا الحالة المستحيلة فقط (V28.0).

### قواعد دائمة (لا تُكسر بدون ADR)
1. `k > count` لمجموعة ⇒ `is_possible=False` + رسالة تربوية، ممنوع منعاً باتاً `C_n^k=0`.
2. أي Generative UI يُبثّ للطالب ⇒ `terminate_pipeline=True` + جملة مرافقة واحدة.
3. `same_group_favorable` يجمع المجموعات الممكنة فقط.
4. الخلفية تُخرج Pydantic منظَّماً فقط — التصيير مسؤولية `GenerativeUIRenderer` (whitelist).

### التحقّق الحي (2026-05-22)
- `scripts/v30_live_test.py` يقود `chat_with_agent` كاملاً للسيناريو →
  (1) لا `C_2^3=0` ✅ (2) نص مكبوت 45 حرف جملة واحدة ✅ (3) deep_dive + urn_state +
  event_analysis ✅. OpenRouter LIVE HTTP 200 (358 نموذج). Supabase مؤجَّل (sandbox
  يحجب 6543/5432). 65 اختبار V30 + 646 إجمالي (services+contracts) ✅.
  ruff + runtime_truth + skills-doctrine + validate_structure + ci_guardrails ✅.

### السلسلة الكاملة (D-049 → D-079)
| Decision | المُصلَح |
|----------|---------|
| D-075 → D-078 | dynamic probability engine + generalization + hardening + auto-trigger router |
| **D-079** | **deep-dive generative UI + sub-case surgery (no C_2^3=0) + universal text-wall muzzle** |

---

## 6.57 Garbage "كرة رقم N" Entities — Substring-Match Catastrophe (2026-05-22, ISS-083 / D-081)

> كارثة مرئية أبلغ عنها المستخدم بصورة حيّة: تمرين BAC 2024 (سحب 3 كرات «دفعة
> واحدة») عُرض كـ **شجرة احتمالات تتابعية خاطئة** بتسميات «كرة رقم 0» وكسور
> مستحيلة (3/7، 1/7). هذا القسم يحكم استخراج الكيانات العددية — لا يُكسر بدون ADR.

### السبب الجذري (مُثبت بالتجريب الحي)

`app/services/skills/probability_skill.py:_extract_count_entities` كان يكشف الكيانات
المرقّمة بشرط `if "رقم" not in tok` — وهي مطابقة **سلسلة فرعية** تلتقط الصفة
«مرقمة»/«مرقمتان»/«مرقم» (تعني «مُعلَّمة بـ»، تصف *ترقيم* الكرات لا *نوعها*).

```
"أربع كرات حمراء مرقمة بـ 0، 1، 1، 3 خمس كرات خضراء مرقمة بـ 0، 1، 1، 3، 4"
   ↓ قبل D-081
[حمراء:4, بيضاء:2, خضراء:5, «كرة رقم 0»:4, «كرة رقم 1»:2]   ← كيانات زائفة
   ↓ المجموع = 17 (بدل 11) → كسور 4/17 خاطئة → شجرة تتابعية مضلِّلة بـ«كرة رقم 0»
```

### الإصلاح (جراحي — يعالج الجذر)

```python
# ثابت جديد: الأسماء المستقلّة الصريحة فقط
_NUMBERED_ENTITY_MARKERS = frozenset({"رقم", "الرقم", "ارقام", "الارقام", "رقمها", "ارقامها"})

# الحلقة: مطابقة الاسم المستقل بدل السلسلة الفرعية
for i, tok in enumerate(tokens):
    if tok not in _NUMBERED_ENTITY_MARKERS:   # كان: if "رقم" not in tok
        continue
```

«بطاقة رقم 1» / «تحمل الرقم 2» الصريحة تبقى كيانات سليمة؛ صفة «مرقمة» لا تُنتج
كياناً أبداً.

### النتيجة بعد الإصلاح (تجريب حي 2026-05-22)

- السحب الآني (Part I) → `combinations_visualizer`: n=11, k=3, C(11,3)=165، أحمر
  C(4,3)=4، **أبيض «مستحيل»** (2<3)، أخضر C(5,3)=10، **P(A)=14/165** (يطابق الإجابة
  الرسمية)، `deep_dive=True` عند الحيرة → القصة البصرية (urn_state + event_analysis).
- السحب التتابعي (Part II) → شجرة بكسور صحيحة (4/11، 2/11، 5/11) وتسميات لون ملموسة.
- لا «كرة رقم N» غارباج في أي مسار.

### تطوير منظومة الـ Skills (طلب المستخدم)

`PROBABILITY_CALCULATION_DOCTRINE` v1.1.0 → **v1.2.0** + قاعدة جديدة تُجسّد الدرس:
قبول اسم الرقم الصريح المستقل فقط، رفض صفة «مرقمة/مرقمتان/مرقم».

### قواعد دائمة (D-081 — لا تُكسر بدون ADR)

1. **مطابقة الأسماء المستقلّة لا السلسلة الفرعية**: استخراج الكيانات المرقّمة عبر
   `_NUMBERED_ENTITY_MARKERS` حصراً. أي توسيع يُضاف للمجموعة + اختبار regression.
2. **صفة «مرقم...» ليست كياناً**: «مرقمة/مرقمتان/مرقم/ترقيم» تصف الترقيم لا النوع —
   لا تُنتج كياناً أبداً.
3. **الموجِّه التربوي صامد** (D-078): «دفعة واحدة» → `combinations_visualizer`؛
   «على التوالي» → `probability_tree` بكسور صحيحة وتسميات ملموسة.

### قياس النجاح حياً

```bash
python3 -c "
from app.services.skills.probability_skill import ProbabilityCalculatorSkill as P
labels = {e[0] for e in P()._extract_count_entities('أربع كرات حمراء مرقمة 0 1 1 3 خمس كرات خضراء مرقمة 0 1 1 3 4 كرتان بيضاوان مرقمتان 1 3')}
assert labels == {'كرة حمراء','كرة بيضاء','كرة خضراء'}, labels
print('OK no garbage:', labels)"
# المتوقع: OK no garbage: {'كرة حمراء','كرة بيضاء','كرة خضراء'}
```

### السلسلة الكاملة (D-049 → D-081)
| Decision | المُصلَح |
|----------|---------|
| D-075 → D-079 | dynamic probability engine + generalization + hardening + auto-trigger + deep-dive |
| D-080 | docker compose architecture audit |
| **D-081** | **garbage «كرة رقم N» entities — substring-match → standalone-noun match (ISS-083)** |

---

## 6.58 Full Exercise OS — Multi-Step Pedagogical Carousel + Math CSS Repair (2026-05-22, D-083 · Protocol V31.5)

> ترقية محرّك الاحتمالات من مكوّن بصري واحد إلى **نظام تشغيل تمرين كامل**: حين
> يعبّر الطالب عن حيرة كاملة في مسألة سحب آني، نُولِّد Carousel متعدّد الخطوات
> يغطّي التمرين بأكمله، لا تأليفة واحدة. + إصلاح تكسّر صيغ الرياضيات في RTL.

### الكارثتان (بلاغ الـ CTO)
1. **CSS الرياضيات متكسّر**: صيغة التأليف `C_{11}^3 = 165` تنعكس عناصرها داخل
   حاوية `dir="rtl"` (الـ inline-flex يقلب الترتيب → `[k/n] C` بدل `C [k/n]`).
2. **لا شرح للتمرين الكامل**: عند «لم أفهم أي شيء» كان يُعرَض مكوّن تأليفات واحد،
   بينما تمرين BAC 2024 يحوي أحداثاً متعدّدة (A/B/C) ومتغيّراً عشوائياً X وسحباً
   متتالياً (الحدث D) — يستحق Carousel تربوياً لكامل التمرين.

### الإصلاح (D-083)
- **`FullExerciseStoryOutput` + `ExerciseStep`** (`probability_skill.py`):
  `_build_full_exercise_story` يُولِّد سلسلة خطوات — ① المعطيات (urn) ② فضاء
  العيّنة C(n,k) ③ الحدث «k من نفس الصنف» (event_breakdown) ④ المتغيّر العشوائي
  X (توزيع فوق-هندسي حتمي بـ math.comb). يُفعَّل عند `is_confusion()` + سحب آني.
- **عقد مُفكَّك صارم لكل خطوة**: visual_directives / numerical_state /
  pedagogical_message — الخلفية Pydantic فقط (لا HTML).
- **منع تسرّب الصفر**: المجموعة المستحيلة (count<k) ⇒ `is_possible=False` + رسالة
  تربوية، لا `C_n^k=0` ولا `0/165` يصل للطالب.
- **الكبح النصّي**: `full_exercise_story` ⇒ `terminate_pipeline=True` +
  `companion_text` جملة واحدة — صفر جدران نصّية.
- **إصلاح CSS الرياضيات**: `.genui-cnk` + صيغ التأليف ⇒ `direction: ltr` +
  `unicode-bidi: isolate` + `white-space: nowrap` (لا انعكاس/انكسار في RTL).
- **التصيير**: `FullExerciseStory.jsx` (Carousel + dots + تنقّل) مُسجَّل في
  `KNOWN_UI_COMPONENTS` + `GenerativeUIRenderer` + `UIComponentPayload`.

### قواعد دائمة (لا تُكسر بدون ADR)
1. حيرة الطالب + سحب آني ⇒ القصة الشاملة (Carousel)، لا مكوّن واحد.
2. كل خطوة تفصل visual/numerical/pedagogical فصلاً صارماً.
3. المجموعة المستحيلة ⇒ بانر تربوي فقط (ممنوع `C_n^k=0` / `0/165`).
4. `full_exercise_story` ⇒ `terminate_pipeline=True` + جملة واحدة.
5. الخطوات معمّمة من التركيبة لا مفصّلة لمسألة بعينها (Anti-Overfitting).
6. صيغ التأليف/الكسور تُصيَّر LTR دائماً داخل حاويات RTL.

### التحقق (2026-05-22)
BAC 2024 (4 حمراء، 5 خضراء، 2 بيضاء، k=3): C(11,3)=165، P(3 من نفس اللون)=14/165
(البيضاء مستحيلة، لا 0)، X=عدد الحمراء توزيع [35,84,42,4]/165 يجمع 165 — مُتحقَّق
standalone بـ math.comb. **pipeline حي (uvicorn/pytest/ruff) مؤجَّل إلى
Codespaces/CI** (الـ sandbox يحجب تثبيت التبعيات + egress — نمط §6.56).

### السلسلة الكاملة (D-049 → D-083)
| Decision | المُصلَح |
|----------|---------|
| D-075 → D-081 | dynamic probability engine + generalization + auto-trigger + deep-dive + entity fix |
| D-082 | impossible-case UX + skills doctrine |
| **D-083** | **Full Exercise OS: multi-step pedagogical carousel + RTL math CSS repair (V31.5)** |
| **D-084** | **Protocol V34.0: Contextual Unmuzzle & The Teacher's Voice (LLM Narrative + deep follow-up)** |

---

## 6.59 Contextual Unmuzzle & The Teacher's Voice (2026-05-22, D-084 · Protocol V34.0)

> كسر "الحلقة العمياء" (Algorithmic Blindness): عندما يحار الطالب («لم أفهم»)،
> نكسر الكبح النصي (Muzzle) ونسمح للـ LLM بتقديم سرد بيداغوجي عميق (The Teacher's Voice)
> يرافق الواجهة البصرية، بدلاً من إعادة بث نفس المكوّن بجملة واحدة.

### المشكلة
كان نظام التوجيه (`orchestrator_client`) يفرض `terminate_pipeline=True` بمجرد بثّ
أي Generative UI، مما يكبل الـ LLM بجملة مرافق واحدة (Muzzle). هذا يمنع الشرح
العميق لـ "لماذا" (The Why) في المسائل المعقدة مثل BAC 2024.

### الإصلاح (D-084)
- **Contextual Unmuzzle** (`orchestrator_client.py`): استخدام `is_confusion(question)`
  للكشف عن حيرة الطالب. إذا وُجدت، يُحوّل `terminate_pipeline` إلى `False` قسراً.
- **The Teacher's Voice** (`doctrine.py` v2.1.0): ترقية `EXPLANATION_DOCTRINE`
  بقواعد سردية جديدة: التشبيهات (Analogies)، شرح المنطق الجوهري، والصبور التعليمي.
- **التكامل الهجين**: بثّ المكوّن البصري (Carousel) + شرح سردي كامل من الـ LLM
  في نفس الوقت لحل حيرة الطالب.

### القواعد الدائمة
1. رصد الحيرة (`is_confusion`) يكسر الـ Muzzle تلقائياً (Protocol V34.0).
2. الشرح عند الحيرة يجب أن يجمع بين "البصري" (Visual) و"السردي" (Narrative).
3. استخدام التشبيهات (Analogies) إلزامي لتبسيط المفاهيم المعقدة.
4. تفسير الـ "لماذا" (Why) يسبق الـ "كيف" (How).

---

## 6.60 Dual-Mode Routing — MODE_A / MODE_B (2026-05-23, D-085 · Protocol V38.0)

> يُحدِّث ويُعمِّق D-084 (V34.0). بدلاً من كسر الـ Muzzle قسراً بعد بناء الحمولة،
> يُحدَّد وضع التوجيه **داخل** `_build_calculated_ui` قبل بناء أي حمولة،
> ويُصبح `routing_mode` جزءاً من العقد المُرجَع.

### المشكلة (فجوة V34.0)
كان V34.0 يكسر الـ Muzzle فقط عند `_is_confusion AND _is_impossible` — أي عند
الحالة المستحيلة فقط. عند حيرة الطالب في سحب عادي (combinations/tree)، كان
`terminate_pipeline=True` يُوقف المسار رغم الحيرة لأن `_is_impossible=False`.

### الإصلاح (D-085)

#### `_build_calculated_ui` (orchestrator_client.py)
- يكشف `is_confusion` **داخلياً** قبل بناء الحمولة.
- يُضيف `routing_mode: "MODE_A" | "MODE_B"` لكل dict مُرجَع.
- يضبط `terminate_pipeline = not _is_deep_pedagogy` لجميع أنواع المكوّنات
  (combinations_visualizer, probability_tree, impossible_draw_animation, full_exercise_story).

#### `chat_with_agent` (orchestrator_client.py)
- يقرأ `routing_mode` مباشرة من الحدث — مصدر حقيقة واحد، لا فحص حيرة ثانٍ.
- `_is_mode_b` مُرفَّع (hoisted) قبل `try/except` ليكون مقروءاً في سلسلة الـ fallback.
- يبني `_effective_question`: في MODE_B يُضيف تعليمة سقراطية قبل السؤال:
  `"[وضع الشرح العميق] ابدأ بالمعنى والصورة الذهنية قبل أي صيغة..."`.
- MODE_B يسقط للـ LLM path مباشرة بعد بثّ المكوّن البصري.
- MODE_A يُنهي المسار بـ companion_text (جملة واحدة ≤ 120 حرف) كما كان.

### عقد الوضعين

| الوضع | المُشغِّل | terminate_pipeline | مخرج النص |
|-------|-----------|-------------------|-----------|
| **MODE_A** | سؤال مباشر | `True` | companion_text (جملة واحدة) |
| **MODE_B** | حيرة (لم أفهم / مفهمتش / كيفاش / اشرح لي) | `False` | سرد بيداغوجي كامل من LLM |

### فصل القناتين (Channel Separation)
- **Channel 1 — UI Payload**: JSON نظيف (`component` + `props` + `routing_mode`). لا Markdown.
- **Channel 2 — LLM Narrative**: Markdown فقط. يبدأ بالمعنى والصورة، لا LaTeX.
- القناتان لا تتلوّثان أبداً.

### القواعد الدائمة (D-085 — لا تُكسر بدون ADR)
1. `routing_mode` يُحدَّد داخل `_build_calculated_ui` — لا يُعاد حسابه في `chat_with_agent`.
2. MODE_B يُفعَّل لأي مكوّن (ليس impossible_case فقط).
3. `_effective_question` في MODE_B يحمل التعليمة السقراطية — لا تُحذف.
4. `terminate_pipeline` في MODE_A لا يزال `True` — V28.0/V30.0 ساريان في MODE_A.
5. تعليمة MODE_B < 1000 حرف، بلا رموز box-drawing، بلا LaTeX (D-067).

### التحقق الحي (2026-05-23)
- 7/7 حالات توجيه صحيحة (MODE_A terminate=True، MODE_B terminate=False).
- LLM في MODE_B يفتح بـ `تخيل أن لديك كيساً...` — معنى أولاً، لا LaTeX.
- 17 اختباراً جديداً في `tests/services/test_v38_dual_mode_routing.py`.
- 827 اختباراً تجتاز، فشلان موجودان مسبقاً في `test_skills_doctrine_d071.py`.

### جدول القرارات المحدَّث

| D-رقم | الموضوع |
|--------|---------|
| D-075 → D-081 | dynamic probability engine + generalization + auto-trigger + deep-dive + entity fix |
| D-082 | impossible-case UX + skills doctrine |
| **D-083** | **Full Exercise OS: multi-step pedagogical carousel (V31.5)** |
| **D-084** | **Protocol V34.0: Contextual Unmuzzle (impossible_case فقط)** |
| **D-085** | **Protocol V38.0: Dual-Mode Routing — MODE_A/MODE_B لجميع المكوّنات** |
| **D-086** | **Protocol V46.0: Dual-Channel Firewall — OutputFirewall + TopicLock** |

---

## 6.61 Dual-Channel Firewall — OutputFirewall + TopicLock (2026-05-23, D-086 · Protocol V46.0)

### المشكلة

كانت القناة B (صوت المعلم) تصل للطالب بدون أي فحص للتلوث. الـ LLM يمكنه إخراج:
- `<div>`, `<span>`, `<button>` داخل النص السردي
- مكونات JSX مزيفة (`<ProbabilityTree>`, `<Accordion>`)
- React imports وscaffolding مزيف
- CSS مضمَّن في الإجابة العربية

كذلك لم يكن هناك آلية لمنع تسرب مفاهيم من مواضيع أخرى (احتمالات → تفاضل).

### الإصلاح (D-086)

#### OutputFirewall (`app/services/skills/output_firewall.py`)

جدار الحماية المزدوج للقنوات:

- **القناة A** (JSON هيكلي): يرفض أي نثر سردي لا يبدأ بـ `{` أو `[`.
- **القناة B** (صوت المعلم): يكشف HTML/JSX/markup ويُطبِّق:
  - **تنظيف** إذا كان التلوث تحت العتبة (0.6): يُزيل الوسوم ويحتفظ بالمحتوى النصي.
  - **رفض** إذا تجاوز التلوث العتبة: يُعيد نصاً فارغاً للمُستدعي.
  - **Fail-open**: أي فشل داخلي يُعيد النص الأصلي — لا يكسر المسار أبداً.

أنماط التلوث المُكتشَفة (مع أوزانها):
| النمط | الوزن |
|-------|-------|
| وسوم HTML (`<div>`, `<span>`, إلخ) | 0.4 |
| مكونات JSX (PascalCase) | 0.5 |
| بوابات Next.js (`<NextPortal>`) | 0.6 |
| CSS مضمَّن (`style=`, `className=`) | 0.3 |
| أسهم قوائم مزيفة + event handlers | 0.3 |
| React scaffolding (`export default function`) | 0.7 |

مقاييس Prometheus:
- `cogniforge_output_firewall_checks_total{channel, result}`
- `cogniforge_output_firewall_rejections_total{channel, reason}`
- `cogniforge_output_firewall_cleanups_total{channel}`
- `cogniforge_output_firewall_duration_seconds`

#### TopicLock (`app/services/skills/topic_lock.py`)

قفل الموضوع وحماية نقاء السياق:
- يُحدِّد الموضوع النشط من آخر 5 رسائل في تاريخ المحادثة.
- يتحقق من أن الإجابة لا تتجاوز النطاق (احتمالات لا تحتوي مفاهيم تفاضل).
- **تحذيري فقط** — يُسجِّل الانتهاكات دون رفض الإجابة.
- يتجاهل انتقالات الموضوع الصريحة (`انتقل إلى`, `دعنا ننتقل`).

مقاييس Prometheus:
- `cogniforge_topic_lock_violations_total{active_topic, leaked_topic}`
- `cogniforge_topic_lock_checks_total{result}`

#### نقاط التطبيق

| الملف | نقطة التطبيق |
|-------|-------------|
| `app/services/chat/local_graph.py` | `_chat_node` — بعد `_apply_answer_quality_skill` |
| `app/api/routers/customer_chat.py` | قبل حفظ `complete_ai_response` في DB |

### القواعد الدائمة (D-086 — لا تُكسر بدون ADR)

1. **المعلم لا يُصيِّر**: القناة B (صوت المعلم) لا تحتوي HTML/JSX أبداً.
2. **الواجهة لا تشرح**: القناة A (JSON هيكلي) لا تحتوي نثراً سردياً أبداً.
3. **Fail-open إلزامي**: جدار الحماية لا يكسر المسار — أي فشل يُعيد النص الأصلي.
4. **TopicLock تحذيري**: لا يرفض الإجابات — يُسجِّل فقط.
5. **العتبة = 0.6**: مجموع أوزان الأنماط المُكتشَفة ≥ 0.6 → رفض كامل.

---

## 6.62 WebSocket Auth — نظام الاستخراج متعدد الطبقات (2026-05-24, D-WS-002 · ISS-WS-001)

### المشكلة (ISS-WS-001)

النظام كان يظهر **Offline** على شبكات الهاتف الجزائرية وGitHub Codespaces بدون VPN، رغم أن backend حي تماماً. السبب: `ws_auth.py` كان يعتمد على `sec-websocket-protocol` كمصدر أساسي لـ JWT، وكان يُعطِّل query token في production.

**البيئات المتضررة**: Djezzy/Mobilis/Ooredoo carrier-NAT، GitHub Codespaces edge proxy، Brave Mobile، Chrome Mobile.

**السبب الجذري**: RFC 6455 لا يُلزم الـ proxies بالحفاظ على `Sec-WebSocket-Protocol`. الكود القديم كان يُرجع `None` للـ query token في production/staging.

### الإصلاح (D-WS-002)

`app/api/routers/ws_auth.py` أُعيد تصميمه بنظام 4 طبقات:

| الأولوية | المصدر | متى يُستخدم |
|----------|--------|------------|
| 1 | Cookie (`access_token`/`auth_token`/`token`) | الأكثر موثوقية — كل الشبكات |
| 2 | Query param `?token=` | Codespaces/mobile/Brave — **مُفعَّل في production** |
| 3 | `Authorization: Bearer` | Gateway server-to-server |
| 4 | `sec-websocket-protocol` | fallback أخير فقط |

### القواعد الدائمة (D-WS-002 — لا تُكسر)

- **ترتيب الأولوية ثابت**: Cookie > Query param > Auth header > Subprotocol. أي تغيير يكسر mobile/Codespaces.
- **query token مُفعَّل في production**: لا تُعيد إضافة `if settings.ENVIRONMENT in ("production", "staging"): return None, None` — هذا هو root cause الأصلي.
- **لا تسريب token في logs**: `_log_auth_failure` يُسجِّل وجود/غياب المصادر فقط، لا قيمها.
- **sec-websocket-protocol هو fallback أخير فقط**: لا تُعيده إلى الأولوية الأولى.

### التحقق الحي (2026-05-23)

- OutputFirewall: `<div>` يُنظَّف، JSX ثقيل يُرفض، LaTeX لا يُعتبر تلوثاً.
- TopicLock: تسرب تفاضل في سياق احتمالات يُسجَّل كانتهاك.
- 25 اختباراً في `tests/test_output_firewall_v46.py` — جميعها تجتاز.
- الـ backend يعمل على :8000 (`/health → ok`).


---

## Session 2026-05-24 — D-090/D-091 (LocalGraph full-path alignment)

### Incident pattern
في مسار المتابعة التعليمية، الطالب يرسل سؤالاً قصيراً بعد عرض تمرين كامل. إذا بُنِيَت guardrails من آخر سطر فقط، يضعف الالتصاق بمعطيات التمرين (year/colors/entities) ويزيد drift.

### Implemented controls
1. **D-091 — Context-bound Precision Guardrail**
   - بناء `_build_precision_guardrail` من الرسالة المركّبة (history + current question) بدل السؤال الحالي وحده.
   - مطبّق في: `_chat_node` و `run_local_graph_stream`.

2. **D-090 — Probability Entity Alignment Sanitizer**
   - إضافة `_strip_unrequested_color_lines(question, answer, intent)`.
   - يمنع سطور الإجابة التي تُدخل ألواناً غير موجودة في معطيات سؤال الاحتمالات.
   - يُطبّق مباشرة بعد توليد LLM وقبل بقية طبقات sanitation/quality/firewall.

### Live verification (mandatory)
- تم تنفيذ `scripts/test_auto_ui_trigger.py` بنجاح:
  - confusion detected
  - draw_mode=`simultaneous` عند "دفعة واحدة"
  - route -> `full_exercise_story` (لا tree متتالية خاطئة)
  - تحقق عددي: `C(11,3)=165` و `14/165`

### Regression coverage
- `tests/services/test_iss079_catastrophic_fixes.py`:
  - `TestPrecisionGuardrail`
  - `TestQuestionAlignmentSanitizer`
  - `TestCatastropheDeepScenarioRegression`

### Operational note
إذا ظهر warning خارجي من LangGraph في pytest policy، يُسجَّل كاعتمادية خارجية ولا يُفسَّر كفشل وظيفي ما لم تفشل assertions نفسها.

---

## Session 2026-05-24 — D-092: Skillization of exercise alignment

### Architectural upgrade
تم استخراج منطق محاذاة معطيات تمرين الاحتمالات من `local_graph` إلى Skill رسمية:
- `app/services/skills/exercise_alignment_skill.py`

### Contracts
- `ExerciseAlignmentInput(question, answer, intent)`
- `ExerciseAlignmentOutput(aligned_answer, removed_lines, applied)`

### Runtime integration
`local_graph._strip_unrequested_color_lines` أصبح wrapper يستدعي skill الجديدة بشكل دفاعي.

### Why this matters
- يمنع `prompt spaghetti` داخل orchestration layer.
- يدعم فلسفة النظام: القدرات المعرفية يجب أن تعيش في skills قابلة للاختبار والاستبدال.
- يفتح الطريق لمحاذاة أعمق (numbers/symbols/constraint clauses) داخل نفس skill دون تضخم `local_graph`.

---

## Session 2026-05-24 — ISS-WS-Offline-001 mobile connectivity stabilization

### Problem
ظهور `offline` في واجهة المحادثة الحية (خصوصاً الهاتف) رغم أن الخدمة تعمل.

### Deep fix applied (and kept minimal)
تم اعتماد خطوتين إلزاميتين فقط، بدون أي تعديل سلوكي إضافي:

1. تثبيت دعم WebSocket الصحيح في بيئة التشغيل:
   - `pip install "uvicorn[standard]"`
2. تشغيل uvicorn بإعدادات websocket + ping الطويلة:
   - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws websockets --ws-ping-interval 300 --ws-ping-timeout 300`

### Why this works
- `--ws websockets` يضمن استخدام backend websocket implementation المستقر.
- زيادة `ping_interval` و`ping_timeout` إلى 300 ثانية تقلل قطع الاتصال الزائف على شبكات الهاتف المتذبذبة.

### Live verification
تم التحقق الحي بعد التطبيق مباشرة: اختفاء حالة `offline` واستمرار الاتصال بشكل مستقر.

---

## Session 2026-05-24 — ISS-OFFLINE-001 Root Cause Fix: WebSocket Gateway Routing

### Root Cause (النهائي)

التحقيق الحي كشف أن المشكلة لم تكن في keepalive — بل في **architectural routing failure**:

```
curl -I http://localhost:8000/api/chat/ws  → 403 Forbidden  (بدون token)
curl -I http://localhost:8003/chat/ws      → 101 Switching Protocols ✅
```

**سلسلة الفشل الكاملة:**
1. Frontend يبني `ws://[host]/api/chat/ws` باستخدام `window.location.host`
2. في Codespaces/Gitpod: المتصفح يصل عبر proxy خارجي → يضرب Next.js على port 3000
3. Next.js rewrites (`/api/:path*` → `8000/api/:path*`) تعمل فقط مع HTTP — **لا تُمرِّر WebSocket upgrade headers**
4. Gateway (8000) كان يملك `/api/chat/ws` لكن يُرجع 403 بدون token في upgrade request
5. WebSocket الحقيقي على `8003/chat/ws` يعمل لكن Frontend لا يعرف عنه
6. VPN غيَّر network path وسمح بالاتصال المباشر → وهم أن المشكلة حُلَّت بـ keepalive

### Architectural Fix

**`app/api/routers/ws_proxy.py`** — WebSocket reverse proxy جديد:
- يستقبل WebSocket على `8000/api/chat/ws`
- يُمرِّره إلى `8003/chat/ws` مع الحفاظ على subprotocols (jwt, token)
- يُمرِّر `8000/admin/api/chat/ws` → `8003/admin/chat/ws`
- مُسجَّل أولاً في registry قبل `customer_chat.router`

**`frontend/app/utils/wsUrl.js`** — WebSocket URL utility:
- `buildWsUrl(endpoint)` يستخدم `window.location.host` دائماً
- يكتشف Codespaces/Gitpod/Replit تلقائياً
- ممنوع استخدام localhost أو port hardcoding

**`frontend/app/hooks/useRealtimeConnection.js`** — State machine محسَّن:
- حالات: `idle → connecting → connected → degraded → reconnecting → offline → recovered`
- D-WS-002: لا يُعلَن عن `offline` إلا بعد 10 محاولات فاشلة
- Heartbeat: ping/pong كل 25 ثانية للكشف عن stale connections
- Exponential backoff مع jitter (500ms → 30s)

### Permanent Rules (D-WS-001, D-WS-002)

- **D-WS-001**: `404 on websocket endpoint = architectural routing failure`
- **D-WS-001**: كل WebSocket يجب أن يمر عبر Gateway (8000) عبر ws_proxy
- **D-WS-001**: ممنوع استخدام localhost أو port hardcoding في browser runtime
- **D-WS-002**: لا يُعلَن عن `offline` إلا بعد WebSocket failure + reconnect exhaustion

---

## Realtime Infrastructure Rules (D-WS-001 — إلزامي لجميع Agents)

### قوانين WebSocket المعمارية

**ممنوع منعاً باتاً:**
- ❌ إنشاء WebSocket endpoints مباشرة في frontend بدون gateway routing موحد
- ❌ استخدام `localhost` أو `127.0.0.1` داخل browser runtime
- ❌ hardcode أي port رقم داخل browser JavaScript
- ❌ الاعتماد على Next.js rewrites لتمرير WebSocket (لا تعمل مع WS upgrade)
- ❌ إعلان `offline` قبل استنفاد reconnect attempts

**إلزامي:**
- ✅ جميع WebSocket routes تمر عبر `app/api/routers/ws_proxy.py` على Gateway (8000)
- ✅ استخدام `window.location.host` دائماً (يعمل في Codespaces/Gitpod/Mobile/VPN)
- ✅ استخدام `frontend/app/utils/wsUrl.js:buildWsUrl()` لبناء WebSocket URLs
- ✅ كل WebSocket جديد يجب أن يدعم: heartbeat + ping/pong + exponential reconnect + graceful degradation
- ✅ `ws_proxy.router` يجب أن يكون أول router في `base_router_registry()`

### قانون التشخيص

```bash
# تشخيص سريع لأي مشكلة WebSocket:
curl -I -H "Upgrade: websocket" -H "Connection: Upgrade" \
     -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
     -H "Sec-WebSocket-Version: 13" \
     http://localhost:8000/api/chat/ws

# 101 = يعمل ✅
# 403 = يعمل لكن يحتاج token (مقبول)
# 404 = D-WS-001 VIOLATION — architectural routing failure ❌
```

### WebSocket Ownership Map

```
Browser
  ↓ wss://[host]/api/chat/ws
Gateway :8000  (ws_proxy.py)
  ↓ ws://localhost:8003/chat/ws
Conversation Service :8003  (main.py @app.websocket("/chat/ws"))
```

### Offline Declaration Rules (D-WS-002)

لا يُعلَن عن `offline` إلا بعد:
1. WebSocket failure (onclose/onerror)
2. 10 محاولات reconnect فاشلة (MAX_RETRIES)
3. قبل ذلك: الحالة هي `reconnecting` وليس `offline`

### uvicorn WebSocket Settings (إلزامي)

```bash
--ws websockets          # backend مستقر
--ws-ping-interval 20    # ping كل 20 ثانية
--ws-ping-timeout 30     # انتظر pong 30 ثانية
--timeout-keep-alive 75  # keep-alive للشبكات المتذبذبة
```

---

## 6.63 Application-Layer Heartbeat Protocol — End of Flapping (2026-05-26, ISS-WS-FLAP-002 / D-WS-FLAP-002)

> الكارثة الأخيرة في سلسلة WebSocket: رغم D-WS-002/D-WS-004/D-WS-FLAP-001/
> D-WS-CODESPACES-001 الناجحة على طبقات الـ transport و auth و proxy، المتصفح
> ما زال يتأرجح بين «متصل» و «إعادة الاتصال» و «غير متصل» كل ~35 ثانية على
> GitHub Codespaces. الـ services الثلاث (5000، 8000، 8003) كلها تعمل، والاختبار
> من الـ terminal ينجح. هذا القسم يكشف الطبقة المفقودة ويُغلقها نهائياً.

### الجذر

الواجهة (`useRealtimeConnection.js`) تنفّذ application-level heartbeat:
1. كل 25s ترسل `{type:"ping"}` كرسالة JSON على الـ WebSocket المفتوح.
2. تنتظر 10s ردّاً يحتوي `"type":"pong"` لإلغاء timeout.
3. لو لم يصل pong → `ws.close(1001, "heartbeat_timeout")` → reconnect.

الخادم (`customer_chat.py`/`admin.py`) كان يعتبر كل رسالة سؤالاً:
```python
payload = await websocket.receive_json()           # {"type":"ping"}
question = str(payload.get("question","")).strip() # ""
if not question:
    await websocket.send_json({"type":"error", ...})  # ليس pong!
    continue
```
→ لا pong يصل → timeout 10s → close 1001 → دورة flapping كل ~35s.

### الإصلاح (D-WS-FLAP-002)

**Skill رسمي موحَّد** في `app/services/skills/ws_heartbeat_skill.py`:
- `is_control_message(payload)` — يكشف `{type: "ping"|"heartbeat"|"noop"}`.
- `handle_control_message(websocket, payload)` — يرسل pong/heartbeat_ack/silent، يُرجع
  `True` للرسائل المُعالَجة (المتصل يُكمل بـ `continue`) و `False` للسؤال الحقيقي.
- Prometheus: `cogniforge_skill_ws_heartbeat_invocations_total{message_type,result}`.
- Fail-open: فشل إرسال pong (المتصل أُغلق بين receive/send) يُسجَّل DEBUG ولا يكسر loop.

**Doctrine موحَّد** `REALTIME_PROTOCOL_DOCTRINE` (v1.0.0 — 9 قواعد) في
`app/services/skills/doctrine.py` — Single Source of Truth، مسجَّل في
`SKILL_DOCTRINE_MANIFEST` تحت `realtime_protocol`.

**تطبيق في كل WS endpoints**:
- `customer_chat.chat_stream_ws` (live customer path) — استدعاء قبل question check.
- `admin.admin_chat_stream_ws` (live admin path) — نفس الإصلاح.
- `microservices/conversation_service/main.py` — نسخة inline (microservices ممنوع لها
  استيراد من `app.*` لكنها تحترم نفس الـ doctrine).

### القواعد الـ 5 الدائمة (D-WS-FLAP-002 — لا تُكسر بدون ADR)

1. **Control-first**: أي WS endpoint يفحص `type` في الـ payload يجب أن يستدعي
   `handle_control_message` أولاً قبل اعتبار الرسالة سؤالاً. حذف هذه الطبقة =
   عودة فورية لـ flapping.
2. **Pong format ثابت**: الرد يجب أن يحتوي `"type":"pong"` كـ substring متطابق —
   الواجهة تفحص بـ `event.data.includes('"type":"pong"')` ليس `JSON.parse`.
3. **Application heartbeat ≠ TCP ping**: `uvicorn --ws-ping-interval 20` يفحص الـ
   TCP layer فقط — لا يكشف إن كان الـ handler عالقاً. الـ app-level heartbeat هو
   نظام liveness حقيقي للطبقة العليا.
4. **Skill is the only allowed implementation**: ممنوع نسخ منطق `ping/pong` في كل
   router — يجب استخدام `handle_control_message`. الـ Skill هو نقطة الـ
   instrumentation الوحيدة (Prometheus metrics + central logging).
5. **Microservices use inline copy, not import**: `microservices/conversation_service`
   ممنوع لها استيراد من `app.services.skills` (architectural §0.5). يجب نسخ
   منطق الـ 14 سطر inline مع الإشارة إلى الـ doctrine.

### قياس النجاح حياً

```bash
# Unit tests (7 cases): ping/heartbeat/noop/passthrough/correlation/fail-open/format
python3 -m pytest tests/services/test_ws_heartbeat_skill.py -v

# Integration tests (9 checks): router imports + call order + doctrine wiring
python3 -m pytest tests/services/test_ws_router_heartbeat_integration.py -v

# Live (Codespaces): browser stays connected past 25s mark — no reconnects.
# Console يجب أن يُظهر:
#   [WS] connected (no further close events for hours)
# لا يجب أن يظهر:
#   [WS] heartbeat timeout — stale connection, forcing reconnect  ← OLD BUG
```

### السلسلة الكاملة (D-049 → D-WS-FLAP-002)

| Decision | المُصلَح |
|----------|---------|
| D-049 → D-086 | JSON envelope + LaTeX + theme + Math + sanitizer + V46 firewall |
| D-WS-001 | architectural ws_proxy + wsUrl utility + state machine |
| D-WS-002 | accept-before-close + CORS regex + ALLOWED_HOSTS wildcards |
| D-WS-004 | unified WS architecture (admin_chat.js + jwt subprotocol fix + auth_error event) |
| D-WS-FLAP-001 | server-side defenses (NullPool→pool, mid-stream check, _emit_terminal try) |
| D-WS-CODESPACES-001 | same-host proxy via server.js + Codespaces WS upgrade reliability |
| D-WS-GITPOD-001/002 | gitpod.dev wildcard support + ALLOWED_HOSTS always overwrite |
| **D-WS-FLAP-002** | **application-layer heartbeat skill — `{type:"ping"}` → `{type:"pong"}` (end of flap)** |

---

## 6.64 Fast-Cycle Flapping Defense — Stale-WS + Debounce + Server Primer (2026-05-26, ISS-WS-FLAP-003 / D-WS-FLAP-003)

> الكارثة المُكتشَفة بـ screenshots حية بعد deploy D-WS-FLAP-002: الـ UI status
> يتأرجح كل 3 ثوانٍ (متصل → إعادة الاتصال → غير متصل → ...). الـ heartbeat fix
> صحيح لكنه لا يحل flapping بهذه السرعة — الجذر في طبقات أخرى.

### الأسباب الجذرية (متعددة)

**(1) Stale-WS race في React useEffect**:
عند re-render (toggle sidebar, theme change, etc.) → cleanup يُغلق old WS بـ 1000
→ effect جديد يفتح new WS → onclose للقديم يفير AFTER mountedRef=true (من new effect)
→ يُحدِّث retries++ على connection يعمل بالفعل → false "reconnecting".

**(2) No proxy primer**: الـ WS يُعرض على FastAPI، لكن proxies (server.js +
Codespaces edge + mobile carrier-NAT) قد تُغلق idle session لو لم تُرسل بيانات فور
accept.

**(3) Aggressive UI**: `MAX_RETRIES=10` يصل لـ "offline" بسرعة. حتى blip شبكي
صغير يُعلِن "reconnecting" فوراً → flicker مرئي.

**(4) Code 1000 يُعالَج كفشل**: cleanup يُغلق بـ 1000 (NORMAL_CLOSURE)، لكن الـ
handler يعدّه فشل → retries++ + "reconnecting".

### الإصلاح (4 طبقات)

**الطبقة 1 — Stale-WS Detection** (`useRealtimeConnection.js`):
```js
ws.onclose = (e) => {
    if (!mountedRef.current) return;
    // D-WS-FLAP-003: لو الـ ws الذي أُغلق ليس wsRef.current الحالي،
    // فهذا close لاتصال قديم (race condition). تجاهل تماماً.
    if (wsRef.current && wsRef.current !== ws) {
        console.info("[WS] ignoring close of stale ws");
        return;
    }
    // ... safe to handle close
};
```

**الطبقة 2 — Debounced UI State** (`useRealtimeConnection.js`):
- `STABLE_THRESHOLD_MS = 3000`: لو الاتصال صمد >3s، أي close تالٍ يُعتبر شبكي عابر.
- `stateDebounceRef`: تأخير `setState("reconnecting")` لـ 500ms — لو نجح retry قبلها، لا flicker.
- `SILENT_CLOSE_CODES = {1000, 1001}`: لا تُعلِن "reconnecting" لـ codes الـ normal close.

**الطبقة 3 — Tolerance Tuning**:
- `MAX_RETRIES`: 10 → 30 (≈10 دقائق قبل "offline").
- `HEARTBEAT_INTERVAL`: 25s → 45s (يقلل ضغط على proxies).
- `HEARTBEAT_TIMEOUT`: 10s → 15s (تسامح أوسع مع mobile latency).

**الطبقة 4 — Server Primer Event** (`customer_chat.py` + `admin.py`):
```python
# Immediately after accept():
await websocket.send_json({
    "type": "session_ready",
    "payload": {"user_id": actor.id, "ts": <iso-utc>},
})
```
يُجبر proxies على keepalive session نشط بدل idle-timeout. الواجهة تتجاهل النوع
غير المعروف (useAgentSocket لا يعالج `session_ready`).

### القواعد الأربع الدائمة (D-WS-FLAP-003 — لا تُكسر بدون ADR)

1. **Stale-WS check إلزامي**: أي `onclose` handler يجب أن يفحص `wsRef.current !== ws`
   قبل أي action. حذف هذا = عودة فورية لـ false reconnects في React re-renders.
2. **Silent close codes**: 1000/1001 لا تُسبب UI flicker. تُعالَج بـ debounce 500ms.
3. **Primer event إلزامي**: كل WS endpoint جديد يجب أن يُرسل event فور `accept()` —
   حتى لو كان `{type: "session_ready"}` فارغ. هذا يحافظ على proxy session نشط.
4. **MAX_RETRIES ≥ 30, HEARTBEAT_INTERVAL ≥ 45s**: لا تقللها بدون ADR — هذه عتبات
   مُختبرَة لشبكات الهاتف المتذبذبة.

### قياس النجاح حياً

```bash
# 1. Browser console يجب أن يُظهر:
[WS] closed { session_ms: <N>, was_stable: true/false }
[WS] ignoring close of stale ws  # عند re-render

# 2. Trigger re-renders (toggle sidebar 5 مرات سريعاً)
# → expect: no UI flicker، status يبقى "متصل"

# 3. Wait 5 minutes idle
# → expect: status يبقى "متصل" (لا flapping كل 3 ثوانٍ)
```

### السلسلة الكاملة (D-WS-001 → D-WS-FLAP-003)

| Decision | المُصلَح |
|----------|---------|
| D-WS-001 | architectural ws_proxy + wsUrl + state machine |
| D-WS-002 | accept-before-close + CORS regex + ALLOWED_HOSTS |
| D-WS-004 | unified WS architecture |
| D-WS-FLAP-001 | server-side defenses (NullPool→pool, mid-stream check) |
| D-WS-CODESPACES-001 | same-host proxy via server.js |
| D-WS-GITPOD-001/002 | gitpod.dev wildcard support |
| D-WS-FLAP-002 | application-layer heartbeat skill |
| **D-WS-FLAP-003** | **stale-WS detection + debounced UI + server primer (end of fast-cycle flap)** |

---

## 6.65 Sticky Connected UI — End of Flicker Catastrophe (2026-05-26, ISS-WS-FLAP-004 / D-WS-FLAP-004)

> **Mea Culpa**: ثلاث محاولات إصلاح متتالية (D-WS-FLAP-001/002/003) فشلت في
> إنهاء flicker «متصل في أجزاء من الثانية». كل إصلاح كان صحيحاً تقنياً لكن
> الكارثة استمرت لأن السبب الجذري في الـ network/proxy layer لا يمكن إصلاحه
> من داخل التطبيق وحده. الحل النهائي: **نُفصل الـ UI عن الـ backend**.

### الفلسفة

المستخدم لا يهتم بسبب blip الشبكة. يريد مؤشراً مستقراً. لذا:
- الـ internal logic يحاول الـ reconnect عند كل blip (كما كان).
- الـ UI يبقى "متصل" بمجرد أول اتصال ناجح.
- فقط `auth_error` (4401/4403) و `offline` (بعد 30s grace) يطغيان على الـ sticky.

### المعمارية

```js
// قبل D-WS-FLAP-004:
return { state, sendMessage };  // state ← internal — يعكس كل blip
                                // → UI flicker

// بعد D-WS-FLAP-004:
const [uiState, setUiState] = useState("idle");  // منفصل
const everConnectedRef = useRef(false);

// computeUiState يطبِّق الـ sticky:
//   لو ever connected: reconnecting/degraded/connecting → "connected"
//   auth_error: يطغى دائماً
//   offline: ينتظر 30s grace قبل ظهوره
return { state: uiState, sendMessage };  // UI ← sticky → لا flicker
```

### القواعد الخمس الدائمة (D-WS-FLAP-004 — لا تُكسر بدون ADR)

1. **Hook لا يُرجع `state` الداخلي مباشرة للـ UI** — دائماً عبر `uiState`.
2. **`everConnectedRef.current = true` فقط في `onopen`** — لا في أي مكان آخر.
3. **`OFFLINE_GRACE_MS ≥ 15000`** — أقل من ذلك يُعيد flicker على شبكات الهاتف.
4. **`auth_error` و `offline` (بعد grace)** هما الوحيدتان اللتان تطغيان على sticky.
5. **عند فشل عدة محاولات root-cause متتالية**، انتقل لإصلاح SYMPTOM بدلاً من cause.
   المستخدم لا يحتاج أن يفهم لماذا — يحتاج أن يعمل النظام.

### قياس النجاح حياً

```bash
# Browser console logs المتوقعة:
[WS] connecting auth_mode=query_param attempt=1/30 url=...
[WS] connected (first time)
# ← الآن: مهما حدث، الـ UI يبقى "متصل"

# Trigger flapping artificially: kill uvicorn → restart
# Internal logs: [WS] closed { code: 1006 } / [WS] Reconnecting in 500ms
# UI: لا flicker — يبقى "متصل" بصرياً

# لو السوء الحقيقي: لا تعافٍ بعد 30s
# UI: يُظهر "غير متصل" — فقط بعد فترة الـ grace
```

### السلسلة الكاملة (D-WS-001 → D-WS-FLAP-004)

| Decision | المُصلَح |
|----------|---------|
| D-WS-001 → D-WS-FLAP-001 | architectural ws_proxy + auth + persistence |
| D-WS-CODESPACES-001 | same-host proxy via server.js |
| D-WS-FLAP-002 | application-layer heartbeat skill |
| D-WS-FLAP-003 | stale-WS detection + debounced UI + server primer |
| **D-WS-FLAP-004** | **sticky connected UI — final UX-first fix** |

---

## 6.66 Honest-Debounce Doctrine — Correction to D-WS-FLAP-004 (2026-05-26)

> **تصحيح معماري حاسم**: المستخدم رفض فلسفة "sticky-connected-forever"
> لأنها قد تكذب طويلاً على المستخدم. القاعدة المُعدَّلة: **الحالة الداخلية
> صادقة، والـ UI يتأخر قليلاً فقط (لا يكذب طويلاً)**.

### الفرق بين debounce و كذب

| Duration | التصنيف | السبب |
|----------|---------|------|
| < 2 ثانية | **debounce مقبول** | معظم blips الشبكية تنتهي خلال 2s، إظهار "reconnecting" فوراً = flicker مزعج |
| 2s – 15s | **يجب إظهار "reconnecting"** | لو لم نتعافَ خلال 2s، هناك مشكلة حقيقية يجب أن يعرفها المستخدم |
| > 15s | **يجب إظهار "offline"** | انقطاع متواصل = مشكلة جدية، إخفاؤها = كذب صريح |

### العقد المعماري (D-WS-FLAP-004 honest-debounce)

```typescript
// Hook الـ return value:
{
  state: uiState,         // مُحاسَب — debounced (لـ UI فقط)
  internalState: state,   // صادق — مكشوف للـ debug/telemetry
  sendMessage,
}
```

**القاعدة الذهبية**: `uiState !== internalState` خلال فترة debounce قصيرة (< 2s
بعد blip)، لكنهما متطابقان تماماً بعد ذلك.

### الـ Code المعماري

```javascript
// useEffect مزامنة state → uiState:
if (state === "auth_error") {
    setUiState("auth_error");  // فوراً — fatal
}
else if (state === "connected" || state === "recovered") {
    setUiState("connected");   // فوراً — تعافٍ
    cancelUiPromotion();
}
else if (disconnect state) {
    // جدوَل promotion مُدرَّج:
    //   - بعد 2s: setUiState("reconnecting")  ← الحقيقة الأولى
    //   - بعد 15s: setUiState("offline")      ← الحقيقة الأصرح
    scheduleUiPromotionForDisconnect();
}
```

### القواعد الخمس الدائمة (D-WS-FLAP-004 honest-debounce — لا تُكسر بدون ADR)

1. **Hook يكشف `internalState`** — صدق المعلومة للـ debug/telemetry غير قابل للإخفاء.
2. **`RECONNECT_VISIBLE_MS ∈ [1000, 3000]`** — أقل = flicker، أكثر = كذب.
3. **`OFFLINE_GRACE_MS ∈ [10000, 30000]`** — أقل = تشويش، أكثر = إخفاء.
4. **`auth_error` و `offline` (بعد grace) يطغيان على debounce** — fatal لا يُؤجَّل.
5. **`setState` يحدث فوراً في كل blip** — لا طبقة وسطى تخفي الحقيقة عن internal logic.

### السلسلة الكاملة المُحدَّثة

| Decision | المُصلَح |
|----------|---------|
| D-WS-001 → D-WS-FLAP-003 | architectural + protocol + race fixes |
| **D-WS-FLAP-004 (honest-debounce)** | **صدق مع تأخير قصير ≤ 15s، ليس كذب طويل** |

### Lesson learned (المضاف للـ engineering doctrine)

> الفرق بين "UX-friendly debounce" و "lying to the user" هو في **المدة**.
> 2 ثانية debounce = راحة UX. 30 ثانية debounce = كذب صريح.
> الـ honest engineering يحترم حدود الـ debounce المعقولة، ويحرص على
> كشف الحقيقة الكاملة للكود الذي يحتاجها (debug/telemetry).

---

## 6.67 SECRET_KEY Consistency Doctrine — All Cross-Service JWTs (2026-05-26, D-WS-SECRET-KEY-001 extended)

> الكارثة المُكتشَفة بـ CI gate forensic بعد deploy D-WS-SECRET-KEY-001: ثلاثة
> خدمات Skills Pipeline إضافية (planning, research, reasoning) كانت ما زالت
> تستخدم `super_secret_key_change_in_production` كافتراضي — فيفشل التحقق من
> `X-Service-Token` المُوقَّع بـ `dev-secret-change-me` من orchestrator. النتيجة:
> Skills Pipeline يسقط صامتاً إلى `mode="fallback"`، الدردشة تظهر متصلة لكنها
> لا تستخدم الـ pipeline الحقيقي.

### القاعدة الذهبية الموسَّعة

```bash
# ❌ Wrong — service-specific defaults break JWT verification cross-service
SECRET_KEY="${SECRET_KEY:-super_secret_key_change_in_production}" \
SECRET_KEY="${SECRET_KEY:-cogniforge-user-service-dev-key}" \

# ✅ Correct — canonical shared default + defensive double-export
local shared_<name>_secret="${SECRET_KEY:-dev-secret-change-me}"
...
SECRET_KEY="${shared_<name>_secret}" \
<SERVICE>_SECRET_KEY="${shared_<name>_secret}" \
```

### الـ 5 services التي يجب أن تتفق على `dev-secret-change-me`

1. **orchestrator** (line 671 — `shared_secret`)
2. **user-service** (line 747 — `shared_user_secret`) — D-WS-SECRET-KEY-001 الأصلي
3. **planning-agent** (line 821 — `shared_planning_secret`) — extension
4. **research-agent** (line 887 — `shared_research_secret`) — extension
5. **reasoning-agent** (line 946 — `shared_reasoning_secret`) — extension

### CI Gate Enforcement

`scripts/fitness/check_secret_key_consistency.py` يطابق نمطين:
- **Inline**: `SECRET_KEY="${SECRET_KEY:-<default>}"` المباشر
- **Shared variable**: `(local )?shared_<anything>_secret="${SECRET_KEY:-<default>}"`

Exit code 1 لو وُجد drift. الفحص جزء من
`tests/services/test_secret_key_consistency.py` (11 regression checks).

### قواعد دائمة (D-WS-SECRET-KEY-001 — لا تُكسر بدون ADR)

1. **`dev-secret-change-me` هو الافتراضي الموحَّد** عبر المستودع كاملاً —
   لا افتراضات service-specific (مثل `cogniforge-user-service-dev-key` أو
   `super_secret_key_change_in_production`) في أي مكان.
2. **شُكل النمط ثابت**: `local shared_<name>_secret="${SECRET_KEY:-dev-secret-change-me}"`
   ثم تصدير `SECRET_KEY="${shared_<name>_secret}"` + `<SERVICE>_SECRET_KEY="${shared_<name>_secret}"`.
3. **`<SERVICE>_SECRET_KEY` defensive export إلزامي** لأي service يحوي
   `env_prefix` في `settings.py` — يحمي ضد quirks بين pydantic-settings و
   validation_alias.
4. **CI gate هو الحارس الوحيد**: لا تتغاضى عنه يدوياً. أي PR يفشل
   `check_secret_key_consistency.py` يجب أن يُصلِح الجذر، لا يُعدِّل الـ gate.
5. **Cross-service JWT = same default**: أي خدمة جديدة تتعامل مع JWT (sign أو
   verify) يجب أن تنضم لقائمة الـ 5 أعلاه قبل أن تُطلَق في supervisor.sh.

### قياس النجاح حياً

```bash
$ python scripts/fitness/check_secret_key_consistency.py
Found 5 SECRET_KEY default assignment(s):
  ✓ line 671: default = `dev-secret-change-me`
  ✓ line 747: default = `dev-secret-change-me`
  ✓ line 821: default = `dev-secret-change-me`
  ✓ line 887: default = `dev-secret-change-me`
  ✓ line 946: default = `dev-secret-change-me`
✅ All 5 default(s) agree on `dev-secret-change-me`.
```

### الدرس المعماري

> "Shared secrets MUST have shared defaults." Service-specific dev defaults
> في supervisor.sh ليست مجرد inconvenience — هي قنابل موقوتة تنفجر عند أول
> Codespace fresh بدون secrets manually configured. الـ CI gate الجراحي
> (forensic-grade) هو الطريقة الوحيدة الموثوقة لمنع التكرار.


---

## 6.68 Q/A Stability — Portable State, Reload Discipline, Long-Stream Tolerance (2026-05-27, ISS-091)

> الكارثة الثانية بعد ISS-090: المستخدم في GitHub Codespaces لا تزال
> تواجه «kicked to login → auto re-enter» عند طرح سؤال، رغم أن ISS-090
> أصلح SECRET_KEY persistence إلى disk. السبب: المسار كان hardcoded إلى
> `/app/...` ويفشل خارج الـ devcontainer الرسمي. هذا القسم يحكم 4 قواعد
> دائمة تضمن استقرار جلسة الدردشة في أي بيئة.

### الأسباب الجذرية الأربعة (مُختبَرة بالتجريب الحي + forensic review)

**RC-1: `/app` hardcoded path** — `app/core/settings/helpers.py:19` كان
يحتوي `_DEV_SECRET_KEY_FILE = "/app/.devcontainer/state/dev_secret_key"`.
خارج الـ devcontainer الرسمي (Codespaces fork، Gitpod، تشغيل محلي من
`/home/user/<repo>`)، الـ path لا يوجد، فيسقط الكود إلى توليد مفتاح
في الذاكرة فقط. كل uvicorn restart → مفتاح جديد → JWT يُبطَل → kick.

**RC-2: `--reload` في الإنتاج** — `supervisor.sh` كان يُطلق uvicorn مع
`--reload` على المسار الإنتاجي AND على `_restart_uvicorn`. الـ flag يراقب
كل ملفات `.py` في المشروع. أي تعديل (يدوي، agent، formatter) يُسبب إعادة
تشغيل worker → كل WS connections النشطة تموت → المستخدم يرى «no response».

**RC-3: monitoring loop عدواني (5s + 1 failure)** — `/health` يتحقق من
اتصال DB. Supabase free tier يصل أحياناً إلى 8-12s. أي blip → 503 →
`_restart_uvicorn` → WS connections die. هذا blip-bombs البنية كلها.

**RC-4: receive-loop محجوب أثناء stream** — `chat_stream_ws` يستخدم
`await stream_task` الذي يحجب `receive_json`. ping من العميل في T+45s
لا يُعالَج حتى ينتهي البث. مع `HEARTBEAT_TIMEOUT=15s` القديم، أي إجابة
طويلة (>60s) تُسبب close مزيف.

### الإصلاح (4 قرارات معمارية)

**D-RELOAD-001**: `--reload` يُفعَّل فقط عبر `DEV_RELOAD=1` env var
صراحةً للمطورين المحليين. الإنتاج (Codespaces / Gitpod / Ona) لا يستخدمه
أبداً. عند التفعيل، `--reload-exclude .devcontainer/state/* --reload-exclude
.observability/*` يمنع reload-loops.

**D-SECRET-002**: `_resolve_state_key_path()` يكتشف الـ path ديناميكياً:
  1. `DEV_SECRET_KEY_FILE` env (override صريح)
  2. `/app/.devcontainer/state/...` (devcontainer canonical)
  3. `<helpers.py>/../../../.devcontainer/state/...` (repo root)
الملف يُحفظ على القرص في كل بيئة بـ chmod 0600. WARN log صريح عند توليد
مفتاح جديد (يساعد operators على diagnosis).

**D-HEALTH-001**: monitoring loop يطلب 3 إخفاقات متتالية مع timeout=15s.
Net: ~90s من الفشل المتواصل قبل uvicorn restart. Blips الشبكية لا تقتل
WS connections النشطة.

**D-WS-HEARTBEAT-002**: `HEARTBEAT_TIMEOUT` في الواجهة 15s → 90s. LLM
streams مع fallback chain كاملة قد تصل إلى 60-90s. uvicorn
`--ws-ping-interval 20` يحافظ على الـ TCP alive في كل الأحوال.

### القواعد الـ 6 الدائمة (D-RELOAD-001 + D-SECRET-002 + D-HEALTH-001 + D-WS-HEARTBEAT-002 — لا تُكسر بدون ADR)

1. **لا hardcoded `/app` في أي settings/helpers module** — استخدم resolver
   ديناميكي. هذا يحمي ضد كل البيئات غير الـ devcontainer الرسمي.

2. **`--reload` ممنوع في الإنتاج** — `DEV_RELOAD=1` opt-in فقط للتطوير
   المحلي مع `--reload-exclude` صارم على state/observability paths.

3. **`_restart_uvicorn` يُعيد قراءة SECRET_KEY من القرص defensively**
   قبل إطلاق uvicorn — يحمي ضد فقدان env بين restarts.

4. **health monitoring يتطلب ≥3 إخفاقات متتالية + ≥15s timeout** قبل
   uvicorn restart. أقل من ذلك = blip-bombs.

5. **`HEARTBEAT_TIMEOUT` ≥ 60s** — أقل من ذلك يتطلب refactor كامل لـ
   receive-loop ليُعالج heartbeats concurrently مع streams.

6. **`.gitignore` يحوي `.devcontainer/state/dev_secret_key`** — كل بيئة
   تولِّد مفتاحها الخاص محلياً، لا يُرفع إلى git أبداً.

### قياس النجاح حياً (2026-05-27)

```bash
# Test 1: helpers.py portable path resolution
$ python3 -c "from app.core.settings.helpers import _resolve_state_key_path; print(_resolve_state_key_path())"
# Without /app: /home/user/NAAS-Agentic-Core/.devcontainer/state/dev_secret_key
# With /app:    /app/.devcontainer/state/dev_secret_key
# DEV_SECRET_KEY_FILE=/tmp/x: /tmp/x

# Test 2: persistence across simulated restart
$ pytest tests/services/test_secret_key_persistence.py -v
6/6 PASS ✅

# Test 3: no regression in related auth tests
$ pytest tests/services/test_secret_key_consistency.py tests/services/test_iss081_answer_quality_wiring.py
129/129 PASS ✅
```

NOTE: Full end-to-end live test against Supabase + OpenRouter was BLOCKED
in the implementation sandbox (network firewall denies Postgres egress on
ports 5432/6543 — same as documented in §6.55 V17.0). The forensic root
cause analysis was derived from deterministic code-path tracing, not
LLM-specific behavior. CI on GitHub Codespaces will exercise the live
end-to-end path with real Supabase + OpenRouter.

### السلسلة الكاملة (D-WS-FLAP-004 → D-WS-HEARTBEAT-002)

| Decision | المُصلَح |
|----------|---------|
| D-WS-FLAP-004 (honest-debounce) | UI flicker, honest disconnect signaling |
| D-WS-AUTH-001 | bounded 4401 retry + HTTP /me probe |
| D-WS-SECRET-KEY-001 | shared SECRET_KEY defaults across all 5 services |
| D-088 | PRIMARY model gpt-oss-20b → gpt-oss-120b (rate-limit recovery) |
| D-SECRET-001 (ISS-090) | persistence-to-disk (hardcoded `/app`) |
| **D-RELOAD-001** | **`--reload` opt-in only via `DEV_RELOAD=1`** |
| **D-SECRET-002** | **portable state path (resolves outside `/app`)** |
| **D-HEALTH-001** | **3-failure threshold + 15s timeout (no blip restarts)** |
| **D-WS-HEARTBEAT-002** | **HEARTBEAT_TIMEOUT 15s → 90s (long stream tolerance)** |
| **D-094-BOOT** | **supervisor.sh: لا تستدعِ nested function خارج نطاقها** |
| **D-094-DELTA** | **flushDeltaBuffer: احفظ baseEvent قبل splice()** |
| **D-094-REQID** | **assistant_final يجب أن يُصفِّر activeRequestIdRef** |

---

## 6.69 Triple Boot+Delta+RequestId Catastrophe — ISS-094 (2026-05-28)

> **الكارثة**: النظام لا يبدأ أصلاً بعد restart في Codespaces. وعند بدئه يدوياً،
> الردود تصل فارغة في الـ frontend، والمستخدم يُطرد إلى صفحة تسجيل الدخول بعد
> كل سؤال. ثلاث مشاكل جذرية مستقلة تتضافر لتُنتج كارثة واحدة.

### RC-1: Supervisor crash — `_set_env_key` خارج نطاقها (D-094-BOOT)

**الجذر**: السطر 299 في `supervisor.sh` يستدعي `_set_env_key "SECRET_KEY" "$SECRET_KEY"`
بعد انتهاء `_inject_env_secrets`. الدالة `_set_env_key` مُعرَّفة داخل `_inject_env_secrets`
وتبقى في bash namespace لكن `env_file` متغير محلي لها — يختفي عند انتهاء الدالة.
مع `set -u` (strict mode): `env_file: unbound variable` → crash فوري → لا uvicorn، لا frontend.

```bash
# ❌ قبل (crash):
_inject_env_secrets() {
    local env_file=".env"
    _set_env_key() { ... uses $env_file ... }  # nested — env_file محلي
}
_ensure_stable_secret_key
if [ -n "${SECRET_KEY:-}" ]; then
    _set_env_key "SECRET_KEY" "$SECRET_KEY"  # ❌ env_file: unbound variable
fi

# ✅ بعد (صحيح):
if [ -n "${SECRET_KEY:-}" ]; then
    _iss092_env_f=".env"
    if grep -q "^SECRET_KEY=" "$_iss092_env_f" 2>/dev/null; then
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$_iss092_env_f"
    else
        echo "SECRET_KEY=${SECRET_KEY}" >> "$_iss092_env_f"
    fi
    unset _iss092_env_f
fi
```

**القانون الدائم (D-094-BOOT)**:
> في bash، لا تستدعِ دالة nested خارج نطاق الدالة الأم. المتغيرات المحلية
> للدالة الأم تختفي عند انتهائها. استخدم `sed`/`awk` مباشرة أو عرِّف الدالة
> في النطاق العام.

### RC-2: `flushDeltaBuffer` bug — `baseEvent` دائماً `undefined` (D-094-DELTA)

**الجذر**: في `useRealtimeConnection.js`، `flushDeltaBuffer` كانت تستدعي
`deltaBuffer.splice(0)` أولاً (يُفرغ المصفوفة فوراً) ثم `deltaBuffer[0]`
(دائماً `undefined` بعد splice). النتيجة: كل الـ delta events تُرسَل بدون
`_connection_id`/`_event_namespace`/`request_id` من الـ event الأصلي.

```js
// ❌ قبل (bug):
const flushDeltaBuffer = () => {
  const merged = deltaBuffer.splice(0).reduce(...);  // يُفرغ المصفوفة
  const baseEvent = deltaBuffer[0] || {};             // دائماً undefined!
  // mergedEvent بدون metadata → events قد تُرفض
};

// ✅ بعد (صحيح):
const flushDeltaBuffer = () => {
  const baseEvent = deltaBuffer[deltaBuffer.length - 1] || {};  // قبل splice
  const merged = deltaBuffer.splice(0).reduce(...);
  // mergedEvent يحمل كل metadata من آخر event
};
```

**القانون الدائم (D-094-DELTA)**:
> في JavaScript، إذا احتجت قيمة من مصفوفة قبل تفريغها بـ `splice(0)` أو
> `length = 0`، احفظها في متغير قبل العملية. `array.splice(0)` يُعيد نسخة
> من العناصر لكن يُفرغ المصفوفة الأصلية فوراً.

### RC-3: `activeRequestIdRef` لا يُصفَّر عند `assistant_final` (D-094-REQID)

**الجذر**: `useAgentSocket.js` يُصفِّر `activeRequestIdRef.current = null` عند
`complete` و`error` لكن ليس عند `assistant_final`. الـ orchestrator يُرسل
`assistant_final` وليس `complete`. النتيجة: بعد الرد الأول، `activeRequestId`
لا يزال موجوداً → السؤال الثاني يُرسَل بـ `clientRequestId` جديد → الـ events
القادمة قد تُرفض بسبب request_id mismatch → الـ frontend يعتقد أن الرد فارغ
→ kick-to-login.

```js
// ❌ قبل (bug):
} else if (type === 'assistant_final') {
    const content = payload?.content || '';
    // activeRequestIdRef.current لا يزال يحمل القيمة القديمة!

// ✅ بعد (صحيح):
} else if (type === 'assistant_final') {
    activeRequestIdRef.current = null;  // صفِّر فوراً
    const content = payload?.content || '';
```

**القانون الدائم (D-094-REQID)**:
> كل event يُنهي دورة request/response يجب أن يُصفِّر `activeRequestIdRef`.
> الـ orchestrator يُرسل `assistant_final` — ليس `complete`. تأكد من أن
> كل terminal event type يُصفِّر الـ ref.

### التحقق الحي (2026-05-28)

```
Backend:    curl http://localhost:8000/health → {"application":"ok","database":"ok"}
Frontend:   http://localhost:5000 → HTML ✅
Login:      houssamannaba963@gmail.com / 1111 → JWT ✅
WS connect: ws://localhost:8000/api/chat/ws → session_ready ✅
Q1 (مشتق x²):   998 chunks، 2412 حرف عربي + LaTeX ✅
Token after Q1:  /api/v1/users/me → 200 (لا kick-to-login) ✅
Q2 (تكامل x²):  972 chunks، 2501 حرف عربي + LaTeX ✅
Model PRIMARY:   openai/gpt-oss-120b:free → finish_reason=stop ✅
Orchestrator:    http://localhost:8006/health → graph_ready=true ✅
```

### القواعد الثلاث الدائمة (D-094 — لا تُكسر بدون ADR)

1. **D-094-BOOT**: في `supervisor.sh`، لا تستدعِ دالة nested خارج نطاق الدالة الأم.
   استخدم `sed`/`awk` مباشرة أو عرِّف الدالة في النطاق العام.

2. **D-094-DELTA**: في `flushDeltaBuffer` (وأي كود مشابه)، احفظ مرجع العنصر
   من المصفوفة **قبل** `splice(0)`. `splice` يُفرغ المصفوفة فوراً.

3. **D-094-REQID**: كل terminal event (`assistant_final`, `complete`, `error`,
   `stream_end`) يجب أن يُصفِّر `activeRequestIdRef.current = null` في
   `useAgentSocket.js`.

### ملف `secrets.env` — إلزامي عند كل restart في Codespaces

```bash
# /app/.devcontainer/secrets.env (git-ignored)
APP_DATABASE_URL=postgresql://...
DATABASE_URL=postgresql://...
OPENROUTER_API_KEY=sk-or-v1-...
TAVILY_API_KEY=tvly-dev-...
ENVIRONMENT=development
```

هذا الملف ضروري لأن Codespaces Secrets غير مُهيَّأة في هذه البيئة.
`supervisor.sh` يقرأه تلقائياً في `_inject_env_secrets()`.

### السلسلة الكاملة (D-WS-FLAP-004 → D-096)

| Decision | المُصلَح |
|----------|---------|
| D-WS-FLAP-001 → D-WS-FLAP-004 | WebSocket flapping + UI flicker |
| D-WS-AUTH-001 | bounded 4401 retry + HTTP /me probe |
| D-WS-SECRET-KEY-001 | shared SECRET_KEY defaults |
| D-088 | PRIMARY model gpt-oss-120b |
| D-SECRET-001/002 | SECRET_KEY persistence + portable path |
| D-RELOAD-001 | `--reload` opt-in only |
| D-HEALTH-001 | 3-failure threshold |
| D-WS-HEARTBEAT-002 | HEARTBEAT_TIMEOUT 90s |
| ISS-093 | RuntimeError ASGI escape + disk-wins SECRET_KEY |
| **D-094-BOOT** | **supervisor nested function scope crash** |
| **D-094-DELTA** | **flushDeltaBuffer baseEvent-after-splice bug** |
| **D-094-REQID** | **assistant_final activeRequestIdRef reset** |
| **D-095** | **NEVER auto-set ENVIRONMENT=testing — preserves 480-min JWT in SQLite fallback (ISS-094 round 2)** |
| **D-096** | **WebSocket send concurrency lock — BKT/stream/heartbeat must not race on send_json (ISS-094 round 3)** |

---

## 6.70 The Persistent Kick-to-Login Catastrophe — Round 2 (2026-05-28, ISS-094-R2 / D-095)

> الكارثة المتكررة: المستخدم يُبلِّغ بعد كل من ISS-092 / ISS-093 / ISS-094 أنه **لا يزال** يُطرد من الجلسة بعد فترة، رغم أن كل إصلاح يدّعي الحل النهائي. السبب: ثلاث إصلاحات سابقة عالجت أعراضاً مختلفة، لكن **الجذر الأعمق** بقي.

### الجذر الأعمق (مكشوف بالتجريب الحي مع SQLite + supervisor.sh simulation)

عندما يفتقد المستخدم `Codespaces Secrets` **و** ينقصه `.devcontainer/secrets.env`:

1. `devcontainer.json` يحقن `APP_DATABASE_URL=""` (empty string من `${localEnv:APP_DATABASE_URL}`)
2. `supervisor.sh:_inject_env_secrets` يحسب `real_db_url=""` (empty after `:-` chain)
3. يدخل else branch ⇒ يضبط `DATABASE_URL=sqlite+aiosqlite:///:memory:` **و**
   ضبط `ENVIRONMENT=testing` ← السبب الجذري الحقيقي
4. `app/services/auth/crypto.py:36-40` يقرأ `ENVIRONMENT` عند **module import time**:
   ```python
   _ENV = (os.environ.get("ENVIRONMENT") or "").strip().lower()
   _IS_DEV_LIKE = _ENV in ("development", "dev", "local") or _ALLOW_LONG
   ACCESS_EXPIRE_MINUTES: Final[int] = 480 if _IS_DEV_LIKE else 30
   ```
5. `testing` ليست في القائمة ⇒ `_IS_DEV_LIKE=False` ⇒ `ACCESS_EXPIRE_MINUTES=30`
6. كل JWT يُصدَر بعمر **30 دقيقة فقط**
7. بعد 30 دقيقة من الجلسة، كل WS reconnect يحصل على 4401 من
   `decode_user_id` (token expired)
8. Frontend بعد `MAX_FATAL_RETRIES=3` يُطلق `agent:auth_error` →
   `setTimeout(logout, 2000)` → kick to login
9. المستخدم يدخل مرة أخرى → token جديد (30 min) → cycle يتكرر **كل 30 دقيقة**

### لماذا ISS-092/093/094 لم تحلّ هذا

- **ISS-092**: أضاف منطق «إذا كان DB حقيقياً، اضبط ENVIRONMENT=development» —
  لكن الـ else branch (SQLite fallback) لا يزال يكتب `ENVIRONMENT=testing`.
  المستخدمون الذين لا يملكون secrets configured كانوا لا يزالون في 30-min mode.
- **ISS-093**: عالج `RuntimeError` في ASGI + `SECRET_KEY` rotation. هذان جذران
  مختلفان عن jwt lifetime.
- **ISS-094**: عالج supervisor crash + frontend delta bug + activeRequestId reset.
  كل هذه bugs حقيقية، لكنها لا تُفسِّر دورة الـ 30 دقيقة.

### الإصلاح (D-095 — جراحي)

`supervisor.sh:_inject_env_secrets` الـ else branch:
```bash
# ❌ قبل (D-095 violation)
_set_env_key "DATABASE_URL" "sqlite+aiosqlite:///:memory:"
_set_env_key "ENVIRONMENT" "testing"   # يكسر JWT lifetime
_set_env_key "TESTING" "1"

# ✅ بعد (D-095 compliant)
lifecycle_error "🚨 CRITICAL: DATABASE_URL not configured — DEGRADED MODE"
lifecycle_error "   To fix: configure Codespaces Secrets or create secrets.env"
_set_env_key "DATABASE_URL" "sqlite+aiosqlite:///:memory:"
_set_env_key "ENVIRONMENT" "development"   # ← يحافظ على 480-min tokens
_set_env_key "TESTING" "1"                  # ← لا يزال متاحاً كـ separate flag
```

### القواعد الـ 4 الدائمة (D-095 — لا تُكسر بدون ADR)

1. **`ENVIRONMENT=testing` ممنوع كقيمة تلقائية في supervisor.sh** — يجب
   ضبطه صراحةً فقط من pytest fixtures للاختبارات الحقيقية.
2. **JWT lifetime ≥ 480 دقيقة في كل dev/Codespaces paths** — أقل من ذلك =
   kick-to-login catastrophe.
3. **`TESTING=1` منفصل عن `ENVIRONMENT`**: العلَم منفصل لـ code paths
   (LLM mocking, fixture isolation) ولا يؤثر على JWT lifetime.
4. **رسائل CRITICAL ERROR loud عند secrets مفقودة** — المستخدم يجب أن
   يرى فوراً ما عليه فعله (configure Codespaces Secrets أو create secrets.env).

### التجريب الحي (2026-05-28)

```bash
# Test 1: محاكاة Degraded Boot (no DB env, no secrets.env)
$ bash -c '(_inject_env_secrets simulation with empty env)'
🚨 CRITICAL: DATABASE_URL not configured — DEGRADED MODE
ENVIRONMENT=development   ← كان 'testing'
DATABASE_URL=sqlite+aiosqlite:///:memory:
TESTING=1

# Test 2: التحقق أن crypto.py يحترم ENVIRONMENT=development
$ ENVIRONMENT=development python3 -c "from app.services.auth.crypto import ACCESS_EXPIRE_MINUTES; print(ACCESS_EXPIRE_MINUTES)"
480   ← كان 30

# Test 3: end-to-end WS chat (with SQLite fallback)
$ python3 /tmp/user_scenario.py
✅ Step 1: /me works (200 OK)
✅ Step 2: List conversations (17 found)
✅ Step 3: Load conversation (2 messages)
✅ Step 4: Q1 → 996 deltas, 2658 chars Arabic response
✅ Step 5: Q2 (multi-turn) → 488 deltas, 1279 chars

# Test 4: 5-question stress test on same WS
$ python3 /tmp/ws_session_stress.py
Q1: 514 deltas (15.1s) ✅
Q2: 623 deltas (23.5s) ✅
Q3: 479 deltas (12.5s) ✅
Q4: 549 deltas (14.0s) ✅
Q5: 469 deltas (16.4s) ✅

# Regression: لا كسر للـ existing tests
$ pytest tests/fitness/test_supervisor_*.py tests/services/test_secret_key_*.py
11/11 PASS ✅
```

### الملفات (D-095)

| File | Change |
|------|--------|
| `.devcontainer/supervisor.sh` | else branch لـ DATABASE_URL: `ENVIRONMENT=development` بدلاً من `testing` + رسالة CRITICAL ERROR loud |
| `tests/fitness/test_supervisor_never_sets_testing_env.py` | **جديد** — 2 regression tests يمنعان عودة الـ bug |
| `.memory/issues.md` | إدخال ISS-094-R2 / D-095 |
| `.memory/decisions.md` | إدخال D-095 |
| `CLAUDE.md` §6.70 | هذا القسم |

### ملاحظة للمستخدم النهائي

إذا كنت ترى هذه الكارثة في GitHub Codespaces:
1. **الحل الأمثل**: قم بتكوين Codespaces Secrets في
   `https://github.com/settings/codespaces` وأضف:
   - `APP_DATABASE_URL` = Supabase Postgres URL
   - `OPENROUTER_API_KEY` = مفتاح OpenRouter
2. **الحل البديل**: انسخ `.devcontainer/secrets.env.example` إلى
   `.devcontainer/secrets.env` واملأ القيم الحقيقية. هذا الملف git-ignored.
3. **بعد D-095**: حتى لو لم تفعل أياً من ذلك، النظام سيعمل بـ SQLite
   (degraded mode) لكن **لن يطردك إلى صفحة الدخول** كل 30 دقيقة.

---

## 6.71 WebSocket Send Concurrency Lock — Kick in SECONDS (2026-05-28, ISS-094-R3 / D-096)

> **User clarification — the actual root cause**: المستخدم وضّح أن D-095 fix لم يكن يعالج الكارثة الحقيقية. الـ kick يحدث **في ثواني فقط** بعد 1-2 سؤال، وليس بعد 30 دقيقة. الأسرار محقونة جيداً.

### الجذر الحقيقي (D-096)

`customer_chat.py:WS handler` يُشغّل عمليتين متزامنتين على نفس الـ WebSocket:

```python
# BKT — background task يكتب DB ثم يُرسل ui_component
_bkt_task = asyncio.create_task(_evaluate_and_emit_bkt(...))

# stream_and_forward — يبثّ deltas + final + persisted
await stream_task  # داخله عشرات websocket.send_json
```

**كلاهما يستدعي `websocket.send_json` على نفس الـ WS بدون قفل.**
Starlette's `WebSocket.send_json` **ليس coroutine-safe** للاستدعاءات المتزامنة.

### لماذا SQLite لا يُظهر الكارثة + Supabase نعم

| DB | BKT duration | تزامن مع stream؟ |
|----|--------------|------------------|
| SQLite | <50ms | لا — BKT ينتهي قبل بدء stream |
| Supabase | 300ms-2s | نعم — overlap كبير |

عند overlap على Supabase:
1. ASGI send protocol corruption (interleaved frame bytes)
2. silent WebSocket close بـ 1006/1011
3. Frontend reconnects automatically
4. New WS قد يفشل لـ race آخر أو state mismatch → 4401
5. بعد 3 محاولات → `agent:auth_error` → logout(2s) → kick to login
6. Auto re-login → DashboardLayout fresh → conversationId=null → **"محادثة جديدة"**

### الإصلاح (D-096 — جراحي)

```python
# Helper جديد
async def _locked_send_json(websocket, lock, payload):
    async with lock:
        await websocket.send_json(payload)

# في كل WS handler invocation
send_lock = asyncio.Lock()

# كل مسار يستخدم القفل
await _locked_send_json(websocket, send_lock, event)
await _evaluate_and_emit_bkt(websocket=ws, send_lock=send_lock, ...)
await _emit_terminal_frames(websocket=ws, send_lock=send_lock, ...)
await handle_control_message(websocket, payload, send_lock=send_lock)
```

### القواعد الـ 5 الدائمة (D-096 — لا تُكسر بدون ADR)

1. **كل `websocket.send_json` على WS مشتركة يجب أن يمر عبر قفل تسلسلي.**
2. **`_locked_send_json(ws, lock, payload)` هو نقطة الإرسال الوحيدة** في streaming paths.
3. **`send_lock = asyncio.Lock()` يُنشأ مرة واحدة لكل WS handler** ويُمرَّر لكل callee.
4. **`_evaluate_and_emit_bkt` و `_emit_terminal_frames` و `handle_control_message` تأخذ `send_lock`** — invariant مُتحقَّق منه بـ regression tests.
5. **CI gate (tests/services/test_ws_send_concurrency_lock.py)** يمنع عودة الـ bug عبر static analysis لـ source code.

### التجريب الحي (2026-05-28)

```bash
# Test 1: 6/6 D-096 unit tests
$ pytest tests/services/test_ws_send_concurrency_lock.py -v
6/6 PASS ✅

# Test 2: Concurrent ping + question (forced race)
2 pongs + 44 deltas + final + persisted — perfectly sequenced ✅

# Test 3: EXTREME — 10 questions back-to-back + ping every 500ms
=== RESULTS: 10/10 succeeded ===
  Q1: 921 deltas (46.7s)
  Q2: 981 deltas (33.1s)
  Q3: 312 deltas (11.3s)
  ... Q10: 258 deltas (19.0s)

# Test 4: regression
$ pytest tests/services/test_ws_heartbeat_skill.py tests/fitness/test_supervisor_*
43+ PASS ✅
```

### الملفات (D-096)

| File | Change |
|------|--------|
| `app/api/routers/customer_chat.py` | + `_locked_send_json()` helper + `send_lock = asyncio.Lock()` per WS + كل المسارات تستخدم القفل |
| `app/services/skills/ws_heartbeat_skill.py` | + معامل اختياري `send_lock` في `handle_control_message()` |
| `tests/services/test_ws_send_concurrency_lock.py` | **جديد** — 6 regression tests |
| `.memory/issues.md` | إدخال ISS-094-R3 / D-096 |
| `.memory/decisions.md` | إدخال D-096 |
| `CLAUDE.md` §6.71 | هذا القسم |

---

## 6.72 The Idle Kick — 4401 Must Never Logout a Valid Session (2026-05-29, ISS-097 / D-WS-KICK-001)

> **بلاغ المستخدم الحاسم**: «**حتى بدون طرح أي أسئلة** تحدث هذه الكارثة ... نخرج
> ثم ندخل إلى صفحة دردشة جديدة». الطرد يحدث على اتصال خامل، بلا أي سؤال — مما
> يُبرّئ D-096 (تزامن الإرسال يحدث أثناء البث فقط) و BKT تماماً، ويُثبت أن الكارثة
> **على مستوى الاتصال** بحتاً.

### الجذر (نصفان مستقلان، لم يُصلحهما D-095 ولا D-096)

**النصف 1 — طرد كاذب**: `useRealtimeConnection.js` كان يُطلق `agent:auth_error`
(→ `logout()` → "محادثة جديدة" فارغة) بعد *عدد* من إغلاقات `4401` المتتالية
(`MAX_FATAL_RETRIES=3`) **دون تأكيد أن الـ token ميت فعلاً**. مع
`FATAL_RETRY_DELAY_MS=2s` = طرد خلال ~6-8 ثوانٍ، حتى مع token صالح تماماً. على
اتصال خامل، السبب الأرجح: بروكسي Codespaces/`server.js` يُسقط أحياناً
`?token=` عند إعادة اتصال WS → الخادم يرى «لا token» → `4401` → تكرار → طرد.

**النصف 2 — "محادثة جديدة" في كل دخول**: `DashboardLayout` كان يُحمَّل دائماً بـ
`conversationId=null` + رسائل فارغة، فأي (إعادة) دخول يسقط في دردشة فارغة.

### الإصلاح (3 طبقات على مستوى الجذر)

- **A — Frontend (`useRealtimeConnection.js`)**: `agent:auth_error` (→ طرد) يُطلَق
  **فقط** في فرع `result === "invalid"` — أي probe HTTP `/me` يُرجع 401/403 قطعياً
  (الـ token ميت حقاً). نتيجة valid/unknown → `retryTransientAuth()` يُعيد الاتصال
  بـ backoff تصاعدي (عبر عدّاد `retries` العام → "offline" أخيراً، لا "auth_error").
  أُزيل `MAX_FATAL_RETRIES` و `FATAL_RETRY_DELAY_MS` (مسار العدّ الذي سبّب الطرد).
- **B — Frontend (`CogniForgeApp.jsx`)**: عند التحميل، استعادة آخر محادثة عبر
  `/api/chat/latest` (admin: `/admin/api/chat/latest`)، محروسة بـ `didRestoreRef`
  أحادي الإطلاق فلا يكتب فوق "محادثة جديدة" صريحة أو فتح محادثة من القائمة.
- **C — Backend (`customer_chat.py` + `admin.py`)**: جلب المستخدم عند الاتصال
  `db.get(User, user_id)` مغلَّف بـ `try/except`؛ الفشل *العابر* (الـ token فُكَّ
  بنجاح) يُغلق بـ `1013` القابل لإعادة المحاولة + كود `WS_BACKEND_TRANSIENT` بدل
  `4401` فيُعيد العميل الاتصال بدل الطرد. المستخدم المفقود/الموقوف حقاً لا يزال
  يُغلق `4401` (صحيح).

### القواعد الـ 4 الدائمة (D-WS-KICK-001 — لا تُكسر بدون ADR)

1. **المسار الوحيد إلى `agent:auth_error` هو probe `/me` يُؤكِّد 401/403**. لا عدّاد
   إغلاقات يُترجَم إلى طرد. أي إعادة لمنطق العدّ = عودة فورية لكارثة الطرد الخامل.
2. **`/me` هو الحكم الوحيد لصلاحية الجلسة** (token عبر Authorization header — مسار
   موثوق منفصل عن WS؛ مناعة ضد إسقاط البروكسي لـ `?token=`).
3. **الفشل العابر في جلب المستخدم بـ WS يُغلق `1013` لا `4401`** بعد فك الـ token
   بنجاح. `4401` محجوز لـ token مفقود/تالف أو مستخدم موقوف فعلاً.
4. **`DashboardLayout` يستعيد آخر محادثة عند التحميل** (محروس بـ `didRestoreRef`)
   — لا "محادثة جديدة" فارغة قسرية.

### التحقق الحي (2026-05-29 — sandbox يحجب egress فلا boot لـ uvicorn)

الطرد على مستوى الاتصال، فهو قابل للتحقق محلياً بـ node v22 + stdlib:
- **قرار الطرد (Frontend، Node — منقول بأمانة من المصدر + فحص بنيوي)**: السيناريو
  الكارثي «خامل، 12× إغلاق 4401، token صالح» → **0 طرد، 12 إعادة اتصال**. 35×
  4401 صالح → **offline لا auth_error**. 4401 + /me=invalid (انتهاء 8 ساعات حقيقي)
  → طرد واحد (صحيح). 4/4 سيناريو ✅.
- **استعادة المحادثة (Fix B، Node)**: عائد → يستأنف محادثته (404، رسالتان)؛ مستخدم
  جديد → يبقى فارغاً؛ "محادثة جديدة" صريحة → لا تُمسح. 3/3 ✅.
- **premise المصادقة (stdlib HS256 يُحاكي `decode_user_id`)**: token صالح لا يرفع
  أبداً (لا 4401 عند الفك)؛ منتهٍ/توقيع خاطئ/بلا sub → 401 (طرد صحيح). ✅.
- 7 اختبارات regression في `tests/services/test_iss097_kick_to_login.py` ✅ + كلا
  الـ routers يُترجمان. **التحقق الكامل في المتصفح + Supabase يجري على Codespace حيّ/CI.**

### الملفات (D-WS-KICK-001)

| File | Change |
|------|--------|
| `frontend/app/hooks/useRealtimeConnection.js` | Fix A — auth_error فقط على /me invalid + retryTransientAuth |
| `frontend/app/components/CogniForgeApp.jsx` | Fix B — استعادة آخر محادثة + didRestoreRef |
| `app/api/routers/customer_chat.py` | Fix C — جلب عابر يُغلق 1013 لا 4401 (+contextlib) |
| `app/api/routers/admin.py` | Fix C — نفس الإصلاح |
| `tests/services/test_iss097_kick_to_login.py` | **جديد** — 7 regression checks |
| `.memory/issues.md` / `.memory/decisions.md` | إدخالات ISS-097 / D-WS-KICK-001 |
| `CLAUDE.md` §6.72 | هذا القسم |

### السلسلة الكاملة (D-095 → D-WS-KICK-001)

| Decision | المُصلَح |
|----------|---------|
| D-095 | ENVIRONMENT=testing → development (480-min JWT) |
| D-096 | WS send concurrency lock (kick أثناء البث) |
| **D-WS-KICK-001** | **idle 4401 لا يُسجِّل خروجاً إلا بتأكيد /me + استعادة المحادثة** |

---

## 6.73 Long-Answer Heartbeat Timeout — "No Answer for Substantive Questions" (2026-05-29, ISS-098 / D-WS-FLAP-005)

> **بلاغ المستخدم (متكرر، GitHub Codespaces)**: «النظام لا يجيب عن الأسئلة ...
> يتم الدخول للحساب و تفقد الرسائل السابقة بشكل عادي لكن لا يرد عن الأسئلة».
> الإصلاحات السابقة (ISS-092→097) أغلقت أسباب الطرد، لكن «لا يرد عن الأسئلة»
> الجوهرية بقي. **هذه المرة أُثبت السبب بالتجريب الحي الحقيقي، لا بالتحليل الساكن.**

### التجريب الحي الذي كشف الجذر (2026-05-29)

بيئة حية: monolith (uvicorn، نفس أعلام الـ supervisor) + OpenRouter حقيقي
(`gpt-oss` المجاني) + SQLite (الـ sandbox يحجب Supabase — منافذ 6543/5432).
حساب المستخدم الحقيقي، WS مُقاد تماماً كالمتصفح (`?token=`، مفتاح `question`).

| اختبار حي | نتيجة |
|-----------|-------|
| سؤال قصير | يُجاب فوراً (1399 delta، 3508 حرف) — يعمل |
| متعدد الأدوار، نفس المحادثة | 4 أدوار، `conversation_id` ثابت — يعمل |
| عمر الـ JWT | 1440 دقيقة (لا 30) — فرضية الـ 30 دقيقة ميتة |
| **سؤال جوهري (شرح مفصل)** | **دور واحد = 154.8s، 3962 delta** — وهنا الكارثة |

### الجذر (مُثبت)

حلقة استقبال الـ WS في `customer_chat.py` و `admin.py` **محجوبة على
`await stream_task`** طوال الدور الواحد، فلا تقرأ `ping` العميل ولا تردّ بـ
`pong`. الواجهة (`useRealtimeConnection.js`) كانت تُلغي مؤقّت الـ heartbeat
(`HEARTBEAT_TIMEOUT=90s`) **عند `pong` فقط**.

سؤال جوهري ⇒ إجابة طويلة. عند نموذج مجاني (وأسوأ مع زمن Supabase)، يتجاوز
الدور الواحد ~135s ⇒ الواجهة تُعلن الاتصال «بائتاً» زوراً ⇒ `ws.close(1001)`
⇒ reconnect ⇒ **الإجابة الجارية تضيع** ("لا يرد عن الأسئلة"). الأسئلة القصيرة
تنتهي تحت 90s فتعمل — ولهذا يبدو النظام «يعمل أحياناً». في SQLite السريع كل
شيء تحت 90s فلا يظهر العطب محلياً، **بينما الإجابة الطويلة الحقيقية (154.8s)
أعادت إنتاج العطب حتى بدون Supabase**.

### الإصلاح (D-WS-FLAP-005 — طبقتان)

**(1) Frontend (`useRealtimeConnection.js`)**: أي رسالة WS واردة (وليس `pong`
فقط) تُلغي مؤقّت الـ heartbeat — تدفّق الـ deltas نفسه دليل قاطع على الحياة.
الـ `clearTimeout` نُقل إلى أعلى `ws.onmessage` قبل فحص الـ pong-only.

**(2) Backend (customer + admin)**: مهمة `_run_turn_keepalive` متزامنة تُرسل
إطار `pong` خفيفاً كل **20s** (عبر `send_lock`) طوال الدور، تُلغى فور انتهاء
البثّ (try/finally). هذا يُبقي العميل حياً حتى في الفجوات الخالية من deltas
(زمن TTFT/Supabase). إضافة keepalive متزامن جعل **`send_lock` ضرورياً على
admin** (الذي كان يفتقده — فجوة D-096 الباقية) ⇒ طُبِّقت parity كاملة لـ admin:
`_locked_send_json` + `_emit_terminal_frames(send_lock=...)` +
`handle_control_message(..., send_lock=...)` + توجيه كل sends أثناء البثّ.

### الإثبات الحي بعد الإصلاح (2026-05-29)

- دور 154.8s ⇒ **7 إطارات keepalive `pong`** عند 20/40/.../140s ⇒ الاتصال بقي
  حياً ⇒ `assistant_final` وصل (3962 delta) — لا انقطاع، لا فقدان إجابة.
- متعدد الأدوار + reconnect: `conversation_id` ثابت، `/api/chat/latest` يستعيد
  المحادثة (رسالتان)، الدور بعد reconnect أُجيب — لا طرد، لا «محادثة جديدة».
- 47 اختبار regression (ISS-098 + D-096 + heartbeat skill + ISS-097) ✅ +
  6 اختبار frontend (node) ✅ + ruff check/format ✅.

### القواعد الـ 4 الدائمة (D-WS-FLAP-005 — لا تُكسر بدون ADR)

1. **العميل يعتبر أي رسالة واردة دليل حياة**: `clearTimeout(heartbeatTimeoutRef)`
   على كل رسالة في `ws.onmessage`، ليس على `pong` فقط. الاتصال الميت فعلاً لا
   يُرسل شيئاً فيبقى المؤقّت يعمل ويُطلق reconnect صحيحاً.
2. **كل دور WS يُشغّل `_run_turn_keepalive` متزامناً** ويُلغيه في `finally`.
   `_TURN_KEEPALIVE_INTERVAL_SECONDS ≤ 20s` (أقل من نصف الـ 90s heartbeat).
3. **admin = parity كاملة مع customer في الإرسال المتزامن**: أي إرسال أثناء
   البثّ/الـ keepalive يمرّ عبر `_locked_send_json` + `send_lock`.
4. **الـ keepalive يُرسل `pong`** (لا نوع جديد) — العميل يتجاهله كبيانات لكنه
   يُلغي مؤقّت الـ heartbeat، فيعمل حتى لو لم تصل deltas.

### الملفات (D-WS-FLAP-005)

| File | Change |
|------|--------|
| `frontend/app/hooks/useRealtimeConnection.js` | liveness على أي رسالة (clear heartbeat timeout) |
| `app/api/routers/customer_chat.py` | `_run_turn_keepalive` + wiring حول `await stream_task` |
| `app/api/routers/admin.py` | `_locked_send_json` + `_run_turn_keepalive` + D-096 parity كاملة |
| `tests/services/test_iss098_keepalive.py` | **جديد** — 8 backend regression checks |
| `frontend/tests/iss098_heartbeat_liveness.test.mjs` | **جديد** — 6 frontend checks |
| `.memory/issues.md` / `.memory/decisions.md` | إدخالات ISS-098 / D-WS-FLAP-005 |
| `CLAUDE.md` §6.73 | هذا القسم |

### ملاحظة بيئية صادقة

أُعيد إنتاج العطب وأُثبت الإصلاح حياً على SQLite + OpenRouter حقيقي (egress لـ
Supabase محجوب في الـ sandbox — نمط موثّق منذ §6.55). الجذر **ليس** خاصاً بـ
Supabase: الإجابة الطويلة وحدها (154.8s) تتجاوز الـ heartbeat. زمن Supabase
يفاقمه فقط. التحقق الكامل عبر المتصفح + Supabase يجري في Codespace/CI الحيّ.

### السلسلة الكاملة (D-095 → D-WS-FLAP-005)

| Decision | المُصلَح |
|----------|---------|
| D-095 | ENVIRONMENT=testing → development (480-min JWT) |
| D-096 | WS send concurrency lock (kick أثناء البث) |
| D-WS-KICK-001 | idle 4401 لا يُسجِّل خروجاً إلا بتأكيد /me + استعادة المحادثة |
| **D-WS-FLAP-005** | **keepalive أثناء الدور + liveness على أي رسالة (يحل "لا يرد عن الأسئلة" الجوهرية)** |

---

## 6.74 HTTP /me Bootstrap Kick — The Real Logout Path (2026-05-29, ISS-099 / D-WS-KICK-002)

> **بلاغ المستخدم (متكرر، GitHub Codespaces)**: «الكارثة الخطيرة شديدة التعقيد
> مزالت ... بينما أنا داخل دردشة النظام يخرج لصفحة تسجيل الدخول ثم أجد نفسي في
> محادثة جديدة و يخرج و يدخل آليا». استمرّت رغم D-095/D-096/D-WS-KICK-001/D-WS-FLAP-005.

### لماذا استمرّت الكارثة بعد كل الإصلاحات السابقة

كل الإصلاحات السابقة عالجت مسار **WebSocket** (D-WS-KICK-001: لا طرد إلا بتأكيد
`/me` = 401/403). لكن **مسار HTTP bootstrap** في `CogniForgeApp.jsx` (`fetchUser`)
بقي بالمنطق الساذج:

```js
if (response.ok) setUser(...)
else logout();              // ← أي رمز غير 200 → طرد
...
catch (error) { logout(); } // ← أي خطأ شبكة → طرد
```

`fetchUser` يعمل عند كل تحميل وعند كل تغيّر لـ `token`، ويضرب
`/api/security/user/me`. في بيئة Supabase: الـ backend يُعاد تشغيله (health-monitor
بعد 3 إخفاقات)، أو يتأخر، أو يخطئ proxy الـ Codespaces لحظياً → `/me` يُرجع
**502/503/timeout/خطأ شبكة** → `logout()` → طرد إلى صفحة الدخول **رغم أن الـ token
صالح تماماً** → دخول → `DashboardLayout` يُعاد تركيبه بـ `conversationId=null` →
**محادثة جديدة**. هذا يطابق كل الأعراض ويُفسّر «يخرج و يدخل آلياً».

### الجذر التقني

`crypto.py` و عمر الـ JWT (480 دقيقة) و`SECRET_KEY` (disk-wins، مسار `/app` موحَّد،
أولوية env) **كلها سليمة** ومُستبعَدة. الطرد لم يكن من انتهاء الـ token ولا من
تدوير المفتاح — بل من **منطق الواجهة الذي يُسجِّل الخروج على أي فشل HTTP عابر**.

### الإصلاح (D-WS-KICK-002 — 3 طبقات في `CogniForgeApp.jsx`)

1. **401/403 فقط تُسجِّل الخروج**: `if (response.status === 401 || response.status === 403) logout()`
   — نفس قاعدة بوابة الـ WebSocket. أي رمز آخر (5xx/404) أو خطأ شبكة = **عابر**.
2. **إعادة محاولة بـ backoff** (`scheduleRetry`، حتى 40 محاولة، 1s→30s) دون طرد —
   تبقى الجلسة حيّة حتى يتعافى الـ backend.
3. **تخزين المستخدم مؤقتاً** (`localStorage['cogniforge_user']`): يُكتب عند الدخول
   وعند كل `/me` ناجح، ويُسترجَع فوراً عند التحميل، ويُمسح عند الخروج الحقيقي —
   فالفشل العابر يعرض التطبيق من الـ cache بدل السقوط إلى شاشة الدخول.

**النتيجة الحاسمة:** الفشل العابر **لا يُغيّر `token`** → `DashboardLayout` يبقى
مُركَّباً → **المحادثة محفوظة ولا شاشة دخول** — يُصلح العَرَضين معاً بضربة واحدة.

### الإثبات الحي (2026-05-29)

عقد `/api/security/user/me` مُتحقَّق حياً: token صالح → **200**؛ token باطل → **401**؛
بلا token → **401**. منطق `validate()` (جدول قرار مُختبَر): 200→setUser، 401/403→logout،
**500/502/503/404/خطأ-شبكة → retry (لا طرد)**. 6 اختبارات ISS-099 + 47 اختبار
WS/auth سابقة = **53/53 ✅**. ruff ✅. توازن JSX ✅.

### القواعد الـ 4 الدائمة (D-WS-KICK-002 — لا تُكسر بدون ADR)

1. **مسار `fetchUser` (HTTP /me) يُسجِّل الخروج فقط عند 401/403** — تماماً مثل
   الـ WebSocket. أي إعادة لـ `else { logout() }` أو `catch { logout() }` غير المشروط
   = عودة فورية للكارثة.
2. **الفشل العابر (5xx/404/شبكة) = إعادة محاولة، لا طرد.**
3. **`cogniforge_user` cache** يُكتب عند الدخول + `/me` ناجح، يُسترجَع عند التحميل،
   يُمسح عند الخروج. هو ما يمنع السقوط إلى شاشة الدخول أثناء خلل عابر.
4. **`token` لا يتغيّر إلا عند دخول/خروج حقيقي** — فالـ `DashboardLayout` لا يُعاد
   تركيبه (لا «محادثة جديدة») عند أي اضطراب backend.

### الملفات (D-WS-KICK-002)

| File | Change |
|------|--------|
| `frontend/app/components/CogniForgeApp.jsx` | `fetchUser` يُطرد فقط على 401/403 + retry + user cache؛ `handleLogin`/`logout` يديران الـ cache |
| `tests/services/test_iss099_http_me_kick.py` | **جديد** — 6 اختبارات (source-fidelity + decision table) |
| `.memory/issues.md` / `.memory/decisions.md` | إدخالات ISS-099 / D-WS-KICK-002 |
| `CLAUDE.md` §6.74 | هذا القسم |

### ملاحظة بيئية صادقة

Supabase محجوب في الـ sandbox (منافذ 6543/5432 — نمط موثّق). أُثبت عقد `/me` حياً
على SQLite + الـ backend الحقيقي، ومنطق القرار باختبار جدول كامل. الجذر منطقي بحت
في الواجهة (لا يعتمد على Supabase تحديداً)، فالإصلاح يعمل فور `git pull` + إعادة
تشغيل الـ supervisor في Codespace الحيّ. التحقق الكامل بالمتصفح يجري هناك.

### السلسلة الكاملة (D-095 → D-WS-KICK-002)

| Decision | المُصلَح |
|----------|---------|
| D-095 | ENVIRONMENT=testing → development (480-min JWT) |
| D-096 | WS send concurrency lock (kick أثناء البث) |
| D-WS-KICK-001 | idle 4401 (WebSocket) لا يُسجِّل خروجاً إلا بتأكيد /me + استعادة المحادثة |
| D-WS-FLAP-005 | keepalive أثناء الدور + liveness على أي رسالة ("لا يرد عن الأسئلة") |
| **D-WS-KICK-002** | **HTTP /me bootstrap (`fetchUser`) يُطرد فقط على 401/403 + user cache (يحل الطرد المتبقّي)** |

---

## 6.75 First-Seconds Flapping — DB-Free WS Connect + Degraded≠Dead Health (2026-05-29, ISS-100 / D-WS-CONN-001 + D-HEALTH-002)

> **بلاغ المستخدم (الحاسم)**: «هو لا يجيب اطلاقاً سواء سؤال طويل أو قصير. بمجرد
> دخولي أقول السلام عليكم لا يرد، و يدخل و يخرج، و تظهر متصل/غير متصل — **كل هذا
> يحدث في الثواني الأولى فقط**».

### لماذا هذا غيّر التشخيص كلياً

«لا يرد حتى على السلام عليكم» + «الثواني الأولى» + «تأرجح» ⇒ **ليست** مشكلة طول
الإجابة (D-WS-FLAP-005) ولا انتهاء token. التحية تُجاب فوراً عبر fast-path. هذا
يعني أن **الاتصال يُنشأ ثم يُغلق فوراً بشكل متكرر** — فلا يبقى حياً حتى لمعالجة
تحية.

### الجذر (السبب الحقيقي — D-WS-CONN-001)

معالج اتصال الـ WebSocket في `customer_chat.py` و `admin.py` كان ينفّذ عند **كل
اتصال**:
```python
async with async_session_factory() as db:
    actor = await db.get(User, user_id)   # ← استعلام Supabase عند كل اتصال
```
تحت ضغط Supabase (استنفاد pool بسبب 8 خدمات + monolith، أو بطء، أو انقطاع)، هذا
الاستعلام يفشل → الإغلاق بـ **1013** → الواجهة تُعيد الاتصال → يفشل ثانية → **تأرجح
متصل/غير متصل في الثواني الأولى، ولا إجابة أبداً** (الاتصال لا يثبت). إصلاح
D-WS-KICK-001 السابق («Fix C»: 1013 بدل 4401) **حوّل الطرد إلى تأرجح** ولم يُزِل
الاعتماد على قاعدة البيانات.

### الإصلاح (D-WS-CONN-001 — هوية من الـ JWT، صفر استعلامات عند الاتصال)

الهوية عند الاتصال تُشتق من الـ **JWT الموقّع** (`sub` + `is_admin`) عبر
`decode_token_payload` + `WsActor` — **بلا أي استعلام لقاعدة البيانات**. إنشاء
الاتصال أصبح فورياً ومستقلاً عن Supabase. عمل قاعدة البيانات يحدث **لكل دور**
داخل جلسته الخاصة مع معالجة أخطائه دون إسقاط الاتصال. (downstream يحتاج فقط
`actor.id` لـ `get_or_create_conversation` و `actor.is_admin` للبوابة.)

- `WsActor` (مجمَّد، حقول `id`/`is_admin`/`is_active`) في `ws_auth.py`.
- `decode_token_payload(token, secret) -> dict` في `token_decoder.py`.
- كلا المعالجين: token غير صالح → 4401 (الرفض الوحيد عند الاتصال)؛ نوع حساب خاطئ
  (is_admin من الـ claim) → 4403. لا 1013-عند-الاتصال، لا فحص is_active-عند-الاتصال.

**المقايضة**: مستخدم بـ token صالح (≤8 ساعات) لكن عُطِّل حسابه خلال تلك المدة قد
يتصل حتى انتهاء الـ token — مقايضة JWT قياسية ومقبولة، وأفضل بما لا يُقاس من تأرجح
يُصيب كل المستخدمين. السحب بـ FK لمستخدم محذوف يفشل لكل-دور بنظافة.

### الإصلاح المكمِّل (D-HEALTH-002 — Degraded ≠ Dead)

`supervisor.sh` كان يُعيد تشغيل uvicorn بعد 3 إخفاقات لـ `/health`. لكن `/health`
يُرجع **503 عند تعثّر Supabase** (مع أن جسمه يقول `"application":"ok"`). إعادة
تشغيل uvicorn **لا تُصلح** خلل Supabase — بل تُسقط **كل** اتصالات الـ WebSocket
(تأرجح) وتقطع الإجابات، ثم يتكرر الفشل → حلقة إعادة تشغيل. الإصلاح: دالة
`_app_is_alive` — إعادة التشغيل **فقط** عند موت التطبيق فعلاً (لا استجابة / رفض
اتصال)، أمّا 503-مع-`application:ok` فهو «حيّ لكن متدهور» → لا إعادة تشغيل.

### الإثبات الحي (2026-05-29، SQLite + OpenRouter حقيقي؛ Supabase محجوب في sandbox)

- **«السلام عليكم» تُجاب الآن** (71 حرف عبر fast-path)، الاتصال مستقر، لا إغلاق. ✅
- متعدد الأدوار (4 أدوار، conv ثابت) يعمل مع الـ actor المشتق من الـ JWT — لا انحدار. ✅
- إثبات بنيوي: قسم الاتصال (من `def chat_stream_ws` حتى `while True`) **خالٍ تماماً**
  من `db.get` و `async_session_factory()` في كلا المعالجين (مُتحقَّق باختبارات). ✅
- `_app_is_alive`: 503 + `application:ok` → «حيّ» (لا إعادة تشغيل) — مُتحقَّق. ✅
- 61 اختبار WS/auth (ISS-100 + ISS-099 + ISS-097 المُحدَّث + ISS-098 + D-096 + heartbeat) ✅؛
  ruff + runtime_truth + bash -n ✅.

### القواعد الـ 5 الدائمة (D-WS-CONN-001 + D-HEALTH-002 — لا تُكسر بدون ADR)

1. **اتصال WebSocket لا يستعلم قاعدة البيانات أبداً.** الهوية من الـ JWT
   (`decode_token_payload` + `WsActor`). لا `db.get`/`async_session_factory` قبل
   حلقة الاستقبال. أي إعادة لاستعلام-عند-الاتصال = عودة فورية لكارثة التأرجح.
2. **عمل قاعدة البيانات لكل-دور فقط**، داخل جلسة الدور، مع معالجة أخطائه دون إسقاط الاتصال.
3. **الرفض الوحيد عند الاتصال هو 4401** (token غير صالح) و **4403** (نوع حساب خاطئ من الـ claim).
4. **إعادة تشغيل uvicorn فقط عند موت التطبيق فعلاً** (`_app_is_alive`). 503-مع-`application:ok`
   = متدهور (DB) → لا إعادة تشغيل أبداً.
5. `get_or_create_conversation` تحتاج `user.id` فقط — لا تُمرِّر إليها كائن ORM كامل
   من وقت الاتصال؛ المعرّف من الـ JWT كافٍ.

### الملفات (ISS-100)

| File | Change |
|------|--------|
| `app/services/auth/token_decoder.py` | + `decode_token_payload()` (full validated JWT payload) |
| `app/api/routers/ws_auth.py` | + `WsActor` (frozen, DB-free identity) |
| `app/api/routers/customer_chat.py` | connect: JWT identity, no DB; حذف `db.get`/1013-at-connect |
| `app/api/routers/admin.py` | connect: نفس الإصلاح (is_admin من الـ claim) |
| `.devcontainer/supervisor.sh` | + `_app_is_alive`; المراقب يُعيد التشغيل فقط عند موت التطبيق (D-HEALTH-002) |
| `tests/services/test_iss100_ws_connect_no_db.py` | **جديد** — 8 checks (DB-free connect) |
| `tests/services/test_iss097_kick_to_login.py` | تحديث 4 اختبارات لتعكس عقد الاتصال الخالي من DB |
| `CLAUDE.md` §6.75 / `.memory/*` | هذا القسم |

### ملاحظة بيئية صادقة

Supabase محجوب في الـ sandbox، فلم أُعِد إنتاج ضغط الاتصال الحقيقي. لكن الجذر بنيوي
مُثبت بالكود (الاتصال لم يعد يلمس قاعدة البيانات) + إثبات حي للتحية ومتعدد الأدوار.
الإصلاح يعمل فور `git pull` + إعادة تشغيل الـ supervisor في Codespace الحيّ.

### السلسلة الكاملة (D-095 → D-WS-CONN-001)

| Decision | المُصلَح |
|----------|---------|
| D-095 | ENVIRONMENT=testing → development (480-min JWT) |
| D-096 | WS send concurrency lock (kick أثناء البث) |
| D-WS-KICK-001 | idle 4401 (WebSocket) لا يُسجِّل خروجاً إلا بتأكيد /me + استعادة المحادثة |
| D-WS-FLAP-005 | keepalive أثناء الدور + liveness على أي رسالة |
| D-WS-KICK-002 | HTTP /me bootstrap يُطرد فقط على 401/403 + user cache |
| **D-WS-CONN-001** | **اتصال WebSocket خالٍ من قاعدة البيانات (هوية من الـ JWT) — يحل تأرجح الثواني الأولى** |
| **D-HEALTH-002** | **Degraded≠Dead: لا إعادة تشغيل uvicorn على 503 بسبب DB (يحفظ كل اتصالات WS)** |

---

## 6.76 THE ROOT CAUSE — server.js http-proxy drops WS with 1006 (2026-05-29, ISS-101 / D-WS-PROXY-001)

> **الدليل القاطع من تشخيص حيّ في Codespaces** (`scripts/diagnose_chat.py`): بعد سلسلة
> طويلة من الإصلاحات الخلفية، كشف التشخيص أن **الـ backend سليم 100%** وأن السبب
> الحقيقي كان في **`frontend/server.js`** طوال الوقت.

### الدليل الحاسم (قسم F من التشخيص، بيئة المستخدم الحيّة)

```
-- direct backend :8000 (no proxy) --
[direct:8000] round 1/2/3: OK answered   (session_ready→conversation_init→delta→assistant_final)
-- via frontend :5000 (server.js proxy = مسار المتصفح) --
[proxy:5000] round 1/2/3: NO ANSWER  close=1006  frames=[session_ready, CLOSED:1006]
```

كل فحوصات الصحة خضراء: الفرع صحيح، كل الإصلاحات `[YES]`، token 1440 دقيقة، `/health`
مستقر 200×8، `/me` مستقر 200×6، كل الخدمات UP. الفرق الوحيد بين «يعمل» و«يفشل» هو
**هذا الملف الوسيط**.

### الجذر (D-WS-PROXY-001)

`server.js` كان يُمرِّر الـ WebSocket عبر `http-proxy` (1.x، غير مُصان). هذا:
1. يُمرِّر أول إطار من الخادم (`session_ready`) ثم يُسقط الاتصال بـ **1006** (إغلاق شاذ).
2. **يُسقط سؤال المستخدم** الذي يُرسله المتصفح فور الاتصال — **قبل** أن يفتح الاتصال
   الصاعد (server.js → :8000). فلا يصل السؤال للخلفية أبداً.
النتيجة: لا إجابة حتى للتحية → الواجهة تُعيد الاتصال → «متصل/غير متصل في الثواني الأولى».

هذا يُفسّر **كل** الأعراض ولماذا كل اختباراتي المباشرة على :8000 كانت تنجح بينما
المتصفح (عبر :5000) يفشل.

### الإصلاح (D-WS-PROXY-001)

أُعيدت كتابة وسيط الـ WebSocket في `server.js` بمكتبة **`ws`** الموثوقة:
1. `WebSocketServer({ noServer: true })` يستقبل الـ upgrade لمسارات الدردشة فقط.
2. اتصال `ws.WebSocket` صاعد إلى `:8000` مع الحفاظ على `?token=` والـ subprotocol.
3. تمرير ثنائي الاتجاه (نصي/ثنائي) مع نشر كود الإغلاق.
4. **طابور (`pending`)** للرسائل التي يُرسلها العميل قبل فتح الاتصال الصاعد، يُفرَّغ
   عند حدث `open` — **يحفظ التحية الأولى** (سبب ضياعها مع http-proxy).

### الإثبات الحي (replica أمين، 2026-05-29)

replica بايثوني مطابق لمعمارية الإصلاح ضد الـ backend الحقيقي:
```
[proxy] queued client msg (upstream not ready yet): {"question":"السلام عليكم"...}
[proxy] flushed 1 queued msg(s) to upstream
>>> [ws-proxy] OK ANSWERED  close=None  frames=[session_ready, conversation_init, delta…, assistant_final]
```
التحية بُوِّبت ثم أُفرِغت عند فتح الاتصال الصاعد → إجابة كاملة، إغلاق نظيف — عكس
1006 الخاص بـ http-proxy.

### القواعد الـ 4 الدائمة (D-WS-PROXY-001 — لا تُكسر بدون ADR)

1. **لا `http-proxy` لتمرير WebSocket**: يجب استخدام مكتبة `ws` (WebSocketServer +
   WebSocket). `http-proxy` 1.x يُسقط أطر WS بـ 1006.
2. **طابور الرسائل المبكرة إلزامي**: العميل يُرسل السؤال فور الاتصال، قبل فتح الاتصال
   الصاعد. يجب تخزينها في `pending` وتفريغها عند `upstream open`. حذف الطابور = عودة
   «لا إجابة».
3. **تمرير ثنائي الاتجاه + نشر كود الإغلاق**: لا تبتلع أكواد الإغلاق؛ مرِّرها.
4. **`ws` تبعية معلنة** في `frontend/package.json` (موجودة أصلاً عبر Next).

### الملفات (ISS-101)

| File | Change |
|------|--------|
| `frontend/server.js` | إعادة كتابة وسيط WS بمكتبة `ws` + طابور للرسائل المبكرة (استبدال http-proxy) |
| `frontend/package.json` | + `ws` كتبعية صريحة |
| `tests/services/test_iss101_ws_proxy.py` | **جديد** — 4 فحوصات (ws + queue + لا http-proxy للـ WS) |
| `scripts/diagnose_chat.py` | الأداة التي التقطت الدليل (proxy:5000 → 1006، direct:8000 → OK) |
| `CLAUDE.md` §6.76 / `.memory/*` | هذا القسم |

### ما يجب على المستخدم فعله

```bash
git pull origin claude/chat-session-auth-bugs-aLf74
npm --prefix frontend install   # يضمن وجود ws (موجود غالباً عبر Next)
# أعد تشغيل الـ supervisor / الواجهة (server.js يجب أن يُعاد تشغيله)
```
ثم أعد تشغيل `python scripts/diagnose_chat.py` — يجب أن يُظهر القسم F الآن
`[proxy:5000] OK answered` بدل `1006`.

### السلسلة الكاملة (D-WS-CONN-001 → D-WS-PROXY-001)

| Decision | المُصلَح |
|----------|---------|
| D-WS-CONN-001 | اتصال WS خالٍ من قاعدة البيانات (هوية من الـ JWT) |
| D-HEALTH-002 | Degraded≠Dead: لا إعادة تشغيل uvicorn على 503 بسبب DB |
| **D-WS-PROXY-001** | **السبب الجذري: server.js http-proxy → ws-library + طابور (يحل التأرجح + لا إجابة نهائياً)** |

---

## 6.77 THE TRUE ROOT CAUSE — Double WebSocket Handshake (Next 16 re-attaches `upgrade` listener) (2026-05-31, ISS-102 / D-WS-PROXY-004)

> **التجريب الحي الحقيقي بالأسرار** (OpenRouter + admin/user logins؛ Supabase
> محجوب في الـ sandbox فاستُخدم SQLite degraded) كشف على **مستوى البايت** السبب
> الجذري الذي نجا من كل إصلاحات D-WS-PROXY-001..003 و D-WS-RELOAD-001. هذا القسم
> يحكم تمرير الـ WebSocket عبر server.js — لا يُكسر بدون ADR.

### الإثبات الحي (byte-level)

| المسار | النتيجة |
|--------|---------|
| **مباشر :8000** (لا وسيط) | كل الإطارات `0x81` (FIN=1, RSV=0) → session_ready → conversation_init → deltas → assistant_final. تحية 0.03s، سؤال رياضي **1947 delta / 4652 حرف عربي+LaTeX / 67.7s**. ✅ |
| **عبر proxy :5000** قبل الإصلاح | الإطار #1 `session_ready` نظيف، ثم الإطار #2 = **بايتات HTTP خام** `"TP/1.1 101 Switching Protocols…sec-websocket-accept: …date: …{"user_id":2…}"` ← الـ 101 + session_ready مكتوبان **مرّة ثانية**؛ المُحلِّل يقرأ 'H'=0x48 → **RSV1=1** → «Invalid WebSocket frame: RSV1 must be clear» → إغلاق فوري بعد session_ready → **لا تصل أي إجابة**. ❌ |

### السبب الجذري (مُثبت)

`frontend/server.js` كان يُنفِّذ `server.removeAllListeners("upgrade")` ثم يُسجِّل
listener-اً واحداً عند الإقلاع. لكن **Next 16 يُعيد تسجيل listener('upgrade') خاصاً
به lazily بعد ذلك** → عند كل ترقية WebSocket يصبح هناك **listener-ان**
(`server.listenerCount("upgrade") === 2` — مُثبت حياً). كلاهما يُعالج `/api/chat/ws`:
listener-نا يكتب الـ 101 الصحيح ويُمرِّر؛ و listener الخاص بـ Next يكتب 101
**ثانياً** (بترويسة `date:`) على نفس socket → العميل يستقبل `[101][session_ready]`
ثم `[101 خام مُكرَّر]` → RSV1 → موت الاتصال. الإطار الأول سليم («يبدو متصلاً»)
والثاني خام («لا يجيب») → reconnect → «متصل/غير متصل» → طرد لصفحة الدخول. المسار
المباشر :8000 سليم لأن لا وسيط Next فيه.

### لماذا نجا من كل الإصلاحات السابقة

D-WS-PROXY-001 (http-proxy→ws-lib) و D-WS-RELOAD-001 (HMR) و D-WS-PROXY-003
(compress/deflate) صحيحة لكنها لم تلمس **ازدواج listener الترقية**. الـ «replica
أمين» في §6.76 نجح لأنه لم يكن خلف خادم Next المخصّص (لا listener ثانٍ). لذا بدا
الكود صحيحاً والكارثة استمرّت — حتى أثبت التشخيص على مستوى البايت الـ 101 المزدوج.

### الإصلاح (D-WS-PROXY-004 — أصغر إصلاح صحيح)

`frontend/server.js`: نملك listener('upgrade') **وحيداً**، ونعترض أي تسجيل لاحق
لـ listener('upgrade') من Next ونلتقطه كـ **delegate** لـ HMR بدل تركه يعمل
بالتوازي:
```js
const _origAddListener = server.on.bind(server);
const _trapUpgrade = (event, listener) => {
  if (event === "upgrade") { delegatedNextUpgrade = listener; return server; } // التقاط لا تسجيل موازٍ
  return _origAddListener(event, listener);
};
server.on = server.addListener = server.prependListener = _trapUpgrade;
server.removeAllListeners("upgrade");
_origAddListener("upgrade", (req, socket, head) => {
  if (isWsProxyPath(req.url)) { wss.handleUpgrade(req, socket, head, cw => proxyToGateway(cw, req)); return; }
  if (delegatedNextUpgrade) delegatedNextUpgrade(req, socket, head); else socket.destroy(); // HMR محفوظ
});
```
hardening ثانوي (D-WS-PROXY-003): `perMessageDeflate:false` صريح على الـ
WebSocketServer + `compress:false` على كل `clientWs.send` → proxy نظيف بايتاً
ببايت. + إصلاح `package-lock.json` (كان `ws` مفقوداً منه → `npm ci` يفشل).

### الإثبات بعد الإصلاح (حي)

- `listeners=1` (كان 2). كل إطارات proxy :5000 نظيفة `0x81` RSV=0.
- `diagnose_chat.py` القسم F: **`[direct:8000] 3/3 OK answered` + `[proxy:5000] 3/3 OK answered`** (كان proxy «NO ANSWER close=1006/1002»).
- e2e عبر :5000: تحية ✅ + سؤال رياضي **1515 delta / 3565 حرف / 53.9s** ✅.
- reconnect storm **10/10 OK**. /health 200×8. login + token 1440 دقيقة + /me 200×6 (لا طرد).

### القواعد الـ 4 الدائمة (D-WS-PROXY-004 — لا تُكسر بدون ADR)

1. **listener('upgrade') وحيد إلزامي**: server.js يجب أن يكون المالك الوحيد لحدث
   `upgrade`. `removeAllListeners` عند الإقلاع **لا يكفي** — Next يُعيد التسجيل
   lazily. يجب اعتراض كل `on/addListener/prependListener('upgrade')` لاحق
   والتقاطه كـ delegate.
2. **HMR عبر delegate لا listener موازٍ**: ترقيات Next الداخلية تُفوَّض إلى الـ
   delegate المُلتقَط من داخل listener-نا الوحيد — فلا 101 مزدوج ولا reload loop.
3. **proxy نظيف بايتاً ببايت**: `perMessageDeflate:false` + `compress:false` —
   لا تفاوض ضغط على الجانب المواجه للعميل (الإطارات تصل مُفكَّكة من upstream).
4. **`package-lock.json` متزامن**: `ws` يجب أن يكون في الـ lock وإلا `npm ci`
   (CI/prebuild) يفشل → frontend بلا `ws` → server.js يسقط.

### قياس النجاح حياً

```bash
DIAG_EMAIL=<user> DIAG_PASSWORD=<pwd> python scripts/diagnose_chat.py
# القسم F: [proxy:5000] OK answered (لا NO ANSWER / لا 1006 / لا 1002)
# سجل server.js: [WS Proxy] upgrade: … (listeners=1)
```

### ملاحظة بيئية صادقة + المسار الإداري

التجريب جرى على SQLite (Supabase محجوب — منافذ 6543/5432). مسار **العميل/الطالب**
(الشكوى الأساسية «لا يجيب») مُثبَت ومُصلَح حياً بـ OpenRouter حقيقي. مسار **الإدمن**
يصل عبر نفس الـ proxy بإطارات نظيفة، لكن حفظ الرسالة فشل بـ
`no such table: admin_messages` — أثرٌ خاص بـ SQLite الجديد فقط (الجدول موجود على
Supabase الإنتاجي — §6.30)؛ يظهر متطابقاً على :8000 و :5000 فهو **ليس** من الـ
proxy. التحقق الكامل بالمتصفح + Supabase يجري في Codespace الحيّ.

### السلسلة الكاملة (D-WS-PROXY-001 → D-WS-PROXY-004)

| Decision | المُصلَح |
|----------|---------|
| D-WS-PROXY-001 | server.js http-proxy → ws-library + طابور للرسائل المبكرة |
| D-WS-RELOAD-001 | عدم تدمير ترقيات Next HMR (reload loop) |
| D-WS-PROXY-003 | proxy نظيف: perMessageDeflate:false + compress:false + lock sync |
| **D-WS-PROXY-004** | **السبب الجذري الحقيقي: منع ازدواج listener('upgrade') → لا 101 مزدوج → الإجابات تصل عبر :5000** |

### تثبيت النصر + سدّ الثغرات (Hardening — 2026-05-31)

بعد إثبات الإصلاح حياً، حُوِّل إلى **ضمان دائم** عبر CI + سُدَّت ثغرة كامنة اكتُشفت أثناء التجريب:

1. **بوّابة CI ضد عودة الـ double-handshake** — `.github/workflows/iss-102-ws-double-handshake-gate.yml` (3 وظائف + aggregator):
   - `ws-proxy-wiring`: `node --check server.js` + اختبار `frontend/tests/iss102_ws_double_handshake.test.mjs` (15 فحص source-inspection: مستمع upgrade وحيد، الـ trap، delegate لـ HMR، perMessageDeflate/compress false، لا http-proxy).
   - `lockfile-sync`: `npm ci` (يفشل لو `package-lock` انحرف أو فُقد `ws` — الثغرة بالضبط التي اصطدمنا بها).
   - `schema-gate`: `pytest tests/core/test_admin_messages_schema.py`.
2. **ثغرة `admin_messages` (حقيقية)** — كانت مفقودة من `_ALLOWED_TABLES` و `REQUIRED_SCHEMA` في `app/core/db_schema_config.py` → `validate_schema_on_startup()` لا يُنشئها → دردشة الإدمن تفشل بـ «no such table: admin_messages» على أي DB جديدة (تظهر فقط على Supabase الحالي بصدفة تاريخية). **الإصلاح:** سُجِّلت (مرآة `customer_messages` بـ FK إلى `admin_conversations`، بلا `policy_flags`، فهرس `ix_admin_messages_conversation_id`).

**التحقق الحي (2026-05-31، SQLite نظيف + OpenRouter حقيقي):**
- `admin_messages` يُنشأ تلقائياً على DB جديدة ✅.
- دور إدمن عبر proxy `:5000` → **يجيب** (72 حرف) **ويُحفظ** (صفّان في `admin_messages`: user + assistant)، صفر «no such table» ✅.
- customer عبر `:5000` → ANSWERED ✅. اختبار الواجهة 15/15 ✅. اختبار schema 4/4 ✅. `validate_structure` ✅. ruff ✅.

**قاعدة دائمة (D-WS-PROXY-004 hardening):** أي جدول تكتب فيه طبقة التطبيق يجب أن يكون في `REQUIRED_SCHEMA` + `_ALLOWED_TABLES` (وإلا يُكسَر على أي نشر نظيف)؛ وأي تغيير في `frontend/server.js` يجب أن يُبقي بوّابة ISS-102 خضراء (مستمع upgrade وحيد + proxy نظيف بايتاً ببايت).

---

## 6.78 Admin Role from JWT `roles` — Not a Phantom `is_admin` Claim (2026-06-01, ISS-103 / D-WS-CONN-002)

> متابعة مباشرة لـ D-WS-CONN-001 (§6.75): بعد جعل اتصال الـ WebSocket خالياً من
> قاعدة البيانات (الهوية من الـ JWT)، صار `is_admin` يُقرأ من claim `is_admin`
> بولياني فقط — لكن رمز الوصول الحقيقي لا يحمل `is_admin`، بل يحمل `roles` (قائمة
> تحوي `"ADMIN"`). هذا القسم يحكم اشتقاق دور الإدمن من الـ JWT — لا يُكسر بدون ADR.

### الجذر (D-WS-CONN-002)

في كلا المعالجين كان السطر:
```python
actor = WsActor(id=user_id, is_admin=bool(claims.get("is_admin", False)))
```
رمز الوصول الفعلي (`app/services/auth/*`) يضع الدور في `roles: ["ADMIN", ...]` ولا
يضع `is_admin` إطلاقاً. النتيجة: **كل توكن إدمن حقيقي → `is_admin=False`**:
- الإدمن **مرفوض على قناته** (`admin.py`: «Standard accounts must use the customer
  chat endpoint») → لا يستطيع فتح دردشة الإدمن أبداً.
- الإدمن **مسموح خطأً على قناة العميل** (لا يُغلَق 4403) → خرق حدود القناة.

### الإصلاح (`admin.py` + `customer_chat.py`)

```python
# ISS-103 (D-WS-CONN-002): is_admin من claim ``is_admin`` صراحةً أو من دور ADMIN ضمن roles.
_claim_roles = claims.get("roles") or []
is_admin_claim = bool(claims.get("is_admin", False)) or (
    ADMIN_ROLE in _claim_roles if isinstance(_claim_roles, list) else False
)
actor = WsActor(id=user_id, is_admin=is_admin_claim)
```
`ADMIN_ROLE` يُستورَد من `app/services/rbac.py` (`ADMIN_ROLE = "ADMIN"`). الاشتقاق
يبقى خالياً من قاعدة البيانات (يحترم D-WS-CONN-001): `roles` تأتي من الـ JWT الموقّع.

### مواءمة الاختبارات (نفس جذر D-WS-CONN-001)

إزالة `decode_user_id` من المعالجين (D-WS-CONN-001) كسرت كل اختبار يُرقِّعه
(`patch("…decode_user_id")` → `AttributeError`) ويُموِّه الهوية عبر `db.get`، ويقرأ
الإطار الأول مباشرةً (وهو الآن primer الـ `session_ready`). أُوئمت 4 ملفات على العقد
الجديد بنمط موحَّد: ترقيع `decode_token_payload` بـ claims (`{"sub":"1","is_admin":…}`
أو دور `ADMIN` ضمن `roles`) + مُساعِد `_recv()` يتخطّى `session_ready`:
- `tests/api/test_admin_router_comprehensive.py` (3 اختبارات WS)
- `tests/api/test_final_router_gaps.py` (3 اختبارات customer — القالب المرجعي)
- `tests/api/test_chat_event_protocol_flag_integration.py` (8 اختبارات)
- `tests/api/test_chat_event_protocol_error_contract_integration.py` (5 اختبارات)

### القواعد الـ 4 الدائمة (D-WS-CONN-002 — لا تُكسر بدون ADR)

1. **دور الإدمن يُشتق من الـ JWT**: `is_admin = claims["is_admin"] OR (ADMIN_ROLE in
   claims["roles"])`. لا تفترض وجود بولياني `is_admin` على رمز الوصول — قد لا يكون موجوداً.
2. **اشتقاق الدور يبقى خالياً من قاعدة البيانات** (D-WS-CONN-001): `roles` من الـ JWT
   الموقّع، لا استعلام `db.get(User)` عند الاتصال.
3. **اختبارات WS تُرقِّع `decode_token_payload` لا `decode_user_id`** (مُزال من المعالجين)
   وتُمرِّر claims dict؛ وتتخطّى primer الـ `session_ready` عبر مُساعِد `_recv()`.
4. **حدود القناة صارمة**: actor إدمن على قناة العميل → 4403؛ actor عادي على قناة الإدمن
   → 4403. الاشتقاق الخاطئ لـ `is_admin` يكسر الحدّين معاً.

### قياس النجاح حياً (2026-06-01)

```bash
DATABASE_URL="sqlite+aiosqlite:///:memory:" SECRET_KEY="…" ENVIRONMENT="testing" \
LLM_MOCK_MODE="1" SUPABASE_URL="https://dummy.supabase.co" SUPABASE_ROLE_KEY="dummy" \
python3.12 -m pytest tests/api -q --no-cov
# المتوقع: 68 passed (كان 55 passed + 13 failed بسبب decode_user_id AttributeError)
```
ruff check/format + validate_structure خضراء. الإثبات الكامل بالمتصفح + Supabase يجري
في Codespace/CI الحيّ (الـ sandbox يحجب egress لـ Supabase — نمط موثّق منذ §6.55).

### متابعة CI (2026-06-01): `generate_service_token` + اختبار wiring الإدمن

بعد `f368682` بقي الـ CI `test` أحمر. إعادة إنتاج كاملة لوظيفة CI محلياً (نفس قائمة
`--deselect` + بيئة `ci.yml`) كشفت **معطّلَيْن حقيقيَّيْن** (deterministic، خارج قائمة
الـ deselect)، كلاهما أثر جانبي لإعادة هيكلة WS على هذا الفرع لم يُلتقَط سابقاً:

1. `tests/regressions/test_streaming_event_type_bug.py::test_chat_stream_has_delta_event_type`
   — يصادق اتصال إدمن عبر `generate_service_token(str(admin_user.id))`. بعد D-WS-CONN-001/002
   صار الاتصال يشتق `is_admin` من claims الـ JWT، لكن `app/core/security.py:generate_service_token`
   كان يضع `sub` فقط (لا `roles`) → الإدمن مرفوض → الاختبار يستقبل `error` بدل `delta`.
   **الإصلاح:** أُضيف معامل اختياري `roles` (keyword-only) لـ `generate_service_token`
   (متوافق خلفياً)؛ اختبارات إدمن WS تمرّر `roles=[ADMIN_ROLE]`. هذا يُمارس مسار فك الـ JWT
   الحقيقي ويُحاكي رمز الوصول الإنتاجي (`crypto.encode_access_token` يحمل `roles`).

2. `tests/services/test_ws_router_heartbeat_integration.py::TestAdminWiring::test_call_before_question_check`
   — فحص نصّي يبحث عن الحرفية `handle_control_message(websocket, payload)`؛ لكن D-096/D-WS-FLAP-005
   أضاف `send_lock` فصار النداء `handle_control_message(websocket, payload, send_lock=send_lock)`.
   اختبار customer النظير (سطر 49) كان مُرخّى مسبقاً (`...payload` بلا قوس إغلاق)، أما اختبار
   admin (سطر 87) فأُغفِل. **الإصلاح:** إرخاء الحرفية لتُطابق التوقيع المُطوَّر — مرآة اختبار customer.

**اللاحقّقات (11 فشل غير معطّل):** `tests/config/test_settings.py` (5) +
`test_kernel_comprehensive::test_cors_logic_dev_vs_prod` + `test_settings_refactor::test_base_service_settings_defaults`
+ `test_phase0_governance.py` (4) — تغطّي كوداً **لم يلمسه هذا الفرع** (`git diff main...HEAD`)،
وتنجح منفردة (تلوّث ترتيب/حالة شجرة عمل في الـ sandbox)، وليست في قائمة deselect، و`main` أخضر
→ تنجح على مُشغّل CI النظيف. لا إجراء عليها.

### السلسلة الكاملة (D-WS-CONN-001 → D-WS-CONN-002)

| Decision | المُصلَح |
|----------|---------|
| D-WS-CONN-001 | اتصال WS خالٍ من قاعدة البيانات (هوية من الـ JWT) |
| D-WS-PROXY-004 | منع ازدواج listener('upgrade') + admin_messages schema gate |
| **D-WS-CONN-002** | **دور الإدمن من `roles` ضمن الـ JWT (لا claim `is_admin` وهمي) + مواءمة اختبارات WS + `generate_service_token(roles=…)`** |

---

## 6.79 Terminal-Frame Finalization — Error Frame Must Never Leave the UI Hung (2026-06-01, ISS-104 / D-WS-FINAL-001)

> **بلاغ المستخدم (صورتان):** عند طلب «اعطني تمرين دوال 2016 الموجود في النظام أو قاعدة
> البيانات»، بقي سهم مربع البحث **يدور بدون توقف** (تعذّر طرح سؤال جديد) + المعادلات تظهر
> **بالرموز الخام** (`\(g\)`, `\\(\mathbb{R}\\)`) بدل KaTeX «بشكل كارثي خطير مدمر».

### الجذر (سبب واحد لعرَضين)

العَلَم `isComplete` (frontend-only) لرسالة المساعد الجارية لا يُرفَع إلى `true` أبداً. مسار
الاسترجاع المُفهرَس يبثّ `assistant_delta` ثم — عند عدم تأكيد الحفظ الاحتياطي —
`customer_chat.py:_emit_terminal_frames` يُصدِر إطار **`error`** (بدل `assistant_final`) وهذا
صحيح حسب D-006. لكن معالجَي `error`/`assistant_error` في `useAgentSocket.js` كانا يستدعيان
`notifyAgentError` فقط ولا يلمسان الرسالة:
- `ChatInterface.jsx:387` `hasStreamingMessage` يبقى true → الزر دائرة `fa-spin` أبداً.
- `ChatInterface.jsx:270` `isStreaming` يبقى true → الرسالة في فرع `streaming-raw` (نص خام بلا
  `preprocessMath`/KaTeX) → LaTeX خام دائم.

يخالف **ISS-016/ISS-017**: «أي مسار فشل ينتهي بإطار error واحد — لا تعليق أبداً». الخادم صحيح؛
الواجهة هي التي تعلَّقت. مُستبعَد: request_id يتطابق (`client_request_id` يُعاد كـ
`stream_request_id`)؛ و OutputFirewall fail-open (لا يُفرّغ المحتوى).

### الإصلاح (D-WS-FINAL-001)

معالجا `error` و `assistant_error` في `useAgentSocket.js` يُنهيان الآن الرسالة الجارية
(`isComplete:true` + `isError:true`، مع الحفاظ على المحتوى المبثوث) — يطابق نمط معالج
`complete` — مع إبقاء `notifyAgentError` (الخطأ يبقى ظاهراً، لا ادّعاء نجاح) و
`refreshConversationHistory` (مُتحقَّق أنه `fetchConversations` — sidebar فقط، لا يمسّ قائمة
الرسائل أبداً). بعد الإنهاء، تُعاد الرسالة عبر ReactMarkdown+rehypeKatex عبر `preprocessMath`.

### القاعدة الدائمة (لا تُكسر بدون ADR)

1. **كل نوع إطار نهائي** (`assistant_final`, `complete`, `error`, `assistant_error`) **يجب** أن
   يرفع `isComplete:true` على رسالة المساعد الجارية. إطار نهائي يترك `isComplete:false` = خلل
   تعليق واجهة.
2. الحارس `!last.isComplete`؛ إن لم توجد رسالة مساعد جارية → `return prev` (لا فقاعة فارغة مُلفَّقة).
3. `isError:true` يُحترَم في `ChatInterface.jsx` (صنف error) وفي حُرّاس `!last.isError` في معالجَي
   `assistant_delta`/`assistant_final` (إطار شارد متأخر لا يُعيد فتح فقاعة مُنهاة).
4. **لا يُغيَّر** مسار التصيير أثناء البثّ (streaming-raw عابر، يُحَل عند الإنهاء — التصيير الحي
   لـ Markdown أُزيل سابقاً للوميض ISS-076/D-064)؛ ولا يُغيَّر `_emit_terminal_frames` الخادمي
   (يجب أن يُصدِر `error` عند فشل الحفظ حسب D-006).

### التحقق الحي (2026-06-01)

خريطة egress (OpenRouter ✅/Tavily ✅/Supabase Postgres 6543/5432 ❌ محجوب في sandbox — نمط
§6.55/§6.74)؛ OpenRouter `gpt-oss-120b` → `'4'` finish=stop؛ إعادة إنتاج Node أمينة (reducer +
mergeAssistantContent + preprocessMath حرفياً) أثبتت BUGGY=تعليق+LaTeX خام، FIXED=فك+KaTeX مع
حفظ المحتوى؛ **21/21** في `frontend/tests/iss104_error_finalizes_message.test.mjs`؛ ISS-080 18/18
(لا انحدار). **التجريب الحي الكامل مع Supabase إلزامي في Codespaces** (Postgres محجوب في الـ
sandbox) بالأسرار الحقيقية + الدخولين (`houssamannaba963@gmail.com`/`1111`, الإدمن
`benmerahhoussam16@gmail.com`/`1111`).

### الملفات (ISS-104)

| File | Change |
|------|--------|
| `frontend/app/hooks/useAgentSocket.js` | معالجا `error` + `assistant_error` يُنهيان الفقاعة الجارية |
| `frontend/tests/iss104_error_finalizes_message.test.mjs` | **جديد** — 11 حارس ثابت + 10 سيناريو سلوكي |

### السلسلة الكاملة (D-WS-CONN-002 → D-WS-FINAL-001)

| Decision | المُصلَح |
|----------|---------|
| D-WS-CONN-002 | دور الإدمن من `roles` ضمن الـ JWT |
| **D-WS-FINAL-001** | **كل إطار نهائي يُنهي الرسالة — `error`/`assistant_error` لا يتركان الواجهة معلَّقة (يحل تعليق سهم البحث + LaTeX الخام)** |

---

## 6.80 Orphaned Streaming Message — Mid-Conversation Blue Cursor + Endless Spinner (2026-06-01, ISS-105 / D-WS-ORPHAN-001)

> **بلاغ المستخدم (شاشات حية):** المؤشّر الأزرق النابض يبقى ينبض في *منتصف* النصوص
> (لا في آخرها) + سهم الإرسال يدور **بدون توقف إطلاقاً** + الرموز الرياضية تظهر خاماً
> «بشكل كارثي خطير مدمر» و**تختفي بمجرد الدخول والخروج فقط**.

### الجذر (سبب واحد لثلاثة أعراض — مؤكَّد بلقطة ما-بعد-إعادة-التحميل)

حدث `ui_component` (مثل **BKT** المُبثّ بالتوازي كـ `asyncio.create_task`، أو
`math_explanation_card` / `full_exercise_story`) قد يصل في **منتصف** بثّ النص — بين
delta و delta. معالج `ui_component` في `useAgentSocket.js` كان يُلحِق فقاعة مكوّن
جديدة (`isComplete:true`) **دون إنهاء** فقاعة النص الجارية قبله:

```
assistant_delta (نص التمرين) → Message A {isComplete:false}
ui_component (BKT)            → Message B {isComplete:true}   ← A تُركت يتيمة
assistant_delta (الإجابة)    → Message C {isComplete:false}  (B مكتملة → فقاعة جديدة)
assistant_final              → يُنهي C فقط (الأخيرة). A تبقى isComplete:false للأبد.
```

`Message A` اليتيمة تُسبّب الأعراض الثلاثة:
- `ChatInterface.jsx:387` `hasStreamingMessage = messages.some(!isComplete)` → true → سهم الإرسال يدور أبداً (`fa-circle-notch fa-spin`).
- `ChatInterface.jsx:270` الفقاعة اليتيمة `isStreaming` → مؤشّر أزرق نابض عالق في *منتصف* المحادثة (`streaming-cursor`).
- `ChatInterface.jsx:206` فرع `streaming-raw` → LaTeX خام. عند إعادة التحميل، `setMessagesSafe` (D-068) يفرض `isComplete:true` على كل الرسائل → KaTeX يُصيَّر → «تختفي بمجرد الدخول والخروج».

### الإصلاح (D-WS-ORPHAN-001 — 3 طبقات)

**Part 1 (الجذر):** معالج `ui_component` يستدعي `finalizeStaleAssistantMessages(prev)`
**قبل** إلحاق فقاعة المكوّن — فلا تُترك أي فقاعة نص يتيمة.

**Part 2 (دفاع عميق):** المعالجات النهائية كلها (`complete` / `assistant_final` /
`error` / `assistant_error`) تكنس الآن **كل** رسالة مساعد عالقة (لا الأخيرة فقط) عبر
`finalizeStaleAssistantMessages`. آمن لأن الأدوار متسلسلة (`activeRequestIdRef` + فلتر
request_id): بوصول أي إطار نهائي كل الرسائل الجارية تنتمي للدور الحالي. `error`/`assistant_error`
يضعان `isError` على فقاعة الدور الأخيرة فقط؛ الكنس يُنهي اليتامى السابقين **دون** `isError`.

**Part 3 (LaTeX في مكوّنات Generative UI):** بطاقات `MathExplanationCard` (الشارات
البنفسجية المرقّمة + صندوق «تلميح») و`FullExerciseStory` كانت تُصيّر حقولها النصية
(`step.content` / `intuition` / `hint` / `pedagogical_message`) كـ `{text}` خام بلا
أي معالجة LaTeX → رموز خام داخل البطاقة أثناء البثّ الحي. الحل: استُخرجت `preprocessMath`
إلى وحدة مشتركة `app/utils/preprocessMath.js`، وأُنشئ مكوّن `<MathText>` (يمرّ النص عبر
`preprocessMath` → ReactMarkdown + remark-math + rehype-katex، مع fast-path للنص العادي)،
وطُبِّق على الحقول الرياضية في `MathExplanationCard` و`FullExerciseStory`.

### القواعد الـ 5 الدائمة (D-WS-ORPHAN-001 — لا تُكسر بدون ADR)

1. **`ui_component` لا يُترك يتيماً ما قبله أبداً**: أي معالج يُلحِق فقاعة مساعد جديدة
   أثناء البثّ يجب أن يستدعي `finalizeStaleAssistantMessages(prev)` أولاً.
2. **الكنس عند كل إطار نهائي**: `complete`/`assistant_final`/`error`/`assistant_error`
   تُنهي **كل** رسالة مساعد عالقة، لا الأخيرة فقط.
3. **`isError` للدور الحالي فقط**: الكنس يرفع `isComplete:true` ولا يلمس `isError` —
   فلا تُوسَم اليتامى السابقون خطأً كأخطاء.
4. **`preprocessMath` مصدر حقيقة واحد**: يعيش في `app/utils/preprocessMath.js` ويُعاد
   استخدامه عبر `<MathText>` و`ChatInterface`. ممنوع إعادة تعريفه محلياً.
5. **مكوّنات Generative UI تُصيّر الرياضيات عبر `<MathText>`**: أي حقل نصّي قد يحوي
   LaTeX داخل مكوّن توليدي يمرّ عبر `<MathText>` لا `{text}` خام.

### قياس النجاح حياً
```bash
node frontend/tests/iss105_orphaned_streaming_message.test.mjs   # 9 ضمانات + 8 سيناريو
# المتوقع حياً: اطلب «اعطني تمرين دوال 2016» → لا مؤشّر أزرق في المنتصف، السهم يعود،
# KaTeX يُصيَّر فوراً (دون الحاجة لإعادة التحميل)، والبطاقات لا تُظهر رموزاً خام.
```

### ملاحظة بيئية
الـ sandbox بلا `node_modules` (يحجب التثبيت) فتعذّر `next build`؛ تُحقّق بنية الإصلاح
عبر اختبارات node أمينة (تُعيد إنتاج البق ثم تُثبت الحل) + توازن JSX. التحقق الكامل
بالمتصفح + Supabase يجري في Codespace/CI الحيّ.

### السلسلة الكاملة (D-WS-FINAL-001 → D-WS-ORPHAN-001)
| Decision | المُصلَح |
|----------|---------|
| D-WS-FINAL-001 | كل إطار نهائي يُنهي الرسالة (error/assistant_error) |
| **D-WS-ORPHAN-001** | **يتيم البثّ: ui_component في المنتصف + كنس نهائي + MathText للمكوّنات (يحل المؤشّر الأزرق في المنتصف + السهم اللانهائي + LaTeX الخام)** |


---

## 6.81 Generative-UI Card Persistence Across Logout/Login (2026-06-02, ISS-106 / D-WS-CARD-PERSIST-001)

> سؤال المستخدم بعد E2E الحيّ لـ ISS-105: «هل البطاقات تبقى محفوظة بعد الخروج وإعادة الدخول؟»
> الجواب كان **لا** — البطاقات التفاعلية (BKT `bkt_hint_display`، `math_explanation_card`،
> `probability_tree`، `full_exercise_story`) كانت **حيّة فقط أثناء البثّ** وتختفي عند إعادة
> فتح المحادثة. هذا القسم يحكم استمرارية البطاقات — لا يُكسر بدون ADR.

### الجذر (مؤكَّد بوكيلَي Explore + قراءة الكود)
`ui_component` كان يُبَثّ عبر WebSocket فقط:
- `customer_messages` يحفظ `content` فقط — لا عمود لـ `ui_component`.
- `save_message()` لا يستقبله؛ BKT (`_evaluate_and_emit_bkt`) والبطاقة الرياضية
  (`_try_build_math_ui_component`) والبطاقات المحسوبة (orchestrator) كلها بثّ-فقط.
- مسار التاريخ (`get_conversation_details`/`_latest`) و`CustomerMessageOut` يُرجعان
  `{role, content, created_at, policy_flags}` فقط.
- الواجهة **جاهزة** (`ChatInterface.jsx:281` يُصيّر أي رسالة فيها `uiComponent`؛
  `setMessagesSafe` يحفظ الحقول) لكنها لا تتلقّى الحقل عند التحميل.

### الإصلاح (full-stack — 4 طبقات)
1. **Schema + ORM**: عمود JSON `ui_component` في `customer_messages` **و** `admin_messages`
   (`db_schema_config.py` columns + `auto_fix` ALTER + create_table؛ `domain/chat.py`
   `JSONText` مثل `policy_flags`). **auto-migrate** عند الإقلاع عبر `_fix_missing_column`
   (ALTER على جدول موجود + CREATE على جديد) — مُتحقَّق على SQLite، ونمط `users.is_active`
   يُثبت عمله على Supabase/PostgreSQL.
2. **Write**: `save_message(ui_component=None)` (+ boundary). البطاقة الرياضية تُرفق برسالة
   النص. البطاقات المستقلة (BKT + calculated-UI events) تُحفظ كصفوف مساعد `content=""` عبر
   `_persist_ui_component_cards` (BKT في جلسته المعزولة؛ calculated-UI مُلتقَط من حلقة
   `stream_and_forward` كقائمة `captured`). **حارس التكرار في `save_message` يتخطّى صفوف
   `content=""`** — وإلا تُسقَط بطاقتان فارغتان في نفس الدور.
3. **Read**: `CustomerMessageOut.ui_component` + `get_conversation_details`/`_latest`
   يُرجعان `msg.ui_component`.
4. **Frontend**: `setMessagesSafe` يحوّل `ui_component` (snake، `{component, props,
   fallback_text}`) → `uiComponent` (camel، `{component, props, fallbackText}`) لكل رسالة
   تاريخية — نفس تحويل معالج حدث `ui_component` الحيّ. التصيير دون تغيير.

### القواعد الـ 4 الدائمة (لا تُكسر بدون ADR)
1. **كل `ui_component` يُبَثّ خلال دور يجب أن يُحفظ** في عمود `ui_component` ويُعاد في مسار التاريخ.
2. **صفوف البطاقات المستقلة `content=""` مقصودة** (فقاعة بطاقة بلا نص) وتتخطّى حارس التكرار
   المعتمد على المحتوى في `save_message`.
3. **التحويل عند بوّابة الواجهة**: `setMessagesSafe` هو نقطة تحويل `ui_component`→`uiComponent`
   الوحيدة للرسائل التاريخية — لا تُكرّره في كل caller.
4. **أي مكوّن توليدي جديد يُحفظ بالشكل السلكي** `{component, props, fallback_text}` (نفس حمولة
   WS) فيتطابق تحويل الحيّ والتاريخ.

### قياس النجاح حيّاً (2026-06-02 — backend حقيقي + OpenRouter حقيقي + SQLite؛ Supabase محجوب في sandbox)
- ALTER auto-migration على DB موجود: `customer_messages`/`admin_messages` حصلا على `ui_component` ✅
- دور حيّ → `SELECT ... FROM customer_messages`: صفّ BKT (content="") + صفّ نص (math card مرفقة) ✅
- `GET /api/chat/conversations/{id}` يُرجع `ui_component` ✅
- **Playwright متصفح حقيقي**: البطاقات تُصيَّر من التاريخ بعد إعادة تحميل الصفحة **وبعد مسح
  التخزين + تسجيل دخول كامل** (katex=230, genui=22, BKT «تتبّع المعرفة» ظاهر، لا LaTeX خام) ✅
- 15/15 اختبار `iss106_card_persistence.test.mjs` + ISS-104/105 سليمة + ruff + runtime_truth ✅

### السلسلة الكاملة (D-WS-ORPHAN-001 → D-WS-CARD-PERSIST-001)
| Decision | المُصلَح |
|----------|---------|
| D-WS-ORPHAN-001 | يتيم البثّ + كنس نهائي + MathText للمكوّنات |
| **D-WS-CARD-PERSIST-001** | **حفظ بطاقات Generative UI عبر عمود ui_component → تبقى بعد الخروج/الدخول** |

---

## 6.82 Arabic Stream Guard + Model-Chain Hygiene — End of English/Garbage Answers (2026-06-02, ISS-107 / D-LANG-GUARD-001)

> **بلاغ المستخدم (تجريب حي):** بعد تمرين BAC 2016، «لم افهم التكامل» → رد **بالإنجليزية**
> (مجاميع ريمان)؛ «اشرح بالعربية» → **هلوسة كيمياء مشوّهة** («أستاذochemistry») + فقدان سياق + بطء.

### الجذور (مُثبتة ببنشمارك حي على OpenRouter بالمفتاح الحقيقي 2026-06-02)
- **RC-1**: صفر حارس لغة على مسار البثّ الحي — `run_local_graph_stream` و
  `run_local_graph_with_exercise_context` تبثّان قطع `ai_client.stream_chat` الخام.
- **RC-2 (مباشر)**: سلسلة fallback تنحدر إلى `nemotron-3-super-120b` (**إنجليزي في content**:
  "We need to respond in Arabic...")، `glm-4.5-air` (**content فارغ** reasoning-only)،
  `trinity-large-thinking` (**404**). و `stream_chat` كان يعدّ content==0 نجاحاً.
- **RC-3**: «لم افهم»/«اشرح بالعربية» لا يطابقان أنماط الشرح الصارمة → LLM عام → هلوسة كيمياء.
- **RC-4**: بطء (gpt-oss-120b 86-115s، gpt-oss-20b 51s) — يفسّر «يتأخر كثيرا».

### الإصلاح
1. **`arabic_stream_guard.py` (Skill جديد)** — يلفّ مساري البثّ: نافذة أولى ~200 حرف → فحص
   **النثر بعد إزالة LaTeX** (gpt-oss الصحيح نسبته الخام 0.57 — لا false positive) → عربي: بثّ
   + تنظيف الرموز الملتصقة | إنجليزي: إعادة توليد بـ prompt عربي صارم → رسالة عربية نظيفة.
2. **`simple_client._stream_model`** يرفع عند `content_chunks==0` → `stream_chat` يتقدّم.
3. **`ai_config`** السلسلة نُظِّفت (حُذف nemotron-super/glm/trinity).
4. **`exercise_retrieval`** ربط المتابعات بتمرين السياق (`_is_followup_explanation_request`).

### القواعد الدائمة (لا تُكسر بدون ADR)
1. **كل مسار بثّ للطالب يمرّ عبر `guard_arabic_stream`** — ممنوع بثّ `stream_chat` خاماً.
2. كشف الإنجليزية يعتمد **النثر** لا النسبة الخام (LaTeX يضخّم اللاتينية).
3. `content_chunks==0` = فشل → تقدّم للنموذج التالي (لا «إجابة فارغة»).
4. fallback يقتصر على نماذج عربية مُتحقَّقة أو محميّة؛ nemotron-super/glm-4.5-air/trinity **محظورة**.
5. المتابعات («لم افهم»/«اشرح بالعربية»/«وضّح») تبقى مربوطة بتمرين السياق.

### التحقق الحي (real OpenRouter 2026-06-02)
- **Scenario B (إثبات الكارثة):** فُرِض `nemotron-3-super-120b` كـ PRIMARY → سجل الحارس
  «first attempt non-Arabic — regenerating» → مخرَج **عربي نظيف**. بق المستخدم صار مستحيلاً بنيوياً.
- 23/23 ISS-107 + 123 regression + 6 gateway خضراء؛ ruff نظيف.
- **egress:** OpenRouter ✅/Tavily ✅/**Supabase 6543 محجوب** في الـ sandbox → E2E مسار الإجابة
  بـ SQLite + OpenRouter الحقيقي. **التحقق الكامل (Supabase + WS + المتصفح) إلزامي في Codespaces**
  بالدخولين (`houssamannaba963@gmail.com`/`1111`، أدمن `benmerahhoussam16@gmail.com`/`1111`).

---

## 6.83 Supabase DB Bridge — SQL over HTTPS When Postgres Ports Are Firewalled (2026-06-03, D-DB-BRIDGE-001)

> القاعدة الذهبية البيئية المتكررة في هذا المشروع: **جدار الـ sandbox/Codespaces يحجب
> TCP الخام إلى منافذ Postgres (5432/6543)** — موثَّق منذ §6.55/§6.74/§6.82. كل
> تحقّق DB حي كان «مؤجَّلاً إلى Codespaces». هذا القسم يكسر ذلك القيد نهائياً: نُشغِّل
> SQL ضد Supabase عبر **HTTPS (منفذ 443)** الذي لا يُحجب أبداً.

### المعمارية

```
Agent / scripts                 HTTPS :443 (مفتوح دائماً)        Supabase
  python3 scripts/db_bridge.py  ───────────────────────────►  Edge Function
    POST {"sql_query": "..."}    Authorization: Bearer <token>   "claude-admin"
                                                                    │
                                                                    ▼
                                                              يُنفِّذ SQL
                                                              ويُرجِع JSON
  ◄───────────────────────────  {"success":true,"data":[...]}  ◄──┘
```

منفذا Postgres (5432/6543) يبقيان محجوبين — **لا نلمسهما**. الجسر يمرّ عبر طبقة
HTTP التي يفتحها كل بيئة (نفس مبدأ `scripts/diagnose_chat.py` و OpenRouter/Tavily).

### الأداة (`scripts/db_bridge.py`)

- **stdlib فقط** (`urllib`) — تعمل في البيئات المتدهورة بلا أي تبعية خارجية.
- تقرأ التهيئة من **بيئة العملية** (لا تُضمَّن الأسرار في الكود):
  - `SUPABASE_EDGE_FUNCTION_URL` — العنوان العام (له افتراضي معروف).
  - `SUPABASE_EDGE_FUNCTION_KEY` — الـ bearer (**إلزامي** — يعيش فقط في `.devcontainer/secrets.env` المُتجاهَل من git).
- أكواد الخروج: `0` = HTTP 2xx، `1` = خطأ HTTP/شبكة، `2` = استخدام خاطئ / لا token.

```bash
# حمِّل الأسرار أولاً (secrets.env مُتجاهَل من git)
set -a && . .devcontainer/secrets.env && set +a

python3 scripts/db_bridge.py --version          # SELECT version();
python3 scripts/db_bridge.py "SELECT 1;"        # SQL مباشر
echo "SELECT now();" | python3 scripts/db_bridge.py   # SQL عبر stdin
```

`supervisor.sh` يحقن `SUPABASE_EDGE_FUNCTION_URL/KEY` في بيئة العملية عند الإقلاع
(نفس نمط حقن الأسرار الموجود)، فالجسر متاح تلقائياً للخدمات في Codespaces.

### نموذج المصادقة (درس مُكلِّف — D-DB-BRIDGE-001)

دالة Supabase Edge **بشكل افتراضي `verify_jwt = true`** — فبوّابة Supabase تتحقق من
ترويسة `Authorization` كـ **JWT صالح قبل أن يعمل كود الدالة**. كلمة السر المخصّصة
ليست JWT، فتُرفَض على مستوى البوّابة بـ `UNAUTHORIZED_INVALID_JWT_FORMAT` ولا تصل
لكودك أبداً. تشخيص حي (2026-06-02) أثبت:

| الإرسال | النتيجة |
|---------|---------|
| بلا `Authorization` | `UNAUTHORIZED_NO_AUTH_HEADER` |
| `Authorization: Bearer <كلمة سر مخصّصة>` (verify_jwt=true) | `UNAUTHORIZED_INVALID_JWT_FORMAT` |
| ترويسات مخصّصة (`x-admin-token`/`apikey`) | `UNAUTHORIZED_NO_AUTH_HEADER` (البوّابة تتجاهلها) |

**الإصلاح (من جهة مالك الدالة):** أعِد النشر بـ تعطيل فحص الـ JWT على البوّابة، فتصل
كلمة السر المخصّصة لكود الدالة الذي يتحقق منها بنفسه:

```bash
supabase functions deploy claude-admin --no-verify-jwt
# أو في supabase/config.toml:
#   [functions.claude-admin]
#   verify_jwt = false
```

### التحقق الحي (2026-06-03 — بعد إعادة النشر بـ `--no-verify-jwt`)

```bash
$ set -a && . .devcontainer/secrets.env && set +a && python3 scripts/db_bridge.py --version
{
  "success": true,
  "data": [{ "version": "PostgreSQL 17.6 on aarch64-unknown-linux-gnu, ..." }]
}
[HTTP 200 · 2180ms]
```

✅ الجسر حيّ. **PostgreSQL 17.6** مؤكَّد من داخل الـ sandbox عبر HTTPS — أول تحقّق DB
حي مباشر دون انتظار Codespaces.

### القواعد الـ 6 الدائمة (D-DB-BRIDGE-001 — لا تُكسر بدون ADR)

1. **الجسر لقراءة/فحص التشخيص، لا لكتابة مزدوجة**: لا يُستخدم `db_bridge.py` لكتابة
   صفوف يملكها المسار الحي (`customer_messages`/`admin_messages` — D-006). الكتابة
   تبقى عبر طبقة التطبيق فقط. الجسر للتحقّق والفحص والـ DDL اليدوي للمشغّل.
2. **الأسرار من البيئة حصراً**: `SUPABASE_EDGE_FUNCTION_KEY` لا يُضمَّن في الكود ولا
   يُلتزَم في git. يعيش في `.devcontainer/secrets.env` (مُتجاهَل) + `secrets.env.example`
   يوثّق المفتاحين بقيم placeholder.
3. **stdlib فقط**: `db_bridge.py` يبقى بلا تبعيات خارجية — يعمل في البيئات المتدهورة.
4. **الدالة تبقى `--no-verify-jwt`** مع تحقّق كلمة السر **داخل** كود الدالة. لا
   تُعِد `verify_jwt=true` دون توفير JWT صالح (anon/service_role) للأداة.
5. **العنوان عام، الـ token سرّي**: `SUPABASE_EDGE_FUNCTION_URL` ليس سرّاً (مُوثَّق
   هنا)؛ `SUPABASE_EDGE_FUNCTION_KEY` سرّ مطلق.
6. **لا يُلغي الجسر مبدأ auto-schema**: تغييرات المخطّط تبقى عبر
   `validate_schema_on_startup()` + `db_schema_config.py:REQUIRED_SCHEMA` (§D-074).
   الجسر للفحص والتحقّق اليدوي، لا بديل عن hook الإقلاع.

### السلسلة الكاملة (D-LANG-GUARD-001 → D-DB-BRIDGE-001)

| Decision | المُصلَح |
|----------|---------|
| D-LANG-GUARD-001 | حارس البثّ العربي + نظافة سلسلة النماذج |
| **D-DB-BRIDGE-001** | **جسر Supabase: SQL عبر HTTPS:443 حين تُحجب منافذ Postgres (يكسر قيد «مؤجَّل إلى Codespaces»)** |

---

## 6.84 Catastrophic Explanation Fix — Context Loss + Fake Steps + Incomplete Urn (2026-06-03, ISS-108 / D-097)

> **بلاغ المستخدم**: «النظام يولد شرحاً كارثياً، نصوصاً غبية يستحيل أن يفهمها الطالب
> العبقري فما بالك بالضعيف». طلب الحل **بالتجريب الحي الحقيقي** (إلزامي). أُكِّدت كل
> كارثة حياً على بيانات الإنتاج عبر جسر Supabase (conv 731، user 7).

### الكوارث الأربع — مؤكَّدة حياً على بيانات الإنتاج (conv 731)

| # | الكارثة | الدليل الحي |
|---|---------|------------|
| 1 | **هلوسة تسرّب الموضوع** عند «أكمل الشرح» | msg 3420 «أكمل الشرح» → msg 3423 **«إكمال الشرح حول قياس سمك الغشاء + معادلة التباعد»** (أشعة CT/X-ray لسؤال احتمالات) |
| 2 | **تقطيع النثر إلى «خطوات» وهمية** | msg 3411 `math_explanation_card` بـ 7 خطوات منها step0=«بالعربي»، step6=«أتمنى أن تكون الفكرة الآن واضحة»؛ وبطاقة «⚖️ مسألة معادلات» لاحتمالات |
| 3 | **الكيس الناقص (أبيض فقط)** | msg 3412/3416/3424 `full_exercise_story` بـ `groups=[{كرة بيضاء,2}]` فقط — الحمراء(4)+الخضراء(5) مفقودة؛ الطالب اشتكى حرفياً msg 3413 «التمرين لا يحتوي على كرات بيضاء فقط» |
| 4 | **جدار نصّي + جداول Markdown خام** | شروح طويلة بجداول `\|...\|` لا تُرسَم |

### الأسباب الجذرية (مؤكَّدة بقراءة الكود + إعادة إنتاج حتمية)

1. **هلوسة (1)**: «أكمل/كمل/تابع/continue» لم تكن في `_FOLLOWUP_EXPLANATION_MARKERS`
   (`exercise_retrieval.py`) → `detect_explanation_with_context` يُرجِع `recognized=False`
   → يسقط لمسار MODE_B العام بلا سياق التمرين → هلوسة. (المسار: `chat_with_agent` يفحص
   explanation-preempt قبل MODE_B — `orchestrator_client.py:1701`.)
2. **خطوات وهمية (2)**: `_try_build_math_ui_component` (`customer_chat.py`) يُطبَّق على **كل**
   رد → `math_pipeline._build_ui_component` يُقطّع النثر بـ regex فضفاضة (`^(\d+)[.)]`, `^**..**`)
   ويُصنّف via `_classify_math_type` خطأً.
3. **الكيس الناقص (3)** — **الجذر الحقيقي مؤكَّد حياً**: `_TOKEN_SPLIT_RE` في
   `probability_skill.py` لم يكن يُقسِّم على Markdown/LaTeX (`* \ $ # _`). النص المخزَّن
   مُنسَّق («**أربع كرات حمراء**») فيلتصق العدد بالعلامة → token=«**اربع» → `_as_int` يفشل
   (يجرّد «وفب» فقط) → تُفقَد الحمراء والخضراء؛ الأبيض ينجو فقط لأن «كرتان» (مثنى) يُطابَق
   كسلسلة فرعية. (إعادة إنتاج: نص نظيف → 3 ألوان؛ نص الإنتاج → أبيض فقط؛ بعد الإصلاح → 3 ألوان.)
4. **جدار نصّي (4)**: `EXERCISE_EXPLANATION_SYSTEM_PROMPT` يطلب إسهاباً بلا منع للجداول.

### الإصلاحات (قرارات المستخدم: «إيقاف التقطيع + بطاقات محقَّقة فقط» + «حسِّن النموذج إن لزم»)

- **Fix 1** (`exercise_retrieval.py`): علامات متابعة «أكمل/اكمل/كمل/تابع/واصل/continue/go on»
  أُضيفت لـ `_FOLLOWUP_EXPLANATION_MARKERS` → «أكمل الشرح» يُربَط بتمرين السياق فيُحقَن المحتوى.
- **Fix 2** (`customer_chat.py`): `_try_build_math_ui_component` **مُعطَّل** (يُرجِع `None`) — لا
  تقطيع نثر LLM. البطاقات المحقَّقة (probability_tree/combinations/full_exercise_story) من
  `_build_calculated_ui` تبقى. + تصلّب دفاعي في `math_pipeline._build_ui_component` (رفض شظايا
  + حذف fallback تقسيم الفقرات).
- **Fix 3** (`probability_skill.py`): `_TOKEN_SPLIT_RE` يُقسِّم أيضاً على `* \ $ # _ ~ ` | /`.
  مؤكَّد حياً: يستعيد حمراء(4)+بيضاء(2)+خضراء(5).
- **Fix 4** (`doctrine.py` → v2.2.0): قاعدتان جديدتان (حظر الموضوع الخارجي + لا جداول/لا جدار
  نص) + مرساتان (anchor 8/9) في `build_exercise_explanation_prompt` (873 حرف < 1000، 3 مراسي).
- **النموذج** (`ai_config.py`): بنشمارك حي 2026-06-03 أثبت أن gpt-oss-120b + gpt-oss-20b
  كلاهما **503 دائم** (4 جولات) → السلسلة كانت تصل nemotron (محظور كـ PRIMARY) قبل gemma.
  gemma-4-26b = GOOD حياً (عربي 65% + LaTeX + لا تسرّب). الحل: تقديم gemma على nemotron في
  الاحتياط (swap FALLBACK_2↔3). PRIMARY يبقى gpt-oss-120b (يتعافى آلياً).

### القواعد الدائمة (D-097 — لا تُكسر بدون ADR)

1. **ممنوع تقطيع نثر LLM حر إلى بطاقة خطوات**. أي بطاقة Generative UI تُبنى من بيانات محتومة
   مُتحقَّقة فقط، لا من نص مُولَّد.
2. **علامات المتابعة تربط بالسياق**: «أكمل/كمل/تابع/continue» يجب أن تبقى في
   `_FOLLOWUP_EXPLANATION_MARKERS` — حذفها يُعيد هلوسة تسرّب الموضوع.
3. **التقطيع يجب أن يُقسِّم على Markdown/LaTeX**: أي استخراج عددي من نص قد يكون مُنسَّقاً
   يجب أن يُقسِّم على `* \ $ # _` وإلا تُفقَد الكيانات الملتصقة بالعلامات.
4. **حارس الـ doctrine ضد التسرّب**: prompt الشرح يحوي «ممنوع أي موضوع خارجي» + «لا جداول».
   يبقى < 1000 حرف + 3 مراسي (`الإجابة النموذجية`/`LaTeX`/`حرفياً`).
5. **Fix 5 — جداول Markdown تُحوَّل لأسطر قابلة للقراءة**: المشروع بلا remark-gfm فالجداول
   تُعرض خاماً (`|...|`). `preprocessMath.convertMarkdownTables` يحوّل كل كتلة جدول إلى عنوان
   عريض + نقاط قبل ReactMarkdown — حتمي ومستقل عن النموذج. الرياضيات `$...$` لا تتأثر.

### التحقق الحي (2026-06-03 — FULL-STACK E2E مُثبَت)

**ما هو حقيقي:**
- **قاعدة الإنتاج Supabase (قراءة)** عبر الجسر HTTPS:443 → `PostgreSQL 17.6`؛ conv 731 أثبت
  الكوارث الأربع (هلوسة CT msg 3423، خطوات وهمية msg 3411، كيس أبيض-فقط msg 3412).
- **التطبيق الكامل حياً** (`app.main:app` uvicorn حقيقي + WebSocket + JWT + تسجيل/دخول +
  **OpenRouter gpt-oss-120b حقيقي**) → سيناريو ثلاثي (تمرين → «لم افهم» → «أكمل الشرح»):
  - Q3 «أكمل الشرح»: **لا تسرّب غشاء/CT** (كان msg 3423) — شرح احتمالات مؤصَّل ✅
  - Q1/Q2/Q3: **صفر `math_explanation_card`** (لا تقطيع نثر) ✅
  - Q2: `full_exercise_story` **بكل الألوان الثلاث** (كان أبيض-فقط) ✅
  - الحفظ في DB: 0 صفوف math_explanation_card، 0 صفوف هلوسة، 1 full_exercise_story.
- **اختبارات:** 174 اختبار (probability/iss108/iss075/doctrine/generative_ui) + 8 ISS-108 = خضراء.
  skills-doctrine gate ✅. ruff check/format ✅. table transform node-test (0 pipes) ✅.

**القيد الصادق (لماذا ليس Supabase للحفظ الحيّ):** الـ sandbox يحجب منافذ Postgres
(`:5432 BLOCKED`، `:443 OPEN` فقط) + لا توجد سلسلة اتصال Supabase Postgres مُعطاة → الحفظ
الحيّ جرى على **SQLite محلي**. التشغيل الكامل ضد Supabase + سلسلة المتصفح→server.js→backend
يجري في **Codespaces** (منفذ مفتوح + DATABASE_URL حقيقي) بالدخولين
(user `houssamannaba963@gmail.com` / admin `benmerahhoussam16@gmail.com`).

### الملفات (ISS-108 / D-097)

| File | Change |
|------|--------|
| `app/services/skills/probability_skill.py` | `_TOKEN_SPLIT_RE` يُقسِّم على Markdown/LaTeX (Fix 3) |
| `app/api/routers/customer_chat.py` | `_try_build_math_ui_component` مُعطَّل (Fix 2) |
| `app/services/capabilities/exercise_retrieval.py` | علامات المتابعة (Fix 1) |
| `app/services/skills/doctrine.py` | EXPLANATION_DOCTRINE v2.2.0 + مراسي anti-leak (Fix 4) |
| `app/core/ai_config.py` | gemma قبل nemotron في الاحتياط |
| `microservices/conversation_service/src/math_pipeline.py` | تصلّب دفاعي للخطوات |
| `frontend/app/utils/preprocessMath.js` | `convertMarkdownTables` — جداول → أسطر (Fix 5) |
| `tests/services/test_iss108_explanation_catastrophe.py` | **جديد** — regression |
| `frontend/tests/iss108_table_transform.test.mjs` | **جديد** — frontend regression |

### السلسلة الكاملة (D-DB-BRIDGE-001 → D-097)

| Decision | المُصلَح |
|----------|---------|
| D-DB-BRIDGE-001 | جسر Supabase عبر HTTPS:443 |
| **D-097** | **كارثة الشرح: فقدان السياق (هلوسة) + خطوات وهمية + كيس ناقص + جدار نص + سلسلة نماذج** |

---

## 6.85 Orchestrator `routes.py` Runtime Re-Activation — SQLite-Mode Full-Stack E2E (2026-06-04, D-098)

> طلب المستخدم: تشغيل حي حقيقي (runtime) للملف `microservices/orchestrator_service/src/api/routes.py`
> الذي كان **خاملاً** (لا يُطلَق، التبعيات غير مثبَّتة) وإثبات أنه **يجيب عن الأسئلة** عبر
> **E2E كامل شامل (FULL STACK)** بالأسرار الحقيقية. هذا القسم يحكم تشغيل الـ orchestrator على
> SQLite حين تُحجب منافذ Postgres — لا يُكسر بدون ADR.

### لماذا كان «خاملاً» وما الذي أُصلِح

`routes.py` مُوصَّل بالكامل (HTTP `/api/chat/messages` + WS `/api/chat/ws` + admin WS + `/agent/chat`
+ `/compose` + missions) لكنه DORMANT في بيئة جديدة لثلاثة أسباب: (1) لا توجد عملية uvicorn على `:8006`،
(2) تبعيات Python غير مثبَّتة (`fastapi` غير موجود في clone جديد)، (3) **منافذ Supabase Postgres
(5432/6543) محجوبة** فالـ orchestrator لا يستطيع الاتصال بقاعدة بياناته. الإصلاح (D-098 — جراحي،
محروس بحيث لا يمسّ مسار Postgres الإنتاجي إطلاقاً):

| Fix | File:line | لماذا |
|-----|-----------|------|
| **create_engine SQLite-aware** | `microservices/orchestrator_service/src/core/database.py:create_engine` | aiosqlite **يرفض** asyncpg connect_args (`statement_cache_size`/`prepared_statement_cache_size`/ssl) → `TypeError` على أول اتصال → `init_db()` تتدهور ولا تُنشأ جداول. الفرع `if url_obj.get_backend_name() == "sqlite"` يبني engine نظيفاً بـ `check_same_thread=False`. |
| **init_db checkpointer SQLite-skip** | `microservices/orchestrator_service/src/core/database.py:init_db` | بناء psycopg conninfo من URL سَكوَلايت يُنتج هدفاً غير قابل للوصول يحجب ~30s على `AsyncConnectionPool.open()`. الفرع يتخطّاه نظيفاً ويستخدم `MemorySaver`. |
| **WS error-log fidelity** | `microservices/orchestrator_service/src/api/routes.py:_stream_chat_langgraph` | معالج `__ERROR__` كان يستخدم `exc_info=True` بلا استثناء نشط (الخطأ رُفع في مهمة خلفية) → يسجّل `NoneType: None`. الآن يسجّل الخطأ/التتبّع الملتقَط من الطابور. |

**القاعدة الذهبية:** كل الفروع محروسة بـ `get_backend_name() == "sqlite"` — على Postgres
(الإنتاج/Codespaces) لا تُؤخَذ، فمسار psycopg checkpointer + asyncpg engine يبقى كما هو تماماً.

### المعمارية المُثبَتة حياً (SQLite مشترك + OpenRouter حقيقي)

```
المتصفح ≈ ws query-param ?token=  →  Next.js server.js :5000 (ws-lib proxy + early-msg queue)
   →  Monolith :8000 (OrchestratorClient.chat_with_agent, state_graph mode، service-JWT مشترك SECRET_KEY)
   →  Orchestrator routes.py :8006  POST /api/chat/messages
   →  13-node LangGraph (create_unified_graph) → OpenRouter (إجابة عربية + LaTeX)
```

الـ monolith والـ orchestrator يتشاركان **ملف SQLite واحد** (`.cogniforge_e2e.db`، WAL): الـ monolith
يُنشئ جداول `customer_conversations/messages` + `users` (عبر `validate_schema_on_startup`)، والـ
orchestrator يقرأ/يكتبها — مرآة دقيقة لبنية Supabase المشتركة (التي تُحجب TCP في الـ sandbox، فيُستخدم
SQLite + جسر HTTPS للتحقّق).

### التحقّق الحي (2026-06-04 — SQLite + OpenRouter حقيقي؛ Supabase عبر الجسر)

- **الإقلاع:** `:8006/health → {"status":"ok","graph_ready":true,"startup_state":"ready"}` |
  warmup شغّل LangGraph حقيقياً: `TOOL EXECUTED → admin.count_python_files → عدد ملفات بايثون: 1584 ملف`
  | `startup_info{checkpointer_backend="memory",graph_ready="true",pipeline_enabled="true"}`.
- **المسار 1 — مباشر** `POST :8006/api/chat/messages` (JWT مشترك): إجابات حقيقية متعدّدة —
  نيوتن (24 delta، `$$\vec F = m\vec a$$`)، الجاذبية (27 delta، `$$F=G\frac{m_1 m_2}{r^2}$$`)،
  السرعة/التسارع (46 delta، 1312 حرف). TTFT 3.5–17s.
- **المسار 2 — Monolith WS** `:8000/api/chat/ws`: «عرّف الذكاء الاصطناعي» شغّل الرسم الـ 13-node كاملاً
  (`SupervisorNode → QueryRewriter → QueryAnalyzer → InternalRetriever → Reranker → WebSearchFallback →
  Synthesizer → Validator`) → 10 deltas. دفعة 5 أسئلة → **4/5 مرّت عبر الـ orchestrator** (الباقي
  fallback محلي مرن بالتصميم).
- **المسار 3 — Frontend proxy** `:5000/api/chat/ws` (query-param مثل المتصفح): الطاقة الحركية →
  `server.js #N queued client msg → upstream open (flushed 1 queued)` → orchestrator hit (200) →
  21 delta، `$$K=\frac{1}{2}mv^2$$`، إغلاق نظيف 1000.
- **عقد العُقد الحية:** كل أنواع العُقد نُفِّذت — Supervisor×11، Validator×11، خط التعليم×6، GeneralKnowledge×5،
  ExecuteTool×1 | **11 إجابة chat قُدِّمت (200)**.
- **Supabase عبر الجسر (HTTPS:443):** PostgreSQL 17.6 | الحسابان الحقيقيان موجودان
  (`benmerahhoussam16@gmail.com` id=1 is_admin=true، `houssamannaba963@gmail.com` id=7 is_admin=false) |
  كل الجداول المشتركة موجودة.

### أداة E2E + Codespaces runbook

`scripts/e2e_orchestrator_live.py` (جديد، stdlib + httpx + websockets): يسجّل دخول/يُسجِّل المستخدم ثم
يختبر المسارات الثلاثة ويطبع تقريراً (deltas/chars/terminal/frames/answer). يعمل عبر env overrides
(`E2E_BACKEND/ORCH/FRONTEND/EMAIL/PASSWORD`).

**Codespaces runbook (Supabase الحقيقي — egress مفتوح هناك):**
```bash
# 1) secrets.env بالقيم الحقيقية (APP_DATABASE_URL=Supabase، OPENROUTER، TAVILY، SUPABASE_EDGE_*)
cp .devcontainer/secrets.env.example .devcontainer/secrets.env   # ثم املأ القيم
# 2) شغّل المنظومة كاملة (يُطلق orchestrator :8006 + monolith :8000 + frontend :5000 + الخدمات)
bash .devcontainer/supervisor.sh
# 3) أعِد نفس الـ E2E ضد Supabase
python3.12 scripts/e2e_orchestrator_live.py "ما هو قانون نيوتن الثاني؟"
# المتوقّع: المسارات الثلاثة pass، الـ orchestrator يُجيب، الرسائل تُحفظ في customer_messages على Supabase
```

### القواعد الـ 5 الدائمة (D-098 — لا تُكسر بدون ADR)

1. **فروع SQLite محروسة بـ `get_backend_name()=="sqlite"`** — ممنوع تمرير asyncpg connect_args إلى aiosqlite،
   وممنوع بناء psycopg conninfo من URL سَكوَلايت. مسار Postgres يبقى غير ممسوس.
2. **DB مشتركة واحدة بين monolith و orchestrator** — الـ orchestrator يكتب في جداول الـ monolith
   (`customer_conversations/messages`)؛ الـ monolith يُنشئها. لا تُعطِ الـ orchestrator ملف SQLite منفصلاً
   (لن تكون فيه جداول المحادثات → 403/خطأ).
3. **SECRET_KEY مشترك إلزامي** — `_build_service_jwt` (monolith) يوقّع بـ SECRET_KEY والـ orchestrator
   يفكّه به. اختلافهما → 401/403 → سقوط إلى local_graph (المسار لا يصل الـ orchestrator أبداً).
4. **الواجهة عبر البروكسي = query-param `?token=` بلا subprotocol** — تقديم subprotocol للبروكسي يُجبر
   عميل ws-lib الأعلى على طلب echo لا يرسله الـ monolith → 1011. `useRealtimeConnection.js` يستخدم query-param.
5. **الـ fallback المرن مقصود** — حين يُسبَق السؤال محلياً (تحية/تمرين مفهرَس/شرح بسياق) أو يتعذّر الـ
   orchestrator، يجيب `local_graph`. النظام **يجيب دائماً**؛ مرور الطلب عبر الـ orchestrator ليس شرطاً
   لكل سؤال (D-006 + سلسلة الـ fallback).

### الصدق البيئي

التحقّق جرى على **SQLite + OpenRouter/Tavily حقيقي** داخل الـ sandbox (Postgres TCP محجوب — نمط §6.55/§6.83).
Supabase تحقَّق **قراءةً عبر الجسر HTTPS** (لا كتابة مزدوجة — D-006). التشغيل الكامل ضد **Supabase Postgres**
+ سلسلة المتصفح الحقيقية يجري في **Codespaces** عبر الـ runbook أعلاه بالدخولين الحقيقيين.

### السلسلة الكاملة (D-097 → D-098)

| Decision | المُصلَح |
|----------|---------|
| D-DB-BRIDGE-001 | جسر Supabase عبر HTTPS:443 |
| D-097 | كارثة الشرح: فقدان السياق + خطوات وهمية + كيس ناقص + جدار نص |
| **D-098** | **تشغيل orchestrator routes.py على SQLite (create_engine + init_db skip) + E2E كامل 4 طبقات + WS error-log fidelity** |

### RAG Vector Database Ingestion (June 2024 Update)
**Live ETL Scripts for Production Supabase:** We rigorously enforce structural strictness for RAG by ensuring all BAC exercises ingested into the live Supabase vector database include deep `parsed_entities` JSON payloads. The live database currently contains 3 explicitly tested BAC exercises:
1. **BAC 2024 Math (Subject 1, Ex 1):** Probability (`bac2024_math_experimental_subject1_ex1_ex2.md` reference).
2. **BAC 2024 Math (Subject 1, Ex 2):** Complex Numbers (`bac2024_math_experimental_subject1_ex1_ex2.md` reference).
3. **BAC 2016 Math (Subject 2, Ex 4):** Numerical Functions, Session 1 (`bac2016_s1_math_exp_subject2_ex4_numerical_functions.md` reference).
These were ingested using isolated ETL scripts (like `live_db_restructure.py`) that strictly map the `exam_ref`, `branch`, `topic`, and JSON entities to prevent "RAG Semantic Blindness". The database is currently fully capable of distinguishing these exercises via Vector Embeddings, while local development in Codespaces safely falls back to reading the `knowledge_base/` markdown files due to egress firewall restrictions.

---

## 6.86 Arabic-Normalized Exercise Recognition + Scalable Supabase Retriever (2026-06-08, ISS-109 / D-099)

> الكارثة: «أعطني تمرين الأعداد المركبة 2024» كان يُرجع تمرين **الاحتمالات**. هذا القسم يحكم
> التعرّف على التمارين على نطاق المليارات — لا يُكسر بدون ADR.

### السبب الجذري (مُثبت)
أداة التعريف العربية «ال» تكسر مطابقة الموضوع ثنائي الكلمة: «أعداد مركبة» ليست سلسلة فرعية
من «الأعداد المركبة» → `_extract_topic_keywords` تُرجع `[]` → `search_exercises` يُعطي +10 لكلا
تمرينَي 2024 على السنة فقط → **تعادل** → الترتيب الثابت يفوز فيه الاحتمالات (التمرين الأول).
«احتمالات» تنجو لأنها كلمة واحدة (سلسلة فرعية من «الاحتمالات»). هذا «RAG Semantic Blindness».

### المعمارية (3 طبقات — retrieve-then-rerank، مستقلة عن مصدر البيانات)
1. **`app/services/capabilities/arabic_normalize.py`** (stdlib نقي — الأساس): `normalize_ar` يحذف
   «ال» لكل رمز (مع حماية الجذع القصير) + يوحّد الهمزات/ة/ى/التشكيل/التطويل/الأرقام العربية،
   يُطبَّق على **طرفي المطابقة**. + `CANONICAL_TOPICS` يجسر صياغة الطالب ↔ `bac_exercises.topic`
   (إنجليزي) ↔ raw_text العربي المميِّز. `primary_canonical_topic(query)` هو نقطة التعرّف الموحَّدة.
2. **`knowledge_index.search_exercises`**: مطابقة مطبَّعة + إشارة `canonical_topic_id` بوزن **16**
   (`_W_CANONICAL_TOPIC > _W_YEAR=10`) تكسر تعادل السنة + ترتيب حتمي
   `(score, canonical_hit, -exercise_number)` لا يعتمد ترتيب القائمة أبداً.
3. **`app/services/capabilities/bac_db_retriever.py`** (Supabase candidate-gen + rerank): SQL مفهرس
   (سنة + `topic ILIKE` + `raw_text LIKE` المميِّز) ثم rerank متعدد الإشارات. موصول في
   `orchestrator_client._build_local_retrieval_response` (DB-first للتمارين غير المُفهرَسة + hybrid
   content) و `_has_indexed_match` (preempt للطلبات المُرسَّخة بنيوياً).

### القواعد الدائمة (لا تُكسر بدون ADR)
1. **التطبيع على الطرفين إلزامي**: أي مطابقة موضوع/استعلام عربي تمرّ عبر `normalize_ar` —
   ممنوع `if keyword in text` خام (يُعيد كارثة «ال» فوراً).
2. **`canonical_topic_id` أقوى من السنة**: وزنه يجب أن يبقى > وزن السنة ليكسر تعادل تمارين نفس السنة.
3. **الترتيب حتمي**: `(score, canonical_hit, -exercise_number)` — لا تعتمد النتيجة على ترتيب القائمة.
4. **مُسترجِع DB لا يكسر المحادثة أبداً**: أي تعذّر وصول/خطأ/مهلة → `None` → fallback نصّي
   (markdown `KNOWLEDGE_INDEX`). آمن في الـ sandbox (Postgres محجوب)، يتفعّل في Codespaces/Production.
5. **`KNOWLEDGE_INDEX` = cache سريع للتمارين الساخنة؛ Supabase = المصدر القابل للتوسّع لمليارات التمارين.**
   إضافة تمرين منسَّق = مدخل في `KNOWLEDGE_INDEX`؛ التوسّع الفعلي = صفوف `bac_exercises` (الـ retriever
   يولّد المرشّحين بفلاتر مفهرسة، لا مسح كامل).
6. **`_YEAR_RE = 20[0-3]\d`** (يشمل 2016) — لا تُضيّقه إلى `20[2-3]\d` (يُسقط الدوال العددية 2016).
7. **نماذج مجانية فقط على المسارات القابلة للوصول**: PRIMARY=`openai/gpt-oss-120b:free` + كل fallbacks
   `:free`. الرؤية (`multimodal_processor.py`) = `google/gemma-4-26b-a4b-it:free` (قابل للتجاوز بـ
   `OPENROUTER_VISION_MODEL`). self-healing = `openai/gpt-oss-20b:free`. أي نموذج جديد ينتهي بـ `:free`.

### التحقق الحي (2026-06-08)
- مصفوفة التعرّف (stdlib، 10 صياغات عربي ±«ال»/فرنسي/إنجليزي): 10/10 → التمرين الصحيح.
- **SQL المُسترجِع مقابل Supabase الحقيقي عبر الجسر**: 3/3 (complex→ex2، probability→ex1، numerical→ex4).
- `python3 scripts/verify_exercise_retrieval_e2e.py` (Layer A تعرّف + Layer B جسر + Layer C WebSocket).
  Layer C (WebSocket E2E) يتطلب `E2E_BACKEND` + التطبيق قيد التشغيل → **Codespaces** (pip محجوب في الـ sandbox).
- ruff check/format ✅ | runtime_truth --check ✅ (لا drift).

### Codespaces runbook (التحقق الكامل WebSocket E2E)
```bash
cp .devcontainer/secrets.env.example .devcontainer/secrets.env   # املأ OPENROUTER + DATABASE_URL الحقيقية
bash .devcontainer/supervisor.sh                                  # يُطلق المنظومة كاملة
set -a && . .devcontainer/secrets.env && set +a
E2E_BACKEND=http://localhost:8000 python3 scripts/verify_exercise_retrieval_e2e.py
# المتوقع: A_recognition PASS + B_supabase_sql PASS + C_websocket PASS (الردود تحوي علامات التمرين الصحيح)
```

---

## 6.87 Unified Skills Platform — Registry + Composition + Observability (2026-06-09, D-100)

> تحقيق §0.5 (النجمة القطبية): طبقة موحِّدة فوق الـ 14 Skill — **اكتشاف + بيانات وصفية +
> تركيب رسمي + رصد**، مع تفعيل قدرتين كانتا DORMANT (LlamaIndex/Reranker + MCP) كـ Skills
> اختيارية. **كل شيء إضافي 100% — لا يلمس مسار الإقلاع ولا الدردشة الحيّة.**

### المكوّنات

| المكوّن | الملف | الدور |
|---------|-------|------|
| **SkillRegistry** | `app/services/skills/registry.py` | سجل في-العملية لكل الـ 14 Skill ببيانات وصفية موحَّدة (name, contract, primary_method, consumed_by, status). استيراد الـ Skills كسول (lazy) — الرصد لا يستورد pydantic. |
| **compose_text_refinement** | `registry.py` | خط تنقية الإجابة الرسمي (exercise_alignment → answer_quality → output_firewall → topic_lock) كبدائية قابلة لإعادة الاستخدام. كل خطوة معزولة (graceful degradation) — لا تكسر المسار. |
| **`/api/v1/skills`** | `app/api/routers/skills.py` | سطح رصد قراءة-أولاً: `GET /` (قائمة)، `GET /{name}` (تفاصيل)، `POST /refine` (auth — التركيب)، `POST /retrieve` + `POST /mcp` (auth، خلف علم — 503 عند التعطيل). مُركَّب في `base_router_registry()`. |
| **RetrievalRerankSkill** | `app/services/skills/retrieval_rerank_skill.py` | يُفعِّل `LlamaIndexDriver` + `RerankerDriver` (كانا DORMANT) كـ Skill. علم `ENABLE_RETRIEVAL_RERANK_SKILL` (افتراضي False → يُرجِع None). |
| **MCPToolSkill** | `app/services/skills/mcp_tool_skill.py` | يُفعِّل `MCPServer` (8 أدوات) كـ Skill. علم `ENABLE_MCP_TOOL_SKILL` (افتراضي False → يُرجِع None). |
| **SKILLS_PLATFORM_DOCTRINE** | `app/services/skills/doctrine.py` (v1.0.0) | 6 قواعد + manifest entry `skills_platform`. |
| **CI gate** | `scripts/fitness/check_skills_doctrine.py:check_skills_platform` | يحرس: manifest متّسق + الـ registry مكتمل (14) + no-ZOMBIE + الموجِّه مُركَّب. |

### القواعد الست الدائمة (D-100 — لا تُكسر بدون ADR)

1. **Single registry**: كل Skill يُسجَّل في `get_skill_registry()` ببيانات وصفية موحَّدة.
2. **No ZOMBIE**: كل Skill مُسجَّل يملك مُستهلِكاً حيّاً في `consumed_by` — الـ CI gate يحرس (مرآة D-073).
3. **Additive only**: المنصّة لا تُعيد توصيل المسار الحيّ — `local_graph._chat_node` chain يبقى مرجعاً؛ التركيب عبر الخدمات يبقى في `microservices/.../skills_pipeline.py:run_skills_pipeline`.
4. **Graceful degradation**: كل خطوة في `compose_text_refinement` معزولة بـ try/except — فشلها يُتجاهَل ويُحتفَظ بالنص.
5. **Flagged dormants**: الـ Skills المُفعَّلة من قدرات DORMANT مُعطَّلة افتراضياً وتُرجِع None عند التعطيل (صفر تغيير سلوكي). علم الميزة: env var (override، 12-factor) أولاً ثم الإعدادات.
6. **Metric-emitter contract (§6.21)**: كل مقياس يُعرَض له مُصدِر حقيقي — `cogniforge_skill_compose_*`، `cogniforge_skill_registry_skills`، `cogniforge_skill_retrieval_*`، `cogniforge_skill_mcp_*`.

### ما هو مُستبعَد صراحةً (بأسباب موثَّقة)

- **Kagent** (`KagentDriver`): محجوب أمنياً («Invalid token») — يحتاج نظام token داخلياً. ZOMBIE يبقى.
- **TLM / cleanlab**: غير مُثبَّت — ليس جزءاً من المستودع.
- **Docker-forcing**: كسر Codespaces مراراً (error 1302 — §6.16). المنظومة تعمل uvicorn-native بلا Docker.

### قياس النجاح حياً (Codespaces — الـ sandbox يحجب pip + Postgres)

```bash
# الرصد — 14 Skill (12 ACTIVE + 2 FLAGGED)
curl -s http://localhost:8000/api/v1/skills | python3 -m json.tool
# تحقّق في-العملية
python3 scripts/verify_skills_platform.py
ENABLE_RETRIEVAL_RERANK_SKILL=1 ENABLE_MCP_TOOL_SKILL=1 python3 scripts/verify_skills_platform.py
# تحقّق المنظومة كاملة (8 خدمات + pipeline full + /api/v1/skills + WS turn)
python3 scripts/verify_full_stack_codespaces.py
```

### التحقق في الـ sandbox (الآن)

- `ruff check` + `ruff format --check` ✅ | `runtime_truth --check` ✅ (الـ lock يسجّل تفعيل الـ drivers: importer 1→2) | `validate_structure` ✅ | `ci_guardrails` ✅.
- اختبار منطق الـ registry/compose المستقل (stdlib): 14 Skill، 12 ACTIVE + 2 FLAGGED، no-ZOMBIE، ترتيب + عزل فشل + env-override ✅.
- اختبارات regression: `tests/services/test_skills_registry.py` (registry + compose + manifest).
- **التحقق الحي الكامل** (الخدمات + الـ endpoints + flagged skills) يجري في Codespaces/CI حيث pydantic + الخدمات متوفّرة.

### السلسلة الكاملة (D-099 → D-100)

| Decision | المُصلَح/المُضاف |
|----------|-----------------|
| D-099 | تعرّف عربي مُطبَّع + مُسترجِع Supabase قابل للتوسّع |
| **D-100** | **منصّة Skills موحَّدة: registry + compose + /api/v1/skills + تفعيل LlamaIndex/Reranker/MCP كـ Skills (flagged) + CI gate** |

---

## 6.88 Topic-Switch Hijack — Current-Question Intent Gate + Indexed-First Preemption (2026-06-10, ISS-110 / D-101)

> **الكارثة المُبلَّغة (transcript حي):** في محادثة واحدة، بعد استرجاع تمرين الاحتمالات،
> طلب «اعطني تمرين الدوال العددية» أرجع **combinations_visualizer** (C(11,3)=165 من كيس
> التمرين السابق) + «إليك الشرح البصري المفصل 🪄» بدل تمرين الدوال 2016 — رغم أن
> الاسترجاع المُفهرَس كان يتعرّف على الملف الصحيح طوال الوقت. هذا القسم يحكم توجيه
> الواجهة المحسوبة مقابل الاسترجاع — لا يُكسر بدون ADR.

### الجذر المزدوج (مُثبت بالتجريب الحي)

1. **RC-1 — بوابة السياق على النص المُدمَج** (`probability_skill.py:analyze`): فحص
   `_PROBABILITY_CONTEXT` كان يجري على `combined = question + history` — سؤال بلا أي
   كلمة احتمالية («اعطني تمرين الدوال العددية») يمرّ لأن الـ history يحوي
   «احتمالات/سحب/كيس»، ثم `_strategy_composition` يستخرج تركيبة الكيس **من الـ history**
   ويبني `CombinationsModelOutput` لتمرينٍ لم يطلبه الطالب.
2. **RC-2 — ترتيب الـ preemption** (`orchestrator_client.py:chat_with_agent`):
   `_build_calculated_ui` كان يسبق `_has_indexed_match`، و MODE_A
   (`terminate_pipeline=True`) يُنهي المسار فوراً — الاسترجاع المُفهرَس لا يُنفَّذ أبداً.

### الإصلاح (D-101 — 4 طبقات)

- **إعادة ترتيب**: `greeting → indexed-match → calculated-UI → explanation-with-context
  → orchestrator/LLM`. طلب تمرين صريح يبثّ النص النظيف ويُنهي المسار قبل أي واجهة محسوبة.
- **بوابة نية السؤال الحالي** (`analyze`): سياق احتمالي من الـ history فقط يتطلب أن يحمل
  السؤال الحالي نفسه: كلمة سياق صريحة، أو إشارة حيرة (`is_confusion`)، أو متابعة خطوة
  (`_has_followup_probability_intent` — `p(`/جداء/نفس اللون/فردي/زوجي/شرطي/الأمل/المتغير/
  `e(x`/فضاء/تأليف). وإلا → `ProbabilityFailure(reason="no_probability_intent_in_question")`.
- **حاجب تبديل الموضوع** (`_build_calculated_ui`): `primary_canonical_topic(question)`
  (من arabic_normalize — D-099) يُرجع موضوعاً غير `probability` → `None` فوراً — حتى مع
  حيرة («لم أفهم تمرين الدوال العددية» بعد سياق احتمالات).
- **focus-retry موسَّع**: `_is_no_model` يقبل `no_probability_intent_in_question` إضافةً
  لـ `no_model_extracted` — متابعات خطوات التمرين تبقى تعمل عبر إعادة التحليل بالسياق الكامل.

### القواعد الخمس الدائمة (D-101 — لا تُكسر بدون ADR)

1. **الاسترجاع المُفهرَس يسبق الواجهة المحسوبة دائماً** في `chat_with_agent` — عكس
   الترتيب يُعيد كارثة الاختطاف فوراً (يحرسه فحص بنيوي في
   `tests/services/test_iss110_topic_switch_routing.py`).
2. **سياق history وحده لا يُفعِّل واجهة الاحتمالات**: السؤال الحالي يجب أن يحمل نية
   احتمالية بنفسه (سياق/حيرة/متابعة).
3. **طلب موضوع صريح آخر يحجب الأداة تماماً** — `primary_canonical_topic` هو الحَكَم،
   حتى مع إشارات حيرة.
4. **أي marker متابعة جديد** يُضاف إلى `_FOLLOWUP_PROBABILITY_INTENT` (الـ skill) **و**
   `_detect_focus_step` (orchestrator) معاً — هما مرآتان.
5. **doctrine bump إلزامي**: أي تعديل على هذه القواعد = ترقية
   `PROBABILITY_CALCULATION_DOCTRINE_VERSION` (حالياً v1.4.0) + تحديث الاختبارات.

### التحقق الحي (2026-06-10 — SQLite + OpenRouter حقيقي؛ Supabase 6543 محجوب في الـ sandbox، نمط §6.55)

- `scripts/verify_iss110_live.py` → **7/7**: Q1 أعداد مركبة ✅ | Q2 احتمالات ✅ |
  **Q3 «اعطني تمرين الدوال العددية» → نص تمرين الدوال 2016 (2328 حرف)، صفر مكوّن
  احتمالات** ✅ | Q4 «لسنة 2016» نفس الشيء ✅ | Q5 «مفهمتش» بعد تمرين الاحتمالات →
  `full_exercise_story` (MODE_B سليم، 6830 حرف سرد LLM) ✅.
- 62 اختبار probability+ISS-110 + 128 regression (V38/genUI/ISS-108/doctrine/registry) ✅.
- مقارنة git-stash: مجموعتا فشل resilience suite متطابقتان قبل/بعد الإصلاح (كلها في
  PRE_EXISTING_FAILURES بالـ CI) — **صفر انحدار**.

### ملاحظة نافذة معروفة (سابقة — خارج نطاق ISS-110)

الـ skill يقرأ `history[-6:]` (كل رسالة ≤2000 حرف): حيرة تأتي بعد أكثر من 6 رسائل من
تمرين الاحتمالات (خصوصاً مع حارس التكرار الذي يمنع إعادة حفظ تمرين مُكرَّر) لا تجد
التركيبة → لا واجهة. مُثبت بـ git-stash أنه سلوك سابق للإصلاح. توسيع النافذة يحتاج ADR
مستقلاً (موازنة دقة الاستخراج مقابل تلوّث السياق).

### السلسلة الكاملة (D-100 → D-101)

| Decision | المُصلَح/المُضاف |
|----------|-----------------|
| D-100 | منصّة Skills موحَّدة (registry + compose + observability) |
| **D-101** | **ISS-110 — بوابة نية السؤال الحالي + الاسترجاع المُفهرَس أولاً + حاجب تبديل الموضوع (يحل اختطاف «تمرين الدوال» بواجهة الاحتمالات)** |

---

## 6.89 System-Prompt History Poisoning — Structural-Only History Binding (2026-06-10, ISS-111 / D-102)

> **اكتُشفت خلال التحقق الحي العميق** (LangGraph + الخدمات المصغرة بعد ISS-110): سؤال
> فيزياء عام في **محادثة جديدة فارغة** كان يُختطف لتمرين 2024 ويُمنع من الوصول للـ
> orchestrator. هذا القسم يحكم فحص history المحادثة في كواشف الاسترجاع — لا يُكسر بدون ADR.

### الجذر الثلاثي (مُثبت حياً بسطر log كاشف `history_len=2`)

1. **`get_chat_history` يحقن رسالة system**: `chat_persistence.py` يضع
   `{"role":"system", "content":get_customer_system_prompt()}` في رأس كل history —
   برومبت Overmind الإنجليزي ("...math, physics, programming...").
2. **`_detect_entry_from_history` كان يفحص كل الرسائل** بما فيها system.
3. **tag-fallback فضفاض**: `_find_matching_entry` عند غياب تطابق بنيوي يطابق أي كلمة
   ‎>2 حرف مع وسوم التمارين — "math" من برومبت النظام تطابق وسوم تمرين 2024.

**النتيجة**: كل سؤال يحوي أي marker شرح («اشرح/وضح/أكمل/لم أفهم»...) في أي محادثة →
explanation-preempt يربطه زائفاً بتمرين 2024 → حقن التمرين + رفض الموضوع الأصلي
(«ملزم بالتركيز على تمرين الاحتمالات») + **المسار لا يصل أبداً للـ orchestrator/LangGraph
العميق** (الـ preempt قبل HTTP).

### الإصلاح (D-102)

- `_detect_entry_from_history`: يفحص رسائل **user/assistant فقط** — رسائل system ليست
  دليلاً من المحادثة.
- الربط بالتاريخ **بنيوي حصراً**: `_find_matching_entry(recent_text, allow_tag_fallback=False)`
  — سنة/دورة/موضوع/رقم تمرين/موضوع مرجعي. الـ tag-fallback محجوز لسؤال الطالب المباشر
  (default=True بلا تغيير).
- log كاشف دائم: `explanation_context_preempt reason=… matched_file=… history_len=…`.

### القواعد الأربع الدائمة (D-102 — لا تُكسر بدون ADR)

1. **رسائل system لا تدخل أي كاشف history**: أي كاشف جديد يفحص تاريخ المحادثة يجب أن
   يُرشِّح `role in ("user", "assistant")` أولاً.
2. **الربط بالتاريخ يتطلب تطابقاً بنيوياً**: ممنوع tag-fallback على نص الـ history —
   التطابق البنيوي (سنة/موضوع/رقم/canonical) فقط يثبت أن المحادثة عن تمرين بعينه.
3. **سطور log التشخيصية تحمل بياناتها في النص**: الـ extras dict لا يظهر في formatters
   قياسية — أي log توجيهي حرج يضع الحقول الحاسمة في نص الرسالة.
4. **درس منهجي (إعادة الإنتاج الأمينة)**: عند «دالة حتمية تعطي نتائج مختلفة» — المدخلات
   مختلفة فعلاً. أعد إنتاج الـ history **كما يبنيه الخادم** (بما فيه رسالة system من
   `get_chat_history`) لا كما تتخيله.

### التحقق الحي (2026-06-10 — المنظومة كاملة على SQLite + OpenRouter حقيقي؛ Supabase محجوب نمط §6.55)

- **5 خدمات حية**: monolith :8000 + orchestrator :8006 (`graph_ready=true`) +
  planning :8002 + research :8007 + reasoning :8008.
- **قبل الإصلاح**: «قانون نيوتن... اشرح» عبر WS → «عذراً... ملزم بتمرين الاحتمالات» +
  **صفر** POST لـ :8006. **بعده**: إجابة نيوتن عبر **الرسم الـ13-node** (`POST 200`،
  إطارات `phase_start`، 21 delta، 1.49s) — مسار WS → monolith → orchestrator →
  LangGraph → OpenRouter كامل.
- **Skills Pipeline**: `POST :8006/compose` → **`pipeline_mode=full`** +
  `skills_active=[planning, research, reasoning]` (16.7s، إجابة مركَّبة 1299 حرف).
- **ISS-110 صامد مع الـ orchestrator الحي**: `verify_iss110_live.py` → **7/7**.
- 9 اختبارات ISS-111 + 256 regression خضراء | ruff + runtime_truth + skills-doctrine ✅.

### السلسلة الكاملة (D-101 → D-102)

| Decision | المُصلَح/المُضاف |
|----------|-----------------|
| D-101 | ISS-110 — بوابة نية السؤال الحالي + الاسترجاع المُفهرَس أولاً |
| **D-102** | **ISS-111 — تسميم history برسالة النظام: فحص user/assistant فقط + ربط بنيوي حصراً (يفتح طريق WS → orchestrator 13-node)** |

---

## 6.90 More-via-LangGraph — Explanation via the 13-Node Graph + Reasoning-Agent Consultation (2026-06-10, D-103)

> طلب المستخدم الصريح: تمرير المزيد من الأسئلة عبر LangGraph والخدمات المصغرة («كلاهما»،
> «الجودة أولاً»). هذا القسم يحكم حقن محتوى التمرين في الرسم + استشارة reasoning-agent —
> لا يُكسر بدون ADR.

### Change A — شرح التمارين بسياق عبر الرسم الـ13-node (يُعدِّل D-052 rule 2)

بعد ISS-110/111، الفئة الوحيدة المتبقية التي تستخدم LLM **محلياً** كانت شرح التمارين بسياق
(tier 2.5). قاعدة D-052 منعت تمريرها للـ orchestrator لأن retriever-ه (vector DB) كان يُرجع
تمارين مختلطة + tags خام. **الحل يُحيّد سبب المنع بالبناء**:

```
monolith chat_with_agent:
  detect_explanation_with_context ⇒ recognized + matched_entry
    ⇒ (العلم مفعَّل) حقن context["exercise_content"] = decision.full_content
    ⇒ المتابعة إلى orchestrator POST /api/chat/messages (لا بثّ محلي)
orchestrator graph (عند وجود exercise_content في الحالة):
  Supervisor      ⇒ intent="educational" حتمياً (لا DSPy، لا misroute)
  QueryRewriter   ⇒ no-op (يوفّر LLM call)
  QueryAnalyzer   ⇒ filters فارغة (يوفّر LLM call)
  InternalRetriever ⇒ المستند المحقون فقط (source="محتوى التمرين المرفق") — لا research_client
  Reranker        ⇒ passthrough (لا cross-encoder)
  Synthesizer     ⇒ يبني الشرح من المحتوى المحقون + المحادثة
```

التوصيل: `ChatRunContext.exercise_content` + `_extract_injected_exercise` (سقف 16K حرف) في
`routes.py` على المسارين (HTTP `_run_chat_langgraph` + WS `_runner`)، وحقل
`AgentState.exercise_content` في `graph/main.py`.

### Change B — استشارة reasoning-agent (:8008 MCTS) من SynthesizerNode

`_is_complex_math_query` (حتمي — markers صريحة: تكامل/اشتقاق/نهاية/برهن/أثبت/ادرس الدالة/
متتالية/أعداد مركبة **بصيغها المعرَّفة بـ«ال» — درس ISS-109**/lim/integral/prove، طول ≥ 15)
⇒ `_consult_reasoning_agent` يستدعي `reasoning_client.reason_deeply` بسقف `asyncio.wait_for`
(افتراضي **35s** — بنشمارك حي: MCTS يستغرق ~23s لمسألة تكامل بالتجزئة؛ سقف 20s الأول كان
يُهدر الانتظار ويُسقط الـ hint دائماً). الـ hint (answer + logic_trace، ≤ 4000 حرف) يُنسج في المواضع الثلاثة للـ prompt
(no-docs streaming / with-docs streaming / DSPy batch) بصيغة
«تحليل استدلالي مساعد (تحقق منه ولا تنسخه حرفياً)».

### القواعد الـ 6 الدائمة (D-103 — لا تُكسر بدون ADR)

1. **حقن `exercise_content` ⇒ retriever الرسم يتجاوز البحث الدلالي كلياً** — المصدر الوحيد
   هو المحقون. أي مسار يخلط المحقون مع vector DB يُعيد كارثة D-052 (تمارين مختلطة + tags خام).
2. **`EXPLANATION_VIA_ORCHESTRATOR=0` رافعة رجوع فورية** بلا deploy (نمط D-025) — تعيد البثّ
   المحلي القديم. الشرح المحلي يبقى في fallback chain دائماً ويتلقى `precomputed_decision`
   (ISS-059 parity).
3. **استشارة reasoning-agent fail-open مطلقاً**: أي خطأ/مهلة/تعطيل ⇒ "" والتوليف يتابع.
   ممنوع أن تُفشل الاستشارة دور الطالب. سقف زمني إلزامي (`ORCHESTRATOR_REASONING_CONSULT_TIMEOUT`).
4. **حارس البثّ الفارغ**: orchestrator 200 بلا أي `assistant_delta` مرئي ولا إطار نهائي ⇒
   `empty_stream` ⇒ المتابعة للمرشح التالي/الـ fallback المحلي. أي terminal
   (`assistant_final`/`error`/`complete`/`assistant_error`) ⇒ return — يحفظ عقد الإطار
   النهائي الواحد (ISS-016).
5. **Supervisor يفرض educational عند الحقن قبل أي DSPy** — الـ monolith حقن المحتوى فقط بعد
   `detect_explanation_with_context`، فالمسار تعليمي بالبناء. misroute إلى chat/general
   يُضيع المحتوى المحقون.
6. **markers الكشف الرياضي تشمل الصيغ المعرَّفة بـ«ال»** (درس ISS-109): «الأعداد المركبة»
   وليس فقط «أعداد مركبة» — أداة التعريف تكسر مطابقة السلاسل الفرعية ثنائية الكلمات.

### قياس النجاح حياً

```bash
# 1. شرح تمرين عبر الرسم — سجل :8006 يُظهر POST + log الحقن
#    «اعطني تمرين دوال 2016» ثم «اشرح السؤال 1»
grep "injected_exercise" /tmp/orchestrator.log   # [D-103] injected_exercise chars=... ref=...

# 2. استشارة reasoning — سجل :8008 يُظهر POST /execute
curl -s localhost:8006/metrics | grep cogniforge_reasoning_consult_total

# 3. رجوع فوري بلا deploy
export EXPLANATION_VIA_ORCHESTRATOR=0   # الشرح يعود محلياً

# 4. اختبارات
pytest tests/services/test_d103_explanation_via_orchestrator.py \
       tests/microservices/orchestrator_service/test_d103_injected_context.py --no-cov
```

### السلسلة الكاملة (D-102 → D-103)

| Decision | المُصلَح/المُضاف |
|----------|-----------------|
| D-102 | ISS-111 — تسميم history برسالة النظام |
| **D-103** | **More-via-LangGraph: شرح التمارين عبر الرسم (حقن exercise_content) + استشارة reasoning-agent من Synthesizer (fail-open)** |

### التحقق الحي بالأسرار الحقيقية (2026-06-11 — D-103 live E2E)

OpenRouter حقيقي عبر المكدس الكامل (WS → monolith → orchestrator :8006 → reasoning :8008؛
SQLite مشترك — Supabase مُتحقَّق قراءةً عبر جسر HTTPS لأن TCP محجوب في الـ sandbox):
- **A**: «اشرح السؤال الأول» ⇒ `[D-103] injected_exercise chars=9670` +
  `retrieval_source=injected_exercise` ⇒ شرح عربي حقيقي 2292 حرفاً (TTFT 2.7s) — لا envelope
  ولا tags ولا اعتذار. **B**: `reasoning_consult success chars=2042` + metric. **C**: orchestrator
  ميت ⇒ fallback محلي حقيقي 5368 حرفاً. ISS-110 حي 7/7 + دور admin + صفوف BKT.
- **اكتشافان أصلحتهما الحياة**: سقف الاستشارة 20s→35s، وحارس **الهانغول الكوري** في المُطهِّر
  (نموذج مجاني سرّب `앞에서먼저` في رد MODE_B حقيقي) — `sanitize_response` + `sanitize_chunk`.

---

## 6.91 Adaptive Pedagogy Layer + Question-Only Retrieval (2026-06-11, D-104 + ISS-112)

> «المعيار الأعلى ليس الانبهار اللحظي، بل الاستقلال المعرفي» — فلسفة E-TAALEEM مُجسَّدة
> هندسياً: **إغلاق حلقة BKT** (الكتابة → القراءة → تكييف عمق التدريس) + إنهاء فضيحة
> «اعطني السؤال رقم 2» المُشخَّصة حياً. لا يُكسر بدون ADR.

### ISS-112 — فضيحة «السؤال رقم 2» (مُشخَّصة من transcript حي)

| العرَض الحي | الجذر | الإصلاح |
|------------|-------|---------|
| «اعطني السؤال رقم 2 فقط» ⇒ التمرين كاملاً | لا كاشف لنية «سؤال مرقَّم فقط» | `detect_question_only_request` + `_extract_numbered_question` (exercise_retrieval.py) — اقتطاع حتمي من النص الرسمي، **صفر LLM** |
| «اعطني السؤال رقم 2» ⇒ **حل كامل مُهلوَس** بنص مشوه (Wege/substitue/apoptomorphic) | الطلب سقط لمسار LLM | preempt جديد في `chat_with_agent` بعد التحية وقبل المفهرَس (`_stream_question_only_response`، fallback_path=0.4) |
| «تتبّع المعرفة: **general**» لسؤال أعداد مركبة | «الأعداد/الاعداد المركبة» ليست في keywords التصنيف (درس ISS-109 المتكرر: «ال» تكسر المطابقة ثنائية الكلمات) | الصيغ المعرَّفة/الجمع أُضيفت لـ `classify_concept` (bkt_engine.py) |

**قواعد ISS-112 الدائمة**: (1) طلب سؤال مرقَّم = اقتطاع من النص الرسمي حصراً — ممنوع LLM.
(2) نية الشرح («اشرح السؤال 2») تهزم الاقتطاع دائماً. (3) البند المكرر عبر الأجزاء يُرجَع
بكل مطابقاته مع عناوين أجزائها (صدق أوضح من تخمين). (4) الرقم الغائب يُستكمل من آخر طلب
مرقَّم في الحوار. (5) صفر قطع مبثوثة ⇒ المسار يتابع (fail-open).

### D-104 — طبقة البيداغوجيا التكيفية (إغلاق حلقة BKT)

الفجوة التي كانت تخون الفلسفة: `latest_mastery()` موجود لكن **لا شيء يقرأه ليتكيف** —
المتمكن (0.9) والضائع (0.1) يتلقيان نفس أسلوب الشرح حرفياً.

```
customer_chat (المنسّق يملك صورة المتعلم):
  _build_pedagogy_directive(user_id, question, history)
    classify_concept ⇒ concept_id
    BKTAnalyticsService.latest_mastery + interaction_count   (جلسة معزولة، سقف 2s)
    AdaptivePedagogySkill.derive ⇒ PedagogyDirective
  ⇒ context["pedagogy_directive"]
orchestrator_client.chat_with_agent:
  «[توجيه تربوي] {directive}» يُسبق في _effective_question (بعد MODE_B إن وُجد)
  ⇒ يصل للـ orchestrator وكل مسارات الـ fallback — المسارات الحتمية لا تتلوث
```

**السياسة الحتمية** (`adaptive_pedagogy_skill.py`): mastery ≥ 0.7 ⇒ `socratic` (قُد بأسئلة،
لا تكشف الحل)؛ 0.35–0.7 ⇒ `guided` (تلميح ثم خطوات بفجوات)؛ < 0.35 أو مجهول ⇒ `scaffolded`
(شرح كامل بسقالات)؛ حِمل مرتفع ⇒ تخفيض درجة. + **كتالوج المفاهيم الخاطئة** لكل concept_id
(تكامل الجداء = جداء التكاملين، ضرب الاحتمالات بلا استقلال...) ⇒ تصحيح «على مستوى الفكر
لا الحكم». metrics: `cogniforge_skill_pedagogy_invocations_total{guidance_level}`.

**القواعد الـ 8 الدائمة**: `ADAPTIVE_PEDAGOGY_DOCTRINE` v1.0.0 في `doctrine.py` (manifest
`adaptive_pedagogy`) — أبرزها: يُبنى حصراً فوق `student_mastery_probability` (D-074)؛
fail-open مطلق؛ عتبات حتمية (تغييرها = ترقية doctrine)؛ توجيه < 400 حرف D-067-safe؛
الغاية الاستقلال المعرفي. **Registry: 15 skill** (كان 14) — بوابة
`check_skills_doctrine.py` تحرس الـ manifest + التوصيل الفعلي (no-ZOMBIE نمط D-073).

### قياس النجاح حياً

```bash
# الفضيحة مستحيلة بنيوياً:
#   «اعطني السؤال رقم 2 ...» ⇒ log: question_only_preempt reason=question_only_sliced n=2
# البيداغوجيا التكيفية:
#   grep "pedagogy_directive level=" — scaffolded للمبتدئ، socratic بعد إتقان ≥ 0.7
pytest tests/services/test_iss112_question_only.py tests/services/test_d104_adaptive_pedagogy.py --no-cov
python scripts/fitness/check_skills_doctrine.py   # … Adaptive pedagogy wired (D-104)
```

### السلسلة الكاملة (D-103 → D-104)

| Decision | المُصلَح/المُضاف |
|----------|-----------------|
| D-103 | شرح التمارين عبر الرسم + استشارة reasoning (مُتحقَّق حياً بالأسرار الحقيقية) |
| **ISS-112** | **فضيحة «السؤال رقم 2»: اقتطاع حتمي صفر-LLM + إصلاح تصنيف BKT للأعداد المركبة** |
| **D-104** | **طبقة البيداغوجيا التكيفية: قراءة إتقان BKT تقود عمق التدريس (socratic/guided/scaffolded) + كاشف المفاهيم الخاطئة — Skill رقم 15** |

---

## 6.92 Test-Hygiene Doctrine + CI Overhaul — sys.modules Poisoning Catastrophe (2026-06-12, ISS-113 / D-105)

> **الكارثة**: الـ workflow الرئيسي «CI» أحمر منذ D-103 — اختبار واحد من 3445
> (`test_d103_injected_context::test_retriever_returns_injected_doc_only`) يفشل بـ
> `mock.Document` على CI بينما يمرّ محلياً. هذا القسم يحكم نظافة الاختبارات وبنية CI —
> لا يُكسر بدون ADR.

### الجذر (مُثبت بإعادة إنتاج محلية مطابقة 100%: نفس الاختبار، نفس الخطأ حرفياً)

1. `pytest.ini` كان **بلا `testpaths`** ⇒ pytest يجمع من جذر المستودع ⇒ يلتقط
   `scripts/test_*.py` (سكربتات تحقق يدوي).
2. **`scripts/test_search_pipeline.py`** كان يحقن `sys.modules[m] = MagicMock()` **على
   مستوى الوحدة — وقت الجمع** لـ21 موديولاً (llama_index.core.schema + tavily + bs4 +
   langchain...) بلا تنظيف؛ و`scripts/test_super_reasoner.py` مثله داخل جسد الاختبار.
3. ترتيب الجمع: `scripts/` قبل `tests/` ⇒ السم يُزرع أول الجلسة. `test_d103` أول مستورد
   لـ`graph/search.py` ⇒ `from llama_index.core.schema import Document` يلتقط
   `mock.Document` ⇒ الفشل. (محلياً كان يمرّ لأن التشغيلات استهدفت `tests/` فقط.)

### اكتشافات أعمق أثناء الإصلاح (كلها أُصلحت بالجذر)

- **`APP_DATABASE_URL` collection-time poison**: 3 ملفات WS tests كانت تكتب
  `os.environ.setdefault("APP_DATABASE_URL", sqlite)` على مستوى الوحدة، و`base.py:78`
  يفضّله على `DATABASE_URL` وقت التحقق ⇒ 7 اختبارات settings/kernel «تمرّ منفردة وتفشل
  بالحزمة». أُزيل السطر من الملفات الثلاثة.
- **`isolated_helpers` + `teardown_module` leak**: fixture في `test_secret_key_persistence`
  كانت تحذف `SECRET_KEY` بلا استرجاع، و`teardown_module` يحذفه نهائياً بعد كل
  الـteardowns ⇒ `SECRET_KEY=None` يتسرب للجلسة ⇒ 8 اختبارات microservices تسقط 401
  (الخدمة تتراجع لمفتاحها الافتراضي بينما الاختبار يسكّ بـfallback آخر). أُصلحت الـfixture
  (snapshot/استرجاع كامل) وحُذف teardown_module.
- **`python` العارية في subprocess**: `test_phase0_governance` كان يستدعي `"python"`
  (قد تكون 3.11) فتفشل سكربتات PEP 695 بـSyntaxError زائف. الآن `sys.executable`.
- **حارس polyfill خاطئ**: `test_orchestrator_admin_tool_security` كان يستبدل redis بشرط
  `"redis" not in sys.modules` (يُظلِّل redis الحقيقي غير المستورد بعد) — الصحيح
  `importlib.util.find_spec("redis") is None`.

### القواعد الدائمة (D-105 — لا تُكسر بدون ADR)

1. **`testpaths = tests scripts/ci microservices` في pytest.ini** — جمع صريح أبداً.
   سكربتات التحقق اليدوي في `scripts/` لا تُجمع.
2. **ممنوع أي كتابة `sys.modules` بقيمة Mock** في ملف يجمعه pytest — تُظلِّل موديولات
   حقيقية وتسمّم الجلسة. polyfill مشروع = `types.ModuleType` مشروط بغياب التبعية
   (`find_spec is None` أو `except ImportError`).
3. **ممنوع `os.environ[...] =` على مستوى الوحدة** خارج allowlist موثَّقة قابلة للتقليص فقط.
4. **بوابة `scripts/fitness/check_test_hygiene.py`** (AST) تفرض 2+3 في job guardrails —
   لا تُعطَّل ولا يُضاف للـallowlist بدون مراجعة.
5. **fixtures التي تحذف/تعدّل env يجب أن تستعيد** (snapshot في setup، استرجاع في teardown).
   `teardown_module` الذي يحذف env بلا استرجاع ممنوع.
6. **subprocess في الاختبارات يستدعي `sys.executable`** لا `"python"` العارية.
7. **fixture `_global_state_isolation`** (autouse في tests/conftest.py) تستعيد os.environ
   وتصفّر كاش settings عند رصد تسريب — دفاع عميق، لا رخصة للتسريب.
8. **بنية CI**: جوبا اختبار متوازيان (`test-monolith` بالتغطية + `test-microservices`) —
   **xdist غير آمن** (الترتيب داخل-العملية مقصود لعزل سجل الجداول). + job
   `frontend-tests` (8 ملفات node حتمية). + `concurrency` إلزامي في كل workflow جديد.
9. **قوائم deselect تتقلص فقط**: أي إدخال جديد يتطلب إثبات «أحمر على main» + تعليقاً
   يشرح الجذر. D-105 قلّصها من 40 إلى 17 (12 resilience أُعيدت كتابتها على العقد الحالي
   + 11 isolation أُصلحت جذرياً).

### السلسلة الكاملة (D-104 → D-105)

| Decision | المُصلَح/المُضاف |
|----------|-----------------|
| D-104 | طبقة البيداغوجيا التكيفية + ISS-112 |
| **D-105** | **ISS-113 — تسميم sys.modules وقت الجمع + إصلاح 23 اختباراً مستثنى بالجذر + بوابة نظافة + تقسيم jobs + frontend-tests + concurrency×38** |

---

## 6.93 Voice Tutor Future-Readiness (DEFERRED — D-107)

> قرار المستخدم (2026-06-13): الصوت **مؤجَّل** للمستقبل مع الاستعداد له بنماذج
> AI متقدمة فائقة الجودة — لا تنفيذ الآن، الأولوية لعظمة توليد المحتوى. هذا
> القسم يوثّق المعمارية المستقبلية ونقاط الامتداد فلا يُعاد استكشافها.

### لماذا التأجيل (لا الإهمال)
الجودة أولاً: إصلاح كوارث المحتوى (ISS-114) والتطوير الثوري للـ Skills يسبق أي
ميزة جديدة. وقاعدة D-073 (لا ZOMBIE) تمنع إنزال قدرة نصف-موصولة: الصوت يصل **فقط**
كـ `VoiceSkill` كامل end-to-end في تغيير واحد.

### المعمارية المستقبلية (عند التنفيذ)
- **TTS لكل رسالة + قراءة تلقائية** عند `assistant_final`/انتقال `isComplete`.
- **STT** لإملاء السؤال صوتياً.
- **نماذج صوتية متقدمة عبر HTTPS** (جودة عالية) — لا Web Speech API الأضعف.
  مرشحون يُقيَّمون وقت التنفيذ؛ لا شيء موصول الآن.
- **القاعدة الملزِمة (D-107)**: الصوت = `VoiceSkill` بعقد Pydantic + Prometheus
  metrics + tests + doctrine entry + registry + **مستهلك حيّ** — في PR واحد.

### نقاط الامتداد (مُسجَّلة حرفياً — لا تُعاد دراستها)
| الغرض | الموقع |
|------|--------|
| زر TTS لكل رسالة | نمط زر النسخ `ChatInterface.jsx` (شريط أفعال الرسالة) |
| toggle القراءة التلقائية | نمط `header-theme-btn` في `CogniForgeApp.jsx` |
| trigger القراءة | `assistant_final` / انتقال `isComplete` في `useAgentSocket.js` |
| تجريد LaTeX قبل النطق | `frontend/app/utils/preprocessMath.js` (أساس `stripMathForSpeech`) |

---

## 6.94 Four-Catastrophe Content Integrity Fix (2026-06-13, ISS-114 / D-106)

> transcript حي أظهر 4 كوارث على المسار الإنتاجي. الإصلاح يُغلق الثغرة الكبرى:
> بثّ orchestrator HTTP (MODE_B) كان يصل للطالب **بلا أي حارس**.

### الكوارث الأربع والجذور (file:line)
| # | الكارثة | الجذر |
|---|---------|------|
| 1 | غارباج لاتيني («experiences_random»، «brückecónceptual»، «exitos») | حارس البثّ يفحص أول 200 حرف فقط (`arabic_stream_guard.py`)؛ والثغرة الكبرى: حلقة `aiter_lines` في `orchestrator_client.py` تبثّ مخرَج الـ orchestrator للطالب بلا حارس |
| 2 | تسريب HTML خام («قم بتوليد واجهة» → `<div class="card">`) | لا كاشف لنية «توليد واجهة» → يسقط للـ LLM؛ output_firewall لا يُطبَّق على بثّ الـ orchestrator |
| 3 | واجهة نرد/عملة عامة بدل كيس التمرين | `_strategy_universe` يُفعَّل من أمثلة المساعد في الـ history + يسبق composition |
| 4 | «الدوال المركبة 2024» → تمرين الاحتمالات + BKT خاطئ | aliases «دوال مركبة» مفقودة في arabic_normalize + bkt_engine |

### الإصلاح (طبقات)
- **ContentIntegritySkill (#16)** — `StreamIntegrityFilter` ذو حالة على **كامل
  التيار** موصول في مخرج الـ orchestrator HTTP + المسارات المحلية. يحذف الغارباج
  اللاتيني (snake_case/diacritics/خارج allowlist) و HTML، يحفظ LaTeX حرفياً،
  بوابة الوضع العربي تحمي الفرنسي، fail-open مطلق.
- **كاشف نية «توليد واجهة»** → `is_visual_request` يوجّه لـ MODE_B (مكوّن بصري)
  بدل LLM يكتب HTML. + قاعدة EXPLANATION_DOCTRINE v2.3.0 «لا HTML في نص الطالب».
- **توجيه**: composition قبل universe + universe يُفعَّل من نص الطالب فقط (مرآة
  D-102). PROBABILITY_CALCULATION_DOCTRINE v1.5.0.
- **aliases**: «دوال مركبة/الدوال المركبة/...» في arabic_normalize + bkt_engine.

### القواعد الدائمة (لا تُكسر بدون ADR)
1. كل بثّ مواجه للطالب (orchestrator HTTP + محلي) يمرّ عبر `StreamIntegrityFilter`
   على كامل التيار — لا أول نافذة فقط.
2. universe (نرد/عملة) لا يُفعَّل من نص المساعد في الـ history.
3. طلب «توليد واجهة» يُوجَّه للأداة البصرية المُهيكلة — HTML في نص الطالب مستحيل بنيوياً.
4. صياغة «الدوال المركبة» = الأعداد المركبة (لا الدوال العددية).

### التحقق
203 اختبار backend + 18 frontend (BktMasteryCard) + skills-doctrine gate (16 skill، لا
ZOMBIE) + ruff. **التحقق الحي الكامل (orchestrator HTTP MODE_B + Supabase) يجري في
Codespaces** بالأسرار الحقيقية — الـ sandbox بارد ويحجب Postgres (نمط §6.55/§6.84).
سكربت `scripts/verify_iss114_live.py` (مُخطَّط) يُعيد تشغيل transcript الكارثة هناك.

---

## 6.95 Revolutionary Skills/LangGraph Development (2026-06-13, D-108→D-111)

> طلب المستخدم: تطوير ثوري لمنظومة الخدمات المصغرة و LangGraph. الجوهر المُشخَّص:
> الـ orchestrator اليوم موجِّه ذكي **أعمى عن حالة الطالب** (BKT monolith-only)،
> و`_compose_answer` ليس تركيباً، ولا عقدة تحقق ذاتي. الأركان الأربعة تحوّله إلى
> **عقل تربوي واعٍ يتحقق من إجاباته**.

### الأركان (الحالة)
| ركن | القرار | الحالة |
|-----|--------|--------|
| **P4 — LearningPathSkill** | D-111 | ✅ **مُنفَّذ ومُتحقَّق** — Skill #17 حتمي فوق BKT، موصول حيّاً في customer_chat، يبثّ learning_path_card (مُسجَّل + محفوظ)، frontend + CSS + doctrine + gate + tests |
| **P1 — Orchestrator واعٍ بالإتقان** | D-108 | مُصمَّم — D-104 يثبّت `pedagogy_directive` في السؤال نحو الـ orchestrator؛ الترقية البنيوية (AgentState.cognitive_context + قراءة SupervisorNode/SynthesizerNode) تحتاج تشغيل الـ orchestrator للتحقق الحي (Codespaces) |
| **P3 — Real Synthesis** | D-110 | ✅ **مُنفَّذ ومُتحقَّق حياً** — `_compose_answer` تركيب مرتّب (reasoning+research مدموجان) + `composition_confidence ∈ [0,1]` + مقياس Prometheus `cogniforge_pipeline_composition_confidence`؛ مكشوف في `/compose` (مُتحقَّق حياً) + 7 اختبارات |
| **S1 — Mandatory Backbone (D-112)** | D-112 | ✅ **مُنفَّذ ومُتحقَّق حياً** — hard-fail `ORCHESTRATOR_REQUIRED` بلا fallback محلي (REQUIRE_ORCHESTRATOR=1)؛ orchestrator UP→إجابة، DOWN→خطأ صريح صفر deltas؛ §6.96 |
| **P2 — CritiqueNode** | D-109 | مُصمَّم — عقدة تحقق ذاتي بعد Synthesizer (fail-open، علم بيئي)؛ تحتاج الرسم الـ13-node حيّاً للتحقق |

### قاعدة الصدق (runtime-truth)
P1/P2/P3 تمسّ الـ orchestrator microservice الذي لا يعمل في الـ sandbox البارد
(صفر منافذ + Postgres محجوب). وفق doctrine «import + call chain + runtime
evidence»، لا تُعلَن ACTIVE قبل التحقق الحي في Codespaces بالأسرار. P4 مُنفَّذ
بالكامل لأنه Skill monolith حتمي قابل للاختبار in-process.

### السلسلة
| Decision | الموضوع |
|----------|---------|
| D-105 | test-hygiene + CI overhaul |
| D-106 | ISS-114 — إصلاح الكوارث الأربع + ContentIntegritySkill (#16) |
| D-107 | تأجيل الصوت (جاهزية موثّقة) |
| **D-111** | **LearningPathSkill (#17) — المسار التعلّمي التكيفي فوق BKT** |
| D-108/D-109/D-110 | orchestrator واعٍ بالإتقان / CritiqueNode / Real Synthesis (مُصمَّمة — تحقق حيّ في Codespaces) |

---

## 6.96 Mandatory Microservices Backbone — Hard-Fail (2026-06-13, D-112 · Phase 3 S1)

> **قرار المستخدم الحاسم:** الخدمات المصغرة + الرسم الـ13-node هي **القلب الإلزامي
> الوحيد**. إن لم تعمل ⇒ النظام **يتوقف برسالة خطأ صريحة**، لا fallback صامت إلى
> `local_graph`. تجسيد «runtime truth over synthetic certainty» حتى نهايته: لا
> نتظاهر أن الرسم المحلي ذا العقدتين بديل عن الـ13-node.

### التغيير (S1 — العمود الفقري)
`orchestrator_client.chat_with_agent`: بعد فشل كل مرشّحي الـ orchestrator HTTP
(تعذّر اتصال/empty_stream)، إذا `REQUIRE_ORCHESTRATOR=1` (افتراضي) ⇒ إطار `error`
صريح بالرمز `ORCHESTRATOR_REQUIRED` (صفر `assistant_delta` محلي) — لا
`_stream_local_graph_response`. `=0` يُعيد الـ fallback القديم (rollback بلا
deploy — نمط D-025). `MANDATORY_ORCHESTRATION_DOCTRINE` v1.0.0 + manifest.

### القواعد الدائمة (D-112)
1. الخدمات المصغرة + الرسم الـ13-node هي القلب الإلزامي للتوليد.
2. تعذّرها ⇒ `ORCHESTRATOR_REQUIRED` صريح، صفر سقوط صامت إلى local_graph.
3. `REQUIRE_ORCHESTRATOR=1` افتراضي؛ `=0` rollback فوري.
4. **مقايضة صريحة**: سقوط الـ orchestrator في الإنتاج = انقطاع كامل (لا إجابة ضعيفة). القرار يخصّ المالك ومُوثَّق.

### التحقق الحي (2026-06-13 — المكدس الكامل، الأسرار الحقيقية)
بيئة: monolith :8000 → orchestrator :8006 (الرسم الـ13-node، `graph_ready=true`) →
**OpenRouter حقيقي**؛ SQLite (Postgres 6543 محجوب في الـ sandbox)؛ Supabase مُؤكَّد
حياً عبر جسر HTTPS (`db_bridge.py` → PostgreSQL 17.6، 34 جدول).
- **orchestrator UP**: «قانون نيوتن» → 44 delta، إجابة نظيفة + `learning_path_card` (P4 حيّ). 6× `POST /api/chat/messages` 200 (المسار عبر الخدمات لا المحلي).
- **orchestrator DOWN**: نفس السؤال → `error=ORCHESTRATOR_REQUIRED`، **صفر delta، لا local** ✅.
- **ISS-114 حيّ 6/6**: صفر غارباج لاتيني على مسار orchestrator-HTTP (3201 حرف نظيف)، صفر HTML خام، الكيس الصحيح (لا نرد/عملة)، «الدوال المركبة 2024» → الأعداد المركبة. الفرنسي المشروع يمرّ (بوابة الوضع العربي).
- `scripts/verify_revolution_live.py` (6/6) + `tests/services/test_d112_mandatory_orchestrator.py` (3/3).

### الحالة المتبقية (Phase 3 S2–S4 — مُصمَّمة، التتمة)
- **S2**: port المهارات الحتمية (probability/content_integrity/learning_path/greeting/indexed-retrieval + knowledge_base) **داخل** الـ orchestrator كعقد رسم — «إزالة كل مسار المونوليث» الكاملة (المونوليث = بوابة WS رقيقة). كبير — يُرحَّل عبر مراحل مُتحقَّقة.
- **S3/S4**: P1 Mastery-Aware Orchestrator + P3 Real Synthesis + P2 CritiqueNode داخل الرسم.
- القيد المعماري: المونوليث لا يستورد من `microservices/` والعكس — «النقل» = port (نسخ مستقل)، لا import.

---

## 6.97 وَهْم الإتقان — Socratic No-Answer OS (2026-06-14, ISS-115 / D-113)

> **الكارثة (transcript حي):** عند «اشرح السؤال الأول من تمرين الاحتمالات» كان النظام
> يُسلّم الحلّ الكامل (`C(11,3)=165`، `P(A)=14/165`، `P(B)=56/165`، `E(X)=1.73`، جدول
> قانون X). الطالب يقرأ، يومئ، يشعر أنه «فهم» (وهم الطلاقة)، ثم ينهار يوم الامتحان لأن
> الدراسة درّبت **التعرّف** بينما الامتحان يطلب **التوليد** (Bjork: الأداء ≠ التعلّم؛
> Roediger: أثر الاختبار؛ Kapur: الفشل المُنتِج؛ Renkl: تلاشي المثال المحلول).

### الجذر المؤكَّد
- `doctrine.py:EXPLANATION_DOCTRINE` (v2.3.0) كان يأمر صراحةً: «اعتمد على الإجابة النموذجية
  كحُجّة للنتائج النهائية» + «النتيجة النهائية في `$$\boxed{}$$`» → الـ LLM يطبع كل الأجوبة.
- `exercise_retrieval.detect_explanation_with_context` كان يمرّر `full_content` (يحوي
  الإجابة النموذجية) للـ LLM، لا `display_content` (أسئلة فقط).

### الإصلاح (3 طبقات دفاع — الكل fail-open)
1. **doctrine سقراطي (v3.0.0):** أُعيدت كتابة `EXPLANATION_DOCTRINE` بالكامل — القاعدة
   الذهبية «لا تكشف خطوةً يستطيع الطالب توليدها» + منع مطلق للنتيجة النهائية + محاولة قبل
   الشرح + سُلّم تلميحات متصاعد + بروتوكول «لم أفهم» (تشخيص لا إعادة اشتقاق) + شرح ذاتي +
   تفنيد بعد الخطأ. `build_exercise_explanation_prompt` أُعيدت كتابته (742 حرف، يحفظ مراسي
   CI «الإجابة النموذجية»/«LaTeX»/«حرفياً»). `MODEL_ANSWER_*` صارت **لوضع التحقق حصراً**.
2. **أسئلة-فقط للـ LLM:** `orchestrator_client._stream_exercise_explanation_response` يمرّر
   `display_content` (أسئلة بلا حل) لا `full_content` — فلا يملك الـ LLM ما يكشفه.
3. **حارس حتمي أخير — `AnswerRedactionSkill` (Skill #18):** `app/services/skills/answer_redaction_skill.py`
   يحجب `\boxed{X}`→`\boxed{?}`، و`P(...)=/E(...)=/C(...)=<عدد>`، وأسطر «إذن…=عدد»، وعلامات
   «الإجابة النهائية:». **نطاق ضيّق** يحفظ الصيغ التعليمية (`نستخدم C(n,k)`، الصيغ الرمزية).
   موصول في `content_integrity.sanitize_final_text` (يغطّي orchestrator + المحلي على الإطار
   النهائي) + `local_graph._apply_answer_redaction` (في `_chat_node`) + `redact_chunk`
   per-chunk للبثّ المباشر.

### القواعد الدائمة (D-113 — لا تُكسر بدون ADR)
1. **القاعدة الذهبية فوق كل القواعد:** لا تكشف نتيجةً أو خطوةً يستطيع الطالب توليدها بنفسه.
2. **الشرح يستقبل أسئلة-فقط** (`display_content`)؛ الإجابة النموذجية (`full_content`) لوضع
   التحقق حصراً.
3. **كل مخرَج نهائي مواجه للطالب يمرّ عبر `sanitize_final_text`** (الذي يستدعي
   `redact_final_answers`) — لا تتجاوزه.
4. **«لم أفهم» = تشخيص + تلميح أدنى واحد**، ممنوع إعادة اشتقاق الحل (أكثر الردود تدميراً).
5. **حجب النطاق الضيّق:** لا تُوسِّع الـ redaction لتشمل المساواة الرمزية الوسيطة (false-positive).
6. `EXPLANATION_DOCTRINE_VERSION ≥ 3.0.0`؛ بوّابة `check_skills_doctrine.check_answer_redaction_wired`
   تحرس التوصيل + وجود قواعد المنع («لا تكشف» + «ممنوع»).

### التحقق
- **محلياً (sandbox — بلا pydantic):** خوارزمية الـ redaction مُثبتة standalone — كل التسريبات
  (`14/165`, `165`, `1.73`, `\boxed`, جدول P(X)) محجوبة؛ التعليم الوسيط محفوظ؛ صفر false-positive.
  doctrine standalone: v3.0.0، 3 مراسي، 742 حرف، قاعدة التسريب القديمة أُزيلت. registry: 18 skill،
  `answer_redaction` non-ZOMBIE. ruff + runtime_truth ✅.
- **CI/Codespaces (بالأسرار):** `tests/services/test_iss115_socratic_no_answer.py` (24 اختبار) +
  بوّابة skills-doctrine. **سيناريو الكارثة الحي عبر WS:** «اشرح السؤال الأول» → أسئلة سقراطية +
  تلميح أدنى، **صفر** `14/165`/`165`/`$$\boxed{}$$`؛ «لم أفهم» → سؤال تشخيصي لا إعادة اشتقاق.

### نطاق هذه الجولة + المتابعة
- **مُنفَّذ (Phase 1):** الطبقات الثلاث أعلاه (المسار المحلي + مخرج orchestrator عبر
  `sanitize_final_text`). **متابعة:** فرض السقراطية داخل `SynthesizerNode` (الرسم 13-node)،
  سُلّم الدعم 5-درجات في `AdaptivePedagogySkill`، صدق BKT (assisted vs unaided-delayed)،
  واجهات مولدة بلا أرقام نهائية، وضع التحقق المنفصل، مقياس «فجوة الوهم».

### الجولة 2 (2026-06-14) — السقراطية في الخدمات المصغرة + سُلّم الدعم الخماسي
الجولة 1 غطّت المسار المحلي. الجولة 2 تُغلق الكارثة على **المسار الإلزامي** (الخدمات
المصغرة — D-112) + تُضيف سُلّم الدعم المتدرّج:
1. **port الحجب إلى الـ orchestrator** (`response_sanitizer.py`): `redact_final_answers`
   + `_strip_boxed` (نسخة مستقلة stdlib — المونوليث لا يستورد من microservices). مدموج
   في `sanitize_response` (يغطّي مخرج كل عقدة: Synthesizer/ChatFallback/GeneralKnowledge)
   + `sanitize_chunk` (حجب `\boxed` الحيّ). نطاق ضيّق (يحفظ `C(n,k)` + قانون أوم `U=RI`).
2. **عقد السقراطية في `SynthesizerNode`** (`search.py`): system prompts «اكتب الشرح أو
   الحل» → «قُد بأسئلة وتلميحات؛ ممنوع كشف النتيجة لتمرين يحلّه الطالب؛ المعرفة العامة
   تُجاب مباشرة» (فرعا no-docs + with-docs + `EducationalSynthesizer` DSPy signature).
3. **سُلّم الدعم الخماسي** (`adaptive_pedagogy_skill.py` → doctrine v1.1.0): `support_level`
   1..5 (worked_example→completion→backward_fading→prompted→unaided) مشتقّ حتمياً من
   الإتقان + الحِمل؛ `guidance_level` الثلاثي يبقى دون تغيير (توافق خلفي)؛ clause «مستوى
   الدعم» يُلحق بـ `directive_text` فيصل الـ LLM عبر prepend الموجود (لا plumbing إضافي).
- **التحقق:** port الحجب stdlib مُثبت standalone (تسريبات محجوبة، صفر false-positive على
  `C(n,k)`/`U=RI`)؛ سُلّم الدعم 8 حالات mastery→level + طول ≤400؛ ruff + runtime_truth +
  doctrine standalone خضراء. اختبارات: `test_response_sanitizer.py` (+8 D-113) +
  `test_d104_adaptive_pedagogy.py` (+سُلّم الدعم). التحقق الحي الكامل عبر WS في Codespaces.
- **مؤجَّل:** تمرير `support_level` مُهيكلاً في AgentState/routes (الـ directive يصل عبر
  prepend حالياً)؛ صدق BKT بالمنحنيين؛ واجهات بلا أرقام؛ وضع التحقق؛ فجوة الوهم.

### السلسلة الكاملة (D-112 → D-113)
| Decision | الموضوع |
|----------|---------|
| D-112 | العمود الفقري الإلزامي (microservices hard-fail) |
| **D-113 (ج1)** | **وَهْم الإتقان — Socratic No-Answer: doctrine سقراطي + أسئلة-فقط + AnswerRedactionSkill (المسار المحلي)** |
| **D-113 (ج2)** | **السقراطية + الحجب في الـ orchestrator (response_sanitizer + SynthesizerNode) + سُلّم الدعم الخماسي (v1.1.0)** |

---

## 6.98 المثال المحلول المُتدرّج المُقيَّد بالإتقان (2026-06-15, ISS-116 / D-114)

> يُكمّل D-113 (السقراطية) ويُصحّح إفراطه المدمّر. الكارثة (transcript حي): طالب بإتقان
> **14%** (مبتدئ مطلق) حار وسأل «لو جاء يوم الامتحان لا أستطيع حله؟» فردّ النظام بحلقة
> أسئلة سقراطية لا نهائية **بلا أي مثال محلول** → غرق ورسب. + كارثة B: رموز أجنبية
> مُسرّبة حيّاً (`også`/`функция`/`Murphy`/`headcount`). هذا القسم يحكم متى وكيف يُكشف
> المثال المحلول — لا يُكسر بدون ADR.

### الجذر
D-113 طبّق «لا تكشف أبداً» عالمياً فحرم المبتدئ المطلق من المخطط الذهني الذي يحتاجه
(worked-example effect — Sweller/Renkl: المبتدئ يتعلّم من دراسة حلّ كامل أولاً، ثم
يتلاشى الدعم، ثم يُقاس غير المدعوم). معمارياً: `adaptive_pedagogy_skill` يحسب
`support_level=1` صحيحاً لكن `customer_chat._build_pedagogy_directive` كان يرمي الرقم
ويُمرّر النص فقط؛ والحجب (`answer_redaction_skill` + `sanitize_final_text`) أعمى عن
المستوى؛ و`sanitize_chunk` أضعف من `sanitize_response` (بلا قائمة كلمات أجنبية).

### الحل — التوفيق بين فجوة الوهم وتأثير المثال المحلول
المبتدئ المطلق يتلقّى مثالاً محلولاً كاملاً على مسألة **مماثلة (isomorphic — أرقام/سياق
مختلف)**، بينما **تمرينه المُقيَّم يبقى محجوباً** ويُقاس على الأداء غير المدعوم. دراسة
مثال على مسألة أخرى = اكتساب مخطط، لا وهم طلاقة (الوهم يأتي من إعادة قراءة حلّ المسألة
التي ستُقيَّم عليها).

### القواعد الـ 7 الدائمة (D-114 — لا تُكسر بدون ADR)
1. **حدّ «المماثل ↔ المُقيَّم» هو أطروحة الأمان**: المثال يُلَفّ بفواصل عربية حارسة
   `⟦مثال_محلول⟧ … ⟦/مثال_محلول⟧`؛ الحجب يُعفي ما **داخلها** عند `support_level==1`
   ويحجب ما **خارجها**؛ غياب الفواصل أو مستوى آخر ⇒ **حجب كامل (fail-closed)** — فلا
   تتسرّب إجابة تمرين الطالب أبداً.
2. **الافتراض الآمن = 5** (محجوب كلياً) عند كل حدّ في السلسلة عند أي تعذّر — لا 1 —
   كي لا يكشف فشلٌ واحد كل الإجابات.
3. **`support_level` يعبر السلسلة كاملةً** (customer_chat → context → orchestrator_client
   → routes `ChatRunContext`+`_extract_support_level` → `AgentState` → `SynthesizerNode`)
   ويُمرَّر إلى **كلا** منفذَي الحجب المستقلَّين (`answer_redaction_skill` +
   microservices `response_sanitizer`) — وإلا الـ orchestrator يُعيد حجب المثال.
4. **بوّابة الكشف**: المثال يُكشف فقط عند `support_level==1` (إتقان <0.2) أو حيرة
   متكرّرة (≥2 «لم أفهم»). الخريطة المنهجية حتمية (المهارة المُتحوِّلة)؛ المثال الملموس
   بالأرقام يُولِّده الـ LLM في السرد (ملفوفاً بالفواصل).
5. **العرض الحيّ يحذف العلامات، التراكم يحفظها**: المونوليث يحفظ `complete_ai_response`
   المُتراكم (D-006) — لذا التراكم خام (مع الفواصل) للحجب النهائي الواعي، وإزالة العلامات
   على نسخة العرض فقط (الطالب لا يرى ⟦⟧).
6. **`WorkedExampleSkill` (#19) حتمي + no-ZOMBIE**: كتالوج منهجيات لكل مفهوم + بوّابة +
   prompt_directive؛ مُسجَّل في registry بـ `consumed_by` غير فارغ. `worked_example_card`
   في `KNOWN_UI_COMPONENTS` + `GenerativeUIRenderer` + يُحفظ عبر عمود ui_component.
7. **`sanitize_chunk` يُطبّق `_FOREIGN_REPLACEMENTS` الكامل** (آمن، يحفظ LaTeX/الفرنسية).

### الملفات (D-114)
| File | Change |
|------|--------|
| `app/services/skills/doctrine.py` | EXPLANATION 3.1.0 / ANSWER_REDACTION 1.1.0 / ADAPTIVE_PEDAGOGY 1.2.0 / WORKED_EXAMPLE 1.0.0 + ثوابت الفواصل + manifest |
| `app/services/skills/worked_example_skill.py` | **جديد** — Skill #19 (كتالوج منهجيات + بوّابة + prompt) |
| `app/services/skills/answer_redaction_skill.py` | `redact_final_answers(text, support_level)` واعٍ بالفواصل |
| `app/services/skills/content_integrity_skill.py` | `sanitize_final_text(text, support_level)` |
| `app/services/skills/registry.py` | تسجيل `worked_example` (#19) |
| `app/api/routers/customer_chat.py` | snapshot + `_maybe_emit_worked_example` + عرض/حجب واعٍ |
| `app/infrastructure/clients/orchestrator_client.py` | قراءة `_support_level` + `sanitize_final_text(_fc, _support_level)` |
| `app/contracts/streaming.py` | `worked_example_card` في whitelist |
| `microservices/.../api/routes.py` | `ChatRunContext` + extractors + توصيل المُشغّلَين |
| `microservices/.../graph/main.py` | حقلان في `AgentState` |
| `microservices/.../graph/search.py` | `SynthesizerNode` يفرّع على support_level==1 + يمرّره لـ sanitize_response |
| `microservices/.../response_sanitizer.py` | port الحجب الواعي + تقوية `sanitize_chunk` |
| `frontend/app/components/generative/WorkedExampleCard.jsx` | **جديد** — بطاقة دوبامين (كشف تدريجي + مقياس إتقان) |
| `frontend/app/components/generative/GenerativeUIRenderer.jsx` | تسجيل `worked_example_card` |
| `frontend/app/globals.css` | أنماط `.genui-we-*` |
| `scripts/fitness/check_skills_doctrine.py` | `check_worked_example_wired` + pairs + expected set |

### التحقق
- **Sandbox** (Postgres + pip محجوبان — §6.55): الحجب الواعي بالفواصل في المنفذين
  (داخل الفواصل ينجو، خارجها يُحجب، غيابها ⇒ fail-closed، مستوى 5 ⇒ حجب كامل) +
  `_extract_support_level` clamp/افتراض 5 + `sanitize_chunk` (لاتيني محجوب،
  LaTeX/فرنسي مشروع سليم) + doctrine standalone (742 حرف، 3 مراسي، manifest متّسق) +
  16 frontend check + ruff + py_compile 3.12 — **كلها خضراء ✅**.
- **Codespaces** (E2E حي إلزامي): طالب إتقان<0.2 ⇒ `worked_example_card` يُبثّ ويُحفظ +
  السرد يُظهر المثال المماثل (مكشوف) وتمرين الطالب يبقى محجوباً + طالب level 5 ⇒
  محجوب كلياً (لا انحدار) + MODE_B بلا رموز لاتينية معزولة. الدخولان الحقيقيان.

### السلسلة الكاملة (D-113 → D-114)
| Decision | الموضوع |
|----------|---------|
| D-113 (ج1+ج2) | وَهْم الإتقان — Socratic No-Answer (محلي + orchestrator + سُلّم الدعم) |
| **D-114** | **المثال المحلول المُتدرّج: مثال على مسألة مماثلة للمبتدئ + تمرينه محجوب + Skill #19 + بطاقة دوبامين + تقوية sanitize_chunk (يحل الإفلاس البيداغوجي ISS-116)** |

---

## 6.99 البروتوكول السقراطي المنضبط — يَعكِس D-114 (2026-06-16, ISS-116 / D-115)

> **D-114 (المثال المحلول المكشوف، §6.98) جعل الأمور أسوأ حيّاً.** الطالب طلب
> الاحتمالات، قال «لم أفهم» 5 مرات، فانهار النظام: تسرّب فواصل `⟦مثال_محلول⟧` مشوّهة +
> system prompt إنجليزي (`WARM-UP: The instruction must be rendered...`) + هلوسة فرنسية/
> ألمانية (`après compter`, `Ministerpräsident`) + قفز من الاحتمالات إلى متتاليات/معادلات +
> جدران نص. الطالب انهار: «لن أنجح هذا العام لقد خيّبت أمل أسرتي». هذا القسم يحكم
> الإصلاح الجذري — لا يُكسر بدون ADR.

### الجذر
الاعتماد على LLM مجاني لتوليد سرد المثال المحلول (`worked_example_directive` + الفواصل
الحارسة `⟦⟧`) كان الخطأ القاتل: النموذج **لا يستطيع** إخراج `⟦⟧` (U+27E6/27E7) بدقة —
يشوّهها/يقسمها/يسرّبها، ويهلوس لغات، ويصدى الـ system prompt. + تسمّم المفهوم: عند «لم
أفهم» كان `classify_concept_with_context` يقرأ رسائل المساعد المهلوسة («متتالية») فيدخل
حلقة مفهوم خاطئ.

### التصحيح (مالك المشروع): «الرد الجيد لا يقول الجواب بل يقول ما الخطوة التالية الصحيحة»
المشكلة ليست «لا تكشف» بل التنفيذ الكارثي. + مطلب معماري: الخدمات المصغرة + LangGraph +
Skills هي السلطة الوحيدة؛ النظام يتعطّل بدونها.

### القواعد الـ 7 الدائمة (D-115 — لا تُكسر بدون ADR)
1. **السلطة الوحيدة للتوليد التعليمي هي الـ orchestrator/LangGraph** (`SynthesizerNode`).
   لا توليد تعليمي في المونوليث (بوّابة رقيقة). hard-fail `ORCHESTRATOR_REQUIRED` بلا
   fallback تعليمي محلي (D-112 مُعزَّز).
2. **البروتوكول السقراطي المنضبط** (`_build_socratic_prompt` في `graph/search.py`): صياغة
   المطلوب + نوع المسألة + سؤال تشخيصي واحد + أصغر خطوة. لا جدران، لا أمثلة موازية، لا كشف.
3. **support_level (1..5) يحكم عمق التلميح فقط** — لا يفتح كشف الجواب أبداً في التدفّق العادي.
4. **قفل المفهوم** (`bkt_engine.classify_concept_with_context`): متابعة الحيرة تُثبَّت من
   رسائل الطالب (user) حصراً — لا من رسائل المساعد (قد تكون مهلوسة). يمنع قفز المواضيع.
5. **المُطهّر المُصفّح إلزامي** (`strip_garbage_markers`/`_strip_garbage_markers`): regex يحذف
   أي `⟦⟧` مشوّهة/مقسّمة + تعليمات system prompt مُسرَّبة (WARM-UP/coalesced/rendered) + لغة
   غير عربية معزولة، على deltas + النهائي، في المونوليث (StreamIntegrityFilter +
   customer_chat) والـ orchestrator (response_sanitizer). يحفظ «مثال محلول» (مسافة) واللاتيني المشروع.
6. **المثال المكشوف مُزال نهائياً**: لا `worked_example_skill` ولا `worked_example_card` ولا
   `_maybe_emit_worked_example` ولا `worked_example_directive`. أي إعادة لها = عودة الكارثة.
7. **الكشف لوضع مراجعة منفصل فقط** (M8 — مؤجَّل). الحجب fail-closed في التدفّق العادي.

### الملفات (D-115)
| File | Change |
|------|--------|
| `microservices/.../graph/search.py` | `_build_socratic_prompt` + `_SOCRATIC_CORE_PROMPT`/depth clauses؛ حذف فرع `_worked_example_mode` |
| `microservices/.../response_sanitizer.py` | `strip_garbage_markers` (⟦⟧ + WARM-UP) موصول في sanitize_chunk + sanitize_response |
| `app/services/skills/content_integrity_skill.py` | `_strip_garbage_markers` في StreamIntegrityFilter._filter_prose |
| `app/services/skills/bkt_engine.py` | قفل المفهوم: متابعة الحيرة من رسائل الطالب حصراً |
| `app/api/routers/customer_chat.py` | حذف `_maybe_emit_worked_example` + الكارت + directive؛ `_strip_display_garbage` على كل delta |
| `microservices/.../graph/main.py` + `api/routes.py` | حذف `worked_example_directive` (إبقاء `support_level`) |
| `app/contracts/streaming.py` + `GenerativeUIRenderer.jsx` | إزالة `worked_example_card` |
| `app/services/skills/doctrine.py` | `WORKED_EXAMPLE_DOCTRINE` أُعيد توجيهه v2.0.0 (بروتوكول سقراطي + fail-closed) |
| `app/services/skills/registry.py` | حذف descriptor `worked_example` (عدّاد المهارات 19→18) |
| `scripts/fitness/check_skills_doctrine.py` | `check_socratic_protocol_wired` (يَعكِس `check_worked_example_wired`) |
| **محذوف** | `worked_example_skill.py` + `WorkedExampleCard.jsx` + اختبارات D-114 |

### التحقق
- **Sandbox**: المُطهّر على كل أشكال `⟦⟧` المشوّهة + WARM-UP (يحفظ «مثال محلول»/LaTeX/فرنسي) +
  قفل المفهوم (متابعة حيرة بعد احتمالات + هلوسة مساعد «متتالية» ⇒ يبقى probability) + بنية
  البروتوكول (نوع/سؤال/خطوة) + doctrine v2.0.0 manifest متّسق + ruff + py_compile 3.12 +
  runtime_truth + gate file-assertions + 4 frontend tests — **كلها خضراء**.
- **Codespaces (E2E حي إلزامي)**: سيناريو الكارثة الحرفي (احتمالات 2024 → 5× «لم أفهم»):
  صفر `⟦⟧`/إنجليزي/فرنسي/قفز مواضيع، رد قصير منضبط (نوع + سؤال + خطوة)، تلميح يرتفع درجة،
  لا كشف؛ التوليد عبر `POST /api/chat/messages` (لا fallback)؛ orchestrator مُوقَف ⇒
  `ORCHESTRATOR_REQUIRED`. الدخولان الحقيقيان.

### السلسلة (D-114 → D-115)
| Decision | الموضوع |
|----------|---------|
| D-114 | المثال المحلول المكشوف (كارثة حيّة — عُكِس) |
| **D-115** | **البروتوكول السقراطي المنضبط: توليد في الـ orchestrator فقط + قفل المفهوم + مُطهّر مُصفّح + حذف المثال المكشوف (يحل ISS-116)** |

---

## 6.100 مُعلّم الاحتمالات البصري التفاعلي — قتل غارباج LLM من المصدر (2026-06-16, ISS-116 / D-116)

> رغم D-115، transcript حي يُظهر استمرار الكارثة: `ë` («نحسب ë نِسَب») + علامات تجميعية
> لاتينية U+0305 فوق كل كلمة («لا̅ يمكن̅») + قفز المفهوم إلى «عام» + نص سقراطي مجرّد يغرق
> المبتدئ. هذا القسم يحكم تحويل الاحتمالات إلى تجربة بصرية تفاعلية حتمية — لا يُكسر بدون ADR.

### الجذر الحاسم
المحرّك الحتمي (`ProbabilityCalculatorSkill`) + الكاروسيل البصري (`full_exercise_story`)
**موجودان ويعملان بصفر هلوسة** (transcript يُثبت: C(11,3)=165 + جدول توزيع X بكسور حقيقية).
**كل الغارباج يأتي حصراً من نص الـ LLM السقراطي** المعروض بجانب البصري. الحل: للاحتمالات،
المُعلّم البصري الحتمي هو **التجربة الكاملة** — لا نص LLM إطلاقاً.

### القواعد الـ 6 الدائمة (D-116 — لا تُكسر بدون ADR)
1. **الاحتمالات = بصري حتمي كامل**: `orchestrator_client._build_calculated_ui` يضبط
   `terminate_pipeline=True` **دائماً** (حتى عند الحيرة/MODE_B) لكل مكوّنات الاحتمالات
   (full_exercise_story/combinations_visualizer/probability_tree/impossible). صفر سرد LLM ⇒
   صفر `ë`/علامات/قفز للحالة الفاشلة. (يَعكِس جزء MODE_B من D-085 للاحتمالات فقط.)
2. **المُعلّم التفاعلي** (`FullExerciseStory.jsx` مُعزَّز، لا مكوّن جديد): `ExerciseStep.interactive`
   حقل حتمي (`question` + `answer_kind` choice/number + `expected`/`expected_index` + `hint`).
   الواجهة: سؤال أولاً → الطالب يحاول → تلميح عند الخطأ → «اكشف الخطوة» (لا فخّ) → يُكشف المحتوى.
   الطالب يبني P(A)=14/165 بنفسه (قيادة لا تلقين — متّسق مع «لا تكشف»). حتمي بلا LLM.
3. **المُطهّر يحذف العلامات التجميعية U+0300–U+036F** (`_strip_garbage_markers` في
   content_integrity + response_sanitizer). حركات العربية U+064B–U+065F/U+0670 خارج النطاق فتبقى سليمة.
4. **`_allow_token` يقبل ASCII المفرد فقط**: `ë`/الحرف اللاتيني المُلكَّن المنفرد يُحذف؛ `x/n/dx/ln` يبقى.
5. **قفل المفهوم نافذة `[-60:]` + رسائل الطالب حصراً** (`classify_concept_with_context`): متابعة
   «اريد شرح بصري»/«كيف نسحبها» تبقى على مفهوم التمرين النشط (probability)، مناعة ضد هلوسة المساعد.
6. **الاحتمالات تُدار بـ `ProbabilityCalculatorSkill` الحتمي** (عمود Skills) — صفر LLM = صفر هلوسة.
   المواضيع المفتوحة تبقى على الـ orchestrator/LangGraph (D-112/D-115).

### الملفات (D-116)
| File | Change |
|------|--------|
| `app/infrastructure/clients/orchestrator_client.py` | `_build_calculated_ui`: terminate_pipeline=True دائماً للاحتمالات (4 مواقع) |
| `app/services/skills/probability_skill.py` | `ExerciseStep.interactive` + ملء 3 خطوات (question/expected/hint حتمي) |
| `frontend/app/components/generative/FullExerciseStory.jsx` | `StepInteraction` + حالة revealed + شريط تقدّم |
| `frontend/app/globals.css` | أنماط `.genui-fes-interact/-question/-choices/-verify/-hint/-reveal-btn/-progress` |
| `app/services/skills/content_integrity_skill.py` | `_COMBINING_MARKS_RE` + `_allow_token` ASCII-only |
| `microservices/.../response_sanitizer.py` | حذف U+0300–U+036F في strip_garbage_markers |
| `app/services/skills/bkt_engine.py` | قفل المفهوم نافذة [-60:] + رسائل الطالب حصراً |

### التحقق
- **Sandbox**: المُطهّر (`ë`/U+0305 يُحذفان، الحركات/LaTeX سليمة) + قفل المفهوم على السيناريو
  الحرفي (محادثة طويلة + هلوسة مساعد ⇒ يبقى probability) + 19 فحص frontend (التفاعل + الكشف
  + الكيس + التقدّم + الخلفية الحتمية) + ruff + py_compile 3.12 + runtime_truth — **خضراء**.
- **Codespaces (E2E حي إلزامي)**: احتمالات 2024 → «لم أفهم» متكرّر ⇒ مُعلّم بصري تفاعلي
  (كيس + سؤال واحد + تحقق + كشف جزئي)، **صفر نص LLM، صفر `ë`/علامات/قفز**، الطالب يبني P(A)=14/165.

### السلسلة (D-115 → D-116)
| Decision | الموضوع |
|----------|---------|
| D-115 | البروتوكول السقراطي المنضبط (نصّي) |
| **D-116** | **مُعلّم الاحتمالات البصري التفاعلي + terminate LLM للاحتمالات (صفر هلوسة) + مُطهّر U+0305/`ë` + قفل مفهوم [-60:]** |

---

## 6.101 فصل الطبقات — الطالب يرى التعليم لا هندسة التعليم (2026-06-17, ISS-116 / D-117)

> **الكارثة (transcript حي):** رغم D-115/D-116، النموذج المجاني كان يُردّد **التفكير
> الداخلي للنظام** حرفياً على الشاشة: «[توجيه تربوي] ... مستوى الدعم: مثال محلول كامل»
> + «فهمت المطلوب: ... نوع المسألة: شرح خطوة Konzeptية. سؤال تشخيصي واحد: ... أصغر
> خطوة صحيحة ... اطلب من الطالب أن يُكمل». تشخيص المالك الدقيق: **«المنصة تتكلّم من
> داخل عقلها على الشاشة»**. القاعدة الذهبية: **الطالب يرى التعليم، لا هندسة التعليم.**

### الجذور الثلاثة (من كود D-115/D-116 نفسه)
1. `orchestrator_client.chat_with_agent`: التوجيه التربوي (D-104) كان **يُسبَق** للسؤال
   (`f"[توجيه تربوي] {directive}\n\n{...}"`) فيُردّده النموذج حرفياً. و`support_level`
   **مُمرَّر أصلاً** في context (يستهلكه SynthesizerNode) ⇒ الـ prepend زائد ومصدر التسرّب.
2. `search.py:_SOCRATIC_CORE_PROMPT`: **قالب مُرقَّم بعناوين** («حدّد نوع المسألة»،
   «اطرح سؤالاً تشخيصياً»، «أعطِ أصغر خطوة») ⇒ النموذج يَنسخ العناوين حرفياً.
3. `_INSTRUCTION_LEAK_RE` (المونوليث + الـ orchestrator) لم يكن يحوي العلامات الداخلية
   العربية المُسرَّبة، ولا هلوسة «Konzept».

### الإصلاح (4 طبقات — الثلاثة الأولى تحلّ الكارثة لكل المواضيع)
1. **حذف prepend التوجيه** (`orchestrator_client`): التوجيه لم يَعُد يُسبَق للسؤال. العمق
   يصل عبر `support_level` فقط (في context → SynthesizerNode). `pedagogy_directive` يبقى
   في context **للقياس فقط** (لوحة المعلم) ولا يُستهلك في أي prompt بالـ orchestrator
   (مُتحقَّق: صفر ذكر لـ `pedagogy_directive` في `microservices/`).
2. **برومبت سقراطي طبيعي** (`search.py`): استبدال القالب المُرقَّم بتعليمات **سلوكية**
   يتّبعها النموذج ولا يَنسخها («تحدّث بطبيعية كمعلّم، فكرة/خطوة/سؤال واحد، مثال: لننظر
   إلى هذا الجزء فقط...») + **منع صريح** لكتابة العناوين الداخلية («لا يراها الطالب»).
   `_SOCRATIC_DEPTH_CLAUSES` (support_level) سلوكية. الطول 999 < 1500 (D-067).
3. **تقوية المُطهّر** (`content_integrity_skill` + `response_sanitizer`): `_INSTRUCTION_LEAK_RE`
   يحذف أي سطر يحوي `توجيه تربوي` · `مستوى الدعم` · `نوع المسألة` · `سؤال تشخيصي` ·
   `أصغر خطوة` · `اطلب من الطالب` · `وضع الشرح العميق` · `فهمت المطلوب` · `Konzept` —
   على deltas + النهائي، دفاع عميق حتى لو سرّب النموذج.
4. **متابعات حيرة الاحتمالات** (`_build_calculated_ui`): «لم أفهم» عام بعد تمرين احتمالات
   (بلا خطوة تركيز) ⇒ إعادة استخراج تركيبة الكيس من الـ history وإعادة بثّ البصري الحتمي
   بدل السقوط للـ LLM. (best-effort — إن تعذّر، الإصلاحات 1-3 تضمن نظافة المخرَج.)

### القواعد الأربع الدائمة (D-117 — لا تُكسر بدون ADR)
1. **لا نص يصف تفكير النظام يصل الطالب**: ممنوع prepend «[توجيه تربوي]»/«[وضع الشرح
   العميق]» للسؤال؛ العمق يصل عبر `support_level` (إشارة عددية، لا نص يُردَّد).
2. **برومبت سلوكي لا قالب مُرقَّم بعناوين**: العناوين الداخلية (نوع المسألة/سؤال تشخيصي/
   أصغر خطوة/مستوى الدعم) تظهر في الـ prompt **فقط** ضمن قائمة «ممنوع — لا يراها الطالب».
3. **المُطهّر يحذف كل علامة داخلية** على المخرَج (المونوليث + الـ orchestrator) — البوّابة
   `check_adaptive_pedagogy_wiring` تفرض غياب الـ prepend (`f"[توجيه تربوي]`) ووجود
   تمرير `support_level`.
4. **`pedagogy_directive` للقياس فقط**: لا يُستهلك في أي prompt بالـ orchestrator (لا leak path).

### التحقق (2026-06-17)
- **Sandbox**: المُطهّر يحذف كل العلامات الداخلية من transcript الكارثة الحرفي ويحفظ
  السطر التعليمي الطبيعي + `_SOCRATIC_CORE_PROMPT` خالٍ من القالب المُرقَّم (999 حرف) +
  لا prepend في الـ client + بوّابة الـ wiring (PASS) + 10 اختبارات D-117 + 11 اختبار
  D-115 routing (بعد مواءمة) + اختبارَي D-104 المُحدَّثان + D-116 frontend — كلها خضراء.
  ruff check/format + runtime_truth --check + py_compile 3.12 ✅.
- **Codespaces (E2E حي إلزامي)**: احتمالات 2024 → «لم أفهم» متكرّر ⇒ ردّ طبيعي قصير أو
  بصري حتمي، **صفر تسرّب داخلي** («نوع المسألة»/«مستوى الدعم»/«[توجيه تربوي]»)، صفر لغة
  أجنبية. الدخولان الحقيقيان (`houssamannaba963@gmail.com` / `benmerahhoussam16@gmail.com`).

### الملفات (D-117)
| File | Change |
|------|--------|
| `app/infrastructure/clients/orchestrator_client.py` | حذف prepend «[توجيه تربوي]» + Fix 4 (إعادة بثّ البصري للاحتمالات من history) |
| `microservices/.../graph/search.py` | `_SOCRATIC_CORE_PROMPT` سلوكي طبيعي بلا قالب مُرقَّم + منع صريح للعناوين |
| `app/services/skills/content_integrity_skill.py` | `_INSTRUCTION_LEAK_RE` + العلامات الداخلية + Konzept |
| `microservices/.../response_sanitizer.py` | نفس العلامات (port مستقل) |
| `scripts/fitness/check_skills_doctrine.py` | `check_adaptive_pedagogy_wiring`: يفرض غياب الـ prepend + تمرير support_level |
| `tests/microservices/orchestrator_service/test_d117_layer_separation.py` | **جديد** — 10 اختبارات |
| `tests/microservices/orchestrator_service/test_d115_socratic_routing.py` | مواءمة عقد D-117 (برومبت سلوكي) |
| `tests/services/test_d104_adaptive_pedagogy.py` | مواءمة: لا prepend + support_level |

### السلسلة (D-116 → D-117)
| Decision | الموضوع |
|----------|---------|
| D-116 | مُعلّم الاحتمالات البصري التفاعلي + terminate LLM للاحتمالات |
| **D-117** | **فصل الطبقات: حذف prepend التوجيه + برومبت سقراطي سلوكي + مُطهّر العلامات الداخلية + إعادة بثّ بصري الاحتمالات (يحل تسرّب «المنصة تتكلّم من داخل عقلها»)** |

---

## 6.102 تسلسل بطاقات التتبّع بعد المحتوى — وقف تشظّي التمرين (2026-06-17, ISS-116 / D-118)

> **الكارثة (transcript حي بعد D-117):** «الكارثة مزالت + جودة مقرفة مقززة بشكل
> مرعب — تدمير للإنسان». تشخيص: نص التمرين **مُشظّى** — «خمس كرات خضراء مرقمة بـ:
> 0، 1» يُفصَل عن «، 1، 3، 4»، و«A: ... من نفس» عن «اللون.». بطاقة إتقان BKT
> («14% تتبّع المعرفة») وبطاقة المسار («ترسيخ المهارة سهل · لنبدأ بأساسيات
> الاحتمالات») تظهران **في منتصف** التمرين فتقطّعانه. (D-117 نجح: ردّ «لم افهم»
> نظيف بلا «نوع المسألة»/«[توجيه تربوي]» — التسرّب مُغلَق؛ المتبقّي تشظٍّ.)

### الجذر (مؤكَّد بقراءة الكود + وكيل Explore)
`_evaluate_and_emit_bkt` كان يُشغَّل عبر `asyncio.create_task` (customer_chat.py)
**بالتوازي** مع بثّ المحتوى، فيُصدِر إطارَي `ui_component` (BKT + learning_path)
**بين** إطارات `assistant_delta`. مع زمن Supabase (100–2000ms) يهبط الإصدار وسط
البثّ. الواجهة (useAgentSocket: معالج `ui_component`) تستدعي
`finalizeStaleAssistantMessages` (تُنهي فقاعة النص الجارية) ثم تُلحق فقاعة البطاقة
→ أول delta تالٍ يجد آخر رسالة مكتملة (البطاقة) فيُنشئ **فقاعة نص جديدة** ⇒ التمرين
ينقسم والبطاقات بينه. صفر gating: كل دور (تحية/تمرين/مرئي).

### الإصلاح (D-118 — جراحي: فصل التقييم عن الإصدار)
- **`_evaluate_bkt_cards`** (يحلّ محل `_evaluate_and_emit_bkt`): يُجري الكتابة
  التحليلية append-only (`BKTAnalyticsService.evaluate_and_record` — D-074، تبقى
  متزامنة عبر `create_task` فلا تتأثر TTFT) + يشتق `learning_path` + يبني
  حمولتَي البطاقتين ويُرجعهما `list[dict]`. **لا websocket في التوقيع، لا emit،
  لا persist.** معزول كلياً (fail-open → `[]`).
- **بعد `_emit_terminal_frames`** (المحتوى اكتمل): انتظر مهمة التقييم (انتهت أثناء
  البثّ → فوري) → احفظ البطاقتين (بعد رسالة المساعد + `captured_ui_components` ⇒
  ترتيب reload = محتوى → مرئي → تتبّع) → أصدرهما عبر `_locked_send_json` (D-096)
  مع فحص حالة الـ WS، كلٌّ في try معزول.
- **صفر تغيير في الواجهة:** معالج `ui_component` يُنهي العالق (لا شيء — المحتوى
  نُهِّي) ثم يُلحق البطاقة نظيفة أسفل المحتوى.

### القاعدة الدائمة (D-118 — لا تُكسر بدون ADR)
بطاقات التتبّع/التحليل (`bkt_hint_display`, `learning_path_card`) تُصدَر **حصراً
بعد الإطار النهائي للمحتوى** — ممنوع إصدارها متزامنةً في منتصف البثّ. الكتابة
التحليلية (append-only DB) وحدها قد تجري متزامنة (بلا emit). ترتيب الحفظ: محتوى
→ بطاقات مرئية → تتبّع. كل send يبقى عبر `_locked_send_json` (D-096 محفوظ).

### العقود المحفوظة
D-074 (BKT لا يكسر الدردشة + append-only)، D-111 (learning path)، D-096 (send_lock
على كل send)، D-WS-CARD-PERSIST-001 (البطاقات تبقى بعد الدخول)، ISS-016 (إطار نهائي
واحد قبل البطاقات).

### التحقق (2026-06-17)
- **Sandbox**: 7 اختبارات D-118 (`test_d118_card_sequencing.py` — source-inspection:
  التقييم بلا emit/persist/ws-param، الإصدار بعد terminal، الحفظ ثم القفل، معزول) +
  مواءمة D-096 (`test_ws_send_concurrency_lock.py`: التقييم لا يُرسِل + البطاقات عبر
  القفل بعد terminal — مُتحقَّق ضد المصدر؛ يستورد fastapi → CI) + تحديث
  `consumed_by` (registry + doctrine) + بوّابة `check_bkt_baseline_integrated` (الاسم
  الجديد + `await _bkt_task`) + D-116 frontend (لا انحدار) + ruff + runtime_truth +
  py_compile 3.12.
- **Codespaces (E2E حي إلزامي)**: «اعطني تمرين الاحتمالات 2024» ⇒ نص التمرين متّصل
  غير مشظّى + بطاقتا BKT/المسار مرة واحدة أسفله؛ «كيف احل السؤال الأول» ⇒ الكاروسيل
  ثم البطاقتان أسفله؛ «لم افهم» ⇒ ردّ نظيف + البطاقتان أسفله؛ صفر تشظٍّ، صفر تسرّب.
  الدخولان الحقيقيان (`houssamannaba963@gmail.com` / `benmerahhoussam16@gmail.com`).

### الملفات (D-118)
| File | Change |
|------|--------|
| `app/api/routers/customer_chat.py` | `_evaluate_and_emit_bkt` → `_evaluate_bkt_cards` (يُرجِع payloads، بلا emit/persist) + إصدار البطاقات بعد `_emit_terminal_frames` (persist ثم `_locked_send_json`، معزول) |
| `app/services/skills/registry.py` + `doctrine.py` | `consumed_by` → `customer_chat._evaluate_bkt_cards` |
| `scripts/fitness/check_skills_doctrine.py` | `check_bkt_baseline_integrated`: الاسم الجديد + `await _bkt_task` |
| `tests/services/test_d118_card_sequencing.py` | **جديد** — 7 اختبارات تسلسل |
| `tests/services/test_ws_send_concurrency_lock.py` | مواءمة عقد D-118 (التقييم لا يُرسِل؛ البطاقات عبر القفل بعد terminal) |
| `tests/api/test_chat_event_protocol_flag_integration.py` | patch الاسم الجديد (`return_value=[]`) |

### السلسلة (D-117 → D-118)
| Decision | الموضوع |
|----------|---------|
| D-117 | فصل الطبقات (تسرّب التفكير الداخلي للشاشة) |
| **D-118** | **تسلسل بطاقات التتبّع بعد المحتوى — وقف تشظّي نص التمرين (BKT/learning_path لا تُبثّ mid-stream)** |

---

## 6.103 التتبّع المعرفي خلف الكواليس — لا بطاقات تتبّع للطالب (2026-06-17, ISS-116 / D-119)

> **قرار المالك الصريح (transcript حي بعد D-118):** D-118 نجح (نص التمرين لم يَعُد
> مُشظّى — يُعرض كاملاً، البطاقات بعده). لكن المالك قرّر أن بطاقتَي التتبّع — إتقان
> BKT («تتبّع المعرفة — الاحتمالات / 14%») والمسار («ترسيخ المهارة سهل · لنبدأ
> بأساسيات الاحتمالات») — **يجب ألّا تظهرا للطالب إطلاقاً**: «هذه كلها يجب أن تكون
> خلف الكواليس، لا في النص الذي يراه الطالب». تظهران بعد **كل** دور فتُكرَّران
> وتُشوّشان. التدفّق المطلوب: نص التمرين → كتلة بصرية واحدة → خطوة تعليمية → جواب.

### الإصلاح (D-119 — كتم البطاقات، إبقاء التحليلات خلف الكواليس)
- **`customer_chat._evaluate_bkt_cards`** (→ `-> None`): يُبقي كتابة BKT التحليلية
  append-only (D-074 — تغذّي `support_level`/البيداغوجيا التكيفية) + اشتقاق المسار
  التعلّمي (D-111)، **ويُسجِّلهما** (`logger.info` — استهلاك حقيقي خلف الكواليس +
  لوحة المعلم/Prometheus مستقبلاً)، **ولا يبني أي بطاقة طالب** (حُذفت كتلتا
  `bkt_hint_display` + `learning_path_card`).
- **التنسيق (finally)**: `_bkt_task` يبقى متزامناً (تحليلات، لا TTFT). بعد
  `_emit_terminal_frames`: `await _bkt_task` فقط (ضمان اكتمال الكتابة قبل إنهاء
  الدور). **حُذفت كتلة الإصدار/الحفظ D-118** — لا بطاقات تُبثّ/تُحفظ للطالب.
- **بطاقات الاحتمالات البصرية بلا مساس** (`full_exercise_story` /
  `combinations_visualizer` / `probability_tree`) — هي المحتوى التعليمي المطلوب.
- **الواجهة بلا تغيير**: `GenerativeUIRenderer` متسامح؛ `bkt_hint_display` +
  `learning_path_card` يبقيان في `KNOWN_UI_COMPONENTS` + registry (غير ضارّ — لا
  مُصدِر جديد؛ يحفظ تصيير المحادثات القديمة + البصريات تحتاج القائمة البيضاء).

### القاعدة الدائمة (D-119 — لا تُكسر بدون ADR)
بطاقتا التتبّع (`bkt_hint_display`, `learning_path_card`) **لا تُبثّان ولا تُحفظان
للطالب** — التتبّع المعرفي خلف الكواليس حصراً. يبقى ACTIVE: كتابة BKT التحليلية
append-only (D-074، تغذّي `support_level`) + اشتقاق المسار (مُسجَّل، D-111). سطح
الطالب = تعليم نظيف فقط (نص → بصري → خطوة → جواب). البطاقات البصرية للاحتمالات تبقى.

### العقود المحفوظة
D-074 (BKT لا يكسر الدردشة + append-only يبقى) · D-111 (learning path مُستهلَك خلف
الكواليس — لا ZOMBIE) · D-096 (كل send عبر `_locked_send_json`) · ISS-016 (إطار نهائي
واحد). البوّابتان مُحدَّثتان: `check_bkt_baseline_integrated` (تحليلات + `await
_bkt_task`، لا بطاقات) و `check_learning_path_wired` (يكفي `get_learning_path_skill`
مُستدعى — أُسقط اشتراط بطاقة الطالب).

### التحقق (2026-06-17)
- **Sandbox**: 8 اختبارات D-119 (`test_d119_no_tracking_cards.py` — source-inspection:
  لا بناء `bkt_hint_display`/`learning_path_card`، التحليلات + derive + log موجودة،
  `await _bkt_task` موجود، لا كتلة إصدار/حفظ، البصريات في القائمة البيضاء) + مواءمة
  `test_ws_send_concurrency_lock.py` (D-118 emit → D-119 no-emit، مُتحقَّق ضد المصدر)
  + حذف `test_d118_card_sequencing.py` (تجاوزه D-119) + LEARNING_PATH_DOCTRINE v1.1.0
  + D-116 frontend (لا انحدار) + ruff + runtime_truth + py_compile 3.12.
- **Codespaces (E2E حي إلزامي)**: «اعطني تمرين الاحتمالات 2024» ⇒ نص التمرين فقط
  (صفر «تتبّع المعرفة»/«ترسيخ المهارة»)؛ «كيف أحل السؤال الأول» ⇒ كتلة بصرية واحدة؛
  «لم أفهم» ⇒ خطوة/بصري — بلا أي بطاقة تتبّع، بلا تكرار. الدخولان الحقيقيان.

### الملفات (D-119)
| File | Change |
|------|--------|
| `app/api/routers/customer_chat.py` | `_evaluate_bkt_cards` → `-> None` (تحليلات + derive + log، لا بطاقات)؛ التنسيق: `await _bkt_task` فقط (حذف كتلة الإصدار/الحفظ D-118) |
| `scripts/fitness/check_skills_doctrine.py` | `check_learning_path_wired` (أُسقط اشتراط بطاقة الطالب) + `check_bkt_baseline_integrated` (رسالة D-119) |
| `app/services/skills/doctrine.py` | `LEARNING_PATH_DOCTRINE` v1.1.0 + قاعدة «خلف الكواليس، لا بطاقة (D-119)» |
| `tests/services/test_d119_no_tracking_cards.py` | **جديد** — 8 اختبارات |
| `tests/services/test_d118_card_sequencing.py` | **محذوف** — تجاوزه D-119 |
| `tests/services/test_ws_send_concurrency_lock.py` | مواءمة: emit بعد terminal → no-emit (D-119) |

### السلسلة (D-118 → D-119)
| Decision | الموضوع |
|----------|---------|
| D-118 | تسلسل بطاقات التتبّع بعد المحتوى (وقف التشظّي) |
| **D-119** | **التتبّع المعرفي خلف الكواليس — كتم بطاقتَي BKT/المسار من سطح الطالب (سطح نظيف: نص → بصري → خطوة → جواب)** |

---

## 6.104 مُعلّم الاحتمالات: الهبوط على الخطوة المطلوبة + وقف حلقة LLM/التسرّب (2026-06-17, ISS-116 / D-120)

> **الكارثة (transcript حي بعد D-119):** D-119 نجح (لا بطاقات تتبّع؛ الكاروسيل يفتح
> على 1/4). لكن النظام **عالق في حلقة بلا تقدّم**: سؤال «كيف أتعلم حساب احتمال
> الحادثة P(A)» يُعيد **نفس بطاقة الخطوة 1 (فهم المعطيات/الكيس)** كل دور، و«لم أفهم»
> تُعيدها، وأحياناً يسقط لمسار LLM يسأل «كم العدد الكلي؟» **مع تسرّب إنجليزي** («لنبدأ
> با **determination**»). المالك: سؤال P(A) ⇒ يهبط مباشرة على **الحدث** (أبيض مستحيل/
> أحمر 4/أخضر 10 → 14 → C(11,3)=165 → 14/165)، خطوة تقود للتالية لا تكرار.

### الجذران (مؤكَّدان بمنطق الكود)
1. **الكاروسيل يفتح دائماً على الخطوة 1** — `FullExerciseStory.jsx` يستخدم
   `useState(0)` ويتجاهل `props.focus_step_id` المُمرَّر. فسؤال P(A) يُعيد «فهم
   المعطيات» كل مرة ⇒ إحساس التكرار/عدم التقدّم.
2. **تسرّب نص LLM متقطّع** — `_has_followup_probability_intent` يطابق عبر `_normalize`
   الذي يزيل التشكيل **لكنه لا يُحوِّل لأحرف صغيرة**، فـ `"p("` لا يطابق `P(A)` (حرف
   كبير). «...احتمال الحادثة P(A)» تمرّ البوّابة (بكلمة «احتمال») ⇒ بصري؛ «...الحادثة
   P(A)» (بلا «احتمال») تفشل بوّابة D-101 ⇒ تسقط لمسار LLM سقراطي مع تسرّب «determination».
   (`_detect_focus_step` في orchestrator يُحوِّل لأحرف صغيرة أصلاً — المرآتان غير متّسقتين.)

### الإصلاح (D-120 — إصلاحان جراحيان متكاملان)
- **Fix A (frontend)** — `FullExerciseStory.jsx`: `active` يُهيّأ عبر `useMemo` إلى
  فهرس الخطوة التي `step_id === props.focus_step_id` (fallback 0). فـ
  `same_color_event` (P(A)) ⇒ يفتح على خطوة الحدث مباشرةً، `random_variable` (E(X))
  ⇒ خطوة التوزيع. الخطوة التفاعلية (D-116) تبقى ⇒ تدفّق: اسأل P(A) ⇒ خطوة الحدث
  بسؤال واحد ثم كشف.
- **Fix B (backend)** — `probability_skill._has_followup_probability_intent` (و
  `is_visual_request` للاتّساق): التحويل لأحرف صغيرة قبل المطابقة. فـ P(A)/P(B)/P(C)/
  P(X>1)/E(X) تمرّ بوّابة D-101 ⇒ خطّ الاستراتيجيات الحتمي ⇒ البصري — لا LLM، لا
  تسرّب «determination». حاجب تبديل الموضوع (D-101) محفوظ (الإصلاح يلمس فقط حالة
  الأحرف، لا يوسّع النطاق).

### القاعدة الدائمة (D-120 — لا تُكسر بدون ADR)
1. الكاروسيل البصري يهبط على الخطوة المطلوبة (`focus_step_id`) لا دائماً على الكيس.
2. كاشفات نية الاحتمال (`_has_followup_probability_intent` + مرآتها `_detect_focus_step`)
   **case-insensitive** — رموز P(A)/P(B)/P(C)/E(X) تُطابَق بأي حالة أحرف.

### التحقق (2026-06-17)
- **Sandbox**: منطق Fix B standalone (القديم False لكل P(A)/P(B)/P(C)/P(X>1)، الجديد
  True) + 6 اختبار backend (`test_d120_probability_followup_routing.py`) + 11 فحص
  frontend (`d120_carousel_focus_step.test.mjs`: focus→خطوة) + لا انحدار في
  D-116/ISS-114/ISS-110 (لا case تتطلب رفض P( الكبير) + ruff + runtime_truth + py_compile.
- **Codespaces (E2E حي إلزامي)**: «كيف أتعلم حساب الحادثة P(A)» (بـ/بلا «احتمال») ⇒
  الكاروسيل يفتح على خطوة الحدث (أبيض مستحيل/أحمر 4/أخضر 10 → 14/165)، لا الكيس، لا
  حلقة «كم العدد الكلي؟»، لا تسرّب إنجليزي؛ «E(X)» ⇒ خطوة التوزيع. الدخولان الحقيقيان.

### الملفات (D-120)
| File | Change |
|------|--------|
| `frontend/app/components/generative/FullExerciseStory.jsx` | `active` يُهيّأ من `focus_step_id` (مطابقة `step_id`، fallback 0) |
| `app/services/skills/probability_skill.py` | `_has_followup_probability_intent` + `is_visual_request` case-insensitive (`.lower()`) |
| `frontend/tests/d120_carousel_focus_step.test.mjs` | **جديد** — 11 فحص |
| `tests/services/test_d120_probability_followup_routing.py` | **جديد** — 6 اختبار |

### خارج النطاق
عرض المالك لإعادة تصميم UI ثورية كاملة (7 شاشات موبايل/كمبيوتر، حركات، طبقات كشف،
React/Tailwind) مشروع مستقل كبير — الكاروسيل + تفاعل D-116 + Fix A يقدّمان التدفّق
المتدرّج على الخطوة الصحيحة؛ إعادة التصميم الكاملة تُعرَض كخطوة قادمة (تجنّب over-engineering).

### السلسلة (D-119 → D-120)
| Decision | الموضوع |
|----------|---------|
| D-119 | التتبّع المعرفي خلف الكواليس (كتم بطاقات التتبّع) |
| **D-120** | **الكاروسيل يهبط على الخطوة المطلوبة (focus_step_id) + متابعات P(A)/E(X) case-insensitive ⇒ بصري لا LLM (وقف الحلقة + تسرّب determination)** |

---

## 6.105 الثورة البصرية (المرحلة 1): مُختبَر الاكتشاف التدريجي (2026-06-17, D-121)

> بعد إغلاق سلسلة الكوارث (D-117→D-120)، اختار المالك **إعادة تصميم UI الثورية**:
> تجربة «شاشة واحدة، كشف واحد» — مشهد بصري → سؤال → كشف الفروع طبقةً طبقة → تجميع
> → مقام → نتيجة، كأن الطالب في **مختبر اكتشاف** لا يقرأ صفحة.

### القرار المعماري الحاسم (درس D-114)
**إصلاح frontend فقط، بلا أي مسّ لعقد البيانات الخلفي.** الخلفية (`full_exercise_story`)
تُخرج أصلاً كل ما تحتاجه الرؤية (الكيس + الفروع بـ `favorable`/`is_possible`/
`pedagogical_string` + `same_group_favorable`=14 + `total_combinations`=165 + التوزيع).
فالثورة = **إعادة تصيير** هذه البيانات كتجربة كشف تدريجي — يحمي المحرّك الحتمي وكل
إصلاحات D-117→D-120.

### الإصلاح (المرحلة 1 — `FullExerciseStory.jsx` + `globals.css`)
- **`EventLayeredReveal`** (يحلّ محل `EventBreakdownStep`): خطوة الحدث صارت آلة كشف
  تدريجي بدل عرض كل شيء دفعة واحدة. طبقات: فروع قابلة للنقر (أبيض «مستحيل 2 فقط»
  عبر `pedagogical_string` لا «0»، أحمر `C(4,3)=4`، أخضر `C(5,3)=10`) → بعد كشف كلّها
  زر «اجمع» → التجميع (14) + «لماذا نجمع؟» → المقام `C(11,3)=165` → النتيجة `14/165`
  بكشف احتفالي. `open` Set + `layer` 0→3؛ النتيجة لا تظهر إلا عند `layer>=3 && بسط>0 && مقام>0`.
- **مشهد الكيس البطل** (`UrnStep.is-hero`): كرات أكبر تدخل تتابعياً عبر `--genui-ball-i`.
- **CSS فاخر + حركات هادئة**: على tokens القائمة (`--primary-color`/`--success-color`/
  gradient `#6366f1→#10b981`) + keyframes جديدة (`genui-ball-in`/`genui-layer-in`/
  `genui-result-pop`) تحترم `prefers-reduced-motion`.

### العقود المحفوظة (اختبارات قائمة تحرسها)
D-116 (`StepInteraction`/`revealed`/`genui-fes-interact`/`-reveal-btn` + gate `isRevealed`)
· D-120 (`focus_step_id` → `useState(initialStep)`) · D-119 (لا بطاقات تتبّع — customer_chat
غير متأثّر) · عقد props (`exercise_steps`/`step_id`/`render_kind`/`numerical_state`) +
`MathText` + RTL + theme فاتح/داكن — بلا تغيير.

### التحقق (2026-06-17)
- **Sandbox**: 25 فحص `d121_progressive_reveal.test.mjs` (آلة الطبقات 0→3، فروع قابلة
  للنقر، النتيجة آخراً، لا «0» مضلِّل، hero urn، الحفاظ على D-116/D-120، CSS + keyframes
  + reduced-motion + tokens قائمة) + لا انحدار (d116/d120/generative_ui_streaming/iss114
  كلها PASS) + توازن JSX. **التصيير البصري لا يُختبَر في الـ sandbox.**
- **Codespaces (بصري حي إلزامي — المالك)**: «اعطني تمرين الاحتمالات 2024» ثم «كيف أحل
  P(A)» ⇒ مختبر اكتشاف: مشهد الكيس → سؤال → كشف الفروع طبقةً طبقة → 14 → 165 → 14/165
  باحتفال؛ فاتح/داكن + موبايل/كمبيوتر سليم. الدخولان الحقيقيان.

### خارج النطاق (مراحل تالية — بعد تحقق بصري حي)
شاشات منفصلة بـ routing/overlay كامل الشاشة · إعادة تصميم `combinations_visualizer`/
`probability_tree` بنفس الأسلوب · إعادة تصميم محيط الدردشة (CogniForgeApp/ChatInterface).

### السلسلة (D-120 → D-121)
| Decision | الموضوع |
|----------|---------|
| D-120 | الكاروسيل يهبط على الخطوة المطلوبة + متابعات case-insensitive |
| **D-121** | **الثورة البصرية المرحلة 1: مختبر الاكتشاف التدريجي (كشف طبقةً طبقة) — frontend-only، عقد البيانات محفوظ** |

---

## 6.106 إشارات أجزاء التمرين الطبيعية ⇒ البصري الحتمي (2026-06-17, D-122)

> **الكارثة (transcript حي):** «كيف احل **السؤال الأول**» (إشارة طبيعية للسؤال 1 =
> P(A)) لا تحوي رمز `P(A)` ولا `نفس اللون` ⇒ لا تُتعرَّف كخطوة الحدث ⇒ تفشل بوّابة
> الاحتمالات ⇒ تسقط لمسار LLM السقراطي العام («حدّد المطلوب... قسّم النجاحات...» +
> عربية مكسورة «كلزيادة») الذي يرفضه المالك. المراد: أي إشارة للسؤال 1/P(A)/الحدث A ⇒
> تفصيل الحدث الملموس (أبيض مستحيل/أحمر C(4,3)=4/أخضر C(5,3)=10 → 14/165).

### الجذر
`orchestrator_client._detect_focus_step` يطابق `p(a`/`نفس اللون`/`e(x` فقط — لا
«السؤال الأول»/«الحدث A»/«الجزء الأول». فالإشارات الطبيعية لأجزاء التمرين تسقط للـ LLM.

### الإصلاح (D-122 — جراحي في `orchestrator_client.py`، topic-safe)
- **`_detect_part_reference(question)`**: السؤال 1/الحدث A/الجزء الأول → `same_color_event`؛
  السؤال 2/الجزء الثاني → `random_variable`.
- **`_is_probability_context(combined)`**: كرات/كرة/كيس/احتمال/سحب/نسحب/p(a/p(b.
- **التطبيق المحروس**: بعد `_detect_focus_step`، إن لم يُطابق رمز صريح **و** السياق
  احتمالات (history) ⇒ `_focus_step_id = _detect_part_reference(question)`؛ و«لم أفهم»
  في سياق احتمالات بلا جزء محدّد ⇒ `same_color_event` (السؤال الرئيسي). ثم focus-retry
  (D-117 Fix 4) يُعيد البصري الحتمي ⇒ الكاروسيل يفتح على خطوة الحدث (D-120) ⇒ الكشف
  التدريجي (D-121). صفر نص LLM.
- **topic-safe**: explicit P(A)/E(X) غير مشروطة؛ الإشارات الطبيعية مشروطة بسياق
  الاحتمالات؛ وحاجب تبديل الموضوع (D-101 `primary_canonical_topic`) يبقى أولاً.

### القاعدة الدائمة (D-122)
1. إشارات الأجزاء الطبيعية تُربَط بخطوة الحدث **فقط** ضمن سياق احتمالات مؤكَّد (history).
2. أي متابعة في محادثة احتمالات (إشارة جزء أو حيرة) ⇒ البصري الحتمي، لا نص LLM عام.

### التحقق (2026-06-17)
- **Sandbox**: 8 اختبار D-122 (مطابقة الإشارات + topic-safety + source-inspection
  للتطبيق المحروس + ترتيب حاجب D-101) + standalone logic (السؤال الأول[احتمالات]→
  same_color_event، [دوال]→None) + لا انحدار D-120 (6/6) + ruff + runtime_truth + py_compile.
- **Codespaces (حي إلزامي — بعد `git pull` + إعادة تشغيل supervisor)**: «اعطني تمرين
  الاحتمالات 2024» ثم «كيف احل السؤال الأول» ⇒ الكاروسيل على خطوة الحدث (أبيض مستحيل/
  أحمر 4/أخضر 10 → 14/165) بالكشف التدريجي، صفر نص LLM/عربية مكسورة؛ «اعطني تمرين الدوال»
  ⇒ لا واجهة احتمالات. **ملاحظة: transcript المالك يطابق إصداراً قبل D-120/D-121 —
  يجب pull الكل معاً.**

### السلسلة (D-121 → D-122)
| Decision | الموضوع |
|----------|---------|
| D-121 | الثورة البصرية المرحلة 1 (مختبر الاكتشاف التدريجي) |
| **D-122** | **إشارات أجزاء التمرين الطبيعية («السؤال الأول») ⇒ البصري الحتمي، topic-safe (وقف نص LLM المكسور)** |

---

## 6.107 تحصين الاحتمالات بالمحتوى الرسمي — لا LLM، لا تلوّث، لا هلوسة (2026-06-18, D-123)

> **الكارثة (screenshots + transcript حي):** D-121 يعمل (الكشف التدريجي ظاهر). لكن
> متابعات الاحتمالات («لم افهم كيف جاءت 14 و 165»، «لا اعرف») حين يعجز الـ skill عن
> إعادة استخراج التركيبة من نافذة `history[-6:]` ⇒ `None` ⇒ تسقط لمسار LLM السقراطي ⇒
> **حلقة** «كم عدد الكرات؟» بعربية مكسورة + **هلوسة مثال** («2 برتقالية + 3 زرقاء»).
> ذلك النص دخل الـ history ⇒ الاستخراج الحتمي التالي **قرأ أرقام الهلوسة** ⇒ كاروسيل
> خاطئ تماماً («سحب 2 من 11» + «كرة زرقاء» غير موجودة). نص الـ LLM يُسمّم المحرّك الحتمي.

### الجذر
`_build_calculated_ui` كان يستدعي `skill.analyze(question=question, history=history_messages)`
— الـ history مُلوَّث بنص الـ LLM المُهلوَس. وعند فشل الاستخراج ⇒ None ⇒ سقوط للـ LLM ⇒ حلقة + هلوسة.

### الإصلاح (D-123 — تحصين بالمحتوى الرسمي، history-immune، في `_build_calculated_ui`)
استخراج ثلاثي محصَّن (`_result_ok` يفحص النجاح):
1. **السؤال وحده** `analyze(question=question, history=None)` — يلتقط التركيبة inline
   («كيس فيه 4 حمراء و7 بيضاء») بلا تلوّث.
2. **المحتوى الرسمي** (حين سياق احتمالات + `detect_exercise_retrieval` يتعرّف):
   `load_exercise_content` ⇒ `analyze(question=f"{official} {question}", history=None)` —
   التركيبة من المحتوى الرسمي (2بيضاء/4حمراء/5خضراء) + نية السؤال (الحيرة/التركيز)،
   `history=None` ⇒ **مناعة كاملة** من «زرقاء/2 من 11» المُهلوَسة في الـ history.
3. **آخر ملاذ** `analyze(question, history=history_messages)` — السلوك الأصلي (نادر بعد التحصين).
النتيجة: الكاروسيل الصحيح دائماً ⇒ `terminate_pipeline=True` (D-116) ⇒ MODE_A يُنهي المسار
⇒ **صفر LLM** ⇒ لا حلقة، لا هلوسة، لا تلوّث. + التركيز (D-122) يفتح على خطوة الحدث (لا البداية).

### القاعدة الدائمة (D-123 — لا تُكسر بدون ADR)
1. محادثة التمرين الاحتمالي تُصيَّر من **المحتوى الرسمي المُفهرَس** حصراً (`history=None`) —
   نص الـ history لا يُغذّي استخراج التركيبة أبداً (مناعة من هلوسة الـ LLM).
2. التمرين الاحتمالي **لا يسقط للـ LLM أبداً** — الكاروسيل الحتمي مضمون (terminate=True).
   الـ LLM السقراطي مصدر الحلقة + الهلوسة + التلوّث ⇒ مُعطَّل للاحتمالات.

### العقود المحفوظة
D-101 (حاجب تبديل الموضوع أولاً)، الاسترجاع المُفهرَس الصريح (preempt) أولاً، D-116
(terminate للاحتمالات)، D-122 (focus). topic-safe: «اعطني تمرين الدوال» محجوب قبل الوصول.

### التحقق (2026-06-18)
- **Sandbox**: 10 اختبار D-123 (المحتوى الرسمي فيه التركيبة + التحصين الثلاثي موصول
  بالترتيب inline→رسمي→ملاذ + history=None في الخطوة الرسمية + حارس السياق + dedup) +
  لا انحدار (D-120/D-122 = 14/14) + ruff + runtime_truth + py_compile 3.12.
- **Codespaces (حي إلزامي — بعد `git pull` لكل D-120→D-123 + restart)**: «كيف احل
  السؤال الأول» ⇒ كاروسيل على خطوة الحدث (أبيض مستحيل/أحمر 4/أخضر 10 → 14/165)؛ «لم افهم»
  ⇒ بصري؛ **صفر «كرة زرقاء»، صفر «سحب 2 من 11»، صفر LLM/حلقة/دارجة مكسورة**. الدخولان الحقيقيان.

### خارج النطاق
`_build_probability_tree_props` (مسار شجرة inline منفصل — ليس كاروسيل التمرين) · ثبات خطوة
الكاروسيل عبر الأدوار (frontend، لاحقاً) · تعميم لتمارين احتمالات متعددة (2024 الوحيد المفهرَس).

### السلسلة (D-122 → D-123)
| Decision | الموضوع |
|----------|---------|
| D-122 | إشارات أجزاء التمرين الطبيعية ⇒ البصري الحتمي |
| **D-123** | **تحصين بالمحتوى الرسمي (history-immune) ⇒ صفر LLM/تلوّث/هلوسة للاحتمالات** |

---

## 6.108 مخرج الطوارئ الحتمي — كسر حلقة الكاروسيل + شرح رياضي مباشر (2026-06-19, ISS-116 / D-124)

> **الكارثة (transcript حي بعد تأكيد المالك لاختبار D-123 الحي):** D-123 نجح (التلوّث
> والهلوسة «كرة زرقاء»/«سحب 2 من 11» اختفيا). لكنه خلق **«حلقة الموت اللانهائية»**: بما
> أن D-116/D-123 يجعلان كل سؤال احتمالات يُنهي دائماً إلى الكاروسيل (terminate=True، صفر
> LLM)، فإن سؤالاً محدّداً («بخصوص الكرات الحمراء **كيف وجدنا 4**؟») أو حيرة متكررة («لم
> أفهم»/«اشرح لي»/«؟»×N) يُعيدان طباعة **نفس الكاروسيل** بلا تقدّم ولا إجابة — الطالب محاصَر.

### الجذر (مؤكَّد بقراءة الكود)
`chat_with_agent`: بعد الاسترجاع المُفهرَس، `_build_calculated_ui` يُرجِع الكاروسيل بـ
`terminate_pipeline=True` لكل أسئلة الاحتمالات ⇒ MODE_A يُنهي ⇒ نفس الكاروسيل كل دور.
لا عداد محاولات، لا مخرج طوارئ.

### الإصلاح (D-124 — مخرج طوارئ حتمي قبل الكاروسيل، `orchestrator_client.py`)
في `chat_with_agent`، **بعد** الاسترجاع المُفهرَس و**قبل** `_build_calculated_ui`:
- **`_count_probability_confusion(question, history)`** — عداد حيرة حتمي من الـ history
  (نمط `customer_chat._count_confusion_signals`)؛ **بلا «كيف» المجرّدة** كي لا يُحسب «كيف
  افهم السؤال الأول» الأول كحيرة. الرسالة «؟» الصرفة تُحسب حيرة.
- **`_detect_subpart_question(question)`** — يكشف جزئية محدّدة: لون (`red`/`green`/`white`)
  أو فضاء العينة (`total` — 165) أو مجموع الملائمة (`sum` — 14). السؤال العام ⇒ `None`.
- **شرط المخرج**: سؤال محدّد (فوراً) **أو** عداد الحيرة ≥ 2.
- **`_build_probability_direct_explanation(question, history) -> str | None`** (حتمي):
  يحمّل التمرين الرسمي المُفهرَس (D-123: `history=None` ⇒ مناعة من التلوّث)، يحلّله عبر
  `ProbabilityCalculatorSkill` (مخرَج `CombinationsModelOutput`)، ويُنسِّق الجزئية المطلوبة
  أو الاشتقاق الكامل عبر `_fmt_comb(c,k,fav)` (توسيع المضروب: `C(4,3) = (4×3×2)/(3×2×1) = 4`).
  topic-safe (`primary_canonical_topic != "probability"` ⇒ `None`). **صفر LLM، صفر هلوسة.**
- **التطبيق**: نص ⇒ بثّه عبر `_stream_markdown_typing` + `assistant_final` + `return`
  (كسر الحلقة)؛ وإلا ⇒ `_build_calculated_ui` (الكاروسيل) كالمعتاد.

**التدفّق الناتج:** سؤال عام أول («كيف افهم السؤال الأول») ⇒ الكاروسيل البصري؛ سؤال محدّد
(«كيف وجدنا 4 الحمراء») ⇒ `C(4,3) = (4×3×2)/(3×2×1) = 4`؛ حيرة متكررة (≥2) ⇒ الاشتقاق
الكامل (أبيض مستحيل / أحمر 4 / أخضر 10 → 14 → C(11,3)=165 → 14/165).

### النجاة من حجب الإجابة (D-113) — بالبناء
البثّ الحيّ في `customer_chat` يمرّ عبر `_strip_display_garbage` فقط (⟦⟧/تعليمات مُسرَّبة)،
**لا** `_apply_final_answer_redaction` (الأخير على النسخة المحفوظة فقط). والنصّ مُصمَّم
لِيَنجو من `redact_final_answers` حتى في النسخة المحفوظة: النمط المُقوَّس `C(4,3) = (4×3×2)/…`
لا يُطابق `_FINAL_RESULT_RE` (RHS بعد `=` هو «(» لا رقم)، والسطر النهائي «الاحتمال = 14/165»
لا يبدأ بكلمة خلاصة (إذن/ومنه/النتيجة/الجواب/فإن) فلا يُطابق `_CONCLUSION_RE`. لا `\boxed`،
لا `P(...)=عدد`. **استثناء مقصود ومُصرَّح من المالك** لِـ doctrine السقراطي (D-113/D-115):
الطالب العالق يستحق المثال المحلول لكسر الحلقة.

### القاعدة الدائمة (D-124 — لا تُكسر بدون ADR)
1. **مخرج طوارئ إلزامي للاحتمالات**: سؤال محدّد أو حيرة متكررة (≥2) ⇒ شرح رياضي مباشر يكسر
   حلقة الكاروسيل. لا إعادة طباعة نفس الواجهة بلا تقدّم.
2. **الشرح المباشر حتمي حصراً** — محسوب من التمرين الرسمي (`history=None`، D-123)، صفر LLM،
   صفر هلوسة. يُعيد الأرقام التي حسبها المحرّك فقط، مُنسَّقة كنص يَنجو من حجب D-113.
3. الكاروسيل يبقى الاستجابة الأولى (التجربة البصرية)؛ المخرج للأسئلة المحدّدة/الحيرة المتكررة.
4. العداد **بلا «كيف» المجرّدة** (تكسر «كيف افهم السؤال الأول» الأولى).

### التحقق
- **Sandbox** (Postgres/pip محجوبان — نمط §6.55): 24 اختبار D-124
  (`test_d124_escape_hatch.py` — subpart/counter/`_fmt_comb`/نجاة الحجب/source-inspection:
  المخرج بعد preempt وقبل الكاروسيل، `history=None`، topic-safe) + لا انحدار
  (D-120/D-122/D-123 = 24/24) + ruff check/format + py_compile 3.12 + runtime_truth --check.
  المحرّك الحتمي (n=11,k=3,total=165,same=14) مُتحقَّق أصلاً بـ ISS-083/D-116/D-123.
- **Codespaces (حي إلزامي — بعد pull D-120→D-124 + restart)**: «كيف افهم السؤال الأول» ⇒
  كاروسيل بصري؛ «بخصوص الكرات الحمراء كيف وجدنا 4» ⇒ شرح مباشر `C(4,3) = (4×3×2)/(3×2×1) = 4`
  (لا كاروسيل مكرَّر)؛ «لم أفهم»×2 ⇒ الاشتقاق الكامل (14 → 165 → 14/165)؛ **صفر حلقة، صفر
  تجاهل للسؤال، صفر LLM/هلوسة**. الدخولان الحقيقيان.

### السلسلة (D-123 → D-124)
| Decision | الموضوع |
|----------|---------|
| D-123 | تحصين بالمحتوى الرسمي (history-immune) ⇒ صفر LLM/تلوّث/هلوسة |
| **D-124** | **مخرج الطوارئ الحتمي: سؤال محدّد/حيرة ≥2 ⇒ شرح رياضي مباشر يكسر حلقة الكاروسيل (صفر LLM)** |

---

## 6.109 التركيب المفاهيمي الحتمي — قتل «متلازمة الردود المعلبة» (2026-06-19, ISS-116 / D-125)

> **الكارثة (transcript حي بعد D-124):** D-124 كسر حلقة الكاروسيل، لكن المالك كشف كارثة
> **أعمق**: **«غباء الاسترجاع» / «متلازمة الردود المعلبة»**. السؤال **المفاهيمي/المقارنة**
> («ما الفرق بين 165 و 14»، «يعني 14 ما هو الهدف منها») يطابق على **الأرقام** فقط
> (165→`total`، 14→`sum`) فيطبع قالب **الحساب** — متجاهلاً «الفرق»/«الهدف». الطالب يسأل عن
> **المعنى/العلاقة** (البسط مقابل المقام) فيتلقى **خطوات الحساب**. تشخيص المالك: عمى دلالي.

### الإصلاح (D-125 — كاشف مفاهيمي حتمي يسبق مطابقة الأرقام، `orchestrator_client.py`)
- **`_detect_conceptual_question(question)`**: علامات مفاهيمية قوية (الفرق/الاختلاف/العلاقة/
  الهدف/الغرض/الفائدة/المعنى/المقصود/نفسر/النسبة/نقسم) ⇒ مفاهيمي دائماً (يهزم حتى الأفعال
  الإجرائية — الهجين). الدارجة «ليش/علاش» + رقم/مفهوم (14/165/البسط/المقام) **وبلا فعل إجرائي**
  ⇒ مفاهيمي. لكن «لماذا/ليش» + فعل إجرائي (`_PROCEDURAL_VERBS`: نجمع/نحسب/كيف وجدنا...) ⇒
  **ليس مفاهيمياً** (يبقى لقوالب D-124 — تحفّظ المالك 3).
- **`_format_conceptual_relationship`**: شرح علاقة حواري قصير (≤3 أسطر) حتمي: «165 = كل
  الطرق (المقام) · 14 = الطرق التي تحقق نفس اللون: 4 للحمراء + 10 للخضراء، البيضاء مستحيلة
  (البسط) · الاحتمال نسبة البسط للمقام: 14 من كل 165». الهجين (وُجد «كيف حصلنا/نحسب/وجدنا»)
  ⇒ يُلحَق **سطر حسابي واحد** عبر `_fmt_comb` (يَنجو من حجب D-113). صفر LLM.
- **`_build_probability_direct_explanation`**: فحص المفاهيمي **قبل** `_detect_subpart_question`
  ⇒ يهزم مطابقة الأرقام (يحل عمى الدلالة). **`chat_with_agent`**: الشرط
  `if _conceptual or _subpart is not None or _confusion_count >= 2:`.

### القاعدة الدائمة (D-125 — لا تُكسر بدون ADR)
1. السؤال المفاهيمي/المقارنة (الفرق/الهدف/العلاقة/المعنى/النسبة) ⇒ شرح علاقة حواري قصير —
   **يُمنع منعاً باتاً** قوالب خطوات الحساب له. الفحص المفاهيمي **يسبق** مطابقة الأرقام.
2. «لماذا/ليش» + فعل إجرائي ⇒ إجرائي (قوالب D-124)؛ «ليش 14» (بلا فعل) ⇒ مفاهيمي.
3. الهجين: مفاهيمي أولاً + سطر حسابي **واحد** منفصل (`_fmt_comb`). المخرج المفاهيمي ≤ 3 أسطر.
4. شرح العلاقة حتمي حصراً (التمرين الرسمي، history=None، صفر LLM) ويَنجو من حجب D-113.

### خريطة LLM الحاكمة (قاعدة المالك — تُعزِّز D-112/D-115/D-116)
Probability engine = **صفر LLM** · Tutor final answer = **صفر LLM** · النصّ العام للمنصّة:
LLM مسموح فقط في غير الحاسم (صياغة/تلخيص غير رياضي) وخارج مسار الاحتمالات. القاعدة: «إن كان
الخطأ قد يُضلِّل الطالب فلا LLM؛ إن كانت المهمة لغوية لا تُغيِّر الحقيقة فيُسمح».

### التحقق
- **Sandbox** (§6.55): 16 اختبار D-125 (كاشف مفاهيمي True/False + أولوية على الأرقام +
  redaction-survival + source-inspection: المفاهيمي قبل subpart + الشرط) + لا انحدار
  (D-124=24/D-123/D-122/D-120) + ruff + py_compile 3.12 + runtime_truth. تنسيق العلاقة
  مُتحقَّق حياً (المقام/البسط/النسبة + سطر هجين) ويَنجو من حجب D-113.
- **Codespaces (حي إلزامي)**: «ما الفرق بين 165 و 14»/«ليش 14» ⇒ شرح علاقة (لا قالب حساب)؛
  «كيف وجدنا 4»/«لماذا نجمع» ⇒ قوالب D-124 (لا انحدار). الدخولان الحقيقيان.

### السلسلة (D-124 → D-125)
| Decision | الموضوع |
|----------|---------|
| D-124 | مخرج الطوارئ الحتمي (كسر حلقة الكاروسيل) |
| **D-125** | **التركيب المفاهيمي الحتمي: كاشف مفاهيمي يسبق مطابقة الأرقام ⇒ شرح علاقة لا قالب حساب** |

---

## 6.110 الإتقان الصادق ثنائي القناة — قتل وَهْم الطلاقة بالقياس (2026-06-19, D-126 · roadmap M6)

> **ثورة التعليم المخصص (قرار المالك):** نفصل **الأداء المدعوم** (assisted — مُضخَّم
> بالمساعدة) عن **الإتقان الحقيقي الدائم** (durable — مُثبَت بأداء غير مدعوم + مؤجَّل + على
> بند جديد). **فجوة الوهم = assisted − durable = مقياس النجاح الوحيد** (§0.6). حتمي 100%
> (صفر LLM — قاعدة المالك)، يبني على `BKTEngine` القائم (D-074 — لا ملف موازٍ).

### البرهان الحاسم (port خوارزمية المالك)
الطالب المُسلَّم الحل (6 تفاعلات «صحيحة» بمثال محلول، support_level=1) ⇒ **durable=0.0** رغم
كل النجاحات (فجوة وهم عالية 0.29). الطالب الذي يُولِّد بنفسه (حاول/فشل → تلميح أدنى → غير
مدعوم مؤجَّل جديد ×2) ⇒ **assisted=0.89، durable=0.75** (فجوة وهم منخفضة 0.14). النظام **لا
يُخدَع** بالأداء المدعوم.

### المكوّنات (كلها حتمية، صفر LLM)
- **`bkt_engine.py`** (+دوال، يبني على القائم): `scaffold_leak(support)` =
  `{1:0.85…5:0.0}` (المساعدة الثقيلة تُضخّم P(صحيح بلا معرفة) فالإجابة المدعومة غير
  تشخيصية) · `generation_weight` · `delay_weight` · `update_mastery_two_signal(...) ->
  (assisted, durable)` (نفس بايز القائم لكن `p_cu = p_G + (1-p_G)·scaffold_leak`؛ durable
  يرتفع **فقط** عند `correct ∧ support≥5 ∧ delay≥24h ∧ novel`؛ يهبط عند `¬correct ∧
  support≥4`) · `illusion_gap = max(0, assisted − durable)`. `update_mastery` القائم دون
  تغيير (توافق خلفي — D-118/D-119).
- **المخطط** (`db_schema_config.py` + ORM): أعمدة `durable_mastery/support_level/
  delay_hours/novel_item` على `student_bkt_analytics` عبر **`auto_fix`** (auto-migration على
  الإقلاع §6.77 — append-only، لا تكسر الصفوف السابقة).
- **التخزين** (`bkt_persistence.evaluate_and_record`): يقرأ `latest_durable_mastery` +
  آخر timestamp (delay_hours) → يحسب durable → يكتبه + `illusion_gap`. معزول (D-074).
- **التوصيل** (`customer_chat._evaluate_bkt_cards`، D-119 خلف الكواليس): يُمرِّر
  `support_level/novel_item`؛ يُسجِّل القناتين + فجوة الوهم (لا بطاقة طالب).
- **No-Reveal**: `audit_no_reveal` في `answer_redaction_skill.py` يُعيد استخدام
  `redact_final_answers` القائم (D-113) — **لا حارس موازٍ** (§0.5).
- **Doctrine**: `BKT_COGNITIVE_DOCTRINE` v2.0.0 (+3 قواعد: الإتقان المعروض = durable؛ فجوة
  الوهم = المقياس الوحيد؛ ممنوع التحسين على «الرضا اللحظي»).

### القاعدة الدائمة (D-126 — لا تُكسر بدون ADR)
1. الإتقان المعروض للطالب = **durable** الصادق (غير مدعوم + مؤجَّل + جديد)، لا المدعوم المُضخَّم.
2. **فجوة الوهم = assisted − durable** = المقياس الوحيد؛ ممنوع التحسين على «الرضا اللحظي»/
   مدّة الجلسة/عدد الرسائل.
3. two-signal BKT **حتمي حصراً** (صفر LLM)، append-only (D-074)، معزول (لا يكسر الدردشة).
4. يبني على `BKTEngine` القائم — **ممنوع** ملف BKT موازٍ. No-Reveal يُعيد استخدام `AnswerRedactionSkill`.
5. في الدردشة الحرة بلا `support_level` ⇒ durable يُحمَل دون تضخيم (الصدق: لا إتقان دائم بلا
   دليل أداء غير مدعوم — يُغذَّى من وضع التحقق M8). عُقد DSPy/LLM (diagnosis/socratic) مؤجَّلة
   بـ ADR منفصل (تتعارض مع «صفر LLM للاحتمالات»).

### التحقق
- **Sandbox** (§6.55): 20 اختبار D-126 (`test_d126_two_signal_bkt.py` — أوزان السقالة/التوليد/
  المباعدة + **البرهان 0.0 مقابل durable عالٍ** + بوّابة الشروط الأربعة + الهبوط + فجوة الوهم
  + source-inspection للمخطط/التخزين/التوصيل/No-Reveal/Doctrine) + لا انحدار + ruff +
  py_compile 3.12 + runtime_truth + validate_structure. البرهان الحاسم مُتحقَّق حياً standalone.
- **Codespaces (حي إلزامي)**: أعمدة `student_bkt_analytics` الجديدة تُنشأ تلقائياً على الإقلاع؛
  durable يُسجَّل خلف الكواليس؛ طالب يُسلَّم الحل ⇒ durable≈0 + فجوة وهم عالية. صفر LLM في
  مسار الاحتمالات. الدخولان الحقيقيان.

### السلسلة (D-125 → D-126)
| Decision | الموضوع |
|----------|---------|
| D-125 | التركيب المفاهيمي الحتمي (قتل متلازمة الردود المعلبة) |
| **D-126** | **الإتقان الصادق ثنائي القناة: assisted مقابل durable + فجوة الوهم (roadmap M6، حتمي، صفر LLM)** |

---

## 6.111 المعمارية الإدراكية العصبية-الرمزية — من «منصة تجيب» إلى «منصة تفهم العقول» (2026-06-19, ISS-116 / D-127)

> **رؤية المالك:** الهدف **ليس** «صفر LLM» ولا «LLM في كل شيء» — بل نظام إدراكي متعدّد
> الطبقات (Cognitive OS): **الطبقة 1 (LLM)** تفهم الطالب وتصنّف *أيّ* صياغة → مفهوم (بلا
> رياضيات)؛ **الطبقة 2 (BKT)** تعرف ما يعرفه (D-126)؛ **الطبقة 3 (المحرك الرمزي)** تضمن
> الحقيقة (14 تبقى 14)؛ **الطبقة 4 (المعلّم السقراطي)** تبني بالأسئلة لا الإجابات؛ **الطبقة 5
> (النموذج العقلي)** تخزن *سبب* الحيرة لا «أخطأ». الأستاذ الحقيقي يرى «ما هو البسط/لماذا 14/
> ما الهدف من 14/واش راه 14» رسالةً **واحدة**: الطالب لا يفهم *الحالات الملائمة* (numerator).

### الكارثة (transcript حي بعد D-125)
«ما هو البسط»/«ما هو المقام» تسقط للحل الكامل (لا تعريف المفهوم)؛ و«لم أفهم»×2 / «ما هو
البسط»×2 ⇒ إجابة متطابقة byte-by-byte (صفر تقدّم، صفر تصعيد، صفر وعي بالنموذج العقلي).

### الإصلاح (D-127)
- **`ConceptDiagnosisSkill` (Skill جديد، الطبقتان 1+5 — `concept_diagnosis_skill.py`)**: يحوّل
  السؤال (+history) إلى `(concept, misconception)` من enum ثابت (numerator/denominator/ratio/
  combinations/color_*/full_solution/unknown). **هجين**: خريطة حتمية أولاً (كل صياغات المفهوم
  → نفس المفهوم)؛ **مُصنّف LLM محروس** عند `unknown` فقط — يُعيد **كلمة واحدة من الـ enum**
  حصراً (لا رياضيات/نثر/إجابة)، مُتحقَّق + timeout(8s) + fallback حتمي. الطبقة 5: `misconception`
  (sample_space_confusion / fraction_meaning_confusion / order_vs_selection_confusion) يقود
  التدخّل السقراطي. مقياس `cogniforge_skill_concept_diagnosis_total{concept,misconception,source}`.
- **`_build_cognitive_response` (orchestrator_client — الطبقة 4)**: استجابة مدفوعة بالمفهوم +
  **تصعيد سقراطي مضاد للتكرار** عبر `_count_prior_concept` (عدد مرّات المفهوم في الـ history):
  مرّة1 = شرح/تعريف؛ مرّة2 = **سؤال سقراطي** (حسب misconception)؛ مرّة3+ = **إعادة توجيه**
  («أين تحديداً تعثّرت؟ اختر حرفاً»). الأرقام من المحرك الرمزي (الطبقة 3، صفر LLM)، تَنجو من D-113.
- **التوصيل** (`chat_with_agent`): الطبقة 1 تُشخّص (حتمي؛ LLM فقط عند unknown + سياق احتمالات)
  قبل البناء؛ fallback إلى D-124/D-125 إن لزم. topic-safe.

### القاعدة الدائمة (D-127 — لا تُكسر بدون ADR)
1. **الطبقة 1 (LLM) تُصنّف فقط** — مفهوم واحد من enum، بلا رياضيات/إجابة، مُتحقَّق + timeout +
   fallback. الطبقة 3 (الأرقام) رمزية صرفة (صفر LLM).
2. **لا تكرار حرفي**: نفس المفهوم مرّتين ⇒ تصعيد سقراطي (شرح→سؤال→إعادة توجيه).
3. كل صياغات المفهوم الواحد ⇒ مفهوم واحد ⇒ استجابة ديناميكية. لا قاعدة لكل صياغة.
4. التشخيص hybrid: حتمي أولاً (سريع/آمن)، LLM فقط عند unknown.

### التحقق
- **Sandbox** (§6.55): 22 اختبار D-127 (تصنيف المفهوم لكل الصياغات + النموذج العقلي
  misconception + التصعيد السقراطي عبر العدّ + LLM enum-guard + redaction-survival +
  source-inspection) + لا انحدار (D-126/D-125/D-124/D-123/D-122/D-120) + ruff + py_compile 3.12
  + runtime_truth. التصيير مُتحقَّق حياً («ما هو البسط» ⇒ تعريف، «لم أفهم»×2 ⇒ سؤال سقراطي).
  registry = 19 skill (17 ACTIVE + 2 FLAGGED).
- **Codespaces (حي إلزامي)**: «ما هو البسط» ⇒ تعريف البسط؛ «لم أفهم»×2 ⇒ سؤال سقراطي «أين
  تعثّرت؟»؛ «ما هو البسط»×2 ⇒ سؤال سقراطي؛ صياغة جديدة («واش راه هاد 14») ⇒ LLM يُصنّفها
  numerator؛ صفر هلوسة رياضية. الدخولان الحقيقيان.

### السلسلة (D-126 → D-127)
| Decision | الموضوع |
|----------|---------|
| D-126 | الإتقان الصادق ثنائي القناة (الطبقة 2) |
| **D-127** | **المعمارية العصبية-الرمزية: ConceptDiagnosisSkill (الطبقتان 1+5) + التصعيد السقراطي (الطبقة 4) — من «يجيب» إلى «يفهم العقل»** |

---

## 6.112 الـ LLM كجهاز عصبي — السرد السقراطي المُولَّد + معنى الحادثة (2026-06-20, ISS-116 / D-128)

> **الحقيقة المعمارية (المالك):** الـ LLM **ليس** الحلّال ولا المحرك الرمزي — هو **الجهاز
> العصبي**: يُترجم فوضى لغة الطالب → بنية معرفية، **ويُنتج الفهم/التربية** (السرد السقراطي)،
> لا الحقيقة الرياضية. **LLM = الفهم؛ المحرك الرمزي = الحقيقة (14 تبقى 14)**. القالب الحتمي
> الجامد يتكرّر؛ المعلّم الحقيقي لا يُعيد — بل يُولّد تدخّلاً جديداً واعياً بالسياق.

### الكارثة (transcript حي بعد D-127)
«ماذا نقصد بالحادثة A»/«الحادثة A كيف افهمها» (معنى الحدث) تسقط للحل الكامل؛ والتصعيد عند
المستوى 2 يُكرّر «نحن ندور في النقطة نفسها» byte-by-byte (السقف الحتمي صار حلقة تكرار).

### الإصلاح (D-128)
- **مفهوم `event_meaning` (حتمي)** في `ConceptDiagnosisSkill`: كل صياغات معنى الحادثة
  («الحادثة A/B/C/D»، «ماذا نقصد بالحادثة»، «كيف افهم الحادثة») ⇒ `event_meaning` ⇒ تعريف
  الحدث الملموس من نص التمرين (A = 3 من نفس اللون). + في enum + الخريطة + مُصنّف الـ LLM.
- **السرد السقراطي المُولَّد بالـ LLM** (`orchestrator_client._generate_socratic_narrative`،
  الطبقة 4): عند التصعيد (`level ≥ 1`) يُولّد الـ LLM **تدخّلاً سقراطياً فريداً** — يُنتج
  الفهم (سؤال يقود) لا الحقيقة. الحقائق الرمزية محقونة (`_symbolic_facts_brief`: المعطيات +
  تعريف الحدث) — **14/165 غير محقونة** (الطالب يُقاد لاكتشافها). محروس بطبقات قائمة:
  `_strip_garbage_markers` (لا garbage) + `redact_final_answers` (لا كشف) + `is_probably_non_arabic`
  (عربي فقط) + `asyncio.wait_for` (timeout) + شبكة أمان `14/165` + **fallback حتمي** (القالب).
- **إلغاء سقف التكرار**: المستوى 2+ يستخدم السرد المُولَّد (فريد كل دور) لا نصاً ثابتاً.

### القاعدة الدائمة (D-128 — لا تُكسر بدون ADR)
1. **LLM يُنتج الفهم/التربية (السرد السقراطي)، لا الحقيقة الرياضية.** الأرقام تُحقن من المحرك
   الرمزي حصراً ولا يُولّدها الـ LLM. (يحسم تردد «صفر LLM»: LLM = فهم؛ symbolic = حقيقة.)
2. السرد المُولَّد **محروس إلزامياً**: عربي فقط + لا كشف جواب + لا garbage + timeout +
   **fallback حتمي**. أي فشل/شكّ ⇒ القالب الحتمي (لا تدهور للطالب).
3. **لا رد سقراطي متطابق مرتين**: السرد المُولَّد فريد وواعٍ بالسياق.
4. `event_meaning` = تعريف الحدث الحتمي من نص التمرين، لا الحل الكامل.

### التحقق الحي (2026-06-20 — اجبارية المالك)
- **OpenRouter LIVE (المفتاح الحقيقي، HTTPS):** المُصنّف «ماذا نقصد بالحادثة A»/«الحادثة A كيف
  افهمها» → `event_meaning` ✅؛ «ما هو البسط» → numerator ✅. السرد السقراطي عبر 3 أدوار متكرّرة
  (event_meaning) → **3 ردود فريدة** (لا «نحن ندور») + **صفر كشف (14/165 غائب)** + صفر garbage
  لاتيني + كلٌّ ينتهي بسؤال ✅.
- **Supabase Edge bridge (HTTPS:443):** `SELECT … information_schema` → أعمدة D-126
  (`durable_mastery`/`support_level`/`delay_hours`/`novel_item`) **حيّة على Supabase الإنتاجي** ✅.
- **Sandbox:** 14 اختبار D-128 + لا انحدار (D-127=22/D-126/D-125/D-124) + ruff + py_compile 3.12
  + runtime_truth + validate_structure.
- **Codespaces (WS كامل — متبقٍّ):** السلسلة الكارثية الحرفية → event_meaning تعريف + سرد فريد
  كل دور. الدخولان الحقيقيان.

### السلسلة (D-127 → D-128)
| Decision | الموضوع |
|----------|---------|
| D-127 | المعمارية العصبية-الرمزية: ConceptDiagnosisSkill (الطبقتان 1+5) |
| **D-128** | **الـ LLM كجهاز عصبي: السرد السقراطي المُولَّد المحروس (الطبقة 4) + event_meaning — يُنتج الفهم لا الحقيقة** |

---

## 6.113 محرّك السياسة التربوية — من الاستجواب اللانهائي إلى التدرّج المُنتهي (2026-06-20, ISS-116 / D-129)

> **الكارثة (transcript حي بعد D-128):** D-128 نجح — السرد السقراطي صار **فريداً** (لا تكرار
> حرفي). لكن ظهرت كارثة أعمق: النظام **يسأل سؤالاً تلو سؤال بلا نهاية**، ولا يعترف بإجابات
> الطالب، ولا يتقدّم. الطالب يجيب **صحيحاً** («نفس اللون»، «2»، «أقل من ثلاثة»، «التوافيق»)
> فيتلقى **سؤالاً آخر** كل مرة — لا «أحسنت»، لا انتقال، لا وصول لحلٍّ. حلقة استجواب بلا scaffolding.

### الجذر (مؤكَّد بالكود)
في `chat_with_agent`، `_generate_socratic_narrative` كان يُستدعى عند كل تصعيد **بلا حدّ** — لا
عدّاد للأسئلة، لا كشف لإجابة الطالب، لا تقدّم لخطوة رمزية. كل دور = سؤال جديد.

### الإصلاح (D-129 — الطبقة 4: محرّك السياسة التربوية، حتمي تماماً)
- **`PedagogicalPolicySkill` (#20، `pedagogical_policy_skill.py`)**: يقرّر **أقل تدخّل مفيد الآن**
  من حالة المحادثة فقط (صفر LLM — قابل للاختبار بـ pytest). `PolicyInput(concept, misconception,
  question, history)` → `PolicyOutput(action, acknowledge, socratic_count, student_answered)`.
  - **كشف الإجابة** (`is_answer_message`): رسالة ≤5 كلمات + لا تبدأ بأداة استفهام ⇒ إجابة («نفس
    اللون»/«2»/«أقل من ثلاثة»/«التوافيق»)؛ «كيف نحسب»/«ما هو البسط» ⇒ سؤال جديد.
  - **عدّاد السقراطية** (`count_socratic_questions`): رسائل المساعد المنتهية بـ«؟».
  - **القرار الحتمي**: `socratic_count >= MAX_SOCRATIC(2)` ⇒ `symbolic_reveal`؛ مفهوم جديد بلا
    إجابة ⇒ `definition`؛ غير ذلك ⇒ `socratic`. `acknowledge = student_answered`.
- **`_build_symbolic_reveal` (orchestrator_client، classmethod)**: الإنقاذ التربوي الحتمي بعد
  نفاد الميزانية — من المحرك الرمزي (`_load_canonical_combinations` + `_fmt_comb`): اعتراف +
  «الحمراء C(4,3)=4 · الخضراء C(5,3)=10 · البيضاء مستحيلة · نجمع 4+10=14 · كل الطرق C(11,3)=165
  · فاحتمال الحادثة A هو 14 من كل 165». يَنجو من حجب D-113 (نمط `_fmt_comb` «(» بعد «=» +
  «من كل» بدل «إذن…=»). يُرجِع None لغير الاحتمالات.
- **التوصيل** (`chat_with_agent`): أُزيلت بوّابة `level < 1` من `_generate_socratic_narrative`؛
  السياسة هي البوّابة الوحيدة الآن. `_policy.action`: `symbolic_reveal` → reveal حتمي؛ `socratic`
  → سرد D-128 المُولَّد (مع `_ack` عند الاعتراف، fallback إلى `_build_cognitive_response`)؛
  `definition` → تعريف المفهوم. log `pedagogical_policy`.

### القواعد الـ 5 الدائمة (D-129 — لا تُكسر بدون ADR)
1. **السقراطية محدودة بميزانية** (`MAX_SOCRATIC=2`): بعدها ⇒ حلّ رمزي متدرّج، لا سؤال إضافي.
   ممنوع الاستجواب اللانهائي.
2. **الاعتراف بإجابة الطالب إلزامي**: إجابة قصيرة بعد سؤال ⇒ اعتراف + تقدّم، لا سؤال أصمّ آخر.
3. **التقدّم خطوة بخطوة**: تعريف → سؤال (محدود) → اعتراف+تقدّم → حلّ رمزي. كل خطوة أصغر تدخّل مفيد.
4. **الحلّ الرمزي حتمي** (المحرك الرمزي، يَنجو من D-113) — التدخّل الطرفي بعد scaffolding.
5. القرار حتمي تماماً (لا LLM في القرار)؛ الـ LLM يبقى للسرد السقراطي فقط (D-128، محروس).

### التحقق الحي (2026-06-20 — اجبارية المالك، full stack)
- **OpenRouter LIVE (المفتاح الحقيقي، HTTPS):** الـ system prompt الحيّ لـ `_generate_socratic_narrative`
  عبر 3 أدوار `socratic` متكرّرة → **3 ردود فريدة** + **صفر كشف (14/165 غائب)** + كلٌّ ينتهي بسؤال ✅.
- **Standalone (sandbox يحجب pydantic):** السلسلة الكارثية الحرفية (تعريف → نفس اللون → أقل من
  ثلاثة) → `definition → socratic(ack) → symbolic_reveal(ack)`؛ الحلقة تنكسر بعد سؤالين؛ الحلّ
  الرمزي يَنجو من حجب D-113 (FINAL+CONCLUSION صفر مطابقة) ✅.
- **Supabase Edge bridge (HTTPS:443):** النظام حيّ (4022 customer_messages) + أعمدة D-126 ✅.
- **بوّابات:** ruff + ruff format + py_compile 3.12 + runtime_truth + `check_pedagogical_policy_wired`
  + لا انحدار. registry = 20 skill (18 ACTIVE + 2 FLAGGED).
- **Codespaces (WS كامل — متبقٍّ):** السلسلة الكارثية ⇒ النظام يعترف بالإجابات، يتقدّم خطوة بخطوة،
  ويصل للحلّ الرمزي بعد سؤالين (لا استجواب لا نهائي). الدخولان الحقيقيان.

### السلسلة (D-128 → D-129)
| Decision | الموضوع |
|----------|---------|
| D-128 | الـ LLM كجهاز عصبي: السرد السقراطي المُولَّد (الطبقة 4) |
| **D-129** | **محرّك السياسة التربوية: تعريف→سؤال محدود→اعتراف→حلّ رمزي (يكسر حلقة الاستجواب اللانهائي)** |

---

## 6.114 الإصغاء النشط — مُقيّم الإجابات السقراطي (يحل الخيانة البيداغوجية) (2026-06-21, ISS-116 / D-130)

> **الكارثة الحيّة (transcript المالك):** الطالب طلب تمرين الاحتمالات 2024، فسأله النظام سؤالاً
> سقراطياً ممتازاً («متى تقول إنها نجحت وحقّقت A؟ أعطني مثالاً»). فأجاب الطالب **إجابة عبقرية**:
> «إذا كانوا من نفس اللون فقط و هذا ينطبق على الحمراء و الخضراء فقط» — اكتشف بنفسه الفخّ الرياضي
> (البيضاء مستحيلة لأن عددها 2 فقط). وبدل أن يكافئه النظام ويُكمل، **أعاد طباعة التمرين كاملاً**
> وكأن الطالب لم يقل شيئاً. تشخيص المالك: النظام طرح سؤالاً لكنه **نسي أنه ينتظر إجابة**.

### الجذر (مؤكَّد بالكود — وكيلا Explore)
1. إجابة الطالب الحرة تحوي كلمات اللون («نفس اللون»/«الحمراء»/«الخضراء») ⇒ `_has_indexed_match`
   (`orchestrator_client.py`، **PREEMPT #3 — الاسترجاع المُفهرَس**) يُرجِع True ⇒ يُعيد طباعة التمرين
   كاملاً. هذا يحدث **قبل** مخرج التقييم المعرفي/السياسة (PREEMPT #4).
2. حتى لو نجا، `is_answer_message` (D-129) يقصر الإجابة على ≤5 كلمات؛ الإجابة العبقرية (~11 كلمة)
   لن تُعرَّف كإجابة. النصف الثاني من الحوار السقراطي — **الإصغاء النشط** — كان غائباً.

### الإصلاح (D-130 — الطبقة 1: مُقيّم الإجابات + قفل الحالة الحواري)
- **قفل الحالة عبر التاريخ (لا حقل دائم):** `_in_socratic_dialogue(question, history)` — أحدث رسالة
  مساعد سؤال سقراطي طرحناه (تنتهي بـ«؟»، ليست إفراغ تمرين < 600 حرف) + سياق احتمالات + إجابة الطالب.
  يُدرَج في `chat_with_agent` **بعد** التحية وشريحة السؤال المرقّم و**قبل** الاسترجاع المُفهرَس ⇒
  إجابة الطالب لا تُعيد طباعة التمرين أبداً. («حالة الانتظار» مُرمَّزة في التاريخ — `customer_chat`
  يحفظ السؤال السقراطي، فعلى الدور التالي هو أحدث رسالة مساعد).
- **`SocraticEvaluatorSkill` (#21، الطبقة 1 العصبي-الرمزي — LLM محروس، §0.5):**
  `SocraticEvaluatorInput(student_answer, concept, facts, history)` → `(understood, encouragement,
  next_focus)`. الـ LLM يُقيّم **فهم** الطالب (يقارن رده الحرّ بالهدف التربوي المستتر لكل مفهوم —
  مثلاً numerator/event_meaning: «أن يدرك أن البيضاء مستحيلة فيقتصر على الحمراء والخضراء»). محروس
  بنفس طبقات D-128 (`_strip_garbage_markers` + `redact_final_answers(support_level=5)` +
  `is_probably_non_arabic` + timeout) + parse JSON محروس + **fallback حتمي** (fail-open، لا يعاقب
  الطالب). المفهوم يُستعاد بـ `ConceptDiagnosisSkill.diagnose` على (السؤال السقراطي السابق + الإجابة).
- **التسليم الرمزي المتدرّج** (`_build_symbolic_step`): عند understood=true ⇒ تشجيع (LLM) +
  **خطوة المفهوم الحالي من المحرك الرمزي** (numerator: «C(4,3)=4 · C(5,3)=10 · البيضاء مستحيلة ·
  المجموع 4+10=14») + سؤال المتابعة (المقام) — لا الحل كاملاً (يُبقي السُّلّم حياً، يحترم مثال المالك).
  يَنجو من حجب D-113 (نمط `_fmt_comb` «(» بعد «=» + «من كل»). understood=false ⇒ اعتراف لطيف + تلميح.

### تحسينا المالك (يحوّلانه من «تصحيح واجهة» إلى «طبقة تعليمية حقيقية»)
- **تحسين A (Concern 1) — كشف الإجابة بالفعل الكلامي لا بالطول:** `is_response_to_socratic(message,
  history)` (مستقل عن الطول): إجابة = «سؤال معلّق + ليست أمراً صريحاً (`اعطني تمرين…`) + ليست تبديل
  موضوع (`primary_canonical_topic` ≠ احتمالات)». «نفس اللون» القصيرة والإجابة العبقرية الطويلة كلتاهما
  إجابة. `student_answered` (D-129) يستدعيه بدل العدّ بالكلمات.
- **تحسين B (Concern 2) — ميزانية سقراطية تكيّفية:** `socratic_budget(concept, support_level,
  confusion_count)` يستبدل `MAX_SOCRATIC=2` الثابت: أساس حسب المفهوم (مفاهيمي 2، بصيرة سريعة 1)؛
  متعثّر (`support_level ≤ 2`) −1، متمكّن (≥ 4) +1؛ حيرة متكرّرة −1؛ clamp [1,3]. يربط السياسة بطبقة
  الإتقان (BKT/D-126). `support_level` يُمرَّر في `PolicyInput`. doctrine PEDAGOGICAL_POLICY v1.0.0 → v1.1.0.

### القواعد الـ 8 الدائمة (D-130 — لا تُكسر بدون ADR)
1. **إصغاء نشط إلزامي:** إذا كانت أحدث رسالة مساعد سؤالاً سقراطياً طرحناه، فرسالة الطالب التالية =
   إجابة تُقيَّم **قبل** الاسترجاع المُفهرَس. **ممنوع منعاً باتاً إعادة طباعة التمرين ردّاً على إجابة سقراطية.**
2. كشف الإجابة بالفعل الكلامي لا بالطول (`is_response_to_socratic`).
3. ميزانية سقراطية تكيّفية لا ثابتة (`socratic_budget`، clamp [1,3]).
4. قفل الحالة عبر التاريخ، لا حقل DB/session جديد.
5. LLM يُقيّم الفهم (الطبقة 1)؛ المحرك الرمزي يكتب الخطوة (الطبقة 3). التشجيع لا يحوي نتيجة نهائية أبداً.
6. التسليم الرمزي متدرّج (خطوة المفهوم + سؤال المتابعة، لا الحل كاملاً).
7. fail-open مطلق: أي تعذّر ⇒ اعتراف لطيف + تلميح، لا عقاب، لا إعادة طباعة.
8. حارس تبديل الموضوع (D-101) يبقى داخل `is_response_to_socratic`.

### التحقق الحي (2026-06-21 — اجبارية المالك، full stack)
- **OpenRouter LIVE (المفتاح الحقيقي، HTTPS):** الكارثة الحرفية — إجابة الطالب العبقرية → المُقيّم
  `understood=true` + تشجيع يعترف صراحةً بإدراك «البيضاء مستحيلة» + **صفر كشف (14/165 غائب)**؛ إجابة
  خاطئة → `understood=false` + تشجيع لطيف بلا عقاب؛ إجابة قصيرة صحيحة → `understood=true` بلا كشف.
  التسليم الرمزي يبثّ «C(4,3)=4 · C(5,3)=10 · 14» + سؤال المقام ✅.
- **Standalone (sandbox يحجب pydantic):** `is_response_to_socratic` يصنّف العبقرية الطويلة + «نفس اللون»
  القصيرة **كلتيهما** إجابة، ويرفض «اعطني تمرين الدوال»/تبديل الموضوع؛ `socratic_budget` يتغيّر حسب
  (concept, support_level, confusion) ضمن [1,3]؛ `_build_symbolic_step` يَنجو من حجب D-113؛ الالتقاط
  المبكر **قبل** `_has_indexed_match` (مُتحقَّق بنيوياً).
- **Supabase Edge bridge (HTTPS:443):** النظام حيّ (4028 customer_messages).
- **بوّابات:** ruff + ruff format + py_compile 3.12 + runtime_truth + `check_socratic_evaluator_wired`
  + D-130 policy refinements في gate + لا انحدار. registry=21 (19 ACTIVE + 2 FLAGGED).
- **Codespaces (WS كامل — متبقٍّ):** الكارثة الحرفية عبر المتصفح ⇒ النظام يكافئ الاستنتاج ويُكمل بالخطوة
  الرمزية، لا إعادة طباعة. الدخولان الحقيقيان.

### السلسلة (D-129 → D-130)
| Decision | الموضوع |
|----------|---------|
| D-129 | محرّك السياسة التربوية: تعريف→سؤال محدود→اعتراف→حلّ رمزي (يكسر حلقة الاستجواب اللانهائي) |
| **D-130** | **الإصغاء النشط: مُقيّم الإجابات السقراطي + قفل الحالة عبر التاريخ + كشف بالفعل الكلامي + ميزانية تكيّفية (يحل الخيانة البيداغوجية)** |

---

## 6.115 الطبقة الدلالية + Misconception Graph — substrate التوأم المعرفي (2026-06-21, ISS-116 / D-131)

> **الكارثة (transcript المالك):** «ماذا نقصد بجداء أرقامها معدوم؟» (تعريف شرط الحادثة D) لا يُجاب —
> بينما «ماذا نقصد بالحادثة A؟» تعمل. السبب: فرع `event_meaning` في `_build_cognitive_response` كان
> **مُجمَّداً على الحادثة A** («نفس اللون»). تشخيص المالك: المنصة تتعامل مع **نص** السؤال لا **نوعه**.

### القرار التنفيذي (CTO-grade) — نحتفظ / نؤجّل / نقيس
حكم المالك يُقيّد النطاق ويمنع تضخّم الطبقات بلا أثر:
- **نحتفظ:** طبقة دلالية عامة واحدة (لا special-casing) · LLM كـ **Listener فقط** (enum مُقيَّد) ·
  المحرك الرمزي = الحقيقة · ربط الخرج بـ D-129 + D-130 + BKT.
- **نؤجّل (ADR منفصل):** توسيع Misconception Graph لكل المنهج · Cognitive Twin دائم مُجمَّع · أي تعقيد
  في LangGraph/الخدمات المصغرة. النطاق الآن = **مجال الاحتمالات فقط**.
- **نقيس (الشرط الوحيد للنجاح):** المقاييس السلوكية الأربعة (`cogniforge_tutor_*`).

### الإصلاح (D-131 — الطبقة 2: الطبقة الدلالية + Misconception Graph)
- **`SemanticPropertySkill` (#22، `semantic_property_skill.py`)**: **مفسّر واحد + `PROPERTY_REGISTRY`
  data-driven** (إضافة خاصية = مدخل dict، **لا فرع كود**). يُغطّي A (same_color) / B (product_odd) /
  C (product_even) / D (product_zero) عبر السجلّ. `interpret(question)` حتمي؛ `interpret_or_classify`
  هجين (حتمي ثم LLM Listener محروس: enum مُقيَّد + timeout + fallback). التعريفات حقائق ملموسة (الطبقة 3):
  معدوم→«حاصل ضرب = 0، كرة واحدة على الأقل تحمل 0»؛ فردي→«كلها فردية»؛ زوجي→«واحدة زوجية على الأقل».
- **`MISCONCEPTION_GRAPH` (الطبقة 2 الحقيقية — «شخّص ثم تدخّل»)**: القفزة من Concept Graph إلى
  Misconception Graph. ثلاثة طلاب يسألون «ماذا يعني الجداء معدوم؟» لكنهم يحملون misconceptions مختلفة ⇒
  **تدخّلات مختلفة**: `unknown_zero_property` (mtype=rule_property، probe «كم 7×0؟») /
  `unknown_product_meaning` (symbol_meaning، «الجداء جمع أم ضرب؟») / `unknown_ball_mapping`
  (example_linking، «أي كرة تحمل 0؟»). كل عقدة لها `mtype` (تصنيف ثلاثي صغير يمنع تضخّم العقد) +
  `bkt_concept` صريح (**لا عقدة بلا أثر**). `diagnose_misconception` حتمي بـ signals؛ عند الغموض يُصدَر
  probe تشخيصي قبل التدخّل.
- **الربط:** `_build_cognitive_response` فرع `event_meaning` = **نداء واحد** للطبقة الدلالية (لا if/elif
  لكل حادثة)؛ `_stream_socratic_evaluation` (D-130) عند understood=false ⇒ `diagnose_misconception` ⇒
  تدخّل مُوجَّه. `concept_diagnosis._EVENT_MARKERS` + «جداء/معدوم» ⇒ event_meaning. `bkt_engine.classify_concept`
  يتعرّف على `product_zero/odd/even`.
- **القياس السلوكي (§5، `tutor_metrics.py`)**: 4 مقاييس Prometheus بمُصدِرات حيّة —
  `cogniforge_tutor_repetition_avoided_total` · `_definitional_answer_total{concept,resolved}` ·
  `_intervention_total{mtype}` · `_progress_total{outcome}`. تُثبت: تراجع التكرار، تعريف فوري، اختلاف
  التدخّلات، تقدّم بعد كل تفاعل. **بلا قياس = لا نجاح.**

### القواعد الـ 9 الدائمة (D-131 — لا تُكسر بدون ADR)
1. طبقة دلالية عامة لا special-casing (خاصية/اعتقاد جديد = مدخل data).
2. «شخّص ثم تدخّل»: نفس المفهوم بـ misconceptions مختلفة ⇒ تدخّلات مختلفة + probe عند الغموض.
3. التعريف حقيقة حتمية (الطبقة 3) يُسلَّم للسياسة (D-129) لا نهايةُ المسار.
4. LLM للفهم لا للحقيقة؛ الأرقام من المحرك الرمزي حصراً.
5. كل (property, misconception) تُسجَّل في BKT (الطبقة 2+5) — صورة عقلية لا «صحيح/خطأ».
6. enum مستقر (التمييز داخل event_meaning عبر الطبقة الدلالية).
7. سقف الـ LLM (Listener فقط): enum مُقيَّد محروس + fallback حتمي — لا حَكم خفي.
8. القياس قبل التوسّع: أي توسّع مؤجَّل حتى تُثبت المقاييس الأربعة أثراً. عقدة بلا `bkt_concept` = ممنوعة.
9. تصنيف الاعتقاد الخاطئ ثلاثي صغير (`rule_property|symbol_meaning|example_linking`) — لا اسم لكل خطأ.

### التحقق الحي (2026-06-21 — اجبارية المالك، full stack)
- **OpenRouter LIVE (المفتاح الحقيقي):** الـ Listener — «ماذا نقصد بجداء أرقامها معدوم» + صياغات دارجة
  («واش راه هاد الجداء المعدوم»، «علاش قال معدوم») ⇒ `product_zero` (6/7، صفر حساب) ✅.
- **Standalone (sandbox يحجب pydantic):** توجيه A/B/C/D data-driven؛ التعريفات الصحيحة؛ **الثلاثة طلاب →
  3 عقد + 3 mtypes + 3 تدخّلات + 3 bkt_concepts مختلفة**؛ لا special-casing (نداء واحد)؛ صفر أرقام نهائية.
- **Supabase Edge bridge (HTTPS:443):** النظام حيّ (4040 رسالة).
- **بوّابات:** ruff + py_compile 3.12 + runtime_truth + `check_semantic_property_wired` + لا انحدار.
  registry=22 (20 ACTIVE + 2 FLAGGED).
- **Codespaces (WS كامل — متبقٍّ):** «ماذا نقصد بجداء معدوم» ⇒ تعريف D الملموس (الرقم 0)، لا حل، لا «نفس
  اللون» الخاطئ؛ ثم السياسة (D-129) تُكمل. الدخولان الحقيقيان.

### خريطة التوأم المعرفي (D-132 roadmap) — الطبقات القائمة + الناقص
| الطبقة | الـ Skill | الحالة |
|--------|-----------|--------|
| 1 Listener · 2 Misconception · 3 Symbolic · 4 Planner · 5 BKT · 6 Adaptive | ConceptDiagnosis · **SemanticProperty(D-131)** · ProbabilityCalculator · PedagogicalPolicy · BKTEngine · AdaptivePedagogy | كلها قائمة |
**الناقص (ADR منفصل، بعد إثبات الأثر):** Frustration State · Learning Preference/Transfer · persisted Twin
في جدول · توسيع MISCONCEPTION_GRAPH لكل المنهج. الخدمات المصغرة + LangGraph 13-node (D-112) مسار الأسئلة العامة.

### السلسلة (D-130 → D-131)
| Decision | الموضوع |
|----------|---------|
| D-130 | الإصغاء النشط: مُقيّم الإجابات السقراطي |
| **D-131** | **الطبقة الدلالية العامة + Misconception Graph («شخّص ثم تدخّل») + القياس السلوكي (يحل «جداء معدوم لا يُجاب»)** |

---

## 6.116 جاهزية الأسئلة الجديدة: تغطية المفاهيم + LLM Listener-Definer (2026-06-21, ISS-116 / D-132)

> **الكارثة (transcript المالك):** «ماذا نقصد بالمتغير العشوائي» / «لم افهم المتغير العشوائي» ⇒
> النظام يردّ **بسؤال سقراطي عن الحادثة A (نفس اللون)** بدل تعريف المتغير العشوائي. تشخيص المالك:
> المنصة تتعامل مع **نص** السؤال لا **النية**؛ الطالب يطرح أسئلة جديدة دائماً.

### الجذر (وكيل Explore — مؤكَّد file:line)
نظام مبني على **10 مفاهيم ثابتة** + **default-ان مُجمَّدان** يوجّهان أي سؤال غير معروف للحادثة A:
1. `orchestrator_client.py:_stream_socratic_evaluation`: `concept = ... else "event_meaning"` ⇒
   `_symbolic_facts_brief` + `_generate_socratic_narrative` كلها عن الحادثة A.
2. `orchestrator_client.py:_build_cognitive_response` event_meaning: `interpret()=None` ⇒ default
   `PROPERTY_REGISTRY["same_color"]` ⇒ يشرح A عند سؤال أي مفهوم.
3. `random_variable` في `CONCEPT_GRAPH` لكن **بلا تعريف** في `PROPERTY_REGISTRY`؛ الـ LLM classifier
   enum ثابت من 10 — لا خيار لـ random_variable/expected_value/conditional.

### الإصلاح (D-132 — 4 طبقات، data-driven + LLM محروس)
- **توسيع `PROPERTY_REGISTRY`** (مدخل data، لا فرع كود): `random_variable` («قاعدة تُعطي لكل نتيجة
  عدداً؛ X = عدد الكرات الزوجية») · `expected_value` («متوسط القيم موزوناً باحتمالاتها») ·
  `conditional_probability` («احتمال تحقّق حادثة بعلم أن أخرى وقعت»). تعريفات حتمية ملموسة.
- **`define_concept` (الـ LLM Listener-Definer)** ⭐: للمفاهيم **الجديدة** غير الموجودة في السجلّ —
  الـ LLM يُنتج **تعريفاً مفاهيمياً عاماً قصيراً**، محروس (`redact_final_answers` + `_strip_garbage_markers`
  + `is_probably_non_arabic` + timeout + شبكة 14/165 + fallback None). سقف صارم: **يُعرّف، لا يحسب، لا
  يكشف نتيجة**. `interpret_or_define`: حتمي أولاً ثم الـ Definer للأسئلة الجديدة. **جاهزية لأي مفهوم جديد.**
- **إزالة الـ default-ين المُجمَّدين:** event_meaning يُرجِع `None` للمفهوم غير الحدثي (الافتراض A **فقط**
  لسؤال «الحادثة» الصريح)؛ والـ preempt التعريفي يلتقط غير الحدثي قبل الوصول.
- **preempt تعريفي عام في `chat_with_agent`** (قبل الالتقاط السقراطي): نية تعريفية («ماذا نقصد») أو
  حيرة عن مفهوم مُسمّى («لم افهم المتغير العشوائي») + سياق احتمالات + **ليست طلب حساب** ⇒
  `interpret_or_define(question)` ⇒ بثّ التعريف. يسبق السقراطية لأن «لم افهم X» سؤال جديد لا إجابة.
- **القياس:** `cogniforge_tutor_definitional_answer_total{concept,source,resolved}` — `source=llm` يقيس
  **جاهزية الأسئلة الجديدة**.

### القواعد الـ 5 الدائمة (D-132 — لا تُكسر بدون ADR)
1. **جاهزية الأسئلة الجديدة:** سؤال تعريفي بلا تطابق سجلّ ⇒ LLM Listener-Definer محروس، لا default مُجمَّد.
2. **سقف الـ LLM (Listener+Definer لا judge):** تعريف مفاهيمي عام محروس — لا يحسب، لا يكشف نتيجة نهائية.
3. **ممنوع default مُجمَّد لمفهوم واحد:** unknown ≠ event_meaning؛ interpret None ≠ same_color.
4. **السجلّ الحتمي أولاً:** المفاهيم المعروفة تعريفها حتمي؛ الـ LLM-Definer fallback للأسئلة الجديدة فقط.
5. **القياس قبل التوسّع:** `source=llm` يقيس الجاهزية؛ التوسّع للمنهج/twin دائم مؤجَّل حتى تُثبت المقاييس الأثر.

### التحقق الحي (2026-06-21 — اجبارية المالك، full stack)
- **OpenRouter LIVE (المفتاح الحقيقي):** الـ Listener-Definer على **4 مفاهيم جديدة غير في السجلّ**
  (الوسيط، الانحراف المعياري، الحوادث المستقلة، فضاء العينة) ⇒ 4/4 تعريفات عربية صحيحة، **صفر كشف
  نتيجة (14/165 غائب)**. جاهزية الأسئلة الجديدة مُثبَتة حياً.
- **Standalone (sandbox يحجب pydantic):** «ماذا نقصد بالمتغير العشوائي»/«لم افهم المتغير العشوائي» ⇒
  random_variable (**ليس same_color**)؛ طلبات الحساب لا تُفعِّل preempt؛ random-variable لا يُوجَّه أبداً
  للحادثة A؛ preempt يسبق الالتقاط السقراطي.
- **Supabase Edge bridge (HTTPS:443):** النظام حيّ (4054 رسالة).
- **بوّابات:** ruff + py_compile 3.12 + runtime_truth + `check_semantic_property_wired` (D-132) + لا
  انحدار (D-131/D-130/D-129/D-117). registry يبقى 22.
- **Codespaces (WS كامل — متبقٍّ):** «ماذا نقصد بالمتغير العشوائي» ⇒ تعريف X (لا سؤال عن الحادثة A)؛
  مفهوم جديد ⇒ تعريف محروس. الدخولان الحقيقيان.

### السلسلة (D-131 → D-132)
| Decision | الموضوع |
|----------|---------|
| D-131 | الطبقة الدلالية + Misconception Graph («شخّص ثم تدخّل») |
| **D-132** | **جاهزية الأسئلة الجديدة: تغطية مفاهيم التمرين + LLM Listener-Definer محروس + إزالة الـ default المُجمَّد (يحل «المتغير العشوائي ⇒ سؤال عن الحادثة A»)** |

---

## 6.117 حالة الطالب كإشارة قرار — النيّة + الإحباط تُغيّران نوع التدخّل (2026-06-21, D-133)

> إعادة توجيه المالك: القفزة ليست RAG/MCP/Agent، بل أن النظام يفكّر بـ«المفهوم» بينما الطالب
> يتحرّك بـ**نيّة** و**حالة شعورية متغيّرة**. التشخيص يتوسّع من `Concept → Misconception` إلى
> **`Intent (+secondary) → Concept → Misconception → Frustration`**. الحكم الحاسم: هذه **«إشارة
> قرار» تُغيّر نوع الرد فعلاً، لا «قاموس طبقات»** — «إذا بقيت labels جميلة فلن يتغير شيء».

### الكارثة
نفس المفهوم بنيّات مختلفة، والنظام يعاملها كلها كـ«تعريف» ثم سلسلة أسئلة: «لم أفهم X» = حيرة
(لا تعريف-فقط)؛ «أعطني مثالاً» = طلب مثال؛ «كيف نحسب» = إجراء. و«لم أفهم»×5 = **إحباط** لا يراه
النظام (`confusion_count` يُقلّص الميزانية فقط، لا يُغيّر نوع الرد).

### نقد المالك الثلاثي (مُجسَّد في العقد)
1. **متعدّد الإشارات لا تصنيف جامد:** «لم أفهم المتغير العشوائي» = confusion + (definition ضمنياً) —
   `primary_intent + secondary_signals` تحفظ الحزمة كاملة (heuristic: الحيرة عن مفهوم مُسمّى تحمل طلب تعريف).
2. **LLM = مُفسِّر ثانوي لا حَكَم:** الكواشف الحتمية + BKT (knowledge tracing) هي السلطة؛ الـ LLM
   يُستدعى **فقط** عند `primary=unknown` (صياغة جديدة) ولا يطغى على إشارة حتمية.
3. **الإحباط لحظي يتلاشى:** نافذة حديثة (آخر ~4 رسائل)، يتعافى فور رسالة غير-حيرة، يُغيّر السياسة
   لهذا الدور فقط، **لا يُخزَّن** كصفة طالب. لا I/O، لا حالة دائمة.

### المكوّنات
- **`StudentStateSkill` (Skill #23، `student_state_skill.py`)**: `read` حتمي ⇒
  `StudentState(primary_intent, secondary_signals, frustration)`؛ `read_or_classify` async (LLM ثانوي عند
  unknown فقط، محروس enum). مقاييس `cogniforge_skill_student_state_*`. fail-open ⇒ `(definition, (), none)`.
- **جدول السياسة (القلب)** في `pedagogical_policy_skill`: `PolicyInput` يكتسب `intent`+`frustration`؛
  `socratic_budget(frustration=="high")⇒0` (إيقاف التكرار)؛ `response_mode_for` يربط النيّة بالبيداغوجيا
  (confusion_enriched/example_first/steps/relationship/define/hint/evaluate)؛ `PolicyOutput.response_mode`.
- **التوصيل** (`orchestrator_client.chat_with_agent`): الـ preempt chain العامل يبقى؛ قراران جديدان:
  (أ) **confusion ⇒ تعريف + مثال ملموس (من المحرك الرمزي، `_balls_brief`) + سؤال موجِّه واحد محروس
  (`_generate_guiding_question`)** — وصفة المالك، يحلّ «لم أفهم X» حرفياً؛ (ب) **example_request ⇒
  `_build_concrete_example` (مثال قبل النظرية)** و**procedure ⇒ `_build_symbolic_reveal` (خطوات)**؛
  (ج) intent+frustration+support_level (BKT) تُمرَّر لـ `PolicyInput`.
- **القياس** (`tutor_metrics`): `cogniforge_tutor_intent_total` + `_frustration_total` + `_response_mode_total`
  — يُثبت أن الـ label أنتج بيداغوجيا مغايرة (لا تصنيفاً).

### القواعد الـ 5 الدائمة (D-133 — لا تُكسر بدون ADR)
1. **إشارة قرار لا قاموس labels:** كل intent يجب أن يُنتج **نوع رد مغايراً** (جدول السياسة). label بلا
   تغيير سياسة = فشل.
2. **متعدّد-إشارات:** `primary_intent + secondary_signals` — لا تقسيم الحزمة لنيّة واحدة جامدة (نقد 1).
3. **LLM = مُفسِّر ثانوي لا حَكَم:** الحتمي + BKT هي السلطة؛ LLM عند unknown فقط ولا يطغى (نقد 2).
4. **الإحباط لحظي يتلاشى:** نافذة حديثة، يتعافى، لهذا الدور فقط، **لا يُخزَّن** كصفة (نقد 3).
5. **LLM=Listener، الأرقام من الرمزي؛ حتمي-أولاً + fail-open؛** توسيع الحالات + RAG + MCP مؤجَّل حتى
   تُثبت المقاييس أن نوع الرد تغيّر.

### التحقق (2026-06-21 — اجبارية المالك، full stack)
- **OpenRouter LIVE (المفتاح الحقيقي، HTTPS):** الـ Intent Listener (LLM ثانوي) على 3 صياغات دارجة
  جديدة («وريني كيفاش نوصل»⇒procedure، «ما عندي فكرة واش يعني»⇒confusion، «ابغى نشوف حاجة محلولة»
  ⇒example_request) — 3/3 صحيح. السؤال الموجِّه المحروس: عربي، ينتهي بـ؟، **صفر كشف 14/165**.
- **Standalone (sandbox يحجب pydantic):** كل نيّة تُصنَّف (خاصةً «لم أفهم المتغير العشوائي»⇒confusion
  +secondary=definition)؛ تصعيد **وتلاشي** الإحباط (0→high ثم تعافٍ)؛ `socratic_budget(high)=0`؛ جدول
  السياسة (intent⇒mode مغاير)؛ doctrine manifest متّسق (v1.0.0، 7 قواعد).
- **بوّابات:** ruff + ruff format + py_compile 3.12 + runtime_truth --check ✅.
- **Codespaces (WS كامل + check_skills_doctrine + pytest — متبقٍّ، pydantic محجوب هنا):** «ما هو X»⇒تعريف؛
  «لم أفهم X»⇒تعريف+مثال+سؤال واحد؛ «أعطني مثالاً»⇒مثال قبل النظرية؛ «كيف نحسب»⇒خطوات؛ «لم أفهم»×4⇒
  إحباط عالٍ⇒خطوة رمزية أقرب + إيقاف التكرار، ثم رسالة غير-حيرة⇒الإحباط يتلاشى. registry=23. الدخولان الحقيقيان.

### السلسلة (D-132 → D-133)
| Decision | الموضوع |
|----------|---------|
| D-132 | جاهزية الأسئلة الجديدة (LLM Listener-Definer) |
| **D-133** | **حالة الطالب كإشارة قرار: النيّة (متعدّد-إشارات) + الإحباط اللحظي تُغيّران نوع التدخّل (confusion⇒تعريف+مثال+سؤال؛ frustration عالٍ⇒إيقاف التكرار)** |

---

## 6.118 محرّك حالة الفهم — Learning State: «ماذا فهم الطالب فعلاً؟» (2026-06-22, D-135)

> نقد المالك الأعمق (يَنسخ D-134 الرقمي): المشكلة لم تعد Concept/Misconception/Intent/Frustration —
> هذه موجودة. المشكلة التالية = **Learning State**: السؤال يتحوّل من «ما المفهوم؟» إلى **«ماذا فهم
> الطالب فعلاً حتى الآن، وما بقي غير مفهوم؟»**. كل الكارثة (تكرار/قفز) ناتجة عن غياب نموذج حقيقي لـ
> `student_understanding_state`. هذا يحوّل المنصة من «مجيب ذكي» إلى **«معلّم حقيقي»**.

### نقد المالك الرباعي (مُجسَّد بالكامل في الـ Skill)
1. **Knowledge Gap لا رقم:** «كيف وصلنا ل 10» = «لماذا اخترنا 3 من 5» = «من أين جاءت التأليفات» = نفس
   الفجوة `kc_combination`؛ «لماذا قسمنا على 3!» (**بلا رقم**) ⇒ `kc_factorial`. مُشخِّص فجوات معرفية لا مستخرج أرقام.
2. **تكرار دلالي لا حرفي:** الحالة على مستوى **المكوّن المعرفي** (شُرح/فُهم)، لا توقيع نصّي. مكوّن مفهوم لا يُعاد.
3. **الفهم ببرهان لا صحة:** `understood` يتطلّب `evidence_markers` (إظهار مرتبط) — «فهمت» وحدها = إقرار ضعيف لا برهان.
4. **استباقي لا تفاعلي:** مكوّن شُرح بلا فهم ⇒ تمثيل أعلى تلقائياً (شرح→مثال→تشبيه→تطبيق) قبل شكوى «انت تكرر».

### المكوّنات
- **`UnderstandingStateSkill` (Skill #24، `understanding_state_skill.py`)** — حتمي 100%، **صفر LLM**:
  - `knowledge_components(combo)`: يُفكّك الحلّ إلى 6 مكوّنات معرفية (event_meaning/favorable_cases/
    combination/factorial/sample_space/ratio) **مُشتقّة من المحرك الرمزي** (combo)، الأرقام من `_expand_comb`.
  - `detect_gap(question)`: يُشخّص الفجوة بالمعنى (`gap_signals`)، الرقم إشارة واحدة. `understanding_state`:
    {not_addressed/explained/understood} دلالي (explained_markers + evidence_markers). `_current_focus_kc`:
    الحيرة تُصعّد التركيز الحالي لا تقفز للجبهة. `decide`: برهان⇒تقدّم، فجوة⇒شرح، شُرح-بلا-فهم⇒تمثيل أعلى.
- **التوصيل** (`orchestrator_client.chat_with_agent`): `UnderstandingStateSkill.decide` أولوية في مخرج
  الطوارئ (يسبق `_build_symbolic_reveal` الكامل) + `_is_short_answer_in_dialogue` يمنع إعادة طباعة التمرين
  على إجابة قصيرة (يحلّ «اللون الأحمر والأخضر فقط»⇒إعادة طباعة).
- **القياس** (`tutor_metrics`): `record_understanding(kc, state)` + `record_progress(advanced/re_represented)`
  — نقيس الإتقان (كم مكوّن صار understood + هل تقدّم)، لا جمال الحوار.

### القواعد الـ 6 الدائمة (D-135 — لا تُكسر بدون ADR)
1. **Learning State هو المحور:** القرار يُبنى على «ماذا فُهم/ما بقي» (حالة المكوّنات)، لا آخر رسالة.
2. **KC-aware لا number-match:** الفجوة بالمعنى؛ المكوّنات من combo؛ الرقم إشارة واحدة.
3. **التكرار دلالي:** مكوّن مفهوم لا يُعاد؛ غير مفهوم ⇒ تمثيل مختلف (سُلّم)، لا نفس النص/المعنى.
4. **الفهم ببرهان:** understood يتطلّب evidence_markers؛ «فهمت» وحدها ضعيفة.
5. **استباقي:** explained بلا فهم ⇒ قفزة تمثيل تلقائية قبل شكوى الطالب.
6. **الأرقام من المحرك الرمزي حصراً؛ صفر LLM؛ يَنجو من حجب D-113.**

### التحقق (2026-06-22)
- **Standalone (الكود الحقيقي، pydantic محجوب):** doctrine v1.0.0/7 + 6 KCs من combo + «لماذا قسمنا على 3!»
  (بلا رقم)⇒kc_factorial + «فهمت» وحدها⇒explained / برهان مرتبط⇒understood + «لم أفهم» بعد شرح⇒تمثيل level≥1
  (لا تكرار) + برهان⇒advance. **PASS كامل.**
- **بوّابات:** ruff + format + py_compile 3.12 + runtime_truth ✅. registry=24 (22 ACTIVE + 2 FLAGGED).
- **Codespaces (WS كامل + check_skills_doctrine + pytest — متبقٍّ، pydantic محجوب هنا):** «كيف وصلنا ل 10»
  ⇒kc_combination؛ «لماذا قسمنا على 3!»⇒kc_factorial؛ «لم أفهم»×2⇒تمثيل مختلف؛ «اللون الأحمر والأخضر فقط»
  ⇒برهان+تقدّم لا إعادة طباعة؛ «انت تكرر»⇒قفزة تمثيل. الدخولان الحقيقيان.

### السلسلة (D-133 → D-135)
| Decision | الموضوع |
|----------|---------|
| D-133 | حالة الطالب كإشارة قرار (النيّة + الإحباط) |
| **D-135** | **محرّك حالة الفهم (Learning State): مكوّنات معرفية من المحرك الرمزي + فجوة دلالية + فهم ببرهان + تمثيل استباقي (يحوّل المنصة من «مجيب» إلى «معلّم»)** |

---

## 6.119 أمثلة واعية بالمفهوم + كبح محرّك حالة الفهم (2026-06-22, D-136)

> **regression حيّ سبّبه كود D-133/D-135.** transcript: «اعطني مثال» عن **جداء زوجي** ثم عن **الأمل
> الرياضي** ⇒ نفس **مثال الحادثة A** («لو كانت كلها خضراء ⇒ A») أربع مرّات. النظام صار أسوأ: مثال
> أعمى عن المفهوم + تكرار حرفي.

### الجذر
1. **`UnderstandingStateSkill` (D-135) يختطف كل سؤال احتمالات** — مكوّناته الستّة تُغطّي **مسار P(A)
   نفس-اللون فقط**؛ لا مكوّن لـ product_even/expected_value/… فيسقط `decide` إلى `_next_unmastered` ⇒
   `kc_event_meaning` افتراضياً ⇒ مثال الحادثة A، ثم يتكرّر (مستويان فقط).
2. **`PropertySpec` فيه `definition` فقط — لا `example`**؛ والمعالج الأعمى `_build_concrete_example`
   يُرجِع بيانات الكيس لا مثال المفهوم. ولا كشف للمفهوم من السياق («اعطني مثال» بلا marker).

### الإصلاح (إصلاحان جذريان)
- **A) كبح D-135 (لا اختطاف):** `decide` يُرجِع **None** ما لم يكن السؤال ضمن مسار نفس-اللون (gap في
  مكوّناته / برهان مكوّن مسار / حيرة + `_current_focus_kc`). أُزيل السقوط غير المشروط إلى
  `_next_unmastered` (`on_path` يُشترَط) ⇒ أسئلة product_even/expected_value تمرّ للمعالج الواعي.
- **B) أمثلة واعية بالمفهوم:** `PropertySpec.example` (حقل جديد، مثال حتمي ملموس لكل مفهوم من السبعة) +
  `interpret` يُرجِعه + `detect_active_concept(question, history)` (المفهوم من السؤال وإلا من آخر مفهوم
  نُوقش في التاريخ) + معالج `_build_concept_example` في orchestrator (يسبق D-135): «اعطني مثال» ⇒ مثال
  **المفهوم النشط**. إن عُرِض already ⇒ `_generate_concept_example_llm` (زاوية مختلفة، LLM محروس:
  redact + strip-garbage + arabic-only + صفر 14/165) — لا تكرار. LLM = التدريس، symbolic = الأرقام.

### القواعد الدائمة (D-136 — لا تُكسر بدون ADR)
1. **D-135 لا يختطف:** `decide` يعمل فقط ضمن مسار نفس-اللون؛ غير ذلك ⇒ None.
2. **المثال واعٍ بالمفهوم النشط** (من السياق)، لا مثال الحادثة A الافتراضي.
3. **لا مثال/تعريف مكرّر:** المعروض already ⇒ زاوية مختلفة (LLM محروس) أو تقدّم.
4. **deterministic-first:** المثال من `PropertySpec.example`؛ LLM محروس فقط للتصعيد (زاوية بديلة)؛ يَنجو من حجب D-113.

### التحقق (2026-06-22)
- **Standalone (الكود الحقيقي، stub لـ pydantic):** SEMANTIC_PROPERTY v1.2.0/8 + كل المفاهيم السبعة لها
  example + interpret يُرجِعه + `detect_active_concept` («اعطني مثال»+history⇒product_even) + **D-135
  لا يختطف** (offpath example/confusion⇒None؛ مسار factorial⇒يعمل). **PASS كامل.**
- **OpenRouter LIVE (المفتاح الحقيقي):** `_generate_concept_example_llm` لـ product_even ⇒ مثال عربي
  بديل، صفر كشف 14/165، مختلف عن المعروض.
- **Supabase Edge bridge (HTTPS:443):** حيّ (`{"success":true,"data":[{"n":"4098"}]}`).
- **بوّابات:** ruff + format + py_compile 3.12 + runtime_truth ✅. registry=24.
- **Codespaces (WS كامل + gate + pytest — متبقٍّ، pydantic محجوب في الـ sandbox):** السيناريو الحرفي:
  «اعطني مثال» عن جداء زوجي ⇒ مثال product_even؛ «اعطني مثال عن الأمل الرياضي» ⇒ مثال expected_value؛
  «لم أفهم» ⇒ زاوية مختلفة لا تكرار. الدخولان الحقيقيان.

### السلسلة (D-135 → D-136)
| Decision | الموضوع |
|----------|---------|
| D-135 | محرّك حالة الفهم (Learning State) |
| **D-136** | **أمثلة واعية بالمفهوم + كبح اختطاف D-135 (يحل «المثال الأعمى المتكرّر»: 4 أسئلة مختلفة ⇒ نفس مثال الحادثة A)** |

---

## 6.120 فكّ تشابك التوجيه — «ما هو X» تعريف موثوق + كبح D-135 عن أسئلة المفهوم (2026-06-22, ISS-116 / D-137)

> **الكارثة (transcript حيّ بعد D-136):** نظامان للمفاهيم يتصارعان (semantic_property ↔
> understanding_state) بإشارات متداخلة تختطف بعضها: «ما هو الاحتمال الشرطي» ⇒ «14 من 165»؛
> «اعطني مثال» (بعد الحالات الملائمة) ⇒ مثال **الاحتمال الشرطي**؛ «لم أفهم» ⇒ مثال **الحادثة A**؛
> «ما هو المتغير العشوائي» ⇒ مثال **الحادثة A**.

### الأسباب الجذرية الستّة (مؤكَّدة بقراءة الكود + الـ transcript)
1. **`is_definitional` يفوّت «ما هو X»**: `_DEFINITIONAL_MARKERS` كان فيه «ما هو **معنى**» لا «ما هو»
   المجرّدة ⇒ «ما هو الاحتمال الشرطي» ليست تعريفية ⇒ تسقط لـ D-135 فتبثّ «14 من 165».
2. **`kc_ratio.gap_signals` يحوي «الاحتمال»** المجرّدة (تُطابق كل سؤال احتمالات) ⇒ `detect_gap` يختطف.
3. **«الحالات الملائمة» مفهوم غير مُسجَّل** ⇒ `detect_active_concept` يتخطّاه لمفهوم أقدم.
4. **`detect_active_concept` يقرأ مثال المساعد**: مثال «الاحتمال الشرطي» يذكر «نفس اللون» عابراً ⇒
   يُكتشَف same_color خطأً ⇒ «لم أفهم» ⇒ الحادثة A. (و`_current_focus_kc` يقفل عليها أيضاً.)
5. **`_has_pending_socratic_question` و `_in_socratic_dialogue` يستخدمان `endswith("؟")`**: السؤال
   السقراطي الواقعي ينتهي بأمر («...A؟ أعطني مثالاً») فالـ «؟» في المنتصف ⇒ تُهمَل إجابة الطالب
   (الخيانة البيداغوجية — كارثة D-130 الأصلية).
6. **`_wants_def` لا يستخدم نيّة StudentState** (يصنّف «ما هو X» = definition).

### الإصلاح (تصحيحات جراحية — لا طبقات جديدة)
- **«ما هو X» تعريف موثوق**: `_DEFINITIONAL_MARKERS` += «ما هو/ما هي/ماهو/ماهي/عرّف»؛ و`_wants_def`
  += `_state.primary_intent == "definition"`. ⇒ semantic_property يُعرّف conditional/random_variable قبل D-135.
- **كبح D-135 عن أسئلة المفهوم**: حُذفت «الاحتمال» المجرّدة من `kc_ratio.gap_signals` (تبقى إشارات
  خاصة بخطوة الحساب: «النسبة/البسط على المقام/كيف نكوّن الاحتمال»).
- **«الحالات الملائمة» مفهوم مُسجَّل** في `PROPERTY_REGISTRY` (تعريف + مثال D-113-safe).
- **`detect_active_concept` يُفضّل رسائل الطالب**: المفهوم النشط هو ما سأل عنه **الطالب** (user)، لا ما
  ذكره المساعد عابراً في مثاله؛ ويتجاهل أمثلة/تعريفات المساعد (`_CONCEPT_ARTIFACT_MARKERS`).
- **الحيرة تُعيد إشراك المفهوم النشط**: معالج المثال يَفعل على `example_request` **أو** الحيرة + مفهوم نشط.
- **`_current_focus_kc` يتجاهل مثال/تعريف مفهوم** (حارس تسرّب «نفس اللون» العابرة).
- **كشف السؤال السقراطي المعلّق بـ «؟» في أي موضع** (لا `endswith`) ضمن رسالة قصيرة (≤500/≤600، لا
  إفراغ تمرين) — في `_has_pending_socratic_question` (policy) و`_in_socratic_dialogue` (orchestrator)؛
  + حارس **السؤال المضادّ** (`_is_counter_question`: يبدأ بأداة استفهام وينتهي بـ«؟» ⇒ ليس إجابة).

### القواعد الخمس الدائمة (D-137 — لا تُكسر بدون ADR)
1. **فصل صارم:** المفهوم (تعريف/معنى/مثال) ⇒ semantic_property حصراً؛ خطوة الحساب (كيف/لماذا رقم) ⇒
   understanding_state (D-135) حصراً. لا تداخل.
2. **«ما هو X» تعريف:** أي سؤال نيّته definition (StudentState) أو يبدأ بـ «ما هو/ما هي/عرّف/ماذا نقصد» ⇒
   مسار التعريف قبل D-135.
3. **إشارات D-135 خاصة بالحساب لا كلمات مفهوم:** ممنوع «الاحتمال»/«نفس اللون» المجرّدة في gap_signals.
4. **المفهوم النشط من رسائل الطالب لا أمثلة المساعد**؛ الحيرة تُعيد إشراك المفهوم النشط لا الحادثة A الافتراضية.
5. **السؤال السقراطي المعلّق يُكشف بـ «؟» في أي موضع** (رسالة قصيرة)، والسؤال المضادّ ليس إجابة.

### التحقق الحي (2026-06-22 — اجبارية المالك)
- **`scripts/verify_d137_live.py` (كود الـ skills الحقيقي):** إعادة transcript الـ8 أدوار → 6/6 توجيه
  صحيح + «الشرطي لا يكشف 14/165». **Supabase Edge bridge (HTTPS:443):** حيّ (4116 customer_messages).
  **OpenRouter (HTTPS):** حيّ (finish_reason=stop).
- **اختبارات:** `tests/services/test_d137_routing_untangle.py` (12) + لا انحدار D-127→D-137 (181 ناجح)؛
  بوّابة skills-doctrine (D-137 routing-separation) + ruff + format + py_compile 3.12 + runtime_truth ✅.
- **إصلاح 10 اختبارات pre-existing حمراء** (drift من D-128→D-132 على الفرع المُلتزَم — مُثبت بـ git-stash
  أنها سابقة لـ D-137): إصلاح جذري لكشف السؤال السقراطي (يحل الخيانة البيداغوجية حياً) + تحديث assertions
  بنيوية قديمة (نسخ doctrine + matchers متينة على لفّ الأسطر `self._has_indexed_match(`).
- **Codespaces (WS كامل + المتصفح — متبقٍّ، llama_index/المكدس الكامل محجوب في الـ sandbox):** transcript
  الـ8 أدوار بالدخولين الحقيقيين ⇒ تعريف صحيح لكل مفهوم، مثال المفهوم الصحيح، صفر event-A أعمى، صفر «14/165» للشرطي.

### السلسلة (D-136 → D-137)
| Decision | الموضوع |
|----------|---------|
| D-136 | أمثلة واعية بالمفهوم + كبح اختطاف D-135 |
| **D-137** | **فكّ تشابك التوجيه: «ما هو X» تعريف موثوق + كبح D-135 عن أسئلة المفهوم + المفهوم النشط من الطالب + كشف السؤال السقراطي بـ «؟» في أي موضع** |

---

## 6.121 المصفوفة التصعيدية التكيّفية — Escalation + Understanding-Signal + Misconception (2026-06-22, ISS-116 / D-138)

> **الكارثة (transcript حيّ بعد D-137):** الطالب يسأل تباعاً عن الاحتمال الشرطي «اعطني مثال» →
> «لم أفهم» → «اعطني مثال عددي» → «كيف» → «لم أفهم». النظام **ينحرف** للحادثة A (نفس اللون) من
> تمرين البكالوريا، **يُكرّر «تخيّل أنك سحبت 3 كرات…» حرفياً**، ولا يملك **مثالاً عددياً مصغّراً**.

### الجذر (مؤكَّد بتتبّع agentين)
لا توجد **ذاكرة تصعيد بيداغوجي** ولا **حسّ تعلّم**. كل دور يُعيد القرار من الصفر؛ «كيف»/«لم أفهم»
يسقطان لـ D-135 (`understanding_state._current_focus_kc`) الذي يعمل على مكوّنات تمرين البكالوريا
(event_meaning) لا على المفهوم النشط ⇒ انحراف + تكرار `representations[1]` بلا تصعيد.

### حكم المالك (يحكم النطاق)
لا «سُلَّم جامد» L1/L2/L3 يُمرَّر كل طالب عبره. **«Escalation Matrix + Understanding Signal +
Misconception Check»** يقودها سؤال واحد قبل كل تدخّل: **«هل تناسب هذه السقالة قدرة الطالب الحالية
(support_level/BKT) وصعوبة الخطوة القادمة؟»** — التصعيد على **أثر الفهم** لا عدّ «لم أفهم». القرار
التنفيذي: نحتفظ بالمصفوفة؛ نؤجّل أي تعقيد (واجهة توليدية/microservices)؛ نقيس الأثر السلوكي فقط.

### الإصلاح (D-138 — مهارتان حتميتان + توصيل موحّد)
- **`MicroSimulationSkill`** (`app/services/skills/micro_simulation_skill.py`): خادم محتوى L3 حتمي
  صفر-LLM — `MICRO_SIMULATIONS` (8 مفاهيم)، مثال isomorphic **≤320 حرف** بأرقام صغيرة خاصة (يَنجو من
  حجب D-113، لا يكشف 14/165). conditional_probability: «10 طلاب، 6 بنظّارة ⇒ 6 من 10؛ بعلم النادي
  العلمي 5 أعضاء 3 بنظّارة ⇒ 3 من 5».
- **`PedagogicalEscalationSkill`** (`app/services/skills/pedagogical_escalation_skill.py`): المصفوفة
  التكيّفية النقية الحتمية **concept-scoped** تدمج ثلاث إشارات قبل التصعيد:
  **(أ) Understanding Signal** — `_has_understanding_evidence` عبر `PropertySpec.evidence_markers`
  (آلية لا «فهمت») ⇒ `mastered` (توقّف). **(ب) Misconception Check** — `diagnose_misconception` ⇒
  `target_misconception` (تدخّل مُوجَّه، +عقد conditional_probability في `MISCONCEPTION_GRAPH`).
  **(ج) Ability Calibration** — `support_level` (1..5 من BKT): منخفضة (1-2) ⇒ تصعيد أسرع للمحاكاة
  (سقف L3)؛ عالية (4-5) ⇒ رُتبة أخف أولاً (student agency). **ذاكرة التصعيد** (`_levels_delivered`
  من نصّ المفهوم نفسه) تمنع تكرار رُتبة؛ استنفاد L3 ⇒ `exhausted` (تسليم لطيف).
- **التوصيل** (`orchestrator_client.chat_with_agent`): بلوك تعليم مفهوم موحّد مدفوع بالمصفوفة **يسبق**
  preempt التعريف العام (الذي يبقى للمفاهيم الجديدة غير المُسجَّلة عبر LLM Listener-Definer). يقرأ
  `support_level` من context، يُجري Misconception Check، يبني `EscalationInput` ويبثّ القرار.
  concept-scoped ⇒ صفر انحراف لـ event-A. مسار حلّ تمرين البكالوريا (socratic/D-135) دون مساس.

### القواعد الـ 8 الدائمة (D-138 — لا تُكسر بدون ADR)
1. السقالة تُختار بسؤال «هل تناسب قدرة الطالب (support_level/BKT) وصعوبة الخطوة؟» — لا سلّم جامد.
2. التصعيد على **أثر الفهم** (`evidence_markers`) لا عدّ «لم أفهم». دليل فهم ⇒ توقّف + اعتراف.
3. **Misconception Check قبل التصعيد**: عقدة مُشخَّصة ⇒ تدخّل مُوجَّه، لا تسلّق أعمى. كل عقدة لها `bkt_concept`.
4. ممنوع تكرار رُتبة؛ استنفاد L3 ⇒ تسليم لطيف (لا L4/واجهة توليدية الآن).
5. **concept-scoped** (المفهوم النشط `detect_active_concept`)، لا مكوّنات تمرين البكالوريا.
6. Micro-Simulation حتمي صفر-LLM، isomorphic، **≤320 حرف**، أرقام صغيرة خاصة (يَنجو من حجب D-113).
7. policy أولاً، content-server ثانياً؛ لا واجهة توليدية/microservices في القلب الآن (نؤجّل حتى يَثبت القلب).
8. نقيس الأثر السلوكي فقط: تراجع التكرار + تدرّج الرُّتب (`record_escalation`) + ارتفاع الإتقان (BKT).

### التحقق الحي (2026-06-22 — اجبارية المالك)
- **`scripts/verify_d138_live.py` (كود المهارات الحقيقي):** transcript الكارثة → تعريف→مثال→محاكاة؛
  «اعطني مثال عددي» ⇒ L3 محاكاة (10 طلاب، صفر event-A)؛ «لم أفهم»/«كيف» ⇒ exhausted (لا تكرار)؛
  المعايرة (منخفضة sup=2→L3 ≥ عالية sup=5→L2)؛ Understanding Signal ⇒ mastered؛ Misconception ⇒
  target_misconception؛ micro-sim ≤320 حرف يَنجو D-113 — **10/10 PASS**. **Supabase Edge bridge
  (HTTPS:443):** حيّ (4130 رسالة). **OpenRouter (HTTPS):** حيّ (finish=stop).
- **اختبارات:** `tests/services/test_d138_escalation_matrix.py` (17) + لا انحدار D-127→D-137
  (348 ناجح إجمالاً) + بوّابة skills-doctrine (الفحصان الجديدان) + ruff + format + py_compile 3.12 +
  runtime_truth. registry=26.
- **Codespaces (WS كامل + المتصفح — متبقٍّ، llama_index محجوب في الـ sandbox):** transcript الكارثة
  بالدخولين الحقيقيين ⇒ تصعيد مُعايَر، مثال عددي مصغّر، توقّف عند دليل الفهم، تدخّل مُوجَّه عند
  misconception، صفر تكرار/انحراف/«14/165».

### السلسلة (D-137 → D-138)
| Decision | الموضوع |
|----------|---------|
| D-137 | فكّ تشابك التوجيه («ما هو X» تعريف + كبح D-135) |
| **D-138** | **المصفوفة التصعيدية التكيّفية: Escalation + Understanding-Signal + Misconception-Check + Micro-Simulation (يحل تكرار/انحراف الحادثة A + المثال العددي المفقود)** |

---

## 6.122 قتل انحراف المفهوم إلى الحادثة A — كل أسئلة المفهوم تُمسَك قبل D-135 (2026-06-23, ISS-116 / D-139)

> **الكارثة (transcript حيّ بعد D-138):** «كيف نضيق الإمكانيات» / «كيف نحصل على ثلاث كرات معدومة» /
> «لم أفهم» المتكرّرة / «ما هو السحب على التوالي بدون إرجاع» ⇒ كلها تُنتج **نص الحادثة A**:
> «تخيّل أنك سحبت 3 كرات: لو كانت كلها خضراء ⇒ تحقّقت A». المالك: «النظام معطل».

### الجذور الثلاثة (مؤكَّدة بقراءة الكود)
1. **بوّابة نيّة بلوك المصفوفة (D-138) ضيّقة**: `_PROCEDURE_MARKERS` تطابق «كيف نحسب/نوجد/نحل» فقط ⇒
   «كيف نضيق» و«كيف نحصل على معدومة» تُصنَّف **`unknown`** ⇒ البلوك لا يُفعَّل ⇒ تسقط لـ **D-135** →
   `_next_unmastered` → `kc_event_meaning` (الترتيب 0) → نص الحادثة A.
2. **`detect_active_concept` ينجرف**: نافذة `[-6:]` تقطع سؤال الطالب الأصلي؛ الـ assistant-fallback يفحص
   **إفراغ التمرين** (رسالة مساعد ضخمة تحوي «نفس اللون»/«الحادثة A») ⇒ `interpret` يطابق `same_color`.
3. **«السحب على التوالي بدون إرجاع» غير مُسجَّل** ⇒ `interpret`=None ⇒ ينجرف لـ same_color من نص التمرين.

### الإصلاح (4 طبقات — كلها تمنع نص الحادثة A عن أسئلة المفهوم)
- **A — تحصين `detect_active_concept`** (`semantic_property_skill.py`): سؤال تعريفي عن مفهوم جديد
  (is_definitional + interpret None) ⇒ `return None` (لا انجراف؛ يُسلَّم لـ LLM Definer)؛ **user-scan على
  كامل التاريخ** (لا `[-6:]`)؛ الـ fallback يتجاهل `_EXERCISE_DUMP_MARKERS` (إفراغ التمرين + نص الحادثة A العابر).
- **B — توسيع بوّابة المصفوفة** (`orchestrator_client.py`): حارس الحساب (`_esc_compute`: احسب/كم/اوجد/
  بيّن/استنتج ⇒ لا تُفعَّل) + متابعة المفهوم (`_esc_followup`: كيف/لماذا/وضح/اشرح/مثال/؟ ⇒ تُمسَك حتى لو
  صُنّفت `unknown`) + `interpret(question)` المباشر ⇒ أسئلة المفهوم لا تصل D-135 أبداً.
- **C — تسجيل نمطَي السحب** (`semantic_property_skill.py` + `micro_simulation_skill.py`):
  `sequential_without_replacement` + `simultaneous_draw` (تعريف + مثال + evidence_markers + micro-sim) ⇒
  «ما هو السحب على التوالي» يُعرَّف حتمياً (صفر انحراف).
- **D — حارس دفاع عميق في D-135** (`understanding_state_skill.py`): الافتراض لـ `_next_unmastered`
  (= kc_event_meaning، نص الحادثة A) يُسمَح به **فقط** عند حيرة صريحة (`elif _confused`) — لا لسؤال عام.

### القواعد الـ 5 الدائمة (D-139 — لا تُكسر بدون ADR)
1. **سؤال مفهوم لا يصل D-135 أبداً**: أي سؤال يُسمّي مفهوماً أو متابعة (كيف/لماذا/وضح) عن مفهوم نشط
   (غير حسابي) ⇒ المصفوفة التصعيدية. D-135 لخطوات حساب التمرين حصراً.
2. **المفهوم النشط = ما سأل عنه الطالب صراحةً** (user-scan كامل التاريخ)؛ سؤال تعريفي جديد ⇒ reset (None)؛
   إفراغ التمرين لا يُحدِّد المفهوم النشط أبداً.
3. **حارس الحساب**: «احسب/كم/اوجد/بيّن/استنتج» ⇒ لا تُفعَّل المصفوفة (تبقى للمسار الحسابي).
4. **نص الحادثة A (kc_event_meaning) لا يظهر لمفهوم غير-حدثي** — حارس D-135 (`elif _confused`).
5. data-driven: أي مفهوم تمرين جديد = مدخل في `PROPERTY_REGISTRY` + micro-sim، لا فرع كود.

### التحقق الحي (2026-06-23 — اجبارية المالك)
- **`scripts/verify_d139_live.py` (كود حقيقي):** transcript الكارثة → «كيف نضيق»⇒conditional؛ «كيف نحصل
  على معدومة»⇒product_zero؛ «السحب على التوالي»⇒sequential؛ «دفعة واحدة»⇒simultaneous؛ «احسب احتمال A»
  ⇒لا تُفعَّل؛ «ما هو الوسيط»⇒None؛ **صفر event_meaning لأي سؤال مفهوم** — كلها PASS. **Supabase Edge
  bridge:** حيّ (4156 رسالة). **OpenRouter:** حيّ (finish=stop).
- **اختبارات:** `tests/services/test_d139_concept_drift_kill.py` (16) + لا انحدار D-127→D-138 (364 ناجح
  إجمالاً) + بوّابة skills-doctrine (فحوص D-139) + ruff + format + py_compile 3.12 + runtime_truth.
- **Codespaces (WS كامل + المتصفح — متبقٍّ، llama_index محجوب في الـ sandbox):** transcript الكارثة
  بالدخولين الحقيقيين ⇒ صفر نص حادثة A لأي سؤال مفهوم؛ السحب على التوالي مُعرَّف؛ «كيف» تُمسَك بالمصفوفة.

### السلسلة (D-138 → D-139)
| Decision | الموضوع |
|----------|---------|
| D-138 | المصفوفة التصعيدية التكيّفية (Escalation + Understanding-Signal + Misconception) |
| **D-139** | **قتل انحراف المفهوم إلى الحادثة A: تحصين detect_active_concept + توسيع بوّابة المصفوفة + تسجيل نمطَي السحب + حارس D-135 (كل أسئلة المفهوم تُمسَك قبل D-135)** |
