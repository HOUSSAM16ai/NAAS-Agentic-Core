#!/usr/bin/env bash
# إعادة تشغيل جميع الخدمات المصغرة مع الأسرار من البيئة أو secrets.env
# الخطوة 11: ISS-042 — Service Token + OPENROUTER + TAVILY حقيقية
#
# الاستخدام:
#   bash scripts/restart_all_services.sh
#
# الأسرار المطلوبة (من Gitpod Secrets أو .devcontainer/secrets.env):
#   OPENROUTER_API_KEY, TAVILY_API_KEY, DATABASE_URL
set -e

APP_ROOT="${APP_ROOT:-/workspaces/NAAS-Agentic-Core}"
LOG_DIR="$APP_ROOT/.observability"

# ── تحميل secrets.env إذا لم تكن الأسرار في البيئة ──────────────────────────
SECRETS_FILE="$APP_ROOT/.devcontainer/secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
    set -a && source "$SECRETS_FILE" && set +a
    echo "[restart] Loaded secrets from $SECRETS_FILE"
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "[restart] ERROR: DATABASE_URL not set — cannot start"
    exit 1
fi

# ISS-038-B + ISS-040: asyncpg + port 5432 (direct PG, not PgBouncer 6543)
if [[ -z "${ORCHESTRATOR_DATABASE_URL:-}" ]]; then
    ORCHESTRATOR_DATABASE_URL=$(echo "$DATABASE_URL" \
        | sed 's|postgresql://|postgresql+asyncpg://|' \
        | sed 's|:6543/|:5432/|' \
        | sed 's|?sslmode=require||')
fi
PLANNING_DATABASE_URL="${ORCHESTRATOR_DATABASE_URL}"
SECRET_KEY="${SECRET_KEY:-super_secret_key_change_in_production}"

mkdir -p "$LOG_DIR"

echo "[restart] Stopping all microservices..."
pkill -f "uvicorn microservices\." 2>/dev/null || true
sleep 2

echo "[restart] Starting reasoning-agent :8008..."
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
REASONING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
SECRET_KEY="$SECRET_KEY" ENVIRONMENT="development" PYTHONPATH="$APP_ROOT" \
nohup python -m uvicorn microservices.reasoning_agent.main:app \
  --host 0.0.0.0 --port 8008 --log-level info --no-access-log \
  >> "$LOG_DIR/reasoning_agent.log" 2>&1 & echo "  PID=$!"

echo "[restart] Starting research-agent :8007..."
RESEARCH_DATABASE_URL="$PLANNING_DATABASE_URL" DATABASE_URL="$PLANNING_DATABASE_URL" \
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
SECRET_KEY="$SECRET_KEY" ENVIRONMENT="development" PYTHONPATH="$APP_ROOT" \
nohup python -m uvicorn microservices.research_agent.main:app \
  --host 0.0.0.0 --port 8007 --log-level info --no-access-log \
  >> "$LOG_DIR/research_agent.log" 2>&1 & echo "  PID=$!"

echo "[restart] Starting planning-agent :8002..."
PLANNING_DATABASE_URL="$PLANNING_DATABASE_URL" \
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" PLANNING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
SECRET_KEY="$SECRET_KEY" ENVIRONMENT="development" PYTHONPATH="$APP_ROOT" \
nohup python -m uvicorn microservices.planning_agent.main:app \
  --host 0.0.0.0 --port 8002 --workers 1 --log-level info \
  >> "$LOG_DIR/planning_agent.log" 2>&1 & echo "  PID=$!"

echo "[restart] Starting user-service :8001..."
DATABASE_URL="${DATABASE_URL}" SECRET_KEY="$SECRET_KEY" \
ENVIRONMENT="development" PYTHONPATH="$APP_ROOT" \
nohup python -m uvicorn microservices.user_service.main:app \
  --host 0.0.0.0 --port 8001 --workers 1 --log-level info \
  >> "$LOG_DIR/user_service.log" 2>&1 & echo "  PID=$!"

echo "[restart] Starting orchestrator-service :8006..."
ORCHESTRATOR_DATABASE_URL="$ORCHESTRATOR_DATABASE_URL" \
OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
SECRET_KEY="$SECRET_KEY" OUTBOX_RELAY_ENABLED="true" CODESPACES="true" \
PLANNING_AGENT_URL="http://localhost:8002" RESEARCH_AGENT_URL="http://localhost:8007" \
REASONING_AGENT_URL="http://localhost:8008" USER_SERVICE_URL="http://localhost:8001" \
ENVIRONMENT="development" PYTHONPATH="$APP_ROOT" \
nohup python -m uvicorn microservices.orchestrator_service.main:app \
  --host 0.0.0.0 --port 8006 --workers 1 --log-level info \
  >> "$LOG_DIR/orchestrator.log" 2>&1 & echo "  PID=$!"

echo "[restart] Starting content-retrieval-skill :8009..."
KB_ROOT="$APP_ROOT/knowledge_base" ENVIRONMENT="development" PYTHONPATH="$APP_ROOT" \
nohup python -m uvicorn microservices.content_retrieval_skill.main:app \
  --host 0.0.0.0 --port 8009 --log-level info --no-access-log \
  >> "$LOG_DIR/content_retrieval_skill.log" 2>&1 & echo "  PID=$!"

echo "[restart] Waiting 15s for all services to boot..."
sleep 15

echo ""
echo "=== Health Matrix ==="
for svc in "8001:user-service" "8002:planning-agent" "8006:orchestrator" "8007:research-agent" "8008:reasoning-agent" "8009:content-retrieval-skill"; do
  port="${svc%%:*}"; name="${svc##*:}"
  result=$(curl -sf --connect-timeout 3 "http://localhost:$port/health" 2>/dev/null || echo '{"status":"DOWN"}')
  echo "  $name :$port → $result"
done
