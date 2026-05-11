# ISS Catalogue — Microservices Issues

## ISS-040 — PgBouncer port 6543 rejects prepared statements

- **Symptom:** `DuplicatePreparedStatementError` at startup or asyncpg connection failure
- **Root cause:** Supabase PgBouncer on port 6543 (transaction mode) intercepts and rejects prepared statements at the protocol level. `statement_cache_size=0` in `connect_args` does not help — PgBouncer acts before asyncpg's cache setting takes effect.
- **Fix:** Use port 5432 (direct PostgreSQL) for all asyncpg connections. Apply in supervisor.sh for every service:
  ```bash
  db_url=$(echo "$db_url" | sed 's/:6543\//:5432\//')
  db_url=$(echo "$db_url" | sed 's/[?&]sslmode=[^&]*//')
  ```
- **Services affected:** orchestrator, planning-agent, research-agent, conversation-service
- **Status:** FIXED in supervisor.sh for orchestrator (original fix). ISS-046-C extended fix to planning-agent.

---

## ISS-038-B — asyncpg URL scheme conversion

- **Symptom:** `sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver. The loaded 'psycopg2' is not async.`
- **Root cause:** `DATABASE_URL` from Supabase uses `postgresql://` scheme. SQLAlchemy maps this to psycopg2 (sync driver). `create_async_engine` requires `postgresql+asyncpg://`.
- **Fix:**
  ```bash
  db_url="${db_url/postgresql:\/\//postgresql+asyncpg://}"
  db_url="${db_url/postgresql+psycopg2:\/\//postgresql+asyncpg://}"
  ```
- **Status:** FIXED in supervisor.sh for all services.

---

## ISS-046-A — orchestrator CODESPACES=false → Docker hostnames

- **Symptom:** `POST /compose → pipeline_mode="fallback"`, `error="[Errno -2] Name or service not known"`
- **Root cause:** `orchestrator-service/src/core/config.py:resolve_service_urls()` uses Docker hostnames (`planning-agent:8002`, `research-agent:8007`, `reasoning-agent:8008`) when `CODESPACES != "true"`. In Codespaces/native mode, services run on localhost.
- **Fix:** Always launch orchestrator with:
  ```bash
  CODESPACES="true" \
  PLANNING_AGENT_URL="http://localhost:8002" \
  RESEARCH_AGENT_URL="http://localhost:8007" \
  REASONING_AGENT_URL="http://localhost:8008" \
  USER_SERVICE_URL="http://localhost:8001"
  ```
- **supervisor.sh status:** Already correct — only affects manually-started instances.
- **Status:** FIXED (2026-05-11).

---

## ISS-046-B — research/reasoning agents start without API keys

- **Symptom:** `research-agent /health → tavily_available="false"`. `reasoning-agent /health → llm_backend="mock"`.
- **Root cause:** Services launched by supervisor.sh at devcontainer boot before secrets were available in process env. Bare `uvicorn` binary (installed as a script) may not inherit env from the parent shell the same way `python -m uvicorn` does.
- **Fix:** Changed `uvicorn` → `nohup python -m uvicorn` in `launch_research_agent()` and `launch_reasoning_agent()`. Also added port 6543→5432 substitution for research_agent DB URL (ISS-040 parity).
- **Status:** FIXED in supervisor.sh (2026-05-11).

---

## ISS-046-C — planning-agent uses SQLite instead of Postgres

- **Symptom:** `GET /health → {"database":"sqlite+aiosqlite:///:memory:"}`.
- **Root cause:** `supervisor.sh:launch_planning_agent()` did not apply port 6543→5432 conversion. asyncpg rejects port 6543 (PgBouncer) → SQLAlchemy falls back to SQLite in-memory.
- **Fix:** Added `planning_db_url=$(echo "$planning_db_url" | sed 's/:6543\//:5432\//') ` to `launch_planning_agent()` in supervisor.sh.
- **Status:** FIXED in supervisor.sh (2026-05-11).

---

## ISS-046-D — secrets.env.example missing TAVILY_API_KEY

- **Symptom:** Developers copying `secrets.env.example` don't know to add `TAVILY_API_KEY` → research-agent starts without Tavily.
- **Fix:** Added `TAVILY_API_KEY=tvly-dev-your-key-here` to `.devcontainer/secrets.env.example`.
- **Status:** FIXED (2026-05-11).

---

## ISS-041 — LangGraph checkpointer must be subclass, not wrapper

- **Symptom:** `ensure_valid_checkpointer()` raises TypeError — checkpointer not recognized.
- **Root cause:** LangGraph validates `isinstance(checkpointer, BaseCheckpointSaver)`. A wrapper class that delegates to `AsyncPostgresSaver` fails this check.
- **Fix:** Use `_make_instrumented_class(AsyncPostgresSaver)` factory to create a true subclass at module load time.
- **Status:** FIXED in `microservices/orchestrator_service/src/core/database.py`.
