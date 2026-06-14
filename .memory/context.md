# CogniForge — Project Context
> 🧭 **الرؤية الثورية وخارطة الطريق:** المصدر الحيّ الوحيد هو **`.memory/roadmap.md`** (ملخّص في CLAUDE.md §0.6).
> Last updated: **2026-05-12** | Branch: `claude/setup-microservices-monitoring-ralbR`.
> **Runtime capability status:** see `.memory/runtime_truth.md` (authoritative — verified live 2026-05-11; static contract sweep 2026-05-12 — see D-046).
> **CI gates today:** ruff/contracts/guardrails/tests + structure-validation + `doc-integrity` + `runtime-truth-drift-check` + `microservices-transition` + `microservices-step3-live` + `microservices-step4` + `microservices-step5-user-service` + `microservices-step6-planning-agent` + `microservices-step7-research-agent` + `microservices-step8-reasoning-agent` + `microservices-step9-skills-pipeline` + `microservices-step10-postgres-checkpointer` + `microservices-step11-full-skills` + `microservices-step12-conversation-service` + `skills-architecture-gate` + `microservices-d045-user-routing`. **All 21 workflow YAMLs validated 2026-05-12 (D-046).**

## Identity
- **Name**: NAAS-Agentic-Core (CogniForge)
- **Purpose**: AI tutor for Algerian high-school students preparing for the Baccalaureate exam
- **Languages**: Arabic (MSA) / French / Darija — all three simultaneously
- **Subjects**: Math, Physics, Chemistry, History, Geography, Languages
- **Supported environments**: GitHub Codespaces (primary dev) **and** Replit — the app is environment-agnostic. In both, microservices are DORMANT by default.
- **Codespaces**: `.devcontainer/devcontainer.json` → `docker-compose.host.yml` (web container only) → `supervisor.sh` launches `uvicorn app.main:app` + Next.js
- **Replit**: `package.json` script runs Next.js on port **5000**; backend started manually with uvicorn on 8000
- **Microservices wake-up** (either environment): `docker compose -f docker-compose.yml up -d`

## Stack (verified live 2026-05-11)
| Layer | Tech | Port | Status |
|-------|------|------|--------|
| Frontend | Next.js 15 | **3000** | ACTIVE — supervisor.sh passes `--port 3000` overriding package.json `--port 5000` |
| Backend | FastAPI (Python 3.12) | **8000** | CONDITIONAL — requires `DATABASE_URL` |
| AI Graph | LangGraph 1.1.10 | in-process | PARTIAL — 2 nodes (supervisor + chat) via fallback |
| DB | PostgreSQL 17.6 (Supabase PgBouncer) | **6543** | ACTIVE — 19 users, 2098 customer_messages, 3038 admin_messages |
| LLM | OpenRouter (primary: `nvidia/nemotron-3-super-120b-a12b:free`) | cloud | ACTIVE — 367 models, live call confirmed |
| Cache | InMemoryCache (Redis process runs but unused — no `REDIS_URL`) | 6379 | ACTIVE (in-memory only) |
| Tracing | UnifiedObservabilityService (in-process) | — | ACTIVE |
| OTEL export | otel_setup.py | — | NO-OP — `OTEL_EXPORTER_OTLP_ENDPOINT=http` is invalid |
| Grafana | native binary | **3001** | ACTIVE — 11 dashboards (Steps 2–8) |
| Prometheus | native binary | **9090** | ACTIVE — 8 scrape targets (fastapi, grafana, prometheus, orchestrator:8006, user:8001, planning:8002, research:8007, reasoning:8008) |
| Routing Policy | ChatRoutingPolicy | — | ACTIVE — default: state_graph → /api/chat/messages (Step 2) |
| orchestrator-service | uvicorn | **8006** | ACTIVE — Step 11, pipeline_mode=full, /metrics, /compose, /checkpointer/status |
| content-retrieval-skill | uvicorn | **8009** | ACTIVE — Step 11, intent_classifier + retrieval_engine, /metrics |
| user-service | uvicorn | **8001** | ACTIVE — Step 5, /metrics |
| planning-agent | uvicorn | **8002** | ACTIVE — Step 6, DSPy+LangGraph, /metrics |
| research-agent | uvicorn | **8007** | ACTIVE — Step 7, Tavily web search, /metrics |
| reasoning-agent | uvicorn | **8008** | ACTIVE — Step 8, MCTS+LLM, /metrics (NEW 2026-05-11) |

## Database state (live 2026-05-09)
- **Users**: 19 total (admin: `benmerahhoussam16@gmail.com`, user: `houssamannaba963@gmail.com`)
- **customer_messages**: 2098 rows
- **admin_messages**: 3038 rows
- **missions**: 79 rows
- **alembic_version**: `f2b3c4d5e6f7`
- **PgBouncer quirk**: transaction mode — always use `statement_cache_size=0` with asyncpg

