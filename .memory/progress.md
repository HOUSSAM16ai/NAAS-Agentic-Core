# Progress — What Has Been Done
> Last updated: 2026-05-10 | Branch: `feat/microservices-step2-stategraph-routing`

---

## ✅ Session: 2026-05-10 — Microservices Step 2: StateGraph Routing (الخطوة الانتقالية الثانية)

**Branch**: `feat/microservices-step2-stategraph-routing`
**Mode**: Live code changes — routing policy + observability + CI gate.
**Verified**: 16/16 tests PASSED | ruff clean | dashboard JSON valid | prometheus config valid

### الخطوة الانتقالية المختارة (D-021 — تنفيذ)
تعديل `ChatRoutingPolicy` لتوجيه المونوليث نحو `/api/chat/messages` (StateGraph 13 عقدة) بدلاً من `/agent/chat` (OrchestratorAgent). هذا يُفعّل المسار الكامل للـ StateGraph عند تشغيل `docker compose up orchestrator-service`.

### التغييرات المُنجزة

#### 1. `app/infrastructure/clients/routing_policy.py` — تعديل جوهري
- إضافة `endpoint_mode: str` كحقل جديد في `ChatRoutingPolicy`
- `_ENDPOINT_MAP`: قاموس صريح يربط الوضع بنقطة النهاية
  - `"state_graph"` → `/api/chat/messages` (الافتراضي الجديد)
  - `"agent"` → `/agent/chat` (للتراجع فقط)
- `ORCHESTRATOR_CHAT_ENDPOINT` env var يتحكم في الوضع
- `targets_state_graph` property للاستعلام السريع
- تحقق صارم: قيمة غير معروفة → تحذير + fallback إلى `state_graph`

#### 2. `app/infrastructure/clients/orchestrator_client.py` — إضافة metrics
- `routing.mode.state_graph` gauge: 1 = StateGraph, 0 = Agent
- `routing.target.total{target=...}` counter: يُحصي كل هدف (state_graph / agent / local_fallback)
- log يشمل `endpoint_mode` و `targets_state_graph` لكل طلب

#### 3. `app/telemetry/metrics.py` — توسيع hist_names
- إضافة `"orchestrator.node.duration_seconds"` → `cogniforge_orchestrator_node_duration_seconds_bucket`
- يُغذّي لوحة latency في dashboard الخدمات المصغرة

#### 4. `observability/grafana/dashboards/50-microservices-transition.json` — dashboard جديد
- **15 panels** على Grafana :3001
- Row 1: Routing Mode gauge + Chat Requests by Target (timeseries) + Orchestrator Health
- Row 2: StateGraph Node Execution Rate + Node Latency (p50/p95/p99)
- Row 3: Tavily Search Outcomes + Research Agent Health + Orchestrator Startup State
- Row 4: Microservices Health Matrix (table — جميع الخدمات)
- Row 5: Fallback Chain Transition Progress (cumulative — يُظهر تقدم الانتقال)
- UID: `cogniforge-ms-transition-step2`

#### 5. `observability/prometheus/prometheus.yml` — scrape targets جديدة
- `orchestrator-service` → `host.docker.internal:8006/metrics`
- `research-agent` → `host.docker.internal:8007/metrics`
- `user-service` → `host.docker.internal:8001/metrics`
- `planning-agent` → `host.docker.internal:8002/metrics`
- جميعها `honor_labels: true` — تظهر DOWN حتى يُشغَّل `docker compose up`

#### 6. `tests/infrastructure/test_routing_policy.py` — 16 اختبار جديد
- `TestDefaultMode`: الوضع الافتراضي = state_graph
- `TestRollbackMode`: وضع التراجع = agent
- `TestUnknownMode`: قيم غير معروفة → state_graph
- `TestBreakglassMode`: وضع الطوارئ متعدد العناوين
- `TestEndpointMap`: التحقق من _ENDPOINT_MAP
- `TestFallbackAndContractVersion`: fallback وإصدار العقد

