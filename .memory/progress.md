# Progress — What Has Been Done
> Last updated: 2026-05-23 | Branch: `feat/math-explanation-generative-ui`

---

## ✅ Session: 2026-05-23 — D-080: Math Pipeline enrich_node + MathExplanationCard Generative UI

**Branch**: `feat/math-explanation-generative-ui`
**Goal**: تفعيل المفاتيح الحقيقية + بناء نظام Generative UI للشرح الرياضي العميق

### ما تم إنجازه

#### 1. تفعيل جميع الخدمات بالمفاتيح الحقيقية
- إنشاء `.devcontainer/secrets.env` بـ OPENROUTER_API_KEY + TAVILY_API_KEY + DATABASE_URL
- إعادة تشغيل 8/8 خدمات: planning (PostgreSQL حقيقي)، reasoning (openrouter)، research (tavily=true)، orchestrator (graph_ready)
- التحقق الحي: Skills Pipeline `mode=full` ✅

#### 2. إضافة enrich_node (Node 4) إلى Math Pipeline
- **الملف**: `microservices/conversation_service/src/math_pipeline.py`
- `enrich_node`: deterministic، لا LLM، يُحلِّل النص ويبني `ui_component`
- `_build_ui_component()`: يستخرج الخطوات + الحدس + الاستعارة البصرية + التلميح
- `visual_metaphors`: 10 استعارات بصرية (مشتق=عدّاد السرعة، تكامل=ملء حوض، نهاية=الاقتراب من جدار...)
- `MathPipelineState` + `invoke_math_pipeline` يُعيدان `ui_component: dict | None`
- Topology: `classify → solve → normalize → enrich → END`

#### 3. تمرير ui_component عبر الـ stack الكامل
- `conversation_graph.py`: `ConversationState.ui_component` + `invoke_graph` يُعيده
- `main.py` (conversation-service): `ChatResponse.ui_component` + WebSocket payload
- `customer_chat.py` (monolith): `_try_build_math_ui_component()` تُحقن في `assistant_final`

#### 4. MathExplanationCard — مكوّن Generative UI جديد
- **الملف**: `frontend/app/components/generative/MathExplanationCard.jsx`
- 11 نوع رياضي، كل نوع له لون + أيقونة مختلفة
- مكوّنات: `StepCard` (قابل للطي)، `VisualMetaphor`، `HintBadge`
- يظهر بعد النص على `isComplete` فقط — لا streaming flicker
- مُسجَّل في `GenerativeUIRenderer` كـ `math_explanation_card`

#### 5. تحديث Frontend
- `GenerativeUIRenderer.jsx`: تسجيل `math_explanation_card`
- `ChatInterface.jsx`: عرض `ui_component` بعد النص (لا بدلاً منه)
- `useAgentSocket.js`: استخراج `ui_component` من `assistant_final` payload

#### 6. تحديث الذاكرة
- `CLAUDE.md`: D-080 invariants مُضافة
- `.memory/runtime_truth.md`: D-080 live verification
- `.memory/decisions.md`: D-080 architectural decision
- `.memory/progress.md`: هذا السجل

### نتائج التحقق الحي
- 3 أنواع رياضية مختبرة: derivative ✅، integral ✅، probability ✅
- Non-math fallback: `ui_component=None` ✅
- 820 اختباراً ✅ · ruff clean ✅

### Files Changed
- `microservices/conversation_service/src/math_pipeline.py`
- `microservices/conversation_service/src/conversation_graph.py`
- `microservices/conversation_service/main.py`
- `app/api/routers/customer_chat.py`
- `frontend/app/components/generative/MathExplanationCard.jsx` (جديد)
- `frontend/app/components/generative/GenerativeUIRenderer.jsx`
- `frontend/app/components/ChatInterface.jsx`
- `frontend/app/hooks/useAgentSocket.js`
- `CLAUDE.md`
- `.devcontainer/secrets.env` (جديد — git-ignored)

---

---

## ✅ Session: 2026-05-13 — ISS-052: BAC 2016 Ex4 Ultra Display + Semantic Retrieval + Streaming

**Branch**: `feat/bac2016-ex4-ultra-display-streaming`
**Goal**: إصلاح استدعاء تمرين الدوال العددية 2016 + تطوير العرض + تحسين streaming

### ما تم إنجازه

#### 1. إصلاح نظام الاسترجاع الدلالي (exercise_retrieval.py)
- **إضافة أنماط جلب جديدة**: `اعطني`, `هات`, `هاتلي`, `أحتاج`, `نص تمرين`, `أظهر`, `عرض`
- **إضافة أنماط دلالية**: `g(x)`, `f(x)`, `الدالة g`, `2016 دوال`, `دوال 2016`
- **إضافة منطق دلالي**: فعل جلب + موضوع رياضي = طلب محتوى (بدون كلمة "تمرين" صريحة)
- **نتيجة**: 10/10 طرق استدعاء تعمل بشكل صحيح

#### 2. تطوير ChatInterface.jsx
- **مكوّن ExamBadge**: شارة "ورقة امتحان رسمية" تظهر تلقائياً عند استرجاع تمرين
- **مكوّن TypingIndicator**: ثلاث نقاط متحركة أثناء انتظار الرد
- **مكوّن MessageBubble**: رسائل منفصلة مع حالة streaming واضحة
- **شاشة الترحيب**: أزرار اقتراحات سريعة لاستدعاء التمارين
- **textarea ذكي**: يتمدد تلقائياً مع المحتوى
- **زر العودة للأسفل**: يظهر عند التمرير للأعلى

#### 3. تطوير globals.css — CSS فائق الجودة
- **KaTeX**: تنسيق احترافي للرموز الرياضية (display + inline)
- **جداول رياضية**: `.math-table-wrapper` + `.math-table` بتصميم احترافي
- **بطاقة الامتحان**: `.exam-content` + `.exam-badge` بتصميم فاخر
- **Streaming cursor**: مؤشر متحرك أثناء البث
- **Typing indicator**: ثلاث نقاط متحركة
- **Quick prompts**: أزرار اقتراحات سريعة
- **RTL كامل**: دعم كامل للعربية من اليمين لليسار

#### 4. تطوير streaming البث (orchestrator_client.py)
- **استراتيجية ذكية**: أسطر فارغة فورية، عناوين كوحدة، LaTeX محمي، نص word-by-word
- **تأخيرات ذكية**: 6ms للكلمات القصيرة، 11ms للعادية، 20ms للرموز الرياضية، 25ms للمعادلات
- **حماية LaTeX**: معادلات `$$...$$` تُرسَل كوحدة واحدة لا تُكسَر

#### 5. تحديث skill bac-exercise-explanation.md
- فهرس التمارين المتاحة
- جميع طرق الاستدعاء المدعومة
- منهجية الشرح المفصل
- قواعد LaTeX الإلزامية
- ملخص نتائج تمرين 2016

### Files Changed
- `app/services/capabilities/exercise_retrieval.py` — إضافة أنماط دلالية
- `app/infrastructure/clients/orchestrator_client.py` — streaming ذكي
- `frontend/app/components/ChatInterface.jsx` — إعادة كتابة كاملة
- `frontend/app/globals.css` — CSS فائق الجودة
- `docs/ai_skills/bac-exercise-explanation.md` — تحديث شامل

---

---

## ✅ Session: 2026-05-13 — BAC 2016 Numerical Functions + Knowledge Index Overhaul

**Branch**: `feat/bac2016-numerical-functions-skill`
**Goal**: إضافة تمرين الدوال العددية 2016 الدورة الأولى + إصلاح نظام استدعاء التمارين

### ما تم إنجازه

#### 1. ملف تمرين الدوال العددية 2016 الدورة الأولى
- **الملف**: `knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md`
- **المحتوى**: نص التمرين الكامل + الإجابة النموذجية المفصلة خطوة بخطوة
- **الإجابة النموذجية** تشمل: النهايات، جداول التغيرات، إثبات f'(x)=-g(x)، نقطتا الانعطاف، المستقيم المقارب، التكامل، حساب A(λ)
- **ملاحظة تاريخية**: 2016 هي السنة الوحيدة بدورتين في تاريخ بكالوريا الجزائر

#### 2. فهرس قاعدة المعرفة المركزي
- **الملف الجديد**: `app/services/capabilities/knowledge_index.py`
- **المبدأ**: Data as Code — كل تمرين له سجل بيانات تصريحي (سنة + دورة + موضوع + رقم + موضوع رياضي + وسوم)
- **الدوال**: `search_exercises()` (بحث متعدد المعايير) + `find_best_match()` (بحث بالوسوم)

#### 3. إصلاح exercise_retrieval.py
- **إضافة**: استيراد `knowledge_index` + استخراج المعايير من النص (سنة، دورة، موضوع، رقم التمرين)
- **إضافة**: `_find_matching_entry()` — يبحث في الفهرس بدلاً من إرجاع ملف ثابت
- **إضافة**: `load_exercise_content()` — يحمِّل محتوى الملف المحدد
- **إضافة**: أنماط جديدة: دوال عددية، أعداد مركبة، الدورة الأولى/الثانية، التمرين الرابع

#### 4. مهارة شرح تمارين البكالوريا
- **الملف الجديد**: `docs/ai_skills/bac-exercise-explanation.md`
- **يغطي**: قاعدة 2016 الاستثنائية، فهرس التمارين، منهجية الشرح، قواعد LaTeX، نموذج الرد المثالي

#### 5. تحديث AGENTS.md
- **إضافة**: trigger rule جديد لـ `bac-exercise-explanation.md`
- **إضافة**: سجل المهارة في Skill Index

### Files Changed
- `knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md` — جديد
- `app/services/capabilities/knowledge_index.py` — جديد
- `app/services/capabilities/exercise_retrieval.py` — محدَّث
- `docs/ai_skills/bac-exercise-explanation.md` — جديد
- `AGENTS.md` — محدَّث (skill trigger + index)
- `.memory/progress.md` — هذا الملف

---

---

## ✅ Session: 2026-05-11 — D-045: End-to-End User Routing via Microservices

**Goal**: توصيل الخدمات المصغرة لتجيب على المستخدمين فعلياً (وليس فقط تشغيلها).

### Live Diagnosis Results
- جميع الخدمات كانت ميتة (لا uvicorn يعمل) — بيئة جديدة بدون secrets.env
- أُنشئ `.devcontainer/secrets.env` بالمفاتيح الحقيقية
- شُغِّلت 8 خدمات بالتسلسل الصحيح مع المتغيرات البيئية الصحيحة

### Fixes Applied
| Issue | Fix |
|-------|-----|
| ISS-048 | `supervisor.sh`: `ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR=true` مضاف |
| ISS-049 | `prometheus_client` مثبَّت + مضاف لـ `conversation_service/requirements.txt` |
| ISS-050 | Chat routing مُثبَّت حياً: WS → Monolith → Orchestrator → Skills → LLM |

### Live Evidence
```
POST /compose → pipeline_mode="full" | skills_active=["planning","research","reasoning"] | 28.5s
WS /api/chat/ws → events: [conversation_init, assistant_delta×6, assistant_final]
Answer: "قانون نيوتن الثاني ينص على أن القوة (F) = كتلة (m) × تسارع (a)..."
Prometheus: 12/12 UP
Grafana: 17 dashboards at :3001
```

### Files Changed
- `.devcontainer/supervisor.sh` — `ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR=true`
- `microservices/conversation_service/requirements.txt` — `prometheus_client>=0.20.0`
- `.memory/issues.md` — ISS-048/049/050 documented
- `.memory/runtime_truth.md` — D-045 results
- `.memory/progress.md` — this entry
- `CLAUDE.md` — D-045 entry

---

## ✅ Session: 2026-05-11 — Full Stack Live Verification + Surgical Fixes (D-044)

**Branch**: `feat/live-verification-d044-surgical-fixes`
**Mode**: Live verification with real secrets — all 8 services confirmed ACTIVE
**Verified**: ruff clean | 12/12 Prometheus targets UP | Skills Pipeline `mode: full` | Grafana 17 dashboards

### ما تم إنجازه

#### 1. تشغيل جميع الخدمات المصغرة بالأسرار الحقيقية
- 8 خدمات تعمل: `:8000` (main) + `:8001` (user) + `:8002` (planning) + `:8003` (conversation) + `:8006` (orchestrator) + `:8007` (research) + `:8008` (reasoning) + `:8009` (content-retrieval)
- `secrets.env` أُنشئ بالأسرار الحقيقية (git-ignored)
- `.env` يحتوي الأسرار للـ pydantic-settings

#### 2. إصلاح reasoning-agent (ISS-047 — OpenRouter 402)
- **السبب**: `gpt-4o` يطلب 16384 token — الرصيد لا يكفي
- **الإصلاح**: `DEFAULT_MODEL = "openai/gpt-4o-mini"` + `MAX_TOKENS = 1024` في `config.py` + `max_tokens` في `ai_service.py`

#### 3. تفعيل content-retrieval-skill (:8009)
- كانت DOWN في Prometheus — أُطلقت كـ uvicorn process
- الآن: 12/12 Prometheus targets UP

#### 4. Skills Pipeline في وضع `full`
- `pipeline_mode: full | skills_active: ['planning', 'research', 'reasoning']`
- مدة الاستجابة: ~23 ثانية (MCTS + LLM حقيقي)

#### 5. إصلاحات ruff (113 خطأ → 0)
- `ruff check . --fix --unsafe-fixes` أصلح 107 خطأ تلقائياً
- إصلاحات يدوية: `ClassVar`, `noqa` comments, lambda args, N812, E741

#### 6. إصلاحات الاختبارات (10 فشل → 0)
- `test_chat_event_protocol_error_contract_integration.py`: إصلاح mock DB session (sync vs async methods)
- `test_conversation_service_envelope.py`: إعادة كتابة كاملة لتطابق عقد conversation-service الفعلي
- `test_settings_base.py`: إضافة `model_config = SettingsConfigDict(env_file=None)` + `monkeypatch`
- `test_db_factory_guardrails.py`: إضافة `monkeypatch.delenv` لعزل env vars
- `test_dual_write_immunity.py`: `pytest_asyncio.fixture` + `expire_on_commit=False` + `full_name` field
- `chat_persistence.py`: إضافة `await self.db.refresh(message)` بعد commit

#### 7. إصلاح GitHub Actions
- `ci.yml` يمر بنجاح: lint ✅ | contracts ✅ | guardrails ✅ | skills-structural ✅
- 12 Prometheus jobs | 17 Grafana dashboards

---

## ✅ Session: 2026-05-11 — Microservices Step 12: Conversation Service Live (الخطوة الثانية عشرة)

**Branch**: `feat/microservices-step12-conversation-service`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 117 tests pass | ruff clean | LangGraph StateGraph compiles | fallback mode works without LLM

### الخطوة الانتقالية المختارة (D-042)
تفعيل `conversation-service` كـ Skill احترافية مستقلة على `:8003` — الخدمة السادسة في Skills Architecture. تُحوِّل إدارة المحادثات من stub بسيط إلى Skill حقيقية بـ LangGraph StateGraph + Prometheus metrics + WebSocket.

### الملفات المُنشأة/المُعدَّلة

