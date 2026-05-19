#!/usr/bin/env bash
# CogniForge — Live Microservices Verification Script
# ----------------------------------------------------
# يُشغَّل في GitHub Codespaces ليُظهِر:
#   1. صحة كل خدمة من الـ 8 خدمات
#   2. اتصال الأسرار (DATABASE_URL, OPENROUTER_API_KEY, TAVILY_API_KEY)
#   3. وضع الـ pipeline (full/partial/fallback)
#   4. حالة Prometheus + Grafana
#
# الاستخدام:
#   bash scripts/verify_microservices_live.sh
#
# Exit 0 = كل شيء يعمل | Exit 1 = خدمة واحدة فاشلة أو أكثر

set -uo pipefail

# ── ألوان ─────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASS=0
FAIL=0
WARN=0

# ── دوال مساعدة ────────────────────────────────────────────────────────────────
hr() { printf '═%.0s' {1..78}; echo; }
section() { hr; echo -e "${BOLD}${CYAN}$1${NC}"; hr; }

probe_health() {
    local port="$1"
    local name="$2"
    local expected="$3"  # نمط grep يجب أن يطابق في الإستجابة

    local response
    response=$(curl -sf --max-time 5 "http://localhost:${port}/health" 2>/dev/null)
    local status=$?

    if [ $status -ne 0 ] || [ -z "$response" ]; then
        echo -e "  ${RED}❌ :${port} ${name} — DEAD (no response)${NC}"
        FAIL=$((FAIL+1))
        return 1
    fi

    if echo "$response" | grep -q "$expected"; then
        echo -e "  ${GREEN}✅ :${port} ${name}${NC}"
        echo "     $response" | head -c 200
        echo ""
        PASS=$((PASS+1))
        return 0
    else
        echo -e "  ${YELLOW}⚠️  :${port} ${name} — ALIVE but unexpected state${NC}"
        echo "     $response" | head -c 200
        echo ""
        WARN=$((WARN+1))
        return 1
    fi
}

check_secret_wired() {
    local label="$1"
    local port="$2"
    local key="$3"
    local expected="$4"  # القيمة المتوقعة (مثلاً "openrouter" أو "true")

    local actual
    actual=$(curl -sf --max-time 5 "http://localhost:${port}/health" 2>/dev/null \
             | grep -oE "\"${key}\":[\"a-zA-Z0-9_]*" | head -1)

    if [ -z "$actual" ]; then
        echo -e "  ${RED}❌ ${label} — ${key} NOT REPORTED${NC}"
        FAIL=$((FAIL+1))
    elif echo "$actual" | grep -qE "$expected"; then
        echo -e "  ${GREEN}✅ ${label} — ${actual}${NC}"
        PASS=$((PASS+1))
    else
        echo -e "  ${YELLOW}⚠️  ${label} — ${actual} (expected ${expected})${NC}"
        WARN=$((WARN+1))
    fi
}

# ── البداية ────────────────────────────────────────────────────────────────────
clear 2>/dev/null || true
section "🌐 CogniForge — Live Microservices Verification"
echo "تاريخ: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "بيئة:  ${CODESPACE_NAME:-local}"
echo ""

# ── (1) فحص متغيرات الأسرار في process env ────────────────────────────────────
section "🔑 1. Secrets in process environment"

check_env() {
    local var="$1"
    local prefix="$2"
    local val="${!var:-}"
    if [ -z "$val" ]; then
        echo -e "  ${RED}❌ ${var} — NOT SET${NC}"
        FAIL=$((FAIL+1))
    elif [ "${val#$prefix}" != "$val" ]; then
        local masked="${val:0:${#prefix}}...${val: -4}"
        echo -e "  ${GREEN}✅ ${var} — ${masked}${NC}"
        PASS=$((PASS+1))
    else
        echo -e "  ${YELLOW}⚠️  ${var} — unexpected format${NC}"
        WARN=$((WARN+1))
    fi
}

check_env "OPENROUTER_API_KEY" "sk-or-"
check_env "TAVILY_API_KEY"     "tvly-"
check_env "DATABASE_URL"       "postgresql"
echo ""

# ── (2) صحة الخدمات المصغرة ───────────────────────────────────────────────────
section "💚 2. Microservices /health probes (8 services)"
probe_health 8000 "monolith (FastAPI)"          '"application":"ok"\|"status":"ok"'
probe_health 8001 "user-service"                '"status":"ok"\|"service":"user-service"'
probe_health 8002 "planning-agent"              '"status":"ok"\|"service":"planning-agent"'
probe_health 8003 "conversation-service"        '"status":"healthy"\|"graph_ready":true'
probe_health 8006 "orchestrator-service"        '"status":"ok"\|"graph_ready":true\|"startup_state":"ready"'
probe_health 8007 "research-agent"              '"status":"healthy"\|"service":"research-agent"'
probe_health 8008 "reasoning-agent"             '"status":"healthy"\|"service":"reasoning-agent"'
probe_health 8009 "content-retrieval-skill"     '"status":"healthy"\|"service":"content-retrieval"'
echo ""

