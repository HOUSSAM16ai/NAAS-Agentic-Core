# Architectural Decisions
> Last updated: 2026-05-12 | Branch: `claude/setup-microservices-monitoring-ralbR`

## D-048 · DSPy/raw-OpenAI Streaming via Custom Events (2026-05-12 — same branch)

**Context**: D-047 plugged the streaming gap on (a) the local monolith fallback and (b) any future LangChain-`ChatOpenAI` node in the orchestrator. But the production hot path — `orchestrator-service:8006` StateGraph (13 عقدة) — uses **DSPy 3.x** (`dspy.Predict`, `dspy.ChainOfThought`) wrapped around **raw `openai.AsyncOpenAI`**. `astream_events(version="v2")` does NOT emit `on_chat_model_stream` for raw OpenAI calls or for DSPy modules, so even after D-047 the user still saw the entire reply land in a single `assistant_final` burst on the default path.

**Decision**: Use LangGraph's `get_stream_writer()` + `astream_events`'s `on_custom_event` channel to expose token-level deltas from the 3 user-facing leaf nodes — surgically, without disturbing DSPy signatures or the rest of the graph.

**Hybrid pattern (every refactored node)**:

```python
@staticmethod
def _get_writer():
    try:
        from langgraph.config import get_stream_writer
        return get_stream_writer()
    except Exception:
        return None

async def __call__(self, state):
    writer = self._get_writer()
    if writer is not None:
        # STREAMING path — raw OpenAI SSE + custom events
        parts = []
        async for chunk in ai_client.stream_chat(messages):
            delta = chunk["choices"][0]["delta"].get("content")
            if not delta:
                continue
            parts.append(delta)
            writer({"chunk_type": "assistant_delta", "content": delta, "node": "<name>"})
        full_text = "".join(parts).strip()
        # ... build final state dict from full_text ...
    else:
        # Non-streaming path — DSPy / send_message (preserves CoT signature, batch/test mode)
        prediction = await anyio.to_thread.run_sync(lambda: self.generator(...))
        full_text = prediction.response.strip()
    return {"final_response": full_text, "messages": [AIMessage(content=full_text)]}
```

`get_stream_writer()` returns `None` when the graph is invoked via `ainvoke()` (batch / tests), so DSPy still runs there — no regression in unit tests, no change to non-streaming callers.

When the graph runs via `astream_events(version="v2")`, every `writer({...})` call surfaces as `on_custom_event` with the dict as `event["data"]`. `routes.py` now listens for both `on_chat_model_stream` (D-047 path) AND `on_custom_event` (D-048 path) and forwards either to `assistant_delta`.

**Nodes refactored**:

| Node | File | Purpose | DSPy preserved? |
|---|---|---|---|
| `GeneralKnowledgeNode` | `general_knowledge.py` | General-knowledge questions | N/A (uses `send_message` in non-stream) |
| `ChatFallbackNode` | `main.py` | Greeting/chat fallback | Yes (`dspy.Predict(ChatFallbackSignature)` in non-stream) |
| `SynthesizerNode` | `search.py` | BAC educational synthesis with `EducationalSynthesizer` signature | Yes (`dspy.Predict(EducationalSynthesizer)` in non-stream) |

`SynthesizerNode` was the most intricate: it returns a structured JSON object (`{"المصدر","التمرين",...}`) with the synthesized text inside `"التمرين"`. The streaming path now constructs the same JSON envelope, but the `"التمرين"` field is filled by concatenating the streamed chunks at the end. Each chunk also flows to the user via `assistant_delta` as it arrives, so the UI renders the long-form Arabic explanation word-by-word while the JSON envelope reaches the persistence layer intact.

**`routes.py` consumer side (3 sites patched)**:
- HTTP `/api/chat/messages` streaming generator
- Customer WS `/api/chat/ws` worker task
- Admin WS `/admin/api/chat/ws` streaming response

Each site already had the `on_chat_model_stream` branch from D-047 (kept as insurance for future LangChain-`ChatOpenAI` migrations). A sibling `on_custom_event` branch was added that reads `event["data"]["content"]` and emits the same `{"type": "assistant_delta", "payload": {"content": str}}` envelope. The existing `streamed_chars` counter and the duplicate-suppression contract (`assistant_final.payload.content = ""` when `streamed_chars > 0`) automatically cover both paths.

**Net effect**:

| Path | Before D-047 | After D-047 only | After D-048 |
|---|---|---|---|
| Monolith local fallback (`local_graph`) | one big `assistant_delta` | ✅ word-by-word | ✅ word-by-word |
| Orchestrator (DSPy + raw OpenAI) — production default | one big `assistant_final` | ❌ still bursting | ✅ word-by-word |
| Orchestrator (future LangChain `ChatOpenAI` migration) | one big `assistant_final` | ✅ word-by-word | ✅ word-by-word |
| Admin WS (DSPy + raw OpenAI) | one big `assistant_delta` after `[DB SAVED]` | ❌ still bursting | ✅ word-by-word |

**Files changed**:
- `microservices/orchestrator_service/src/services/overmind/graph/general_knowledge.py` — hybrid streaming path
- `microservices/orchestrator_service/src/services/overmind/graph/main.py` — `ChatFallbackNode` hybrid streaming
- `microservices/orchestrator_service/src/services/overmind/graph/search.py` — `SynthesizerNode` hybrid streaming (most complex due to JSON envelope)
- `microservices/orchestrator_service/src/api/routes.py` — `on_custom_event` consumer added at 3 sites

**Time-to-first-word**: expected ~800ms (limited by OpenRouter first SSE chunk) — down from 25–40s burst.

**Risks and mitigations**:
- `get_stream_writer()` is documented in LangGraph 0.2.39+ (requirements.txt pins `langgraph>=0.2.39,<2.0.0`). If a future version removes it, the `try/except` falls back to `None` and DSPy still produces the final response — no streaming, no regression.
- `on_custom_event` requires `astream_events(version="v2")`. The orchestrator already uses v2 at all three sites — verified by grep.
- The duplicate-suppression contract (D-047) applies unchanged: if any chunks streamed, `assistant_final.payload.content = ""`. UI sees no duplication.

**Status**: IMPLEMENTED 2026-05-12 — pending live verification in Codespaces with real secrets.

**Rules added**:
1. Any orchestrator graph leaf node that emits a `final_response` to the user MUST attempt `get_stream_writer()` and stream via custom events when available. DSPy non-streaming remains the fallback for batch/test.
2. `routes.py` MUST listen for both `on_chat_model_stream` and `on_custom_event` to cover both LangChain-native and DSPy/raw-OpenAI nodes.
3. The `{"chunk_type": "assistant_delta", "content": str, "node": str}` envelope is the canonical custom-event shape — do not invent variants. The `node` field is for telemetry only; routes.py ignores it.

---

## D-047 · Streaming Bottleneck Eliminated — Token-Level WS Deltas (2026-05-12)

**Decision**: تصفية "Streaming Event Bottleneck" في الـ 3 طبقات (monolith + orchestrator HTTP + orchestrator WS) لتمكين typing-effect كلمة بكلمة على الواجهة، بدل تجميع الرد ثم إرساله دفعة واحدة كارثية.

**Root causes (مثبَتة سابقاً في `.memory/streaming_architecture_breakdown.md`)**:
1. **Monolith**: `app/services/chat/local_graph.py::run_local_graph` كان يستخدم `graph.ainvoke(...)` الذي يحبس التنفيذ حتى نهاية الرد بالكامل ثم يُرجِع نصاً واحداً. `OrchestratorClient._build_local_graph_response` كان يأخذ هذا النص ويُصدِر `assistant_delta` واحداً ضخماً + `assistant_final` فارغاً.
2. **Orchestrator microservice**: `microservices/orchestrator_service/src/api/routes.py` كان يستخدم `astream_events(..., version="v2")` صحيحاً، لكن أحداث `on_chat_model_stream` كانت **مُتجاهَلة صراحةً** (`pass`) — تبتلع كل token deltas. ينتظر `on_chain_end` ثم يُرسل النص كاملاً كـ `assistant_final`.
3. **Frontend**: `mergeAssistantContent` يعمل بشكل صحيح، لكنه يعتمد على وصول `assistant_delta` متعددة — لم تكن تصله.

**Architecture (post-fix)**:

```
المستخدم
   │
   ▼  WebSocket /api/chat/ws  ──────────────────────────────────────
   │
   ▼ customer_chat.py (no change — already forwards each event)
   │
   ├──[1] orchestrator-service:8006 reachable
   │        │
   │        ▼ /api/chat/messages (HTTP NDJSON) OR /api/chat/ws
   │        │   astream_events(version="v2")
   │        │     ├── on_chain_start  → phase_start
   │        │     ├── on_chat_model_stream → assistant_delta (D-047 NEW — token-level)
   │        │     ├── on_chain_end    → phase_completed + final aggregation
   │        │     └── final           → assistant_final (content="" if streamed_chars>0)
   │        │
   │        └── streamed_chars metadata attached for client observability
   │
   └──[2] Fallback (orchestrator unreachable):
            ├── _stream_local_graph_response()   ── D-047 NEW
            │     └── run_local_graph_stream() → OpenRouterClient.stream_chat() → yield content
            │           → emits N × assistant_delta + 1 × assistant_final(content="")
            └── _stream_local_general_chat_response()  ── D-047 NEW
                  └── direct OpenRouterClient.stream_chat() with general system prompt
```