#### 1. `microservices/conversation_service/prom_metrics.py` — جديد كلياً
- `CollectorRegistry` مستقل — لا يتعارض مع microservices أخرى
- 11 مقياساً: `cogniforge_conversation_requests_total`, `cogniforge_conversation_request_duration_seconds`, `cogniforge_conversation_active_connections`, `cogniforge_conversation_messages_total{direction,route}`, `cogniforge_conversation_sessions_total{route,status}`, `cogniforge_conversation_session_duration_seconds`, `cogniforge_conversation_graph_invocations_total{node,status}`, `cogniforge_conversation_graph_duration_seconds`, `cogniforge_conversation_graph_errors_total{error_type}`, `cogniforge_conversation_db_operations_total`, `cogniforge_conversation_startup_info{step,version,graph_ready,db_ready,ws_enabled}`
- دوال: `record_request()`, `record_ws_connection()`, `record_message()`, `record_session()`, `record_graph_invocation()`, `record_graph_error()`, `record_db_operation()`, `set_startup_info()`, `get_metrics_output()`

#### 2. `microservices/conversation_service/src/conversation_graph.py` — جديد كلياً
- `ConversationState` TypedDict: question, intent, history, response, thread_id, correlation_id, error
- `_classify_intent()` — deterministic (no LLM): educational | chat | general
- `_build_fallback_response()` — يعمل بدون OPENROUTER_API_KEY
- `intent_node` + `response_node` — كل node يُسجِّل في Prometheus
- `asyncio.wait_for(..., timeout=30.0)` — timeout guard إلزامي
- Topology: `START → intent_node → response_node → END`
- `get_conversation_graph()` — lazy singleton
- `invoke_graph()` — public API للـ main.py

#### 3. `microservices/conversation_service/main.py` — إعادة كتابة كاملة (v2.0.0)
- lifespan: DB check + graph warmup (timeout 15s) + `set_startup_info()`
- `GET /health` → `HealthResponse{status, service, version, step="12", graph_ready, ws_enabled}`
- `GET /metrics` → Prometheus text format
- `POST /chat/message` → `ChatResponse{response, intent, thread_id, correlation_id, step="12"}`
- `WS /chat/ws` → customer WebSocket (120s timeout per message)
- `WS /admin/chat/ws` → admin WebSocket
- Legacy: `ANY /api/chat/{path}` → 200 + `new_endpoint="/chat/message"`

#### 4. `microservices/conversation_service/database.py` — إعادة كتابة
- `_normalize_db_url()` — يُحوِّل `postgresql://` → `postgresql+asyncpg://`, يُزيل `sslmode`
- `get_engine()` — lazy singleton (لا يتصل عند import)
- `statement_cache_size=0` لـ asyncpg (PgBouncer compatibility)

#### 5. `microservices/conversation_service/requirements.txt` — تحديث
- أُضيف: `langgraph`, `prometheus-client>=0.20.0`, `sqlalchemy>=2.0.0`, `aiosqlite>=0.19.0`, `httpx>=0.27.0`

#### 6. `.devcontainer/supervisor.sh` — STEP 4J
- `launch_conversation_service()` — يُطلق uvicorn على :8003
- URL conversion: `postgresql://` → `postgresql+asyncpg://` + port 6543→5432
- يعمل بدون OPENROUTER_API_KEY (fallback mode)

#### 7. `observability/native/prometheus.yml` — scrape target جديد
- `job_name: conversation-service` → `localhost:8003` مع `step="12"`

#### 8. `observability/grafana/dashboards/140-microservices-step12-conversation-service.json`
- 15 panels | UID: `cogniforge-ms-step12-conversation` | refresh: 10s
- Row 1: Startup Info + Active WS + Total Messages + Graph Invocations + P95 Latency
- Row 2: HTTP Request Rate + WS Sessions Rate
- Row 3: LangGraph Node Invocations + Duration P50/P95/P99
- Row 4: Messages Rate (Inbound/Outbound) + Graph Errors by Type
- Row 5: Session Duration P50/P95 + DB Operations
- Row 6: Health Matrix (Steps 4-12) + Step 12 Guide

#### 9. `.ona/automations.yaml` — service + tasks
- service `conversation-service` — start/ready/stop
- task `verify-step12-conversation-service` — تحقق شامل حي
- task `restart-conversation-service` — إعادة تشغيل يدوي
- task `run-step12-tests` — 117 اختبار

#### 10. `.github/workflows/microservices-step12-conversation-service.yml` — CI gate
- 7 jobs: static-checks / metrics-gate / graph-gate / lint / step12-tests / regression-steps-4-11 / pr-summary

#### 11. `tests/microservices/conversation_service/test_step12_conversation_service.py` — 117 اختبار
- C1: prom_metrics.py — 11 مقياس + دوال (20 اختبار)
- C2: conversation_graph.py — StateGraph + nodes + fallback (22 اختبار)
- C3: main.py — endpoints (18 اختبار)
- C4: database.py — URL normalization (8 اختبار)
- C5: prometheus.yml (4 اختبار)
- C6: Grafana dashboard (5 اختبار)
- C7: supervisor.sh STEP 4J (4 اختبار)
- C8: automations.yaml (5 اختبار)
- C9: GitHub Actions (4 اختبار)
- C10: Skill isolation (4 اختبار)

#### 12. `tests/microservices/conversation_service/conftest.py` — جديد
- يُسكِّت `LangChainPendingDeprecationWarning` من LangGraph عند fixture-import

#### 13. `pytest.ini` — تحديث
- أُضيف: `ignore::UserWarning` + `ignore:.*allowed_objects.*`

### الخدمات النشطة بعد Step 12
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Steps 4+9+10) |
| user-service | :8001 | ✅ ACTIVE (Step 5) |
| planning-agent | :8002 | ✅ ACTIVE (Step 6) |
| **conversation-service** | **:8003** | **✅ ACTIVE (Step 12 — جديد)** |
| research-agent | :8007 | ✅ ACTIVE (Step 7) |
| reasoning-agent | :8008 | ✅ ACTIVE (Step 8) |
| content-retrieval-skill | :8009 | ✅ ACTIVE (Step 11) |
| Skills Pipeline | :8006/compose | ✅ ACTIVE (Step 9) |
| Postgres Checkpointer | :8006/checkpointer/status | ✅ ACTIVE (Step 10) |
| Grafana | :3001 | ✅ ACTIVE (14 dashboards) |
| Prometheus | :9090 | ✅ ACTIVE (11 scrape targets) |

### الخطوة التالية (Step 13)
- ربط `conversation-service:8003` بـ `orchestrator-service:8006` — الـ orchestrator يُوجِّه المحادثات إليه
- أو: تفعيل `memory-agent` على `:8009` (يتعارض مع content-retrieval-skill — يحتاج port مختلف)
- أو: تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`)
- أو: إضافة JWT authentication لـ `/chat/message` endpoint

---

---

## ✅ Session: 2026-05-11 — Microservices Step 11: Full Skills Pipeline Live (الخطوة الحادية عشرة)

**Branch**: `feat/microservices-step11-full-skills-live`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 63 tests pass (content-retrieval-skill) | pipeline_mode="full" confirmed live | ISS-038 fixed | ISS-042 fixed

### الخطوة الانتقالية المختارة (D-041)
تحويل Skills Pipeline من "partial" إلى **"full" حقيقي** — جميع الـ 3 Skills (planning+research+reasoning) تعمل بالتوازي الكامل مع LLM حقيقي. وتحويل exercise retrieval من keyword matching إلى **content-retrieval-skill** مستقلة قابلة للقياس.

### الإصلاحات المُنجزة

#### ISS-042 — Service Token + DSPy 3.x + Parallel Pipeline
1. **Service Token**: `_generate_service_token()` في `skills_pipeline.py` — يُولِّد JWT HS256 لـ planning-agent
2. **DSPy 3.x**: `dspy.OpenAI` → `dspy.LM` مع `openrouter/` prefix في `planning_agent/main.py`
3. **Parallel Pipeline**: planning+research+reasoning تعمل بـ `asyncio.gather` الكامل (لا تسلسل)
4. **Timeout**: رُفع من 10s → 55s لاستيعاب LLM latency (~30-45s)
5. **SECRET_KEY**: توحيد `super_secret_key_change_in_production` بين orchestrator و planning-agent
6. **DATABASE_URL**: إضافة `postgresql+asyncpg://` لـ research-agent في restart script

#### Live Verification (2026-05-11)
```
POST /compose → pipeline_mode="full" skills_active=["planning","research","reasoning"] total_ms=32069
GET /metrics → cogniforge_pipeline_invocations_total{mode="full"} 1.0
              cogniforge_pipeline_skill_calls_total{skill="planning",status="success"} 1.0
              cogniforge_pipeline_skill_calls_total{skill="research",status="success"} 1.0
              cogniforge_pipeline_skill_calls_total{skill="reasoning",status="success"} 1.0
```

### content-retrieval-skill (microservices/content_retrieval_skill/)
Skill مستقلة جديدة على :8009 — تُحوِّل exercise retrieval من keyword matching إلى Skill احترافية:
- `src/intent_classifier.py` — مُصنِّف النوايا (explanation/retrieval/unknown) بمنطق ثلاثي المراحل
- `src/retrieval_engine.py` — محرك الاسترجاع من knowledge_base/ مع تسجيل درجة الملاءمة
- `main.py` — FastAPI: POST /retrieve + GET /health + GET /metrics
- `prom_metrics.py` — 7 مقاييس: cogniforge_retrieval_*
- 63 اختباراً: intent_classifier (30) + retrieval_engine (7) + endpoints (16) + ISS-038 regression (13)

#### Live Verification (2026-05-11)
```
GET /health → {"status":"healthy","service":"content-retrieval-skill","step":"11","kb_files":2}
POST /retrieve {"question":"أريد تمرين بكالوريا احتمالات 2024"} → intent="retrieval" total=1
POST /retrieve {"question":"اشرح الجزء أ من هذا التمرين"} → intent="explanation" total=0 ← ISS-038 FIXED
GET /metrics → cogniforge_retrieval_startup_info{step="11"} 1.0
              cogniforge_retrieval_knowledge_base_size 2.0
```

### الملفات المُنشأة/المُعدَّلة
- `microservices/content_retrieval_skill/` — Skill جديدة كاملة (5 ملفات)
- `microservices/orchestrator_service/src/services/skills_pipeline.py` — Service Token + parallel + timeout 55s
- `microservices/orchestrator_service/src/core/config.py` — SECRET_KEY default موحَّد
- `microservices/planning_agent/main.py` — DSPy 3.x fix (dspy.LM)
- `.devcontainer/supervisor.sh` — STEP 4I: content-retrieval-skill + SECRET_KEY fixes
- `observability/native/prometheus.yml` — scrape target :8009 step=11
- `observability/grafana/dashboards/120-microservices-step11-full-skills.json` — 15 panels
- `.github/workflows/microservices-step11-full-skills.yml` — 7 jobs CI gate
- `scripts/restart_all_services.sh` — restart script مع الأسرار الحقيقية
- `tests/microservices/content_retrieval_skill/test_step11_content_retrieval_skill.py` — 63 tests

---

## ✅ Session: 2026-05-11 — Microservices Step 10: Postgres Checkpointer (الخطوة الانتقالية العاشرة)

**Branch**: `feat/microservices-step10-postgres-checkpointer`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 101 tests pass | ruff clean | Live /checkpointer/status ✅ | Live /metrics ✅ | checkpointer_backend="postgres" confirmed

### الخطوة الانتقالية المختارة (D-040 — تنفيذ)
ترقية LangGraph من `MemorySaver` (in-memory، يُفقد عند restart) إلى `AsyncPostgresSaver` (Postgres دائم). هذا يُحوِّل النظام من "محادثة تبدأ من الصفر" إلى **ذاكرة تراكمية حقيقية** — كل thread_id محفوظ في Postgres ويستمر بعد restart.

### ISS-041 — _InstrumentedCheckpointer يجب أن يرث من AsyncPostgresSaver
**المشكلة**: LangGraph يتحقق من `isinstance(checkpointer, BaseCheckpointSaver)` في `ensure_valid_checkpointer()`. Wrapper بسيط (composition) يفشل هذا الفحص.
**الحل**: `_make_instrumented_class(AsyncPostgresSaver)` ينشئ subclass حقيقي يرث من `AsyncPostgresSaver` → يقبله LangGraph تلقائياً.
**التحقق**: `issubclass(_InstrumentedCheckpointer, BaseCheckpointSaver) == True` ✅

### التغييرات المُنجزة

#### 1. `microservices/orchestrator_service/src/core/prom_metrics.py` — 6 مقاييس جديدة
- `cogniforge_checkpointer_writes_total{thread_id_prefix, status}`
- `cogniforge_checkpointer_reads_total{thread_id_prefix, status}` — hit | miss | error
- `cogniforge_checkpointer_duration_seconds{operation}` — write | read | setup
- `cogniforge_checkpointer_errors_total{error_type}` — connection_error | serialization_error | timeout | unknown
- `cogniforge_checkpointer_active_threads` — عدد thread_ids النشطة
- `cogniforge_checkpointer_backend_info{backend, step, pool_size, tables_ready}`
- `cogniforge_orchestrator_startup_info` — أُضيف label `checkpointer_backend`
- دوال: `record_checkpointer_write()`, `record_checkpointer_read()`, `record_checkpointer_error()`, `set_checkpointer_active_threads()`, `set_checkpointer_backend_info()`

#### 2. `microservices/orchestrator_service/src/core/database.py` — إعادة كتابة كاملة
- `_make_instrumented_class(base_class)` — factory ينشئ subclass من AsyncPostgresSaver
- `_InstrumentedCheckpointer` — subclass يُسجِّل كل aput/aget/aget_tuple/setup في Prometheus
- `_build_psycopg_conninfo()` — يُحوِّل postgresql+asyncpg:// إلى postgresql:// لـ psycopg
- `init_db()` — يُهيِّئ AsyncConnectionPool (max_size=5) + AsyncPostgresSaver + setup()
- `get_checkpointer()` — يُعيد _InstrumentedCheckpointer أو None
- Fallback: إذا فشل init → يُسجِّل في Prometheus ولا يوقف الخدمة

#### 3. `microservices/orchestrator_service/src/api/routes.py` — endpoint جديد
- `GET /checkpointer/status` → `{"backend":"postgres","step":"10","active":true,"tables_ready":true,"active_threads":N}`

#### 4. `microservices/orchestrator_service/main.py`
- `set_startup_info(..., checkpointer_backend="postgres"|"memory"|"none")`
- يكتشف backend من `get_checkpointer()` بعد `init_db()`

#### 5. `observability/native/prometheus.yml`
- scrape target جديد: `job_name: postgres-checkpointer` → `localhost:8006/metrics` مع `step="10"`

#### 6. `observability/grafana/dashboards/130-microservices-step10-postgres-checkpointer.json`
- 13 panels | UID: `cogniforge-ms-step10-checkpointer` | refresh: 10s
- Row 1: Backend Info + Active Threads + Total Writes + Total Reads (Hit) + Errors + Startup Backend
- Row 2: Writes Rate (success vs error) + Reads Rate (hit/miss/error)
- Row 3: Duration P50/P95/P99 + Duration P95 by Operation
- Row 4: Errors by Type + Active Threads Over Time
- Row 5: Health Matrix (Steps 4-10) + Step 10 Guide

#### 7. `.github/workflows/microservices-step10-postgres-checkpointer.yml` — CI gate
- 7 jobs: static-checks / routes-gate / infrastructure-gate / lint / step10-tests / regression-steps-4-9 / pr-summary

#### 8. `tests/microservices/orchestrator_service/test_step10_postgres_checkpointer.py` — 101 اختبار
- C1: prom_metrics.py — 6 مقاييس جديدة (19 اختبارات)
- C2: database.py — _InstrumentedCheckpointer + _build_psycopg_conninfo (19 اختبارات)
- C3: routes.py — /checkpointer/status (7 اختبارات)
- C4: main.py — checkpointer_backend (3 اختبارات)
- C5: prometheus.yml — scrape target (4 اختبارات)
- C6: Grafana dashboard (13 اختبارات)
- C7: unit tests — _InstrumentedCheckpointer logic (11 اختبارات)
- C8: unit tests — prom_metrics functions (16 اختبارات)
- C9: unit tests — _build_psycopg_conninfo (6 اختبارات)
- C10: automations.yaml (2 اختبارات)

