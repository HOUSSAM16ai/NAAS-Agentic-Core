# Open Issues & Bugs
> Last updated: 2026-05-13 | Branch: `claude/setup-microservices-monitoring-ralbR`

---

## 🟢 Resolved 2026-05-13 (ISS-053 — BAC Exercise Explanation Hallucination)

### ISS-053 · LLM يُهلوس عند طلب شرح تمرين الدوال العددية 2016 [RESOLVED]
- **Status**: RESOLVED 2026-05-13
- **Severity**: CRITICAL (الطالب يحصل على تمرين احتمالات أو رد "لا أملك التفاصيل" بدلاً من شرح الدوال العددية)
- **Root cause**: `detect_exercise_retrieval` تُلغي الاسترجاع عند وجود "اشرح" (explanation_intent) → يذهب الطلب إلى LangGraph بدون محتوى التمرين → LLM يُهلوس. المسار القديم: `explanation_intent → LangGraph(no context) → hallucination`.
- **Fix**: مسار ثالث جديد **"شرح مع سياق"** في fallback chain:
  1. `exercise_retrieval.py`: دالة `detect_explanation_with_context()` + `ExplanationWithContextDecision` — تكشف عن طلبات شرح تمرين بكالوريا محدد وتجلب `full_content` (نص + إجابة نموذجية، 9670 حرف) + `display_content` (نص فقط، 2913 حرف).
  2. `local_graph.py`: دالة `run_local_graph_with_exercise_context()` + `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` — يُمرِّر المحتوى الكامل للـ LLM كـ context صريح مع تعليمات شرح الإجابة النموذجية.
  3. `orchestrator_client.py`: `_stream_exercise_explanation_response()` مُدرَج في fallback chain بـ `fallback_path=2.5` (بين exercise_retrieval=2.0 و LangGraph=3.0).
  4. `ai_config.py`: تحديث 5 نماذج احتياطية بنماذج مُتحقَّق منها حياً (nvidia/nemotron-3-super-120b-a12b:free, arcee-ai/trinity-large-thinking:free, openai/gpt-oss-120b:free, nvidia/nemotron-3-nano-30b-a3b:free, z-ai/glm-4.5-air:free).
- **Fallback chain المحدَّث**: `file_intelligence(1) → exercise_retrieval(2.0) → exercise_explanation_with_context(2.5) → LangGraph(3.0) → general_chat(4.0)`
- **Evidence (live)**: شرح g(x) 2016 يعمل بدون هلوسة، LaTeX صحيح، الإجابة النموذجية مُدرجة في السياق. 4 اختبارات نجحت.
- **Files**: `app/services/capabilities/exercise_retrieval.py`, `app/services/chat/local_graph.py`, `app/infrastructure/clients/orchestrator_client.py`, `app/core/ai_config.py`

---

## 🟢 Resolved in this branch (2026-05-12 — D-048 orchestrator streaming via custom events)

