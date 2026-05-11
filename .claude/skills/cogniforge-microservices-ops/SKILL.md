---
name: cogniforge-microservices-ops
description: >
  Live verification, surgical diagnosis, and repair of CogniForge microservices.
  Use when any of these occur: a microservice /health check fails or returns wrong
  values (tavily_available=false, llm_backend=mock, database=sqlite), Skills Pipeline
  is in fallback or partial mode instead of full, Prometheus targets are DOWN,
  API keys are not reaching services, or supervisor.sh launch issues arise.
  Triggers on: "pipeline fallback", "tavily false", "mock mode", "sqlite memory",
  "service not responding", "Name or service not known", "port 6543", "CODESPACES",
  "supervisor.sh", "restart microservice", "health check failed", "metrics DOWN".
---

# CogniForge Microservices Ops

> **Runtime truth law:** A service is ACTIVE only when `/health` returns expected
> field values AND `/metrics` exports non-zero startup_info. A running process ≠ a healthy service.

---

## 1. Quick Diagnosis (run first — 10 seconds)

```bash
# Health matrix
for port in 8000 8001 8002 8003 8006 8007 8008 8009; do
  echo -n ":$port "; curl -s --max-time 3 http://localhost:$port/health 2>&1 || echo "DEAD"
done

# Prometheus targets
curl -s http://localhost:9090/api/v1/targets | python3 -c "
import json,sys; d=json.load(sys.stdin)
for t in d['data']['activeTargets']:
    s='✅' if t['health']=='up' else '❌'
    print(s, t['labels'].get('job','?'), t.get('lastError','')[:60])
"

# Pipeline mode
curl -s -X POST http://localhost:8006/compose \
  -H "Content-Type: application/json" \
  -d '{"query":"test","user_id":"diag"}' --max-time 10 | \
  python3 -c "import json,sys; d=json.load(sys.stdin); print('mode:', d.get('pipeline_mode'), '| active:', d.get('skills_active'))"
```

**Expected healthy state:**
- `:8002` → `"database":"postgresql+asyncpg://..."` (NOT sqlite)
- `:8007` → `"tavily_available":"true"`
- `:8008` → `"llm_backend":"openrouter"`
- `:8006` → `"graph_ready":true,"startup_state":"ready"`
- Prometheus: 12/12 UP
- Pipeline: `mode: full | active: ['planning', 'research', 'reasoning']`

---

## 2. Symptom → Root Cause → Fix

### `[Errno -2] Name or service not known` on /compose

**Root cause (ISS-046-A):** orchestrator started without `CODESPACES=true`. `config.py:resolve_service_urls()` uses Docker hostnames (`planning-agent:8002`) instead of `localhost`.

**Fix:** Restart orchestrator with correct env (see §3 restart commands). supervisor.sh already sets `CODESPACES=true` — only affects manually-started instances.

---

### `tavily_available=false` or `llm_backend=mock`

**Root cause (ISS-046-B):** Service started before API keys were in process env. Bare `uvicorn` binary may not inherit env from parent shell.

**Fix:** Kill and restart with explicit keys:
```bash
kill $(pgrep -f "research_agent.main:app") 2>/dev/null
kill $(pgrep -f "reasoning_agent.main:app") 2>/dev/null
sleep 2
# See §3 for restart commands with keys
```

---

### `database=sqlite+aiosqlite:///:memory:` on planning-agent

**Root cause (ISS-046-C):** `PLANNING_DATABASE_URL` not set, and `DATABASE_URL` with port 6543 is rejected by asyncpg → falls back to SQLite.

**Fix:** Restart planning-agent with asyncpg URL using port 5432 (see §3).

---

### `DuplicatePreparedStatementError` or asyncpg connection failure

**Root cause (ISS-040):** Supabase PgBouncer on port **6543** (transaction mode) rejects prepared statements at protocol level. `statement_cache_size=0` does not help.

**Fix:** Always use port **5432** (direct PostgreSQL) for asyncpg connections. Apply this URL transformation:
```bash
db_url=$(echo "$db_url" | sed 's/:6543\//:5432\//')
db_url=$(echo "$db_url" | sed 's/[?&]sslmode=[^&]*//')
```

---

### `sqlalchemy.exc.InvalidRequestError: psycopg2 is not async`

**Root cause (ISS-038-B):** `DATABASE_URL` uses `postgresql://` scheme → SQLAlchemy maps to psycopg2 (sync). `create_async_engine` requires `postgresql+asyncpg://`.

**Fix:**
```bash
db_url="${db_url/postgresql:\/\//postgresql+asyncpg://}"
```

---

### Prometheus target DOWN

Check if the service is running and `/metrics` responds:
```bash
curl -s http://localhost:<PORT>/metrics | head -5
```
If empty or 404 → service crashed. Check logs: `cat /tmp/<service>.log | tail -30`.

---

## 3. Restart Commands (with real keys)

Replace `<OPENROUTER_KEY>`, `<TAVILY_KEY>`, `<DB_URL>` with actual values from `.devcontainer/secrets.env`.

