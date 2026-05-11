# supervisor.sh Launch Patterns

## Location

`.devcontainer/supervisor.sh` — runs at devcontainer boot. Each service has a `launch_<service>()` function called in the background.

## Canonical Launch Function Pattern

```bash
launch_myservice() {
    local PORT="80XX"
    local LOG_DIR="$APP_ROOT/.observability"
    local LOG="$LOG_DIR/myservice.log"
    local HEALTH="http://localhost:${PORT}/health"

    mkdir -p "$LOG_DIR"

    # 1. Guard: skip if no DATABASE_URL
    if [ -z "${DATABASE_URL:-}" ]; then
        lifecycle_warn "myservice: DATABASE_URL not set — skipping"
        return 0
    fi

    # 2. Idempotent: skip if already running and healthy
    if pgrep -f "myservice.main:app" > /dev/null 2>&1 \
       && curl -sf --connect-timeout 2 "$HEALTH" > /dev/null 2>&1; then
        lifecycle_info "myservice: already running — skipping"
        return 0
    fi

    # 3. Kill stale process
    pkill -f "myservice.main:app" 2>/dev/null || true
    sleep 1

    # 4. Build asyncpg URL (ISS-040 + ISS-038-B)
    local db_url="${MYSERVICE_DATABASE_URL:-${DATABASE_URL:-}}"
    db_url="${db_url/postgresql:\/\//postgresql+asyncpg://}"
    db_url="${db_url/postgresql+psycopg2:\/\//postgresql+asyncpg://}"
    db_url=$(echo "$db_url" | sed 's/:6543\//:5432\//')      # ISS-040
    db_url=$(echo "$db_url" | sed 's/[?&]sslmode=[^&]*//')   # asyncpg no sslmode in URL

    lifecycle_info "myservice: starting on :${PORT}..."

    # 5. Launch with nohup python -m uvicorn (NOT bare uvicorn — ISS-046-B)
    MYSERVICE_DATABASE_URL="$db_url" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    SECRET_KEY="${SECRET_KEY:-super_secret_key_change_in_production}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    PYTHONPATH="$APP_ROOT" \
    nohup python -m uvicorn microservices.myservice.main:app \
        --host 0.0.0.0 \
        --port "$PORT" \
        --workers 1 \
        --log-level info \
        >> "$LOG" 2>&1 &

    local pid=$!
    lifecycle_info "myservice: launched (PID=$pid) — health at $HEALTH"
    lifecycle_info "             Logs: $LOG"
}

# Call in background — never blocks supervisor
launch_myservice >> "$APP_ROOT/.observability/myservice.log" 2>&1 &
lifecycle_info "✅ myservice initialization offloaded to background"
```

## Critical Rules

1. **Always `nohup python -m uvicorn`** — bare `uvicorn` binary may not inherit env vars reliably (ISS-046-B).
2. **Always convert port 6543→5432** — PgBouncer rejects asyncpg prepared statements (ISS-040).
3. **Always strip `sslmode` from URL** — asyncpg handles SSL via `connect_args`, not query string.
4. **Always convert `postgresql://` → `postgresql+asyncpg://`** — SQLAlchemy async requires asyncpg driver (ISS-038-B).
5. **Idempotent check before launch** — prevents duplicate processes on supervisor restart.
6. **Background call** — `launch_X >> log 2>&1 &` — never blocks the supervisor main flow.

## Orchestrator-specific: CODESPACES=true

Orchestrator requires additional env vars for Skills Pipeline routing:

```bash
CODESPACES="true" \                              # ISS-046-A: use localhost URLs
OUTBOX_RELAY_ENABLED="true" \
PLANNING_AGENT_URL="http://localhost:8002" \
RESEARCH_AGENT_URL="http://localhost:8007" \
REASONING_AGENT_URL="http://localhost:8008" \
USER_SERVICE_URL="http://localhost:8001" \
```

Without `CODESPACES=true`, `config.py:resolve_service_urls()` returns Docker hostnames that don't resolve in native/Codespaces mode.

## Step Labels in Prometheus

Each service sets a `step` label in its startup_info metric. This maps to the development step when the service was activated:

| Service | Step |
|---------|------|
| user-service | 5 |
| planning-agent | 6 |
| research-agent | 7 |
| reasoning-agent | 8 |
| skills-pipeline (orchestrator) | 9 |
| postgres-checkpointer (orchestrator) | 10 |
| content-retrieval-skill | 11 |
| conversation-service | 12 |

When adding a new service, use the next step number and add a Prometheus scrape target in `observability/native/prometheus.yml`.

## Log Locations

All service logs go to `$APP_ROOT/.observability/`:
- `orchestrator.log`
- `planning_agent.log`
- `research_agent.log`
- `reasoning_agent.log`
- `user_service.log`
- `conversation_service.log`
- `content_retrieval_skill.log`

Quick tail: `tail -f /workspaces/NAAS-Agentic-Core/.observability/<service>.log`