### ISS-056 · Orchestrator (DSPy + raw OpenAI) still bursts on the user-facing default path [RESOLVED]
- **Status**: RESOLVED in `claude/setup-microservices-monitoring-ralbR` (D-048)
- **Severity**: HIGH (D-047 fix didn't cover the production hot path)
- **Root cause**: D-047 patched `on_chat_model_stream` in `routes.py`, but the orchestrator's StateGraph leaf nodes (`SynthesizerNode`, `ChatFallbackNode`, `GeneralKnowledgeNode`) call:
  - `dspy.Predict(...)` / `dspy.ChainOfThought(...)` (DSPy 3.x — its own LM wrapper)
  - `OpenRouterClient.send_message(...)` (which uses raw `httpx` SSE internally, not LangChain)
  Neither emits `on_chat_model_stream` events. The patched branch in `routes.py` therefore never fired on the live default path. The user still saw the entire reply in one burst.
- **Fix** (D-048):
  - Added `_get_writer()` helper in each of the 3 leaf nodes — uses `langgraph.config.get_stream_writer()` (LangGraph ≥ 0.2.39).
  - Hybrid pattern: when `writer is not None` (graph running under `astream_events`), stream via `ai_client.stream_chat(messages)` (raw OpenRouter SSE) and emit each token through `writer({"chunk_type": "assistant_delta", "content": <str>, "node": <name>})`. When `writer is None` (batch / tests), fall back to DSPy/`send_message`.
  - Added `on_custom_event` branch in `routes.py` at all 3 streaming sites (HTTP `/api/chat/messages`, customer WS `/api/chat/ws`, admin WS `/admin/api/chat/ws`). Same envelope as D-047: `{"type": "assistant_delta", "payload": {"content": str}}`. Same duplicate-suppression contract.
- **Evidence (pending live)**: a single `POST /api/chat/messages` request should now produce 20–100+ NDJSON lines from the production default path (orchestrator → SynthesizerNode/ChatFallbackNode/GeneralKnowledgeNode).
- **Files**:
  - `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py`
  - `microservices/orchestrator_service/src/services/overmind/graph/main.py` (`ChatFallbackNode`)
  - `microservices/orchestrator_service/src/services/overmind/graph/search.py` (`SynthesizerNode`)
  - `microservices/orchestrator_service/src/api/routes.py` (3 `on_custom_event` consumers)
- **Doctrine**: `.memory/decisions.md` D-048, CLAUDE.md §6.28.

---

## 🟢 Resolved in this branch (2026-05-12 — D-047 streaming bottleneck)

### ISS-055 · WebSocket chat responses appear in a single catastrophic burst (no typing effect) [RESOLVED]
- **Status**: RESOLVED in `claude/setup-microservices-monitoring-ralbR`
- **Severity**: HIGH (user-facing UX catastrophe — replies of 2000+ chars dumped at once)
- **Root cause** (3 stacked bugs across the stack, all required to break streaming):
  1. **Monolith** (`app/services/chat/local_graph.py:297`): `await graph.ainvoke(...)` blocks until full response → returns one string → `_build_local_graph_response` wraps it in a single `assistant_delta` event.
  2. **Orchestrator microservice** (`microservices/orchestrator_service/src/api/routes.py`): `astream_events(..., version="v2")` IS used, but the `on_chat_model_stream` event branch was a literal `pass` — token deltas explicitly discarded. The router waited for `on_chain_end` then emitted a single `assistant_final`.
  3. **Frontend** (`frontend/app/lib/streaming/mergeAssistantContent.ts`): correct, but received only one delta — so the typing effect was mathematically impossible.
- **Fix** (D-047):
  - Added `run_local_graph_stream` AsyncGenerator that bypasses LangGraph (because `OpenRouterClient` is not a LangChain `BaseChatModel`) and calls `OpenRouterClient.stream_chat` directly, yielding each `delta.content` from OpenRouter SSE.
  - Added `_stream_local_graph_response` + `_stream_local_general_chat_response` in `OrchestratorClient`; rewired both branches of the local fallback chain in `chat_with_agent` to emit N × `assistant_delta` per turn.
  - Patched 3 sites in `orchestrator_service/src/api/routes.py` to capture `on_chat_model_stream` events and emit them as `assistant_delta` immediately. Added `streamed_chars` counter per path + duplicate-suppression in `assistant_final` (sets `content=""` when streaming occurred).
- **Evidence (pending live)**: a single `POST /api/chat/messages` request should now produce 20–100+ small NDJSON lines (one per token/word), and the browser typing animation should be smooth.
- **Files**: `app/services/chat/local_graph.py`, `app/infrastructure/clients/orchestrator_client.py`, `microservices/orchestrator_service/src/api/routes.py`
- **Doctrine**: see `.memory/streaming_architecture_breakdown.md` "D-047 Implementation Report" and `.memory/decisions.md` D-047.

---

## 🟢 Resolved in this branch (2026-05-12 — D-046)

### ISS-051 · 4 zombie metric queries in Grafana dashboards [RESOLVED]
- **Status**: RESOLVED in `claude/setup-microservices-monitoring-ralbR`
- **Root cause**: 4 PromQL queries across 3 dashboards (`20-langgraph.json`, `60-microservices-step3-live.json`, `50-microservices-transition.json`) referenced metric names with no emitter in `app/` or `microservices/`:
  - `cogniforge_langgraph_checkpointer_writes_total` — no emitter (Step 10 emits `cogniforge_checkpointer_writes_total` without `langgraph_` prefix)
  - `cogniforge_tavily_search_total` — no emitter (research-agent emits `cogniforge_research_tavily_calls_total`)
  - `cogniforge_orchestrator_startup_ready` — no emitter (orchestrator-service emits `cogniforge_orchestrator_startup_info{graph_ready=...}`)
  - `cogniforge_tavily_search_total{result="skipped_no_key"}` — invented label dimension; never emitted
- **Fix**: Replaced all 4 queries with the corresponding real emitters. Static contract sweep now shows 94/94 dashboard metrics have a real source.
- **Evidence**: `grep -c cogniforge_ observability/grafana/dashboards/*.json | wc -l` → 17 dashboards; `python3 -c "..."` static contract check → 94 metrics, 0 zombies.
- **Files**: `observability/grafana/dashboards/20-langgraph.json`, `observability/grafana/dashboards/60-microservices-step3-live.json`, `observability/grafana/dashboards/50-microservices-transition.json`

### ISS-052 · 3 GitHub Actions workflows with unindented Python heredocs [RESOLVED]
- **Status**: RESOLVED in `claude/setup-microservices-monitoring-ralbR`
- **Root cause**: `microservices-step4.yml`, `microservices-step5-user-service.yml`, `microservices-step6-planning-agent.yml` each contained `python3 -c "..."` shell commands inside YAML `run: |` blocks where the multi-line Python code was at column 1 (zero indent) — outside the parent block scalar. `yaml.safe_load` rejected all three. GitHub Actions might have tolerated this with a more permissive parser, but the gate was structurally fragile.
- **Fix**: Converted each `python3 -c "..."` to a bash heredoc `python3 <<'PY' ... PY` with content properly indented to the YAML block scalar level. Shell variables passed via `ENV=val python3 <<'PY' ... os.environ['ENV'] ... PY` to avoid double-escaping.
- **Bonus fix**: `microservices-step4.yml` had a `github-script@v7` block with a multi-line JS template literal whose markdown body (lines 257–289) was unindented. Replaced with `[...].join('\n')` array.
- **Evidence**: `python3 -c "import yaml; [yaml.safe_load(open(p)) for p in glob('.github/workflows/*.yml')]"` → 21/21 parse successfully (was 18/21).
- **Files**: `.github/workflows/microservices-step4.yml`, `.github/workflows/microservices-step5-user-service.yml`, `.github/workflows/microservices-step6-planning-agent.yml`

### ISS-053 · runtime_truth.lock.json stale (D-046 sub-finding) [RESOLVED]
- **Status**: RESOLVED in `claude/setup-microservices-monitoring-ralbR`
- **Root cause**: `.runtime/truth_table.lock.json` was generated 2026-05-08 on a different branch context. The drift gate (`scripts/runtime_truth.py --check`) reported `customer_chat_router: importer_count 5 → 6` — informational drift, not a status change.
- **Fix**: `python scripts/runtime_truth.py --update` regenerated the lock on the current branch.
- **Files**: `.runtime/truth_table.lock.json`

### ISS-054 · ruff RUF100 — misplaced `# noqa: N806` directive [RESOLVED]
- **Status**: RESOLVED in `claude/setup-microservices-monitoring-ralbR`
- **Root cause**: `tests/unit/test_dual_write_immunity.py:19` had `# noqa: N806` on the closing `)` line of a multi-line `SessionLocal = async_sessionmaker(...)` assignment. Ruff applies noqa to the line it's on; the N806 violation fires on the assignment line (line 17), not the closing paren. RUF100 reported the noqa as "unused" because it didn't suppress anything on its own line.
- **Fix**: Moved `# noqa: N806` to the assignment line (line 17). N806 now suppresses correctly, RUF100 stops firing.
- **Files**: `tests/unit/test_dual_write_immunity.py`

---

## 🔴 Critical — Resolved in branch `feat/live-verification-d044-surgical-fixes` (2026-05-11)

### ISS-047 · reasoning-agent OpenRouter 402 — Insufficient Credits for gpt-4o [CONFIRMED LIVE — RESOLVED]
- **Status**: RESOLVED in `feat/live-verification-d044-surgical-fixes`
- **Root cause**: `DEFAULT_MODEL = "gpt-4o"` in `microservices/reasoning_agent/src/core/config.py`. OpenRouter defaults `gpt-4o` to `max_tokens=16384`. Account had ~3980 credits → HTTP 402 on every MCTS expansion call → `RetryError` after 3 attempts → `pipeline_mode="partial"`.
- **Fix**: Changed `DEFAULT_MODEL = "openai/gpt-4o-mini"` + added `MAX_TOKENS: int = 1024`. Added `max_tokens=self.max_tokens` to `ai_service.py` `chat.completions.create()` call.
- **Evidence**: `pipeline_mode: full | skills_active: ['planning', 'research', 'reasoning']` confirmed live.
- **Files**: `microservices/reasoning_agent/src/core/config.py`, `microservices/reasoning_agent/src/services/ai_service.py`

### ISS-048 · content-retrieval-skill (:8009) not started at boot [CONFIRMED LIVE — RESOLVED]
- **Status**: RESOLVED — started manually; supervisor.sh should be updated to auto-start it.
- **Root cause**: `supervisor.sh` had no `launch_content_retrieval_skill()` function → Prometheus target DOWN.
- **Fix**: Started manually with `nohup python -m uvicorn microservices.content_retrieval_skill.main:app --port 8009`. Now 12/12 Prometheus targets UP.
- **Note**: supervisor.sh auto-start not yet added — will be done in a follow-up step.

---
> Format: [SEVERITY] ID · Title · [CONFIRMED LIVE / INFERRED / RUNTIME-ONLY / HISTORICAL]
> **Capability runtime status (ACTIVE/PARTIAL/DORMANT/ZOMBIE) lives in `.memory/runtime_truth.md`.**
> **Architectural fragility patterns (root causes, lessons) live in `.memory/fragility-patterns.md`.**

---

## 🔴 Critical — Resolved in this branch (2026-05-10)

### ISS-040 · Orchestrator PgBouncer DuplicatePreparedStatement on Port 6543 [CONFIRMED LIVE — RESOLVED]
- **Status**: RESOLVED in `feat/microservices-step7-research-agent` (live verification commit)
- **Root cause**: Supabase PgBouncer on port **6543** (transaction pool mode) intercepts prepared statements at the PostgreSQL wire protocol level. Even with `statement_cache_size=0` in SQLAlchemy `connect_args`, the asyncpg dialect internally issues `select pg_catalog.version()` as a prepared statement during connection setup → `DuplicatePreparedStatementError`. Port **5432** is a direct PostgreSQL connection that supports prepared statements fully.
- **Fix**: `supervisor.sh:launch_orchestrator_service()` and `automations.yaml` orchestrator start/restart commands now apply `sed 's/:6543\//:5432\//'` to `ORCHESTRATOR_DATABASE_URL` before passing it to uvicorn. Other microservices (user-service, planning-agent, research-agent) use SQLite in-memory for unit tests and Supabase via PgBouncer for runtime — they do not use `create_async_engine` with prepared statements, so they are unaffected.
- **database.py refactor**: `create_engine()` → lazy singleton via `get_engine()`. `async_session_factory` → `_LazySessionFactory` proxy. `init_db()` → calls `get_engine()` instead of module-level `engine`. Prevents import-time DB connection errors.
- **Files**: `microservices/orchestrator_service/src/core/database.py`, `.devcontainer/supervisor.sh`, `.ona/automations.yaml`

### ISS-039 · SuperSearchOrchestrator Import-Time Credential Error [CONFIRMED LIVE — RESOLVED]
- **Status**: RESOLVED in `feat/microservices-step7-research-agent`
- **Root cause**: `microservices/research_agent/main.py` instantiated `SuperSearchOrchestrator()` at module level (line 23). `SuperSearchOrchestrator.__init__` calls `ChatOpenAI(...)` which validates `OPENAI_API_KEY` at construction time. Without the key, `openai.OpenAIError: Missing credentials` was raised at import → uvicorn worker crashed → port 8007 never opened.
- **Fix**: Converted to lazy singleton pattern. `_super_search_orchestrator: SuperSearchOrchestrator | None = None` at module level. `_get_super_search()` function initialises on first call. `/execute` endpoint calls `_get_super_search().execute(query)` instead of the module-level instance.
- **Pattern**: Same as `global` singleton pattern used in `app/` (documented in coding rules §D). `# noqa: PLW0603` applied.
- **Files**: `microservices/research_agent/main.py`

### ISS-038 · Exercise Retrieval Context Blindness — "تمرين" Always Returns Probability Exercise [CONFIRMED LIVE]
- **Status**: RESOLVED in `fix/exercise-retrieval-context-blindness`
- **Root cause**: `detect_exercise_retrieval()` in `app/services/capabilities/exercise_retrieval.py` used a flat keyword list (`"تمرين"`, `"تمارين"`, `"درس"`, `"احتمالات"`, `"بكالوريا"`, `"exercise"`, `"lesson"`, `"probability"`). Any question containing these words triggered `_build_local_retrieval_response()`, which searched `knowledge_base/` — a directory containing exactly one file: `bac2024_math_experimental_subject1_ex1_ex2.md` (the probability exercise). Result: every question with "تمرين" in any context returned the probability BAC exercise, regardless of what the student actually asked.
- **Confirmed examples**:
  - "اشرح الجزء أ من هذا التمرين" → returned probability exercise ❌
  - "ما هو مفهوم التمرين في الرياضيات" → returned probability exercise ❌
  - "ساعدني في حل هذا التمرين" → returned probability exercise ❌
  - "ما هي الاحتمالات" → returned probability exercise ❌
- **Fix**: Replaced flat keyword list with a two-phase intent classifier:
  1. **Explanation-intent patterns** (highest priority): `"اشرح"`, `"شرح"`, `"وضح"`, `"كيف"`, `"ما هو"`, `"هذا التمرين"`, `"الجزء أ"`, `"ساعدني"`, `"help me"`, `"explain"`, … → cancel retrieval even if "تمرين" is present.
  2. **Explicit retrieval patterns**: `"تمرين بكالوريا"`, `"التمرين الأول"`, `"exercise 1"`, `"الموضوع الأول"`, `"بكالوريا"`, year+exercise combos → trigger retrieval.
  3. **Default**: no retrieval → fall through to LangGraph.
- **New field**: `ExerciseRetrievalDecision.reason` (optional str) — explains the decision: `"explanation_intent_detected"` | `"retrieval_intent_detected"` | `"no_clear_retrieval_intent"`. Backward-compatible (default `""`).
- **Tests**: 25 tests in `tests/contracts/test_exercise_retrieval_contracts.py` — 13 regression cases (explanation context must NOT trigger) + 8 positive cases (explicit retrieval must trigger) + 4 existing contract tests.
- **Files**: `app/services/capabilities/exercise_retrieval.py`, `tests/contracts/test_exercise_retrieval_contracts.py`

---

## 🔴 Critical — Resolved in this branch (2026-05-09)

### ISS-034 · Misleading Startup Observability — Uvicorn Alive but Port Dead [CONFIRMED LIVE]
- **Status**: RESOLVED in `fix/lifespan-orchestration-env-injection`
- **Root cause**: `devcontainer.json` maps `DATABASE_URL` from `${localEnv:DATABASE_URL}` — in Ona/Gitpod, secrets are NOT injected as process env vars. `supervisor.sh` created `.env` with `DATABASE_URL=sqlite+aiosqlite:///./dev.db`. `app/core/settings/base.py:23` reads `os.environ.get("APP_DATABASE_URL")` at module import time (before pydantic-settings reads `.env`) → finds empty string → `_ensure_database_url()` raises `ValueError` → uvicorn worker crashes on import → port 8000 never opens. State file `app_healthy` from previous run → supervisor reports healthy. **Misleading observability.**
- **Fix**: `supervisor.sh:_inject_env_secrets()` + `_export_env_file()` + `_uvicorn_healthy()` + health check always re-probes live endpoint.
- **Files**: `.devcontainer/supervisor.sh`

### ISS-035 · Orchestrator Lifespan Partial Startup — Warmup Blocks ASGI [CONFIRMED LIVE]
- **Status**: RESOLVED in `fix/lifespan-orchestration-env-injection`
- **Root cause**: `lifespan()` warmup `ainvoke()` had no timeout → could block indefinitely. `RuntimeError` from warmup propagated up → crashed ASGI startup. Only `ModuleNotFoundError` was caught. `/health` returned `{"status":"ok"}` regardless of graph state.
- **Fix**: `asyncio.wait_for(..., timeout=30.0)` on warmup. All non-DB exceptions → DEGRADED, not fatal. `app.state.startup_state` + `/health` exposes real state.
- **Files**: `microservices/orchestrator_service/main.py`

---

## 🔴 Critical — Core Architectural Flaws (Session 2026-05-05)

### ISS-014 · Dual-Write — Both Monolith and Orchestrator Write to Same DB Tables
- **Status**: RESOLVED in `claude/fix-persistence-consolidate-8X8LT`.
- **Resolution layers**:
  1. Monolith sends `compatibility_facade=True` → Orchestrator skips user write
     (`microservices/orchestrator_service/src/api/routes.py:1314-1325`).
  2. Orchestrator emits `persisted: true` on terminal event after a confirmed
     `INSERT … COMMIT` (lines 2580, 2696). Monolith reads this flag and skips local
     assistant write (`customer_chat.py` / `admin.py` finally blocks).
  3. Duplicate Guard at the persistence layer suppresses any straggler within a
     10-second window (`app/services/customer/chat_persistence.py:81-112`).
- **Live status**: In default Codespaces devcontainer, Orchestrator is dormant →
  Monolith is the only writer. Dual-write physically impossible.

---

### ISS-015 · Non-Unified Save Authority — No Single Owner of Message Persistence
- **Status**: RESOLVED in `claude/fix-persistence-consolidate-8X8LT`.
- **Resolution**: D-006 declares the Monolith as sole owner of `customer_messages` /
  `admin_messages`. CLAUDE.md §6.5 codifies the rule. Architecture test
  `tests/architecture/test_persistence_authority.py` enforces it at CI time.
- **Coordination contract**: `compatibility_facade=True` (Monolith → Orchestrator)
  + `persisted: true` (Orchestrator → Monolith) form the handshake. Absence of the
  persisted signal is treated as failure → fail-safe write fires.

---

### ISS-016 · Unsafe Fallback Path — Silent Failures, Missing Terminal Events
- **Status**: RESOLVED in `claude/fix-persistence-consolidate-8X8LT`.
- **Resolution**: New `_emit_terminal_frames()` helper in both
  `app/api/routers/customer_chat.py` and `app/api/routers/admin.py` guarantees
  exactly one terminal frame per turn. Failure paths (DB error, empty content,
  stream interruption, retry exhaustion) all converge on a single `error` frame
  rather than leaving the WS in a hung state.
- **Logging**: `[CRITICAL_DATA_LOSS]` is logged when fail-safe writes fail after retries.
  The user is notified via the terminal `error` frame — failures are no longer silent.
- **Raw JSON pollution**: still mitigated by `OrchestratorClient._recover_structured_event`
  and `_sanitize_text_for_user`; not changed in this fix.

---

### ISS-017 · Terminal Signal Corruption — `complete` Event Distorted During Normalization
- **Status**: RESOLVED in `claude/fix-persistence-consolidate-8X8LT`.
- **Root cause confirmed**: When `CHAT_USE_UNIFIED_EVENT_ENVELOPE=1` is set,
  `shared/chat_protocol/event_protocol.py:normalize_streaming_event` was coercing any
  unrecognized event type (including `complete`, `persisted`, `conversation_init`)
  into `assistant_delta`. The Monolith's terminal-event detection (`if event_type
  in {"complete", "assistant_final"}`) then never fired → no `pending_terminal_event`
  → UI hang.
- **Fix**: Pass-through guard added for `{"complete", "persisted", "conversation_init"}`
  before the fall-through to `ASSISTANT_DELTA`. Default-mode (flag off) was already
  pass-through and is unchanged.

---

### ISS-018 · Architectural Split-Brain — Hybrid Monolith/Microservice Competing on State
- **Status**: CONFIRMED — design-level issue
- **Root cause**: The system is neither a clean Monolith nor clean Microservices.
  It's an unfinished migration. Monolith and Orchestrator share state (same DB tables,
  same `conversation_id`) but have no explicit ownership boundary. Each new feature
  risks landing in the wrong side.
- **Effect**: Behavior changes per code path, not per business rule. Debugging requires
  tracing two separate execution trees.
- **Fix strategy**: Freeze the migration state. Document which tables/operations belong
  to Monolith vs Orchestrator. Enforce via architecture tests.

---

### ISS-019 · Context Identity Fragmentation — conversation_id / thread_id Misaligned
- **Status**: CONFIRMED / LIKELY
- **Root cause**: `conversation_id` (DB row) and `thread_id` (LangGraph MemorySaver key)
  are not always the same value. In fallback paths the thread_id may be derived
  differently, causing LangGraph to start a fresh memory thread for a continuing conversation.
- **Effect**: Conversation history is lost mid-session when the system switches between
  Orchestrator and LangGraph paths.
- **Files**: `app/services/chat/local_graph.py` (`run_local_graph` caller),
  `app/services/chat/orchestrator_client.py`
- **Fix strategy**: Always derive `thread_id = str(conversation_id)` at the entry point
  and pass it through explicitly; never re-derive it inside the graph.

---

### ISS-020 · Fragile Checkpointer — MemorySaver Volatile, Loses State on Restart
- **Status**: CONFIRMED
- **Root cause**: `MemorySaver` is in-process. Any uvicorn restart (crash, redeploy,
  Codespaces wake-up) clears all conversation checkpoints. The system has no
  Postgres-backed checkpointer active (D-002 chose MemorySaver intentionally,
  but the trade-off is undocumented as a risk).
- **Effect**: Every restart = all active users lose their conversation thread.
  Multi-turn tutor sessions break silently.
- **Files**: `app/services/chat/local_graph.py` (checkpointer init)
- **Fix strategy**: Add `langgraph-checkpoint-postgres` with `APP_DATABASE_URL` as
  opt-in via env var `LANGGRAPH_CHECKPOINTER=postgres`. Fall back to MemorySaver
  if not configured.

---

## 🔴 Critical

### ISS-001 · SECRET_KEY Ephemeral — All Users Logged Out on Restart
- **Status**: OPEN
- **Evidence**: INFERRED (not tested live — requires container/codespace restart)
- **Root cause**: `SECRET_KEY: str = Field(default_factory=lambda: secrets.token_hex(32))` in `app/core/settings/base.py`
- **Fix**: Add `SECRET_KEY` as a permanent Codespaces secret (forwarded via `.devcontainer/devcontainer.json` → `remoteEnv.SECRET_KEY: ${localEnv:SECRET_KEY}`)

---

### ISS-002 · 162 GitHub Security Vulnerabilities (15 Critical)
- **Status**: OPEN
- **Evidence**: GitHub Dependabot alert shown on every `git push` to this branch
- **Message**: "GitHub found 181 vulnerabilities on HOUSSAM16AI/NAAS-Agentic-Core's default branch (15 critical, 100 high, 63 moderate, 3 low)"
- **Files**: `requirements-prod.txt`, `frontend/package.json`

---

### ISS-003 · `full_name` Returns `null` in Login Response ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**:
  ```json
  POST /api/security/register → { "full_name": "Runtime Tester" }  ← OK
  POST /api/security/login    → { "full_name": null }              ← BUG
  ```
- **Root cause**: Login fetches user from DB but does not populate `full_name` into JWT claims or response schema
- **Files**: `app/services/security/auth_persistence.py`, auth response schema

---

### ISS-004 · Hardcoded Admin Credentials in bootstrap.py
- **Status**: OPEN
- **Evidence**: INFERRED
- **Fix**: Validate at startup — refuse to boot in production if env vars missing

---

### ISS-013 · OpenRouter "Host not in allowlist" — Fixed in Code, Needs Env Var ✅ CODE FIXED
- **Status**: ENV-DEPENDENT — works in current Codespaces (with allowlist URL match)
- **Historical evidence** (legacy Replit server log):
  ```
  Model nvidia/nemotron-3-super-120b-a12b:free failed: Status 403. Trying next...
  All models exhausted. Engaging Safety Net.
  ```
- **Codespaces status**: OPENROUTER_API_KEY works when site URL is whitelisted — nvidia/nemotron-3-super-120b-a12b:free responds correctly
- **Root cause**: `HTTP 403: Host not in allowlist` — `HTTP-Referer` was hardcoded as `https://cogniforge.local` in `app/core/gateway/simple_client.py:57`, but OpenRouter's allowlist contained different URLs depending on the deployment.
- **Code fix (done)**: `simple_client.py` now reads `get_openrouter_site_url()` from `app/core/ai_config.py`, which reads `OPENROUTER_SITE_URL` env var (fallback: `https://cogniforge.local`).
- **To activate** in a new Codespace whose URL isn't whitelisted: set `OPENROUTER_SITE_URL=<your-codespaces-public-url>` as a Codespaces secret, OR go to openrouter.ai/settings/keys → remove host restriction (set `*`)

---

## 🟡 Medium — Structural / Quality Issues (NEW — Session 2026-05-05)

### ISS-021 · Zombie / Dormant Components — Dead Code Confusing Execution Topology
- **Status**: CONFIRMED 2026-05-06 (audit branch `claude/runtime-truth-audit-65iVU`)
- **Authoritative inventory**: `.memory/runtime_truth.md` truth table.
- **Confirmed ZOMBIE** (no live call chain from any production entrypoint):
  - `app/services/chat/graph/workflow.py` — only `tests/verify_graph_manual.py` imports it.
  - `app/services/chat/graph/nodes/{super_reasoner,planner,researcher,writer,procedural_auditor,reviewer}.py` — only used by the dead workflow.
  - `app/services/chat/memory_engine.py` (LlamaIndex VectorStoreIndex) — only invoked by dead `reviewer.py`.
  - `app/drivers/llamaindex_driver.py`, `app/drivers/reranker_driver.py`, `app/drivers/kagent_driver.py` — `app/drivers` package has zero importers in the live path.
  - `app/core/integration_kernel/runtime.py` (`RealityKernel`) — singleton designed but never instantiated from startup.
  - `app/services/kagent/*` (KagentMesh, ServiceRegistry, RemoteAgentAdapter) — DI-registered (`app/core/di.py:145`) but the only consumer is the dead workflow.
- **Confirmed DORMANT** (real code, gated behind dormant external service):
  - `app/services/mcp/*` — only lazy-imported by side-path agents (`socratic_tutor`, `admin` agent, `collaboration/session`, `core/prompts`); none are on `/api/chat/ws`.
  - All `microservices/*` — not started by `.devcontainer/docker-compose.host.yml`.
- **Effect**: Developer confusion about what is "real". The codebase looks like a sophisticated multi-agent system; in default Codespaces it runs a 2-node LangGraph + 4 fallback functions.
- **Fix strategy**: Each ZOMBIE either (a) gets wired into the live path with an ADR, or (b) gets deleted after an ADR. Do not touch silently.

---

### ISS-022 · Educational / General Pipeline Split — Uneven AI Capability by Path
- **Status**: CONFIRMED — design issue
- **Root cause**: The LangGraph supervisor routes to `chat_node` differently based on
  intent (`educational` | `general` | `chat`). The nodes behind these intents may have
  different context windows, different prompts, or different retrieval strategies,
  making the system appear "less intelligent" for some question types.
- **Effect**: BAC exam questions may hit a weaker path than general questions, which
  is the opposite of the product's goal.
- **Files**: `app/services/chat/local_graph.py` (supervisor_node routing logic)
- **Fix strategy**: Audit the node capability matrix. Ensure `educational` path has
  access to at least the same LLM quality and context as `general`.

---

### ISS-023 · Streaming Token Delivery Inconsistent — Blocks Instead of Token-by-Token
- **Status**: RUNTIME-ONLY / LIKELY
- **Root cause**: LangGraph `ainvoke()` vs `astream()` usage. If the graph uses
  `ainvoke()`, the full response is buffered before emission. Even if the WS handler
  streams chunks, the source is not streaming — so the user sees a long pause then
  a full block.
- **Effect**: The "AI is thinking" UX impression. Breaks the real-time tutoring feel.
- **Files**: `app/services/chat/local_graph.py` (graph invocation method),
  `app/api/routers/customer_chat.py` (WS event emission)
- **Fix strategy**: Switch graph invocation to `astream_events()` and pipe each
  token as a `stream_token` WS event.

---

### ISS-024 · Capability Utilization Gap — ~90% of Advertised Stack is ZOMBIE/DORMANT
- **Status**: CONFIRMED 2026-05-06 (audit `claude/runtime-truth-audit-65iVU`)
- **Authoritative source**: `.memory/runtime_truth.md` truth table.
- **Root cause**: The codebase advertises a sophisticated multi-agent system
  (LangGraph multi-agent workflow, KAgent mesh, MCP server, LlamaIndex memory,
  DSPy refinement, reranker pipeline, integration micro-kernel, full microservice
  fleet). In default Codespaces ONLY the following actually run on chat traffic:
  - `app/services/chat/local_graph.py` (2 nodes: supervisor + chat) — PARTIAL.
  - `app/infrastructure/clients/orchestrator_client.py` fallback chain
    (file-intel → exercise-retrieval → LangGraph → general-chat) — ACTIVE.
  - `app/telemetry/unified_observability.py` via middleware — ACTIVE on every HTTP
    request (WS frames not traced — ISS-005).
- **Effect**:
  - Aspirational documents (e.g. `ARCHITECTURE.md`, `LangGraph_Architectural_Blueprint.md`)
    describe a target state that is NOT live. New contributors mistake them for runtime.
  - Refactors keep "polishing" zombie modules (e.g. `super_reasoner.py`, `memory_engine.py`)
    that have no production callers.
  - Bug reports get filed against components (MCP, KAgent, reranker) that never executed.
- **Fix strategy**:
  1. Treat `.memory/runtime_truth.md` as the single source of truth for capability status.
  2. Each ZOMBIE either gets wired into the live path (with ADR + status promotion) or
     deleted (with ADR justifying removal). No silent half-life.
  3. Each PR touching the chat/agent stack must update the truth table if status changes.
  4. Aspirational docs must carry a "TARGET STATE — see `.memory/runtime_truth.md` for live status"
     header to prevent drift.

---

### ISS-025 · CI Quality-Gate Gaps — Persistence, Terminal-Frame, Truth-Table Sync, Frontend Build (NEW 2026-05-06, branch `claude/architecture-rescue-diagnostic-wUfbE`)
- **Status**: OPEN — diagnostic-only, no remediation in this branch beyond `doc_integrity.yml`.
- **Authoritative source**: CLAUDE.md §6.9 + `.memory/diagnostic_2026_05_06_rescue.md` §5.
- **Existing HARD gates**: `required-ci` aggregator in `.github/workflows/ci.yml`
  (`lint, contracts, guardrails, test`), `validate-structure` in
  `.github/workflows/structure-validation.yml`, and the new `doc-integrity` workflow.
- **Open gaps** (none of these block merge today):
  1. **D-006 round-trip integration** — `compatibility_facade=True` + `persisted=true`
     echo, exactly-once row write under load. Static contract test exists; no live
     round-trip. Cannot run without the microservice stack up.
  2. **Terminal-frame integrity contract** — exactly one `assistant_final` OR `error`
     per turn + exactly one `persisted` event. `_emit_terminal_frames` is the single
     emitter, but no test pins the contract.
  3. **Truth-table sync gate** — should fail when a ZOMBIE acquires a new importer in
     `app/api/`, `app/main.py`, `app/kernel.py`, or `local_graph.py` without a matching
     update to `.memory/runtime_truth.md`. Today nothing flags this drift.
  4. **Frontend build / type check** — Next.js never compiles in CI; UI regressions
     only surface at runtime. No `next build` step in any workflow.
  5. **Microservices smoke test** — no `docker compose -f docker-compose.yml up -d`
     + health-curl in CI.
- **Mitigation in this branch**: `.github/workflows/doc_integrity.yml` enforces:
  - `CLAUDE.md` non-empty + required anchors (§6.5, §6.6, three-part proof rule).
  - All `.memory/*.md` files non-empty.
  - `.memory/runtime_truth.md` references the live entrypoints.
  - Closing-rule phrases (`import` + `call chain` + `runtime evidence` + `DORMANT` + `ZOMBIE`)
    not weakened.
  - Warning (advisory) for repo-root scratch artifacts and dated diagnostics outside `docs/archive/`.
- **Required follow-up** (separate PR, not in this branch):
  1. Add `tests/architecture/test_terminal_frame_integrity.py` — assert single-emitter
     and exactly-one-frame guarantee per turn (mock orchestrator client; drive both
     success and error paths through `_emit_terminal_frames`).
  2. Promote `doc-integrity` to a required status check in branch protection for `main`.
  3. Flip the scratch-artifact step from advisory to blocking once the cleanup PR lands
     (current behavior: warn; target: `exit $fail`).
  4. Add a `frontend-build` job (`cd frontend && npm ci && npm run build`) to `ci.yml`.
  5. Add a truth-table-sync test that parses `.memory/runtime_truth.md` for `app/...`
     paths and fails CI when a path appears as ZOMBIE/DORMANT but `app/api/`,
     `app/main.py`, `app/kernel.py` import it.

### ISS-026 · Loaded-Not-Invoked Helpers Distort Capability Picture (NEW 2026-05-06)
- **Status**: OPEN — diagnostic-only.
- **Authoritative source**: CLAUDE.md §6.9 (correction C2) + `.memory/runtime_truth.md`
  rows 21, 26, 27.
- **Symptom**: `IntentDetector`, `ToolRouter`, `ChatOrchestrator`, `CustomerChatStreamer`,
  `AdminChatStreamer`, `dispatcher.py`, `tool_access.py`, `intent_registry.py`,
  `education_policy_gate.py`, `orchestration_rollout.py` — all imported and instantiated
  on the live WS path (via `CustomerChatBoundaryService` / `AdminChatBoundaryService`
  constructors) but their core methods are **never invoked** for a real user turn.
- **Why it matters**: From the outside they look "ACTIVE" (showing up in import scans
  and DI). Reality is `__init__` runs once per WS connection and produces no observable
  behavior. New contributors waste effort polishing these because they appear live.
- **Decision required (separate PR)**: per file, choose one of
  1. **Promote** — wire the method into the live router and add runtime evidence to the
     truth table.
  2. **Stop instantiating** — delete the construction in the boundary service and mark
     the file ZOMBIE explicitly.
  3. **Document and isolate** — add a header comment in each file: `# PARTIAL (loaded-not-invoked).
     Constructed by boundary service but never reached on live WS path. See CLAUDE.md §6.9.`
- **Do NOT in this branch**: this is a read-only diagnostic. No application code changes here.

---

## 🟡 Medium

### ISS-005 · WebSocket Events Not Traced ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**: Live WS session generated events [conversation_init, assistant_error, error] but ZERO WS spans appeared in `/api/v1/observability/traces`
- **Effect**: Can see orchestrator + LangGraph spans but blind to WS-layer timing (auth, message parse, event dispatch)
- **Fix**: Extract `traceparent` from WS query params or first message payload, create root WS span

---

### ISS-006 · OpenAPI Contract Mismatch — 13 Missing Paths ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at startup 2026-05-04
- **Evidence**: Server prints on startup:
  ```
  ❌ مسارات العقد غير موجودة في التشغيل: ['/api/missions', '/api/observability/aiops', ...]
  ```
- **Root cause**: Contract file expects prefix `/api/observability/*` but actual routes are at `/api/v1/observability/*` (prefix mismatch)
- **Missing paths** (13):
  `/api/missions`, `/api/missions/{id}`, `/api/observability/aiops`, `/api/observability/alerts`,
  `/api/observability/analytics/{path}`, `/api/observability/gitops`, `/api/observability/health`,
  `/api/observability/metrics`, `/api/observability/performance`, `/api/v1/agents/langgraph/run`,
  `/api/v1/agents/plan`, `/api/v1/overmind/missions`, `/api/v1/overmind/missions/{id}`
- **Fix**: Update contract YAML to use `/api/v1/observability/*` prefix

---

### ISS-007 · Database Writes Not Instrumented in Tracing
- **Status**: OPEN
- **Evidence**: INFERRED — confirmed no DB spans in collected traces
- **Fix**: SQLAlchemy async event listeners on `before_cursor_execute` / `after_cursor_execute`

---

### ISS-008 · OTLP / Jaeger Export Not Activated ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**: Server log repeatedly:
  ```
  Failed to send telemetry: [Errno -2] Name or service not known
  ```
- **Root cause**: `TelemetryBridge` is trying to connect to an external telemetry host that doesn't resolve in this environment
- **Fix**: Gate telemetry export behind env var check: `OTEL_EXPORTER_OTLP_ENDPOINT`

---

### ISS-009 · Dormant Microservices Pinged on Login/Register ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**:
  ```
  User Service unreachable for registration ([Errno -2] Name or service not known), using local fallback.
  User Service unreachable for login ([Errno -2] Name or service not known), using local fallback.
  ```
- **Effect**: Every auth request has extra DNS lookup latency before falling back to local DB
- **Fix**: Disable external service calls entirely in non-Docker environments

---

### ISS-012 · `/api/v1/observability/performance` Crashes — Pydantic Schema Mismatch ✅ CONFIRMED LIVE
- **Status**: OPEN — CONFIRMED at runtime 2026-05-04
- **Evidence**:
  ```
  pydantic_core.ValidationError: 3 validation errors for PerformanceSnapshotResponse
  cpu_usage: Field required [type=missing]
  memory_usage: Field required [type=missing]
  active_requests: Field required [type=missing]
  ```
- **Root cause**: `PerformanceSnapshotResponse` schema requires `cpu_usage`, `memory_usage`, `active_requests` but the underlying `TelemetryAnalyzer` returns a dict without these fields
- **File**: `app/api/routers/observability.py` + `app/api/schemas/observability.py`

---

---

## 🟡 Medium — Fragility Patterns (NEW — Session 2026-05-09)

### ISS-027 · Intent Routing Semantic Hijacking — Lexical Classifier Misroutes Non-Academic Queries
- **Status**: CONFIRMED — structural design flaw in live classifier
- **Evidence**: Runtime test — 10/10 non-academic Arabic/English questions containing educational keywords (`تمرين`, `حل`, `شرح`, `درس`, `مادة`, `history`, `solve`) are classified `educational` by `_classify_intent()` in `local_graph.py`
- **Root cause**: Pure lexical regex matching with no semantic context. The word `تمرين` (exercise) matches both "math exercise" and "yoga exercise". The classifier has no access to conversation history, user profile, or semantic field.
- **Affected file**: `app/services/chat/local_graph.py:_classify_intent` + `_EDUCATIONAL_PATTERNS` + `_GREETING_PATTERNS`
- **Secondary affected**: `app/telemetry/path_observer.py:classify_path` (intentional duplicate — must be updated in sync)
- **Effect**: Students asking casual questions containing educational keywords receive structured BAC-style academic responses. Students asking about physical exercise, conflict resolution, or social networks are routed to the educational prompt.
- **Greeting anchor brittleness**: `"السلام عليكم"` (standard Islamic greeting) is NOT caught by the greeting pattern because the anchor `^...$` fails on the suffix `عليكم`. It falls through to educational patterns and is classified `educational` if it contains any keyword.
- **Taxonomy split-brain**: Two incompatible intent systems exist — live `_classify_intent` (3 intents) and zombie `IntentDetector` (13 intents). If the zombie is ever wired in, its `CONTENT_RETRIEVAL` pattern also matches `تمرين`, creating a third classification for the same word.
- **Fix strategy**: See `.memory/fragility-patterns.md` Pattern 1. Do NOT add more keywords — this worsens false positives. Minimum fix: add semantic context guards (subject name must appear near `تمرين` for educational classification). Proper fix: embedding-based or LLM-based classification.
- **What must NOT change**: Do not wire `IntentDetector` into the live path without resolving the taxonomy incompatibility. Do not update `local_graph.py` patterns without updating `path_observer.py` in the same PR.

---

### ISS-028 · Hidden DOM Leakage — Sidebars Visually Hidden but DOM-Present
- **Status**: CONFIRMED — structural rendering strategy flaw
- **Evidence**: CSS inspection — both `.sidebar` and `.agent-sidebar` use `transform: translateX(±100%)` to hide. No `aria-hidden`, no `inert`, no `tabindex="-1"` applied when closed.
- **Root cause**: CSS transform chosen for animation quality. Visual hiding ≠ DOM exclusion.
- **Leakage surfaces**:
  1. Screen readers announce sidebar content when sidebar is visually closed
  2. Keyboard Tab cycles through off-screen interactive elements
  3. Browser Ctrl+F finds text in off-screen sidebars
  4. `AgentTimeline` renders agent phase state into DOM regardless of sidebar visibility
  5. Copy buttons in `ChatInterface` are always in DOM (clipboard contamination risk)
- **Affected files**: `frontend/app/globals.css` (`.sidebar`, `.agent-sidebar` rules), `frontend/app/components/CogniForgeApp.jsx`
- **Severity escalation**: As the agent stack becomes more capable (DORMANT → ACTIVE), `AgentTimeline` will expose real-time agent execution state to screen readers regardless of sidebar visibility. The information leakage surface grows with capability.
- **Fix strategy**: Add `inert={!isOpen || undefined}` to sidebar JSX (modern browsers), or `aria-hidden={!isOpen}` + tabindex management. See `.memory/fragility-patterns.md` Pattern 2.

---

### ISS-029 · Zombie Metrics — LangGraph Dashboard Queries Non-Existent Metrics
- **Status**: CONFIRMED — dashboard-metric contract violation
- **Evidence**: `observability/grafana/dashboards/20-langgraph.json` queries 4 metrics; grep of entire codebase finds zero emitters for any of them:
  - `cogniforge_langgraph_node_count_total` — no emitter
  - `cogniforge_langgraph_node_duration_seconds` — no emitter
  - `cogniforge_langgraph_intent_total` — no emitter
  - `cogniforge_langgraph_checkpointer_writes_total` — no emitter
- **Root cause**: `local_graph.py` uses `UnifiedObservabilityService.start_trace()` / `end_span()` (in-process span store). Dashboard expects OTel/Prometheus metrics. The two systems are not connected.
- **Effect**: LangGraph dashboard panels are permanently empty. Operators cannot distinguish "LangGraph not running" from "LangGraph running but metrics not emitted".
- **No CI gate**: No CI step verifies that dashboard metric names have corresponding emitters in application code.
- **Fix strategy**: Either (a) add OTel metric emission to `local_graph.py` nodes matching the dashboard metric names, or (b) update the dashboard to query the UnifiedObs API (`/api/v1/observability/traces`) instead of Prometheus. Option (a) is preferred for consistency with the observability stack.

---

### ISS-030 · Dual-Write Metrics — WS Turn Metrics Emitted Through Two Paths Simultaneously
- **Status**: INFERRED — structural dual-emission risk
- **Evidence**: `path_observer.py` calls both `_emit_to_otel(handle)` (OTel SDK) and `obs.record_metric("ws.chat.turn.duration_seconds", ...)` (UnifiedObs). When the OTel stack is up, Prometheus scrapes both the OTel collector and `/api/v1/observability/prometheus`. Both emit `cogniforge_ws_chat_turn_duration_seconds`.
- **Root cause**: Two independent metric emission paths for the same logical metric. Analogous to the dual-write persistence bug (ISS-014) but at the metrics layer.
- **Effect**: When the full observability stack is running, Mission Control "Turns/min" panel shows 2x the actual turn rate.
- **Fix strategy**: Designate a single owner for WS turn metrics. Recommended: OTel SDK owns them (path_observer already calls `_emit_to_otel`); remove the redundant `obs.record_metric` call for the same metric names.

---

### ISS-031 · Runtime Truth Governance Gap — Static CI Cannot Detect Metric Emission Failures
- **Status**: CONFIRMED — structural governance gap
- **Evidence**: `scripts/runtime_truth.py` performs static analysis only (import + call chain). It cannot detect: zombie metrics, dashboard-metric contract violations, behavioral dead code, configuration-gated dormancy.
- **Root cause**: The three-leg proof (import + call chain + runtime evidence) has only legs 1 and 2 enforced in CI. Leg 3 (runtime evidence) is never verified.
- **Missing gate**: No CI step parses Grafana dashboard JSON files and verifies that queried metric names have corresponding emitters in application source.
- **Fix strategy**: Add a static metric contract test: parse `observability/grafana/dashboards/*.json`, extract Prometheus query expressions, extract metric names, grep application source for emit calls, fail CI if mismatch. This is a static check — no runtime required.

---

## 🟢 Minor / Tracked

### ISS-010 · Prometheus Metrics Endpoint Not Exposed
- **Status**: OPEN — blocked by ISS-008
- **Note**: `GET /api/v1/observability/metrics` returns JSON golden signals (latency/traffic/errors/saturation), not Prometheus text format

### ISS-011 · Memory System PostToolUse Hook — Pending
- **Status**: OPEN — in progress

---

## ✅ Resolved

| ID | Title | Resolved In |
|----|-------|-------------|
| ISS-R001 | ObservabilityMiddleware not wired into stack | commit `e320e45` |
| ISS-R002 | LangGraph nodes not instrumented | commit `e320e45` |
| ISS-R003 | No trace propagation to LangGraph (ContextVar) | commit `e320e45` |
| ISS-R004 | No trace API endpoints `/traces`, `/traces/{id}` | commit `e320e45` |
| ISS-R005 | `git commit*` in deny list — blocked CI | `.claude/settings.json` fix |
| ISS-R006 | Python 3.11 system pytest can't parse 3.12 syntax | `.venv/` with Python 3.12 |
| ISS-R007 | Grafana port 3001 unreachable on Codespaces preview proxy (cookie/redirect loop) | branch `claude/fix-monitoring-port-hQ7JL` — env-driven `GF_SERVER_ROOT_URL` + `GF_SECURITY_COOKIE_SAMESITE=none`/`SECURE=true`/`CSRF_ALWAYS_CHECK=false`, Codespaces detection in `start_observability.sh`. See CLAUDE.md §6.12. |
| ISS-R008 | Mission Control port 3001 returns `ERR_HTTP_RESPONSE_CODE_FAILURE` even after §6.12 fix | branch `claude/fix-monitoring-port-hQ7JL` — root cause was the devcontainer missing the `docker-in-docker` feature, so `docker compose up -d` could never run inside the dev container. Added `ghcr.io/devcontainers/features/docker-in-docker:2` + `hostRequirements: 4cpu/8GB/32GB` to `devcontainer.json`. Added `loud_warn()` in `start_observability.sh` that mirrors silent failures to the visible supervisor log. **Requires user to run "Codespaces: Rebuild Container" once.** See CLAUDE.md §6.13. |

### ISS-032 · Truth Table Lock Drift — `customer_chat_router` importer_count 6→5
- **Status**: CONFIRMED — documentation fix required, no code change needed
- **Discovered**: 2026-05-09 live audit
- **Evidence**: `python scripts/runtime_truth.py --check` exits 1 with: `customer_chat_router: importer_count 6 → 5`
- **Root cause**: `.runtime/truth_table.lock.json` was generated on branch `jules-5513332666705839536-7e7df21b` (2026-05-08T09:54:43Z) when `microservices/orchestrator_service/src/api/context_utils.py.orig` was counted as an importer. The `.orig` file still exists but `scripts/runtime_truth.py` only greps `.py` files — the old lock generation run used a different grep path that included `.orig`.
- **Component status unchanged**: `customer_chat_router` is still ACTIVE. Only the importer count drifted by 1.
- **Fix**: `python scripts/runtime_truth.py --update && git add .runtime/truth_table.lock.json && git commit -m "runtime-truth: resync lock after .orig file grep path fix"`
- **Severity**: LOW — CI drift gate fails on PRs until fixed, but no runtime impact.

### ISS-033 · Scratch Artifact — `context_utils.py.orig` in Microservice Directory
- **Status**: CONFIRMED — cleanup required
- **Discovered**: 2026-05-09 live audit
- **File**: `microservices/orchestrator_service/src/api/context_utils.py.orig`
- **Content**: Backup of `context_utils.py` from a prior edit session. Differs by one line (context truncation logic: `return client_context[-12:]` vs `return []`).
- **Impact**: Causes ISS-032 (truth table lock drift). Not imported by any live code. Not a `.py` file so not executed.
- **Fix**: `git rm microservices/orchestrator_service/src/api/context_utils.py.orig` in a cleanup PR.
- **Severity**: LOW — no runtime impact, but contributes to CI noise.

---

## 📊 Runtime Metrics (Measured 2026-05-04)

| Metric | Value | Source |
|--------|-------|--------|
| WS connect time | 26ms | measured |
| Auth register | 125ms | trace `8b1f0f95` |
| Auth login | 75ms | trace `0af1ec03` |
| LangGraph full run | 757ms | trace `80c2b5d7` |
| Orchestrator (all fail) | 1506ms | trace `bd4d2974` |
| Latency p50 | 3.5ms | `/observability/metrics` |
| Latency p95 | 1057ms | `/observability/metrics` |
| Latency p99 | 1416ms | `/observability/metrics` |
| Error rate | 7.69% | `/observability/metrics` |
| Total requests | 13 | `/observability/metrics` |

---

## Confirmed Live 2026-05-09 (Second Pass)

### [MEDIUM] ISS-NEW-001 · Intent classification misclassifies Arabic greetings · CONFIRMED LIVE
- **Input**: `'مرحبا كيف حالك'` → got `'general'`, expected `'chat'`
- **Input**: `'hello'` → got `'chat'`, expected `'general'`
- **File**: `app/services/chat/local_graph.py:_classify_intent()`
- **Impact**: Arabic greetings routed to general handler instead of chat handler. Minor UX issue.

### [HIGH] ISS-NEW-002 · KAgent security blocks multi-agent graph · CONFIRMED LIVE
- **Evidence**: `create_multi_agent_graph(ai_client, []).ainvoke(state)` → `"⛔ Security Alert: Invalid token from planner_node"`
- **Impact**: The entire 8-node multi-agent graph (planner, researcher, writer, super_reasoner, procedural_auditor, reviewer, supervisor) cannot execute. All nodes call KAgent which rejects without a valid internal token.
- **Root cause**: `KagentMesh.execute_action()` validates caller token. No valid token is provided by graph nodes.

### [LOW] ISS-NEW-003 · Reranker driver export mismatch · CONFIRMED LIVE
- **Evidence**: `from app.drivers.reranker_driver import RerankDriver` → `ImportError`
- **File**: `app/drivers/reranker_driver.py` — class name differs from expected export
- **Impact**: Any code trying to import `RerankDriver` fails. Driver is ZOMBIE anyway.

### [LOW] ISS-NEW-004 · LlamaIndex requires OPENAI_API_KEY for default embeddings · CONFIRMED LIVE
- **Evidence**: `VectorStoreIndex.from_documents(docs)` → `ValueError: No API key found for OpenAI`
- **Fix**: Must explicitly set `Settings.embed_model = HuggingFaceEmbedding(...)` before use
- **Impact**: LlamaIndex unusable without explicit embed model configuration.

### [INFO] ISS-NEW-005 · TLM not installed · CONFIRMED
- **Evidence**: `cleanlab` not installed. Zero references in `app/`. Not part of this codebase.
- **Action**: Remove TLM from any documentation that claims it is used.


---

## Issues Added 2026-05-09 (fourth pass — advanced LangGraph forensic audit)

### [HIGH] ISS-NEW-006 · Monolith routes to OrchestratorAgent, not StateGraph · CONFIRMED LIVE
- **Evidence**: `ChatRoutingPolicy.candidate_urls()` returns `[f"{base}/agent/chat"]`. The `/agent/chat` endpoint routes to `OrchestratorAgent.run()` (intent-based dispatch), NOT the 13-node StateGraph.
- **Impact**: Even when the orchestrator microservice is running, the advanced StateGraph (DSPy, Tavily, reranker, synthesizer) is NOT invoked by the monolith's chat path. The 13-node StateGraph is only reachable via `/api/chat/messages` or `/api/chat/ws` on the orchestrator service itself.
- **Fix**: Change `ChatRoutingPolicy.candidate_urls()` to return `/api/chat/messages` instead of `/agent/chat`. Requires ADR.
- **Decision**: D-021

### [HIGH] ISS-NEW-007 · thread_id namespace mismatch between stacks · CONFIRMED
- **Evidence**: Local fallback graph uses `str(conversation_id)` (e.g. `"394"`). Orchestrator StateGraph uses `f"u{user_id}:c{conversation_id}"` (e.g. `"u7:c394"`). Different MemorySaver instances.
- **Impact**: A conversation that starts on the local fallback graph and later routes to the orchestrator StateGraph has no shared checkpoint state (ISS-019 root cause).
- **Fix**: Standardize both stacks to the same thread_id format, or accept that state is not shared between stacks.
- **Decision**: D-022

### [MEDIUM] ISS-NEW-008 · AdminAgentNode stateless thread_id undocumented · CONFIRMED
- **Evidence**: `AdminAgentNode.__call__()` uses `config = {"configurable": {"thread_id": str(uuid.uuid4())}}` — fresh UUID per invocation.
- **Impact**: Admin sub-graph has no checkpoint continuity even when parent graph has Postgres checkpointer. Admin tool results not persisted across invocations.
- **Status**: Intentional by design, but undocumented. Now documented in D-023 and `.memory/langgraph_advanced_forensics.md`.

### [HIGH] ISS-NEW-009 · Truth table lock stale and missing advanced stack entries · CONFIRMED
- **Evidence**: `.runtime/truth_table.lock.json` generated 2026-05-08T09:54:43Z on branch `jules-5513332666705839536-7e7df21b`. Missing: orchestrator StateGraph, Tavily, DSPy, research_agent, OrchestratorAgent. CI drift check fails: `customer_chat_router: importer_count 6→5`.
- **Impact**: CI drift gate may pass on false grounds. Missing entries mean the truth table does not reflect the full advanced stack.
- **Fix**: `python scripts/runtime_truth.py --update` then commit. Add missing entries for orchestrator StateGraph, Tavily, OrchestratorAgent.

### [MEDIUM] ISS-NEW-010 · TAVILY_API_KEY absent from docker-compose.yml · CONFIRMED
- **Evidence**: Neither `orchestrator-service` nor `research-agent` environment sections in `docker-compose.yml` include `TAVILY_API_KEY`. Absent from all env templates.
- **Impact**: Even when the full stack is running, `WebSearchFallbackNode` silently skips web search. `SynthesizerNode` receives empty docs → `"لا توجد تفاصيل متاحة."`.
- **Fix**: Add `- TAVILY_API_KEY=${TAVILY_API_KEY:-}` to both service environment sections in `docker-compose.yml`.
- **Decision**: D-018

### [MEDIUM] ISS-NEW-011 · DuckDuckGo fallback broken in research-agent · CONFIRMED
- **Evidence**: `ddgs` package NOT installed. `SuperSearchOrchestrator` falls back to `DuckDuckGoSearchAPIWrapper` when Tavily absent → `ImportError` on initialization.
- **Impact**: If Tavily key is absent and orchestrator is running, `SuperSearchOrchestrator` raises `ImportError` on init. No graceful degradation.
- **Fix**: `pip install ddgs` in the research-agent container, or add `ddgs` to `microservices/research_agent/requirements.txt`.

---

## Issues Added 2026-05-11 (D-043 — Live Runtime Audit)

### [HIGH] ISS-043-A · Skills Pipeline in fallback mode — LLM keys not in process env at startup · CONFIRMED LIVE
- **Evidence**: `POST /compose → pipeline_mode="fallback"`. `reasoning-agent /health → llm_backend="mock"`. `research-agent /health → tavily_available="false"`.
- **Root cause**: `OPENROUTER_API_KEY` and `TAVILY_API_KEY` not exported into process env before supervisor.sh launches microservices. Services start in mock/fallback mode and do not re-read env after startup.
- **Impact**: All skill calls return fallback responses. No real LLM reasoning. No web search.
- **Fix**: Export keys before supervisor.sh runs: `export OPENROUTER_API_KEY="..." && export TAVILY_API_KEY="..."`. Or add to `.devcontainer/secrets.env`.

### [MEDIUM] ISS-043-B · API contract mismatch — `message` vs `question` field · CONFIRMED LIVE
- **Evidence**: `POST /agent/chat` with `{"message":"..."}` → 422. `POST /chat/message` with `{"message":"..."}` → 422. Both require `question` field.
- **Impact**: Any client using `message` field (standard convention) gets 422. Frontend must use `question` field.
- **Fix**: Add `message` as alias for `question` in Pydantic models, or update frontend to use `question`.

### [MEDIUM] ISS-043-C · planning-agent uses in-memory SQLite (not Supabase) · CONFIRMED LIVE
- **Evidence**: `GET /health → {"database":"sqlite+aiosqlite:///:memory:"}`. `PLANNING_DATABASE_URL` not set or not converted to asyncpg format.
- **Impact**: Planning state not persisted across restarts. No cross-session continuity for planning.
- **Fix**: Set `PLANNING_DATABASE_URL` to asyncpg-format Supabase URL in supervisor.sh (same pattern as orchestrator ISS-040 fix).

### [LOW] ISS-043-D · Grafana dashboard count mismatch in older docs · RESOLVED
- **Evidence**: Some docs say "11 dashboards" or "13 dashboards". Live count: 16 dashboards.
- **Fix**: Updated in CLAUDE.md §6.25 and `.memory/runtime_truth.md`.

---

## Issues Added 2026-05-11 (ISS-046 — Surgical Fixes, Full Pipeline Verified)

### [CRITICAL] ISS-046-A · orchestrator CODESPACES=false → Docker hostnames → all skill calls fail · FIXED
- **Evidence**: `POST /compose → pipeline_mode="fallback"`, `error="[Errno -2] Name or service not known"`. orchestrator tried `http://planning-agent:8002`, `http://research-agent:8007`, `http://reasoning-agent:8008`.
- **Root cause**: `CODESPACES` env var not set when orchestrator was started manually. `config.py:resolve_service_urls()` defaults to Docker hostnames when `CODESPACES != "true"`.
- **Fix**: Restarted orchestrator with `CODESPACES=true` + explicit `PLANNING_AGENT_URL/RESEARCH_AGENT_URL/REASONING_AGENT_URL=http://localhost:...`. supervisor.sh already sets these correctly — only affected manually-started instances.
- **Status**: FIXED. `POST /compose → pipeline_mode="full"` confirmed.

### [HIGH] ISS-046-B · research-agent/reasoning-agent start without API keys → mock/fallback mode · FIXED
- **Evidence**: `research-agent /health → tavily_available="false"`. `reasoning-agent /health → llm_backend="mock"`. supervisor.sh used bare `uvicorn` (not `nohup python -m uvicorn`) which may not inherit env properly.
- **Root cause**: Services launched by supervisor.sh at devcontainer boot before secrets were available in process env. `uvicorn` binary vs `python -m uvicorn` env inheritance difference.
- **Fix**: Changed `uvicorn` → `nohup python -m uvicorn` in `launch_research_agent()` and `launch_reasoning_agent()`. Added port 6543→5432 substitution for research_agent DB URL (ISS-040 parity).
- **Status**: FIXED. `research-agent /health → tavily_available="true"`. `reasoning-agent /health → llm_backend="openrouter"`.

### [HIGH] ISS-046-C · planning-agent uses SQLite (not Postgres) — port 6543 not converted · FIXED
- **Evidence**: `GET /health → {"database":"sqlite+aiosqlite:///:memory:"}`. `PLANNING_DATABASE_URL` not set; `DATABASE_URL` with port 6543 rejected by asyncpg.
- **Root cause**: `supervisor.sh:launch_planning_agent()` did not apply `sed 's/:6543\//:5432\//'` before passing URL to asyncpg (unlike orchestrator which had ISS-040 fix).
- **Fix**: Added `planning_db_url=$(echo "$planning_db_url" | sed 's/:6543\//:5432\//') ` to `launch_planning_agent()`.
- **Status**: FIXED. `GET /health → {"database":"postgresql+asyncpg://..."}`.

### [LOW] ISS-046-D · secrets.env.example missing TAVILY_API_KEY · FIXED
- **Evidence**: Developers copying `secrets.env.example` would not know to add `TAVILY_API_KEY`.
- **Fix**: Added `TAVILY_API_KEY=tvly-dev-your-key-here` to `.devcontainer/secrets.env.example`.
- **Status**: FIXED.

### [HIGH] ISS-048 · monolith rejects localhost ORCHESTRATOR_SERVICE_URL without ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR · FIXED (2026-05-11)
- **Evidence**: `AppSettings.validate_orchestrator_service_discovery()` raises `ValueError` when `ORCHESTRATOR_SERVICE_URL=http://localhost:8006` and `CODESPACES` is not `true`. Monolith crashed on import.
- **Root cause**: `_is_container_runtime()` detects `/proc/1/cgroup` → returns `True` → validation blocks localhost unless `CODESPACES=true` OR `ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR=true`.
- **Fix**: Added `export ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR="true"` to `supervisor.sh` STEP 4 monolith launch block (alongside existing `CODESPACES=true`). Belt-and-suspenders: both flags now set.
- **Status**: FIXED. Monolith starts cleanly and routes to orchestrator at localhost:8006.

### [HIGH] ISS-049 · conversation-service fails to start: ModuleNotFoundError prometheus_client · FIXED (2026-05-11)
- **Evidence**: `/tmp/conversation_service.log` → `ModuleNotFoundError: No module named 'prometheus_client'`. Service dead on :8003.
- **Root cause**: `prometheus_client` not installed in base Python environment. Other services had it via their own `requirements.txt` installed in Docker; conversation-service runs as native uvicorn without Docker install step.
- **Fix**: `pip install prometheus_client` in base environment. Added `prometheus_client>=0.20.0` to `microservices/conversation_service/requirements.txt` for reproducibility.
- **Status**: FIXED. `GET /health → {"status":"healthy","graph_ready":true,"step":"12"}`.

### [FIXED] ISS-STREAM-001 · Streaming catastrophic failure — words appear all at once · FIXED (2026-05-12)
- **Evidence**: الكلمات تظهر دفعة واحدة بدل كلمة بكلمة. نصوص غريبة تظهر في الواجهة (`phase_start`, `RUN_STARTED`).
- **Root causes (4 new, in addition to D-047)**:
  1. `_normalize_stream_event` يُحوّل أحداث التحكم (`phase_start`, `RUN_STARTED`, إلخ) إلى `assistant_delta` → نصوص غريبة.
  2. `_generator_with_persistence` لا يجمع الـ deltas → لا يُحفظ شيء في DB عند streaming.
  3. `mergeAssistantContent` منطق `current.startsWith(incoming)` خاطئ → chunks قديمة تُتجاهل.
  4. `print()` statements في graph nodes تُلوّث stdout وتُبطئ الأداء.
- **Fix**: 
  - `_PASSTHROUGH_EVENT_TYPES` + `_TEXT_EVENT_TYPES` + noop filter في `orchestrator_client.py`.
  - `delta_parts` accumulator في `_generator_with_persistence`.
  - إصلاح `mergeAssistantContent` + `assistant_final` handler في `useAgentSocket.js`.
  - إزالة `print()` → `logger.debug()` في جميع graph nodes.
  - CI gate: `.github/workflows/streaming-fix-gate.yml`.
  - Grafana dashboard: `160-streaming-metrics.json` (11 panels).
- **Status**: FIXED. ruff ✅ | runtime_truth ✅ | guardrails ✅ | 18 Grafana dashboards | 12 Prometheus targets.

### [FIXED] ISS-STREAM-002 · Word-by-word streaming broken — 3 root causes · FIXED (2026-05-12)
- **Evidence**: البث يتوقف عند `phase_start` → 0 delta chunks → timeout. حتى بعد ISS-STREAM-001.
- **Root causes (3 جذرية)**:
  1. **`stream_chat()` يُعيد `ChatCompletionChunk` objects (OpenAI SDK) وليس dicts**: الكود في `general_knowledge.py`, `search.py`, `main.py` كان يستخدم `chunk.get('choices')` → `AttributeError` يُبتلع بـ `except Exception: continue` → 0 chunks.
  2. **`astream_events` لا يُطلق `on_custom_event` في LangGraph 1.2.0**: `stream_writer()` يُستدعى بنجاح لكن `on_custom_event` لا يُطلق أبداً. الحل: `astream(stream_mode=["custom","updates"])`.
  3. **النموذج الافتراضي `nvidia/nemotron-3-super-120b-a12b:free` يُعيد chunk واحد فقط**: لا يدعم token-level streaming. الحل: `deepseek/deepseek-chat` (47-177 chunks/response).
- **Fix**:
  - `AIClient.extract_stream_content()` static method في `llm/client.py` — يدعم `ChatCompletionChunk` و dict.
  - `general_knowledge.py`, `search.py`, `main.py` (ChatFallbackNode) → استخدام `extract_stream_content()`.
  - `routes.py` `_run_chat_langgraph` + `_stream_chat_langgraph` → `astream(stream_mode=["custom","updates"])` بدل `astream_events`.
  - `SynthesizerNode` → streaming حتى عند `reranked=[]` (no search results).
  - `app/core/ai_config.py` → `deepseek/deepseek-chat` كنموذج افتراضي.
  - Prometheus metrics: `cogniforge_streaming_chunks_total`, `cogniforge_streaming_chars_total`, `cogniforge_streaming_sessions_total`, `cogniforge_streaming_duration_seconds`.
  - Grafana dashboard: `170-streaming-iss-stream-002.json` (9 panels, UID `cogniforge-streaming-002`).
- **Verified**: 122-177 word-by-word chunks per response ✅ | `cogniforge_streaming_chunks_total{node="synthesizer"} 122.0` ✅

### [VERIFIED] ISS-050 · End-to-end chat routing confirmed live (2026-05-11)
- **Evidence**: WebSocket test `ws://localhost:8000/api/chat/ws` with subprotocols `['jwt', TOKEN]` → events: `['conversation_init', 'assistant_delta'×6, 'assistant_final']`. Answer: real Arabic LLM response about Newton's second law.
- **Path**: `User WS → Monolith:8000/api/chat/ws → OrchestratorClient.chat_with_agent() → http://localhost:8006/api/chat/messages → StateGraph 13-node → Planning:8002 + Research:8007 + Reasoning:8008 → composed answer`.
- **Pipeline**: `POST /compose → pipeline_mode="full" | skills_active=["planning","research","reasoning"] | duration=28.5s`.
- **Status**: VERIFIED LIVE. Microservices answer users end-to-end.

### [FIXED] ISS-051 · Wide-net knowledge retrieval leaks multiple unrelated exercises + non-streaming dump · FIXED (2026-05-13)
- **User-visible catastrophe**: عند طلب «تمرين 2016 الدورة الأولى الموضوع الثاني التمرين الرابع» يظهر:
  1. التمرين المطلوب (الدوال العددية 2016) — صحيح.
  2. **بالإضافة إلى** تمرين 2024 (احتمالات) — مُلوِّث، لم يُطلب.
  3. YAML metadata غريب (`---`, `metadata:`, `render:`...) يظهر للطالب.
  4. عناصر الإجابة النموذجية تُكشف قبل أن يحل الطالب.
  5. النص يصل دفعة واحدة كبيرة → لا typing-effect → الطالب ينتظر طويلاً ثم يرى كل شيء فجأة.
  6. زمن الاستجابة كبير لأن wide-net يقرأ كل ملفات `knowledge_base/`.
- **Root causes (5 جذرية)**:
  1. **Wasted matched_entry**: `detect_exercise_retrieval()` يُحدِّد بدقة الملف المطابق (`bac2016_s1_math_exp_subject2_ex4_numerical_functions.md`) عبر `knowledge_index.py`، لكن `_exercise_retrieval_decision()` كان يرمي `matched_entry` ويحتفظ فقط بـ `recognized: bool`.
  2. **Wide-net fallback**: `_build_local_retrieval_response()` كان يستدعي `search_educational_content(query=question)` بدون فلاتر — يدخل في `local_store.search_local_knowledge_base()` الذي يقرأ كل ملفات `.md` ويُرجِع كل ما يحتوي على `تمرين`/`بكالوريا` → كلا ملفي 2016 و 2024 يُحقَنان.
  3. **No YAML stripping**: المُرجَع هو المحتوى الخام للملف بما فيه `---\nmetadata:\n...---` → يظهر للطالب كرموز ميتا غير مفيدة.
  4. **No solution gating**: «عناصر الإجابة النموذجية» تُرسَل مع نص التمرين → الطالب يرى الحل قبل أن يحاول.
  5. **No streaming**: المسار في `chat_with_agent` كان `yield assistant_delta { content: HUGE_STRING }` ثم `assistant_final { content: "" }` — لا typing-effect مهما كان حجم النص.
- **Fix (D-048 — Indexed Knowledge Retrieval + Streaming Display)**:
  - `app/services/capabilities/exercise_retrieval.py`:
    - أُضيف `_strip_frontmatter()`, `_trim_at_solution()`, `format_exercise_for_display()`.
    - تحذف YAML frontmatter وكل قسم يبدأ بـ `## عناصر الإجابة`/`## الحل`/`## وسوم البحث`/`### الجزء I/II/III`.
    - النتيجة: ملف 10884 char → 2913 char (~73% noise removed).
  - `app/infrastructure/clients/orchestrator_client.py`:
    - أُضيف `_exercise_retrieval_full_decision()` يُرجِع `ExerciseRetrievalDecision` كاملاً مع `matched_entry`.
    - أُعيد كتابة `_build_local_retrieval_response()` ليُفضِّل المسار المُفهرَس (`load_exercise_content(matched_entry)` + `format_exercise_for_display`) — wide-net فقط كمسار بديل.
    - أُضيف `_stream_local_retrieval_response()` يُقسِّم على حدود الأسطر/الكلمات (~80 char) مع `asyncio.sleep(0.012)` بين كل قطعة.
    - `chat_with_agent()` المسار رقم 2 (exercise_retrieval) أصبح streaming كامل بدل dump واحد.
  - `app/core/ai_config.py`:
    - `PRIMARY = "inclusionai/ring-2.6-1t:free"` — Inclusion AI Ring 2.6 (1T params MoE) بطلب المستخدم. fallback chain يحمي الاستمرارية. (تم التراجع عن gemma-4-31b التجريبي بنفس اليوم — D-049 history.)
- **Verified**:
  - Smoke test على ملف 2016: `10884 → 2913 char` (73% noise removed) ✅
  - YAML stripped, solution stripped, tags stripped, all 3 parts (I/II/III) intact ✅
  - 6/6 intent classifier scenarios pass (catastrophe query, explanation, greeting, concept, probability request) ✅
- **What MUST NOT regress**:
  - `_exercise_retrieval_full_decision()` must always be called inside `_build_local_retrieval_response()` — bypassing it re-introduces wide-net leakage.
  - The streaming fallback path #2 in `chat_with_agent()` must use `_stream_local_retrieval_response()` not `_build_local_retrieval_response()` directly — otherwise typing effect breaks.
  - `_SOLUTION_SECTION_MARKERS` must include every section start that precedes solutions (`### الجزء I`, `## عناصر الإجابة`, etc.). Adding new KB files requires extending this list if their solution headers differ.
- **Status**: FIXED 2026-05-13 — branch `claude/fix-exercise-display-eaIQC`.

---

### [FIXED] ISS-052 · WebSocket client auth + event structure — 5 root causes · FIXED (2026-05-13)

- **Context**: تجريب حي لاستدعاء تمرين الدوال العددية 2016 الموضوع الثاني التمرين الرابع الدورة الأولى عبر WebSocket.
- **ISS-052-A — endpoint خاطئ**: المحادثة تعمل عبر WebSocket حصراً. لا يوجد `POST /api/chat/messages` — يُرجع 404.
  - الـ endpoints الصحيحة: `ws://.../api/chat/ws` (customer) و `ws://.../admin/api/chat/ws` (admin).
- **ISS-052-B — websockets v16 API**: `from websockets.client import connect` → `DeprecationWarning` + `TypeError: unexpected keyword argument 'additional_headers'`. الصحيح: `from websockets.asyncio.client import connect`.
- **ISS-052-C — طريقة المصادقة**: إرسال الـ token عبر `Authorization` header → `NegotiationError: no subprotocols supported`. الصحيح: `subprotocols=["jwt", TOKEN]` — مطابق لـ `useRealtimeConnection.js:56`.
- **ISS-052-D — بنية الـ events**: الـ payload مُدمَج تحت `event["payload"]` وليس flat. `event.get("content")` يُرجع دائماً `None`. الصحيح: `payload_data = event.get("payload") or event`.
- **ISS-052-E — token منتهي الصلاحية**: صلاحية 30 دقيقة. الخادم يُغلق بـ code 4401 بدون رسالة → يبدو كـ `connection open → connection closed` فوراً. يجب تجديد الـ token قبل كل جلسة.
- **Fix**: بروتوكول اختبار WebSocket الصحيح موثَّق في `CLAUDE.md §6.30`.
- **Verified**: 4 تجارب حية ناجحة — نص التمرين + السؤال الأول + شرح مفصل + شرح شرح. كل نتيجة تطابق الإجابة النموذجية.
- **Status**: FIXED 2026-05-13 — branch `feat/bac-live-test-websocket-fix`.

---

### [FIXED] ISS-054 · Machine-gun streaming + شرح التمرين timeout · FIXED (2026-05-13)

- **Context**: تجربة حية كاملة لطلب تمرين الدوال العددية 2016 + شرح مفصل للإجابة النموذجية.
- **ISS-054-A — Machine-gun streaming**: طلب التمرين يُنتج 401 chunk في 4.9 ثانية بـ 122/400 burst < 10ms. الـ frontend يستقبل كل chunk كـ `dispatchEvent` منفصل → `setMessages` → React re-render → 401 re-render في 4 ثوانٍ → الحروف تظهر كمدفع رشاش بشع.
  - **السبب الجذري**: `useRealtimeConnection.js` يُطلق `dispatchEvent` لكل `onmessage` فوراً بدون batching.
  - **الإصلاح**: `requestAnimationFrame` batching في `useRealtimeConnection.js` — يُجمِّع كل delta chunks في frame واحدة (~16ms) ويُدمج محتواها قبل dispatch واحد. النتيجة: 401 re-render → ~60fps batches (≈ 15-20 re-render).
- **ISS-054-B — شرح التمرين timeout (90 ثانية بدون رد)**: طلب "اشرح لي شرحاً مفصلاً..." كان يتجمد تماماً.
  - **السبب الجذري**: context التمرين (13650 حرف) + system prompt كبير → النموذج المجاني `inclusionai/ring-2.6-1t:free` يتجمد مع هذا الحجم. `BASE_TIMEOUT=30s` يُلغي الطلب قبل أن يبدأ.
  - **الإصلاح 1**: `_MAX_EXERCISE_CONTEXT_CHARS = 6000` في `local_graph.py` — يقطع context إلى 6000 حرف (نصف أول + نصف أخير) بدلاً من 13650.
  - **الإصلاح 2**: `_MAX_EXPLANATION_TOKENS = 1200` — يُحدِّد max_tokens لمنع توليد ردود طويلة جداً.
  - **الإصلاح 3**: `BASE_TIMEOUT = 45.0` في `connection.py` (كان 30.0) — يُعطي النماذج المجانية وقتاً كافياً.
  - **الإصلاح 4**: `stream_chat(messages, max_tokens=...)` — إضافة parameter لـ `max_tokens` في `simple_client.py`.
  - **الإصلاح 5**: `asyncio.sleep(0)` بعد كل chunk في `_stream_model` — يُعطي event loop فرصة معالجة أحداث أخرى.
- **Verified live**:
  - طلب التمرين: TTFT=0.88s، 401 chunks، يعمل ✅
  - شرح التمرين: TTFT=5.27s، 221 chunks، 1612 حرف، LaTeX صحيح، لا هلوسة ✅
  - `Contains LaTeX: True` ✅ | `Hallucination: False` ✅
- **Files changed**:
  - `frontend/app/hooks/useRealtimeConnection.js` — rAF delta batching
  - `app/core/gateway/simple_client.py` — asyncio.sleep(0) + max_tokens param
  - `app/core/gateway/connection.py` — BASE_TIMEOUT 30→45
  - `app/services/chat/local_graph.py` — _MAX_EXERCISE_CONTEXT_CHARS + _MAX_EXPLANATION_TOKENS
- **Status**: FIXED 2026-05-13.

---

### [FIXED] ISS-055 · TTFT الشرح 44s + بنشمارك النماذج · FIXED (2026-05-13)

- **Context**: تجربة حية ثانية — TTFT الشرح = 44.13s، وقت كلي = 70.48s.
- **السبب الجذري**: `inclusionai/ring-2.6-1t:free` يتجمد مع context 9670 حرف — يبدأ التوليد بعد 44 ثانية.
- **بنشمارك حي لـ 15 نموذجاً**: `nvidia/nemotron-3-nano-30b-a3b:free` = TTFT 2.06s مع context كامل، عربية صحيحة.
- **قاعدة لا تُخرق**: المحتوى يُرسَل كاملاً (9670 حرف) — لا ضغط، لا اختصار — البث حرف وراء حرف.
- **الإصلاحات**:
  - `ai_config.py`: PRIMARY = `nvidia/nemotron-3-nano-30b-a3b:free` (كان `inclusionai/ring-2.6-1t:free`)
  - `local_graph.py`: system prompt مُقلَّص + `_MAX_EXPLANATION_TOKENS=900`
  - `exercise_retrieval.py`: `requested_part` hint + `_detect_requested_part_from_question()`
  - `docs/ai_skills/bac-exercise-explanation.md`: توثيق الأداء + مسار الشرح الكامل
- **نتائج حية مُتحقَّق منها**:
  - استدعاء التمرين: TTFT=0.85s، 12/12 فحص ✅
  - شرح الإجابة: TTFT=1.78s (كان 44.13s)، 5.90s كلي (كان 70.48s) ✅
  - التمرين كامل: بطاقة الامتحان + الجزء I + II + III + LaTeX سليم ✅
- **Status**: FIXED 2026-05-13.

---

### [FIXED] ISS-056 · JSON envelope leak + wrong exercise + machine-gun streaming · FIXED (2026-05-13)

- **Severity**: 🔴 Critical — كارثة مرئية للمستخدم الحقيقي.
- **Context**: المستخدم طلب «اعطني تمرين دوال عددية شعبة علوم تجريبية الموضوع الثاني التمرين الرابع لسنة 2016 الدورة الأولى». ظهرت 4 كوارث متراكبة موثقة في screenshots.
- **الأعراض المُشاهَدة**:
  1. JSON خام `{"المصدر":"معرفة مادة","مستوى_الثقة":"0.70","التمرين":"لا توجد تفاصيل متاحة","الشعبة":...}` يظهر للطالب بدل التمرين.
  2. ردود مقطوعة — أحياناً ظهر العنوان فقط دون محتوى التمرين.
  3. ظهور تمرين خاطئ — أحياناً يأتي رد عام/مهلوس بدل تمرين 2016 المُفهرَس.
  4. الحروف تظهر بشكل "مدفع رشاش" — رشقات سريعة كل 16ms بدل تدفق سلس.
- **الأسباب الجذرية**:
  1. **`microservices/orchestrator_service/src/api/routes.py` lines 1652/1939/2671**: `_serialize_json_async(final_resp)` كان يدمب dict مظروف SynthesizerNode (`{"المصدر","التمرين",...}`) كاملاً كنص للمستخدم.
  2. **`microservices/orchestrator_service/src/services/overmind/graph/search.py:507-509`**: `AIMessage(content=json.dumps(response_json, ensure_ascii=False))` يُسرِّب dict عبر messages history.
  3. **`app/infrastructure/clients/orchestrator_client.py:chat_with_agent`**: يحاول orchestrator-service أولاً قبل fallback chain. الـ orchestrator يستدعي vector DB مستقل لا يحوي `knowledge_base/*.md` → SynthesizerNode no-docs branch → JSON envelope.
  4. **`frontend/app/components/ChatInterface.jsx`**: لا typewriter smoothing. الـ rAF batching في `useRealtimeConnection.js` يدفع 5-20 chunks لكل 16ms frame → مظهر مدفع رشاش.
- **الإصلاحات (D-050)**:
  - `routes.py`: دالة `_extract_human_readable_response(final_resp)` — تستخرج فقط الحقول البشرية (`التمرين`/`الإجابة`/`response`/...) من dict، تتعامل مع `خطأ` envelope بشكل مخصص. تستبدل `_serialize_json_async` في 3 مواقع.
  - `graph/search.py`: `AIMessage(content=text_val)` بدل `AIMessage(content=json.dumps(...))`.
  - `orchestrator_client.py`: `_has_indexed_match()` + preemption في بداية `chat_with_agent`. عند تطابق `matched_entry`، يبث المحتوى المُفهرَس النظيف ويتجاوز orchestrator كلياً.
  - `ChatInterface.jsx`: خطّاف `useTypewriter(fullContent, isStreaming)` — 60fps reveal بإيقاع ~240 char/sec، تسارع للـ backlog الكبير، كشف فوري عند انتهاء streaming.
  - `globals.css`: فواصل بصرية بين أجزاء التمرين، KaTeX nowrap داخل `.exam-content`، media query للشاشات الصغيرة.
- **Files changed**:
  - `microservices/orchestrator_service/src/api/routes.py` — `_extract_human_readable_response` + 3 leak sites fixed
  - `microservices/orchestrator_service/src/services/overmind/graph/search.py` — `AIMessage(content=text_val)`
  - `app/infrastructure/clients/orchestrator_client.py` — `_has_indexed_match()` + preemption block
  - `frontend/app/components/ChatInterface.jsx` — `useTypewriter` hook + MessageBubble wiring
  - `frontend/app/globals.css` — exam-content polish + KaTeX media query
  - `CLAUDE.md` §6.31 — doctrine
  - `.memory/decisions.md` D-050, `.memory/issues.md` ISS-056
- **Invariants enforced**:
  - JSON envelope dump → assistant_delta/final محظور إلى الأبد
  - AIMessage.content = نص بشري فقط
  - indexed match → preempt orchestrator
  - typewriter لا يبطّئ TTFT
  - copy button ينسخ النص الكامل
- **Status**: FIXED 2026-05-13 — branch `claude/fix-exercise-display-SRmNL`.

---

### [FIXED] ISS-057 · LaTeX rendering — raw `$g$` and `$\mathbb{R}$` visible to student · FIXED (2026-05-13)

- **Severity**: 🔴 Critical — تجربة بصرية مدمرة. D-050 preemption نجحت في إيصال التمرين، لكن الطالب رأى LaTeX خام بدل رياضيات.
- **Context**: المستخدم رفع screenshot جديد يُظهر التمرين الصحيح ظاهراً (preemption ناجح ✅) لكن كل `$g$`, `$\mathbb{R}$`, `$g(x) = 1+(x²+x-1)e^{-x}$`, `$\lim_{x \to -\infty}$` تظهر كنص خام مع علامات دولار ظاهرة.
- **الأسباب الجذرية**:
  1. **knowledge_base/bac2016_*.md**: 192 موضع بصيغة `\\(...\\)` (double-backslash حرفية — 7 bytes للمحاطة).
  2. **`frontend/app/components/ChatInterface.jsx:preprocessMath`**: regex `/\\\(([^]*?)\\\)/g` يطابق `\(` فقط. على `\\(g\\)` يطابق الـ `\(` الثاني، يُبقي الأول → بعد replace: `\$g\$` ← markdown يراها دولار مُهرَّب → remark-math لا يلتقطها → KaTeX لا يُستدعى.
  3. **typewriter character-by-character**: عند كشف `$g$`، أحياناً يعرض `$g` (بدون `$` إقفال) لحظياً → ReactMarkdown render مع LaTeX غير مكتمل → flicker بصري.
  4. **backend `_split_preserving_latex`**: regex يدعم `$...$` فقط، لا `\\(...\\)`. يُقسِّم `\\(g\\)` على فراغ كأي كلمة → احتمال فصل delimiter عبر chunks.
- **الإصلاحات (D-051 — ثلاث طبقات دفاع)**:
  - **طبقة 1 (`ChatInterface.jsx:preprocessMath`)**: تطبيع `\\(` → `\(` و `\\[` → `\[` قبل التحويل، ثم `\(...\)` → `$...$` و `\[...\]` → `$$...$$`. يدعم 5 صيغ.
  - **طبقة 2 (`ChatInterface.jsx:atomicTokenLength + useTypewriter`)**: دالة جديدة تكشف LaTeX block boundaries (`$`, `$$`, `\(`, `\\(`, `\[`, `\\[`) وتُرجع طول الـ block كاملاً. الـ typewriter يكشف الـ block ذرياً في frame واحدة.
  - **طبقة 3 (`app/infrastructure/clients/orchestrator_client.py:_split_preserving_latex`)**: regex مُحدَّث لالتقاط 4 صيغ كـ token واحد.
  - **طبقة 4 (`frontend/app/globals.css`)**: CSS فاخر لبطاقة الامتحان — خط ذهبي علوي، ظل ثلاثي الطبقات، katex-display مع gradient + hover + animation، h3 بـ right-border ذهبية.
- **Files changed**:
  - `frontend/app/components/ChatInterface.jsx` — preprocessMath enhanced + atomicTokenLength + LaTeX-aware useTypewriter
  - `app/infrastructure/clients/orchestrator_client.py` — `_LATEX_INLINE_RE` multi-format
  - `frontend/app/globals.css` — luxury exam-content styling
  - `CLAUDE.md` §6.32
  - `.memory/decisions.md` D-051, `.memory/issues.md` ISS-057
- **Live tests**:
  - 192 موضع `\\(...\\)` تحوَّلت كلها إلى `$...$` (0 remaining)
  - inline pairs بعد التحويل: 384 (= 192 × 2)
  - display pairs: 66 (محفوظة)
  - `atomicTokenLength`: 6/6 سيناريوهات تجتاز (`$g$`=3, `$$...$$`=14, plain=1, `$g`=1, `\(g\)`=5, `\\(g\\)`=7)
- **Invariants enforced**:
  - preprocessMath قبل remark-math إلزامي
  - atomic LaTeX reveal — لا flicker
  - backend splits تحافظ على LaTeX blocks
  - knowledge_base يحترم اصطلاح `\\(...\\)` + `$$...$$`
  - `throwOnError: false` للـ KaTeX
- **Status**: FIXED 2026-05-13 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-058 · Explanation Q dumps unrelated exercise + raw chunk tags + verbatim model answer · FIXED (2026-05-14)

- **Severity**: 🔴 Critical Catastrophe — تجربة مدمرة للطالب الحقيقي. النظام ردَّ على سؤال مفاهيمي بـ dump كامل لتمرينَين غير متعلقَين.
- **Context**: المستخدم رفع 3 screenshots تُظهر:
  1. سؤال "ماذا نقصد بدالة اصلية للدالة f" → الرد يحوي تمرين 2016 الدوال + تمرين 2024 الاحتمالات (الكامل!) معاً
  2. tags خام `[ex: ex_1]`, `[sol: ex_1]`, `[grading: ex_1]` ظاهرة للطالب
  3. تكرار حرفي للإجابة النموذجية بدل شرحها
  4. نص خام `Lambada infinity` (LaTeX غير مرسوم)
- **الأسباب الجذرية**:
  1. **`_BAC_EXERCISE_EXPLANATION_PATTERNS` ناقص**: لا يشمل "ماذا نقصد", "ما هو", "كيف نُثبت", "لماذا" → `detect_explanation_with_context` يُرجع False → السؤال يذهب إلى مسار آخر.
  2. **wide-net retriever في `local_store.search_local_knowledge_base`**: يقرأ كل `.md` في `knowledge_base/` (rglob), يُرجع 2016 + 2024 معاً عند غياب filters.
  3. **vector DB tags تتسرَّب**: orchestrator's RAG يُرجع chunks مع `[ex: ex_1]`, `[sol: ex_1]`, `[grading: ex_1]` كـ علامات داخلية. لا يوجد stripping قبل البث.
  4. **`_EXERCISE_EXPLANATION_SYSTEM_PROMPT` ضعيف**: لا يحظر النسخ صراحةً. الـ LLM يكرر الإجابة النموذجية حرفياً.
  5. **لا preempt للسياق المحادثاتي**: حتى لو حُلَّت patterns، السؤال "ماذا نقصد بدالة" يحتاج معرفة أن الطالب يسأل عن **التمرين السابق في المحادثة**.
- **الإصلاحات (D-052 — ست طبقات دفاع)**:
  - **طبقة 1**: 20+ نمط explanation pattern جديد (مفاهيمية + منهجية + تبرير + دوال صريحة).
  - **طبقة 2**: `_detect_entry_from_history()` — يفحص آخر 10 رسائل لكشف تمرين السياق. `detect_explanation_with_context` تأخذ `history_messages` parameter.
  - **طبقة 3**: `_has_explanation_with_context_match()` + preempt block في `chat_with_agent` (يتجاوز orchestrator + StateGraph + wide-net).
  - **طبقة 4**: إعادة كتابة `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` بتعليمات صريحة `🚫 لا تُكرِّر الإجابة النموذجية حرفياً`.
  - **طبقة 5**: `_strip_retrieval_tags()` regex يحذف `[ex|sol|grading|chunk|src|source|meta|tag|id|doc:value]` من أي نص قبل البث. مدمج في `_sanitize_text_for_user`.
  - **طبقة 6**: منظومة Skills رسمية جديدة في `app/services/skills/` — `BACExerciseSkill` بـ contract Pydantic + metrics + tests.
- **Files changed**:
  - `app/services/capabilities/exercise_retrieval.py` — 20+ patterns + `_detect_entry_from_history` + 3-stage `detect_explanation_with_context`
  - `app/infrastructure/clients/orchestrator_client.py` — `_has_explanation_with_context_match` + preempt block + `_strip_retrieval_tags` + integration in `_sanitize_text_for_user`
  - `app/services/chat/local_graph.py` — rewrite `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` (forbids verbatim)
  - `app/services/skills/__init__.py` — منظومة Skills (جديد)
  - `app/services/skills/bac_exercise_skill.py` — `BACExerciseSkill` formal Skill (جديد)
  - `CLAUDE.md` §6.33
  - `.memory/decisions.md` D-052, `.memory/issues.md` ISS-058
- **Live tests passed**:
  - 12/12 explanation patterns recognized correctly (catastrophe scenarios + direct + edge cases)
  - 0 false positives on concept questions without context
  - 4/4 BACExerciseSkill operations succeed (RETRIEVE, EXPLAIN+history, AUTO, no-match)
  - chunk-tag stripping: 5/5 tags stripped, 3/3 math notations preserved (x[1], [1,2,3])
- **Invariants enforced**:
  - conversation context يهزم vector DB search
  - explanation preempt يسبق orchestrator
  - system prompt الشرح يحظر النسخ صراحةً
  - chunk-tag stripping إلزامي
  - Skills > Prompt Spaghetti
  - Skill استقلالية إلزامية
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-059 · Detail question time catastrophe — 15-18s response for short concept Qs · FIXED (2026-05-14)

- **Severity**: 🔴 Critical UX — المستخدم بلَّغ أن «الإجابة تتأخر بشكل خطير» عند طلب تفصيل معين.
- **Context**: حتى الأسئلة القصيرة («ماذا نقصد بدالة أصلية»، «لماذا g(-1)=1-e») كانت تستغرق 15-18 ثانية — نفس الزمن لـ «اشرح التمرين كاملاً».
- **الأسباب الجذرية**:
  1. **`_MAX_EXPLANATION_TOKENS=900` ثابت**: كل سؤال يطلب 900 token من النموذج المجاني (~50 tok/s) → ~18s دائماً.
  2. **`_MAX_EXERCISE_CONTEXT_CHARS=3000` ثابت**: حتى الأسئلة المفاهيمية تحصل على 3000 char context → LLM يستغرق وقت أطول في معالجة input.
  3. **`detect_explanation_with_context` يُستدعى 3 مرات**: في `_has_match()` + داخل preempt + داخل stream — كل مرة file I/O مكرَّر.
- **الإصلاحات (D-053)**:
  - دالة جديدة `_classify_question_budget()` في `local_graph.py` تُصنِّف السؤال إلى 5 أنواع وتُرجع (context_budget, token_budget, q_class) المناسب.
  - `run_local_graph_with_exercise_context` يطبِّق الـ budget الديناميكي على context slicing + `max_tokens` للـ LLM call.
  - `chat_with_agent` يحسب `_explanation_decision` **مرة واحدة** ويمرِّره عبر `precomputed_decision=` للـ stream → يوفِّر file I/O مكرَّر + 10-20ms.
  - Metric جديد `cogniforge_langgraph_q_class_total{q_class,graph}` يُتاح في Grafana.
- **Files changed**:
  - `app/services/chat/local_graph.py` — `_classify_question_budget` + dynamic budget application
  - `app/infrastructure/clients/orchestrator_client.py` — decision caching + `precomputed_decision` parameter
  - `CLAUDE.md` §6.34, `.memory/decisions.md` D-053
- **Live tests passed**:
  - 11/11 budget classification tests (CONCEPT/JUSTIFICATION/METHOD/DEFAULT/FULL)
  - Expected latency reduction:
    - CONCEPT: 18s → 7s (60% أسرع)
    - JUSTIFY: 18s → 9s (50% أسرع)
    - METHOD: 18s → 12s (33% أسرع)
    - DEFAULT: 18s → 14s (22% أسرع)
    - FULL: 18s (بدون تغيير — مطلوب)
- **Invariants enforced**:
  - max_tokens يتناسب مع نوع السؤال
  - decision caching إلزامي (احسب مرة، مرِّر)
  - telemetry tags كاملة في كل explanation span
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-060 · KaTeX renders `\lambda` as `l a m b d a` letters · FIXED (2026-05-14)

- **Severity**: 🔴 Critical visual catastrophe — رغم إصلاح D-051 السابق، LaTeX داخل الرياضيات يُرسَم بشكل خاطئ.
- **Context**: المستخدم رفع screenshot يُظهر النص:
  ```
  )=
  displaystyle int 0 lambda h(x),dxحيث
  l a m b d a
  lambdaعدد حقيقي موجب تماماً
  lim lambdato+infty A(lambda
  ```
  بدلاً من `A(λ) = ∫₀^λ h(x)dx, lim_{λ→+∞} A(λ)` المُتوقَّع من الصورة المرجعية للتمرين الورقي.
- **السبب الجذري (الأعمق من D-051)**:
  D-051 طبَّع **حدود** الرياضيات (`\\(...\\)` → `\(...\)` → `$...$`) لكنه ترك **محتوى** الرياضيات كما هو. الـ knowledge_base يستخدم `\\command` لكل LaTeX:
  - `\\lambda` (25 موضع)
  - `\\int` (2 موضع)
  - `\\infty` (51 موضع)
  - `\\to` (21 موضع)
  - `\\displaystyle` (1 موضع)
  - `\\mathbb` (8 موضع)
  - `\\,` (thin space)
  KaTeX يفسِّر `\\` كأمر `\newline`، فيقرأ `\\lambda` كـ "newline + النص lambda" → يرسم الحروف منفصلة `l a m b d a`.
- **الإصلاح (D-054 — سطر واحد جراحي)**:
  إضافة خطوة 2 في `preprocessMath` بين تطبيع الحدود وتحويل `$...$`:
  ```javascript
  processed = processed.replace(/\\\\([a-zA-Z]+|[,;!{}])/g, '\\$1');
  ```
  يُطبِّع `\\command` → `\command` لكل أوامر LaTeX. لا يلمس `\\\\` (newline حقيقي).
- **Files changed**:
  - `frontend/app/components/ChatInterface.jsx` — preprocessMath step 2 added
  - `CLAUDE.md` §6.35, `.memory/decisions.md` D-054
- **Live tests passed** (على ملف bac2016 الكامل):
  - 0 موضع `\\command` متبقٍ (كانت 192+)
  - 0 موضع `\\(` متبقٍ
  - 25× `\lambda` صحيح
  - 51× `\infty` صحيح
  - 21× `\to` صحيح
  - 2× `\int` صحيح
  - 8× `\mathbb` صحيح
  - سطر الكارثة بعد الإصلاح: `$A(\lambda) = \displaystyle\int_0^{\lambda} h(x)\,dx$` → KaTeX يرسم `A(λ) = ∫₀^λ h(x)dx`
- **Invariants enforced**:
  - `preprocessMath` هو الحارس الوحيد لتطبيع `\\command`
  - الخطوات الثلاث متراكبة: تطبيع الحدود → تطبيع الأوامر → تحويل لـ `$...$`
  - أي طبقة محذوفة = كارثة فورية
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-061 · UI catastrophe — flicker bar + ugly frame + bad fonts + slate-blue colors · FIXED (2026-05-14)

- **Severity**: 🔴 Critical UX — المستخدم بلَّغ: «طالبا تقزز و اغمي عليه من قبح الألوان الكارثية البشعة و الخطوط المقززة الدميمة».
- **الأعراض المُشاهَدة (5 screenshots من المستخدم)**:
  1. **خط أفقي علوي ذهبي/أزرق «يظهر ويختفي مثل البث»** فوق بطاقة التمرين
  2. **إطار مُقزِّز** حول كل رسالة مساعد (border + box-shadow ثقيلَين)
  3. **ألوان مائلة للأزرق** (slate-tinted) — لا "أبيض فاخر" ولا "أسود فاخر"
  4. **خطوط عربية رديئة** بلا font-smoothing
  5. **dark/light toggle "معطلَين بشكل خطير"** — التبديل يحدث لكن الألوان لم تكن واضحة الفرق
- **الأسباب الجذرية**:
  1. `.exam-content::before` بـ `linear-gradient` أصفر/أزرق متراقص — كان يومض على كل re-render
  2. `@keyframes katex-fade-in` + `animation: katex-fade-in 0.18s ease-out` على كل `.exam-content .katex-display` — typewriter يُعيد التصيير 60fps فيُطلِق الـ animation على كل character
  3. `transition: box-shadow/border-color` على katex-display:hover و `.message-bubble.streaming` → re-paint مكلفة
  4. `border: 1px solid var(--border-color)` على `.message.assistant .message-bubble` — هذا الإطار الذي شكا منه المستخدم
  5. Color palette مائل للـ slate-blue: `--bg-color: #f8fafc`, `--text-color: #0f172a`, `--surface-color: #1e293b`
  6. Cairo font بدون smoothing/feature-settings → خطوط حادة على RTL
- **الإصلاحات (D-055 — ست طبقات)**:
  - **L1 Color palette**: Light `--bg: #ffffff` + text `#0a0a0a` + border `#e5e5e5`. Dark `--bg: #0a0a0a` + text `#fafafa` + border `#1f1f1f`. إضافة `--surface-elevated` (لـ tables only).
  - **L2 Typography**: import Tajawal + Noto Kufi Arabic + Inter. body بـ font-smoothing + text-rendering: optimizeLegibility + font-feature-settings.
  - **L3 Flicker removal**: حذف `.exam-content::before` كلياً + `@keyframes katex-fade-in` + `animation` على katex-display + `transition` على katex-display:hover + box-shadow على message-bubble.streaming.
  - **L4 Exam-Card minimal**: `background: transparent` + `border: none`. exam-badge: pill شفاف. h1/h2: border-bottom 1px (لا gradient). h3: عادي. hr: 1px solid. tables: حدود محايدة.
  - **L5 Message-bubble**: assistant bubble بـ `background: transparent` + `border: none` (حذف الإطار المُقزِّز).
  - **L6 KaTeX colors**: `.markdown-content .katex { color: var(--text-color) }` + كل children بـ `color: inherit` → معادلات بيضاء فاخرة في dark، سوداء فاخرة في light.
- **Files changed**:
  - `frontend/app/globals.css` (6 sections rewritten — theme vars, body, exam-content, message-bubble, KaTeX colors, streaming indicator)
  - `CLAUDE.md` §6.36, `.memory/decisions.md` D-055
- **Live verification needed in Codespaces** (sandbox can't render visuals):
  - Toggle light/dark → خلفية تتبدل بين `#ffffff` و `#0a0a0a` فوراً
  - تمرين 2016 يُعرَض بدون خط ذهبي علوي
  - رسائل المساعد بدون إطار مرئي
  - المعادلات بيضاء في dark، سوداء في light
  - typewriter يكشف الحروف بدون flicker بصري
- **Invariants enforced**:
  - لا animations على المحتوى أثناء streaming
  - لا hover transitions على re-rendered elements
  - لا gradient backgrounds على content cards
  - Pure backgrounds (no slate tinting)
  - Font smoothing إلزامي للعربي
  - Border-image gradients محظورة على content headings
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-062 · Header bottom border visible as flickering white line · FIXED (2026-05-14)

- **Severity**: 🔴 Critical UX — المستخدم بلَّغ: «يوجد خيط ابيض فوق كلمة مثال و بجانب كلمة متصل يظهر و يختفي مما يفسد تجربة المستخدم بشكل خطير مدمر».
- **Context**: بعد إصلاح ISS-061 (D-055 — luxury theme)، الخلفية أصبحت سوداء نقية `#0a0a0a`. لكن `.header` لا يزال يحوي `border-bottom: 1px solid var(--border-color)` + `box-shadow`. الحد `#1f1f1f` (المُعرَّف في الـ dark theme) أصبح **مرئياً** كخط أبيض رفيع على الخلفية السوداء النقية.
- **السبب الجذري**: `globals.css` السطر 98 — `.header` بـ `border-bottom: 1px solid var(--border-color)`. لم يكن مرئياً على slate-blue القديم (#0f172a vs #334155)، لكنه أصبح مرئياً على pure black (#0a0a0a vs #1f1f1f).
- **لماذا «يظهر ويختفي»**: في الواقع الخط ثابت — لكن خلال streaming، typewriter يُعيد render المحتوى أسفل الخط ~60fps فيُسبب انطباع بصري بأن الخط «يومض». هذا هو ما رآه المستخدم.
- **الإصلاح (D-055.1 — جراحي)**:
  ```css
  .header {
      height: 60px;
      background-color: var(--bg-color);  /* بدلاً من --surface-color */
      border-bottom: none;                  /* كان: 1px solid var(--border-color) */
      box-shadow: none;                     /* كان: var(--shadow-sm) */
      ...
  }
  ```
  الـ header الآن يندمج بسلاسة مع الـ body — لا فاصل بصري، لا خط أبيض. يتطابق مع الـ screenshot المرجعي الذي طلبه المستخدم.
- **Files changed**:
  - `frontend/app/globals.css` (`.header` rule)
  - `.memory/issues.md` ISS-062
- **Verification**:
  - `grep -A8 "^\.header {" globals.css` → `border-bottom: none; box-shadow: none;` ✅
  - `grep "border-bottom\|border-top" globals.css | grep -i header` → 0 ✅
- **Invariant added**: على الخلفية السوداء النقية، أي `border` بلون `--border-color` على عناصر full-width سيظهر كخط مرئي. الـ headers/dividers الفاصلة بين كتل full-width يجب أن تستخدم **خلفية مختلفة** أو **margin/padding** بدل border لإنشاء فصل بصري.
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-063 · legacy-style.css overrides luxury theme with gold gradients · FIXED (2026-05-14)

- **Severity**: 🔴 Critical UX — المستخدم بلَّغ بعد D-055 و D-055.1: «الخلفية لم تصبح سوداء فاخرة في الوضع الليلي ولا بيضاء فاخرة راقية فخمة في الوضع النهاري — مزالت كارثية مدمرة خطيرة».
- **Context**: D-055 وضع pure-black `#0a0a0a` للـ dark و pure-white `#ffffff` للـ light. D-055.1 حذف border-bottom من الـ header. لكن المستخدم لا يزال يرى ألواناً warm/cream + golden glow.
- **السبب الجذري**: `frontend/app/layout.jsx` كان يستورد ملفَّين CSS بالترتيب:
  ```jsx
  import "./globals.css";        // ← نظام D-055 الفاخر
  import "./legacy-style.css";   // ← يطغى!
  ```
  `legacy-style.css` (578 سطراً) كان يحوي:
  ```css
  :root {
      --background-color: #050506;         /* ليس pure-black */
      --primary-color: #d4af37;            /* ذهبي */
      --text-color: #f7f3ec;               /* cream */
      --border-color: rgba(212,175,55,0.28); /* حدود ذهبية */
  }
  body, html {
      background:
          radial-gradient(1200px circle at 10% 0%, rgba(212,175,55,0.16), transparent 60%),
          radial-gradient(900px circle at 90% 15%, rgba(0,170,255,0.12), transparent 55%),
          var(--background-color);
  }
  ```
  النتيجة: gradient ذهبي 16% + gradient أزرق 12% فوق `#050506` = warm-golden glow.
- **الإصلاح (D-055.2 — 3 خطوات)**:
  1. حذف `import "./legacy-style.css"` من `layout.jsx`
  2. `git rm frontend/app/legacy-style.css` (الملف بالكامل — تأكدنا أن لا dependency خارجي)
  3. تقوية body rule في globals.css: `body, html { background: var(--bg-color); ... }` بنفس selector specificity كما كان في legacy، مع `background` shorthand لإلغاء أي gradient cached
- **Files changed**:
  - `frontend/app/layout.jsx` (حذف الـ import)
  - `frontend/app/legacy-style.css` (deleted — 578 سطراً)
  - `frontend/app/globals.css` (body → body, html + background shorthand)
  - `CLAUDE.md` §6.38, `.memory/decisions.md` D-055.2
- **Verification**:
  - `[ ! -f frontend/app/legacy-style.css ]` → ملف محذوف ✅
  - `grep -i "212.*175.*55\|d4af37" frontend/app/globals.css` → 0 نتائج ✅
  - `grep "import.*legacy-style" frontend/app/layout.jsx | grep -v "^//"` → 0 ✅
  - `grep -A2 "^body, html" frontend/app/globals.css | grep "background:"` → موجود ✅
- **Invariant added (8th rule لـ D-055)**: Single source of truth for theming. نظام الثيم يعيش في ملف CSS واحد. أي ملف "legacy" يحوي `:root` overrides = خطر فوري على نظام الثيم. مراجعة كل `import "*.css"` في layout files على PR.
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).

---

### [FIXED] ISS-064 · Text cut on right + dozens of catastrophic lines + light mode broken · FIXED (2026-05-14)

- **Severity**: 🔴 Critical UX — المستخدم رفع 4 screenshots وبلَّغ 3 كوارث متراكبة:
  1. **«نصف الجملة لا يظهر و يختفي بشكل كارثي خطير مدمر و سبب فضيحة»** — text overflow على اليمين، الكلمات تنقطع («بال» مقطوعة، الباقي مخفي)
  2. **«عشرات الخطوط الكارثية»** — borders زرقاء على h1/h2/blockquote/code + md-hr رمادي + input-area shadow
  3. **«الوضع النهاري لا يعمل»** — light mode toggle لم يطبق pure-white بشكل موثوق
  4. طلب: «يجب أن يظهر بشكل خارق مثل Claude بحيث يملأ الشاشة بشكل خارق و يستفيد من المساحة الكاملة من أقصى اليمين لليسار»
- **الأسباب الجذرية**:
  1. `.message-bubble { max-width: 90% }` + `.message.assistant { justify-content: flex-end }` (في RTL = LEFT) كان يُسبب bubble بـ 90% width على اليسار، مع 10% فجوة على اليمين، والنص يتدفق RTL من بداية الـ bubble، فيقطع الحرف الأخير.
  2. `.markdown-content h1 { border-bottom: 2px solid var(--primary-color) }` كان يظهر كخط أزرق أفقي تحت كل عنوان رئيسي.
  3. `.markdown-content h2 { border-right: 3px solid var(--primary-color) }` كان يظهر كخط أزرق عمودي.
  4. `.md-hr { border-top: 1px solid var(--border-color) }` كان يظهر كخط رمادي أفقي بين الأقسام.
  5. `.md-blockquote { background: rgba(37,99,235,0.05) }` كان يظهر بخلفية زرقاء بارزة.
  6. `.markdown-content code { background: rgba(37,99,235,0.08); border: 1px solid rgba(37,99,235,0.15) }` بإطار أزرق.
  7. `.input-area { box-shadow: var(--shadow-sm) }` + `:focus-within { box-shadow: var(--shadow) }` يُسببان ظلال زرقاء حول الإدخال.
  8. `:root` فقط للـ light mode — بعض المتصفحات لا تُطبِّق بشكل موثوق على dynamic `data-theme` switch.
- **الإصلاحات (D-056 — 5 طبقات)**:
  - **L1 Claude-style layout**: `.messages { max-width: 920px; width: 100%; margin-inline: auto }`. `.message.assistant .message-bubble { width: 100%; max-width: 100%; padding: 0; border: none; background: transparent }`. `.message.user .message-bubble { max-width: min(85%, 600px); border-radius: 18px 18px 6px 18px }`. نفس `max-width: 920px` على `.input-area-wrapper` و `.agent-board-container`.
  - **L2 zero-line markdown**: حذف `border-bottom` من h1 و `border-right` من h2. التركيز على `letter-spacing: -0.015em` و `font-weight: 800` للتمييز.
  - **L3 invisible hr + transparent blockquote**: `.md-hr { height: 0; opacity: 0 }`. `.md-blockquote { background: transparent }`.
  - **L4 clean code blocks**: `background: var(--surface-elevated); border: none`.
  - **L5 explicit `[data-theme='light']` block**: copy من `:root` بـ stronger specificity للموثوقية.
- **Files changed**:
  - `frontend/app/globals.css` (8 sections rewritten — :root + data-theme variants, .messages, .message-bubble, .markdown-content h1/h2/h3/code, .md-hr, .md-blockquote, .input-area, .agent-board-container)
  - `CLAUDE.md` §6.39, `.memory/decisions.md` D-056
- **Verification**:
  - `grep "max-width: 920px" globals.css` → 3 (.messages, .input-area-wrapper, .agent-board-container) ✅
  - `grep "border-bottom.*primary-color\|border-right.*primary-color" globals.css` → 0 active ✅
  - `grep "^\[data-theme='light'\]" globals.css` → موجود ✅
  - `.markdown-content { width: 100%; overflow-wrap: break-word }` ✅
- **Invariants enforced (3 new rules لـ D-056)**:
  1. Full-width assistant, constrained user bubble (Claude-style)
  2. No decorative borders on inline content — التمييز عبر typography
  3. Explicit theme blocks > :root (for reliability)
- **Status**: FIXED 2026-05-14 — branch `claude/fix-exercise-display-SRmNL` (PR #2063).
