# Runtime Truth Lock
> Last updated: **2026-05-09** | Branch: `fix/lifespan-orchestration-env-injection`
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

## Infrastructure truth (verified live 2026-05-09 — fifth pass)

| Service | Port | Status | Evidence |
|---------|------|--------|---------|
| **Next.js** | **3000** | **ACTIVE** | supervisor.sh `--port 3000` overrides package.json `--port 5000`. HTML confirmed. |
| **FastAPI** | **8000** | **ACTIVE** | `GET /health → {"application":"ok","database":"ok"}`. Requires DATABASE_URL in **process env** (not just .env). |
| **Grafana** | **3001** | **ACTIVE** | `GET /api/health → {"database":"ok"}`. 5 dashboards. Prometheus datasource UP. |
| **Prometheus** | **9090** | **ACTIVE** | `GET /-/healthy → Healthy`. 3 targets UP: fastapi, grafana, prometheus. |
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

## Full capability truth table (2026-05-09 — fifth pass)

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
| 14 | Advanced orchestrator StateGraph (13 nodes) | `orchestrator_service/src/services/overmind/graph/main.py` | **DORMANT** | Compiles in isolation. Not on live call chain. |
| 15 | Database | `app/core/database.py` | **ACTIVE** | PostgreSQL 17.6 Supabase. database:ok confirmed. |
| 16 | Cache | `app/caching/factory.py` | **ACTIVE (InMemoryCache)** | REDIS_URL not set → InMemoryCache |
| 17 | AI Gateway | `app/core/gateway/simple_client.py` | **ACTIVE** | nvidia/nemotron-3-super-120b-a12b:free. Live call confirmed. |
| 18 | Microservices stack | `microservices/*/` | **DORMANT** | Not started by devcontainer |
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