# ── (3) فحص ربط الأسرار بالخدمات ───────────────────────────────────────────────
section "🔗 3. Secrets wired into running services"
check_secret_wired "research-agent  Tavily"    8007 "tavily_available"  "true"
check_secret_wired "reasoning-agent LLM"       8008 "llm_backend"       "openrouter\|openai"
check_secret_wired "reasoning-agent MCTS"      8008 "mcts_enabled"      "true"
check_secret_wired "orchestrator   graph"      8006 "graph_ready"       "true"
check_secret_wired "orchestrator   startup"    8006 "startup_state"     "ready"
check_secret_wired "conversation   graph"      8003 "graph_ready"       "true"
echo ""

# ── (4) Pipeline /compose (الاختبار النهائي) ─────────────────────────────────
section "🧠 4. Skills Pipeline /compose — real BAC question"
RESP=$(curl -sf --max-time 90 -X POST http://localhost:8006/compose \
       -H "Content-Type: application/json" \
       -d '{"query":"اشرح قانون أوم في الكهرباء","user_id":7,"conversation_id":1}' \
       2>/dev/null)
if [ -z "$RESP" ]; then
    echo -e "  ${RED}❌ /compose — UNREACHABLE${NC}"
    FAIL=$((FAIL+1))
else
    MODE=$(echo "$RESP" | grep -oE '"pipeline_mode":"[a-z]+"' | head -1 | cut -d'"' -f4)
    SKILLS=$(echo "$RESP" | grep -oE '"skills_active":\[[^]]+\]' | head -1)
    DURATION=$(echo "$RESP" | grep -oE '"total_duration_ms":[0-9.]+' | head -1 | cut -d: -f2)
    ANSWER=$(echo "$RESP" | grep -oE '"composed_answer":"[^"]*"' | head -1 | cut -d'"' -f4 | head -c 300)

    if [ "$MODE" = "full" ]; then
        echo -e "  ${GREEN}✅ pipeline_mode = full${NC}"
        PASS=$((PASS+1))
    elif [ "$MODE" = "partial" ]; then
        echo -e "  ${YELLOW}⚠️  pipeline_mode = partial${NC}"
        WARN=$((WARN+1))
    else
        echo -e "  ${RED}❌ pipeline_mode = ${MODE:-fallback}${NC}"
        FAIL=$((FAIL+1))
    fi
    echo "     skills_active: $SKILLS"
    echo "     duration_ms:   $DURATION"
    echo "     answer (first 300 chars):"
    echo "       $ANSWER"
fi
echo ""

# ── (5) Infrastructure (Prometheus + Grafana) ─────────────────────────────────
section "📊 5. Observability stack"
probe_health 9090 "Prometheus" '/-/healthy\|Prometheus Server is Healthy' || \
    curl -sf --max-time 5 http://localhost:9090/-/healthy >/dev/null && \
    { echo -e "  ${GREEN}✅ :9090 Prometheus — healthy${NC}"; PASS=$((PASS+1)); } || \
    { echo -e "  ${RED}❌ :9090 Prometheus — DEAD${NC}"; FAIL=$((FAIL+1)); }

if curl -sf --max-time 5 http://localhost:3001/api/health >/dev/null 2>&1; then
    echo -e "  ${GREEN}✅ :3001 Grafana — healthy${NC}"
    PASS=$((PASS+1))
else
    echo -e "  ${RED}❌ :3001 Grafana — DEAD${NC}"
    FAIL=$((FAIL+1))
fi

# Prometheus targets
TARGETS_UP=$(curl -sf --max-time 5 "http://localhost:9090/api/v1/targets?state=active" 2>/dev/null \
              | grep -oE '"health":"up"' | wc -l)
TARGETS_DOWN=$(curl -sf --max-time 5 "http://localhost:9090/api/v1/targets?state=active" 2>/dev/null \
                | grep -oE '"health":"down"' | wc -l)
echo "     Prometheus targets: UP=${TARGETS_UP} DOWN=${TARGETS_DOWN}"
[ "$TARGETS_DOWN" -eq 0 ] && [ "$TARGETS_UP" -gt 0 ] && PASS=$((PASS+1)) || WARN=$((WARN+1))
echo ""

# ── الخلاصة ────────────────────────────────────────────────────────────────────
section "📋 خلاصة (Summary)"
TOTAL=$((PASS + WARN + FAIL))
echo -e "  ${GREEN}✅ PASS: $PASS${NC}  |  ${YELLOW}⚠️  WARN: $WARN${NC}  |  ${RED}❌ FAIL: $FAIL${NC}  /  TOTAL: $TOTAL"
echo ""

if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}🎉 الخدمات المصغرة تعمل بشكل خارق — جميع الفحوصات نجحت!${NC}"
    exit 0
elif [ "$FAIL" -eq 0 ]; then
    echo -e "${YELLOW}${BOLD}⚠️  الخدمات تعمل لكن بعض الإعدادات تحتاج مراجعة (${WARN} تحذير)${NC}"
    exit 0
else
    echo -e "${RED}${BOLD}❌ ${FAIL} خدمة/فحص فشل — راجع التفاصيل أعلاه${NC}"
    echo ""
    echo "💡 إصلاحات شائعة:"
    echo "  - إذا الخدمات DEAD: bash .devcontainer/supervisor.sh restart"
    echo "  - إذا الأسرار غير مُعَيَّنة: راجع GitHub Codespaces Secrets settings"
    echo "  - إذا pipeline_mode=fallback: تأكد من OPENROUTER_API_KEY + TAVILY_API_KEY"
    exit 1
fi
