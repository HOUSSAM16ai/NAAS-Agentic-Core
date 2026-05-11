# Open Issues & Bugs
> Last updated: 2026-05-11 | Branch: `feat/live-verification-d044-surgical-fixes`

---

## 🔴 Critical — Resolved in this branch (2026-05-11)

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

### [VERIFIED] ISS-050 · End-to-end chat routing confirmed live (2026-05-11)
- **Evidence**: WebSocket test `ws://localhost:8000/api/chat/ws` with subprotocols `['jwt', TOKEN]` → events: `['conversation_init', 'assistant_delta'×6, 'assistant_final']`. Answer: real Arabic LLM response about Newton's second law.
- **Path**: `User WS → Monolith:8000/api/chat/ws → OrchestratorClient.chat_with_agent() → http://localhost:8006/api/chat/messages → StateGraph 13-node → Planning:8002 + Research:8007 + Reasoning:8008 → composed answer`.
- **Pipeline**: `POST /compose → pipeline_mode="full" | skills_active=["planning","research","reasoning"] | duration=28.5s`.
- **Status**: VERIFIED LIVE. Microservices answer users end-to-end.
