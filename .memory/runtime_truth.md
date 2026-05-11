# Runtime Truth Lock
> Last updated: **2026-05-11** | Branch: `feat/live-runtime-audit-d043`
> Audit method: Direct HTTP probes + Prometheus /api/v1/targets + Grafana /api/search
> Authority: this file overrides any contradictory aspirational doc in `docs/` or root markdown.

## Golden rule
A capability counts as real ONLY when proven by **all three** of:
1. **import** — the module is imported by code reachable from `app/main.py`.
2. **call chain** — there is a live caller that flows from a router/middleware/startup hook.
3. **runtime evidence** — the code actually executes on the production path (logs, traces, DB writes).

Missing any one → DORMANT, ZOMBIE, or UNKNOWN. No exceptions.

## Status legend
| Status | Meaning |
|--------|---------|
| **ACTIVE** | import + call chain + runtime evidence all present |
| **ACTIVE (no-op without ENV_VAR)** | import + call chain present; runtime effect absent without a specific env var |
| **PARTIAL** | on a live chain but only via fallback, conditional, or non-default branch |
| **DORMANT** | code real, gated behind an external service not started by default |
| **ZOMBIE** | no live call chain from any production entrypoint |
| **UNKNOWN** | insufficient evidence |

---

## Infrastructure truth (updated 2026-05-10 — Step 5 pass)

| Service | Port | Status | Evidence |
|---------|------|--------|----------|
| **Next.js** | **3000** | **ACTIVE** | supervisor.sh `--port 3000` overrides package.json `--port 5000`. HTML 200 confirmed. `allowedDevOrigins` includes `*.app.github.dev`. |
| **FastAPI** | **8000** | **ACTIVE** | `GET /health → {"application":"ok","database":"ok"}`. Requires DATABASE_URL in **process env**. |
| **orchestrator-service** | **8006** | **ACTIVE** | Step 4. uvicorn process. `OUTBOX_RELAY_ENABLED=true`. `/metrics` → 11 `cogniforge_outbox_*`+`cogniforge_stategraph_*` metrics. `graph_ready:true`, `startup_state:ready` confirmed live. ISS-040 fix: port 5432 (direct PG) instead of 6543 (PgBouncer) in supervisor.sh. `database.py` lazy engine singleton. |
| **user-service** | **8001** | **ACTIVE** | Step 5. uvicorn process. `/metrics` → 11 `cogniforge_user_*` metrics. Auto-starts via supervisor.sh when `DATABASE_URL` set. |
| **planning-agent** | **8002** | **ACTIVE** | Step 6. uvicorn process. `/metrics` → 11 `cogniforge_planning_*` metrics. DSPy+LangGraph (fallback when no OPENROUTER_API_KEY). Requires `postgresql+asyncpg://` URL (ISS-038-B). Auto-starts via supervisor.sh when `DATABASE_URL` set. |
| **research-agent** | **8007** | **ACTIVE** | Step 7. uvicorn process. `/metrics` → 11 `cogniforge_research_*` metrics. Tavily web search ACTIVE when `TAVILY_API_KEY` set. ISS-039: lazy `_get_super_search()` singleton prevents import-time credential errors. Auto-starts via supervisor.sh when `DATABASE_URL` set. Live verified: `/health → {"step":"7","tavily_available":"true"}`. |
| **reasoning-agent** | **8008** | **ACTIVE** | Step 8. uvicorn process. `/metrics` → 11 `cogniforge_reasoning_*` metrics. MCTS always enabled. LLM: openrouter when `OPENROUTER_API_KEY` set, openai when `OPENAI_API_KEY` set, mock otherwise. ISS-039-B: `main.py` does NOT import `ai_service` at module level. Auto-starts via supervisor.sh when `DATABASE_URL` set. Live verified 2026-05-11: `/health → {"status":"healthy","step":"8","llm_backend":"openrouter","mcts_enabled":"true"}` \| `/metrics → cogniforge_reasoning_startup_info{...,step="8",...} 1.0`. |
| **Skills Pipeline** | **8006/compose** | **ACTIVE** | Step 11. `/compose` endpoint في orchestrator-service. Calls planning:8002 + research:8007 + reasoning:8008 بالتوازي الكامل (`asyncio.gather` 3-way). ISS-042: Service Token (JWT HS256) مُرسَل لـ planning-agent. DSPy 3.x fix: `dspy.LM` بدلاً من `dspy.OpenAI`. Timeout: 55s. Live verified 2026-05-11: `POST /compose → pipeline_mode="full", skills_active=["planning","research","reasoning"], total_ms=32069`. |
| **Postgres Checkpointer** | **8006/checkpointer/status** | **ACTIVE** | Step 10. `AsyncPostgresSaver` (subclass `_InstrumentedCheckpointer`) — LangGraph state persisted to PostgreSQL. 6 new Prometheus metrics: `cogniforge_checkpointer_*`. Live verified 2026-05-11: `GET /checkpointer/status → {"backend":"postgres","step":"10","active":true,"tables_ready":true}` \| `cogniforge_checkpointer_writes_total{status="success",thread_id_prefix="warmup"} 7.0` \| `cogniforge_checkpointer_backend_info{backend="postgres",step="10",tables_ready="true"} 1.0` \| `cogniforge_orchestrator_startup_info{checkpointer_backend="postgres",graph_ready="true"} 1.0`. ISS-041: `_InstrumentedCheckpointer` يرث من `AsyncPostgresSaver` مباشرةً (subclass لا wrapper) لأن LangGraph يتحقق من `isinstance(BaseCheckpointSaver)`. |
| **content-retrieval-skill** | **8009** | **ACTIVE** | Step 11. Skill مستقلة لاسترجاع المحتوى التعليمي من knowledge_base/. intent_classifier (explanation/retrieval/unknown) + retrieval_engine (score-based). 7 Prometheus metrics: `cogniforge_retrieval_*`. ISS-038 fix: explanation context blocks retrieval. Live verified 2026-05-11: `GET /health → {"status":"healthy","step":"11","kb_files":2}` \| `POST /retrieve {"question":"أريد تمرين بكالوريا"} → intent="retrieval" total=1` \| `POST /retrieve {"question":"اشرح الجزء أ"} → intent="explanation" total=0`. |
| **conversation-service** | **8003** | **ACTIVE** | Step 12. D-042. Skill مستقلة لإدارة المحادثات التعليمية. LangGraph StateGraph: `intent_node → response_node`. `ConversationState` TypedDict. `_classify_intent()` deterministic (no LLM). Fallback mode بدون OPENROUTER_API_KEY. 11 Prometheus metrics: `cogniforge_conversation_*`. HTTP `POST /chat/message` + WS `/chat/ws` + `/admin/chat/ws`. Lazy DB singleton + asyncpg URL normalization. Auto-starts via supervisor.sh STEP 4J. 117 tests pass. |
| **Grafana** | **3001** | **ACTIVE** | `GET /api/health → {"database":"ok"}`. **16 dashboards** (Steps 2–12). Prometheus datasource UP. |
| **Prometheus** | **9090** | **ACTIVE** | `GET /-/healthy → Healthy`. **12 scrape targets ALL UP**: fastapi, grafana, prometheus, orchestrator-service(:8006), user-service(:8001), planning-agent(:8002), conversation-service(:8003), research-agent(:8007), reasoning-agent(:8008), skills-pipeline(:8006), postgres-checkpointer(:8006), content-retrieval-skill(:8009). |
| **Redis** | **6379** | **ACTIVE (process only)** | ping OK. REDIS_URL not set → app uses InMemoryCache. |
| **PostgreSQL** | **6543** | **ACTIVE** | PostgreSQL 17.6 Supabase PgBouncer. database:ok confirmed. |
| **OpenRouter** | external | **ACTIVE** | Primary: nvidia/nemotron-3-super-120b-a12b:free. Live graph call confirmed. |

