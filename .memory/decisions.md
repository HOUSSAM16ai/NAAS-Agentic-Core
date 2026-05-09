# Architectural Decisions
> Last updated: 2026-05-09 | Branch: `fix/lifespan-orchestration-env-injection`

## D-024 · Process Env Wins Over .env at Module Import Time
**Decision**: Secrets (DATABASE_URL, OPENROUTER_API_KEY, SECRET_KEY) must be present in the **process environment** before uvicorn starts, not just in `.env`. The `.env` file is read by pydantic-settings after module-level code runs.
**Reason**: `app/core/settings/base.py:23` calls `os.environ.get("APP_DATABASE_URL")` at import time. If the process env is empty, the validator raises `ValueError` and uvicorn crashes before pydantic-settings ever reads `.env`.
**Implementation**: `supervisor.sh:_export_env_file()` exports all `.env` keys into the shell process before `python -m uvicorn`. `_inject_env_secrets()` writes real secrets from process env into `.env` first.
**Status**: IMPLEMENTED 2026-05-09 — see `fix/lifespan-orchestration-env-injection`.

## D-025 · Lifespan Warmup Must Be Timeout-Guarded
**Decision**: Any `ainvoke()` or async LLM call inside an ASGI `lifespan()` context manager must be wrapped in `asyncio.wait_for(..., timeout=N)`. Default timeout: 30 seconds.
**Reason**: An unbounded `await` in lifespan blocks ASGI startup indefinitely. Uvicorn accepts connections but the app is not ready. The service appears alive (PID, port open) but is actually in a partial startup state — the exact "misleading startup observability" problem described in ISS-035.
**Consequence**: If warmup times out, the service starts in DEGRADED mode (not dead). `/health` exposes `startup_state: "degraded"` and `startup_errors`. Operators can diagnose without restarting.
**Status**: IMPLEMENTED 2026-05-09 — see `microservices/orchestrator_service/main.py`.

## D-026 · /health Must Expose startup_state, Not Just "ok"
**Decision**: Every microservice `/health` endpoint must return `startup_state` (`"ready"` / `"degraded"`) and `startup_errors` (list) in addition to `{"status": "ok"}`.
**Reason**: A service that passes `/health` but has a failed graph warmup is DEGRADED, not healthy. Returning `{"status":"ok"}` unconditionally hides the real state from operators and load balancers.
**Implementation**: `app.state.startup_state` set during lifespan. `/health` reads it and includes it in the response.
**Status**: IMPLEMENTED 2026-05-09 — see `microservices/orchestrator_service/main.py`.

## D-027 · Supervisor Must Re-Verify Health on Every Boot
**Decision**: `supervisor.sh` must always re-probe the live `/health` endpoint on every boot cycle. It must never trust stale `.devcontainer/state/app_healthy` from a previous run.
**Reason**: The state file persists across container restarts. If uvicorn crashed on the previous boot, the state file still shows `app_healthy` from the run before that. The supervisor then skips the health check and reports the system as ready — while port 8000 is not listening.
**Implementation**: `_uvicorn_healthy()` checks both `kill -0 $PID` AND `curl -sf $HEALTH_ENDPOINT`. Health check step always runs regardless of state file.
**Status**: IMPLEMENTED 2026-05-09 — see `.devcontainer/supervisor.sh`.

## D-028 · LangGraph Local Graph Must Emit Prometheus Metrics Per Turn
**Decision**: `_supervisor_node` and `_chat_node` in `app/services/chat/local_graph.py` must emit `langgraph.intent.total`, `langgraph.node.count.total`, and `langgraph.node.duration_seconds` via `UnifiedObservabilityService` on every invocation.
**Reason**: The Grafana LangGraph dashboard (`20-langgraph.json`) references `cogniforge_langgraph_intent_total`, `cogniforge_langgraph_node_count_total`, `cogniforge_langgraph_node_duration_seconds_bucket`. Without emitters, these panels are permanently empty — zombie metrics (ISS-029, D-016).
**Consequence**: After this change, the LangGraph dashboard shows real data after the first WS chat turn. `cogniforge_langgraph_checkpointer_writes_total` remains a zombie metric until Postgres checkpointer is activated (ISS-020).
**Status**: IMPLEMENTED 2026-05-09 — see `app/services/chat/local_graph.py` + `app/telemetry/metrics.py`.

