---
name: microservices-live-verification
description: >
  Live verification and surgical repair of CogniForge microservices.
  Use when any microservice health check fails, when Skills Pipeline is in
  fallback/partial mode, when Prometheus targets are DOWN, or when API keys
  are not reaching services. Covers ISS-040/046 patterns, port conversion,
  CODESPACES env, and supervisor.sh launch sequences.
triggers:
  - "microservice not responding"
  - "pipeline_mode fallback"
  - "tavily_available false"
  - "llm_backend mock"
  - "Name or service not known"
  - "DuplicatePreparedStatementError"
  - "sqlite+aiosqlite:///:memory:"
  - "prometheus target down"
  - "supervisor.sh"
---

# CogniForge Microservices — Live Verification & Surgical Repair

> **Runtime truth law:** A service is ACTIVE only when:
> `import + call chain + runtime evidence + /metrics + /health` all pass.
> A process running ≠ a service healthy.

---

## 0. Quick Health Matrix

Run this first — takes 5 seconds:

```bash
for port in 8000 8001 8002 8003 8006 8007 8008 8009; do
  echo -n "Port $port: "
  curl -s --max-time 3 http://localhost:$port/health 2>&1 || echo "DEAD"
done
```

Expected healthy output per service:

| Port | Service | Key fields to verify |
|------|---------|---------------------|
| 8000 | monolith | `"application":"ok","database":"ok"` |
| 8001 | user-service | `"status":"ok"` |
| 8002 | planning-agent | `"database":"postgresql+asyncpg://..."` (NOT sqlite) |
| 8003 | conversation-service | `"graph_ready":true,"step":"12"` |
| 8006 | orchestrator-service | `"graph_ready":true,"startup_state":"ready"` |
| 8007 | research-agent | `"tavily_available":"true"` (requires TAVILY_API_KEY) |
| 8008 | reasoning-agent | `"llm_backend":"openrouter"` (requires OPENROUTER_API_KEY) |
| 8009 | content-retrieval-skill | `"kb_files":2,"step":"11"` |

---

## 1. Prometheus Targets Check

```bash
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data['data']['activeTargets']:
    status = '✅' if t['health'] == 'up' else '❌'
    print(f\"{status} {t['labels'].get('job','?'):35s} {t['health']}\")
    if t.get('lastError'):
        print(f\"   ERROR: {t['lastError'][:80]}\")
"
```

Expected: 12/12 UP. If any are DOWN, the service is not running or `/metrics` is broken.

---

## 2. Skills Pipeline Full Test

```bash
curl -s -X POST http://localhost:8006/compose \
  -H "Content-Type: application/json" \
  -d '{"query": "اشرح قانون نيوتن الثاني", "user_id": "test"}' \
  --max-time 65 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Mode:', d['pipeline_mode'])
print('Active:', d['skills_active'])
print('Duration:', round(d['total_duration_ms']/1000, 1), 's')
print('Plan:', d['plan']['status'])
print('Research:', d['research']['status'])
print('Reasoning:', d['reasoning']['status'])
"
```

**Expected:** `pipeline_mode="full"`, all 3 skills `"success"`.

---

## 3. Surgical Fixes Catalogue

### ISS-040 — PgBouncer port 6543 → 5432

**Symptom:** `DuplicatePreparedStatementError` or asyncpg connection failure.

**Root cause:** Supabase PgBouncer on port 6543 (transaction mode) rejects prepared statements at protocol level. asyncpg's `statement_cache_size=0` does not help.

**Fix pattern** (in supervisor.sh for every service):
```bash
db_url=$(echo "$db_url" | sed 's/:6543\//:5432\//')
db_url=$(echo "$db_url" | sed 's/[?&]sslmode=[^&]*//')
```

**Services requiring this fix:** orchestrator, planning-agent, research-agent, conversation-service.

---

### ISS-038-B — asyncpg URL scheme conversion

**Symptom:** `sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver. The loaded 'psycopg2' is not async.`

**Root cause:** `DATABASE_URL` from Supabase uses `postgresql://` which SQLAlchemy maps to psycopg2 (sync). `create_async_engine` requires `postgresql+asyncpg://`.

**Fix pattern:**
```bash
db_url="${db_url/postgresql:\/\//postgresql+asyncpg://}"
db_url="${db_url/postgresql+psycopg2:\/\//postgresql+asyncpg://}"
```

---

### ISS-046-A — CODESPACES=false → Docker hostnames

**Symptom:** `[Errno -2] Name or service not known` on skill calls. `/compose` returns `pipeline_mode="fallback"`.

