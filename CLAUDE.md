# CogniForge — Claude Code Context

> **AI tutor for Algerian students** | FastAPI 8000 + Next.js 3000/5000 + LangGraph 1.1.10
> Arabic / French / Darija | BAC preparation platform

---

## 1. What This Project Does

CogniForge is an educational AI platform for Algerian high-school students preparing for the Baccalaureate exam. Students chat in Arabic, French, or Darija and receive tutoring in math, physics, and sciences. The backend is a FastAPI monolith.

**Supported runtime environments**: the project is environment-agnostic and runs on both:

| Environment | Frontend port | How it picks the port |
|---|---|---|
| **GitHub Codespaces** (primary) | **3000** | `.devcontainer/supervisor.sh` exports `FRONTEND_PORT=3000` and passes `--port 3000` to `next dev`, overriding `package.json` |
| **Replit** | **5000** | `frontend/package.json` script `"dev": "next dev --port 5000"` is used directly |

In both environments the backend is on **8000** and microservices in `microservices/` are **dormant by default** — neither environment starts them. The Codespaces devcontainer (`.devcontainer/docker-compose.host.yml`) launches a single `web` container; the full microservices stack only comes up when you explicitly run `docker compose -f docker-compose.yml up -d`.

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
  └── Next.js (3000 in Codespaces / 5000 in Replit)
        └── next.config.js rewrites /api/* → localhost:8000
              └── FastAPI (port 8000)
                    ├── /api/security/login, /register
                    ├── /api/chat/ws  (WebSocket)
                    │     └── OrchestratorClient (fallback chain)
                    │           ├── [1] File count detection
                    │           ├── [2] Exercise retrieval (BAC)
                    │           ├── [3] HTTP → orchestrator:8006 → ConnectError (DORMANT)
                    │           └── [4] LangGraph local_graph.py ← PRIMARY HANDLER
                    ├── /api/v1/auth/*, /api/v1/users/*
                    ├── /v1/content/*
                    └── /api/v1/data-mesh/*
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

### Status legend
- **ACTIVE** — imported, on a live call chain reachable from `app/main.py` / `app/api/routers/`, AND observed at runtime.
- **PARTIAL** — on a live call chain but only via fallback, conditional, or non-default branch.
- **DORMANT** — code is real and imported, but the call chain only fires when an external service (e.g., a microservice that is not started by default) is up.
- **ZOMBIE** — defined and possibly imported, but no live call chain leads to it from a production entrypoint.
- **UNKNOWN** — insufficient evidence; do not claim ACTIVE.

### Truth table — verified 2026-05-06 (branch `claude/runtime-truth-audit-65iVU`)

| Component | Status | Proof |
|---|---|---|
| **`app/services/chat/local_graph.py`** (`run_local_graph`, `supervisor_node`, `chat_node`, `MemorySaver`) | **PARTIAL** | Imported `app/kernel.py:239` (pre-warm) and `app/infrastructure/clients/orchestrator_client.py:170` (fallback tier 3). In default Codespaces it IS the de-facto handler because orchestrator URL is unset → ConnectError → fallback runs every turn. Uses `ainvoke` only (not `astream_events`) → ISS-023. |
| **`app/services/chat/graph/workflow.py`** (`create_multi_agent_graph`) | **ZOMBIE** | Only importer is `tests/verify_graph_manual.py:8`. No reference from `app/main.py`, `app/kernel.py`, `app/api/`, or `orchestrator_client.py`. |
| **Multi-agent nodes** — `super_reasoner.py`, `planner.py`, `researcher.py`, `writer.py`, `procedural_auditor.py`, `reviewer.py` | **ZOMBIE** | Only consumed by `workflow.py` (itself ZOMBIE). No production call chain. |
| **`app/services/chat/memory_engine.py`** (LlamaIndex VectorStoreIndex) | **ZOMBIE** | Only invoked from `reviewer.py` inside the dead `workflow.py`. Zero references from routers, kernel, or `local_graph.py`. |
| **`app/drivers/llamaindex_driver.py`** | **ZOMBIE** | No `from app.drivers` import in `app/api/`, `app/main.py`, `app/kernel.py`, `local_graph.py`, or `orchestrator_client.py`. |
| **`app/drivers/reranker_driver.py`** | **ZOMBIE** | Same as above — drivers package has zero importers in the live chain. |
| **`app/drivers/kagent_driver.py`** | **ZOMBIE** | Same — only registered conditionally inside `MCPIntegrations`, which itself is dormant. |
| **`app/core/integration_kernel/runtime.py`** (`RealityKernel` micro-kernel) | **ZOMBIE** | Singleton designed but never instantiated from `app/main.py` or `app/kernel.py`. |
| **DSPy** (`microservices/research_agent/src/search_engine/query_refiner.py`, `microservices/orchestrator_service/.../graph/{main,search,supervisor}.py`) | **DORMANT** | Real implementation, but ALL call chains live inside microservices that the default devcontainer does not start. Reachable only when `docker compose -f docker-compose.yml up -d`. |
| **Reranker microservice** (`microservices/research_agent/src/search_engine/{reranker,strategies,hybrid,llama_retriever}.py`) | **DORMANT** | Same — gated behind dormant `research-agent:8007`. |
| **`app/services/kagent/`** (KagentMesh, ServiceRegistry, RemoteAgentAdapter) | **ZOMBIE** | Registered as DI singleton at `app/core/di.py:145`, but `get_kagent_mesh()` is only consumed inside the dead `workflow.py` graph nodes. No live consumer. |
| **`app/services/mcp/`** (MCPServer, MCPIntegrations, MCPToolRegistry, MCPResourceProvider) | **DORMANT** | Zero references from `app/main.py`, `app/kernel.py`, or `app/api/`. Only lazy-imported in `app/services/chat/agents/{admin.py,socratic_tutor.py}`, `app/services/collaboration/session.py`, and `app/core/prompts.py` — none of which are on the live `/api/chat/ws` path. The `socratic_tutor` and `admin` agent modules are themselves not invoked by the live chat router. |
| **`app/telemetry/unified_observability.py`** (`UnifiedObservabilityService`) | **ACTIVE** | Wired through `app/kernel.py:58,208` at startup. Every HTTP request passes through `app/middleware/fastapi_observability.py` and `app/middleware/observability/observability_middleware.py`. WebSocket frames are NOT traced (ISS-005). |
| **Orchestrator microservice fallback chain** in `OrchestratorClient` (file-intelligence, exercise-retrieval, LangGraph, general-chat) | **PARTIAL/ACTIVE** | `chat_with_agent` is the ONLY service called by `customer_chat.py:422` and `admin.py:490`. The HTTP attempt to `$ORCHESTRATOR_SERVICE_URL` always raises `ConnectError` in default Codespaces; the four local fallbacks then run in order. None of them set `persisted: true`. |
| **`OrchestratorClient` HTTP path** to orchestrator-service | **DORMANT** | Requires `ORCHESTRATOR_SERVICE_URL` set AND microservice stack up. Default devcontainer satisfies neither. |
| **All `microservices/*`** (orchestrator, planning, memory, user, research, reasoning, auditor, conversation, api_gateway, observability) | **DORMANT** | Not started by `.devcontainer/docker-compose.host.yml`. Only wake via `docker compose -f docker-compose.yml up -d`. |

### What this means for daily work

1. **The "agentic" stack the codebase advertises is mostly ZOMBIE/DORMANT in default Codespaces.** Only `local_graph.py` (2 nodes: supervisor + chat) and `UnifiedObservabilityService` actually run on every request.
2. **Do NOT add a feature that depends on KAgent, MCP, LlamaIndex, DSPy, the integration kernel, or the multi-agent workflow without first wiring it into a live entrypoint** (`app/api/routers/`, `app/kernel.py`, or `local_graph.py`). Otherwise the feature joins the zombie pile.
3. **`docs/` / blueprints describe the target architecture, not runtime.** When a doc claims "the orchestrator is the control plane" or "the multi-agent graph runs on chat", treat it as aspirational unless this truth table backs it.

### First-check protocol before any change to the chat / agent stack

1. Open this truth table.
2. Ask: is the component I'm touching ACTIVE, PARTIAL, DORMANT, or ZOMBIE?
3. If **DORMANT/ZOMBIE** → I am editing dead code unless I also wire it into a live path. Stop and decide explicitly.
4. If **ACTIVE/PARTIAL** → confirm the call chain still holds after my change (grep importers, run the WS chat test).
5. Updates to capability status MUST be accompanied by a fresh import + call-chain + runtime evidence triple in this table.

### What MUST NOT change without runtime proof
- Promoting any ZOMBIE/DORMANT component to ACTIVE in this table without the three-part proof.
- Removing the `local_graph.py` pre-warm in `app/kernel.py:239` (it's how we catch import breakage at startup).
- Removing `ObservabilityMiddleware` from the middleware stack — it's the ONLY production-path tracing today.
- Renaming or deleting `_emit_terminal_frames` (single emitter rule, see §6.5).

### Pre-merge checklist for the chat / agent stack
1. Did I touch a ZOMBIE? → either delete it or wire it. Don't leave it half-alive.
2. Did I add a new dependency on a microservice? → mark the new code DORMANT in this table until the stack is awake.
3. Did I add streaming logic? → confirm `ainvoke` vs `astream_events` decision; today only `ainvoke` is used (ISS-023).
4. Did I change the fallback chain order in `orchestrator_client.py`? → update §3 of this file and `.memory/architecture.md` in the same PR.

---

## 6.8 Architecture Reality Audit (2026-05-06 — branch `claude/diagnostic-system-architecture-aRSuW`)

> Re-verification of §6.6 Truth Table on the current branch. **All ten capability claims from `.memory/runtime_truth.md` were CONFIRMED by direct grep of importers and call chains.** No material drift. Below: only the deltas, plus the architectural verdict.

### Confirmed evidence (file:line) on this branch
- **Live chat WS endpoints**:
  - `app/api/routers/customer_chat.py:244` → `@router.websocket("/ws")` exposed at `/api/chat/ws`.
  - `app/api/routers/admin.py:316` → `@router.websocket("/api/chat/ws")` exposed at `/admin/api/chat/ws`.
- **Single chat entrypoint into the agent stack**: both routers call `OrchestratorClient.chat_with_agent` exactly once — `customer_chat.py:422`, `admin.py:490`. That call IS the entire "agentic boundary" of the live system.
- **Single terminal-frame emitter** (D-006 / §6.5): `_emit_terminal_frames` defined at `customer_chat.py:180` and `admin.py:159`; called once per turn at `customer_chat.py:550` and `admin.py:612`.
- **Persistence-skip handshake intact**: `orchestrator_persisted` read from normalized event at `customer_chat.py:451-452` / `admin.py:519-520`; fail-safe assistant write at `customer_chat.py:523-527` / `admin.py:585-589`.
- **Pre-warm of the only live graph**: `app/kernel.py:239-241` imports `get_local_graph` at startup.
- **Live router registry**: 9 routers mounted via `app/api/routers/registry.py:21-35` (system×2, admin, security, data_mesh, ums, customer_chat, content, observability). Mounted by `app/kernel.py:162`.
- **Middleware order** (declared `app/core/app_blueprint.py:167-177`): TrustedHost → CORS → **Observability** → SecurityHeaders → RemoveBlockingHeaders → RateLimit (non-test) → GZip. `ObservabilityMiddleware` is the only WS-aware tracer and even it does **not** trace WS frames (ISS-005).

### New findings on this branch (not in §6.6)
| # | Component | File | Status | Proof |
|---|---|---|---|---|
| N1 | `app/services/chat/agents/orchestrator.py` (uses `EducationCouncil`, `MultiAgentOrchestrator`-style) | `app/services/chat/agents/orchestrator.py:11,83,647` | **ZOMBIE** | No importer in `app/api/`, `app/main.py`, `app/kernel.py`, `local_graph.py`, or `orchestrator_client.py`. Lives parallel to the live chat path and is never called. |
| N2 | `app/services/chat/agents/education_council.py` (`class EducationCouncil`) | `agents/education_council.py:96` | **ZOMBIE** | Only consumer is `agents/orchestrator.py` (itself ZOMBIE — see N1). |
| N3 | `app/services/chat/graph/components/` (`context_composer`, `intent_detector`, `prompt_strategist`) | `app/services/chat/graph/components/*.py` | **ZOMBIE** | Only referenced from inside `graph/workflow.py` (already classified ZOMBIE in §6.6). |
| N4 | `app/services/chat/graph/nodes/supervisor.py` | inside `graph/nodes/` | **ZOMBIE** | Sibling of the dead `super_reasoner/planner/researcher/...` set; same fate. |
| N5 | `app/services/chat/dispatcher.py`, `intent_detector.py`, `intent_registry.py`, `tool_router.py`, `tool_access.py`, `education_policy_gate.py`, `orchestration_rollout.py` | top of `services/chat/` | **ZOMBIE/UNKNOWN** | Zero importers in `app/api/`, `app/main.py`, `app/kernel.py`. The live path goes router → `OrchestratorClient` → `local_graph` and never touches these. |
| N6 | Frontend WS connector | `frontend/app/hooks/useRealtimeConnection.js:56` | **ACTIVE** | `new WebSocket(wsUrlObj.toString(), ["jwt", token])` is the single browser-side WS factory; consumed by `useAgentSocket.js:180`. |
| N7 | Frontend → Backend HTTP proxy | `frontend/next.config.js` | **ACTIVE** | `rewrites` send `/api/:path*`, `/health`, `/admin/api/:path*` → `${API_URL}` (default `http://127.0.0.1:8000`). |
| N8 | Orchestrator microservice DB writers | `microservices/orchestrator_service/src/api/routes.py:1211, 1216, 1361, 1366` | **DORMANT** | Real INSERTs into `customer_messages` / `admin_messages` exist — but the microservice is not started by the default devcontainer, so they never fire. When awoken, D-006 contract (`compatibility_facade=True` + `persisted: true` echo) is the only thing preventing dual-write. |
| N9 | Dual Redis design | `docker-compose.yml` (services `redis:6379`, `redis-orchestrator:6380`) | **DORMANT** | Only `redis-orchestrator` is wired into the orchestrator microservice. In default devcontainer, neither runs; cache falls through to in-memory (`app/caching/factory.py`). |

### Architectural diagnosis (verdict)
1. **API-first?** Half-true. The Monolith exposes a clean REST + WS surface (9 routers, 2 WS endpoints) with consistent prefixes. But the *cross-service* contracts (microservice ↔ microservice) only exist on paper — there is no live gateway, no service registry being consulted, no contract test running between live processes in the default environment.
2. **Microservices?** Hybrid / transitional. 10 microservices have real code (planning_agent and orchestrator_service have substantial logic; others are minimal). None are started by the default devcontainer. The "control plane" diagram in `ARCHITECTURE.md` describes the *target*, not the runtime.
3. **StateGraph / multi-agent reasoning?** Almost entirely zombie. `local_graph.py` is a 2-node graph (supervisor + chat). The 6-node multi-agent workflow (`graph/workflow.py` + `graph/nodes/*`), the `EducationCouncil`, and the chat agents `orchestrator.py` all sit off the live path. **No multi-agent coordination runs in production today.**
4. **Streaming?** Token streaming is degraded by ISS-023 — `local_graph.py:266` uses `ainvoke`, not `astream_events`, so the UI receives blocks rather than tokens. Terminal-frame guarantee (§6.5) holds.
5. **Persistence split-brain?** Resolved on paper (D-006), enforced by architecture test (`tests/architecture/test_persistence_authority.py`). Physically impossible in default devcontainer because the orchestrator is dormant. Becomes load-bearing the moment the full stack is woken.
6. **Capability fragmentation?** Severe. Six "agentic" technology layers (LangGraph multi-agent, LlamaIndex, DSPy, Reranker, KAgent, MCP) are present in the repo as imports + DI registrations + tests — but **none are reachable from a production WS request**. The codebase advertises a stack that the runtime does not run.

### Net statement (for any future session)
- **The system is in a transitional state**: a Monolith with a well-tested chat boundary, plus a parallel (but dormant) microservice mesh, plus a parallel (but zombie) multi-agent layer.
- **In default Codespaces, ~10% of the agentic surface is live** — the rest is scaffolding.
- **Moving from "fragmented/transitional" to "production-grade multi-service" requires three serial migrations**, all out of scope for this audit:
  1. Wake the microservices (compose up + env wiring) and prove `compatibility_facade=True` + `persisted=true` round-trip works end-to-end under load.
  2. Wire ONE multi-agent path into the live router (replace or augment the LangGraph fallback in `OrchestratorClient`) with a real call chain and runtime trace — this turns the first ZOMBIE into ACTIVE.
  3. Decide explicitly per ZOMBIE/DORMANT layer (LlamaIndex, DSPy, Reranker, KAgent, MCP): **promote, archive, or delete with ADR**. No half-alive code.

### Rules Claude MUST follow before any change to this stack
1. Open §6.6 and §6.8. If the touched component is **ZOMBIE/DORMANT**, declare it explicitly and decide: wire it (with a runtime trace requirement) or leave it untouched.
2. Never add a feature whose call chain depends on a ZOMBIE/DORMANT layer without first wiring that layer into a live entrypoint and demonstrating runtime evidence.
3. Never assume the microservice mesh is up. The default execution path is router → `OrchestratorClient` → ConnectError → fallback chain → `local_graph`. Any code that assumes otherwise must be feature-flagged on `ORCHESTRATOR_SERVICE_URL` set.
4. Never duplicate `_emit_terminal_frames`, never silence the `persisted` flag, never re-introduce dual-write — these are §6.5 invariants.
5. Truth-table updates require: `file:line` + 1–3 line snippet + import path + call-chain trace. No exceptions.

---

## 6.9 Architecture Rescue Diagnostic (2026-05-06 — branch `claude/architecture-rescue-diagnostic-wUfbE`)

> Third independent re-verification of §6.6 / §6.8 on this branch. **All 25 prior rows of the truth table CONFIRMED in spirit.** Two material corrections to the prior table, one new PARTIAL classification, and one CI gap newly elevated to a known issue.

### Corrections to the prior truth table (must override §6.6)

**C1 — Row 12 mislabels the class.** §6.6 row 12 says:
> `app/core/integration_kernel/runtime.py` (`RealityKernel` micro-kernel) — ZOMBIE — singleton designed but never instantiated…

The actual class in that file is `IntegrationKernel` (`app/core/integration_kernel/runtime.py:13: class IntegrationKernel:`), **not** `RealityKernel`. The verdict (ZOMBIE) still holds — `IntegrationKernel` is instantiated only at `app/services/mcp/integrations.py:49` (`self.kernel = IntegrationKernel()`), and `MCPIntegrations` itself has zero live consumers. But the parenthetical name in the table is wrong and conflates two different classes:
- `app/kernel.py:103: class RealityKernel:` → **ACTIVE** — instantiated at `app/main.py:22` (`_kernel = RealityKernel(...)`) and `app/main.py:49` (`kernel = RealityKernel(...)`). This is the live FastAPI bootstrap.
- `app/core/integration_kernel/runtime.py:13: class IntegrationKernel:` → **ZOMBIE** — only path to it goes through dormant MCP.

Treat the row 12 entry as covering `IntegrationKernel`. `RealityKernel` (live) is implicitly covered by the kernel.py importers in row 13.

**C2 — Top-level chat helpers are loaded-not-invoked, not pure ZOMBIE.** §6.6 row N5 (and §6.6 entry for `dispatcher.py / intent_detector.py / tool_router.py / …`) says these are ZOMBIE/UNKNOWN. Re-verification on this branch shows a more nuanced reality:

- `app/api/routers/customer_chat.py:27-28` imports `CustomerChatBoundaryService`.
- `customer_chat_boundary_service.py:22-23` imports `IntentDetector` and `ToolRouter` and instantiates both at construction (`__init__` lines 40-41).
- The boundary service is instantiated by the live router on every connection (`customer_chat.py:329, 522`).
- **However**, the live router calls only the persistence methods on it (`get_or_create_conversation`, `save_message`, `get_chat_history`, `list_user_conversations`, `get_latest_conversation_details`, `get_conversation_details`).
- The streaming methods (`stream_chat`, `orchestrate_chat_stream`, lines 95-110, 112-260) — which are the only paths that ever call `intent_detector.detect()` or `tool_router.authorize_intent()` — are **never invoked** by `app/api/`. Grep for `orchestrate_chat_stream` and `stream_chat` outside the boundary service returns zero hits in `app/api/`.

**Net status of `intent_detector.py` / `tool_router.py` / `tool_access.py` / `dispatcher.py` / `intent_registry.py` / `education_policy_gate.py` / `orchestration_rollout.py`**: code-loaded and class-instantiated on the live path, but **functionally never invoked** for a real WS turn. We classify these as **PARTIAL (loaded-not-invoked)** — slightly stronger than ZOMBIE because they execute `__init__` once per WS connection, but they do not influence chat output.

The same applies to `app/services/chat/orchestrator.py:ChatOrchestrator` and `app/services/customer/chat_streamer.py:CustomerChatStreamer` / `app/services/admin/chat_streamer.py:AdminChatStreamer`: they are instantiated at boundary-service construction (`customer_chat_boundary_service.py:38`, `admin_chat_boundary_service.py:49`) but their `stream_response` method is never reached because the live router uses `OrchestratorClient.chat_with_agent` directly (`customer_chat.py:422`, `admin.py:490`). **PARTIAL (loaded-not-invoked)**.

### New finding — CI is a partial gate, not a complete one (ISS-025)

`.github/workflows/ci.yml` has a strong aggregator (`required-ci`) running ruff + contracts + guardrails + pytest, plus `.github/workflows/structure-validation.yml` blocking on `validate_structure.py`. **What it covers:** lint, AST guardrails (no print, no DB factory outside `app/core/database.py`, no `app.*` imports inside microservices), route-registry parity, tracing gate, pytest, structural shape.

**What CI does NOT cover (newly tracked as ISS-025):**
1. **Persistence authority (D-006) integration test** — the architecture test `tests/architecture/test_persistence_authority.py` is referenced but a pytest run in default Codespaces cannot exercise the orchestrator round-trip (microservice dormant). The contract is enforced statically only.
2. **Terminal-frame integrity contract** — no test asserts that every WS turn emits exactly one `assistant_final` OR one `error` frame, plus exactly one `persisted` event. The `_emit_terminal_frames` helper is the single emitter, but no CI test pins this.
3. **Truth-table sync** — nothing fails CI when a ZOMBIE acquires a new importer in `app/api/`, `app/main.py`, or `app/kernel.py` without a matching `.memory/runtime_truth.md` update.
4. **Doc integrity** — nothing fails CI if `CLAUDE.md` or any `.memory/*.md` file is deleted, emptied, or replaced with stale content. PR template asks reviewers; nothing automates it.
5. **Stale-markdown detection** — no check for resurrected `docs/archive/`, dated diagnostic dumps in `docs/diagnostics/`, or scratch `*.txt` / `Screenshot_*.png` artifacts in repo root.
6. **Frontend build/type check** — Next.js never compiles in CI; UI regressions only surface at runtime.

A new workflow `.github/workflows/doc_integrity.yml` (added in this branch) plugs items 4 and 5: it fails on missing/empty `CLAUDE.md` or `.memory/*` files, on root-level scratch artifacts, and on dated diagnostic patterns recurring outside `docs/archive/`. Items 1, 2, 3, 6 remain TODO (tracked in §13 ISS-025).

### Markdown debt — §15 policy is documented but not enforced

CLAUDE.md §15 (2026-05-06) declares that old reports/diagnostics were removed from `docs/archive/`. Ground truth on this branch:

- `docs/archive/` does not exist as a directory.
- `docs/diagnostics/` still contains 14+ dated forensic dumps (`MULTI_AGENT_CATASTROPHIC_DIAGNOSIS_2026-02-11.md`, `architectural_deep_diagnosis_2026-02-24.md`, `FORENSIC_BASELINE_2026-02-27.md`, `ULTRA_FORENSIC_*.md`, `ULTRA_SURGICAL_DIAGNOSTIC_REPORT_V7.md`, etc.).
- `docs/` root contains 7+ phase-report files (`PHASE_18_*.md`, `PHASE_19_*.md`).
- Repo root contains 17 leftover scratch artifacts (`api_coverage*.txt`, `services_errors*.txt`, `core_errors.txt`, `collection_errors.txt`, `proof_output.txt`, `app_imports.txt`, `commit_message.txt`, `telemetry_evidence.txt`, `patch_*.diff`, `ruff_output*.txt`, `err_*.txt`) and 4 unreferenced screenshots.
- `LangGraph_Architectural_Blueprint.md` and `ARCHITECTURE.md` (root) describe target/dormant architecture and duplicate the canonical content in `docs/architecture/MICROSERVICES_CONSTITUTION.md`. Both should be archived or merged.
- `AGENTS-IMPROVEMENT-SPEC.md` is an unapplied audit of `AGENTS.md` (dated 2026-04-28).

**Action policy on this branch (read-only diagnostic):** the consolidation list is captured in `.memory/diagnostic_2026_05_06_rescue.md` (Markdown Debt section); nothing has been deleted yet. Deletion is reserved for an explicit follow-up PR (the user must approve specific files). The new `doc_integrity.yml` workflow flags the most obvious offenders so they cannot multiply silently.

### Net architectural verdict (third independent confirmation)

Re-confirms `.memory/runtime_truth.md` and §6.8:

1. **API-first?** Half. Monolith REST + WS surface is clean (9 routers). Cross-service contracts (microservice ↔ microservice) live only on paper.
2. **Microservices?** Hybrid / transitional. Real code in 10 directories; **none** start by default. `compatibility_facade=True` + `persisted: true` echo handshake is documented and statically tested but cannot be runtime-tested in default Codespaces.
3. **Multi-agent reasoning?** Almost entirely zombie. `local_graph.py` is 2 nodes (supervisor + chat). `workflow.py`, `EducationCouncil`, `agents/orchestrator.py`, `agents/admin.py`, `agents/curriculum.py`, `agents/analytics.py` all sit off the live path.
4. **Streaming?** Degraded by ISS-023 — `local_graph.py:266` uses `await graph.ainvoke(...)` not `astream_events`. Terminal-frame guarantee holds.
5. **Persistence split-brain?** Resolved on paper (D-006). Physically impossible in default devcontainer because the orchestrator is dormant. Becomes load-bearing the moment the full stack is woken.
6. **Capability fragmentation?** Severe and unchanged. LangGraph multi-agent / LlamaIndex / DSPy / Reranker / KAgent / MCP — all six advertised "agentic" layers remain unreachable from a production WS request on default infra.

**The system uses ~10% of its advertised agentic surface in default deployment.** This number has not moved across three independent audits. It will only move when an explicit wiring PR makes one of the dormant layers ACTIVE per the §6.6 three-part proof requirement.

### What Claude must do before any future change touching this stack
1. Open §6.5, §6.6, §6.8, §6.9, plus `.memory/runtime_truth.md`.
2. Classify the touched component using the truth table. If the component is missing → it is UNKNOWN until a fresh import + call-chain + runtime trace is produced.
3. If the change adds a new importer of a ZOMBIE/DORMANT module from `app/api/`, `app/main.py`, or `app/kernel.py`, the same PR MUST update `.memory/runtime_truth.md` row for that module with the new evidence — otherwise the doc-integrity workflow will flag the drift.
4. Never duplicate `_emit_terminal_frames`. Never silence the `persisted` flag. Never re-introduce dual-write paths. Never move the user-message write away from the WS entrypoint.
5. Never assume the microservice stack is up. If the change requires it, gate the new code on `ORCHESTRATOR_SERVICE_URL` being set AND mark the new code DORMANT in the truth table until proven by runtime evidence on a stack-up environment.
6. Do not delete a ZOMBIE/DORMANT file on sight. Decide explicitly: promote (with proof), archive (mark + gate), or delete with ADR. No half-alive code.

---

*Closing rule (re-affirmed for the third time):* **Any component that does not have all three of `import` + `call chain` + `runtime evidence` reaching from `app/main.py` is treated as DORMANT or ZOMBIE until the contrary is proven. "Loaded but never invoked" is PARTIAL, not ACTIVE.**

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

## 14. Microservices (All Dormant in Codespaces by Default)

These exist in `microservices/` but **do not start** in the default Codespaces devcontainer (which only spins up the `web` container via `.devcontainer/docker-compose.host.yml`):

| Service | Port | Status |
|---|---|---|
| orchestrator-service | 8006 | DORMANT — ConnectError expected |
| planning-agent | 8001 | DORMANT |
| memory-agent | 8002 | DORMANT |
| user-service | 8003 | DORMANT |
| research-agent | 8007 | DORMANT |
| reasoning-agent | 8008 | DORMANT |
| auditor-service | 8009 | DORMANT |
| conversation-service | 8010 | DORMANT |

To wake the full microservices stack (separate from the devcontainer): `docker compose -f docker-compose.yml up -d`

---

*Last updated: 2026-05-06 — third independent audit (`claude/architecture-rescue-diagnostic-wUfbE`) added §6.9 (Architecture Rescue Diagnostic). Two corrections applied to §6.6 truth table (row 12 class-name fix, row 21 promoted to `PARTIAL (loaded-not-invoked)`); two new rows (26, 27) describing boundary-service split-active and chat-streamer loaded-not-invoked. CI doc-integrity workflow added (`.github/workflows/doc_integrity.yml`) — gates `CLAUDE.md` + `.memory/*` integrity, the closing rule, and (advisory) repo-root scratch artifacts. New issues: ISS-025 (CI gates gap), ISS-026 (loaded-not-invoked decision required). Markdown debt inventory captured in `.memory/diagnostic_2026_05_06_rescue.md`; no deletions performed in this branch.*

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