---

## Root cause of the "Partial/Degraded Runtime" problem (ISS-034 — RESOLVED 2026-05-09)

**Symptom**: Uvicorn PID alive, port 8000 not listening, state file shows `app_healthy` from previous run.

**Root cause chain**:
1. `devcontainer.json` maps `DATABASE_URL` from `${localEnv:DATABASE_URL}` — in Ona/Gitpod, secrets are NOT injected as process env vars.
2. `supervisor.sh` created `.env` with `DATABASE_URL=sqlite+aiosqlite:///./dev.db` as placeholder.
3. `app/core/settings/base.py:23` reads `os.environ.get("APP_DATABASE_URL")` at **module import time** — before pydantic-settings reads `.env`. Finds empty string.
4. `_ensure_database_url()` raises `ValueError` in `development` environment.
5. Uvicorn worker crashes on import. Port 8000 never opens.
6. `supervisor.sh` health check reads stale `app_healthy` state file → reports healthy. **Misleading observability.**

**Fix applied** (this branch):
- `supervisor.sh:_inject_env_secrets()` — reads real secrets from process env, writes to `.env`.
- `supervisor.sh:_export_env_file()` — exports `.env` keys into shell process before `python -m uvicorn` so module-level `os.environ.get()` finds the real value.
- `supervisor.sh:_uvicorn_healthy()` — checks PID alive AND port responding; kills stale zombie before restart.
- `supervisor.sh` health check — always re-probes live endpoint; never trusts stale state files.
- Degraded mode (no DATABASE_URL) no longer crashes supervisor — Grafana + Prometheus stay up.

---

## Orchestrator lifespan problem (ISS-035 — RESOLVED 2026-05-09)

**Symptom**: Orchestrator uvicorn alive, `/health` returns 200, but graph nodes don't execute.

**Root cause**: `lifespan()` warmup `ainvoke()` had no timeout → could block indefinitely. `RuntimeError` from warmup propagated up → crashed ASGI startup. Only `ModuleNotFoundError` was caught.

**Fix applied** (`microservices/orchestrator_service/main.py`):
- Warmup wrapped in `asyncio.wait_for(..., timeout=30.0)`.
- All non-DB exceptions caught → logged as DEGRADED, not fatal.
- `app.state.startup_state` tracks `"ready"` / `"degraded"`.
- `/health` endpoint exposes `startup_state` and `startup_errors`.

---

## LangGraph metrics (ISS-029 — PARTIALLY RESOLVED 2026-05-09)

**Previous state**: `cogniforge_langgraph_*` — zero emitters. Dashboard panels permanently empty.

**Fix applied** (`app/services/chat/local_graph.py` + `app/telemetry/metrics.py`):
- `_supervisor_node`: emits `langgraph.intent.total`, `langgraph.node.count.total`, `langgraph.node.duration_seconds`.
- `_chat_node`: emits `langgraph.node.count.total`, `langgraph.node.duration_seconds`.
- `metrics.py:hist_names` extended with `langgraph.node.duration_seconds`.

**Verified live**: `cogniforge_langgraph_intent_total{graph="local",intent="general"} 1.0` confirmed.

**Still ZOMBIE**: `cogniforge_langgraph_checkpointer_writes_total` — no emitter. Requires Postgres checkpointer (ISS-020).