```bash
export OPENROUTER_API_KEY="<OPENROUTER_KEY>"
export TAVILY_API_KEY="<TAVILY_KEY>"
export ASYNCPG_URL="postgresql+asyncpg://user:pass@host:5432/db"
export SECRET_KEY="super_secret_key_change_in_production"
export PYTHONPATH="/workspaces/NAAS-Agentic-Core"
cd /workspaces/NAAS-Agentic-Core

# research-agent (needs TAVILY_API_KEY)
kill $(pgrep -f "research_agent.main:app") 2>/dev/null; sleep 1
TAVILY_API_KEY="$TAVILY_API_KEY" OPENROUTER_API_KEY="$OPENROUTER_API_KEY" \
PYTHONPATH="$PYTHONPATH" nohup python -m uvicorn \
  microservices.research_agent.main:app \
  --host 0.0.0.0 --port 8007 --log-level info --no-access-log \
  > /tmp/research.log 2>&1 &

# reasoning-agent (needs OPENROUTER_API_KEY)
kill $(pgrep -f "reasoning_agent.main:app") 2>/dev/null; sleep 1
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" PYTHONPATH="$PYTHONPATH" \
nohup python -m uvicorn microservices.reasoning_agent.main:app \
  --host 0.0.0.0 --port 8008 --log-level info --no-access-log \
  > /tmp/reasoning.log 2>&1 &

# planning-agent (needs SECRET_KEY + asyncpg URL port 5432)
kill $(pgrep -f "planning_agent.main:app") 2>/dev/null; sleep 1
PLANNING_DATABASE_URL="$ASYNCPG_URL" SECRET_KEY="$SECRET_KEY" \
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" PYTHONPATH="$PYTHONPATH" \
nohup python -m uvicorn microservices.planning_agent.main:app \
  --host 0.0.0.0 --port 8002 --workers 1 --log-level info \
  > /tmp/planning.log 2>&1 &

# orchestrator (needs CODESPACES=true + explicit localhost URLs)
kill $(pgrep -f "orchestrator_service.main:app") 2>/dev/null; sleep 1
ORCHESTRATOR_DATABASE_URL="$ASYNCPG_URL" \
OPENROUTER_API_KEY="$OPENROUTER_API_KEY" TAVILY_API_KEY="$TAVILY_API_KEY" \
SECRET_KEY="$SECRET_KEY" CODESPACES="true" OUTBOX_RELAY_ENABLED="true" \
PLANNING_AGENT_URL="http://localhost:8002" \
RESEARCH_AGENT_URL="http://localhost:8007" \
REASONING_AGENT_URL="http://localhost:8008" \
USER_SERVICE_URL="http://localhost:8001" \
PYTHONPATH="$PYTHONPATH" \
nohup python -m uvicorn microservices.orchestrator_service.main:app \
  --host 0.0.0.0 --port 8006 --workers 1 --log-level info \
  > /tmp/orch.log 2>&1 &

echo "Waiting 15s..."; sleep 15
for port in 8002 8006 8007 8008; do
  echo -n ":$port "; curl -s --max-time 3 http://localhost:$port/health
  echo
done
```

---

## 4. secrets.env Setup

```bash
cp .devcontainer/secrets.env.example .devcontainer/secrets.env
# Fill in:
# APP_DATABASE_URL=postgresql://user:pass@host:6543/db?sslmode=require
# DATABASE_URL=postgresql://user:pass@host:6543/db?sslmode=require
# OPENROUTER_API_KEY=sk-or-v1-...
# TAVILY_API_KEY=tvly-dev-...
# SECRET_KEY=<min 32 chars>
```

`secrets.env` is git-ignored. supervisor.sh reads it at devcontainer boot before launching services.

---

## 5. Full Pipeline Verification

```bash
curl -s -X POST http://localhost:8006/compose \
  -H "Content-Type: application/json" \
  -d '{"query": "اشرح قانون نيوتن الثاني", "user_id": "verify"}' \
  --max-time 65 | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('Mode:', d['pipeline_mode'])
print('Active:', d['skills_active'])
print('Duration:', round(d['total_duration_ms']/1000, 1), 's')
for skill in ['plan', 'research', 'reasoning']:
    print(f'{skill}: {d[skill][\"status\"]}', d[skill].get('error') or '')
print()
print('Answer preview:', d['composed_answer'][:200])
"
```

**Expected:** `Mode: full | Active: ['planning', 'research', 'reasoning']`

---

## 6. Reference Files

- `references/iss-catalogue.md` — full ISS-040/046 issue history with evidence and fix details
- `references/service-matrix.md` — port map, env vars, health field expectations per service
- `references/supervisor-launch-patterns.md` — supervisor.sh patterns for adding new services

---

## 7. Anti-patterns

- **Never** trust `ps aux | grep uvicorn` as proof of health — always probe `/health`.
- **Never** use port 6543 with asyncpg — always convert to 5432 before passing to SQLAlchemy.
- **Never** start orchestrator without `CODESPACES=true` in non-Docker environments.
- **Never** use bare `uvicorn` binary in supervisor.sh — use `nohup python -m uvicorn`.
- **Never** assume API keys are in process env — verify with `/health` field values.
- **Never** mark a service ACTIVE if `/health` shows `tavily_available=false` or `llm_backend=mock` when keys are expected.
- **Never** wrap `AsyncPostgresSaver` — subclass it (LangGraph validates `isinstance`).