## D-001 · LangGraph as Primary Chat Handler
**Decision**: `app/services/chat/local_graph.py` is the real handler. The orchestrator microservice is DORMANT in the default development environment.
**Reason**: GitHub Codespaces devcontainer (`.devcontainer/docker-compose.host.yml`) only spins up the `web` container; it does NOT start the microservices stack from `docker-compose.yml`. The orchestrator at `orchestrator:8006` always fails with ConnectError.
**Consequence**: All chat goes through the fallback chain → LangGraph `run_local_graph()`. This holds for both Codespaces and Replit-style single-process deployments.
**Rule**: NEVER assume the orchestrator microservice is reachable. LangGraph is the truth — unless you explicitly run `docker compose -f docker-compose.yml up -d` to wake the full stack.

## D-002
`app/kernel.py` is the authoritative composition root.

## D-002 · MemorySaver for Conversation Persistence
**Decision**: LangGraph uses `MemorySaver(thread_id=conversation_id)` for per-conversation state.
**Reason**: Simple, in-process, no Redis/Postgres needed. Works in any single-process deployment (Codespaces devcontainer, Replit, bare uvicorn).
**Consequence**: Conversation memory is lost on process restart.
**Alternative considered**: `langgraph-checkpoint-postgres` — too heavy for current setup.

## D-004
Cross-boundary communication is API-first only; direct DB coupling is forbidden.

## D-005
Architecture documentation must be code-evidenced and updated in the same PR.

## D-006 · Single Persistence Owner — Monolith Owns Message Writes
**Decision**: The Monolith (`app/api/routers/customer_chat.py` and `app/api/routers/admin.py`) is the sole owner of writes to `customer_messages` and `admin_messages`.
The Orchestrator microservice may only persist when the Monolith delegates explicitly via
`compatibility_facade=True` AND signals success back via `persisted: true` on the terminal
event. Absence of the `persisted` flag is treated as failure.
**Reason**: Dual-write (ISS-014) corrupts conversation history and inflates LLM context.
**Implementation** (this branch):
1. User message: always written by Monolith at WS entry (`save_message(USER)`).
2. Assistant message: Monolith reads `event.get("persisted") is True` on the trapped
   terminal event. If True → SKIP local write; if False/absent → fail-safe write with
   2 retries; on retry exhaustion → `[CRITICAL_DATA_LOSS]` log + terminal `error` frame.
3. The `persisted` flag is preserved through `_normalize_stream_event` in
   `OrchestratorClient` (lines 280–283) so the router can read it post-normalization.
4. None of the local fallback paths (file-intel / exercise-retrieval / LangGraph /
   general-chat) ever set `persisted: true` — they don't write to DB.
**Status**: IMPLEMENTED — see `claude/fix-persistence-consolidate-8X8LT`.

## D-009 · Single Terminal Frame per Turn — No Silent Failure
**Decision**: Every WS chat turn emits exactly one terminal frame (`assistant_final`
on success, `error` on failure). The helper `_emit_terminal_frames()` in both routers
is the only code that emits these frames. `persisted` is emitted ONLY after a
confirmed save.
**Reason**: ISS-016 (silent failures) and ISS-017 (terminal-event corruption by the
unified envelope normalizer) both manifested as UI hangs. The previous finally block
had paths where no terminal event was sent (no content + no error + no pending_terminal_event).
**Implementation**:
1. `app/api/routers/customer_chat.py:_emit_terminal_frames` and
   `app/api/routers/admin.py:_emit_terminal_frames` synthesize a frame when
   the upstream did not provide one.