---

## Prometheus scrape targets (verified live 2026-05-09)

| Job | URL | Health |
|-----|-----|--------|
| `cogniforge-fastapi` | `http://localhost:8000/api/v1/observability/prometheus` | **UP** |
| `grafana` | `http://localhost:3001/metrics` | **UP** |
| `prometheus` | `http://localhost:9090/metrics` | **UP** |

---

## Supervisor crash — `local` outside function (ISS-037 — RESOLVED 2026-05-09)

**Symptom**: After merging commit `3fd78247`, ALL ports dead (3000, 8000, 3001, 9090). Supervisor log shows:
```
/app/.devcontainer/supervisor.sh: line 336: local: can only be used in a function
[ERROR] Supervisor failed at line 336
```

**Root cause**: commit `3fd78247` added `local stale_pid` at top-level scope in `supervisor.sh` (inside an `if/else` block but outside any `function`). bash rejects `local` outside functions → supervisor exits at Step 4 → uvicorn never starts → all ports dead.

**Fix applied** (`.devcontainer/supervisor.sh`):
- `local stale_pid` → `stale_pid` (removed `local` keyword — variable is already in a subshell context)

**Additional fix**: Added `.devcontainer/secrets.env` fallback read at the top of `_inject_env_secrets()`. When Codespaces Secrets are not configured, supervisor now reads credentials from this git-ignored file instead of falling back to SQLite. Template at `.devcontainer/secrets.env.example`.

**Verified live** (2026-05-09):
- Supervisor runs to completion: `✅ Backend is healthy and ready!`
- `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`
- `GET http://localhost:3000/ → HTTP 200`
- No `local: can only be used in a function` error

---

## Codespaces Next.js proxy fix (ISS-036 — RESOLVED 2026-05-09)

**Symptom**: Port 3000 in GitHub Codespaces returns `ERR_HTTP_RESPONSE_CODE_FAILURE` even when Next.js is running and responding 200 on localhost.

**Root cause**: `frontend/next.config.js` `allowedDevOrigins` listed only Replit domains. Next.js 15+ enforces origin validation on the dev server — requests proxied through `*.app.github.dev` (Codespaces tunnel) were rejected at the framework level before reaching any route handler.

**Fix applied** (`frontend/next.config.js`):
- Added `*.app.github.dev` and `*.preview.app.github.dev` to `allowedDevOrigins`.
- Added `*.gitpod.io` and `*.ws-eu*.gitpod.io` for Gitpod/Ona environments.

**Verified live**:
- `curl -s http://localhost:3000/ → HTTP 200`
- `curl -H "Origin: https://didactic-giggle-7vwwj76p66vfrjg4-3000.app.github.dev" http://localhost:3000/ → HTTP 200`
- FastAPI: `GET /health → {"application":"ok","database":"ok","version":"v4.1-root"}`

---

## Full capability truth table (2026-05-09 — sixth pass)

