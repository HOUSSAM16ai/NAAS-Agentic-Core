# Architectural Decisions
> Last updated: 2026-05-11 | Branch: `feat/microservices-step8-reasoning-agent`

## D-038 · Skills Architecture as the Canonical AI Pattern (2026-05-11)
**Decision**: كل قدرة ذكاء اصطناعي في النظام يجب أن تُبنى كـ **Skill** — microservice مستقل بمسؤولية واحدة، مدخلات/مخرجات محددة، مقاييس Prometheus، واختبارات قابلة للتشغيل. **Prompt Spaghetti محظور** كنمط معماري.

**Reason**: Prompt Spaghetti (prompt واحد كبير يحاول كل شيء) يُنتج جودة متوسطة في كل شيء، لا يمكن اختباره، لا يمكن قياسه، ويموت مع تغيير النموذج. Skills تُنتج جودة ممتازة في شيء واحد، قابلة للاختبار بـ pytest، قابلة للقياس بـ Prometheus، ومستقلة عن النموذج.

**Skill Contract** (إلزامي لكل Skill جديد):
1. `/health` endpoint — يُعيد `status`, `service`, `step`
2. `/metrics` endpoint — `cogniforge_{skill}_startup_info{step=N} 1.0` + invocation metrics
3. `/execute` أو endpoint وظيفي — مدخلات/مخرجات محددة بـ Pydantic
4. `prom_metrics.py` — `CollectorRegistry` مستقل، minimum 11 مقياساً
5. `tests/microservices/{skill}/test_step{N}_{skill}_metrics.py` — minimum 79 اختباراً
6. Fallback mode — يعمل بدون API key أو خدمات خارجية

**Skills الحالية (ACTIVE)**:
- `orchestrator-service` :8006 — Composition Skill (يُركِّب النتائج)
- `user-service` :8001 — Identity Skill (إدارة المستخدمين)
- `planning-agent` :8002 — Planning Skill (التخطيط)
- `research-agent` :8007 — Retrieval Skill (البحث والاسترجاع)
- `reasoning-agent` :8008 — Reasoning Skill (التفكير العميق MCTS)

**الهدف المستقبلي**:
```
Browser → FastAPI → orchestrator.compose([
    PlanningSkill.plan(query),
    ResearchSkill.retrieve(context),
    ReasoningSkill.reason(problem),
]) → إجابة مُركَّبة
```

**Anti-patterns المحظورة**:
- prompt واحد يحاول كل شيء
- Skill يستدعي Skill آخر مباشرة (يجب المرور عبر orchestrator)
- Skill بدون `/metrics` endpoint
- Skill بدون اختبارات

**Status**: ADOPTED 2026-05-11 — مُدرج في CLAUDE.md §0.5 كـ North Star معماري. يُطبَّق على كل خطوة انتقالية لاحقة.



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

## D-029 · docker-compose.step3.yml as Isolated Step 3 Activation File
**Decision**: الخطوة الانتقالية الثالثة تستخدم `docker-compose.step3.yml` منفصلاً عن `docker-compose.yml` الرئيسي.
**Reason**: `docker-compose.yml` الرئيسي يُشغِّل الـ stack الكامل (20+ خدمة) وهو ثقيل جداً للتطوير. `docker-compose.step3.yml` يُشغِّل 3 خدمات فقط (postgres-orchestrator + redis-orchestrator + orchestrator-service) مع volumes مستقلة لا تتعارض مع الـ stack الرئيسي.
**Consequence**: يمكن تشغيل Step 3 بجانب الـ devcontainer الافتراضي بدون تعارض. المنافذ 5441/6380/8006 لا تتعارض مع أي خدمة في الـ devcontainer.
**Rollback**: `docker compose -f docker-compose.step3.yml down` يوقف الـ stack بالكامل. المونوليث يعود تلقائياً إلى LangGraph local fallback.
**Status**: IMPLEMENTED 2026-05-10 — see `feat/microservices-step3-live-activation`.

## D-030 · Ona automations.yaml as Step 3 Canonical Trigger
**Decision**: `.ona/automations.yaml` هو المُشغِّل الرسمي للخطوة 3 في بيئة Ona/Gitpod.
**Reason**: يوفر تجربة موحدة: `gitpod automations service start orchestrator-stack` يُشغِّل الـ stack + يتحقق من الصحة + يُبلِّغ عن الحالة. لا يتطلب معرفة بـ docker compose مباشرة.
**Services vs Tasks**: `orchestrator-stack` هو service (يعمل باستمرار، له `ready` command). `health-probe`, `verify-stack`, `run-step3-tests` هي tasks (تُشغَّل يدوياً عند الطلب).
**Schema constraint**: Services لا تدعم `dependsOn` (schema rejects it). الترتيب يُدار عبر `ready` command فقط.
**Status**: IMPLEMENTED 2026-05-10 — see `.ona/automations.yaml`.