2. `shared/chat_protocol/event_protocol.py:normalize_streaming_event` now passes
   `complete`, `persisted`, and `conversation_init` through unchanged when the
   unified envelope flag is on (previously they were mangled to `assistant_delta`).
**Status**: IMPLEMENTED — see `claude/fix-persistence-consolidate-8X8LT`.

## D-007 · thread_id Must Equal conversation_id — No Re-derivation
**Decision**: LangGraph `thread_id` (MemorySaver key) is always derived as
`str(conversation_id)` at the OrchestratorClient entry point and passed explicitly.
It is NEVER re-derived inside graph nodes or fallback handlers.
**Reason**: Re-derivation caused context identity fragmentation (ISS-019) where
fallback paths opened a fresh LangGraph thread for a continuing conversation.
**Status**: DECIDED — implementation pending (ISS-019 open)

## D-008 · Postgres Checkpointer as Opt-In (Not Default)
**Decision**: MemorySaver remains the default checkpointer (D-002). Postgres-backed
checkpointing (`langgraph-checkpoint-postgres`) is opt-in via
`LANGGRAPH_CHECKPOINTER=postgres` env var.
**Reason**: MemorySaver is sufficient for development. The trade-off (state lost on
restart) is acceptable in Codespaces but documented explicitly as ISS-020.
**Consequence**: Production deployment MUST set `LANGGRAPH_CHECKPOINTER=postgres`
to preserve conversation continuity across restarts.
**Status**: DECIDED — implementation pending (ISS-020 open)

## D-010 · Runtime Truth Lock — Code Presence ≠ Runtime Usage
**Decision**: A capability is treated as ACTIVE only when proven by the triple
**import + call chain + runtime evidence**. Anything missing one is DORMANT,
ZOMBIE, or UNKNOWN. The authoritative table lives in `.memory/runtime_truth.md`
and is mirrored as CLAUDE.md §6.6.
**Reason**: The codebase advertises a multi-agent stack (LangGraph workflow,
KAgent mesh, MCP server, LlamaIndex, DSPy, reranker, integration kernel) that
in default Codespaces is overwhelmingly ZOMBIE/DORMANT. Aspirational docs
(ARCHITECTURE.md, LangGraph_Architectural_Blueprint.md) describe a target
state that the runtime does not implement. Treating those docs as truth led to
repeated drift and false claims.
**Consequence**:
1. No PR may promote a component to ACTIVE without the three-part proof.
2. Any change to the chat / agent stack must update `.memory/runtime_truth.md`
   in the same PR if it changes a component's runtime status.
3. Aspirational docs (`docs/architecture/*`, root blueprints) may continue to
   describe target architecture, but they are not authoritative for runtime —
   `.memory/runtime_truth.md` is.
4. ZOMBIE components are not deleted on sight. They are flagged. Removal
   requires an ADR.
**Status**: DECIDED 2026-05-06 — see branch `claude/runtime-truth-audit-65iVU`.


## D-011 · Sanitize Admin Stream Errors
**Decision**: Never expose raw Python exception text to chat clients on admin stream failures.
**Reason**: Prevent internal detail leakage and keep stable error contract.
**Implementation**: `app/services/boundaries/admin_chat_boundary_service.py` now emits generic message + code `STREAM_RUNTIME_ERROR` while retaining full error logs server-side.
**Status**: IMPLEMENTED 2026-05-06.