**Duplicate-suppression contract (NEW)**:
- إذا بُثَّت أي قطعة عبر `assistant_delta` token-level خلال الـ turn، فإن `assistant_final.payload.content` يجب أن يكون `""` بدلاً من النص الكامل، لمنع `mergeAssistantContent` من إظهار الرد مرتين.
- `streamed_chars` يُعلَّق على `assistant_final.payload` للقياس وللتتبع.

**Why bypass LangGraph for the local stream path?**: `OpenRouterClient` ليس `BaseChatModel` من LangChain، فلا تُولِّد `astream_events` أحداث `on_chat_model_stream`. الطريق الأسرع والأبسط: تشغيل `_classify_intent` يدوياً واستدعاء `stream_chat` مباشرة. زمن أول-قطعة ينخفض إلى ~1s.

**Files changed**:
- `app/services/chat/local_graph.py` — أضيفت `run_local_graph_stream` (AsyncGenerator[str, None]) + استيراد `AsyncGenerator`
- `app/infrastructure/clients/orchestrator_client.py` — أضيفت `_stream_local_graph_response` و `_stream_local_general_chat_response`؛ مسار LangGraph المحلي ومسار general_chat في `chat_with_agent` أُعيدا كتابةً ليبثا token-by-token
- `microservices/orchestrator_service/src/api/routes.py` — التقاط `on_chat_model_stream` في 3 مواقع (HTTP /api/chat/messages، WS /api/chat/ws، WS /admin/api/chat/ws) + duplicate-suppression في الـ assistant_final

**Observability**:
- مقياس جديد: `cogniforge_ws_chat_delta_total{path="local_graph_stream"}` — عدّاد القطع الـ token-level من المسار المحلي
- موجود سابقاً: `cogniforge_ws_chat_turn_duration_seconds`, `cogniforge_ws_chat_terminal_events_total` (path_observer.py) — تستمر بالعمل بدون تغيير
- مقياس جديد في الـ orchestrator: `streamed_chars` على كل `assistant_final.payload` كحقل metadata (ليس Prometheus metric)

**ما لم يتغير (مقصوداً)**:
- `frontend/app/hooks/useAgentSocket.js` — يعمل بشكل صحيح أصلاً، البق كان 100% backend
- D-006 persistence semantics — `persisted=true/false` بدون تغيير
- `_emit_terminal_frames` single-emitter rule — بدون تغيير
- `microservices/conversation_service` — لا يزال يستخدم `ainvoke` لأنه ليس على المسار الحي للمستخدم اليوم؛ سيُحَدَّث عند تفعيله

**Verification commands**: في `streaming_architecture_breakdown.md` تحت "D-047 Implementation Report".

**Status**: IMPLEMENTED 2026-05-12 — branch `claude/setup-microservices-monitoring-ralbR`. **Pending live verification** في Codespaces مع الأسرار الحقيقية.

**Rules added (must remain true forever)**:
1. أي LangGraph runtime موجَّه للـ user-facing real-time chat **يجب** أن يستخدم `astream_events(version="v2")` (أو AsyncGenerator مكافئ) — `ainvoke()` ممنوع على المسار الحي.
2. أي مكان يلتقط `on_chat_model_stream` **يجب** أن يُصدِر `assistant_delta` فوراً بدون buffering.
3. عند بث الـ token deltas، الـ `assistant_final.payload.content` يجب أن يكون `""` — مخالفة هذا تُسبب double-rendering.
4. `path_observer.WsTurnSpan` المُنفَّذ منذ §6.10 يبقى المنتج الوحيد لـ WS turn metrics — لا تكسر هذا العقد.

---

## D-046 · Dashboard Zombie-Metric Sweep + CI YAML Repair (2026-05-12)
**Decision**: إلغاء 4 مقاييس zombie من 3 لوحات Grafana واستبدالها بمقاييس حقيقية موجودة في الكود، وإصلاح 3 ملفات GitHub Actions كانت تحوي Python heredoc بمسافة بادئة خاطئة (يقاطع YAML block scalar).

**Scope**:
1. **Dashboard ↔ emitter contract** — مسح شامل عبر 17 لوحة Grafana لـ 94 مقياسًا فريدًا. 4 منها كانت تستعلم عن أسماء لا يُصدِرها أي ملف في `app/` أو `microservices/`:
   - `cogniforge_langgraph_checkpointer_writes_total` (في `20-langgraph.json`) → استبدلت بـ `cogniforge_checkpointer_writes_total{status,thread_id_prefix}` المنبعث فعلاً من `microservices/orchestrator_service/src/core/prom_metrics.py:246` (Step 10 — Postgres checkpointer).
   - `cogniforge_tavily_search_total` (في `60-microservices-step3-live.json` و `50-microservices-transition.json`) → استبدلت بـ `cogniforge_research_tavily_calls_total` المنبعث من `microservices/research_agent/prom_metrics.py:115`.
   - `cogniforge_orchestrator_startup_ready` (في `50-microservices-transition.json`) → استبدلت بـ `max(cogniforge_orchestrator_startup_info{graph_ready="true"})`.
   - بُعد `{result="skipped_no_key"}` على `cogniforge_tavily_search_total` لم يكن له وجود إطلاقاً → استبدل بـ `cogniforge_research_startup_info{tavily_available="false"}`.

2. **YAML heredoc fix** — `microservices-step4.yml` و `microservices-step5-user-service.yml` و `microservices-step6-planning-agent.yml` كانت تستخدم `python3 -c "..."` بمحتوى Python بمسافة بادئة صفر داخل بلوك `run: |`. `yaml.safe_load` كان يرفضها — GitHub Actions ربما تساهَل، لكن البوابة كانت هشة بنيوياً. الحل: تحويل كل كتلة إلى `python3 <<'PY' ... PY` bash heredoc بمسافة بادئة صحيحة. عند تمرير متغيرات شِل، استُعملت `ENV=val python3 <<'PY' ... os.environ['ENV'] ... PY` بدل الاستبدال النصي.

3. **github-script template literal fix** — `microservices-step4.yml` كان يحوي قالب JavaScript multi-line ضمن `actions/github-script@v7` بأسطر Markdown غير مُحاذاة. حُوِّل إلى `[...].join('\n')` array لإبقاء YAML block scalar متناسقاً.

**Result**:
- ✅ 94/94 dashboard metrics لها emitter حقيقي (كانت 90/94)
- ✅ 21/21 GitHub Actions workflow تُحلَّل YAML بنجاح (كانت 18/21)
- ✅ ruff: 0 errors (كانت 2)
- ✅ runtime truth lock re-generated 2026-05-12 (كانت stale من 2026-05-08)
- ✅ Skills Architecture replay: 7/7 skills مع ≥ 7 metrics + `/health` + 0 cross-skill imports + 12 prom targets + 17 dashboards

**Status**: IMPLEMENTED 2026-05-12 — branch `claude/setup-microservices-monitoring-ralbR`.