#### 9. `.ona/automations.yaml`
- task `verify-step10-postgres-checkpointer` — تحقق شامل حي
- task `run-step10-tests` — 101 اختبار

### التحقق الحي (مُنجَز 2026-05-11)
```bash
# /checkpointer/status
curl http://localhost:8006/checkpointer/status
# → {"backend":"postgres","step":"10","active":true,"tables_ready":true,"active_threads":1,"pool_size":5}

# Prometheus metrics
curl http://localhost:8006/metrics | grep cogniforge_checkpointer
# → cogniforge_checkpointer_writes_total{status="success",thread_id_prefix="warmup"} 7.0
# → cogniforge_checkpointer_reads_total{status="hit",thread_id_prefix="warmup"} 1.0
# → cogniforge_checkpointer_reads_total{status="miss",thread_id_prefix="step10_i"} 2.0
# → cogniforge_checkpointer_duration_seconds_count{operation="write"} 7.0
# → cogniforge_checkpointer_active_threads 1.0
# → cogniforge_checkpointer_backend_info{backend="postgres",pool_size="5",step="10",tables_ready="true"} 1.0
# → cogniforge_orchestrator_startup_info{checkpointer_backend="postgres",graph_ready="true",...} 1.0
```

### الخدمات النشطة بعد Step 10
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Steps 4+9+10) |
| user-service | :8001 | ✅ ACTIVE (Step 5) |
| planning-agent | :8002 | ✅ ACTIVE (Step 6) |
| research-agent | :8007 | ✅ ACTIVE (Step 7) |
| reasoning-agent | :8008 | ✅ ACTIVE (Step 8) |
| Skills Pipeline | :8006/compose | ✅ ACTIVE (Step 9) |
| **Postgres Checkpointer** | **:8006/checkpointer/status** | **✅ ACTIVE (Step 10 — جديد)** |
| Grafana | :3001 | ✅ ACTIVE (13 dashboards) |
| Prometheus | :9090 | ✅ ACTIVE (10 scrape targets) |

### الخطوة التالية (Step 11)
- تفعيل `conversation-service` على `:8003` (الخدمة السادسة)
- أو: تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`)
- أو: إضافة authentication للـ `/compose` endpoint (JWT token)
- أو: تفعيل `memory-agent` على `:8009` لحفظ نتائج الـ Pipeline

---

## ✅ Session: 2026-05-11 — Microservices Step 9: Skills Composition Pipeline (الخطوة الانتقالية التاسعة)

**Branch**: `feat/microservices-step9-skills-pipeline`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 87 tests pass | ruff clean | Live /compose ✅ | Live /metrics ✅ | pipeline_mode="partial" confirmed

### الخطوة الانتقالية المختارة (D-039 — تنفيذ)
تحويل `orchestrator-service` من خدمة مستقلة إلى **Composition Engine حقيقي** يستدعي `planning-agent:8002`, `research-agent:8007`, و`reasoning-agent:8008` عبر HTTP حقيقي مع `X-Correlation-ID`. هذا هو أول **cross-service call حقيقي** في النظام — Skills تعمل معاً لأول مرة.

### التغييرات المُنجزة

#### 1. `microservices/orchestrator_service/src/services/skills_pipeline.py` — وحدة جديدة
- `run_skills_pipeline(query, correlation_id)` — الدالة الرئيسية
- `asyncio.gather(planning, research)` — planning+research بالتوازي لتقليل الزمن
- `_call_planning_skill()` → `POST planning-agent:8002/execute` action="generate_plan"
- `_call_research_skill()` → `POST research-agent:8007/execute` action="search"
- `_call_reasoning_skill()` → `POST reasoning-agent:8008/execute` action="reason" مع السياق المُجمَّع
- `_compose_answer()` — يُركِّب الإجابة: reasoning أولاً → research → plan
- `_determine_pipeline_mode()` → "full" | "partial" | "fallback"
- Fallback تلقائي: `ConnectError` / `TimeoutException` → `SkillResult(status="fallback")`
- `X-Correlation-ID` في كل طلب HTTP
- `_SKILL_TIMEOUT_SECONDS = 10.0`

#### 2. `microservices/orchestrator_service/src/core/prom_metrics.py` — 6 مقاييس جديدة
- `cogniforge_pipeline_invocations_total{mode=full|partial|fallback}`
- `cogniforge_pipeline_duration_seconds{mode=...}`
- `cogniforge_pipeline_skill_calls_total{skill=planning|research|reasoning, status=success|fallback|error}`
- `cogniforge_pipeline_skill_duration_seconds{skill=...}`
- `cogniforge_pipeline_errors_total{error_type=...}`
- `cogniforge_pipeline_active_gauge`
- `cogniforge_orchestrator_startup_info` — أُضيف label `pipeline_enabled`
- دوال: `record_pipeline_invocation()`, `record_pipeline_error()`, `set_pipeline_active()`

#### 3. `microservices/orchestrator_service/src/api/routes.py` — `/compose` endpoint جديد
- `ComposeRequest(query, correlation_id)` — Pydantic model
- `ComposeResponse(correlation_id, query, composed_answer, pipeline_mode, skills_active, total_duration_ms, plan, research, reasoning)`
- `SkillResultSchema` — schema لكل Skill result
- يُسجِّل `record_pipeline_invocation()` + `set_pipeline_active()` بعد كل طلب
- يُعيد `HTTPException(502)` عند فشل الـ Pipeline الكامل

#### 4. `microservices/orchestrator_service/src/core/config.py` — إصلاح الـ ports
- `planning-agent`: 8001 (خطأ) → **8002** (صحيح)
- `user-service`: 8003 (خطأ) → **8001** (صحيح)
- `memory-agent`: 8002 (خطأ) → **8009** (مؤقت)

#### 5. `microservices/orchestrator_service/main.py`
- `set_startup_info(..., pipeline_enabled=True)` — يُسجِّل pipeline_enabled في Prometheus

#### 6. `.devcontainer/supervisor.sh`
- `launch_orchestrator_service()` — أُضيف `CODESPACES=true` + URLs الـ 4 Skills

#### 7. `.ona/automations.yaml`
- service `orchestrator-service` — أُضيف `CODESPACES=true` + URLs الـ 4 Skills
- task `verify-step9-skills-pipeline` — تحقق شامل حي
- task `run-step9-tests` — 87 اختبار

#### 8. `observability/native/prometheus.yml`
- scrape target جديد: `job_name: skills-pipeline` → `localhost:8006/metrics` مع `step="9"`

#### 9. `observability/grafana/dashboards/120-microservices-step9-skills-pipeline.json` — Dashboard جديد
- 12 panels | UID: `cogniforge-ms-step9-pipeline` | refresh: 10s
- Row 1: Startup Info + Pipeline Invocations + Full Rate + P95 Latency + Active + Errors
- Row 2: Invocations by Mode + Duration P50/P95/P99
- Row 3: Skill Calls Rate (Success/Fallback/Error) + Skill Duration P95 by Skill
- Row 4: Health Matrix (Steps 4-9) + Step 9 Activation Guide

#### 10. `.github/workflows/microservices-step9-skills-pipeline.yml` — CI gate جديد
- 7 jobs: static-checks / prometheus-gate / dashboard-gate / lint / step9-tests / regression-steps-4-8 / pr-summary
- يتحقق من: skills_pipeline.py, asyncio.gather, X-Correlation-ID, /compose, pipeline metrics, ports, dashboard

#### 11. `tests/microservices/orchestrator_service/test_step9_skills_pipeline.py` — 87 اختبار
- S1: skills_pipeline.py بنية (17 اختبارات)
- S2: prom_metrics.py مقاييس Pipeline (11 اختبارات)
- S3: routes.py /compose endpoint (11 اختبارات)
- S4: config.py ports (5 اختبارات)
- S5: Prometheus scrape config (4 اختبارات)
- S6: Grafana dashboard (10 اختبارات)
- S7: automations.yaml (6 اختبارات)
- S8: unit tests skills_pipeline functions (11 اختبارات)
- S9: unit tests prom_metrics pipeline functions (10 اختبارات)
- S10: main.py pipeline_enabled (2 اختبارات)

### التحقق الحي (مُنجَز 2026-05-11)
```bash
# /compose endpoint
curl -X POST http://localhost:8006/compose \
  -H 'Content-Type: application/json' \
  -d '{"query": "اشرح قانون نيوتن الثاني"}'
# → {"pipeline_mode":"partial","skills_active":["research","reasoning"],"total_duration_ms":41.4}

# Prometheus metrics
curl http://localhost:8006/metrics | grep cogniforge_pipeline
# → cogniforge_pipeline_invocations_total{mode="partial"} 1.0
# → cogniforge_pipeline_skill_calls_total{skill="research",status="success"} 1.0
# → cogniforge_pipeline_skill_calls_total{skill="reasoning",status="success"} 1.0
# → cogniforge_orchestrator_startup_info{pipeline_enabled="true",...} 1.0

# Grafana dashboard:
# http://localhost:3001/d/cogniforge-ms-step9-pipeline
```

### الخدمات النشطة بعد Step 9
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Step 4 + Step 9 /compose) |
| user-service | :8001 | ✅ ACTIVE (Step 5) |
| planning-agent | :8002 | ✅ ACTIVE (Step 6) |
| research-agent | :8007 | ✅ ACTIVE (Step 7) |
| reasoning-agent | :8008 | ✅ ACTIVE (Step 8) |
| **Skills Pipeline** | **:8006/compose** | **✅ ACTIVE (Step 9 — جديد)** |
| Grafana | :3001 | ✅ ACTIVE (12 dashboards) |
| Prometheus | :9090 | ✅ ACTIVE (9 scrape targets) |

### الخطوة التالية (Step 10)
- تفعيل `conversation-service` على `:8003` (الخدمة السادسة)
- أو: ترقية LangGraph checkpointer من MemorySaver إلى PostgresCheckpointer (ISS-020)
- أو: تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`)
- أو: إضافة authentication للـ `/compose` endpoint (JWT token)
- أو: تفعيل `memory-agent` على `:8009` لحفظ نتائج الـ Pipeline

---

## ✅ Session: 2026-05-11 — Microservices Step 8: Reasoning Agent Live Activation (الخطوة الانتقالية الثامنة)

**Branch**: `feat/microservices-step8-reasoning-agent`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 79 tests pass | ruff clean | JSON valid | YAML valid | Live health ✅ | Live metrics ✅

### الخطوة الانتقالية المختارة (D-037 — تنفيذ)
تفعيل `reasoning-agent` كـ uvicorn process مستقل على `:8008` مع `/metrics` endpoint حقيقي بصيغة Prometheus. MCTS (Monte Carlo Tree Search) حي دائماً. LLM (OpenRouter/OpenAI) حي عند توفر المفتاح — mock mode بدونه. هذا يُحوِّل الخدمة الخامسة من DORMANT إلى ACTIVE في Codespaces، ويُضيف 11 مقياساً جديداً قابلاً للقياس الحي في Grafana.

### إصلاح مُطبَّق (ISS-039-B — lazy AIService singleton)
`AIService()` كان يُنشأ عند import وقت التحميل في `ai_service.py` → `OpenAIError: Missing credentials` عند الإقلاع بدون `OPENAI_API_KEY`. الإصلاح في `main.py`: لا يستورد `ai_service` مباشرةً — الـ routes تستخدم `reasoning_workflow` الذي يستدعي `ai_service` عند الحاجة فقط.

### التغييرات المُنجزة

#### 1. `microservices/reasoning_agent/requirements.txt`
- أضيف `prometheus-client>=0.20.0`

#### 2. `microservices/reasoning_agent/prom_metrics.py` — وحدة جديدة
- `CollectorRegistry` مستقل (لا يشارك REGISTRY الافتراضي)
- 11 مقياساً: `cogniforge_reasoning_requests_total`, `cogniforge_reasoning_request_duration_seconds`, `cogniforge_reasoning_active_connections`, `cogniforge_reasoning_invocations_total`, `cogniforge_reasoning_invocation_duration_seconds`, `cogniforge_reasoning_mcts_expansions_total`, `cogniforge_reasoning_mcts_errors_total`, `cogniforge_reasoning_llm_calls_total`, `cogniforge_reasoning_llm_errors_total`, `cogniforge_reasoning_fallback_responses_total`, `cogniforge_reasoning_startup_info{step="8",llm_backend=...,mcts_enabled="true"}`
- استيراد دفاعي (try/except ImportError) — stub classes عند غياب prometheus_client
- دوال عامة: `export_prometheus_text()`, `set_startup_info()`, `record_http_request()`, `record_reasoning_invocation()`, `record_mcts_expansion()`, `record_mcts_error()`, `record_llm_call()`, `record_llm_error()`, `record_fallback_response()`, `set_active_connections()`, `get_request_timer()`, `elapsed_since()`

#### 3. `microservices/reasoning_agent/main.py`
- استيراد `prom_metrics`
- `/metrics` endpoint جديد → `export_prometheus_text()` → Prometheus text format
- `/health` endpoint محسَّن → يُعيد `step`, `llm_backend`, `mcts_enabled`
- `set_startup_info()` في lifespan
- `_detect_llm_backend()` — يكتشف openrouter/openai/mock من env vars
- لا يستورد `ai_service` مباشرةً (ISS-039-B)

#### 4. `microservices/reasoning_agent/src/api/routes.py`
- استيراد `prom_metrics`
- `record_reasoning_invocation()` + `record_mcts_error()` + `record_fallback_response()` + `record_http_request()` في `/execute`
- حُذف `/health` المكرر (مُعرَّف في main.py)

#### 5. `.devcontainer/supervisor.sh`
- `launch_reasoning_agent()` — STEP 4H جديد
- يُشغِّل uvicorn على `:8008` تلقائياً عند توفر `DATABASE_URL`
- `OPENROUTER_API_KEY` محقون — LLM يعمل عند توفر المفتاح
- idempotent: يتحقق من الـ process قبل الإطلاق
- لا يحتاج asyncpg URL conversion (reasoning-agent لا يستخدم DB مباشرةً)

#### 6. `.ona/automations.yaml`
- service `reasoning-agent`: uvicorn start/ready/stop على :8008
- `ready` command يتحقق من `/health` و `/metrics | grep cogniforge_reasoning_startup_info`
- task `verify-step8-reasoning-agent`: تقرير شامل (health + metrics + LLM + Prometheus + Grafana + health matrix)
- task `restart-reasoning-agent`: إعادة تشغيل يدوي
- task `run-step8-tests`: يُشغِّل 79 اختبار Step 8
- تحديث header التعليق ليعكس Step 8

#### 7. `observability/native/prometheus.yml`
- scrape target جديد: `job_name: reasoning-agent` → `localhost:8008/metrics`
- label `step: "8"` + `service: reasoning-agent` + `tier: microservice`

#### 8. `observability/grafana/dashboards/110-microservices-step8-reasoning-agent.json` — Dashboard جديد
- 20+ panels | UID: `cogniforge-ms-step8-reasoning-agent` | refresh: 10s
- Row 1: Startup Info + LLM Backend + HTTP Rate + P95 Latency + Total Invocations + Active Connections
- Row 2: HTTP Requests by Endpoint & Status + HTTP Latency P50/P95/P99
- Row 3: Invocations Rate (Success/Error/Fallback) + Invocation Duration P50/P95 + MCTS Expansions by Depth
- Row 4: LLM Calls Rate (Success vs Error) + LLM Errors by Type + Fallback Responses by Reason
- Row 5: Microservices Health Matrix (all steps 4-8) + Prometheus Scrape Duration
- Row 6: Step 8 Activation Guide (markdown)