## D-013 · Intent Classifier Patterns Must Be Updated in Two Files Simultaneously
**Decision**: `_EDUCATIONAL_PATTERNS` and `_GREETING_PATTERNS` are intentionally duplicated between `app/services/chat/local_graph.py` and `app/telemetry/path_observer.py`. The duplication is load-bearing: `path_observer.py` must classify intent before the graph runs, without importing from `local_graph.py`'s private API.
**Consequence**: Any change to intent patterns MUST be applied to both files in the same PR. A PR that updates only one file creates a classification split-brain between the graph's routing and the observability path labels.
**Anti-pattern to avoid**: Adding more keywords to `_EDUCATIONAL_PATTERNS` to fix false negatives. This worsens false positives (ISS-027). The correct fix is semantic context guards or embedding-based classification.
**Status**: DECIDED 2026-05-09 — see `.memory/fragility-patterns.md` Pattern 1.

## D-014 · Zombie IntentDetector Must Not Be Wired Without Taxonomy Resolution
**Decision**: `app/services/chat/intent_detector.py:IntentDetector` (13-intent taxonomy: FILE_READ, CONTENT_RETRIEVAL, ADMIN_QUERY, etc.) must NOT be wired into the live WS chat path without first resolving the taxonomy incompatibility with the live classifier's 3-intent taxonomy (educational/general/chat).
**Reason**: The two systems are semantically incompatible. `IntentDetector` routes to tool-based handlers (file operations, code search). The live classifier routes to LLM prompt variants. Wiring `IntentDetector` into the live path without a translation layer would produce undefined routing behavior.
**Consequence**: `IntentDetector` remains PARTIAL (loaded-not-invoked) until an explicit ADR resolves the taxonomy conflict and defines the routing contract.
**Status**: DECIDED 2026-05-09.

## D-015 · Sidebar Rendering Must Use DOM Exclusion, Not Visual Hiding
**Decision**: Any new sidebar or modal component that contains sensitive or contextually inappropriate content must use DOM exclusion (`display: none`, conditional rendering, or `inert` attribute) rather than CSS transform/opacity hiding when in the closed state.
**Reason**: CSS `transform: translateX(±100%)` keeps elements in the DOM, making them accessible to screen readers, keyboard navigation, browser find-in-page, and programmatic text selection (ISS-028). As the agent stack becomes more capable, `AgentTimeline` will expose real-time agent execution state to screen readers regardless of sidebar visibility.
**Exception**: The existing `.sidebar` and `.agent-sidebar` may retain their CSS transform for animation quality, but MUST add `inert={!isOpen || undefined}` (or `aria-hidden={!isOpen}` + tabindex management) to prevent accessibility leakage.
**Status**: DECIDED 2026-05-09 — see `.memory/fragility-patterns.md` Pattern 2.

## D-016 · Dashboard Metric Names Must Have Verified Emitters Before Merge
**Decision**: No Grafana dashboard panel may be merged if the Prometheus query expression references a metric name that has no corresponding emitter in the application source code.
**Verification method**: Before adding a dashboard panel, grep the application source for the metric name in emit calls (`record_metric`, `create_histogram`, `create_counter`, `increment_counter`). If no emitter exists, either add the emitter first or do not add the panel.
**Reason**: Zombie metrics (ISS-029) create permanently empty panels that operators cannot distinguish from "system not running". This is worse than no dashboard — it creates false confidence.
**Consequence**: The LangGraph dashboard (`20-langgraph.json`) has 4 zombie metric panels that must either gain emitters or be removed.
**Status**: DECIDED 2026-05-09 — see `.memory/fragility-patterns.md` Pattern 4.

## D-018 · Tavily Key Must Be Injected via Environment — Never Hardcoded
**Decision**: `TAVILY_API_KEY` must be injected at runtime via environment variable. It must never be hardcoded in source files, committed to `.env` files, or embedded in `docker-compose.yml` as a literal value.
**Reason**: The key is a secret. `docker-compose.yml` uses `${TAVILY_API_KEY:-}` pattern (empty default) so the service starts in degraded mode when the key is absent rather than failing.
**Key format**: Must start with `tvly-`. MCP URL format (`https://mcp.tavily.com/mcp/?tavilyApiKey=...`) is auto-sanitized by `readiness.py` and `super_search.py` — but the raw key form is preferred.
**Current state**: `TAVILY_API_KEY` is absent from `docker-compose.yml` (both `orchestrator-service` and `research-agent` environment sections). Must be added before the full stack can use web search.
**Status**: DECIDED 2026-05-09 — see CLAUDE.md §6.7.