## D-031 · OUTBOX_RELAY_ENABLED=true in Step 4 (D-031 fulfilled)
**Decision**: يُعطَّل outbox relay في Step 3 (`OUTBOX_RELAY_ENABLED=false`). يُفعَّل في Step 4 بعد التحقق من مسار الـ persistence الكامل.
**Reason**: تفعيل outbox relay قبل التحقق من D-006 (single persistence owner) يخاطر بـ dual-write. Step 3 يُثبت أن الخدمة تعمل وتُجيب على `/health`. Step 4 يُثبت أن الـ persistence صحيح.
**Status**: IMPLEMENTED 2026-05-10 — `supervisor.sh` و `.ona/automations.yaml` يُشغِّلان orchestrator مع `OUTBOX_RELAY_ENABLED=true`. انظر `feat/microservices-step4-persistence-relay`.

## D-032 · Independent prometheus_client Registry per Microservice
**Decision**: كل microservice يُصدِّر `/metrics` يجب أن يستخدم `CollectorRegistry()` مستقل — لا يشارك الـ default REGISTRY مع المونوليث أو أي خدمة أخرى.
**Reason**: في بيئات الاختبار والـ CI، قد يعمل المونوليث والـ orchestrator في نفس الـ process. استخدام الـ default REGISTRY يُسبب `ValueError: Duplicated timeseries` عند تسجيل نفس اسم المقياس مرتين.
**Implementation**: `microservices/orchestrator_service/src/core/prom_metrics.py` — `_REGISTRY = CollectorRegistry()` مع lazy init. كل counter/gauge/histogram يمرر `registry=_REGISTRY`.
**Status**: IMPLEMENTED 2026-05-10 — انظر `feat/microservices-step4-persistence-relay`.

## D-033 · /metrics Endpoint as Prometheus Scrape Target (Step 4)
**Decision**: `orchestrator-service` يجب أن يُصدِّر `/metrics` بصيغة Prometheus text format حقيقية (ليس JSON golden signals).
**Reason**: Prometheus يتوقع text format من `prometheus_client.generate_latest()`. الـ `/metrics` endpoint الموجود في `routes.py` يُعيد JSON (golden signals) — غير متوافق مع Prometheus scrape. Step 4 يضيف endpoint منفصل في `main.py` يستخدم `export_prometheus_text()` من `prom_metrics.py`.
**Metrics exposed**: `cogniforge_outbox_relay_cycles_total`, `cogniforge_outbox_relay_processed_total`, `cogniforge_outbox_relay_failed_total`, `cogniforge_outbox_relay_skipped_total`, `cogniforge_outbox_pending_gauge`, `cogniforge_stategraph_invocations_total`, `cogniforge_stategraph_duration_seconds`, `cogniforge_stategraph_errors_total`, `cogniforge_orchestrator_requests_total`, `cogniforge_orchestrator_request_duration_seconds`, `cogniforge_orchestrator_startup_info`.
**Status**: IMPLEMENTED 2026-05-10 — انظر `feat/microservices-step4-persistence-relay`.

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


## D-034 · User Service Activated as uvicorn Process on :8001 — Step 5 (2026-05-10)
**Decision**: `user-service` is activated as a uvicorn process on `:8001` in Codespaces (no Docker). It is the second microservice to go ACTIVE alongside `orchestrator-service` (:8006). Starts automatically via `supervisor.sh:launch_user_service()` (STEP 4E) when `DATABASE_URL` is set.
**Reason**: Step 4 proved the uvicorn-process pattern for microservice activation in Codespaces (no Docker-in-Docker). `user-service` is the natural next candidate: it has a complete FastAPI app, its own DB schema, auth routes, and UMS routes. Adding `/metrics` (prometheus_client) makes it fully observable.
**Port**: `:8001` — matches the existing `docker-compose.yml` port assignment for `user-service`.
**DB**: `USER_DATABASE_URL` (defaults to `DATABASE_URL` — Supabase shared). Separate schema from orchestrator.
**Metrics**: 11 `cogniforge_user_*` metrics in independent `CollectorRegistry`. `/metrics` endpoint at `localhost:8001/metrics`. Prometheus scrape target added with `step="5"` label.
**Grafana**: Dashboard `80-microservices-step5-user-service.json` (UID `cogniforge-ms-step5-user-service`, 17 panels, 10s refresh).
**CI gate**: `.github/workflows/microservices-step5-user-service.yml` (6 jobs).
**What MUST NOT change without an ADR**:
- The port `:8001` for user-service (matches docker-compose.yml).
- The `CollectorRegistry` isolation pattern — never use the default REGISTRY.
- The `step="5"` label in `cogniforge_user_startup_info` — used by CI gate and Grafana.
**Status**: IMPLEMENTED 2026-05-10 — branch `feat/microservices-step5-user-service`.