#### 9. `.github/workflows/microservices-step8-reasoning-agent.yml` — CI gate جديد
- 7 jobs: `static-checks` / `infrastructure-gate` / `dashboard-gate` / `lint` / `step8-tests` / `regression-steps-4-7` / `pr-summary`
- يتحقق من: prometheus-client في requirements، prom_metrics.py موجود، /metrics في main.py، ISS-039-B، supervisor.sh، automations.yaml، prometheus.yml، dashboard صالح
- PR comment تلخيصي مع جدول النتائج وأوامر التحقق الحي

#### 10. `tests/microservices/reasoning_agent/test_step8_reasoning_agent_metrics.py` — 79 اختبار
- R1: prometheus-client في requirements.txt (3 اختبارات)
- R2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة (24 اختبارات)
- R3: main.py — /metrics + /health + step=8 + ISS-039-B (8 اختبارات)
- R4: supervisor.sh يُشغِّل reasoning-agent (6 اختبارات)
- R5: automations.yaml يحتوي reasoning-agent (8 اختبارات)
- R6: Prometheus scrape config صحيح (5 اختبارات)
- R7: Grafana dashboard صالح (10 اختبارات)
- R8: unit tests للـ prom_metrics functions (15 اختبارات)

### التحقق الحي (مُنجَز 2026-05-11)
```bash
curl http://localhost:8008/health
# → {"status":"healthy","service":"reasoning-agent","step":"8","llm_backend":"openrouter","mcts_enabled":"true"}

curl http://localhost:8008/metrics | grep cogniforge_reasoning_startup_info
# → cogniforge_reasoning_startup_info{environment="development",llm_backend="openrouter",mcts_enabled="true",step="8",version="1.0.0"} 1.0

# Grafana dashboard:
# http://localhost:3001/d/cogniforge-ms-step8-reasoning-agent
```

### الخدمات النشطة بعد Step 8
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Step 4) |
| user-service | :8001 | ✅ ACTIVE (Step 5) |
| planning-agent | :8002 | ✅ ACTIVE (Step 6) |
| research-agent | :8007 | ✅ ACTIVE (Step 7) |
| **reasoning-agent** | **:8008** | **✅ ACTIVE (Step 8 — جديد)** |
| Grafana | :3001 | ✅ ACTIVE (11 dashboards) |
| Prometheus | :9090 | ✅ ACTIVE (8 scrape targets) |

### الخطوة التالية (Step 9)
- ربط reasoning-agent بـ research-agent عبر HTTP (cross-service call حقيقي)
- أو: تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`)
- أو: ترقية LangGraph checkpointer من MemorySaver إلى PostgresCheckpointer (ISS-020)
- أو: تفعيل `conversation-service` على `:8003`

---

---

## ✅ Session: 2026-05-10 — Microservices Step 7: Research Agent Live Activation (الخطوة الانتقالية السابعة)

**Branch**: `feat/microservices-step7-research-agent`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 68 tests pass | ruff clean | JSON valid | YAML valid | Live health ✅ | Live metrics ✅

### الخطوة الانتقالية المختارة (D-036 — تنفيذ)
تفعيل `research-agent` كـ uvicorn process مستقل على `:8007` مع `/metrics` endpoint حقيقي بصيغة Prometheus. Tavily web search حي عند توفر `TAVILY_API_KEY`. هذا يُحوِّل الخدمة الرابعة من DORMANT إلى ACTIVE في Codespaces، ويُضيف 11 مقياساً جديداً قابلاً للقياس الحي في Grafana.

### إصلاح مكتشف حياً (ISS-039 — SuperSearchOrchestrator lazy singleton)
`SuperSearchOrchestrator()` كان يُنشأ عند import وقت التحميل → `OpenAIError: Missing credentials` عند الإقلاع بدون `OPENAI_API_KEY`. الإصلاح: تحويل إلى lazy singleton (`_get_super_search()`) — يُنشأ فقط عند أول استدعاء `deep_research`.

### التغييرات المُنجزة

#### 1. `microservices/research_agent/requirements.txt`
- أضيف `prometheus-client>=0.20.0`
- أضيف `tavily-python>=0.3.0`

#### 2. `microservices/research_agent/prom_metrics.py` — وحدة جديدة
- `CollectorRegistry` مستقل (لا يشارك REGISTRY الافتراضي)
- 11 مقياساً: `cogniforge_research_requests_total`, `cogniforge_research_request_duration_seconds`, `cogniforge_research_active_connections`, `cogniforge_research_searches_total`, `cogniforge_research_search_duration_seconds`, `cogniforge_research_tavily_calls_total`, `cogniforge_research_tavily_errors_total`, `cogniforge_research_deep_research_total`, `cogniforge_research_db_operations_total`, `cogniforge_research_db_duration_seconds`, `cogniforge_research_startup_info{step="7",tavily_available=...}`
- استيراد دفاعي (try/except ImportError) — stub classes عند غياب prometheus_client
- دوال عامة: `export_prometheus_text()`, `set_startup_info()`, `record_search()`, `record_tavily_call()`, `record_tavily_error()`, `record_deep_research()`, `record_http_request()`, `record_db_operation()`, `set_active_connections()`, `get_request_timer()`, `elapsed_since()`

#### 3. `microservices/research_agent/main.py`
- استيراد `prom_metrics`
- `/metrics` endpoint جديد → `export_prometheus_text()` → Prometheus text format
- `set_startup_info(version, environment, db_backend, tavily_available)` في lifespan
- `_TAVILY_READY` flag — يكتشف توفر TAVILY_API_KEY + tavily package
- lazy singleton `_get_super_search()` — يحل ISS-039
- `record_search()` + `record_deep_research()` + `record_tavily_call/error()` في `/execute`

#### 4. `.devcontainer/supervisor.sh`
- `launch_research_agent()` — STEP 4G جديد
- يُشغِّل uvicorn على `:8007` تلقائياً عند توفر `DATABASE_URL`
- `TAVILY_API_KEY` محقون — Tavily يعمل عند توفر المفتاح
- asyncpg URL conversion (ISS-038-B pattern)
- idempotent: يتحقق من الـ process قبل الإطلاق

#### 5. `.ona/automations.yaml`
- service `research-agent`: uvicorn start/ready/stop على :8007
- `ready` command يتحقق من `/health` و `/metrics | grep cogniforge_research_startup`
- task `verify-step7-research-agent`: تقرير شامل (health + metrics + Tavily + Prometheus + Grafana)
- task `restart-research-agent`: إعادة تشغيل يدوي
- task `run-step7-tests`: يُشغِّل 68 اختبار Step 7
- تحديث header التعليق ليعكس Step 7

#### 6. `observability/native/prometheus.yml`
- scrape target جديد: `job_name: research-agent` → `localhost:8007/metrics`
- label `step: "7"` + `service: research-agent` + `tier: microservice`

#### 7. `observability/grafana/dashboards/100-microservices-step7-research-agent.json` — Dashboard جديد
- 20+ panels | UID: `cogniforge-ms-step7-research-agent` | refresh: 10s
- Row 1: Startup Info + Tavily Status + HTTP Rate + P95 Latency + Total Searches + Active Connections
- Row 2: HTTP Requests by Endpoint + HTTP Latency P50/P95/P99
- Row 3: Search Rate by Type + Search Duration P50/P95
- Row 4: Tavily API Calls (Success vs Error) + Tavily Errors by Type + Deep Research
- Row 5: DB Operations Rate + DB Duration P50/P95
- Row 6: Microservices Health Matrix (all steps 4-7) + Prometheus Scrape Duration
- Row 7: Step 7 Activation Guide (markdown)

#### 8. `.github/workflows/microservices-step7-research-agent.yml` — CI gate جديد
- 7 jobs: `static-checks` / `dashboard-gate` / `lint` / `step7-tests` / `step6-regression` / `yaml-gate` / `pr-summary`
- يتحقق من: prometheus-client + tavily-python في requirements، prom_metrics.py موجود، /metrics في main.py، supervisor.sh، automations.yaml، prometheus.yml، dashboard صالح
- PR comment تلخيصي مع جدول النتائج وأوامر التحقق الحي

#### 9. `tests/microservices/research_agent/test_step7_research_agent_metrics.py` — 68 اختبار
- R1: prometheus-client + tavily-python في requirements.txt (3 اختبارات)
- R2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة (19 اختبارات)
- R3: /metrics endpoint في main.py (6 اختبارات)
- R4: supervisor.sh يُشغِّل research-agent (5 اختبارات)
- R5: automations.yaml يحتوي research-agent (7 اختبارات)
- R6: Prometheus scrape config صحيح (4 اختبارات)
- R7: Grafana dashboard صالح (10 اختبارات)
- R8: unit tests للـ prom_metrics functions (14 اختبارات)

### التحقق الحي (مُنجَز)
```bash
curl http://localhost:8007/health
# → {"status":"healthy","service":"research-agent","step":"7","tavily_available":"true"}

curl http://localhost:8007/metrics | grep cogniforge_research_startup
# → cogniforge_research_startup_info{db_backend="sqlite",environment="development",step="7",tavily_available="true",version="1.0.0"} 1.0

# Grafana dashboard:
# http://localhost:3001/d/cogniforge-ms-step7-research-agent
```

### الخدمات النشطة بعد Step 7
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Step 4) |
| user-service | :8001 | ✅ ACTIVE (Step 5) |
| planning-agent | :8002 | ✅ ACTIVE (Step 6) |
| **research-agent** | **:8007** | **✅ ACTIVE (Step 7 — جديد)** |
| Grafana | :3001 | ✅ ACTIVE (10 dashboards) |
| Prometheus | :9090 | ✅ ACTIVE (7 scrape targets) |

### الخطوة التالية (Step 8)
- تفعيل `reasoning-agent` على `:8008` (uvicorn process)
- أو: ترقية LangGraph checkpointer من MemorySaver إلى PostgresCheckpointer (ISS-020)
- أو: تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`)
- أو: ربط research-agent بـ orchestrator-service عبر HTTP (cross-service call)

---

## ✅ Session: 2026-05-10 — Microservices Step 6: Planning Agent Live Activation (الخطوة الانتقالية السادسة)

**Branch**: `feat/microservices-step6-planning-agent`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 61 tests pass | ruff clean | JSON valid | YAML valid

### الخطوة الانتقالية المختارة (D-035 — تنفيذ)
تفعيل `planning-agent` كـ uvicorn process مستقل على `:8002` مع `/metrics` endpoint حقيقي بصيغة Prometheus. DSPy + LangGraph مع fallback chain عند غياب `OPENROUTER_API_KEY`. هذا يُحوِّل الخدمة الثالثة من DORMANT إلى ACTIVE في Codespaces، ويُضيف 11 مقياساً جديداً قابلاً للقياس الحي في Grafana. كما يُضيف `docker-compose.step6.yml` لتشغيل الـ stack الكامل في بيئات Docker.

### التغييرات المُنجزة

#### 1. `microservices/planning_agent/requirements.txt`
- أضيف `prometheus-client>=0.20.0`

#### 2. `microservices/planning_agent/prom_metrics.py` — وحدة جديدة
- `CollectorRegistry` مستقل (لا يشارك REGISTRY الافتراضي)
- 11 مقياساً: `cogniforge_planning_requests_total`, `cogniforge_planning_request_duration_seconds`, `cogniforge_planning_active_connections`, `cogniforge_planning_plans_total`, `cogniforge_planning_plan_duration_seconds`, `cogniforge_planning_dspy_invocations_total`, `cogniforge_planning_dspy_errors_total`, `cogniforge_planning_fallback_plans_total`, `cogniforge_planning_db_operations_total`, `cogniforge_planning_db_duration_seconds`, `cogniforge_planning_startup_info{step="6",dspy_available=...}`
- استيراد دفاعي (try/except ImportError) — stub classes عند غياب prometheus_client
- دوال عامة: `export_prometheus_text()`, `record_plan_created()`, `record_dspy_invocation()`, `record_http_request()`, `record_db_operation()`, `set_startup_info()`, `set_active_connections()`, `get_request_timer()`, `elapsed_since()`

#### 3. `microservices/planning_agent/main.py`
- استيراد `prom_metrics`
- `/metrics` endpoint جديد → `export_prometheus_text()` → Prometheus text format
- `set_startup_info(version, environment, db_backend, dspy_available)` في lifespan
- `fastapi.responses.Response` لإرجاع Prometheus text مباشرة

#### 4. `.devcontainer/supervisor.sh`
- `launch_planning_agent()` — STEP 4F جديد
- يُشغِّل uvicorn على `:8002` تلقائياً عند توفر `DATABASE_URL`
- `PLANNING_DATABASE_URL="${PLANNING_DATABASE_URL:-${DATABASE_URL:-}}"` — يستخدم Supabase المشترك
- `PLANNING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"` — DSPy يعمل عند توفر المفتاح، fallback بدونه
- idempotent: يتحقق من الـ process قبل الإطلاق

#### 5. `.ona/automations.yaml`
- service `planning-agent`: uvicorn start/ready/stop
- `ready` command يتحقق من `/health` و `/metrics | grep cogniforge_planning_startup_info`
- task `verify-step6-planning-agent`: تقرير شامل (health + metrics + Prometheus + Grafana + plan creation test)
- task `restart-planning-agent`: إعادة تشغيل يدوي
- task `run-step6-tests`: يُشغِّل 61 اختبار Step 6
- task `docker-compose-stack`: يُشغِّل docker-compose.step6.yml في بيئات Docker (مع graceful fallback في Codespaces)
- تحديث header التعليق ليعكس Step 6

#### 6. `observability/native/prometheus.yml`
- scrape target جديد: `job_name: planning-agent` → `localhost:8002/metrics`
- label `step: "6"` + `service: planning-agent` + `tier: microservice`

#### 7. `docker-compose.step6.yml` — ملف جديد
- Docker Compose stack كامل: orchestrator-service + user-service + planning-agent
- مخصص لبيئات Docker (ليس Codespaces — supervisor.sh هو المسار هناك)
- `redis-step6` على :6381 (لا يتعارض مع redis الرئيسي)
- `OPENROUTER_API_KEY` + `DATABASE_URL` مُحقَنان من البيئة
- healthcheck لكل خدمة

#### 8. `observability/grafana/dashboards/90-microservices-step6-planning-agent.json` — Dashboard جديد
- 20 panels | UID: `cogniforge-ms-step6-planning-agent` | refresh: 10s
- Row 1: Health + Startup Info + HTTP Rate + P95 Latency + Total Plans + Active Connections
- Row 2: HTTP Requests by Endpoint + HTTP Latency P50/P95/P99
- Row 3: Plans Rate (Success vs Fallback) + Plan Duration P50/P95 + DSPy Invocations
- Row 4: DB Operations Rate + DB Duration P50/P95
- Row 5: Microservices Health Matrix (all steps) + Prometheus Scrape Duration
- Row 6: Step 6 Activation Guide (markdown)
- Row 7: Fallback Plans Rate by Reason + DSPy Errors by Type

