# CogniForge — Project Context
> Last updated: 2026-05-06 | Re-verified on branch: `claude/architecture-rescue-diagnostic-wUfbE` (third audit).
> **Runtime capability status:** see `.memory/runtime_truth.md` (authoritative — corrections in rows 12, 21; new rows 26, 27).
> **Diagnostic snapshots:**
>   - `.memory/diagnostic_2026_05_06.md` — second audit (`claude/diagnostic-system-architecture-aRSuW`).
>   - `.memory/diagnostic_2026_05_06_rescue.md` — third audit (this branch); architectural rescue diagnostic + CI gap (ISS-025) + loaded-not-invoked classification (ISS-026) + markdown debt inventory.
> **CI gates today:** ruff/contracts/guardrails/tests + structure-validation + new `doc-integrity` workflow. Open gaps tracked in ISS-025.

## Identity
- **Name**: NAAS-Agentic-Core (CogniForge)
- **Purpose**: AI tutor for Algerian high-school students preparing for the Baccalaureate exam
- **Languages**: Arabic (MSA) / French / Darija — all three simultaneously
- **Subjects**: Math, Physics, Chemistry, History, Geography, Languages
- **Supported environments**: GitHub Codespaces (primary dev) **and** Replit — the app is environment-agnostic. In both, microservices are DORMANT by default.
- **Codespaces**: `.devcontainer/devcontainer.json` → `docker-compose.host.yml` (web container only) → `supervisor.sh` launches `uvicorn app.main:app` + Next.js on port **3000**
- **Replit**: `package.json` script runs Next.js on port **5000**; backend started manually with uvicorn on 8000
- **Microservices wake-up** (either environment): `docker compose -f docker-compose.yml up -d`

## Stack
| Layer | Tech | Port |
|-------|------|------|
| Frontend | Next.js 15 | **3000** (Codespaces) / **5000** (Replit) |
| Backend | FastAPI (Python 3.12) | 8000 |
| AI Graph | LangGraph 1.1.10 | in-process |
| DB | PostgreSQL (Supabase) + aiosqlite (tests) | 5432 |
| LLM | OpenRouter (primary) → OpenAI (fallback) | cloud |
| Cache | Redis (optional, falls back to memory) | 6379 |
| Tracing | UnifiedObservabilityService (in-process) | — |

## Start Commands
```bash
# Backend
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm run dev

# Tests
DATABASE_URL="sqlite+aiosqlite:///:memory:" SECRET_KEY="test-secret-key-for-ci-pipeline-secure-length" \
ENVIRONMENT="testing" LLM_MOCK_MODE="1" SUPABASE_URL="https://dummy.supabase.co" SUPABASE_ROLE_KEY="dummy" \
.venv/bin/pytest tests/ -v

# Lint
ruff check . && isort --check-only .
```

## Request Flow (MEASURED — not assumed)
```
Student browser
  └─ Next.js  (:3000 Codespaces / :5000 Replit)
        └─ /api/* → rewrites → FastAPI :8000
              └─ ObservabilityMiddleware  ← traces every HTTP request (W3C Trace Context)
                    └─ /api/chat/ws  (WebSocket)
                          │  WS connect: 26ms (measured)
                          │  Auth: ?token= query param in dev mode
                          │  ⚠️ WS layer NOT traced (ISS-005)
                          │
                          └─ OrchestratorClient.chat_with_agent()
                                span: orchestrator.chat_with_agent (1506ms measured when all fail)
                                │
                                ├─ [1] File intelligence (0.1ms → SKIP if no files)
                                ├─ [2] Exercise retrieval (0.0ms → SKIP if no BAC match)
                                ├─ [3] HTTP → orchestrator:8006 → ConnectError (DORMANT in Codespaces)
                                └─ [4] LangGraph local_graph.py  ← DE-FACTO HANDLER (PARTIAL — fallback only; runs every turn because [3] always ConnectErrors in default Codespaces)
                                          span: langgraph.run (757ms measured)
                                          │
                                          ├─ supervisor_node  (0.0ms, intent=educational)
                                          └─ chat_node (747ms)
                                                └─ OpenRouter free models → 403 ❌ BROKEN
                                                   "All models exhausted. Engaging Safety Net."
```

## 18 Database Tables
```
Auth:     users, roles, permissions, user_roles, role_permissions, refresh_tokens
Audit:    audit_log
Chat:     customer_conversations, customer_messages, admin_conversations
Missions: missions, mission_plans, tasks, mission_events
AI:       prompt_templates, generated_prompts, knowledge_nodes, knowledge_edges
```