#### 7. `.github/workflows/microservices-transition.yml` — CI gate جديد
- 5 وظائف: routing-policy-gate / stategraph-compile-gate / dashboard-schema-gate / prometheus-config-gate / transition-gate
- يُشغَّل عند تعديل أي ملف يمس الخدمات المصغرة أو سياسة التوجيه
- يتحقق من: الوضع الافتراضي state_graph، StateGraph يُترجَم، dashboard JSON صالح، prometheus config صالح
- يُنشر ملخص في PR summary

### كيفية تفعيل الانتقال الكامل
```bash
# 1. تشغيل orchestrator-service
OPENROUTER_API_KEY="sk-or-v1-..." TAVILY_API_KEY="tvly-dev-..." \
docker compose -f docker-compose.yml up -d orchestrator-service postgres-orchestrator redis-orchestrator

# 2. ضبط ORCHESTRATOR_SERVICE_URL في بيئة المونوليث
export ORCHESTRATOR_SERVICE_URL=http://localhost:8006
# ORCHESTRATOR_CHAT_ENDPOINT=state_graph (افتراضي — لا حاجة لضبطه)

# 3. إعادة تشغيل المونوليث
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. التحقق من Grafana :3001 → dashboard "Microservices Transition — Step 2"
# Routing Mode يجب أن يظهر "STATE_GRAPH (active)"
# Orchestrator Service Health يجب أن يظهر "UP"

# 5. التراجع الفوري إذا لزم
export ORCHESTRATOR_CHAT_ENDPOINT=agent
```

### الملفات المعدّلة (5 ملفات — حد Jules)
- `app/infrastructure/clients/routing_policy.py`
- `app/infrastructure/clients/orchestrator_client.py`
- `app/telemetry/metrics.py`
- `observability/prometheus/prometheus.yml`
- `.memory/*`, `CLAUDE.md`

### الملفات الجديدة (2 ملفات)
- `observability/grafana/dashboards/50-microservices-transition.json`
- `tests/infrastructure/test_routing_policy.py`
- `.github/workflows/microservices-transition.yml`

---

---

## ✅ Session: 2026-05-10 — Orchestrator Revival Step 1 (خطوة انتقالية واحدة مؤكدة)

**Branch**: `feat/orchestrator-revival-step1`
**Mode**: Live runtime fixes — application code + configuration + tests.
**Verified live**: DB ✅ (2107 customer_messages, 19 users) | OpenRouter ✅ (200 OK) | Tavily ✅ (2 BAC results)

### الخطوة الانتقالية المختارة
إزالة ثلاثة حواجز تقنية تمنع تشغيل `orchestrator_service` (الخدمة المصغرة الأساسية):

### H1 — إضافة `TAVILY_API_KEY` لـ `docker-compose.yml` ✅
- `- TAVILY_API_KEY=${TAVILY_API_KEY:-}` في `orchestrator-service.environment`
- `- TAVILY_API_KEY=${TAVILY_API_KEY:-}` في `research-agent.environment`
- `TAVILY_API_KEY=` مع تعليق في `.env.docker`
- **التأثير**: `WebSearchFallbackNode` تستخدم Tavily بدلاً من التجاهل الصامت

### H2 — إصلاح DuckDuckGo Fallback ✅
- `ddgs>=6.0` أُضيف إلى `microservices/research_agent/requirements.txt`
- **التأثير**: لا `ImportError` عند غياب `TAVILY_API_KEY`

### H3 — إصلاح `cognitive_engine.memorize` NullPointerError ✅
- **الملف**: `microservices/orchestrator_service/src/core/gateway/simple_client.py:116`
- **السبب**: `get_cognitive_engine()` يُرجع `None` دائماً
- **الإصلاح**: `and self.cognitive_engine is not None` قبل `memorize`
- **التأثير**: لا `AttributeError` في كل استدعاء ناجح للنموذج

### اختبارات التحقق: 9/9 PASSED ✅
- `tests/microservices/orchestrator_service/test_orchestrator_revival.py`