## D-025 · ChatRoutingPolicy Default Changed to state_graph — Step 2 Transition (2026-05-10)
**Decision**: `ChatRoutingPolicy.from_environment()` now defaults to `endpoint_mode="state_graph"`, routing to `/api/chat/messages` (StateGraph 13 nodes) instead of `/agent/chat` (OrchestratorAgent). Controlled by `ORCHESTRATOR_CHAT_ENDPOINT` env var.
**Reason**: D-021 identified that even when the orchestrator microservice is running, the 13-node StateGraph was never invoked because `ChatRoutingPolicy.candidate_urls()` always returned `/agent/chat`. The StateGraph (with DSPy, Tavily, reranker, synthesizer) is the intended production handler. The routing policy was the only blocker.
**Rollback**: Set `ORCHESTRATOR_CHAT_ENDPOINT=agent` in the monolith's environment. Takes effect immediately without restart (read per-request from env). No code change required.
**Observability**: `cogniforge_routing_mode_state_graph` gauge (1=StateGraph, 0=Agent) and `cogniforge_routing_target_total{target=...}` counter emitted per request. Visible in Grafana :3001 → "Microservices Transition — Step 2" dashboard.
**CI gate**: `.github/workflows/microservices-transition.yml` — `routing-policy-gate` job asserts default mode is `state_graph` on every PR touching `routing_policy.py`.
**What MUST NOT change without an ADR**:
- The default value of `ORCHESTRATOR_CHAT_ENDPOINT` (currently `"state_graph"`).
- The `_ENDPOINT_MAP` keys — adding a new mode requires an ADR.
- The `targets_state_graph` property — it is used by the CI gate and monitoring.
**Status**: IMPLEMENTED 2026-05-10 — branch `feat/microservices-step2-stategraph-routing`.

## D-018 · Exercise Retrieval Uses Two-Phase Intent Classifier, Not Keyword List (ISS-038)
**Decision**: `detect_exercise_retrieval()` in `app/services/capabilities/exercise_retrieval.py`
uses a two-phase intent classifier instead of a flat keyword list.
**Reason**: A flat keyword list on `"تمرين"` / `"احتمالات"` / `"درس"` causes context blindness.
Since `knowledge_base/` contains exactly one file, any false-positive trigger returns the
probability BAC exercise unconditionally — regardless of what the student asked. A student
asking "اشرح الجزء أ من هذا التمرين" received a probability exercise instead of an explanation.
**The two phases**:
1. **Explanation-intent guard** (highest priority): patterns like `"اشرح"`, `"كيف"`, `"هذا التمرين"`,
   `"ساعدني"`, `"explain"`, `"help me"`, `"الجزء أ"` cancel retrieval even when "تمرين" is present.
2. **Explicit retrieval trigger**: patterns like `"تمرين بكالوريا"`, `"التمرين الأول"`, `"exercise 1"`,
   `"الموضوع الأول"`, year+exercise combos trigger retrieval.
3. **Default**: no retrieval → fall through to LangGraph.
**New field**: `ExerciseRetrievalDecision.reason` (optional str, default `""`) — audit trail for
debugging misclassifications. Backward-compatible: callers only read `.recognized`.
**Consequence**:
- Explanation/help questions now fall through to LangGraph, which handles them correctly.
- Explicit BAC retrieval requests still work as before.
- Adding new trigger keywords requires a corresponding negation pattern — enforced by 25 regression tests.
**What MUST NOT change**:
- The explanation-intent list must always take priority over the retrieval list.
- The `reason` field must not be removed — it is the only audit trail for misclassification debugging.
- New keywords must not be added to the retrieval list without a corresponding explanation-intent guard.
**Status**: IMPLEMENTED 2026-05-10 — branch `fix/exercise-retrieval-context-blindness`.