| # | Component | File | Status | Evidence |
|---|-----------|------|--------|---------|
| 1 | Monolith API — customer WS | `app/api/routers/customer_chat.py` | **ACTIVE** | `chat_stream_ws` is the live entrypoint. 62 routes registered. |
| 2 | Monolith API — admin WS | `app/api/routers/admin.py` | **ACTIVE** | Admin WS entrypoint. `_emit_terminal_frames` guarantees exactly one terminal frame per turn. |
| 3 | Terminal frame guarantee | `_emit_terminal_frames` in `customer_chat.py` + `admin.py` | **ACTIVE** | Single emitter for `assistant_final`/`error`. Exactly one frame per turn. |
| 4 | RealityKernel / app composition | `app/kernel.py` | **ACTIVE** | Composition root. Loaded at startup via `app/main.py`. |
| 5 | Frontend Next.js | `frontend/` | **ACTIVE** | Port 3000, HTML confirmed |
| 6 | LangGraph local engine (2 nodes) | `app/services/chat/local_graph.py` | **PARTIAL** | Fallback tier 3. Live confirmed. |
| 7 | LangGraph metrics emission | `app/services/chat/local_graph.py` → `unified_observability` | **ACTIVE** | `cogniforge_langgraph_*` emitted per turn (NEW this branch) |
| 8 | OrchestratorClient fallback chain | `app/infrastructure/clients/orchestrator_client.py` | **ACTIVE** | 4-tier fallback. Tier 3 (LangGraph) is primary handler. |
| 9 | LangGraph multi-agent workflow | `app/services/chat/graph/workflow.py` | **ZOMBIE** | Only test file imports it |
| 10 | KAgent Mesh | `app/services/kagent/` | **ZOMBIE** | DI-registered, only consumer is dead workflow |
| 11 | MCP | `app/services/mcp/` | **DORMANT** | Lazy-imported by side-path agents not on WS path |
| 12 | Reranker / LlamaIndex / DSPy | `microservices/research_agent`, `orchestrator_service` | **DORMANT** | Blocked by dormant microservices |
| 13 | Tavily | `orchestrator_service/src/services/overmind/graph/search.py` | **DORMANT** | Key in .env, orchestrator not running |
| 14 | Advanced orchestrator StateGraph (13 nodes) | `orchestrator_service/src/services/overmind/graph/main.py` | **DORMANT→PARTIAL** | Compiles in isolation (verified live 2026-05-10 with real OPENROUTER_API_KEY). 3 blockers removed (H1/H2/H3). Needs `docker compose up orchestrator-service` to reach ACTIVE. |
| 27 | ChatRoutingPolicy — endpoint_mode | `app/infrastructure/clients/routing_policy.py` | **ACTIVE** | Default: `state_graph` → `/api/chat/messages`. Rollback: `ORCHESTRATOR_CHAT_ENDPOINT=agent` → `/agent/chat`. D-021 implemented 2026-05-10. |
| 28 | Routing metrics | `app/infrastructure/clients/orchestrator_client.py` | **ACTIVE** | `cogniforge_routing_mode_state_graph` gauge + `cogniforge_routing_target_total{target=...}` counter emitted per chat request. |
| 29 | Microservices Transition Dashboard (Step 2) | `observability/grafana/dashboards/50-microservices-transition.json` | **ACTIVE** | 15 panels on Grafana :3001. UID: cogniforge-ms-transition-step2. Shows routing mode, StateGraph metrics, Tavily, microservices health matrix, fallback chain progress. |
| 30 | Microservices Prometheus scrape | `observability/prometheus/prometheus.yml` | **ACTIVE (targets DOWN by default)** | orchestrator-service:8006, research-agent:8007, user-service:8001, planning-agent:8002 added. DOWN until `docker compose -f docker-compose.step3.yml up -d`. |
| 31 | Microservices Transition CI gate (Step 2) | `.github/workflows/microservices-transition.yml` | **ACTIVE** | 5-job workflow: routing-policy-gate / stategraph-compile-gate / dashboard-schema-gate / prometheus-config-gate / transition-gate. Triggers on routing_policy.py changes. |
| 32 | docker-compose.step3.yml | `docker-compose.step3.yml` | **REFERENCE ONLY in Codespaces** | Docker not available in devcontainer. File exists for local/CI environments with Docker. In Codespaces: supervisor.sh is the activation path. |
| 33 | Ona automation — orchestrator-service | `.ona/automations.yaml` | **ACTIVE** | service: `orchestrator-service` (uvicorn start/ready/stop). tasks: `health-probe`, `verify-stack`, `restart-orchestrator`, `run-step3-tests`. Trigger: `gitpod automations service start orchestrator-service`. |
| 34 | Grafana dashboard Step 3 | `observability/grafana/dashboards/60-microservices-step3-live.json` | **ACTIVE** | 20 panels. UID: cogniforge-ms-step3-live. Refresh: 10s. Covers: orchestrator health, routing distribution, LangGraph nodes, intent classification, fallback chain, memory/CPU. |
| 35 | Step 3 CI gate | `.github/workflows/microservices-step3-live.yml` | **ACTIVE** | 7-job workflow: compose-validation / stategraph-compile-gate / dashboard-gate / prometheus-config-gate / transition-tests / automations-validation / step3-gate. PR comment with results. |
| 36 | orchestrator-service (Step 4 — OUTBOX_RELAY + /metrics) | `microservices/orchestrator_service/` + `supervisor.sh:launch_orchestrator_service()` | **DORMANT→ACTIVE (auto at boot when OPENROUTER_API_KEY set)** | Step 4: OUTBOX_RELAY_ENABLED=true (relay loop every 15s). /metrics endpoint returns prometheus_client text format. prom_metrics.py: 11 metrics (outbox_relay_*, stategraph_*, startup_info). Port 8006. |
| 37 | native/prometheus.yml — orchestrator scrape (Step 4) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until process starts)** | job: orchestrator-service, target: localhost:8006/metrics, step="4". Scrapes prometheus_client text format. DOWN until supervisor.sh launches the process. |
| 38 | prom_metrics.py — orchestrator Prometheus registry | `microservices/orchestrator_service/src/core/prom_metrics.py` | **ACTIVE (when orchestrator running)** | Independent CollectorRegistry. 11 metrics. export_prometheus_text() → /metrics endpoint. record_outbox_relay_cycle() called from _outbox_relay_loop. set_startup_info() called in lifespan Phase 6. |
| 39 | Grafana dashboard Step 4 | `observability/grafana/dashboards/70-microservices-step4-persistence.json` | **ACTIVE** | 24 panels. UID: cogniforge-ms-step4-persistence. Refresh: 10s. Covers: startup_info, outbox relay cycles/rates, StateGraph heatmap, HTTP P50/P95/P99, active connections, scrape health. |
| 40 | Step 4 CI gate | `.github/workflows/microservices-step4.yml` | **ACTIVE** | 5-job workflow: static-checks / lint / step4-tests (44) / step3-regression / pr-summary. Triggers on orchestrator_service changes. |
| 41 | planning-agent (Step 6 — DSPy + LangGraph + /metrics) | `microservices/planning_agent/` + `supervisor.sh:launch_planning_agent()` | **ACTIVE (auto at boot when DATABASE_URL set)** | Step 6: DSPy+LangGraph plan generation with fallback chain. /metrics endpoint returns prometheus_client text format. prom_metrics.py: 11 metrics (planning_requests_*, planning_plans_*, planning_dspy_*, planning_db_*, startup_info{step="6",dspy_available=...}). Port 8002. |
| 42 | native/prometheus.yml — planning-agent scrape (Step 6) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until process starts)** | job: planning-agent, target: localhost:8002/metrics, step="6". Scrapes prometheus_client text format. DOWN until supervisor.sh launches the process. |
| 43 | prom_metrics.py — planning-agent Prometheus registry | `microservices/planning_agent/prom_metrics.py` | **ACTIVE (when planning-agent running)** | Independent CollectorRegistry. 11 metrics. export_prometheus_text() → /metrics endpoint. record_plan_created() / record_dspy_invocation() / set_startup_info() callable from main.py. |
| 44 | Grafana dashboard Step 6 | `observability/grafana/dashboards/90-microservices-step6-planning-agent.json` | **ACTIVE** | 20 panels. UID: cogniforge-ms-step6-planning-agent. Refresh: 10s. Covers: startup_info, HTTP traffic, plan generation (success/fallback), DSPy invocations, DB ops, microservices health matrix, Docker Compose guide. |
| 45 | Step 6 CI gate | `.github/workflows/microservices-step6-planning-agent.yml` | **ACTIVE** | 7-job workflow: static-checks / compose-gate / dashboard-gate / lint / step6-tests (61) / step5-regression / pr-summary. PR comment with results. |
| 46 | docker-compose.step6.yml | `docker-compose.step6.yml` | **REFERENCE (Docker environments only)** | Docker Compose stack: orchestrator-service + user-service + planning-agent. In Codespaces: supervisor.sh is the activation path. For local Docker: `docker compose -f docker-compose.step6.yml up -d`. |
| 47 | Ona automation — planning-agent | `.ona/automations.yaml` | **ACTIVE** | service: `planning-agent` (uvicorn start/ready/stop). tasks: `verify-step6-planning-agent`, `restart-planning-agent`, `run-step6-tests`, `docker-compose-stack`. |
| 48 | reasoning-agent (Step 8 — MCTS + LLM + /metrics) | `microservices/reasoning_agent/` + `supervisor.sh:launch_reasoning_agent()` | **ACTIVE (auto at boot when DATABASE_URL set)** | Step 8: MCTS always enabled. LLM via openrouter/openai/mock. /metrics endpoint returns prometheus_client text format. prom_metrics.py: 11 metrics (reasoning_requests_*, reasoning_invocations_*, reasoning_mcts_*, reasoning_llm_*, reasoning_fallback_*, startup_info{step="8",llm_backend=...,mcts_enabled="true"}). Port 8008. ISS-039-B: no import-time AIService instantiation in main.py. |
| 49 | native/prometheus.yml — reasoning-agent scrape (Step 8) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until process starts)** | job: reasoning-agent, target: localhost:8008/metrics, step="8". Scrapes prometheus_client text format. DOWN until supervisor.sh launches the process. |
| 50 | prom_metrics.py — reasoning-agent Prometheus registry | `microservices/reasoning_agent/prom_metrics.py` | **ACTIVE (when reasoning-agent running)** | Independent CollectorRegistry. 11 metrics. export_prometheus_text() → /metrics endpoint. record_reasoning_invocation() / record_mcts_expansion() / record_llm_call() / set_startup_info() callable from routes.py and main.py. |
| 51 | Skills Composition Pipeline (Step 9 — /compose) | `microservices/orchestrator_service/src/services/skills_pipeline.py` + `src/api/routes.py:/compose` | **ACTIVE** | Step 9. `run_skills_pipeline()` calls planning:8002 + research:8007 via asyncio.gather (parallel), then reasoning:8008 with composed context. X-Correlation-ID on every HTTP call. Fallback mode: ConnectError/TimeoutException → SkillResult(status="fallback"). 6 new Prometheus metrics: cogniforge_pipeline_invocations_total{mode=full\|partial\|fallback}, cogniforge_pipeline_duration_seconds, cogniforge_pipeline_skill_calls_total{skill,status}, cogniforge_pipeline_skill_duration_seconds, cogniforge_pipeline_errors_total, cogniforge_pipeline_active_gauge. startup_info{pipeline_enabled="true"}. Live verified: POST /compose → pipeline_mode="partial", skills_active=["research","reasoning"]. |
| 52 | Grafana dashboard Step 9 | `observability/grafana/dashboards/120-microservices-step9-skills-pipeline.json` | **ACTIVE** | 12 panels. UID: cogniforge-ms-step9-pipeline. Refresh: 10s. Covers: startup_info, pipeline invocations by mode, P50/P95/P99 latency, skill calls (success/fallback/error), skill duration by skill, health matrix (steps 4-9). |
| 53 | skills-pipeline Prometheus scrape (Step 9) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until orchestrator starts)** | job: skills-pipeline, target: localhost:8006/metrics, step="9". Scrapes cogniforge_pipeline_* metrics. Same process as orchestrator-service:8006 — separate job for step label. |
| 54 | Step 9 CI gate | `.github/workflows/microservices-step9-skills-pipeline.yml` | **ACTIVE** | 7-job workflow: static-checks / prometheus-gate / dashboard-gate / lint / step9-tests (87) / regression-steps-4-8 / pr-summary. Triggers on skills_pipeline.py, prom_metrics.py, routes.py changes. |
| 55 | Postgres Checkpointer (Step 10) | `microservices/orchestrator_service/src/core/database.py:_InstrumentedCheckpointer` | **ACTIVE** | Step 10. `_InstrumentedCheckpointer` يرث من `AsyncPostgresSaver` (subclass لا wrapper — ISS-041). `_make_instrumented_class(AsyncPostgresSaver)` ينشئ subclass يقبله LangGraph. `AsyncConnectionPool` (psycopg, max_size=5). جداول checkpoint موجودة في Postgres. Live: writes=7, reads=3, errors=0. |
| 56 | Checkpointer Prometheus metrics (Step 10) | `microservices/orchestrator_service/src/core/prom_metrics.py` | **ACTIVE** | 6 مقاييس جديدة: `cogniforge_checkpointer_writes_total{thread_id_prefix,status}`, `cogniforge_checkpointer_reads_total{thread_id_prefix,status}`, `cogniforge_checkpointer_duration_seconds{operation}`, `cogniforge_checkpointer_errors_total{error_type}`, `cogniforge_checkpointer_active_threads`, `cogniforge_checkpointer_backend_info{backend,step,pool_size,tables_ready}`. `set_startup_info` أُضيف إليه `checkpointer_backend` label. Live: backend_info{backend="postgres",step="10",tables_ready="true"} 1.0. |
| 57 | /checkpointer/status endpoint (Step 10) | `microservices/orchestrator_service/src/api/routes.py` | **ACTIVE** | `GET /checkpointer/status` → `{"backend":"postgres","step":"10","active":true,"tables_ready":true,"active_threads":1,"pool_size":5}`. Runtime evidence للـ checkpointer. |
| 58 | Grafana dashboard Step 10 | `observability/grafana/dashboards/130-microservices-step10-postgres-checkpointer.json` | **ACTIVE** | 13 panels. UID: cogniforge-ms-step10-checkpointer. Refresh: 10s. Covers: backend info, active threads, writes/reads rate, duration P50/P95/P99, errors by type, health matrix (steps 4-10). |
| 59 | postgres-checkpointer Prometheus scrape (Step 10) | `observability/native/prometheus.yml` | **ACTIVE (target DOWN until orchestrator starts)** | job: postgres-checkpointer, target: localhost:8006/metrics, step="10". Scrapes cogniforge_checkpointer_* metrics. |
| 60 | Step 10 CI gate | `.github/workflows/microservices-step10-postgres-checkpointer.yml` | **ACTIVE** | 7-job workflow: static-checks / routes-gate / infrastructure-gate / lint / step10-tests (101) / regression-steps-4-9 / pr-summary. |
| 55 | config.py service_map port fix | `microservices/orchestrator_service/src/core/config.py` | **FIXED** | planning-agent was mapped to port 8001 (wrong). Fixed to 8002. research-agent: 8007. reasoning-agent: 8008. user-service: 8001. |
| 56 | supervisor.sh CODESPACES + Skills URLs | `.devcontainer/supervisor.sh:launch_orchestrator_service()` | **ACTIVE** | Added CODESPACES=true + PLANNING_AGENT_URL=http://localhost:8002 + RESEARCH_AGENT_URL=http://localhost:8007 + REASONING_AGENT_URL=http://localhost:8008 + USER_SERVICE_URL=http://localhost:8001 to orchestrator launch env. |
| 51 | Grafana dashboard Step 8 | `observability/grafana/dashboards/110-microservices-step8-reasoning-agent.json` | **ACTIVE** | 20+ panels. UID: cogniforge-ms-step8-reasoning-agent. Refresh: 10s. Covers: startup_info, LLM backend, HTTP traffic, invocations (success/error/fallback), MCTS expansions, LLM calls/errors, microservices health matrix (steps 4-8), Prometheus scrape health, activation guide. |
| 52 | Step 8 CI gate | `.github/workflows/microservices-step8-reasoning-agent.yml` | **ACTIVE** | 7-job workflow: static-checks / infrastructure-gate / dashboard-gate / lint / step8-tests (79) / regression-steps-4-7 / pr-summary. PR comment with results. |
| 53 | Ona automation — reasoning-agent | `.ona/automations.yaml` | **ACTIVE** | service: `reasoning-agent` (uvicorn start/ready/stop on :8008). tasks: `verify-step8-reasoning-agent`, `restart-reasoning-agent`, `run-step8-tests`. |
| 15 | Database | `app/core/database.py` | **ACTIVE** | PostgreSQL 17.6 Supabase. database:ok confirmed. |
| 16 | Cache | `app/caching/factory.py` | **ACTIVE (InMemoryCache)** | REDIS_URL not set → InMemoryCache |
| 17 | AI Gateway | `app/core/gateway/simple_client.py` | **ACTIVE** | nvidia/nemotron-3-super-120b-a12b:free. Live call confirmed. |
| 18 | Microservices stack | `microservices/*/` | **DORMANT** | Not started by devcontainer. Revival Step 1 applied 2026-05-10: H1+H2+H3 unblock orchestrator_service. |
| 19 | Grafana | native binary `/opt/grafana` | **ACTIVE** | Port 3001. 5 dashboards. Datasource connected. |
| 20 | Prometheus | native binary `/opt/prometheus` | **ACTIVE** | Port 9090. 3 targets UP. |
| 21 | OTEL export | `app/telemetry/otel_setup.py` | **ACTIVE (no-op)** | Endpoint set to localhost:4317 but no collector running |
| 22 | UnifiedObservabilityService | `app/telemetry/unified_observability.py` | **ACTIVE** | In-process. Every HTTP request traced. |
| 23 | IntentDetector / ChatOrchestrator | `app/services/chat/intent_detector.py` | **PARTIAL (loaded-not-invoked)** | Constructed by boundary service, never called on WS path |
| 24 | Outbox relay | `orchestrator_service/main.py` | **DORMANT** | OUTBOX_RELAY_ENABLED=False by default |
| 25 | Postgres checkpointer | `orchestrator_service/src/core/database.py` | **DORMANT** | AsyncPostgresSaver importable, not configured |
| 26 | cogniforge_langgraph_checkpointer_writes_total | `observability/grafana/dashboards/20-langgraph.json` | **ZOMBIE metric** | No emitter. Requires Postgres checkpointer. |