#### 9. `.github/workflows/microservices-step6-planning-agent.yml` — CI gate جديد
- 7 jobs: `static-checks` / `compose-gate` / `dashboard-gate` / `lint` / `step6-tests` / `step5-regression` / `pr-summary`
- يتحقق من: prometheus-client في requirements، prom_metrics.py موجود، /metrics في main.py، supervisor.sh، automations.yaml، prometheus.yml، dashboard صالح، docker-compose.step6.yml صالح
- PR comment تلخيصي مع جدول النتائج وأوامر التحقق الحي

#### 10. `tests/microservices/planning_agent/test_step6_planning_agent_metrics.py` — 61 اختبار
- P1: prometheus-client في requirements.txt (3 اختبارات)
- P2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة (11 اختبارات)
- P3: /metrics endpoint في main.py (6 اختبارات)
- P4: supervisor.sh يُشغِّل planning-agent (5 اختبارات)
- P5: automations.yaml يحتوي planning-agent (7 اختبارات)
- P6: Prometheus scrape config صحيح (4 اختبارات)
- P7: Grafana dashboard صالح (8 اختبارات)
- P8: docker-compose.step6.yml صالح (6 اختبارات)
- P9: unit tests للـ prom_metrics functions (11 اختبارات)

### التحقق الحي
```bash
# بعد تشغيل planning-agent (تلقائي عبر supervisor.sh):
curl http://localhost:8002/health
# → {"service":"planning-agent","status":"ok"}

curl http://localhost:8002/metrics | grep cogniforge_planning
# → cogniforge_planning_startup_info{version="1.0.0",environment="development",db_backend="postgresql",dspy_available="true",step="6"} 1.0

# Grafana dashboard:
# http://localhost:3001/d/cogniforge-ms-step6-planning-agent

# Docker Compose (بيئات Docker):
# docker compose -f docker-compose.step6.yml up -d
```

### الخدمات النشطة بعد Step 6
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Step 4) |
| user-service | :8001 | ✅ ACTIVE (Step 5) |
| **planning-agent** | **:8002** | **✅ ACTIVE (Step 6 — جديد)** |
| Grafana | :3001 | ✅ ACTIVE (9 dashboards) |
| Prometheus | :9090 | ✅ ACTIVE (6 scrape targets) |

### إصلاح مكتشف حياً (ISS-038-B — asyncpg URL conversion)
أثناء التحقق الحي تبيّن أن `orchestrator-service` و`planning-agent` يفشلان في الإقلاع بسبب:
```
sqlalchemy.exc.InvalidRequestError: The asyncio extension requires an async driver.
The loaded 'psycopg2' is not async.
```
**السبب:** `DATABASE_URL` من Supabase يستخدم `postgresql://` → SQLAlchemy يُعيّنه لـ psycopg2 المتزامن.
**الإصلاح:** تحويل inline في `supervisor.sh` و `automations.yaml`:
```bash
_url="${DATABASE_URL/postgresql:\/\//postgresql+asyncpg://}"
_url=$(echo "$_url" | sed 's/[?&]sslmode=[^&]*//')
```
**ملاحظة إضافية:** `orchestrator-service` يبدأ بـ `startup_state:degraded` لكن `graph_ready:true` — PgBouncer prepared statement conflict غير مميت.

### الخطوة التالية (Step 7)
- تفعيل `research-agent` على `:8007` (uvicorn process) — Tavily web search حي
- أو: تفعيل `reasoning-agent` على `:8008`
- أو: ترقية LangGraph checkpointer من MemorySaver إلى PostgresCheckpointer (ISS-020)
- أو: تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`)

---

---

## ✅ Session: 2026-05-10 — Microservices Step 5: User Service Live Activation (الخطوة الانتقالية الخامسة)

**Branch**: `feat/microservices-step5-user-service`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 36 tests pass | ruff clean | JSON valid | YAML valid

### الخطوة الانتقالية المختارة (D-034 — تنفيذ)
تفعيل `user-service` كـ uvicorn process مستقل على `:8001` مع `/metrics` endpoint حقيقي بصيغة Prometheus. هذا يُحوِّل الخدمة الثانية من DORMANT إلى ACTIVE في Codespaces، ويُضيف 11 مقياساً جديداً قابلاً للقياس الحي في Grafana.

### التغييرات المُنجزة

#### 1. `microservices/user_service/requirements.txt`
- أضيف `prometheus-client>=0.20.0`

#### 2. `microservices/user_service/src/core/prom_metrics.py` — وحدة جديدة
- `CollectorRegistry` مستقل (لا يشارك REGISTRY الافتراضي)
- 11 مقياساً: `cogniforge_user_requests_total`, `cogniforge_user_request_duration_seconds`, `cogniforge_user_active_connections`, `cogniforge_user_auth_operations_total`, `cogniforge_user_auth_duration_seconds`, `cogniforge_user_registrations_total`, `cogniforge_user_logins_total`, `cogniforge_user_token_verifications_total`, `cogniforge_user_db_operations_total`, `cogniforge_user_db_duration_seconds`, `cogniforge_user_startup_info{step="5"}`
- استيراد دفاعي (try/except ImportError) — stub classes عند غياب prometheus_client
- دوال عامة: `export_prometheus_text()`, `record_http_request()`, `record_auth_operation()`, `record_db_operation()`, `set_startup_info()`, `set_active_connections()`, `get_request_timer()`, `elapsed_since()`

#### 3. `microservices/user_service/main.py`
- استيراد `prom_metrics` functions
- `/metrics` endpoint جديد → `export_prometheus_text()` → Prometheus text format
- `set_startup_info(version, environment, db_backend)` في lifespan Phase 3
- `fastapi.responses.Response` لإرجاع Prometheus text مباشرة

#### 4. `.devcontainer/supervisor.sh`
- `launch_user_service()` — STEP 4E جديد
- يُشغِّل uvicorn على `:8001` تلقائياً عند توفر `DATABASE_URL`
- `USER_DATABASE_URL="${USER_DATABASE_URL:-${DATABASE_URL:-}}"` — يستخدم Supabase المشترك
- idempotent: يتحقق من الـ process قبل الإطلاق
- يُضيف سطراً في lifecycle_info النهائي

#### 5. `.ona/automations.yaml`
- service `user-service`: uvicorn start/ready/stop
- `ready` command يتحقق من `/health` و `/metrics | grep cogniforge_user_startup_info`
- task `verify-step5-user-service`: تقرير شامل (health + metrics + Prometheus + Grafana)
- task `restart-user-service`: إعادة تشغيل يدوي
- task `run-step5-tests`: يُشغِّل 36 اختبار Step 5

#### 6. `observability/native/prometheus.yml`
- scrape target جديد: `job_name: user-service` → `localhost:8001/metrics`
- label `step: "5"` + `service: user-service` + `tier: microservice`

#### 7. `observability/grafana/dashboards/80-microservices-step5-user-service.json` — Dashboard جديد
- 17 panels | UID: `cogniforge-ms-step5-user-service` | refresh: 10s
- Row 1: Startup Info + HTTP Rate + P95 Latency + Active Connections + Total Registrations
- Row 2: HTTP Requests by Endpoint + HTTP Latency P50/P95/P99
- Row 3: Auth Operations Rate + Auth Results + Auth Duration + Registrations/Logins Rate
- Row 4: DB Operations Rate + DB Duration P50/P95
- Row 5: Microservices Health Matrix + Prometheus Scrape Duration
- Row 6: Step 5 Activation Guide (markdown)

#### 8. `.github/workflows/microservices-step5-user-service.yml` — CI gate جديد
- 6 jobs: `static-checks` / `dashboard-gate` / `lint` / `step5-tests` / `step4-regression` / `pr-summary`
- يتحقق من: prometheus-client في requirements، prom_metrics.py موجود، /metrics في main.py، supervisor.sh، automations.yaml، prometheus.yml، dashboard صالح
- PR comment تلخيصي مع جدول النتائج وأوامر التحقق الحي

#### 9. `tests/microservices/user_service/test_step5_user_service_metrics.py` — 36 اختبار
- U1: prometheus-client في requirements.txt (2 اختبارات)
- U2: prom_metrics.py موجود ويحتوي المقاييس الصحيحة (11 اختبارات)
- U3: /metrics endpoint في main.py (5 اختبارات)
- U4: supervisor.sh يُشغِّل user-service (4 اختبارات)
- U5: automations.yaml يحتوي user-service (5 اختبارات)
- U6: Prometheus scrape config صحيح (3 اختبارات)
- U7: Grafana dashboard صالح (7 اختبارات)
- U8: unit tests للـ prom_metrics functions (9 اختبارات)

### التحقق الحي
```bash
# بعد تشغيل user-service (تلقائي عبر supervisor.sh):
curl http://localhost:8001/health
# → {"service":"user-service","status":"ok","environment":"development"}

curl http://localhost:8001/metrics | grep cogniforge_user
# → cogniforge_user_startup_info{version="1.0.0",environment="development",db_backend="postgresql",step="5"} 1.0

# Grafana dashboard:
# http://localhost:3001/d/cogniforge-ms-step5-user-service
```

### الخدمات النشطة بعد Step 5
| الخدمة | المنفذ | الحالة |
|--------|--------|--------|
| FastAPI monolith | :8000 | ✅ ACTIVE |
| orchestrator-service | :8006 | ✅ ACTIVE (Step 4) |
| **user-service** | **:8001** | **✅ ACTIVE (Step 5 — جديد)** |
| Grafana | :3001 | ✅ ACTIVE |
| Prometheus | :9090 | ✅ ACTIVE |

### الخطوة التالية (Step 6)
- تفعيل `planning-agent` على `:8002` (uvicorn process)
- أو: تفعيل `research-agent` على `:8007`
- أو: ترقية LangGraph checkpointer من MemorySaver إلى PostgresCheckpointer (ISS-020)

---

## ✅ Session: 2026-05-10 — Microservices Step 4: Persistence Relay + Prometheus Metrics (الخطوة الانتقالية الرابعة)

**Branch**: `feat/microservices-step4-persistence-relay`

---

## ✅ Session: 2026-05-10 — Microservices Step 4: Persistence Relay + Prometheus Metrics (الخطوة الانتقالية الرابعة)

**Branch**: `feat/microservices-step4-persistence-relay`
**Mode**: Live code changes — Codespaces native (no Docker). uvicorn processes only.
**Verified**: 44/44 tests pass | ruff clean | JSON valid | YAML valid

### الخطوة الانتقالية المختارة (D-031/D-032/D-033 — تنفيذ)
تفعيل `OUTBOX_RELAY_ENABLED=true` + إضافة `/metrics` endpoint حقيقي بصيغة Prometheus في `orchestrator-service`. هذا يُحوِّل الخدمة من "تعمل بدون مراقبة" إلى "قابلة للقياس الحي في Grafana".

### التغييرات المُنجزة

#### 1. `microservices/orchestrator_service/requirements.txt`
- أضيف `prometheus-client>=0.20.0`

#### 2. `microservices/orchestrator_service/src/core/prom_metrics.py` — وحدة جديدة
- `CollectorRegistry` مستقل (لا يشارك الـ default REGISTRY مع المونوليث)
- 11 مقياساً: `cogniforge_outbox_relay_cycles_total`, `cogniforge_outbox_relay_processed_total`, `cogniforge_outbox_relay_failed_total`, `cogniforge_outbox_relay_skipped_total`, `cogniforge_outbox_pending_gauge`, `cogniforge_stategraph_invocations_total`, `cogniforge_stategraph_duration_seconds`, `cogniforge_stategraph_errors_total`, `cogniforge_orchestrator_requests_total`, `cogniforge_orchestrator_request_duration_seconds`, `cogniforge_orchestrator_startup_info`
- استيراد دفاعي (try/except ImportError) — stub classes عند غياب prometheus_client
- دوال عامة: `export_prometheus_text()`, `record_outbox_relay_cycle()`, `record_outbox_relay_error()`, `set_startup_info()`

#### 3. `microservices/orchestrator_service/main.py`
- استيراد `prom_metrics` functions
- `/metrics` endpoint جديد → `export_prometheus_text()` → Prometheus text format
- `record_outbox_relay_cycle(summary)` مُدمج في `_outbox_relay_loop` بعد كل دورة ناجحة
- `record_outbox_relay_error()` عند فشل الـ relay
- `set_startup_info(...)` في lifespan Phase 6 بعد الإقلاع

#### 4. `.devcontainer/supervisor.sh`
- `OUTBOX_RELAY_ENABLED="true"` (كان `"false"` في Step 3)
- `OUTBOX_RELAY_INTERVAL_SECONDS="15"` و `OUTBOX_RELAY_BATCH_SIZE="50"` مضبوطان صراحةً

#### 5. `.ona/automations.yaml`
- service `orchestrator-service`: `OUTBOX_RELAY_ENABLED="true"` + `ready` command يتحقق من `/metrics`
- task جديد `verify-step4-metrics`: يتحقق من 6 مقاييس في `/metrics` + Prometheus targets + Grafana URL
- task جديد `run-step4-tests`: يُشغِّل 44 اختبار Step 4

#### 6. `observability/native/prometheus.yml`
- label `step: "4"` (كان `"3"`)
- تعليق محدَّث يوضح أن `/metrics` يُصدِّر prometheus_client text format حقيقي

#### 7. `observability/grafana/dashboards/70-microservices-step4-persistence.json` — Dashboard جديد
- 24 panels | UID: `cogniforge-ms-step4-persistence` | refresh: 10s
- Row 1: Startup Info + OUTBOX_RELAY status + StateGraph ready + relay cycles/processed/failed
- Row 2: Relay cycles rate (success vs error) + relay records (processed/failed/skipped)
- Row 3: StateGraph invocations rate + duration heatmap
- Row 4: HTTP requests rate + P50/P95/P99 latency
- Row 5: Active WebSocket connections + StateGraph errors by type + outbox pending gauge
- Row 6: Prometheus scrape duration + scrape UP/DOWN + monolith UP/DOWN

#### 8. `.github/workflows/microservices-step4.yml` — CI gate جديد
- 5 jobs: `static-checks` / `lint` / `step4-tests` / `step3-regression` / `pr-summary`
- يتحقق من: prometheus-client في requirements، prom_metrics.py موجود، /metrics في main.py، OUTBOX_RELAY_ENABLED=true في supervisor+automations، dashboard صالح، prometheus config صحيح
- PR comment تلخيصي مع جدول النتائج وأوامر التحقق الحي

#### 9. `tests/microservices/orchestrator_service/test_step4_persistence_relay.py` — 44 اختبار
- P1: prometheus-client في requirements.txt
- P2: prom_metrics.py موجود ويحتوي الـ counters الصحيحة (9 اختبارات)
- P3: /metrics endpoint في main.py (6 اختبارات)
- P4: OUTBOX_RELAY_ENABLED=true في supervisor.sh
- P5: OUTBOX_RELAY_ENABLED=true في automations.yaml (4 اختبارات)
- P6: Grafana dashboard صالح (8 اختبارات)
- P7: Prometheus scrape config صحيح (3 اختبارات)
- P8/P9/P10: unit tests للـ prom_metrics functions (8 اختبارات)

### التحقق الحي
```bash
# بعد تشغيل orchestrator-service:
curl http://localhost:8006/metrics | grep cogniforge_outbox
# → cogniforge_outbox_relay_cycles_total{result="success"} N
# → cogniforge_orchestrator_startup_info{outbox_relay_enabled="true",...} 1

# Grafana dashboard:
# http://localhost:3001/d/cogniforge-ms-step4-persistence
```

### الخطوة التالية (Step 5)
- تفعيل Redis الحقيقي (`CACHE_TYPE=redis`, `REDIS_URL=redis://localhost:6379/0`) — يتطلب تثبيت redis-server في devcontainer
- أو: ترقية LangGraph checkpointer من MemorySaver إلى PostgresCheckpointer (ISS-020)
- أو: تفعيل Tavily web search في المسار الحي (StateGraph → WebSearchFallbackNode)