## DB access for Claude Code — Supabase bridge (D-DB-BRIDGE-001, live 2026-06-03)
- **Tool**: `scripts/db_bridge.py` runs SQL against live Supabase over **HTTPS:443** (Postgres
  ports 5432/6543 stay firewalled in sandbox/Codespaces). Verified live: **PostgreSQL 17.6**,
  `current_user=postgres` (full SQL access).
- **Usage**: `set -a && . .devcontainer/secrets.env && set +a && python3 scripts/db_bridge.py "SELECT ...;"`
- **Config (env only)**: `SUPABASE_EDGE_FUNCTION_URL` (public, default in script) +
  `SUPABASE_EDGE_FUNCTION_KEY` (secret — lives in git-ignored `.devcontainer/secrets.env`,
  injected by `supervisor.sh`; **never** committed to any tracked file).
- **Scope**: read / diagnose / manual DDL only — NOT for live-path writes (`customer_messages`/
  `admin_messages` stay app-owned per D-006). Full doctrine: CLAUDE.md §6.83.

## AI Gateway (live 2026-05-09)
- **Client**: `SimpleAIClient` (`app/core/gateway/simple_client.py`)
- **Primary model**: `nvidia/nemotron-3-super-120b-a12b:free`
- **Fallback models**: `google/gemini-2.0-flash-exp:free`, `qwen/qwen3-coder:free`, `kwaipilot/kat-coder-pro:free`, `microsoft/phi-3-mini-128k-instruct:free`, `meta-llama/llama-3.2-11b-vision-instruct:free`

## Start Commands
```bash
# Backend (requires DATABASE_URL)
DATABASE_URL="..." OPENROUTER_API_KEY="..." uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (supervisor.sh overrides to port 3000)
cd frontend && npm run dev -- --port 3000

# Tests
DATABASE_URL="sqlite+aiosqlite:///:memory:" SECRET_KEY="test-secret-key-for-ci-pipeline-secure-length" \
ENVIRONMENT="testing" LLM_MOCK_MODE="1" SUPABASE_URL="https://dummy.supabase.co" SUPABASE_ROLE_KEY="dummy" \
pytest tests/ -v

# Lint
ruff check . && ruff format --check .
```

## Request Flow (verified live 2026-05-09)
```
Student browser
  └─ Next.js (:3000)
        └─ /api/* → rewrites → FastAPI :8000
              └─ ObservabilityMiddleware ← traces every HTTP request
                    └─ /api/chat/ws (WebSocket)
                          │  Auth: ?token= query param
                          │  ⚠️ WS layer NOT traced per-frame (ISS-005)
                          │
                          └─ OrchestratorClient.chat_with_agent()
                                │
                                ├─ [1] File intelligence → SKIP (no files)
                                ├─ [2] Exercise retrieval → SKIP (no BAC match)
                                ├─ [3] HTTP → orchestrator:8006 → ConnectError (DORMANT)
                                └─ [4] LangGraph local_graph.py ← DE-FACTO HANDLER
                                          supervisor_node (intent: educational/chat/general)
                                          └─ chat_node → OpenRouter API → response
```

## 31 Database Tables (verified live 2026-05-21)
```
Auth:        users, roles, permissions, user_roles, role_permissions, refresh_tokens, password_resets
Audit:       audit_log, audit_logs
Chat:        customer_conversations, customer_messages, admin_conversations, admin_messages
Missions:    missions, mission_plans, tasks, mission_events, mission_outbox
AI:          prompt_templates, generated_prompts, knowledge_nodes, knowledge_edges
Content:     content_items, content_search, content_solutions
Checkpoints: checkpoints, checkpoint_blobs, checkpoint_migrations, checkpoint_writes
BKT:         student_bkt_analytics
Planning:    plan
System:      alembic_version
```

## Content Storage Architecture (verified live 2026-05-21)

### محتوى التمارين — مكانان
التمارين مخزّنة في **مكانين**: ملفات Markdown في المستودع (المصدر الأصلي) وجدول
`content_items` في Supabase (نسخة runtime للاستعلام).

**ملفات المستودع (المصدر):**
- `knowledge_base/` — 2 ملف (BAC 2016 دوال عددية + BAC 2024 رياضيات)
- `data/knowledge/` — 2 ملف (BAC 2015 أسية + BAC 2024 احتمالات)
- `content/ar/math/` — 1 ملف (BAC 2024 علوم تجريبية)

**قاعدة البيانات (runtime):**
- `content_items` — 3 سجلات (كلها نفس تمرين الاحتمالات BAC 2024 بصيغ مختلفة)
- `content_solutions` — 2 سجلات (solution_md فقط، steps_json=NULL، verified_by_human=False)
- `content_search` — 1 سجل فقط له embedding (باقي التمارين غير قابلة للبحث الدلالي)
- `knowledge_nodes` — 16 عقدة لتمرين واحد، بدون foreign key لـ content_items

