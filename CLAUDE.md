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

*Last updated: 2026-05-05 — environment corrected from Replit to GitHub Codespaces*