**Root cause:** `orchestrator-service/src/core/config.py:resolve_service_urls()` uses Docker hostnames (`planning-agent:8002`) when `CODESPACES != "true"`.

**Fix:** Always launch orchestrator with:
```bash
CODESPACES="true" \
PLANNING_AGENT_URL="http://localhost:8002" \
RESEARCH_AGENT_URL="http://localhost:8007" \
REASONING_AGENT_URL="http://localhost:8008" \
USER_SERVICE_URL="http://localhost:8001" \
```

**Verify:** `curl -s http://localhost:8006/compose -d '{"query":"test"}' -H "Content-Type: application/json"` — should NOT return `"Name or service not known"`.

---

### ISS-046-B — API keys not reaching services at startup

**Symptom:** `research-agent /health → tavily_available="false"`. `reasoning-agent /health → llm_backend="mock"`.

**Root cause:** Services launched by supervisor.sh at devcontainer boot before secrets were available. Bare `uvicorn` binary may not inherit env properly.

**Fix:** Use `nohup python -m uvicorn` (not bare `uvicorn`) in supervisor.sh:
```bash
nohup python -m uvicorn microservices.research_agent.main:app \
    --host 0.0.0.0 --port 8007 --log-level info --no-access-log \
    >> "$LOG" 2>&1 &
```

**Restart with keys:**
```bash
kill $(pgrep -f "research_agent.main:app")
kill $(pgrep -f "reasoning_agent.main:app")
sleep 2

OPENROUTER_API_KEY="..." TAVILY_API_KEY="..." PYTHONPATH="/workspaces/NAAS-Agentic-Core" \
nohup python -m uvicorn microservices.research_agent.main:app \
    --host 0.0.0.0 --port 8007 --log-level info --no-access-log > /tmp/research.log 2>&1 &

OPENROUTER_API_KEY="..." PYTHONPATH="/workspaces/NAAS-Agentic-Core" \
nohup python -m uvicorn microservices.reasoning_agent.main:app \
    --host 0.0.0.0 --port 8008 --log-level info --no-access-log > /tmp/reasoning.log 2>&1 &
```

---

### ISS-046-C — planning-agent uses SQLite instead of Postgres

**Symptom:** `GET /health → {"database":"sqlite+aiosqlite:///:memory:"}`.

**Root cause:** `supervisor.sh:launch_planning_agent()` did not apply port 6543→5432 conversion. asyncpg rejects port 6543 → falls back to SQLite.

**Fix in supervisor.sh** (already applied):
```bash
planning_db_url=$(echo "$planning_db_url" | sed 's/:6543\//:5432\//')
```

**Restart:**
```bash
kill $(pgrep -f "planning_agent.main:app")
sleep 2
PLANNING_DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/db" \
SECRET_KEY="super_secret_key_change_in_production" \
OPENROUTER_API_KEY="..." \
PYTHONPATH="/workspaces/NAAS-Agentic-Core" \
nohup python -m uvicorn microservices.planning_agent.main:app \
    --host 0.0.0.0 --port 8002 --workers 1 --log-level info > /tmp/planning.log 2>&1 &
```

---

## 4. Full Stack Restart Sequence

When all services need restart with real keys:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
export TAVILY_API_KEY="tvly-dev-..."
export DATABASE_URL="postgresql://user:pass@host:6543/db?sslmode=require"
export ASYNCPG_URL="postgresql+asyncpg://user:pass@host:5432/db"
export SECRET_KEY="super_secret_key_change_in_production"
export PYTHONPATH="/workspaces/NAAS-Agentic-Core"

# 1. Kill all microservices (not monolith)
for svc in orchestrator_service planning_agent research_agent reasoning_agent \
           user_service conversation_service content_retrieval_skill; do
  pkill -f "$svc" 2>/dev/null || true
done
sleep 3

# 2. Start in dependency order
# user-service (no deps)
USER_DATABASE_URL="$ASYNCPG_URL" nohup python -m uvicorn \
  microservices.user_service.main:app --host 0.0.0.0 --port 8001 \
  --workers 1 --log-level info > /tmp/user.log 2>&1 &

# planning-agent (needs SECRET_KEY)
PLANNING_DATABASE_URL="$ASYNCPG_URL" SECRET_KEY="$SECRET_KEY" \
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" nohup python -m uvicorn \
  microservices.planning_agent.main:app --host 0.0.0.0 --port 8002 \
  --workers 1 --log-level info > /tmp/planning.log 2>&1 &