### مشاكل التخزين الحالية (D-078 — 2026-05-21)
1. **تكرار**: نفس تمرين BAC 2024 موجود 3 مرات بـ IDs مختلفة
2. **عدم اتساق metadata**: `subject` يأخذ قيم `mathematics`/`Mathematics`/`general` بدون ENUM
3. **steps_json فارغ**: الحل موجود كـ Markdown خام فقط، غير مُهيكل
4. **embeddings ناقصة**: 2 من 3 تمارين بدون embedding → لا يمكن البحث الدلالي فيها
5. **knowledge_nodes منفصلة**: لا foreign key يربطها بـ content_items

### النمط الصحيح (غير مكتمل بعد)
الملف يُكتب مرة واحدة في المستودع → يُحوَّل تلقائياً لـ DB عبر GitHub Actions →
النظام يقرأ من DB فقط. هذا النمط موجود في البنية لكن التطبيق جزئي (3 تمارين فقط).

## Docker Compose — الدور الحقيقي (verified 2026-05-21, D-079)

### الواقع: Distributed Monolith لا Microservices حقيقية

المشروع يعمل كـ **monolith داخل container واحد** رغم وجود ملفات docker-compose متعددة:

```
ما هو مكتوب:                    ما يعمل فعلاً:
كل خدمة في container مستقل  →  supervisor.sh يُشغِّل كل uvicorn processes
مع DB خاصة بها                  داخل container واحد (web) مع Supabase مشتركة
```

### ملفات docker-compose وحالتها

| الملف | الدور | يُستخدم؟ |
|-------|-------|----------|
| `.devcontainer/docker-compose.host.yml` | يبني container واحد (`web`) — supervisor.sh يعمل بداخله | ✅ نعم |
| `docker-compose.yml` (478 سطر) | stack كامل: 9 خدمات + 8 Postgres منفصلة + Redis | ❌ نظري فقط |
| `docker-compose.step3.yml` | orchestrator مع postgres+redis مستقلين | ❌ للتطوير خارج Codespaces |
| `docker-compose.step6.yml` | orchestrator + user-service + planning-agent | ❌ للتطوير خارج Codespaces |
| `docker-compose.legacy.yml` | نسخة قديمة بـ `profiles: ["legacy"]` | ❌ مهجور |
| `observability/docker-compose.observability.yml` | Grafana + Prometheus | ❌ يعملان مباشرةً بدون Docker |

### المشاكل المعمارية

1. **لا عزل حقيقي**: كل الخدمات تشترك في نفس process space + filesystem + Python interpreter
2. **قاعدة بيانات واحدة مشتركة**: `docker-compose.yml` يعرّف `postgres-planning/memory/user/...` لكن كلها تستخدم Supabase واحدة فعلياً
3. **`docker-compose.yml` وهمي**: 478 سطر لبنية لم تُختبر — تكلفة صيانة بدون فائدة
4. **Distributed Monolith**: أسوأ من الاثنين — تعقيد microservices بدون عزلها

### التوصية (D-079)
الأولوية الحالية = المحتوى التعليمي لا البنية التحتية. الخيار الأكثر واقعية:
- **ابقَ على supervisor.sh** كمسار التشغيل الوحيد
- **احذف أو أرشف** `docker-compose.yml` الوهمي لتقليل تكلفة الصيانة
- **لا تُضف خدمات جديدة** بـ docker-compose حتى يكون هناك حاجة scaling حقيقية

## Critical environment facts
- `DATABASE_URL` or `APP_DATABASE_URL` **must** be set — app crashes without it
- `OPENROUTER_API_KEY` **must** be set — all LLM calls fail without it (reasoning-agent falls back to mock)
- `TAVILY_API_KEY` — optional; research-agent starts without it (`tavily_available=false`)
- `OTEL_EXPORTER_OTLP_ENDPOINT=http` is currently set but is an **invalid URL** — OTEL is a no-op
- `REDIS_URL` is **not set** — cache falls back to `InMemoryCache`
- `ORCHESTRATOR_SERVICE_URL` is **not set** — orchestrator HTTP path always fails → fallback chain runs
- `ORCHESTRATOR_DATABASE_URL` — must be `postgresql+asyncpg://` on port 5432 (not 6543 PgBouncer)
- `PLANNING_DATABASE_URL` — not set → planning-agent uses `sqlite+aiosqlite:///:memory:` (ISS-043-C)

## Live Service Status (verified 2026-05-11)
All 8 microservices ACTIVE. Skills Pipeline in `fallback` mode (LLM keys not in process env at startup).
To activate full pipeline: export `OPENROUTER_API_KEY` + `TAVILY_API_KEY` before supervisor.sh runs.

## API Contract Quick Reference
| Endpoint | Required Fields | Auth |
|----------|----------------|------|
| `POST /agent/chat` (8006) | `question`, integer `user_id` | `Authorization: Bearer <JWT>` |
| `POST /chat/message` (8003) | `question` | None |
| `POST /plans` (8002) | `query` | `X-Service-Token: <JWT>` |
| `POST /execute` (8007) | `query`, `caller_id`, `action` | None |
| `POST /execute` (8008) | `query`, `caller_id`, `action` | None |
| `POST /compose` (8006) | `query` | None |
| `POST /retrieve` (8009) | `question` | None |