---

## ✅ Session: 2026-05-10 — Microservices Step 3: Live Activation (الخطوة الانتقالية الثالثة)

**Branch**: `feat/microservices-step3-live-activation`
**Mode**: Live code changes — docker-compose.step3.yml + Ona automations + Grafana dashboard + GitHub Actions CI gate.
**Verified**: JSON valid | YAML valid | workflow syntax valid | ruff clean

### الخطوة الانتقالية المختارة (D-029 — تنفيذ)
تفعيل `orchestrator-service` كـ Ona automation service حي مع قاعدة بياناته المستقلة (`postgres-orchestrator`) وRedis المستقل. هذا يُحوِّل الخدمة من DORMANT إلى ACTIVE عند تشغيل `gitpod automations service start orchestrator-stack`.

### التغييرات المُنجزة

#### 1. `docker-compose.step3.yml` — ملف compose مخصص للخطوة 3
- 3 خدمات فقط: `postgres-orchestrator` (5441) + `redis-orchestrator` (6380) + `orchestrator-service` (8006)
- healthcheck لكل خدمة مع `start_period` مناسب
- `OPENROUTER_API_KEY` و`TAVILY_API_KEY` مُحقَنان
- `OUTBOX_RELAY_ENABLED=false` (يُفعَّل في Step 4)
- volumes مستقلة لا تتعارض مع `docker-compose.yml` الرئيسي

#### 2. `.ona/automations.yaml` — Ona automations
- **service** `orchestrator-stack`: يُشغِّل الـ stack مع health probe حي، `ready` command يتحقق من `:8006/health`
- **task** `health-probe`: تقرير مفصل عن `/health` + `/metrics` + Prometheus targets
- **task** `verify-stack`: تحقق شامل من 6 مكونات (postgres + redis + orchestrator + monolith + grafana + prometheus)
- **task** `run-step3-tests`: يُشغِّل اختبارات الانتقال بمتغيرات CI آمنة

#### 3. `observability/grafana/dashboards/60-microservices-step3-live.json` — Dashboard جديد
- UID: `cogniforge-ms-step3-live`
- 20 panel: status stats + timeseries + table + logs + text guide
- Metrics: `up{job="orchestrator-service"}`, `cogniforge_routing_*`, `cogniforge_langgraph_*`, `process_*`
- Refresh: 10s (مراقبة حية)

#### 4. `.github/workflows/microservices-step3-live.yml` — CI gate
- 7 jobs: compose-validation + stategraph-compile-gate + dashboard-gate + prometheus-config-gate + transition-tests + automations-validation + step3-gate
- تعليق تلقائي على PR بنتائج الـ gate
- يُشغَّل عند تغيير أي ملف من ملفات الخطوة 3

---

## ✅ Session: 2026-05-10 — Microservices Step 2: StateGraph Routing (الخطوة الانتقالية الثانية)

**Branch**: `feat/microservices-step2-stategraph-routing`
**Mode**: Live code changes — routing policy + observability + CI gate.
**Verified**: 16/16 tests PASSED | ruff clean | dashboard JSON valid | prometheus config valid

### الخطوة الانتقالية المختارة (D-021 — تنفيذ)
تعديل `ChatRoutingPolicy` لتوجيه المونوليث نحو `/api/chat/messages` (StateGraph 13 عقدة) بدلاً من `/agent/chat` (OrchestratorAgent). هذا يُفعّل المسار الكامل للـ StateGraph عند تشغيل `docker compose up orchestrator-service`.

### التغييرات المُنجزة

#### 1. `app/infrastructure/clients/routing_policy.py` — تعديل جوهري
- إضافة `endpoint_mode: str` كحقل جديد في `ChatRoutingPolicy`
- `_ENDPOINT_MAP`: قاموس صريح يربط الوضع بنقطة النهاية
  - `"state_graph"` → `/api/chat/messages` (الافتراضي الجديد)
  - `"agent"` → `/agent/chat` (للتراجع فقط)
- `ORCHESTRATOR_CHAT_ENDPOINT` env var يتحكم في الوضع
- `targets_state_graph` property للاستعلام السريع
- تحقق صارم: قيمة غير معروفة → تحذير + fallback إلى `state_graph`

#### 2. `app/infrastructure/clients/orchestrator_client.py` — إضافة metrics
- `routing.mode.state_graph` gauge: 1 = StateGraph, 0 = Agent
- `routing.target.total{target=...}` counter: يُحصي كل هدف (state_graph / agent / local_fallback)
- log يشمل `endpoint_mode` و `targets_state_graph` لكل طلب

#### 3. `app/telemetry/metrics.py` — توسيع hist_names
- إضافة `"orchestrator.node.duration_seconds"` → `cogniforge_orchestrator_node_duration_seconds_bucket`
- يُغذّي لوحة latency في dashboard الخدمات المصغرة

#### 4. `observability/grafana/dashboards/50-microservices-transition.json` — dashboard جديد
- **15 panels** على Grafana :3001
- Row 1: Routing Mode gauge + Chat Requests by Target (timeseries) + Orchestrator Health
- Row 2: StateGraph Node Execution Rate + Node Latency (p50/p95/p99)
- Row 3: Tavily Search Outcomes + Research Agent Health + Orchestrator Startup State
- Row 4: Microservices Health Matrix (table — جميع الخدمات)
- Row 5: Fallback Chain Transition Progress (cumulative — يُظهر تقدم الانتقال)
- UID: `cogniforge-ms-transition-step2`

#### 5. `observability/prometheus/prometheus.yml` — scrape targets جديدة
- `orchestrator-service` → `host.docker.internal:8006/metrics`
- `research-agent` → `host.docker.internal:8007/metrics`
- `user-service` → `host.docker.internal:8001/metrics`
- `planning-agent` → `host.docker.internal:8002/metrics`
- جميعها `honor_labels: true` — تظهر DOWN حتى يُشغَّل `docker compose up`

#### 6. `tests/infrastructure/test_routing_policy.py` — 16 اختبار جديد
- `TestDefaultMode`: الوضع الافتراضي = state_graph
- `TestRollbackMode`: وضع التراجع = agent
- `TestUnknownMode`: قيم غير معروفة → state_graph
- `TestBreakglassMode`: وضع الطوارئ متعدد العناوين
- `TestEndpointMap`: التحقق من _ENDPOINT_MAP
- `TestFallbackAndContractVersion`: fallback وإصدار العقد

#### 7. `.github/workflows/microservices-transition.yml` — CI gate جديد
- 5 وظائف: routing-policy-gate / stategraph-compile-gate / dashboard-schema-gate / prometheus-config-gate / transition-gate
- يُشغَّل عند تعديل أي ملف يمس الخدمات المصغرة أو سياسة التوجيه
- يتحقق من: الوضع الافتراضي state_graph، StateGraph يُترجَم، dashboard JSON صالح، prometheus config صالح
- يُنشر ملخص في PR summary

### كيفية تفعيل الانتقال الكامل
```bash
# 1. تشغيل orchestrator-service
OPENROUTER_API_KEY="sk-or-v1-..." TAVILY_API_KEY="tvly-dev-..." \
docker compose -f docker-compose.yml up -d orchestrator-service postgres-orchestrator redis-orchestrator

# 2. ضبط ORCHESTRATOR_SERVICE_URL في بيئة المونوليث
export ORCHESTRATOR_SERVICE_URL=http://localhost:8006
# ORCHESTRATOR_CHAT_ENDPOINT=state_graph (افتراضي — لا حاجة لضبطه)

# 3. إعادة تشغيل المونوليث
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. التحقق من Grafana :3001 → dashboard "Microservices Transition — Step 2"
# Routing Mode يجب أن يظهر "STATE_GRAPH (active)"
# Orchestrator Service Health يجب أن يظهر "UP"

# 5. التراجع الفوري إذا لزم
export ORCHESTRATOR_CHAT_ENDPOINT=agent
```

### الملفات المعدّلة (5 ملفات — حد Jules)
- `app/infrastructure/clients/routing_policy.py`
- `app/infrastructure/clients/orchestrator_client.py`
- `app/telemetry/metrics.py`
- `observability/prometheus/prometheus.yml`
- `.memory/*`, `CLAUDE.md`

### الملفات الجديدة (2 ملفات)
- `observability/grafana/dashboards/50-microservices-transition.json`
- `tests/infrastructure/test_routing_policy.py`
- `.github/workflows/microservices-transition.yml`

---

---

## ✅ Session: 2026-05-10 — Orchestrator Revival Step 1 (خطوة انتقالية واحدة مؤكدة)

**Branch**: `feat/orchestrator-revival-step1`
**Mode**: Live runtime fixes — application code + configuration + tests.
**Verified live**: DB ✅ (2107 customer_messages, 19 users) | OpenRouter ✅ (200 OK) | Tavily ✅ (2 BAC results)

### الخطوة الانتقالية المختارة
إزالة ثلاثة حواجز تقنية تمنع تشغيل `orchestrator_service` (الخدمة المصغرة الأساسية):

### H1 — إضافة `TAVILY_API_KEY` لـ `docker-compose.yml` ✅
- `- TAVILY_API_KEY=${TAVILY_API_KEY:-}` في `orchestrator-service.environment`
- `- TAVILY_API_KEY=${TAVILY_API_KEY:-}` في `research-agent.environment`
- `TAVILY_API_KEY=` مع تعليق في `.env.docker`
- **التأثير**: `WebSearchFallbackNode` تستخدم Tavily بدلاً من التجاهل الصامت

### H2 — إصلاح DuckDuckGo Fallback ✅
- `ddgs>=6.0` أُضيف إلى `microservices/research_agent/requirements.txt`
- **التأثير**: لا `ImportError` عند غياب `TAVILY_API_KEY`

### H3 — إصلاح `cognitive_engine.memorize` NullPointerError ✅
- **الملف**: `microservices/orchestrator_service/src/core/gateway/simple_client.py:116`
- **السبب**: `get_cognitive_engine()` يُرجع `None` دائماً
- **الإصلاح**: `and self.cognitive_engine is not None` قبل `memorize`
- **التأثير**: لا `AttributeError` في كل استدعاء ناجح للنموذج

### اختبارات التحقق: 9/9 PASSED ✅
- `tests/microservices/orchestrator_service/test_orchestrator_revival.py`

### تحقق حي من الـ graph
```
Graph compiled: CompiledStateGraph — 13 nodes
['supervisor', 'query_rewriter', 'query_analyzer', 'retriever',
 'reranker', 'web_fallback', 'admin_agent', 'tool_executor',
 'chat_fallback', 'general_knowledge', 'synthesizer', 'validator']
```

### الملفات المعدّلة
- `docker-compose.yml`
- `microservices/research_agent/requirements.txt`
- `microservices/orchestrator_service/src/core/gateway/simple_client.py`
- `.env.docker`
- `tests/microservices/orchestrator_service/test_orchestrator_revival.py` (جديد)
- `.memory/*`, `CLAUDE.md`

---

## ✅ Session: 2026-05-09 (fifth pass) — Lifespan Orchestration Fix + Live Metrics

**Branch**: `fix/lifespan-orchestration-env-injection`
**Mode**: Live runtime diagnosis + application code fixes + documentation update.

### Root Cause Diagnosed (Live — Surgical Precision)

**ISS-034**: Uvicorn PID alive, port 8000 not listening, state file shows `app_healthy` from previous run.
- `devcontainer.json` maps `DATABASE_URL` from `${localEnv:DATABASE_URL}` — Ona/Gitpod does NOT inject secrets as process env vars.
- `supervisor.sh` created `.env` with `DATABASE_URL=sqlite+aiosqlite:///./dev.db` placeholder.
- `app/core/settings/base.py:23` reads `os.environ.get("APP_DATABASE_URL")` at **module import time** — before pydantic-settings reads `.env`. Finds empty string.
- `_ensure_database_url()` raises `ValueError` in `development` environment → uvicorn worker crashes on import → port 8000 never opens.
- Stale `app_healthy` state file → supervisor reports healthy. **Misleading observability confirmed live.**

**ISS-035**: Orchestrator lifespan warmup blocks ASGI startup indefinitely.
- `ainvoke()` with no timeout → could block forever on slow LLM/network.
- `RuntimeError` from warmup propagated up → crashed ASGI startup.
- `/health` returned `{"status":"ok"}` regardless of graph state.

### Fixes Applied

1. **`.devcontainer/supervisor.sh`**:
   - `_inject_env_secrets()` — reads real secrets from process env, writes to `.env` with priority logic.
   - `_export_env_file()` — exports `.env` keys into shell process before `python -m uvicorn`.
   - `_uvicorn_healthy()` — checks PID alive AND port responding; kills stale zombie before restart.
   - Health check step — always re-probes live endpoint; never trusts stale state files.
   - Degraded mode — no DATABASE_URL no longer crashes supervisor; Grafana + Prometheus stay up.
   - Completion message — shows actual `app_ready` state, not hardcoded "Verified".

2. **`microservices/orchestrator_service/main.py`**:
   - Warmup wrapped in `asyncio.wait_for(..., timeout=30.0)`.
   - All non-DB exceptions caught → logged as DEGRADED, not fatal.
   - `app.state.startup_state` tracks `"ready"` / `"degraded"`.
   - `/health` endpoint exposes `startup_state` and `startup_errors`.
   - 5-phase lifespan with clear Arabic docstring explaining criticality of each phase.

3. **`app/services/chat/local_graph.py`**:
   - `_supervisor_node`: emits `langgraph.intent.total`, `langgraph.node.count.total`, `langgraph.node.duration_seconds`.
   - `_chat_node`: emits `langgraph.node.count.total`, `langgraph.node.duration_seconds` on success and error.

4. **`app/telemetry/metrics.py`**:
   - `hist_names` extended with `langgraph.node.duration_seconds` → `cogniforge_langgraph_node_duration_seconds_bucket` now exported.

### Live Verification Results

| Check | Result |
|-------|--------|
| FastAPI `:8000/health` | `{"application":"ok","database":"ok"}` ✅ |
| Grafana `:3001/api/health` | `{"database":"ok"}` ✅ |
| Prometheus `/-/healthy` | `Prometheus Server is Healthy.` ✅ |
| Prometheus target `cogniforge-fastapi` | **UP** ✅ |
| Prometheus target `grafana` | **UP** ✅ |
| Prometheus target `prometheus` | **UP** ✅ |
| Next.js `:3000` | HTML confirmed ✅ |
| LangGraph metrics | `cogniforge_langgraph_intent_total{graph="local",intent="general"} 1.0` ✅ |

### Files Changed
- `.devcontainer/supervisor.sh` — env injection + zombie detection + degraded mode
- `microservices/orchestrator_service/main.py` — lifespan timeout + startup_state + /health
- `app/services/chat/local_graph.py` — LangGraph metric emission
- `app/telemetry/metrics.py` — histogram extension for langgraph metrics
- `.memory/runtime_truth.md` — full rewrite (fifth pass)
- `.memory/issues.md` — ISS-034, ISS-035 added
- `.memory/decisions.md` — D-024 through D-028 added
- `.memory/progress.md` — this entry
- `.memory/context.md` — updated
- `.memory/architecture_truth.md` — updated
- `CLAUDE.md` — §6.6 truth table + §6.8 new doctrine section

### What Was NOT Changed
- No test files
- No CI workflows
- No frontend code
- No database schema

---

## ✅ Session: 2026-05-09 (third pass) — Advanced LangGraph + Tavily Deep Investigation