### تحقق حي من الـ graph
```
Graph compiled: CompiledStateGraph — 13 nodes
['supervisor', 'query_rewriter', 'query_analyzer', 'retriever',
 'reranker', 'web_fallback', 'admin_agent', 'tool_executor',
 'chat_fallback', 'general_knowledge', 'synthesizer', 'validator']
```

### الملفات المعدّلة
- `docker-compose.yml`
- `microservices/research_agent/requirements.txt`
- `microservices/orchestrator_service/src/core/gateway/simple_client.py`
- `.env.docker`
- `tests/microservices/orchestrator_service/test_orchestrator_revival.py` (جديد)
- `.memory/*`, `CLAUDE.md`

---

## ✅ Session: 2026-05-09 (fifth pass) — Lifespan Orchestration Fix + Live Metrics

**Branch**: `fix/lifespan-orchestration-env-injection`
**Mode**: Live runtime diagnosis + application code fixes + documentation update.

### Root Cause Diagnosed (Live — Surgical Precision)

**ISS-034**: Uvicorn PID alive, port 8000 not listening, state file shows `app_healthy` from previous run.
- `devcontainer.json` maps `DATABASE_URL` from `${localEnv:DATABASE_URL}` — Ona/Gitpod does NOT inject secrets as process env vars.
- `supervisor.sh` created `.env` with `DATABASE_URL=sqlite+aiosqlite:///./dev.db` placeholder.
- `app/core/settings/base.py:23` reads `os.environ.get("APP_DATABASE_URL")` at **module import time** — before pydantic-settings reads `.env`. Finds empty string.
- `_ensure_database_url()` raises `ValueError` in `development` environment → uvicorn worker crashes on import → port 8000 never opens.
- Stale `app_healthy` state file → supervisor reports healthy. **Misleading observability confirmed live.**

**ISS-035**: Orchestrator lifespan warmup blocks ASGI startup indefinitely.
- `ainvoke()` with no timeout → could block forever on slow LLM/network.
- `RuntimeError` from warmup propagated up → crashed ASGI startup.
- `/health` returned `{"status":"ok"}` regardless of graph state.

### Fixes Applied

1. **`.devcontainer/supervisor.sh`**:
   - `_inject_env_secrets()` — reads real secrets from process env, writes to `.env` with priority logic.
   - `_export_env_file()` — exports `.env` keys into shell process before `python -m uvicorn`.
   - `_uvicorn_healthy()` — checks PID alive AND port responding; kills stale zombie before restart.
   - Health check step — always re-probes live endpoint; never trusts stale state files.
   - Degraded mode — no DATABASE_URL no longer crashes supervisor; Grafana + Prometheus stay up.
   - Completion message — shows actual `app_ready` state, not hardcoded "Verified".

2. **`microservices/orchestrator_service/main.py`**:
   - Warmup wrapped in `asyncio.wait_for(..., timeout=30.0)`.
   - All non-DB exceptions caught → logged as DEGRADED, not fatal.
   - `app.state.startup_state` tracks `"ready"` / `"degraded"`.
   - `/health` endpoint exposes `startup_state` and `startup_errors`.
   - 5-phase lifespan with clear Arabic docstring explaining criticality of each phase.

3. **`app/services/chat/local_graph.py`**:
   - `_supervisor_node`: emits `langgraph.intent.total`, `langgraph.node.count.total`, `langgraph.node.duration_seconds`.
   - `_chat_node`: emits `langgraph.node.count.total`, `langgraph.node.duration_seconds` on success and error.

4. **`app/telemetry/metrics.py`**:
   - `hist_names` extended with `langgraph.node.duration_seconds` → `cogniforge_langgraph_node_duration_seconds_bucket` now exported.

### Live Verification Results

| Check | Result |
|-------|--------|
| FastAPI `:8000/health` | `{"application":"ok","database":"ok"}` ✅ |
| Grafana `:3001/api/health` | `{"database":"ok"}` ✅ |
| Prometheus `/-/healthy` | `Prometheus Server is Healthy.` ✅ |
| Prometheus target `cogniforge-fastapi` | **UP** ✅ |
| Prometheus target `grafana` | **UP** ✅ |
| Prometheus target `prometheus` | **UP** ✅ |
| Next.js `:3000` | HTML confirmed ✅ |
| LangGraph metrics | `cogniforge_langgraph_intent_total{graph="local",intent="general"} 1.0` ✅ |