---

## Rules (immutable)

1. **Code presence ≠ runtime usage.** Triple proof required: import + call chain + runtime evidence.
2. **No DATABASE_URL = no FastAPI.** A running uvicorn PID is NOT proof of a healthy server. Check `/health`.
3. **Process env wins over `.env`.** `app/core/settings/base.py:23` reads `os.environ` at module import time — before pydantic-settings reads `.env`. Secrets must be in the process environment.
4. **Stale state files are a finding.** `.devcontainer/state/app_healthy` from a previous run does NOT mean the current uvicorn is healthy. Always re-probe the live endpoint.
5. **ACTIVE (no-op) is not ACTIVE.** Missing env var = no observable output = not truly ACTIVE.
6. **Zombie metrics are worse than no metrics.** Always-zero panels are indistinguishable from "system not running". Add emitters or remove the panel (D-016).
7. **Degraded ≠ Dead.** A microservice that passes `/health` but has a failed warmup is DEGRADED. The `/health` endpoint must expose `startup_state`.
8. **Warmup must be timeout-guarded.** Any `ainvoke()` in a lifespan context must use `asyncio.wait_for(..., timeout=N)`.
9. **Supervisor must not trust stale state.** On every boot, re-verify uvicorn is actually serving (PID alive AND port responding).
10. **Grafana :3001 requires process env at boot.** `GF_SERVER_HTTP_PORT=3001` set by supervisor.sh before launching grafana-server.
11. **Orchestrator StateGraph NOT on monolith chat path.** `ChatRoutingPolicy` returns `/agent/chat` → `OrchestratorAgent.run()`, NOT the 13-node StateGraph.
12. **thread_id namespaces incompatible.** Local graph: `str(conversation_id)`. Orchestrator: `f"u{user_id}:c{conversation_id}"`. Never mix.
13. **LangGraph metrics now ACTIVE for local graph.** `cogniforge_langgraph_intent_total`, `cogniforge_langgraph_node_count_total`, `cogniforge_langgraph_node_duration_seconds_bucket` emitted per WS turn.
14. **Lock file staleness is a finding.** Always check `generated_at_utc` in `.runtime/truth_table.lock.json` before trusting it.
15. **`allowedDevOrigins` must include all hosting environments.** Next.js 15+ rejects dev-server requests from unlisted origins. Always include `*.app.github.dev` (Codespaces), `*.replit.dev` (Replit), and `*.gitpod.io` (Gitpod/Ona) in `frontend/next.config.js`.
16. **`local` is illegal outside bash functions.** Using `local var` in top-level script scope (even inside `if/else`) causes bash to abort with `local: can only be used in a function`. In `supervisor.sh`, any variable at top-level must use plain assignment (`var=value`). This was the root cause of ISS-037 (commit `3fd78247`) — all ports dead after merge.
17. **`.devcontainer/secrets.env` is the Codespaces fallback.** When Codespaces Secrets are not configured, `supervisor.sh` reads `.devcontainer/secrets.env` (git-ignored) before falling back to SQLite. Copy `.devcontainer/secrets.env.example` and fill in real values. Never commit `secrets.env`.
19. **`cognitive_engine.memorize` يتطلب حارس None (H3 — 2026-05-10).** `get_cognitive_engine()` يُرجع `None` دائماً. أي استدعاء لـ `self.cognitive_engine.memorize(...)` بدون `if self.cognitive_engine is not None` يرفع `AttributeError` في كل استجابة ناجحة للنموذج. الإصلاح مُطبَّق في `simple_client.py:116`.
20. **`postgresql://` يُفشل `create_async_engine` — يجب `postgresql+asyncpg://` (ISS-038-B — مكتشف حياً 2026-05-10).** `DATABASE_URL` من Supabase يستخدم `postgresql://` الذي يُعيَّن إلى psycopg2 المتزامن. `create_async_engine` يرفعه بـ `InvalidRequestError`. الإصلاح في `supervisor.sh` و `automations.yaml`: تحويل inline بـ bash substitution + إزالة `sslmode` من query string (asyncpg يتعامل مع SSL عبر `connect_args`). **القاعدة:** أي microservice يستخدم SQLAlchemy async يجب أن يستقبل `postgresql+asyncpg://` وليس `postgresql://`.
21. **orchestrator-service يبدأ في وضع `degraded` مع `graph_ready:true` — هذا طبيعي.** `startup_state: degraded` يعني warmup probe فشل بسبب PgBouncer prepared statement conflict (`prepared statement "_pg3_0" already exists`). لكن `graph_ready: true` يعني الـ StateGraph 13 عقدة يعمل. الخدمة تستجيب وتعالج الطلبات. هذا سلوك متوقع مع PgBouncer transaction mode — ليس خطأً مميتاً.
23. **planning-agent يعمل في وضع fallback بدون OPENROUTER_API_KEY.** `_dspy_dependencies_available()` تتحقق من DSPy قبل التهيئة. عند غياب المفتاح أو فشل DSPy، `_get_fallback_plan()` تُولِّد خطة احتياطية بدلاً من رفع استثناء. `cogniforge_planning_fallback_plans_total{reason=...}` يُسجِّل السبب. هذا سلوك مقصود — الخدمة لا تتعطل بدون DSPy.
24. **docker-compose.step6.yml مخصص لبيئات Docker فقط.** في Codespaces: `supervisor.sh:launch_planning_agent()` هو المسار الوحيد. `docker-compose.step6.yml` للتطوير المحلي وCI فقط. لا تحاول تشغيل Docker Compose في Codespaces devcontainer — Docker-in-Docker غير مدعوم.
25. **PLANNING_* env vars prefix.** `PlanningAgentSettings` تستخدم `env_prefix="PLANNING_"`. لذا `OPENROUTER_API_KEY` في البيئة يُقرأ كـ `PLANNING_OPENROUTER_API_KEY`. في supervisor.sh: `PLANNING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"` يُحوِّل المفتاح العام إلى المتغير المُقيَّد بالـ prefix.
20. **`TAVILY_API_KEY` يجب أن يكون في `docker-compose.yml` لكلا الخدمتين (H1 — 2026-05-10).** `WebSearchFallbackNode` في `orchestrator_service` و`SuperSearchOrchestrator` في `research_agent` تتجاهلان البحث صامتتين عند غياب المفتاح. القيمة الآمنة: `${TAVILY_API_KEY:-}`.
21. **`ddgs>=6.0` مطلوب في `research_agent/requirements.txt` (H2 — 2026-05-10).** بدونه، `SuperSearchOrchestrator` ترفع `ImportError` عند غياب `TAVILY_API_KEY` — وهو الوضع الافتراضي في بيئة التطوير.
18. **Exercise retrieval requires intent classification, not keyword matching (ISS-038).** `detect_exercise_retrieval()` must use a two-phase classifier: (1) explanation-intent patterns cancel retrieval at highest priority; (2) only explicit retrieval patterns trigger it. A flat keyword list on "تمرين"/"احتمالات" causes context blindness — every explanation request returns the same static knowledge-base file. When in doubt, do NOT trigger retrieval; LangGraph handles ambiguous questions better. The `knowledge_base/` directory currently contains exactly one file — any retrieval trigger without explicit context returns that file unconditionally.
22. **`ORCHESTRATOR_CHAT_ENDPOINT` controls routing target (Step 2 — 2026-05-10).** Default: `"state_graph"` → `/api/chat/messages` (StateGraph 13 nodes). Rollback: `"agent"` → `/agent/chat` (OrchestratorAgent). Unknown values fall back to `"state_graph"` with a warning. Do NOT change the default without an ADR (D-021).
23. **Routing metrics are emitted per chat request.** `cogniforge_routing_mode_state_graph` (gauge: 1=StateGraph, 0=Agent) and `cogniforge_routing_target_total{target=...}` (counter) are emitted by `orchestrator_client.py` on every `chat_with_agent` call. These feed the `50-microservices-transition.json` dashboard on Grafana :3001.
24. **Microservices Prometheus targets are DOWN by default.** `orchestrator-service`, `research-agent`, `user-service`, `planning-agent` scrape targets added to `prometheus.yml`. They show as DOWN until `docker compose -f docker-compose.yml up -d` is run. DOWN is the expected state in the default devcontainer — it is not an error.
25. **Grafana :3001 has 6 dashboards after Step 2.** `50-microservices-transition.json` (UID: `cogniforge-ms-transition-step2`) added. 15 panels covering routing mode, StateGraph execution, Tavily, microservices health matrix, and fallback chain transition progress.
26. **Grafana :3001 has 7 dashboards after Step 3.** `60-microservices-step3-live.json` (UID: `cogniforge-ms-step3-live`) added. 20 panels, 10s refresh. Covers orchestrator health, routing distribution, LangGraph node execution, intent classification, fallback chain progress, memory/CPU, and activation guide.
27. **docker-compose.step3.yml is the Step 3 activation file.** Runs only 3 services: `postgres-orchestrator` (5441), `redis-orchestrator` (6380), `orchestrator-service` (8006). Isolated from the main `docker-compose.yml`. Use `docker compose -f docker-compose.step3.yml up -d` to activate. Volumes are named `cogniforge-postgres-orchestrator-step3-data` to avoid conflicts.
28. **Ona automation `orchestrator-stack` is the canonical Step 3 trigger.** `gitpod automations service start orchestrator-stack` → builds + starts the 3-service stack → waits for `/health` → reports LIVE. `ready` command: `curl -sf http://localhost:8006/health`. Stop: `docker compose -f docker-compose.step3.yml down`.
29. **Step 3 CI gate has 7 jobs.** `.github/workflows/microservices-step3-live.yml` validates: compose syntax + required services + port assignments + StateGraph imports + /health structure + asyncio.wait_for guard + dashboard JSON (20 panels, correct UID) + Prometheus orchestrator-service job + automations.yaml schema (no `dependsOn` in services). PR comment posted automatically.
30. **`OUTBOX_RELAY_ENABLED=false` in Step 3.** Disabled in both `docker-compose.step3.yml` and `supervisor.sh:launch_orchestrator_service()`. Enabled in Step 4 after verifying the full persistence path (D-006 compliance check).
31. **Docker is NOT available in the default Codespaces devcontainer.** `devcontainer.json` intentionally omits `docker-in-docker` (fails on `python:3.12-slim` + `network_mode: host`). `docker-compose.step3.yml` is for local/CI environments only. In Codespaces, `supervisor.sh:launch_orchestrator_service()` is the canonical Step 3 activation path.
32. **orchestrator-service auto-starts at Codespace boot when `OPENROUTER_API_KEY` is set.** `supervisor.sh` STEP 4D calls `launch_orchestrator_service()` in background. If `OPENROUTER_API_KEY` is absent, it logs a warning and skips — no crash. Add the key to Gitpod Secrets to activate automatically.
33. **`ORCHESTRATOR_DATABASE_URL` defaults to `DATABASE_URL` in Codespaces.** The orchestrator uses Supabase (same DB as monolith) with a separate schema. No local postgres needed. This is intentional for Step 3 — Step 4 may introduce a dedicated schema or separate DB.
34. **native/prometheus.yml is the real Prometheus config in Codespaces.** `observability/prometheus/prometheus.yml` is used by Docker compose stack only. `observability/native/prometheus.yml` is what the native Prometheus binary reads (launched by supervisor.sh). Always edit `native/prometheus.yml` for Codespaces scrape targets.