**Branch**: `docs/advanced-langgraph-tavily-audit-2026-05-09`
**Mode**: Live runtime investigation + documentation update. No application code changed.

### What Was Investigated (Live Runtime — No Code Changes)

1. **Advanced orchestrator StateGraph (13 nodes)**:
   - `create_unified_graph()` compiles without error → `CompiledStateGraph` with 13 nodes
   - `graph.ainvoke(state)` with `OPENROUTER_API_KEY` → valid Arabic response in ~10s (confirmed live)
   - NOT on live call chain — `ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8006` → Docker DNS → ConnectError
   - `cognitive_engine.memorize` bug confirmed: `AttributeError: 'NoneType' object has no attribute 'memorize'` on primary model (non-blocking, fallback models handle)
   - `FlagEmbeddingReranker` not installed → `RerankerNode` falls back to simple score sort
   - Postgres checkpointer absent → graph compiled without checkpointer
   - 4-intent taxonomy: `educational`, `general_knowledge`, `admin`, `chat` (different from local graph's 3-intent)
   - DSPy usage confirmed: `IntentClassifier`, `QueryRewriterSignature`, `AnalyzeQuery`, `EducationalSynthesizer`

2. **Tavily integration**:
   - `tavily-python==0.7.24` installed, `TavilyClient` importable
   - Live search confirmed: `TavilyClient(api_key='tvly-dev-...').search('بكالوريا جزائر رياضيات')` → 2 results in <3s
   - Key format validation: must start with `tvly-`. MCP URL format auto-sanitized in `readiness.py` and `super_search.py`
   - `TAVILY_API_KEY` absent from `docker-compose.yml` (both `orchestrator-service` and `research-agent`)
   - Silent skip confirmed: `WebSearchFallbackNode` returns `{"used_web": False, "reranked_docs": []}` with no exception when key absent
   - Monolith does NOT use Tavily — `strategy_handlers.py:208` only checks for key as a warning, and `strategy_handlers.py` is on the PARTIAL (loaded-not-invoked) path

3. **DuckDuckGo fallback broken**:
   - `ddgs` package NOT installed → `ImportError` when `SuperSearchOrchestrator` initializes without Tavily
   - `DuckDuckGoSearchAPIWrapper` from `langchain_community` requires `ddgs`

4. **`WebSearchFallbackNode` call chain**:
   - Calls `research_client.deep_research()` → HTTP to `research-agent:8007` → ConnectError (DORMANT)
   - `research_client` base URL: `http://research-agent:8007` — Docker DNS, not running by default

5. **`TAVILY_API_KEY` in docker-compose.yml**:
   - Absent from `docker-compose.yml` (current version)
   - Only present in `docker-compose.legacy.yml:61` as `TAVILY_API_KEY: ${TAVILY_API_KEY:-}`
   - Must be added to both `orchestrator-service` and `research-agent` environment sections

### Files Updated
- `CLAUDE.md` — added §6.7 (Advanced LangGraph + Tavily doctrine), updated §6.6 truth table (rows 24, 24a, 24b), updated §10 env vars table
- `.memory/runtime_truth.md` — rows 24, 24a, 24b added/updated, architectural verdict updated, rules 11–15 added
- `.memory/architecture_truth.md` — component inventory updated, Transformation Gap updated, revival checklist added
- `.memory/decisions.md` — D-018, D-019, D-020 added
- `.memory/tasks.md` — H1–H4 tasks added (revival roadmap)
- `.memory/progress.md` — this entry

### What Was NOT Changed
- No application source code (`app/`, `microservices/`, `frontend/`)
- No test files
- No CI workflows
- No runtime behavior

---

## ✅ Session: 2026-05-09 — Full Live Runtime Investigation (Ona Agent)

**Branch**: `docs/live-runtime-audit-2026-05-09`

### What Was Investigated (Live Runtime — No Code Changes)
Full live runtime investigation with real DATABASE_URL and OpenRouter API key:

1. **DB connection verified**: PostgreSQL 17.6 Supabase, 19 users, 2098 customer_messages, 3038 admin_messages, 79 missions
2. **OpenRouter API verified**: 367 models, primary `nvidia/nemotron-3-super-120b-a12b:free`
3. **local_graph live call**: `run_local_graph('مرحبا', 9999)` → `'مرحبا! كيف يمكنني مساعدتك اليوم؟'`
4. **FastAPI startup verified**: 62 routes with real DB
5. **Port map corrected**: Next.js=3000 (supervisor.sh override), Grafana=3001 (provisioning CLI override), Prometheus=9090
6. **OTEL confirmed no-op**: `OTEL_EXPORTER_OTLP_ENDPOINT=http` is invalid URL
7. **Redis confirmed unused**: process running but `REDIS_URL` not set → InMemoryCache
8. **ZOMBIE/DORMANT re-verified**: KagentMesh, multi-agent workflow, MCP, LlamaIndex all confirmed dead

### Files Updated
- `.memory/runtime_truth.md` — 34 rows, full rewrite with live evidence
- `.memory/context.md` — stack table with live status, DB state, AI gateway details
- `.memory/architecture_truth.md` — port map, component inventory
- `.memory/logs.md` — session record
- `CLAUDE.md` — §6.6 truth table (34 rows), §3 architecture diagram, §1 port table


## ✅ Session: 2026-05-05 — Persistence Consolidation + Terminal-Event Guarantee + Markdown Cleanup

**Branch**: `claude/fix-persistence-consolidate-8X8LT`

### What Was Fixed
1. **ISS-014/015 (Dual-write & save authority)** — D-006 implemented as a hard
   contract in CLAUDE.md §6.5 + architecture test
   `tests/architecture/test_persistence_authority.py`. Monolith is sole writer;
   Orchestrator only persists when delegated and signals back via `persisted: true`.
2. **ISS-016 (Silent fallback failures)** — New `_emit_terminal_frames()` helper in
   both `customer_chat.py` and `admin.py` finally blocks. Exactly one terminal
   frame (assistant_final/error) per turn. `[CRITICAL_DATA_LOSS]` logging surfaces
   when fail-safe writes fail.
3. **ISS-017 (Terminal-event corruption)** — `normalize_streaming_event` now passes
   `complete`, `persisted`, `conversation_init` through unchanged when the unified
   envelope flag is on. Previously they were coerced to `assistant_delta` and the
   router's terminal-event detection silently broke.

### Files Touched
- `shared/chat_protocol/event_protocol.py` — pass-through for control events.
- `app/api/routers/customer_chat.py` — `_emit_terminal_frames` helper + finally restructure.
- `app/api/routers/admin.py` — `_emit_terminal_frames` helper + WRITE_DECISION logs + retry parity.
- `tests/architecture/test_persistence_authority.py` — new regression guard.
- `CLAUDE.md` — added §6.5 "Architecture Truth and Persistence Rules".
- `.memory/decisions.md` — D-006 marked IMPLEMENTED, D-009 added.
- `.memory/issues.md` — ISS-014/015/016/017 marked RESOLVED.

### Markdown Consolidation
Deleted ~38 legacy diagnosis/forensic markdown files at repo root. Their conclusions
already lived in `.memory/issues.md` and CLAUDE.md; the standalone files were
point-in-time snapshots that drift from reality. Kept canonical operational docs
(README, CHANGELOG, LICENSE, SECURITY, governance, ARCHITECTURE, AGENTS, ROADMAP,
LangGraph blueprint, replit.md, README_MIGRATIONS, scientific applications).

---

## ✅ Session: 2026-05-05 — Environment Documentation Correction

**Branch**: `claude/fix-duplicate-messages-nTEBj`
**Goal**: Correct the recorded runtime environment from Replit to GitHub Codespaces

### What Was Verified
- User confirmed they run the project via **GitHub Codespaces**, not Replit
- Inspected `.devcontainer/devcontainer.json` and `.devcontainer/docker-compose.host.yml`
- Confirmed devcontainer launches a single `web` container running `uvicorn app.main:app` via `.devcontainer/supervisor.sh`
- Confirmed microservices stack (`docker-compose.yml`) is **not** started by the devcontainer → orchestrator-service:8006 + 7 other services remain DORMANT exactly as documented for Replit
- Net effect on dual-write analysis: **identical to Replit** (Monolith is the sole writer; no dual-write physically possible without manually running the full microservices stack)

### What Was Updated
1. `CLAUDE.md` — sections 1, 6, 10, 13, 14 — Replit references replaced with Codespaces; added devcontainer paths and the explicit `docker compose -f docker-compose.yml up -d` escape hatch to wake microservices
2. `.memory/context.md` — Identity block now lists Codespaces, devcontainer file, supervisor script; env var table updated to reference Codespaces secrets and `OPENROUTER_SITE_URL`
3. `.memory/architecture.md` — Fallback 3 annotation now explains *why* the microservice is dormant (devcontainer scope)
4. `.memory/decisions.md` — D-001, D-002 reworded to be environment-agnostic with Codespaces as the concrete case
5. `.memory/issues.md` — ISS-001 fix instructions updated for Codespaces secrets; ISS-013 historical-vs-current framing
6. `.memory/tasks.md` — task #2 (SECRET_KEY) and task #8 (microservice DNS) updated for Codespaces context
7. `.memory/progress.md` — this entry
8. `.memory/logs.md` — session log entry

---

## Completed
- Delivered a full architectural dissection summary in `CLAUDE.md`.
- Synchronized `.memory` architecture/context/decisions/issues to match the updated narrative.
- Preserved hybrid control-plane/execution-plane interpretation.

## ✅ Session: 2026-05-09 — Architectural Intelligence Enrichment

**Branch**: (memory-only — no application code changed)
**Mode**: Diagnosis + memory evolution only. No runtime code changes.

### What Was Analyzed
Four systemic fragility patterns were discovered through deep code inspection and runtime testing:

1. **Intent routing semantic hijacking** (`app/services/chat/local_graph.py:_classify_intent`)
   - Runtime test confirmed: 10/10 non-academic questions containing educational keywords are misclassified as `educational`
   - Root cause: pure lexical regex, no semantic context, no conversation history
   - Hidden split-brain: zombie `IntentDetector` (13-intent taxonomy) vs live classifier (3-intent taxonomy) — incompatible if ever wired together
   - Intentional duplication between `local_graph.py` and `path_observer.py` — must be updated in sync

2. **Hidden DOM leakage** (`frontend/app/globals.css`, `CogniForgeApp.jsx`)
   - Both sidebars use `transform: translateX(±100%)` — visual hiding, not DOM exclusion
   - No `aria-hidden`, no `inert`, no `tabindex="-1"` on closed sidebars
   - `AgentTimeline` renders agent state into DOM regardless of sidebar visibility
   - Severity escalates as agent stack becomes more capable

3. **Runtime truth governance gap** (`scripts/runtime_truth.py`, `.github/workflows/runtime_truth.yml`)
   - CI enforces import + call chain (legs 1 and 2 of the triple)
   - Leg 3 (runtime evidence) is never verified in CI
   - No CI gate checks dashboard-metric contract (dashboard queries vs application emitters)
   - Lock file branch is stale (`jules-5513332666705839536-7e7df21b`)

4. **Zombie metrics + observability integrity** (`observability/grafana/dashboards/20-langgraph.json`)
   - 4 LangGraph dashboard metrics have zero emitters in the entire codebase
   - `local_graph.py` uses UnifiedObs spans (in-process), not OTel/Prometheus metrics
   - Dual-emission risk: WS turn metrics emitted through both OTel SDK and UnifiedObs simultaneously → double-counting when full stack is up
   - OTel setup is ACTIVE (imported + called) but is a no-op in default Codespaces — a fourth status tier not in the current taxonomy

### What Was Created / Updated
- **NEW**: `.memory/fragility-patterns.md` — 4 deep root-cause analyses with institutional lessons, anti-patterns, and fix strategies
- **UPDATED**: `.memory/issues.md` — added ISS-027 through ISS-031
- **UPDATED**: `.memory/decisions.md` — added D-013 through D-017
- **UPDATED**: `.memory/observability-topology.md` — zombie metric inventory + dual-emission risk section
- **UPDATED**: `.memory/context.md` — session note + documentation source of truth pointer
- **UPDATED**: `CLAUDE.md` — §6.14–§6.17 governance doctrine for all 4 patterns

### What Was NOT Changed
- No application source code (`app/`, `microservices/`, `frontend/`)
- No test files
- No CI workflows
- No runtime behavior

## ✅ Session: 2026-05-09 (second pass) — Live Architecture Audit + Memory Update

**Branch**: `docs/architecture-memory-audit-2026-05-09`
**Mode**: READ-ONLY investigation + documentation update. No application code changed.

### What Was Investigated
Live inspection of the running environment (no DATABASE_URL, no secrets):
1. FastAPI startup failure confirmed — uvicorn spawns then crashes at `AppSettings()` validation. Port 8000 not listening.
2. Grafana + Prometheus native binaries confirmed running (ports 3001 + 9090). Health checks pass. Prometheus shows `cogniforge-fastapi=0`.
3. Truth table lock drift confirmed — `scripts/runtime_truth.py --check` exits 1: `customer_chat_router: importer_count 6→5`. Root cause: `.orig` file counted in old lock. Component status unchanged.
4. `context_utils.py.orig` scratch artifact confirmed in `microservices/orchestrator_service/src/api/`.
5. `otel_setup.py` ACTIVE (no-op) tier formalised — import + call chain present, runtime effect absent without `OTEL_EXPORTER_OTLP_ENDPOINT`.

### What Was Updated
- `CLAUDE.md` — §0 (3 new doctrine rules), §6.6 truth table (otel_setup + Grafana/Prometheus native + FastAPI conditional rows), §6.22 (lock staleness), §6.23 (new audit section)
- `.memory/runtime_truth.md` — rows 30–32, extended status legend, branch ledger
- `.memory/observability_truth.md` — Grafana/Prometheus native rows, otel_setup correction
- `.memory/issues.md` — ISS-032 (truth table drift), ISS-033 (context_utils.py.orig)
- `.memory/context.md` — session note
- `.memory/progress.md` — this entry

### What Was NOT Changed
- No application source code, no tests, no CI workflows, no runtime behavior
- All 29 prior truth table rows remain valid — no status promotions or demotions

---

## ✅ Session: 2026-05-11 — Live Runtime Audit D-043 + Full Stack Verification

**Branch**: `feat/live-runtime-audit-d043`
**Mode**: Live HTTP probes + documentation update. No application code changed.

### What Was Verified (Live)

All 8 uvicorn processes confirmed running via `ps aux`. All 12 Prometheus scrape targets UP. All 16 Grafana dashboards active.

| Service | Port | Health Response | Metrics |
|---------|------|----------------|---------|
| monolith | 8000 | `{"application":"ok","database":"ok","version":"v4.1-root"}` | UP |
| user-service | 8001 | `{"service":"user-service","status":"ok"}` | UP (step=5) |
| planning-agent | 8002 | `{"service":"planning-agent","status":"ok","database":"sqlite+aiosqlite:///:memory:"}` | UP (step=6) |
| conversation-service | 8003 | `{"status":"healthy","graph_ready":true,"step":"12"}` | UP (step=12) |
| orchestrator-service | 8006 | `{"status":"ok","graph_ready":true,"startup_state":"ready"}` | UP (step=10) |
| research-agent | 8007 | `{"status":"healthy","tavily_available":"false","step":"7"}` | UP (step=7) |
| reasoning-agent | 8008 | `{"status":"healthy","llm_backend":"mock","mcts_enabled":"true","step":"8"}` | UP (step=8) |
| content-retrieval-skill | 8009 | `{"status":"healthy","kb_files":2,"step":"11"}` | UP (step=11) |

### API Contract Findings (live probes)

- `POST /agent/chat` (orchestrator:8006) → 401 without JWT. Requires `question` field (not `message`) + integer `user_id`.
- `POST /chat/message` (conversation-service:8003) → 422 with `message` field. Requires `question` field.
- `POST /plans` (planning-agent:8002) → 401 without `X-Service-Token` JWT header.
- `POST /execute` (research-agent:8007) → 422 without `caller_id` + `action` fields.
- `POST /execute` (reasoning-agent:8008) → 422 without `caller_id` + `action` + `query` fields.
- `POST /compose` (orchestrator:8006) → works without auth, returns `pipeline_mode=fallback` (skills in fallback mode without LLM keys in env).

### Live Metrics Sample

```
cogniforge_outbox_relay_cycles_total{result="success"} 6.0
cogniforge_pipeline_invocations_total{mode="fallback"} 1.0
cogniforge_checkpointer_backend_info{backend="postgres",step="10",tables_ready="true"} 1.0
cogniforge_orchestrator_startup_info{graph_ready="true",outbox_relay_enabled="true"} 1.0
```

### What Was Updated

- `CLAUDE.md` — §3 (Architecture at a Glance), §14 (Microservices Live Status), §6.25 (new audit section with full Prometheus targets + Grafana dashboards + metrics sample + known gaps)
- `.memory/runtime_truth.md` — Grafana dashboard count (13→16), Prometheus target count (10→12), branch updated
- `.memory/progress.md` — this entry

### What Was NOT Changed

- No application source code, no tests, no CI workflows, no runtime behavior

---

## ✅ Session: 2026-05-11 — ISS-046 Surgical Fixes + Full Pipeline Verified

### Summary

Full live verification with real API keys (OPENROUTER + TAVILY + Supabase). Four surgical fixes applied to `supervisor.sh` and `secrets.env.example`. Skills Pipeline confirmed at `pipeline_mode="full"` with real LLM responses in Arabic.

### Fixes Applied

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| ISS-046-A | orchestrator started without `CODESPACES=true` → Docker hostnames | Restarted with correct env; supervisor.sh already correct |
| ISS-046-B | research/reasoning agents started without API keys | `uvicorn` → `nohup python -m uvicorn`; port 6543→5432 for research DB |
| ISS-046-C | planning-agent used SQLite (port 6543 not converted) | Added `sed 's/:6543\//:5432\//'` to `launch_planning_agent()` |
| ISS-046-D | `secrets.env.example` missing `TAVILY_API_KEY` | Added entry to example file |

### Live Verification Results (2026-05-11)

```
POST /compose → pipeline_mode="full", skills_active=["planning","research","reasoning"]
                composed_answer=<real Arabic LLM response>, total_ms=39590

research-agent  /health → tavily_available="true"
reasoning-agent /health → llm_backend="openrouter"
planning-agent  /health → database="postgresql+asyncpg://..."

Prometheus: 12/12 targets UP
cogniforge metrics: 79 active
cogniforge_pipeline_invocations_total{mode="full"} 2.0
```

### Files Changed

- `.devcontainer/supervisor.sh` — 3 surgical fixes (ISS-046-B, ISS-046-C)
- `.devcontainer/secrets.env.example` — added `TAVILY_API_KEY` (ISS-046-D)
- `CLAUDE.md` — ISS-046 entry + updated service matrix (fallback→full)
- `.memory/issues.md` — ISS-046-A/B/C/D documented
- `.memory/progress.md` — this entry
- `observability/grafana/dashboards/150-microservices-master-overview.json` — new master dashboard

---

## ✅ Session: 2026-05-12 — ISS-STREAM-001 Streaming Fix

### Summary
إصلاح جراحي شامل لمشكلة البث الكارثية — الكلمات تظهر دفعة واحدة بدل كلمة بكلمة.

### Root Causes Fixed (4 new)
1. `_normalize_stream_event` يُحوّل أحداث التحكم إلى `assistant_delta` → نصوص غريبة
2. `_generator_with_persistence` لا يجمع الـ deltas → لا يُحفظ شيء في DB
3. `mergeAssistantContent` منطق خاطئ → chunks تُتجاهل أو تُكرَّر
4. `print()` debug statements في graph nodes

### Files Changed
- `app/infrastructure/clients/orchestrator_client.py` — `_PASSTHROUGH_EVENT_TYPES` + noop filter
- `app/api/routers/customer_chat.py` — noop filter
- `app/api/routers/admin.py` — noop filter
- `microservices/orchestrator_service/src/api/routes.py` — `delta_parts` accumulator
- `microservices/orchestrator_service/src/services/overmind/graph/main.py` — print → logger.debug
- `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py` — print → logger.debug
- `frontend/app/hooks/useAgentSocket.js` — mergeAssistantContent + assistant_final handler
- `.runtime/truth_table.lock.json` — updated after customer_chat_router change

### New Files
- `.github/workflows/streaming-fix-gate.yml` — CI gate (4 jobs)
- `observability/grafana/dashboards/160-streaming-metrics.json` — 11 panels

### Verification
- `ruff check . ✅ | ruff format --check . ✅`
- `runtime_truth --check ✅`
- `guardrails ✅ | route_registry ✅ | tracing_gate ✅`
- 18 Grafana dashboards | 12 Prometheus targets

---

## ✅ Session: 2026-05-12 — ISS-STREAM-002: Word-by-Word Streaming Fix (3 Root Causes)

### Problem
البث يتوقف عند `phase_start` → 0 delta chunks → timeout كارثي. حتى بعد ISS-STREAM-001.

### Root Causes Found & Fixed
1. **`ChatCompletionChunk` vs dict**: `stream_chat()` يُعيد OpenAI SDK objects لكن الكود يستخدم `chunk.get()` → `AttributeError` صامت → 0 chunks.
2. **LangGraph 1.2.0 `astream_events` bug**: `on_custom_event` لا يُطلق أبداً رغم أن `stream_writer()` يعمل. الحل: `astream(stream_mode=["custom","updates"])`.
3. **نموذج لا يدعم streaming**: `nvidia/nemotron-3-super-120b-a12b:free` → 1 chunk فقط. الحل: `deepseek/deepseek-chat` → 47-177 chunks.

### Files Changed
- `microservices/orchestrator_service/src/services/llm/client.py` — `extract_stream_content()` static method
- `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py` — استخدام `extract_stream_content()`
- `microservices/orchestrator_service/src/services/overmind/graph/main.py` (ChatFallbackNode) — استخدام `extract_stream_content()`
- `microservices/orchestrator_service/src/services/overmind/graph/search.py` (SynthesizerNode) — streaming عند `reranked=[]` + `extract_stream_content()`
- `microservices/orchestrator_service/src/api/routes.py` — `astream(stream_mode=["custom","updates"])` في `_run_chat_langgraph` + `_stream_chat_langgraph`
- `microservices/orchestrator_service/src/core/prom_metrics.py` — 4 streaming metrics جديدة
- `app/core/ai_config.py` — `deepseek/deepseek-chat` كنموذج افتراضي

### New Files
- `observability/grafana/dashboards/170-streaming-iss-stream-002.json` — 9 panels, UID `cogniforge-streaming-002`

### Verification (Live)
- **122-177 word-by-word chunks** per response ✅
- `cogniforge_streaming_chunks_total{channel="http",node="synthesizer"} 122.0` ✅
- E2E WebSocket test: 177 chunks, 827 chars, 14s ✅
- Prometheus: 10/12 targets UP (content-retrieval-skill + conversation-service DOWN — not started)

---

## ✅ Session: 2026-05-13 — BAC Live Test + WebSocket Auth Fixes (ISS-052)

### ما تم التحقق منه
تجريب حي كامل لتمرين الدوال العددية 2016 الموضوع الثاني التمرين الرابع الدورة الأولى عبر WebSocket بحساب الطالب العادي (`STANDARD_USER`).

### نتائج التشخيص (4 تجارب على conversation_id: 448/449)
| التجربة | النتيجة | الحجم | Chunks |
|---------|---------|-------|--------|
| T1 نص التمرين الكامل | ✅ I+II+III بدون YAML وبدون إجابة نموذجية | 2925 حرف | 108 |
| T2 السؤال الأول بدون حل | ✅ نص السؤال فقط بدون أي حسابات | 767 حرف | 100 |
| T3 شرح مفصل حسب المنهجية | ✅ يصل إلى نتائج الإجابة النموذجية | 3717-7397 حرف | streaming |
| T4 شرح شرح (تعمق أكثر) | ✅ مبررات رياضية كاملة | 14323-14868 حرف | streaming |

### أخطاء WebSocket تم توثيقها (ISS-052 — 5 root causes)
1. **ISS-052-A**: المحادثة WebSocket فقط — لا `POST /api/chat/messages`
2. **ISS-052-B**: websockets v16 → `from websockets.asyncio.client import connect`
3. **ISS-052-C**: token في `subprotocols=["jwt", TOKEN]` وليس Authorization header
4. **ISS-052-D**: payload مُدمَج تحت `event["payload"]` وليس flat
5. **ISS-052-E**: token صلاحيته 30 دقيقة — يجب تجديده

### Artefacts جديدة
- `tests/integration/test_bac_exercise_websocket.py` — 6 اختبارات تكاملية رسمية
- `CLAUDE.md §6.30` — بروتوكول WebSocket الصحيح موثَّق
- `.memory/issues.md` — ISS-052 موثَّق

---

## ✅ Session: 2026-05-13 — ISS-053: BAC Exercise Explanation Hallucination Fix

### المشكلة
طلبات "اشرح تمرين الدوال العددية 2016" كانت تُهلوس — LLM يُرجع تمرين احتمالات أو يقول "لا أملك التفاصيل".

### السبب الجذري
`detect_exercise_retrieval` تُلغي الاسترجاع عند وجود "اشرح" (explanation_intent) → يذهب الطلب إلى LangGraph بدون محتوى التمرين → هلوسة.

### الحل: مسار ثالث "شرح مع سياق" (fallback_path=2.5)

| الملف | التعديل |
|-------|---------|
| `exercise_retrieval.py` | `detect_explanation_with_context()` + `ExplanationWithContextDecision` + 35 نمط |
| `local_graph.py` | `run_local_graph_with_exercise_context()` + `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` |
| `orchestrator_client.py` | `_stream_exercise_explanation_response()` في fallback chain |
| `ai_config.py` | 5 نماذج احتياطية مُتحقَّق منها حياً |

### Fallback chain المحدَّث
`file_intelligence(1) → exercise_retrieval(2.0) → exercise_explanation_with_context(2.5) → LangGraph(3.0) → general_chat(4.0)`

### نتائج الاختبار الحي
| الاختبار | النتيجة |
|---------|---------|
| جلب نص التمرين | ✅ 2913 حرف، بدون إجابة نموذجية |
| شرح مع سياق — full_content | ✅ 9670 حرف (نص + إجابة نموذجية) |
| شرح حي مع LLM | ✅ يذكر g(x)، لا هلوسة احتمالات، LaTeX صحيح |
| الشرح العام لا يُفعِّل المسار | ✅ يذهب للـ LangGraph كالمعتاد |

---

## ✅ Session: 2026-05-22 — Protocol V34.0: Contextual Unmuzzle & The Teacher's Voice

- **المهمة**: كسر حلقة الكبح النصي (Muzzle) عند حيرة الطالب في المسائل المعقدة.
- **الإصلاح (D-083)**:
    - تعديل `orchestrator_client.py`: تعطيل `terminate_pipeline` تلقائياً عند كشف `is_confusion`.
    - تعديل `doctrine.py`: ترقية `EXPLANATION_DOCTRINE` إلى v2.1.0 وإضافة قواعد "صوت الأستاذ" (السرد العميق، التشبيهات، تفسير الـ Why).
- **النتيجة**: عند قول الطالب «لم أفهم»، يبث النظام المكوّن البصري ويتبعه فوراً بشرح سردي مفصل من الـ LLM يربط المنطق بالتمثيل البصري.
- **الملفات**: `orchestrator_client.py` + `doctrine.py`.

---

## ✅ Session: 2026-05-23 — Protocol V38.0: Dual-Mode Routing (D-085)

- **المهمة**: إصلاح فجوة V34.0 — الكبح النصي كان يُوقف المسار حتى عند حيرة الطالب في السحب العادي (combinations/tree)، لأن الكشف كان مقيّداً بـ `_is_confusion AND _is_impossible`.

- **الإصلاح (D-085)**:
  - نقل قرار التوجيه إلى داخل `_build_calculated_ui`: يكشف `is_confusion` قبل بناء الحمولة ويُضيف `routing_mode: "MODE_A" | "MODE_B"` لكل مكوّن.
  - `terminate_pipeline = not _is_deep_pedagogy` لجميع أنواع المكوّنات الأربعة.
  - `chat_with_agent` يقرأ `routing_mode` مباشرة — مصدر حقيقة واحد.
  - `_effective_question` في MODE_B يُضيف تعليمة سقراطية قبل السؤال لكل مسارات الـ fallback.
  - V28.0/V30.0 لا يزالان ساريَين في MODE_A.

- **الاختبارات**:
  - 17 اختباراً جديداً في `tests/services/test_v38_dual_mode_routing.py`.
  - تحديث `test_v28_text_wall_muzzle.py` و`test_generative_ui_streaming.py`.
  - 827 اختباراً تجتاز، فشلان موجودان مسبقاً (غير مرتبطَين).

- **التحقق الحي** (`openai/gpt-oss-20b:free`):
  - 7/7 حالات توجيه صحيحة.
  - MODE_B: LLM يفتح بـ `تخيل أن لديك كيساً...` — معنى أولاً، لا LaTeX.

- **الملفات**: `app/infrastructure/clients/orchestrator_client.py` | `tests/services/test_v38_dual_mode_routing.py` | `tests/services/test_v28_text_wall_muzzle.py` | `tests/contracts/test_generative_ui_streaming.py` | `CLAUDE.md` | `.memory/decisions.md` | `.memory/progress.md`.

---

## D-086 · Protocol V46.0 — Dual-Channel Firewall (2026-05-23)

- **المشكلة**: القناة B (صوت المعلم) بلا حماية — الـ LLM يمكنه إخراج HTML/JSX داخل النص السردي. لا آلية لمنع تسرب المواضيع.

- **الإصلاح (D-086)**:
  - **OutputFirewall** (`app/services/skills/output_firewall.py`): Skill جديد يفرض الفصل الصارم.
    - القناة B: 6 أنماط regex مُرجَّحة. تنظيف إذا score < 0.6، رفض إذا score ≥ 0.6. Fail-open دائماً.
    - القناة A: يرفض أي نثر لا يبدأ بـ `{` أو `[`.
  - **TopicLock** (`app/services/skills/topic_lock.py`): Skill تحذيري يكشف تسرب المواضيع (احتمالات → تفاضل). يُسجِّل دون رفض.
  - **نقاط التطبيق**: `local_graph.py:_chat_node` + `customer_chat.py:complete_ai_response`.

- **الاختبارات**:
  - 25 اختباراً في `tests/test_output_firewall_v46.py` — جميعها تجتاز.
  - تحقق حي: `<div>` يُنظَّف، JSX ثقيل يُرفض، LaTeX لا يُعتبر تلوثاً.

- **الملفات**: `app/services/skills/output_firewall.py` (جديد) | `app/services/skills/topic_lock.py` (جديد) | `app/services/skills/__init__.py` | `app/services/chat/local_graph.py` | `app/api/routers/customer_chat.py` | `tests/test_output_firewall_v46.py` | `CLAUDE.md` | `.memory/decisions.md` | `.memory/progress.md`.