## D-019 · Advanced Orchestrator Graph Uses 4-Intent Taxonomy — Do Not Conflate with Local Graph
**Decision**: The orchestrator microservice's `SupervisorNode` uses a 4-intent taxonomy: `educational`, `general_knowledge`, `admin`, `chat`. The local `local_graph.py` uses a 3-intent taxonomy: `educational`, `general`, `chat`. These are semantically different and must not be conflated.
**Reason**: The orchestrator's `general_knowledge` intent routes to `GeneralKnowledgeNode` (a dedicated LLM handler). The local graph's `general` intent routes to the same `chat_node` as `chat`. Merging the taxonomies without a translation layer would break routing in both graphs.
**Consequence**: Any future work that wires the orchestrator graph into the live path must account for this taxonomy difference. The local graph's intent classification bugs (Arabic greetings → 'general') are separate from the orchestrator's DSPy-based classification.
**Status**: DECIDED 2026-05-09 — see CLAUDE.md §6.7.

## D-021 · Monolith Routes to OrchestratorAgent, Not StateGraph — Routing Policy Gap
**Decision**: `ChatRoutingPolicy.candidate_urls()` returns `[f"{base}/agent/chat"]`. The `/agent/chat` endpoint routes to `OrchestratorAgent.run()` (intent-based dispatch, 13-intent taxonomy), NOT the 13-node `StateGraph`. The StateGraph is only invoked by `/api/chat/messages` and `/api/chat/ws` on the orchestrator service itself.
**Reason**: The routing policy was set to `/agent/chat` as the primary endpoint. The StateGraph endpoints (`/api/chat/messages`, `/api/chat/ws`) were added later as the orchestrator evolved. The routing policy was never updated to point to the StateGraph path.
**Consequence**: Even when the orchestrator microservice is running, the 13-node StateGraph (with DSPy, Tavily, reranker, synthesizer) is NOT invoked by the monolith's chat path. The monolith hits `OrchestratorAgent` instead. To route through the StateGraph, `ChatRoutingPolicy.candidate_urls()` must return `/api/chat/messages` instead of `/agent/chat`. This is a deliberate future migration step, not a bug to fix immediately.
**Status**: DOCUMENTED 2026-05-09 — see `.memory/langgraph_advanced_forensics.md`.

## D-022 · thread_id Namespaces Are Incompatible Between Stacks — Do Not Mix
**Decision**: The local fallback graph uses `str(conversation_id)` as `thread_id` (e.g. `"394"`). The orchestrator StateGraph uses `f"u{user_id}:c{conversation_id}"` (e.g. `"u7:c394"`). These are different namespaces in different `MemorySaver` instances. They must never be mixed.
**Reason**: The local graph was designed for simplicity (bare conversation_id). The orchestrator graph added user-scoping to prevent cross-user state contamination. The two stacks evolved independently.
**Consequence**: A conversation that starts on the local fallback graph and later routes to the orchestrator StateGraph will have no shared checkpoint state (ISS-019). This is the context identity fragmentation issue. Resolution requires either: (a) standardizing both stacks to the same format, or (b) accepting that state is not shared between stacks.
**Status**: DOCUMENTED 2026-05-09 — see `.memory/langgraph_advanced_forensics.md`.

## D-023 · AdminAgentNode Uses uuid4() thread_id — Stateless by Design
**Decision**: Inside the 13-node StateGraph, `AdminAgentNode.__call__()` invokes the admin sub-graph with `config = {"configurable": {"thread_id": str(uuid.uuid4())}}`. A fresh UUID per invocation.
**Reason**: Admin queries are stateless by nature — each admin tool invocation is independent. Using a fresh UUID prevents stale admin state from contaminating subsequent admin queries.
**Consequence**: The admin sub-graph has no checkpoint continuity even when the parent graph has a Postgres checkpointer. Admin tool results are not persisted across invocations. This is intentional but was undocumented.
**Status**: DOCUMENTED 2026-05-09 — see `.memory/langgraph_advanced_forensics.md`.

