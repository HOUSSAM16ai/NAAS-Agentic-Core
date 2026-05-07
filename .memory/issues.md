# Open Issues & Bugs
> Last updated: 2026-05-06 | Branch: claude/runtime-truth-audit-65iVU
> Format: [SEVERITY] ID · Title · [CONFIRMED LIVE / INFERRED / RUNTIME-ONLY / HISTORICAL]
> **Capability runtime status (ACTIVE/PARTIAL/DORMANT/ZOMBIE) lives in `.memory/runtime_truth.md`.**

---

## 🔴 Critical — Core Architectural Flaws (NEW — Session 2026-05-05)

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