## Environment Variables (Real Status)
Sourced from Codespaces secrets, forwarded via `.devcontainer/devcontainer.json` → `remoteEnv`.

| Variable | Status | Notes |
|----------|--------|-------|
| APP_DATABASE_URL | ✅ Codespaces secret | Supabase PostgreSQL |
| SECRET_KEY | ⚠️ Ephemeral if unset | Restart = all users logged out |
| OPENROUTER_API_KEY | ✅ Codespaces secret | Works — nvidia/nemotron-3-super-120b-a12b:free confirmed |
| OPENAI_API_KEY | ❌ Not set | Fallback unavailable |
| ENVIRONMENT | ✅ development | Set via devcontainer.json |
| ORCHESTRATOR_SERVICE_URL | ❌ Not set | Always ConnectError in default devcontainer (microservices not started) |
| REDIS_URL | ❌ Not set | Falls back to in-memory |
| OTEL_EXPORTER_OTLP_ENDPOINT | ❌ Not set | Telemetry bridge tries DNS → fails every request |
| OPENROUTER_SITE_URL | ⚠️ Optional | Set to Codespaces public URL if OpenRouter rejects with `Host not in allowlist` |

## Python Environment
- Python 3.12 (`.python-version`)
- Virtual env: `.venv/` (created with `uv venv`)
- Test runner: `.venv/bin/pytest` (NOT the system pytest which is 3.11)
- Backend runner: `.venv/bin/uvicorn` (NOT system uvicorn)
- 1658 tests collected total

## Measured Performance (2026-05-04 live test)
| Operation | Time | Status |
|-----------|------|--------|
| Server health check | 7ms | ✅ |
| WS connect | 26ms | ✅ |
| User register | 125ms | ✅ |
| User login | 75ms | ✅ (but full_name=null) |
| LangGraph full run | 757ms | ✅ (but LLM fails inside) |
| Orchestrator (all paths fail) | 1506ms | ❌ |
| p50 response time | 3.5ms | ✅ |
| p95 response time | 1057ms | ⚠️ |
| Error rate | 7.69% | ⚠️ |

## Known Broken in Current Environment
1. **Chat**: All OpenRouter free models return 403 — NO chat response reaches the user
2. ~~**Dual-write**~~: RESOLVED in `claude/fix-persistence-consolidate-8X8LT` — Monolith is sole writer (D-006); Orchestrator persists only via `compatibility_facade=True` + `persisted: true` handshake
3. **Context identity**: conversation_id / thread_id can diverge across fallback paths (ISS-019)
4. ~~**Terminal signal**~~: RESOLVED — `_emit_terminal_frames()` guarantees one terminal frame per turn; `normalize_streaming_event` passes control events through
5. **Streaming**: Graph uses `ainvoke` → blocks instead of token-by-token (ISS-023)
6. **Telemetry export**: TelemetryBridge DNS failures on every request (ISS-008)
7. **Auth microservices**: DNS failures on every login/register (ISS-009)
8. **/performance endpoint**: Pydantic schema mismatch → 500 error (ISS-012)
9. **full_name**: Always null in login response (ISS-003)

## Architectural Debt Summary (Session 2026-05-05)
Seven core architectural issues documented in `.memory/issues.md` (ISS-014–ISS-020):
- ISS-014: Dual-write (CRITICAL — fix first)
- ISS-015: Non-unified save authority
- ISS-016: Unsafe fallback path
- ISS-017: Terminal signal corruption
- ISS-018: Architectural split-brain (Monolith/Microservice hybrid unresolved)
- ISS-019: Context identity fragmentation
- ISS-020: Fragile MemorySaver checkpointer
Three quality issues: ISS-021 (zombies), ISS-022 (pipeline split), ISS-023 (streaming blocks)


## Session Note 2026-05-06
- Hardened admin chat stream error payloads to avoid leaking internal exception strings to clients.

## Documentation Source of Truth
- التشغيل اليومي: `.memory/`
- الملخص التنفيذي/السياسات: `CLAUDE.md`
- تم حذف الأرشيفات القديمة في `docs/archive/` لتجنب تضارب المعرفة.



## Educational vs General Chat (Operational Contract)
- **Educational Path**: objective-driven tutoring flow (diagnose -> explain -> verify -> next-step), should prefer retrieval + evaluation signals and explicit learner-state updates.
- **General Chat Path**: open conversation flow, optimized for latency and usability; retrieval is optional.
- **Routing Principle**: the supervisor/router should classify intent early and choose state schema + tool budget accordingly.
- **API-first impact**: each capability (auth, retrieval, orchestration, analytics) should remain independently deployable behind explicit HTTP/gRPC/event contracts.