## D-020 · WebSearchFallbackNode Silent Skip Is a Known Degradation — Not a Bug
**Decision**: `WebSearchFallbackNode` silently returns `{"used_web": False, "reranked_docs": []}` when `TAVILY_API_KEY` is absent. This is intentional degraded-mode behavior, not a bug.
**Reason**: The node must not block the graph when web search is unavailable. The `SynthesizerNode` handles empty docs by returning `"لا توجد تفاصيل متاحة."`.
**Risk**: Silent degradation is invisible to operators without telemetry. The telemetry event `retrieval_source="web_skipped_missing_tavily"` is the only signal. Operators must monitor this event to detect key absence.
**Consequence**: Any dashboard that shows "web search active" must verify against this telemetry event, not just the presence of the `TAVILY_API_KEY` env var.
**Status**: DECIDED 2026-05-09 — see CLAUDE.md §6.7.

## D-017 · WS Turn Metrics Must Have a Single Emission Owner
**Decision**: `ws.chat.turn.duration_seconds`, `ws.chat.terminal_events.total`, and `ws.chat.fallback.total` must be emitted through exactly one path. The designated owner is the OTel SDK path (`path_observer._emit_to_otel`). The redundant `obs.record_metric(...)` calls for the same metric names in `path_observer.py` must be removed to prevent double-counting (ISS-030).
**Reason**: Dual-write at the metrics layer is the observability equivalent of the dual-write persistence bug (ISS-014). When the full stack is up, Prometheus scrapes both the OTel collector and `/api/v1/observability/prometheus`, producing 2x counts.
**Exception**: `UnifiedObservabilityService` may retain its own internal metric store for the `/api/v1/observability/metrics` endpoint (golden signals). The prohibition is on emitting the same Prometheus-exported metric through two paths simultaneously.
**Status**: DECIDED 2026-05-09.

## D-012 · Grafana Cross-Origin Proxy Wiring is Done at Boot, Not in `grafana.ini`
**Decision**: `grafana.ini` holds LOCAL-only defaults. The Codespaces-correct
values (`root_url`, `domain`, `cookie_samesite=none`, `cookie_secure=true`,
`csrf_always_check=false`) are computed at container-boot time by
`.devcontainer/start_observability.sh` and exported as `GF_*` env vars before
`docker compose up -d`.
**Reason**: `${CODESPACE_NAME}` is unique per Codespace and changes per
recreate. Hard-coding the URL in `grafana.ini` would break every other user.
Grafana's documented behavior is "env vars override grafana.ini at process
start" — this is the right hook.
**Consequence**:
1. Local Linux dev → `start_observability.sh` `unset`s the env vars, Grafana keeps `localhost` defaults. Local dev path unchanged.
2. Codespaces → script detects `${CODESPACE_NAME}` and exports the proxy-correct URL + cookie settings. Grafana boots already-aware-of-the-proxy.
3. Any future cloud dev environment (Gitpod, Coder, etc.) can be supported by adding a single `elif` branch in `detect_grafana_public_url()` — no config-file rewrites needed.
**What MUST NOT change**:
- The detection function in `start_observability.sh` is the SINGLE source of truth for "what URL is Grafana served from".
- `docker-compose.observability.yml` Grafana env block uses `${VAR:-default}` for every `GF_*` var so missing vars never break the local boot.
- Never set `cookie_secure=true` unconditionally — it breaks plain `http://localhost:3001/`.
**Status**: IMPLEMENTED 2026-05-07 — see branch `claude/fix-monitoring-port-hQ7JL` and CLAUDE.md §6.12.