### Files Changed
- `.devcontainer/supervisor.sh` — env injection + zombie detection + degraded mode
- `microservices/orchestrator_service/main.py` — lifespan timeout + startup_state + /health
- `app/services/chat/local_graph.py` — LangGraph metric emission
- `app/telemetry/metrics.py` — histogram extension for langgraph metrics
- `.memory/runtime_truth.md` — full rewrite (fifth pass)
- `.memory/issues.md` — ISS-034, ISS-035 added
- `.memory/decisions.md` — D-024 through D-028 added
- `.memory/progress.md` — this entry
- `.memory/context.md` — updated
- `.memory/architecture_truth.md` — updated
- `CLAUDE.md` — §6.6 truth table + §6.8 new doctrine section

### What Was NOT Changed
- No test files
- No CI workflows
- No frontend code
- No database schema

---

## ✅ Session: 2026-05-09 (third pass) — Advanced LangGraph + Tavily Deep Investigation

**Branch**: `docs/advanced-langgraph-tavily-audit-2026-05-09`
**Mode**: Live runtime investigation + documentation update. No application code changed.

### What Was Investigated (Live Runtime — No Code Changes)

1. **Advanced orchestrator StateGraph (13 nodes)**:
   - `create_unified_graph()` compiles without error → `CompiledStateGraph` with 13 nodes
   - `graph.ainvoke(state)` with `OPENROUTER_API_KEY` → valid Arabic response in ~10s (confirmed live)
   - NOT on live call chain — `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` → Docker DNS → ConnectError
   - `cognitive_engine.memorize` bug confirmed: `AttributeError: 'NoneType' object has no attribute 'memorize'` on primary model (non-blocking, fallback models handle)
   - `FlagEmbeddingReranker` not installed → `RerankerNode` falls back to simple score sort
   - Postgres checkpointer absent → graph compiled without checkpointer
   - 4-intent taxonomy: `educational`, `general_knowledge`, `admin`, `chat` (different from local graph's 3-intent)
   - DSPy usage confirmed: `IntentClassifier`, `QueryRewriterSignature`, `AnalyzeQuery`, `EducationalSynthesizer`

2. **Tavily integration**:
   - `tavily-python==0.7.24` installed, `TavilyClient` importable
   - Live search confirmed: `TavilyClient(api_key='tvly-dev-...').search('بكالوريا جزائر رياضيات')` → 2 results in <3s
   - Key format validation: must start with `tvly-`. MCP URL format auto-sanitized in `readiness.py` and `super_search.py`
   - `TAVILY_API_KEY` absent from `docker-compose.yml` (both `orchestrator-service` and `research-agent`)
   - Silent skip confirmed: `WebSearchFallbackNode` returns `{"used_web": False, "reranked_docs": []}` with no exception when key absent
   - Monolith does NOT use Tavily — `strategy_handlers.py:208` only checks for key as a warning, and `strategy_handlers.py` is on the PARTIAL (loaded-not-invoked) path

3. **DuckDuckGo fallback broken**:
   - `ddgs` package NOT installed → `ImportError` when `SuperSearchOrchestrator` initializes without Tavily
   - `DuckDuckGoSearchAPIWrapper` from `langchain_community` requires `ddgs`

4. **`WebSearchFallbackNode` call chain**:
   - Calls `research_client.deep_research()` → HTTP to `research-agent:8007` → ConnectError (DORMANT)
   - `research_client` base URL: `http://research-agent:8007` — Docker DNS, not running by default

5. **`TAVILY_API_KEY` in docker-compose.yml**:
   - Absent from `docker-compose.yml` (current version)
   - Only present in `docker-compose.legacy.yml:61` as `TAVILY_API_KEY: ${TAVILY_API_KEY:-}`
   - Must be added to both `orchestrator-service` and `research-agent` environment sections

### Files Updated
- `CLAUDE.md` — added §6.7 (Advanced LangGraph + Tavily doctrine), updated §6.6 truth table (rows 24, 24a, 24b), updated §10 env vars table
- `.memory/runtime_truth.md` — rows 24, 24a, 24b added/updated, architectural verdict updated, rules 11–15 added
- `.memory/architecture_truth.md` — component inventory updated, Transformation Gap updated, revival checklist added
- `.memory/decisions.md` — D-018, D-019, D-020 added
- `.memory/tasks.md` — H1–H4 tasks added (revival roadmap)
- `.memory/progress.md` — this entry

### What Was NOT Changed
- No application source code (`app/`, `microservices/`, `frontend/`)
- No test files
- No CI workflows
- No runtime behavior

---

## ✅ Session: 2026-05-09 — Full Live Runtime Investigation (Ona Agent)

**Branch**: `docs/live-runtime-audit-2026-05-09`

### What Was Investigated (Live Runtime — No Code Changes)
Full live runtime investigation with real DATABASE_URL and OpenRouter API key:

1. **DB connection verified**: PostgreSQL 17.6 Supabase, 19 users, 2098 customer_messages, 3038 admin_messages, 79 missions
2. **OpenRouter API verified**: 367 models, primary `nvidia/nemotron-3-super-120b-a12b:free`
3. **local_graph live call**: `run_local_graph('مرحبا', 9999)` → `'مرحبا! كيف يمكنني مساعدتك اليوم؟'`
4. **FastAPI startup verified**: 62 routes with real DB
5. **Port map corrected**: Next.js=3000 (supervisor.sh override), Grafana=3001 (provisioning CLI override), Prometheus=9090
6. **OTEL confirmed no-op**: `OTEL_EXPORTER_OTLP_ENDPOINT=http` is invalid URL
7. **Redis confirmed unused**: process running but `REDIS_URL` not set → InMemoryCache
8. **ZOMBIE/DORMANT re-verified**: KagentMesh, multi-agent workflow, MCP, LlamaIndex all confirmed dead

### Files Updated
- `.memory/runtime_truth.md` — 34 rows, full rewrite with live evidence
- `.memory/context.md` — stack table with live status, DB state, AI gateway details
- `.memory/architecture_truth.md` — port map, component inventory
- `.memory/logs.md` — session record
- `CLAUDE.md` — §6.6 truth table (34 rows), §3 architecture diagram, §1 port table


## ✅ Session: 2026-05-05 — Persistence Consolidation + Terminal-Event Guarantee + Markdown Cleanup

**Branch**: `claude/fix-persistence-consolidate-8X8LT`

### What Was Fixed
1. **ISS-014/015 (Dual-write & save authority)** — D-006 implemented as a hard
   contract in CLAUDE.md §6.5 + architecture test
   `tests/architecture/test_persistence_authority.py`. Monolith is sole writer;
   Orchestrator only persists when delegated and signals back via `persisted: true`.
2. **ISS-016 (Silent fallback failures)** — New `_emit_terminal_frames()` helper in
   both `customer_chat.py` and `admin.py` finally blocks. Exactly one terminal
   frame (assistant_final/error) per turn. `[CRITICAL_DATA_LOSS]` logging surfaces
   when fail-safe writes fail.
3. **ISS-017 (Terminal-event corruption)** — `normalize_streaming_event` now passes
   `complete`, `persisted`, `conversation_init` through unchanged when the unified
   envelope flag is on. Previously they were coerced to `assistant_delta` and the
   router's terminal-event detection silently broke.

### Files Touched
- `shared/chat_protocol/event_protocol.py` — pass-through for control events.
- `app/api/routers/customer_chat.py` — `_emit_terminal_frames` helper + finally restructure.
- `app/api/routers/admin.py` — `_emit_terminal_frames` helper + WRITE_DECISION logs + retry parity.
- `tests/architecture/test_persistence_authority.py` — new regression guard.
- `CLAUDE.md` — added §6.5 "Architecture Truth and Persistence Rules".
- `.memory/decisions.md` — D-006 marked IMPLEMENTED, D-009 added.
- `.memory/issues.md` — ISS-014/015/016/017 marked RESOLVED.

### Markdown Consolidation
Deleted ~38 legacy diagnosis/forensic markdown files at repo root. Their conclusions
already lived in `.memory/issues.md` and CLAUDE.md; the standalone files were
point-in-time snapshots that drift from reality. Kept canonical operational docs
(README, CHANGELOG, LICENSE, SECURITY, governance, ARCHITECTURE, AGENTS, ROADMAP,
LangGraph blueprint, replit.md, README_MIGRATIONS, scientific applications).

---

## ✅ Session: 2026-05-05 — Environment Documentation Correction

**Branch**: `claude/fix-duplicate-messages-nTEBj`
**Goal**: Correct the recorded runtime environment from Replit to GitHub Codespaces

### What Was Verified
- User confirmed they run the project via **GitHub Codespaces**, not Replit
- Inspected `.devcontainer/devcontainer.json` and `.devcontainer/docker-compose.host.yml`
- Confirmed devcontainer launches a single `web` container running `uvicorn app.main:app` via `.devcontainer/supervisor.sh`
- Confirmed microservices stack (`docker-compose.yml`) is **not** started by the devcontainer → orchestrator-service:8006 + 7 other services remain DORMANT exactly as documented for Replit
- Net effect on dual-write analysis: **identical to Replit** (Monolith is the sole writer; no dual-write physically possible without manually running the full microservices stack)

### What Was Updated
1. `CLAUDE.md` — sections 1, 6, 10, 13, 14 — Replit references replaced with Codespaces; added devcontainer paths and the explicit `docker compose -f docker-compose.yml up -d` escape hatch to wake microservices
2. `.memory/context.md` — Identity block now lists Codespaces, devcontainer file, supervisor script; env var table updated to reference Codespaces secrets and `OPENROUTER_SITE_URL`
3. `.memory/architecture.md` — Fallback 3 annotation now explains *why* the microservice is dormant (devcontainer scope)
4. `.memory/decisions.md` — D-001, D-002 reworded to be environment-agnostic with Codespaces as the concrete case
5. `.memory/issues.md` — ISS-001 fix instructions updated for Codespaces secrets; ISS-013 historical-vs-current framing
6. `.memory/tasks.md` — task #2 (SECRET_KEY) and task #8 (microservice DNS) updated for Codespaces context
7. `.memory/progress.md` — this entry
8. `.memory/logs.md` — session log entry

---

## Completed
- Delivered a full architectural dissection summary in `CLAUDE.md`.
- Synchronized `.memory` architecture/context/decisions/issues to match the updated narrative.
- Preserved hybrid control-plane/execution-plane interpretation.

## ✅ Session: 2026-05-09 — Architectural Intelligence Enrichment

**Branch**: (memory-only — no application code changed)
**Mode**: Diagnosis + memory evolution only. No runtime code changes.

### What Was Analyzed
Four systemic fragility patterns were discovered through deep code inspection and runtime testing:

1. **Intent routing semantic hijacking** (`app/services/chat/local_graph.py:_classify_intent`)
   - Runtime test confirmed: 10/10 non-academic questions containing educational keywords are misclassified as `educational`
   - Root cause: pure lexical regex, no semantic context, no conversation history
   - Hidden split-brain: zombie `IntentDetector` (13-intent taxonomy) vs live classifier (3-intent taxonomy) — incompatible if ever wired together
   - Intentional duplication between `local_graph.py` and `path_observer.py` — must be updated in sync

2. **Hidden DOM leakage** (`frontend/app/globals.css`, `CogniForgeApp.jsx`)
   - Both sidebars use `transform: translateX(±100%)` — visual hiding, not DOM exclusion
   - No `aria-hidden`, no `inert`, no `tabindex="-1"` on closed sidebars
   - `AgentTimeline` renders agent state into DOM regardless of sidebar visibility
   - Severity escalates as agent stack becomes more capable

3. **Runtime truth governance gap** (`scripts/runtime_truth.py`, `.github/workflows/runtime_truth.yml`)
   - CI enforces import + call chain (legs 1 and 2 of the triple)
   - Leg 3 (runtime evidence) is never verified in CI
   - No CI gate checks dashboard-metric contract (dashboard queries vs application emitters)
   - Lock file branch is stale (`jules-5513332666705839536-7e7df21b`)

4. **Zombie metrics + observability integrity** (`observability/grafana/dashboards/20-langgraph.json`)
   - 4 LangGraph dashboard metrics have zero emitters in the entire codebase
   - `local_graph.py` uses UnifiedObs spans (in-process), not OTel/Prometheus metrics
   - Dual-emission risk: WS turn metrics emitted through both OTel SDK and UnifiedObs simultaneously → double-counting when full stack is up
   - OTel setup is ACTIVE (imported + called) but is a no-op in default Codespaces — a fourth status tier not in the current taxonomy

### What Was Created / Updated
- **NEW**: `.memory/fragility-patterns.md` — 4 deep root-cause analyses with institutional lessons, anti-patterns, and fix strategies
- **UPDATED**: `.memory/issues.md` — added ISS-027 through ISS-031
- **UPDATED**: `.memory/decisions.md` — added D-013 through D-017
- **UPDATED**: `.memory/observability-topology.md` — zombie metric inventory + dual-emission risk section
- **UPDATED**: `.memory/context.md` — session note + documentation source of truth pointer
- **UPDATED**: `CLAUDE.md` — §6.14–§6.17 governance doctrine for all 4 patterns

### What Was NOT Changed
- No application source code (`app/`, `microservices/`, `frontend/`)
- No test files
- No CI workflows
- No runtime behavior

## ✅ Session: 2026-05-09 (second pass) — Live Architecture Audit + Memory Update

**Branch**: `docs/architecture-memory-audit-2026-05-09`
**Mode**: READ-ONLY investigation + documentation update. No application code changed.

### What Was Investigated
Live inspection of the running environment (no DATABASE_URL, no secrets):
1. FastAPI startup failure confirmed — uvicorn spawns then crashes at `AppSettings()` validation. Port 8000 not listening.
2. Grafana + Prometheus native binaries confirmed running (ports 3001 + 9090). Health checks pass. Prometheus shows `cogniforge-fastapi=0`.
3. Truth table lock drift confirmed — `scripts/runtime_truth.py --check` exits 1: `customer_chat_router: importer_count 6→5`. Root cause: `.orig` file counted in old lock. Component status unchanged.
4. `context_utils.py.orig` scratch artifact confirmed in `microservices/orchestrator_service/src/api/`.
5. `otel_setup.py` ACTIVE (no-op) tier formalised — import + call chain present, runtime effect absent without `OTEL_EXPORTER_OTLP_ENDPOINT`.

### What Was Updated
- `CLAUDE.md` — §0 (3 new doctrine rules), §6.6 truth table (otel_setup + Grafana/Prometheus native + FastAPI conditional rows), §6.22 (lock staleness), §6.23 (new audit section)
- `.memory/runtime_truth.md` — rows 30–32, extended status legend, branch ledger
- `.memory/observability_truth.md` — Grafana/Prometheus native rows, otel_setup correction
- `.memory/issues.md` — ISS-032 (truth table drift), ISS-033 (context_utils.py.orig)
- `.memory/context.md` — session note
- `.memory/progress.md` — this entry

### What Was NOT Changed
- No application source code, no tests, no CI workflows, no runtime behavior
- All 29 prior truth table rows remain valid — no status promotions or demotions

---

## ✅ Session: 2026-05-06 — Markdown Archive Cleanup

- حُذِف مجلد `docs/archive/` بالكامل لأنه يحتوي تقارير تاريخية غير محدثة.
- تم ترحيل السياسة المهمة إلى `CLAUDE.md` (قسم توحيد الوثائق).
- تم الإبقاء على `.memory/` بالكامل بدون حذف أي ملف، مع استمرار اعتباره ذاكرة التشغيل الأساسية.

