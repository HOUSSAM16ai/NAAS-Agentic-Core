#!/usr/bin/env bash
# E2E launcher (sandbox/local): brings up monolith :8000 + orchestrator :8006 + frontend :5000
# on a shared SQLite file with real OpenRouter/Tavily, so you can verify routes.py answers.
# In Codespaces with real Supabase, prefer `bash .devcontainer/supervisor.sh` instead.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# 1) secrets (OPENROUTER/TAVILY/SUPABASE bridge) — git-ignored
if [ -f .devcontainer/secrets.env ]; then set -a; . .devcontainer/secrets.env; set +a; fi

# 2) shared SQLite + matching SECRET_KEY for monolith<->orchestrator JWT
DB="sqlite+aiosqlite:////${ROOT#/}/.cogniforge_e2e.db"
export APP_DATABASE_URL="$DB" DATABASE_URL="$DB"
export SECRET_KEY="${SECRET_KEY:-cogniforge-e2e-dev-secret-key-stable-0123456789abcdef}"
export ENVIRONMENT="development" CODESPACES="true"
export ORCHESTRATOR_SERVICE_URL="http://localhost:8006" ORCHESTRATOR_CHAT_ENDPOINT="state_graph"
export ORCHESTRATOR_DATABASE_URL="$DB" OUTBOX_RELAY_ENABLED="false"
export SUPABASE_URL="${SUPABASE_URL:-https://dummy.supabase.co}" SUPABASE_ROLE_KEY="${SUPABASE_ROLE_KEY:-dummy}"
PY=python3.12

_up() { curl -s -o /dev/null -w "%{http_code}" --max-time 3 "http://localhost:$1/health" 2>/dev/null; }
_wait() { for _ in $(seq 1 40); do [ "$(_up "$1")" = "200" ] && return 0; sleep 2; done; return 1; }

echo "→ monolith :8000 ..."
[ "$(_up 8000)" = "200" ] || nohup $PY -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > .e2e_monolith.log 2>&1 &
_wait 8000 && echo "  ✅ monolith UP" || { echo "  ❌ monolith failed — tail .e2e_monolith.log"; tail -5 .e2e_monolith.log; }

echo "→ orchestrator :8006 ..."
[ "$(_up 8006)" = "200" ] || nohup $PY -m uvicorn microservices.orchestrator_service.main:app --host 0.0.0.0 --port 8006 > .e2e_orchestrator.log 2>&1 &
_wait 8006 && echo "  ✅ orchestrator UP" || { echo "  ❌ orchestrator failed — tail .e2e_orchestrator.log"; tail -5 .e2e_orchestrator.log; }

echo "→ frontend :5000 ..."
if [ "$(_up 5000)" != "200" ]; then
  ( cd frontend && API_URL="http://127.0.0.1:8000" PORT=5000 HOSTNAME="0.0.0.0" nohup node server.js > "$ROOT/.e2e_frontend.log" 2>&1 & )
fi
_wait 5000 && echo "  ✅ frontend UP" || echo "  ⚠️ frontend slow/failed — tail .e2e_frontend.log"

echo
echo "الخدمات جاهزة. تحقّق بـ:"
echo "  $PY scripts/e2e_orchestrator_live.py \"ما هو قانون نيوتن الثاني؟\""