**Caveat**: السندبوكس بدون شبكة خارجية. الأسرار (`OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `DATABASE_URL`) ستُمارَس من قِبَل CI على GitHub. الاستنتاجات بشأن وضع الـ pipeline (`full`/`partial`/`fallback`) في الإصدار الحي تبقى مرجعها D-043/D-044/D-045 من 2026-05-11.

**Rule added**: قبل دمج أي لوحة Grafana جديدة، شغِّل فحص العقد الثابت (يطابق أسماء المقاييس بين الـ JSON والمصدر بـ grep). إضافة CI step مخصص `dashboard-metric-contract` — تتبع في PR منفصل.

---

## D-042 · Conversation Service Live Activation — Step 12 (2026-05-11)
**Decision**: تفعيل `conversation-service` كـ Skill احترافية مستقلة على `:8003` — الخدمة السادسة في Skills Architecture. تُحوِّل إدارة المحادثات من stub بسيط (`capability_level="stub"`) إلى Skill حقيقية بـ LangGraph StateGraph + Prometheus metrics + WebSocket.

**Architecture**:
- `ConversationState` TypedDict: question, intent, history, response, thread_id, correlation_id
- `intent_node` → `response_node` (StateGraph topology)
- `_classify_intent()` deterministic — لا يعتمد على LLM للتصنيف
- `_build_fallback_response()` — يعمل بدون OPENROUTER_API_KEY (Skill isolation)
- `asyncio.wait_for(..., timeout=30.0)` — timeout guard إلزامي في كل node

**Reason**: conversation-service كان stub لا يُصدِّر مقاييس ولا يملك StateGraph حقيقي. الخطوة 12 تُحوِّله إلى Skill قابلة للقياس والاختبار والاستبدال — مطابقة لتعريف الـ Skill في D-038.

**Pattern**: نفس نمط الخطوات 4-11 — uvicorn process مباشر في Codespaces، لا Docker.

**ISS-043 (مُحلَّل)**: `LangChainPendingDeprecationWarning` من `langgraph.cache.base` عند import — مُسكَّت في `tests/microservices/conversation_service/conftest.py` + `pytest.ini`.

**Status**: IMPLEMENTED 2026-05-11 — branch `feat/microservices-step12-conversation-service`.

---

## D-041 · Full Skills Pipeline + content-retrieval-skill (2026-05-11)
**Decision**: تحويل Skills Pipeline من "partial" إلى "full" حقيقي عبر 4 إصلاحات متزامنة:
1. **ISS-042-A**: `_generate_service_token()` في `skills_pipeline.py` — JWT HS256 لـ planning-agent
2. **ISS-042-B**: `dspy.LM` بدلاً من `dspy.OpenAI` (DSPy 3.x) في `planning_agent/main.py`
3. **ISS-042-C**: `asyncio.gather` 3-way (planning+research+reasoning بالتوازي الكامل)
4. **ISS-042-D**: timeout 55s لاستيعاب LLM latency (~30-45s)

**content-retrieval-skill**: Skill مستقلة جديدة على :8009 تُحوِّل exercise retrieval من keyword matching إلى وحدة قابلة للقياس مع intent_classifier + retrieval_engine + 7 Prometheus metrics.

**Reason**: pipeline_mode="partial" كان يعني أن planning-agent يفشل دائماً (HTTP 401 — missing Service Token) وأن reasoning-agent يعمل بـ mock (OPENROUTER_API_KEY لم يصل). الإصلاح يُحوِّل النظام من "microservices موجودة" إلى "microservices تعمل معاً فعلاً".

**Live verified (2026-05-11)**:
```
POST /compose → pipeline_mode="full" skills_active=["planning","research","reasoning"] total_ms=32069
GET /health (8009) → {"status":"healthy","step":"11","kb_files":2}
POST /retrieve → intent="retrieval" total=1 (BAC 2024 exercise found)
POST /retrieve (explanation) → intent="explanation" total=0 (ISS-038 FIXED)
```

**Status**: IMPLEMENTED 2026-05-11 — branch `feat/microservices-step11-full-skills-live`.



## D-039 · Skills Composition Pipeline — /compose Endpoint (2026-05-11)
**Decision**: `orchestrator-service` يُحوَّل من خدمة مستقلة إلى **Composition Engine حقيقي** يستدعي `planning-agent`, `research-agent`, و`reasoning-agent` عبر HTTP مع `X-Correlation-ID` للتتبع الموزع. `/compose` endpoint جديد يُشغِّل الـ 3 Skills بالتوازي (planning+research) ثم reasoning مع السياق المُجمَّع.

**Reason**: Skills Architecture (D-038) تتطلب Composition Layer حقيقي — orchestrator يجب أن يُركِّب النتائج من Skills مستقلة، لا أن يكون مجرد proxy. هذا هو الفرق بين "microservices موجودة" و"microservices تعمل معاً".

**Implementation**:
- `microservices/orchestrator_service/src/services/skills_pipeline.py` — Composition Engine
- `asyncio.gather(planning, research)` → parallel execution → reasoning مع السياق
- Fallback mode تلقائي: فشل أي Skill لا يوقف الـ Pipeline
- `X-Correlation-ID` في كل طلب HTTP للتتبع الموزع
- 6 مقاييس Prometheus جديدة: `cogniforge_pipeline_*`
- `cogniforge_orchestrator_startup_info{pipeline_enabled="true"}` منذ Step 9

**Live verified (2026-05-11)**:
```
POST /compose → {"pipeline_mode":"partial","skills_active":["research","reasoning"],"total_duration_ms":41.4}
GET /metrics → cogniforge_pipeline_invocations_total{mode="partial"} 1.0
              cogniforge_pipeline_skill_calls_total{skill="research",status="success"} 1.0
              cogniforge_pipeline_skill_calls_total{skill="reasoning",status="success"} 1.0
              cogniforge_orchestrator_startup_info{pipeline_enabled="true"} 1.0
```

**Config fix**: `service_map` في `config.py` كان يُعيِّن planning-agent على port 8001 (خطأ). صُحِّح إلى 8002.
**supervisor.sh fix**: أُضيف `CODESPACES=true` + `PLANNING_AGENT_URL/RESEARCH_AGENT_URL/REASONING_AGENT_URL` في `launch_orchestrator_service()`.

**Status**: IMPLEMENTED 2026-05-11 — branch `feat/microservices-step9-skills-pipeline`.

## D-038 · Skills Architecture as the Canonical AI Pattern (2026-05-11)
**Decision**: كل قدرة ذكاء اصطناعي في النظام يجب أن تُبنى كـ **Skill** — microservice مستقل بمسؤولية واحدة، مدخلات/مخرجات محددة، مقاييس Prometheus، واختبارات قابلة للتشغيل. **Prompt Spaghetti محظور** كنمط معماري.

**Reason**: Prompt Spaghetti (prompt واحد كبير يحاول كل شيء) يُنتج جودة متوسطة في كل شيء، لا يمكن اختباره، لا يمكن قياسه، ويموت مع تغيير النموذج. Skills تُنتج جودة ممتازة في شيء واحد، قابلة للاختبار بـ pytest، قابلة للقياس بـ Prometheus، ومستقلة عن النموذج.

**Skill Contract** (إلزامي لكل Skill جديد):
1. `/health` endpoint — يُعيد `status`, `service`, `step`
2. `/metrics` endpoint — `cogniforge_{skill}_startup_info{step=N} 1.0` + invocation metrics
3. `/execute` أو endpoint وظيفي — مدخلات/مخرجات محددة بـ Pydantic
4. `prom_metrics.py` — `CollectorRegistry` مستقل، minimum 11 مقياساً
5. `tests/microservices/{skill}/test_step{N}_{skill}_metrics.py` — minimum 79 اختباراً
6. Fallback mode — يعمل بدون API key أو خدمات خارجية

**Skills الحالية (ACTIVE)**:
- `orchestrator-service` :8006 — Composition Skill (يُركِّب النتائج)
- `user-service` :8001 — Identity Skill (إدارة المستخدمين)
- `planning-agent` :8002 — Planning Skill (التخطيط)
- `research-agent` :8007 — Retrieval Skill (البحث والاسترجاع)
- `reasoning-agent` :8008 — Reasoning Skill (التفكير العميق MCTS)

**الهدف المستقبلي**:
```
Browser → FastAPI → orchestrator.compose([
    PlanningSkill.plan(query),
    ResearchSkill.retrieve(context),
    ReasoningSkill.reason(problem),
]) → إجابة مُركَّبة
```

**Anti-patterns المحظورة**:
- prompt واحد يحاول كل شيء
- Skill يستدعي Skill آخر مباشرة (يجب المرور عبر orchestrator)
- Skill بدون `/metrics` endpoint
- Skill بدون اختبارات

**Status**: ADOPTED 2026-05-11 — مُدرج في CLAUDE.md §0.5 كـ North Star معماري. يُطبَّق على كل خطوة انتقالية لاحقة.



## D-024 · Process Env Wins Over .env at Module Import Time
**Decision**: Secrets (DATABASE_URL, OPENROUTER_API_KEY, SECRET_KEY) must be present in the **process environment** before uvicorn starts, not just in `.env`. The `.env` file is read by pydantic-settings after module-level code runs.
**Reason**: `app/core/settings/base.py:23` calls `os.environ.get("APP_DATABASE_URL")` at import time. If the process env is empty, the validator raises `ValueError` and uvicorn crashes before pydantic-settings ever reads `.env`.
**Implementation**: `supervisor.sh:_export_env_file()` exports all `.env` keys into the shell process before `python -m uvicorn`. `_inject_env_secrets()` writes real secrets from process env into `.env` first.
**Status**: IMPLEMENTED 2026-05-09 — see `fix/lifespan-orchestration-env-injection`.

## D-025 · Lifespan Warmup Must Be Timeout-Guarded
**Decision**: Any `ainvoke()` or async LLM call inside an ASGI `lifespan()` context manager must be wrapped in `asyncio.wait_for(..., timeout=N)`. Default timeout: 30 seconds.
**Reason**: An unbounded `await` in lifespan blocks ASGI startup indefinitely. Uvicorn accepts connections but the app is not ready. The service appears alive (PID, port open) but is actually in a partial startup state — the exact "misleading startup observability" problem described in ISS-035.
**Consequence**: If warmup times out, the service starts in DEGRADED mode (not dead). `/health` exposes `startup_state: "degraded"` and `startup_errors`. Operators can diagnose without restarting.
**Status**: IMPLEMENTED 2026-05-09 — see `microservices/orchestrator_service/main.py`.

## D-026 · /health Must Expose startup_state, Not Just "ok"
**Decision**: Every microservice `/health` endpoint must return `startup_state` (`"ready"` / `"degraded"`) and `startup_errors` (list) in addition to `{"status": "ok"}`.
**Reason**: A service that passes `/health` but has a failed graph warmup is DEGRADED, not healthy. Returning `{"status":"ok"}` unconditionally hides the real state from operators and load balancers.
**Implementation**: `app.state.startup_state` set during lifespan. `/health` reads it and includes it in the response.
**Status**: IMPLEMENTED 2026-05-09 — see `microservices/orchestrator_service/main.py`.

## D-027 · Supervisor Must Re-Verify Health on Every Boot
**Decision**: `supervisor.sh` must always re-probe the live `/health` endpoint on every boot cycle. It must never trust stale `.devcontainer/state/app_healthy` from a previous run.
**Reason**: The state file persists across container restarts. If uvicorn crashed on the previous boot, the state file still shows `app_healthy` from the run before that. The supervisor then skips the health check and reports the system as ready — while port 8000 is not listening.
**Implementation**: `_uvicorn_healthy()` checks both `kill -0 $PID` AND `curl -sf $HEALTH_ENDPOINT`. Health check step always runs regardless of state file.
**Status**: IMPLEMENTED 2026-05-09 — see `.devcontainer/supervisor.sh`.

## D-028 · LangGraph Local Graph Must Emit Prometheus Metrics Per Turn
**Decision**: `_supervisor_node` and `_chat_node` in `app/services/chat/local_graph.py` must emit `langgraph.intent.total`, `langgraph.node.count.total`, and `langgraph.node.duration_seconds` via `UnifiedObservabilityService` on every invocation.
**Reason**: The Grafana LangGraph dashboard (`20-langgraph.json`) references `cogniforge_langgraph_intent_total`, `cogniforge_langgraph_node_count_total`, `cogniforge_langgraph_node_duration_seconds_bucket`. Without emitters, these panels are permanently empty — zombie metrics (ISS-029, D-016).
**Consequence**: After this change, the LangGraph dashboard shows real data after the first WS chat turn. `cogniforge_langgraph_checkpointer_writes_total` remains a zombie metric until Postgres checkpointer is activated (ISS-020).
**Status**: IMPLEMENTED 2026-05-09 — see `app/services/chat/local_graph.py` + `app/telemetry/metrics.py`.

## D-029 · docker-compose.step3.yml as Isolated Step 3 Activation File
**Decision**: الخطوة الانتقالية الثالثة تستخدم `docker-compose.step3.yml` منفصلاً عن `docker-compose.yml` الرئيسي.
**Reason**: `docker-compose.yml` الرئيسي يُشغِّل الـ stack الكامل (20+ خدمة) وهو ثقيل جداً للتطوير. `docker-compose.step3.yml` يُشغِّل 3 خدمات فقط (postgres-orchestrator + redis-orchestrator + orchestrator-service) مع volumes مستقلة لا تتعارض مع الـ stack الرئيسي.
**Consequence**: يمكن تشغيل Step 3 بجانب الـ devcontainer الافتراضي بدون تعارض. المنافذ 5441/6380/8006 لا تتعارض مع أي خدمة في الـ devcontainer.
**Rollback**: `docker compose -f docker-compose.step3.yml down` يوقف الـ stack بالكامل. المونوليث يعود تلقائياً إلى LangGraph local fallback.
**Status**: IMPLEMENTED 2026-05-10 — see `feat/microservices-step3-live-activation`.

## D-030 · Ona automations.yaml as Step 3 Canonical Trigger
**Decision**: `.ona/automations.yaml` هو المُشغِّل الرسمي للخطوة 3 في بيئة Ona/Gitpod.
**Reason**: يوفر تجربة موحدة: `gitpod automations service start orchestrator-stack` يُشغِّل الـ stack + يتحقق من الصحة + يُبلِّغ عن الحالة. لا يتطلب معرفة بـ docker compose مباشرة.
**Services vs Tasks**: `orchestrator-stack` هو service (يعمل باستمرار، له `ready` command). `health-probe`, `verify-stack`, `run-step3-tests` هي tasks (تُشغَّل يدوياً عند الطلب).
**Schema constraint**: Services لا تدعم `dependsOn` (schema rejects it). الترتيب يُدار عبر `ready` command فقط.
**Status**: IMPLEMENTED 2026-05-10 — see `.ona/automations.yaml`.

## D-031 · OUTBOX_RELAY_ENABLED=true in Step 4 (D-031 fulfilled)
**Decision**: يُعطَّل outbox relay في Step 3 (`OUTBOX_RELAY_ENABLED=false`). يُفعَّل في Step 4 بعد التحقق من مسار الـ persistence الكامل.
**Reason**: تفعيل outbox relay قبل التحقق من D-006 (single persistence owner) يخاطر بـ dual-write. Step 3 يُثبت أن الخدمة تعمل وتُجيب على `/health`. Step 4 يُثبت أن الـ persistence صحيح.
**Status**: IMPLEMENTED 2026-05-10 — `supervisor.sh` و `.ona/automations.yaml` يُشغِّلان orchestrator مع `OUTBOX_RELAY_ENABLED=true`. انظر `feat/microservices-step4-persistence-relay`.

## D-032 · Independent prometheus_client Registry per Microservice
**Decision**: كل microservice يُصدِّر `/metrics` يجب أن يستخدم `CollectorRegistry()` مستقل — لا يشارك الـ default REGISTRY مع المونوليث أو أي خدمة أخرى.
**Reason**: في بيئات الاختبار والـ CI، قد يعمل المونوليث والـ orchestrator في نفس الـ process. استخدام الـ default REGISTRY يُسبب `ValueError: Duplicated timeseries` عند تسجيل نفس اسم المقياس مرتين.
**Implementation**: `microservices/orchestrator_service/src/core/prom_metrics.py` — `_REGISTRY = CollectorRegistry()` مع lazy init. كل counter/gauge/histogram يمرر `registry=_REGISTRY`.
**Status**: IMPLEMENTED 2026-05-10 — انظر `feat/microservices-step4-persistence-relay`.

## D-033 · /metrics Endpoint as Prometheus Scrape Target (Step 4)
**Decision**: `orchestrator-service` يجب أن يُصدِّر `/metrics` بصيغة Prometheus text format حقيقية (ليس JSON golden signals).
**Reason**: Prometheus يتوقع text format من `prometheus_client.generate_latest()`. الـ `/metrics` endpoint الموجود في `routes.py` يُعيد JSON (golden signals) — غير متوافق مع Prometheus scrape. Step 4 يضيف endpoint منفصل في `main.py` يستخدم `export_prometheus_text()` من `prom_metrics.py`.
**Metrics exposed**: `cogniforge_outbox_relay_cycles_total`, `cogniforge_outbox_relay_processed_total`, `cogniforge_outbox_relay_failed_total`, `cogniforge_outbox_relay_skipped_total`, `cogniforge_outbox_pending_gauge`, `cogniforge_stategraph_invocations_total`, `cogniforge_stategraph_duration_seconds`, `cogniforge_stategraph_errors_total`, `cogniforge_orchestrator_requests_total`, `cogniforge_orchestrator_request_duration_seconds`, `cogniforge_orchestrator_startup_info`.
**Status**: IMPLEMENTED 2026-05-10 — انظر `feat/microservices-step4-persistence-relay`.

## D-001 · LangGraph as Primary Chat Handler
**Decision**: `app/services/chat/local_graph.py` is the real handler. The orchestrator microservice is DORMANT in the default development environment.
**Reason**: GitHub Codespaces devcontainer (`.devcontainer/docker-compose.host.yml`) only spins up the `web` container; it does NOT start the microservices stack from `docker-compose.yml`. The orchestrator at `orchestrator:8006` always fails with ConnectError.
**Consequence**: All chat goes through the fallback chain → LangGraph `run_local_graph()`. This holds for both Codespaces and Replit-style single-process deployments.
**Rule**: NEVER assume the orchestrator microservice is reachable. LangGraph is the truth — unless you explicitly run `docker compose -f docker-compose.yml up -d` to wake the full stack.

## D-002
`app/kernel.py` is the authoritative composition root.

## D-002 · MemorySaver for Conversation Persistence
**Decision**: LangGraph uses `MemorySaver(thread_id=conversation_id)` for per-conversation state.
**Reason**: Simple, in-process, no Redis/Postgres needed. Works in any single-process deployment (Codespaces devcontainer, Replit, bare uvicorn).
**Consequence**: Conversation memory is lost on process restart.
**Alternative considered**: `langgraph-checkpoint-postgres` — too heavy for current setup.

## D-004
Cross-boundary communication is API-first only; direct DB coupling is forbidden.

## D-005
Architecture documentation must be code-evidenced and updated in the same PR.

## D-006 · Single Persistence Owner — Monolith Owns Message Writes
**Decision**: The Monolith (`app/api/routers/customer_chat.py` and `app/api/routers/admin.py`) is the sole owner of writes to `customer_messages` and `admin_messages`.
The Orchestrator microservice may only persist when the Monolith delegates explicitly via
`compatibility_facade=True` AND signals success back via `persisted: true` on the terminal
event. Absence of the `persisted` flag is treated as failure.
**Reason**: Dual-write (ISS-014) corrupts conversation history and inflates LLM context.
**Implementation** (this branch):
1. User message: always written by Monolith at WS entry (`save_message(USER)`).
2. Assistant message: Monolith reads `event.get("persisted") is True` on the trapped
   terminal event. If True → SKIP local write; if False/absent → fail-safe write with
   2 retries; on retry exhaustion → `[CRITICAL_DATA_LOSS]` log + terminal `error` frame.
3. The `persisted` flag is preserved through `_normalize_stream_event` in
   `OrchestratorClient` (lines 280–283) so the router can read it post-normalization.
4. None of the local fallback paths (file-intel / exercise-retrieval / LangGraph /
   general-chat) ever set `persisted: true` — they don't write to DB.
**Status**: IMPLEMENTED — see `claude/fix-persistence-consolidate-8X8LT`.

## D-009 · Single Terminal Frame per Turn — No Silent Failure
**Decision**: Every WS chat turn emits exactly one terminal frame (`assistant_final`
on success, `error` on failure). The helper `_emit_terminal_frames()` in both routers
is the only code that emits these frames. `persisted` is emitted ONLY after a
confirmed save.
**Reason**: ISS-016 (silent failures) and ISS-017 (terminal-event corruption by the
unified envelope normalizer) both manifested as UI hangs. The previous finally block
had paths where no terminal event was sent (no content + no error + no pending_terminal_event).
**Implementation**:
1. `app/api/routers/customer_chat.py:_emit_terminal_frames` and
   `app/api/routers/admin.py:_emit_terminal_frames` synthesize a frame when
   the upstream did not provide one.
2. `shared/chat_protocol/event_protocol.py:normalize_streaming_event` now passes
   `complete`, `persisted`, and `conversation_init` through unchanged when the
   unified envelope flag is on (previously they were mangled to `assistant_delta`).
**Status**: IMPLEMENTED — see `claude/fix-persistence-consolidate-8X8LT`.

## D-007 · thread_id Must Equal conversation_id — No Re-derivation
**Decision**: LangGraph `thread_id` (MemorySaver key) is always derived as
`str(conversation_id)` at the OrchestratorClient entry point and passed explicitly.
It is NEVER re-derived inside graph nodes or fallback handlers.
**Reason**: Re-derivation caused context identity fragmentation (ISS-019) where
fallback paths opened a fresh LangGraph thread for a continuing conversation.
**Status**: DECIDED — implementation pending (ISS-019 open)

## D-008 · Postgres Checkpointer as Opt-In (Not Default)
**Decision**: MemorySaver remains the default checkpointer (D-002). Postgres-backed
checkpointing (`langgraph-checkpoint-postgres`) is opt-in via
`LANGGRAPH_CHECKPOINTER=postgres` env var.
**Reason**: MemorySaver is sufficient for development. The trade-off (state lost on
restart) is acceptable in Codespaces but documented explicitly as ISS-020.
**Consequence**: Production deployment MUST set `LANGGRAPH_CHECKPOINTER=postgres`
to preserve conversation continuity across restarts.
**Status**: DECIDED — implementation pending (ISS-020 open)

## D-010 · Runtime Truth Lock — Code Presence ≠ Runtime Usage
**Decision**: A capability is treated as ACTIVE only when proven by the triple
**import + call chain + runtime evidence**. Anything missing one is DORMANT,
ZOMBIE, or UNKNOWN. The authoritative table lives in `.memory/runtime_truth.md`
and is mirrored as CLAUDE.md §6.6.
**Reason**: The codebase advertises a multi-agent stack (LangGraph workflow,
KAgent mesh, MCP server, LlamaIndex, DSPy, reranker, integration kernel) that
in default Codespaces is overwhelmingly ZOMBIE/DORMANT. Aspirational docs
(ARCHITECTURE.md, LangGraph_Architectural_Blueprint.md) describe a target
state that the runtime does not implement. Treating those docs as truth led to
repeated drift and false claims.
**Consequence**:
1. No PR may promote a component to ACTIVE without the three-part proof.
2. Any change to the chat / agent stack must update `.memory/runtime_truth.md`
   in the same PR if it changes a component's runtime status.
3. Aspirational docs (`docs/architecture/*`, root blueprints) may continue to
   describe target architecture, but they are not authoritative for runtime —
   `.memory/runtime_truth.md` is.
4. ZOMBIE components are not deleted on sight. They are flagged. Removal
   requires an ADR.
**Status**: DECIDED 2026-05-06 — see branch `claude/runtime-truth-audit-65iVU`.


## D-011 · Sanitize Admin Stream Errors
**Decision**: Never expose raw Python exception text to chat clients on admin stream failures.
**Reason**: Prevent internal detail leakage and keep stable error contract.
**Implementation**: `app/services/boundaries/admin_chat_boundary_service.py` now emits generic message + code `STREAM_RUNTIME_ERROR` while retaining full error logs server-side.
**Status**: IMPLEMENTED 2026-05-06.

## D-013 · Intent Classifier Patterns Must Be Updated in Two Files Simultaneously
**Decision**: `_EDUCATIONAL_PATTERNS` and `_GREETING_PATTERNS` are intentionally duplicated between `app/services/chat/local_graph.py` and `app/telemetry/path_observer.py`. The duplication is load-bearing: `path_observer.py` must classify intent before the graph runs, without importing from `local_graph.py`'s private API.
**Consequence**: Any change to intent patterns MUST be applied to both files in the same PR. A PR that updates only one file creates a classification split-brain between the graph's routing and the observability path labels.
**Anti-pattern to avoid**: Adding more keywords to `_EDUCATIONAL_PATTERNS` to fix false negatives. This worsens false positives (ISS-027). The correct fix is semantic context guards or embedding-based classification.
**Status**: DECIDED 2026-05-09 — see `.memory/fragility-patterns.md` Pattern 1.

## D-014 · Zombie IntentDetector Must Not Be Wired Without Taxonomy Resolution
**Decision**: `app/services/chat/intent_detector.py:IntentDetector` (13-intent taxonomy: FILE_READ, CONTENT_RETRIEVAL, ADMIN_QUERY, etc.) must NOT be wired into the live WS chat path without first resolving the taxonomy incompatibility with the live classifier's 3-intent taxonomy (educational/general/chat).
**Reason**: The two systems are semantically incompatible. `IntentDetector` routes to tool-based handlers (file operations, code search). The live classifier routes to LLM prompt variants. Wiring `IntentDetector` into the live path without a translation layer would produce undefined routing behavior.
**Consequence**: `IntentDetector` remains PARTIAL (loaded-not-invoked) until an explicit ADR resolves the taxonomy conflict and defines the routing contract.
**Status**: DECIDED 2026-05-09.

## D-015 · Sidebar Rendering Must Use DOM Exclusion, Not Visual Hiding
**Decision**: Any new sidebar or modal component that contains sensitive or contextually inappropriate content must use DOM exclusion (`display: none`, conditional rendering, or `inert` attribute) rather than CSS transform/opacity hiding when in the closed state.
**Reason**: CSS `transform: translateX(±100%)` keeps elements in the DOM, making them accessible to screen readers, keyboard navigation, browser find-in-page, and programmatic text selection (ISS-028). As the agent stack becomes more capable, `AgentTimeline` will expose real-time agent execution state to screen readers regardless of sidebar visibility.
**Exception**: The existing `.sidebar` and `.agent-sidebar` may retain their CSS transform for animation quality, but MUST add `inert={!isOpen || undefined}` (or `aria-hidden={!isOpen}` + tabindex management) to prevent accessibility leakage.
**Status**: DECIDED 2026-05-09 — see `.memory/fragility-patterns.md` Pattern 2.

## D-016 · Dashboard Metric Names Must Have Verified Emitters Before Merge
**Decision**: No Grafana dashboard panel may be merged if the Prometheus query expression references a metric name that has no corresponding emitter in the application source code.
**Verification method**: Before adding a dashboard panel, grep the application source for the metric name in emit calls (`record_metric`, `create_histogram`, `create_counter`, `increment_counter`). If no emitter exists, either add the emitter first or do not add the panel.
**Reason**: Zombie metrics (ISS-029) create permanently empty panels that operators cannot distinguish from "system not running". This is worse than no dashboard — it creates false confidence.
**Consequence**: The LangGraph dashboard (`20-langgraph.json`) has 4 zombie metric panels that must either gain emitters or be removed.
**Status**: DECIDED 2026-05-09 — see `.memory/fragility-patterns.md` Pattern 4.

## D-018 · Tavily Key Must Be Injected via Environment — Never Hardcoded
**Decision**: `TAVILY_API_KEY` must be injected at runtime via environment variable. It must never be hardcoded in source files, committed to `.env` files, or embedded in `docker-compose.yml` as a literal value.
**Reason**: The key is a secret. `docker-compose.yml` uses `${TAVILY_API_KEY:-}` pattern (empty default) so the service starts in degraded mode when the key is absent rather than failing.
**Key format**: Must start with `tvly-`. MCP URL format (`https://mcp.tavily.com/mcp/?tavilyApiKey=...`) is auto-sanitized by `readiness.py` and `super_search.py` — but the raw key form is preferred.
**Current state**: `TAVILY_API_KEY` is absent from `docker-compose.yml` (both `orchestrator-service` and `research-agent` environment sections). Must be added before the full stack can use web search.
**Status**: DECIDED 2026-05-09 — see CLAUDE.md §6.7.

## D-019 · Advanced Orchestrator Graph Uses 4-Intent Taxonomy — Do Not Conflate with Local Graph
**Decision**: The orchestrator microservice's `SupervisorNode` uses a 4-intent taxonomy: `educational`, `general_knowledge`, `admin`, `chat`. The local `local_graph.py` uses a 3-intent taxonomy: `educational`, `general`, `chat`. These are semantically different and must not be conflated.
**Reason**: The orchestrator's `general_knowledge` intent routes to `GeneralKnowledgeNode` (a dedicated LLM handler). The local graph's `general` intent routes to the same `chat_node` as `chat`. Merging the taxonomies without a translation layer would break routing in both graphs.
**Consequence**: Any future work that wires the orchestrator graph into the live path must account for this taxonomy difference. The local graph's intent classification bugs (Arabic greetings → 'general') are separate from the orchestrator's DSPy-based classification.
**Status**: DECIDED 2026-05-09 — see CLAUDE.md §6.7.

## D-021 · Monolith Routes to OrchestratorAgent, Not StateGraph — Routing Policy Gap
**Decision**: `ChatRoutingPolicy.candidate_urls()` returns `[f"{base}/agent/chat"]`. The `/agent/chat` endpoint routes to `OrchestratorAgent.run()` (intent-based dispatch, 13-intent taxonomy), NOT the 13-node `StateGraph`. The StateGraph is only invoked by `/api/chat/messages` and `/api/chat/ws` on the orchestrator service itself.
**Reason**: The routing policy was set to `/agent/chat` as the primary endpoint. The StateGraph endpoints (`/api/chat/messages`, `/api/chat/ws`) were added later as the orchestrator evolved. The routing policy was never updated to point to the StateGraph path.
**Consequence**: Even when the orchestrator microservice is running, the 13-node StateGraph (with DSPy, Tavily, reranker, synthesizer) is NOT invoked by the monolith's chat path. The monolith hits `OrchestratorAgent` instead. To route through the StateGraph, `ChatRoutingPolicy.candidate_urls()` must return `/api/chat/messages` instead of `/agent/chat`. This is a deliberate future migration step, not a bug to fix immediately.
**Status**: DOCUMENTED 2026-05-09 — see `.memory/langgraph_advanced_forensics.md`.

## D-022 · thread_id Namespaces Are Incompatible Between Stacks — Do Not Mix
**Decision**: The local fallback graph uses `str(conversation_id)` as `thread_id` (e.g. `"394"`). The orchestrator StateGraph uses `f"u{user_id}:c{conversation_id}"` (e.g. `"u7:c394"`). These are different namespaces in different `MemorySaver` instances. They must never be mixed.
**Reason**: The local graph was designed for simplicity (bare conversation_id). The orchestrator graph added user-scoping to prevent cross-user state contamination. The two stacks evolved independently.
**Consequence**: A conversation that starts on the local fallback graph and later routes to the orchestrator StateGraph will have no shared checkpoint state (ISS-019). This is the context identity fragmentation issue. Resolution requires either: (a) standardizing both stacks to the same format, or (b) accepting that state is not shared between stacks.
**Status**: DOCUMENTED 2026-05-09 — see `.memory/langgraph_advanced_forensics.md`.

## D-023 · AdminAgentNode Uses uuid4() thread_id — Stateless by Design
**Decision**: Inside the 13-node StateGraph, `AdminAgentNode.__call__()` invokes the admin sub-graph with `config = {"configurable": {"thread_id": str(uuid.uuid4())}}`. A fresh UUID per invocation.
**Reason**: Admin queries are stateless by nature — each admin tool invocation is independent. Using a fresh UUID prevents stale admin state from contaminating subsequent admin queries.
**Consequence**: The admin sub-graph has no checkpoint continuity even when the parent graph has a Postgres checkpointer. Admin tool results are not persisted across invocations. This is intentional but was undocumented.
**Status**: DOCUMENTED 2026-05-09 — see `.memory/langgraph_advanced_forensics.md`.

## D-020 · WebSearchFallbackNode Silent Skip Is a Known Degradation — Not a Bug
**Decision**: `WebSearchFallbackNode` silently returns `{"used_web": False, "reranked_docs": []}` when `TAVILY_API_KEY` is absent. This is intentional degraded-mode behavior, not a bug.
**Reason**: The node must not block the graph when web search is unavailable. The `SynthesizerNode` handles empty docs by returning `"لا توجد تفاصيل متاحة."`.
**Risk**: Silent degradation is invisible to operators without telemetry. The telemetry event `retrieval_source="web_skipped_missing_tavily"` is the only signal. Operators must monitor this event to detect key absence.
**Consequence**: Any dashboard that shows "web search active" must verify against this telemetry event, not just the presence of the `TAVILY_API_KEY` env var.
**Status**: DECIDED 2026-05-09 — see CLAUDE.md §6.7.

## D-017 · WS Turn Metrics Must Have a Single Emission Owner
**Decision**: `ws.chat.turn.duration_seconds`, `ws.chat.terminal_events.total`, and `ws.chat.fallback.total` must be emitted through exactly one path. The designated owner is the OTel SDK path (`path_observer._emit_to_otel`). The redundant `obs.record_metric(...)` calls for the same metric names in `path_observer.py` must be removed to prevent double-counting (ISS-030).
**Reason**: Dual-write at the metrics layer is the observability equivalent of the dual-write persistence bug (ISS-014). When the full stack is up, Prometheus scrapes both the OTel collector and `/api/v1/observability/prometheus`, producing 2x counts.
**Exception**: `UnifiedObservabilityService` may retain its own internal metric store for the `/api/v1/observability/metrics` endpoint (golden signals). The prohibition is on emitting the same Prometheus-exported metric through two paths simultaneously.
**Status**: DECIDED 2026-05-09.

## D-012 · Grafana Cross-Origin Proxy Wiring is Done at Boot, Not in `grafana.ini`
**Decision**: `grafana.ini` holds LOCAL-only defaults. The Codespaces-correct
values (`root_url`, `domain`, `cookie_samesite=none`, `cookie_secure=true`,
`csrf_always_check=false`) are computed at container-boot time by
`.devcontainer/start_observability.sh` and exported as `GF_*` env vars before
`docker compose up -d`.
**Reason**: `${CODESPACE_NAME}` is unique per Codespace and changes per
recreate. Hard-coding the URL in `grafana.ini` would break every other user.
Grafana's documented behavior is "env vars override grafana.ini at process
start" — this is the right hook.
**Consequence**:
1. Local Linux dev → `start_observability.sh` `unset`s the env vars, Grafana keeps `localhost` defaults. Local dev path unchanged.
2. Codespaces → script detects `${CODESPACE_NAME}` and exports the proxy-correct URL + cookie settings. Grafana boots already-aware-of-the-proxy.
3. Any future cloud dev environment (Gitpod, Coder, etc.) can be supported by adding a single `elif` branch in `detect_grafana_public_url()` — no config-file rewrites needed.
**What MUST NOT change**:
- The detection function in `start_observability.sh` is the SINGLE source of truth for "what URL is Grafana served from".
- `docker-compose.observability.yml` Grafana env block uses `${VAR:-default}` for every `GF_*` var so missing vars never break the local boot.
- Never set `cookie_secure=true` unconditionally — it breaks plain `http://localhost:3001/`.
**Status**: IMPLEMENTED 2026-05-07 — see branch `claude/fix-monitoring-port-hQ7JL` and CLAUDE.md §6.12.


## D-034 · User Service Activated as uvicorn Process on :8001 — Step 5 (2026-05-10)
**Decision**: `user-service` is activated as a uvicorn process on `:8001` in Codespaces (no Docker). It is the second microservice to go ACTIVE alongside `orchestrator-service` (:8006). Starts automatically via `supervisor.sh:launch_user_service()` (STEP 4E) when `DATABASE_URL` is set.
**Reason**: Step 4 proved the uvicorn-process pattern for microservice activation in Codespaces (no Docker-in-Docker). `user-service` is the natural next candidate: it has a complete FastAPI app, its own DB schema, auth routes, and UMS routes. Adding `/metrics` (prometheus_client) makes it fully observable.
**Port**: `:8001` — matches the existing `docker-compose.yml` port assignment for `user-service`.
**DB**: `USER_DATABASE_URL` (defaults to `DATABASE_URL` — Supabase shared). Separate schema from orchestrator.
**Metrics**: 11 `cogniforge_user_*` metrics in independent `CollectorRegistry`. `/metrics` endpoint at `localhost:8001/metrics`. Prometheus scrape target added with `step="5"` label.
**Grafana**: Dashboard `80-microservices-step5-user-service.json` (UID `cogniforge-ms-step5-user-service`, 17 panels, 10s refresh).
**CI gate**: `.github/workflows/microservices-step5-user-service.yml` (6 jobs).
**What MUST NOT change without an ADR**:
- The port `:8001` for user-service (matches docker-compose.yml).
- The `CollectorRegistry` isolation pattern — never use the default REGISTRY.
- The `step="5"` label in `cogniforge_user_startup_info` — used by CI gate and Grafana.
**Status**: IMPLEMENTED 2026-05-10 — branch `feat/microservices-step5-user-service`.

## D-025 · ChatRoutingPolicy Default Changed to state_graph — Step 2 Transition (2026-05-10)
**Decision**: `ChatRoutingPolicy.from_environment()` now defaults to `endpoint_mode="state_graph"`, routing to `/api/chat/messages` (StateGraph 13 nodes) instead of `/agent/chat` (OrchestratorAgent). Controlled by `ORCHESTRATOR_CHAT_ENDPOINT` env var.
**Reason**: D-021 identified that even when the orchestrator microservice is running, the 13-node StateGraph was never invoked because `ChatRoutingPolicy.candidate_urls()` always returned `/agent/chat`. The StateGraph (with DSPy, Tavily, reranker, synthesizer) is the intended production handler. The routing policy was the only blocker.
**Rollback**: Set `ORCHESTRATOR_CHAT_ENDPOINT=agent` in the monolith's environment. Takes effect immediately without restart (read per-request from env). No code change required.
**Observability**: `cogniforge_routing_mode_state_graph` gauge (1=StateGraph, 0=Agent) and `cogniforge_routing_target_total{target=...}` counter emitted per request. Visible in Grafana :3001 → "Microservices Transition — Step 2" dashboard.
**CI gate**: `.github/workflows/microservices-transition.yml` — `routing-policy-gate` job asserts default mode is `state_graph` on every PR touching `routing_policy.py`.
**What MUST NOT change without an ADR**:
- The default value of `ORCHESTRATOR_CHAT_ENDPOINT` (currently `"state_graph"`).
- The `_ENDPOINT_MAP` keys — adding a new mode requires an ADR.
- The `targets_state_graph` property — it is used by the CI gate and monitoring.
**Status**: IMPLEMENTED 2026-05-10 — branch `feat/microservices-step2-stategraph-routing`.

## D-018 · Exercise Retrieval Uses Two-Phase Intent Classifier, Not Keyword List (ISS-038)
**Decision**: `detect_exercise_retrieval()` in `app/services/capabilities/exercise_retrieval.py`
uses a two-phase intent classifier instead of a flat keyword list.
**Reason**: A flat keyword list on `"تمرين"` / `"احتمالات"` / `"درس"` causes context blindness.
Since `knowledge_base/` contains exactly one file, any false-positive trigger returns the
probability BAC exercise unconditionally — regardless of what the student asked. A student
asking "اشرح الجزء أ من هذا التمرين" received a probability exercise instead of an explanation.
**The two phases**:
1. **Explanation-intent guard** (highest priority): patterns like `"اشرح"`, `"كيف"`, `"هذا التمرين"`,
   `"ساعدني"`, `"explain"`, `"help me"`, `"الجزء أ"` cancel retrieval even when "تمرين" is present.
2. **Explicit retrieval trigger**: patterns like `"تمرين بكالوريا"`, `"التمرين الأول"`, `"exercise 1"`,
   `"الموضوع الأول"`, year+exercise combos trigger retrieval.
3. **Default**: no retrieval → fall through to LangGraph.
**New field**: `ExerciseRetrievalDecision.reason` (optional str, default `""`) — audit trail for
debugging misclassifications. Backward-compatible: callers only read `.recognized`.
**Consequence**:
- Explanation/help questions now fall through to LangGraph, which handles them correctly.
- Explicit BAC retrieval requests still work as before.
- Adding new trigger keywords requires a corresponding negation pattern — enforced by 25 regression tests.
**What MUST NOT change**:
- The explanation-intent list must always take priority over the retrieval list.
- The `reason` field must not be removed — it is the only audit trail for misclassification debugging.
- New keywords must not be added to the retrieval list without a corresponding explanation-intent guard.
**Status**: IMPLEMENTED 2026-05-10 — branch `fix/exercise-retrieval-context-blindness`.

## D-040 · Postgres Checkpointer Activated as Instrumented Subclass — Step 10 (2026-05-11)
**Decision**: `AsyncPostgresSaver` مُفعَّل كـ checkpointer دائم للـ StateGraph عبر `_InstrumentedCheckpointer` — subclass يرث من `AsyncPostgresSaver` مباشرةً ويُضيف مقاييس Prometheus على كل عملية.
**Reason**: LangGraph يتحقق من `isinstance(checkpointer, BaseCheckpointSaver)` في `ensure_valid_checkpointer()`. Wrapper بسيط (composition) يفشل هذا الفحص (ISS-041). Subclass يرث كل سلوك `AsyncPostgresSaver` ويُضيف instrumentation بدون كسر الـ type contract.
**Pattern**: `_make_instrumented_class(base_class)` — factory function تُنشئ subclass في runtime. يُمكِّن اختبار الـ class بدون pool حقيقي.
**DB**: `AsyncConnectionPool` (psycopg, max_size=5). يستخدم port 5432 (direct PG) لا 6543 (PgBouncer). `_build_psycopg_conninfo()` يُحوِّل `postgresql+asyncpg://` إلى `postgresql://`.
**Metrics**: 6 مقاييس جديدة: `cogniforge_checkpointer_*`. `cogniforge_orchestrator_startup_info` أُضيف إليه `checkpointer_backend` label.
**Fallback**: إذا فشل init → يُسجِّل في Prometheus (`backend="none"`) ولا يوقف الخدمة — يعود إلى `MemorySaver`.
**What MUST NOT change without an ADR**:
- `_make_instrumented_class` pattern — أي تغيير لـ wrapper strategy يحتاج ADR.
- `_POOL_SIZE = 5` — تغيير pool size يؤثر على Supabase connection limits.
- `_build_psycopg_conninfo` — يجب أن يُزيل `+asyncpg` ويُضيف `sslmode=require`.
- `checkpointer_backend` label في `STARTUP_INFO` — يُستخدم في CI gate و Grafana.
**Status**: IMPLEMENTED 2026-05-11 — branch `feat/microservices-step10-postgres-checkpointer`.

## D-043 · Live Runtime Audit — Full Stack Verified (2026-05-11)
**Decision**: تحديث جميع ملفات الذاكرة (`CLAUDE.md`, `.memory/`) بناءً على تشخيص حي مباشر لجميع الخدمات.
**Reason**: الوثائق السابقة تحتوي على معلومات قديمة (عدد dashboards، حالة scrape targets، API contracts). التحديث يضمن أن كل agent مستقبلي يبدأ من الواقع لا من التوقعات.
**Findings**:
- 8 خدمات uvicorn تعمل (8000, 8001, 8002, 8003, 8006, 8007, 8008, 8009)
- 12 Prometheus scrape target كلها UP
- 16 Grafana dashboard نشطة
- Skills Pipeline في وضع `fallback` (LLM keys غير موجودة في process env عند الإقلاع)
- API contracts: `question` field (ليس `message`) مطلوب في `/agent/chat` و `/chat/message`
- planning-agent يستخدم SQLite in-memory (ليس Supabase) — ISS-043-C
**What MUST NOT change**:
- API contract findings يجب أن تبقى موثقة حتى يتم إصلاحها.
- حالة `pipeline_mode=fallback` يجب أن تُعرض كـ PARTIAL وليس ACTIVE في truth table.
**Status**: DOCUMENTED 2026-05-11 — branch `feat/live-runtime-audit-d043`.

## D-048 · Indexed Knowledge Retrieval + Streaming Exercise Display (2026-05-13)
**Decision**: استرجاع التمارين التعليمية يجب أن يكون **مُفهرَساً وذرياً وبثياً**:
1. **Indexed**: استخدام `matched_entry` من `knowledge_index.py` لجلب ملف واحد بالضبط، لا wide-net search على كل `knowledge_base/*.md`.
2. **Atomic**: تنسيق العرض يحذف YAML frontmatter + قسم الحل + الوسوم — يبقى فقط نص التمرين (بطاقة + 3 أجزاء).
3. **Streaming**: المحتوى يُبَث كلمة بكلمة عبر `assistant_delta` متتابعة (typing-effect) بدل dump واحد كبير.

**Reason**: قبل هذا القرار، استرجاع تمرين 2016 الدوال العددية كان يُرجِع:
- ملفي 2016 + 2024 معاً (wide-net leakage)
- YAML metadata غريب يظهر للطالب
- الحل النموذجي يُكشف قبل أن يحل الطالب
- النص كله يصل دفعة واحدة (لا typing-effect)

**Architecture**:
```
detect_exercise_retrieval(question)
  → ExerciseRetrievalDecision(recognized, matched_entry, reason)
  → if matched_entry:
      load_exercise_content(entry)
      → format_exercise_for_display(entry, raw_content)
        → strip YAML frontmatter
        → trim at first solution/tags marker
        → return clean Q-only text
  → if NOT matched_entry: legacy wide-net fallback (rare)
  → _stream_local_retrieval_response:
      → split on \n boundaries → preserve LaTeX markers
      → for line > 80 chars: split on spaces
      → yield with asyncio.sleep(0.012) for typing-effect
```

**New artifacts**:
- `app/services/capabilities/exercise_retrieval.py`:
  - `_strip_frontmatter(content) -> str`
  - `_trim_at_solution(content) -> str`
  - `format_exercise_for_display(entry, raw_content) -> str`
  - `_SOLUTION_SECTION_MARKERS` tuple — list of section starts that end the exercise text.
- `app/infrastructure/clients/orchestrator_client.py`:
  - `_exercise_retrieval_full_decision(question) -> ExerciseRetrievalDecision`
  - `_stream_local_retrieval_response(question) -> AsyncGenerator[str, None]`

**What MUST NOT change without an ADR**:
- The indexed-first path inside `_build_local_retrieval_response()` — wide-net is fallback only.
- `_SOLUTION_SECTION_MARKERS` must cover ALL solution headers in `knowledge_base/`. New KB files require auditing this list.
- The streaming fallback path #2 in `chat_with_agent()` must call `_stream_local_retrieval_response()` not the non-streaming variant — otherwise typing-effect contract (D-047) breaks for retrieval queries.
- `ExerciseRetrievalDecision.matched_entry` is the single source of truth for which file to read. Re-introducing wide-net code paths without first checking `matched_entry is None` re-introduces ISS-051.

**Streaming chunk size invariants**:
- ≤80 chars: emit line verbatim (preserves `$$...$$` and `\\(...\\)` markers atomically).
- >80 chars: split on spaces, never inside a token (no risk of breaking `e^{-x}` mid-token).

**Status**: IMPLEMENTED 2026-05-13 — branch `claude/fix-exercise-display-eaIQC`.

## D-050 · Exercise Explanation with Context — Third Fallback Path (ISS-053, 2026-05-13)
**Decision**: إضافة مسار ثالث في fallback chain بين exercise_retrieval (2.0) و LangGraph (3.0) يُسمى "شرح مع سياق" (fallback_path=2.5).
**Problem**: طلبات "اشرح تمرين الدوال العددية 2016" كانت تُلغي الاسترجاع (explanation_intent) وتذهب إلى LangGraph بدون محتوى التمرين → هلوسة.
**Solution**:
- `detect_explanation_with_context()` في `exercise_retrieval.py`: تكشف عن طلبات شرح تمرين بكالوريا محدد (نمط شرح + تحديد بالسنة/الموضوع/الدالة) وتجلب `full_content` (نص + إجابة نموذجية) + `display_content` (نص فقط).
- `run_local_graph_with_exercise_context()` في `local_graph.py`: يُمرِّر المحتوى الكامل للـ LLM كـ context صريح مع `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` (منهجية شرح الإجابة النموذجية خطوة بخطوة).
- `_stream_exercise_explanation_response()` في `orchestrator_client.py`: مُدرَج في fallback chain.
**Fallback chain المحدَّث**: `file_intelligence(1) → exercise_retrieval(2.0) → exercise_explanation_with_context(2.5) → LangGraph(3.0) → general_chat(4.0)`
**Invariants**:
- `full_content` يشمل دائماً الإجابة النموذجية (للـ LLM فقط).
- `display_content` لا يشمل الإجابة النموذجية (للعرض المبدئي للطالب).
- المسار يُفعَّل فقط عند وجود نمط شرح + تحديد تمرين بكالوريا معروف في الفهرس.
- الشرح العام ("اشرح مفهوم المشتقة") يذهب للـ LangGraph كالمعتاد.
**Evidence**: 4 اختبارات نجحت حياً. شرح g(x) 2016 يعمل بدون هلوسة.
**Status**: IMPLEMENTED 2026-05-13.

## D-049 · Primary Model Switch to inclusionai/ring-2.6-1t:free (2026-05-13, superseded gemma-4-31b)
**Decision**: النموذج الأساسي = `inclusionai/ring-2.6-1t:free` (Inclusion AI Ring 2.6, 1T params MoE).
**History (نفس اليوم)**:
1. كان `liquid/lfm-2.5-1.2b-instruct:free` — نموذج صغير، إجابات سطحية في الرياضيات.
2. تجربة `google/gemma-4-31b-it:free` — تم التراجع عنها بنفس اليوم.
3. الاختيار النهائي `inclusionai/ring-2.6-1t:free` — بطلب المستخدم.
**Reason**: نموذج 1T params (mixture of experts) يُعطي جودة عالية للشرح التعليمي العربي والرياضيات المتقدمة، مع إتاحته مجاناً على OpenRouter.
**Risk**: توفّر النموذج لم يُتحقَّق منه حياً من السandbox (لا اتصال خارجي). الـ fallback chain الخمسية تحمي الاستمرارية إذا 404'd: Gemini 2 Flash → Qwen Coder → KAT → Phi 3 → Llama 3.2 Vision.
**Override**: تبديل سريع عبر `export OPENROUTER_PRIMARY_MODEL=<other>` بدون إعادة بناء.
**Streaming guarantee**: إذا كان النموذج لا يدعم token-level streaming حقيقي، الـ fallback chain ينتقل لنموذج يدعمه (D-047 + D-048 ضمانة معمارية، ليست خاصية نموذج معين).
**What MUST NOT change without ADR**:
- إذا أراد فريق العمليات تغيير الافتراضي، يجب توثيق السبب هنا (D-050+).
- لا تَحذف `_resolve_primary_model()` — هي بوابة الـ env override.
- لا تُعدِّل ترتيب الـ fallback chain إلا بعد تجربة كل نموذج على streaming حقيقي.
**Status**: IMPLEMENTED 2026-05-13 — branch `claude/fix-exercise-display-eaIQC`.

## D-050 · JSON Envelope Anti-Leak + Indexed Retrieval Preemption + Typewriter Smoothing (2026-05-13, ISS-056)
**Decision**: ثلاث طبقات دفاع متراكبة لمنع كارثة JSON envelope leak التي شاهدها المستخدم حياً.
**Problem**: عند طلب «اعطني تمرين دوال عددية 2016 الدورة الأولى الموضوع الثاني التمرين الرابع»، ظهر للطالب:
1. JSON خام `{"المصدر":"معرفة مادة","مستوى_الثقة":"0.70","التمرين":"لا توجد تفاصيل متاحة"...}` بدل التمرين الحقيقي.
2. ملف صحيح موجود في `knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md` لكن orchestrator-service لا يقرأه (vector DB مستقل).
3. حروف "مدفع رشاش" بسبب rAF batching بـ 16ms frames.
**Solution**:
- **طبقة 1 (`microservices/orchestrator_service/src/api/routes.py`)**: دالة `_extract_human_readable_response(final_resp)` تستخرج فقط `التمرين`/`الإجابة`/`response`/`answer`/`content`/`text`/`final_response` من dict. تستبدل `_serialize_json_async(final_resp)` في ثلاثة مواقع (HTTP `/api/chat/messages`, WS `/api/chat/ws`, Admin WS).
- **طبقة 2 (`microservices/orchestrator_service/src/services/overmind/graph/search.py`)**: `SynthesizerNode.__call__` يُرجِع `AIMessage(content=text_val)` بدل `AIMessage(content=json.dumps(response_json))`. هذا يمنع أي downstream consumer من التقاط dict كنص.
- **طبقة 3 (`app/infrastructure/clients/orchestrator_client.py`)**: دالة `_has_indexed_match(question)` + preemption في بداية `chat_with_agent`. عند تطابق `decision.matched_entry is not None`، يبث المحتوى المُفهرَس النظيف مباشرة عبر `_stream_local_retrieval_response` ويتجاوز orchestrator-service + StateGraph + fallback chain.
- **طبقة 4 (`frontend/app/components/ChatInterface.jsx`)**: خطّاف `useTypewriter(fullContent, isStreaming)` يكشف الحروف بإيقاع 60fps (~240 char/sec) أثناء streaming. عند `isStreaming=false` → كشف فوري للباقي.
- **تنسيق (`frontend/app/globals.css`)**: فواصل بصرية بين أجزاء التمرين، KaTeX `nowrap` داخل `.exam-content`، media query للشاشات الصغيرة.
**Invariants**:
- `_serialize_json_async(final_resp)` للحمولة الخام محظور إلى الأبد. كل تحويل dict→نص يمر عبر `_extract_human_readable_response`.
- `AIMessage.content` يجب أن يكون نص بشري — ليس JSON dump.
- preemption الفهرسي يسبق orchestrator دائماً. بدون استثناء.
- typewriter لا يبطّئ TTFT — يُجمِّل الإيقاع البصري فقط.
- زر النسخ ينسخ `msg.content` الكامل، لا `displayedContent`.
**Evidence**: قبل الإصلاح — JSON envelope مرئي في screenshot من المستخدم 2026-05-13. بعد الإصلاح — preemption يتطابق مع `knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md` ويبث المحتوى النظيف.
**Status**: IMPLEMENTED 2026-05-13 — branch `claude/fix-exercise-display-SRmNL`.

## D-051 · LaTeX Rendering Fix — Double-Backslash Delimiters + Atomic Typewriter (2026-05-13, ISS-057)
**Decision**: ثلاث طبقات لإصلاح تصيير LaTeX الذي ظهر كنص خام (`$g$`, `$\mathbb{R}$`) للطالب.
**Problem**: D-050 (preemption) عملت بنجاح وأوصلت محتوى التمرين النظيف، لكن الطالب رأى LaTeX كنص خام بدل رياضيات مرسومة. التحقيق كشف 192 موضع `\\(...\\)` (double-backslash حرفية) في `knowledge_base/bac2016_*.md`. الـ `preprocessMath` regex القديم (`/\\\(...\\\)/`) يطابق `\(` (واحد) فيُبقي شرطة فائضة → markdown يراها `\$` (دولار مُهرَّب) → KaTeX لا يُستدعى.
**Solution**:
- **`frontend/app/components/ChatInterface.jsx`**: 
  - `preprocessMath` يُطبِّع أولاً `\\(` → `\(` و `\\[` → `\[`، ثم يحوِّل `\(...\)` → `$...$` و `\[...\]` → `$$...$$`. يدعم 5 صيغ: `\(`, `\\(`, `\[`, `\\[`, `$...$`, `$$...$$`.
  - دالة جديدة `atomicTokenLength(text, start)` تكشف عن بداية LaTeX block وتُرجع طول الـ block كاملاً. الـ typewriter يستخدمها لكشف LaTeX blocks ذرّياً (atomic). يضمن: لا flicker من LaTeX غير مكتمل لحظياً.
- **`app/infrastructure/clients/orchestrator_client.py:_split_preserving_latex`**: الـ regex مُحدَّث لالتقاط الصيغ الأربع (`$$...$$`, `$...$`, `\\(...\\)`, `\(...\)`) كـ token واحد. يضمن: WebSocket chunks لا تكسر LaTeX block أبداً.
- **`frontend/app/globals.css`**: ترقية CSS لبطاقة الامتحان إلى مستوى "فاخر/مشروع عملاق":
  - خط ذهبي علوي (`exam-content::before` gradient)
  - ظل ثلاثي الطبقات (sharp + diffuse + blue glow)
  - `katex-display` بـ background gradient + border + hover state + `katex-fade-in` animation
  - `h3` بـ right-border ذهبية + خلفية gradient = بصرياً يحدِّد الجزء (I/II/III)
  - أعمدة جدول بطاقة الامتحان بخلفيات gradient مختلفة (header زرقاء، first column ذهبية)
**Invariants**:
- أي محتوى يحوي `\\(`, `\\[`, `\(`, `\[` يجب أن يمر عبر `preprocessMath` قبل ReactMarkdown.
- الـ typewriter يكشف LaTeX blocks ذرياً — لا يجوز أبداً عرض `$g` بدون `$` إقفال.
- `_split_preserving_latex` يدعم الصيغ الأربع. إضافة صيغة جديدة (`\begin{...}\end{...}`) → تحديث الـ regex.
- knowledge_base يستخدم `\\(...\\)` (inline) و `$$...$$` (display). لا تخلط في ملف واحد.
- `throwOnError: false` في KaTeX — لا تُغيِّره (يحمي من crash على LaTeX commands غير مدعومة).
**Evidence**: قبل الإصلاح — LaTeX خام مرئي في screenshot 2026-05-13. اختبار حي بعد الإصلاح: 192 موضع `\\(...\\)` تحوَّلت كلها إلى `$...$`، 0 موضع متبقٍ، 384 inline pairs + 66 display pairs. atomicTokenLength اجتاز 6 سيناريوهات اختبار.
**Status**: IMPLEMENTED 2026-05-13 — branch `claude/fix-exercise-display-SRmNL`.