# research-agent (needs TAVILY_API_KEY)
TAVILY_API_KEY="$TAVILY_API_KEY" OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
nohup python -m uvicorn microservices.research_agent.main:app \
  --host 0.0.0.0 --port 8007 --log-level info --no-access-log > /tmp/research.log 2>&1 &

# reasoning-agent (needs OPENROUTER_API_KEY)
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" nohup python -m uvicorn \
  microservices.reasoning_agent.main:app --host 0.0.0.0 --port 8008 \
  --log-level info --no-access-log > /tmp/reasoning.log 2>&1 &

# content-retrieval-skill (no external deps)
nohup python -m uvicorn microservices.content_retrieval_skill.main:app \
  --host 0.0.0.0 --port 8009 --log-level info > /tmp/content.log 2>&1 &

# conversation-service
CONVERSATION_DATABASE_URL="$ASYNCPG_URL" nohup python -m uvicorn \
  microservices.conversation_service.main:app --host 0.0.0.0 --port 8003 \
  --log-level info > /tmp/conv.log 2>&1 &

# orchestrator (needs all others running, CODESPACES=true)
sleep 5
ORCHESTRATOR_DATABASE_URL="$ASYNCPG_URL" OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
TAVILY_API_KEY="$TAVILY_API_KEY" SECRET_KEY="$SECRET_KEY" \
CODESPACES="true" OUTBOX_RELAY_ENABLED="true" \
PLANNING_AGENT_URL="http://localhost:8002" \
RESEARCH_AGENT_URL="http://localhost:8007" \
REASONING_AGENT_URL="http://localhost:8008" \
USER_SERVICE_URL="http://localhost:8001" \
nohup python -m uvicorn microservices.orchestrator_service.main:app \
  --host 0.0.0.0 --port 8006 --workers 1 --log-level info > /tmp/orch.log 2>&1 &

echo "Waiting 15s for startup..."
sleep 15

# 3. Verify
for port in 8001 8002 8003 8006 8007 8008 8009; do
  echo -n "Port $port: "
  curl -s --max-time 3 http://localhost:$port/health 2>&1 || echo "DEAD"
done
```

---

## 5. Prometheus Metrics Verification

```bash
# Count active cogniforge metrics
curl -s "http://localhost:9090/api/v1/label/__name__/values" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  m=[x for x in d['data'] if 'cogniforge' in x]; print(f'{len(m)} cogniforge metrics')"

# Verify pipeline mode
curl -s "http://localhost:9090/api/v1/query?query=cogniforge_pipeline_invocations_total" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  [print(r['metric'].get('mode'), r['value'][1]) for r in d['data']['result']]"

# Verify startup info
curl -s "http://localhost:9090/api/v1/query?query=cogniforge_orchestrator_startup_info" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  [print(r['metric']) for r in d['data']['result']]"
```

**Expected:** 79+ cogniforge metrics, `pipeline_invocations_total{mode="full"} > 0`.

---

## 6. Grafana Dashboard Verification

```bash
# List all dashboards
curl -s -u admin:admin "http://localhost:3001/api/search?type=dash-db&limit=50" | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  print(f'{len(d)} dashboards'); [print(f'  {x[\"title\"]}') for x in d]"
```

**Expected:** 17 dashboards including `CogniForge — Master Overview (All Services)` (UID: `cogniforge-master-overview`).

---

## 7. Anti-patterns

- **Never** trust `ps aux | grep uvicorn` as proof of health — always probe `/health`.
- **Never** use port 6543 with asyncpg — always convert to 5432 before passing to SQLAlchemy.
- **Never** start orchestrator without `CODESPACES=true` in non-Docker environments.
- **Never** use bare `uvicorn` binary in supervisor.sh — use `python -m uvicorn` for reliable env inheritance.
- **Never** assume API keys are in process env — always verify with `/health` endpoint fields.
- **Never** mark a service ACTIVE if `/health` shows `tavily_available="false"` or `llm_backend="mock"` when keys are expected.

---

## 8. secrets.env Setup

Copy and fill:
```bash
cp .devcontainer/secrets.env.example .devcontainer/secrets.env
# Edit with real values:
# APP_DATABASE_URL=postgresql://...
# DATABASE_URL=postgresql://...
# OPENROUTER_API_KEY=sk-or-v1-...
# TAVILY_API_KEY=tvly-dev-...
# SECRET_KEY=<min 32 chars>
```

The file is git-ignored. supervisor.sh reads it at startup before launching services.
