# SUPER AGENT FINAL RUNTIME TRUTH REPORT

## 1. Executive Summary

- **CONFIRMED:** يوجد مساران WebSocket متزامنان في الكود لنفس واجهات الدردشة (`/api/chat/ws` و`/admin/api/chat/ws`): مسار المونوليث (`app/api/routers/*.py`) ومسار المايكروسيرفس عبر API Gateway (`microservices/api_gateway/main.py` → orchestrator/conversation). هذا يثبت خطر Split-Brain في طبقة التحكم.
- **CONFIRMED:** في مسار المونوليث، نقطة التفرع الأولى بين الدردشة العادية وSuper Agent تقع داخل `ChatOrchestrator.process` عند تحويل النية عبر `metadata.mission_type == "mission_complex"` ثم اختيار `MissionComplexHandler`.
- **CONFIRMED:** في مسار orchestrator-service، نقطة التفرع الأولى تقع داخل `chat_ws_stategraph`/`admin_chat_ws_stategraph` عند شرط `incoming.mission_type` أو `incoming.metadata.mission_type`؛ العادي يمر إلى `_run_chat_langgraph`، وSuper يمر إلى `handle_mission_complex_stream`.
- **CONFIRMED:** ملكية التخزين (conversation/message persistence) للدردشة العادية في المونوليث واضحة: Boundary/Persistence/Streamer في `app/services/boundaries/*`, `app/services/*/chat_persistence.py`, `app/services/*/chat_streamer.py`.
- **CONFIRMED:** لا يوجد ربط مؤكد ونشط بين `mission_id` وconversation في المسار الحالي؛ آلية الربط الوحيدة (`_link_mission_to_conversation`) موجودة في `app/services/chat/handlers/mission_handler.py` لكنها غير مستدعاة من أي مسار حي.
- **HIGH-CONFIDENCE:** فشل Super Agent يرتبط بتباين العقود (protocol contracts): بعض المسارات تُخرج `type/payload` event envelope، بينما orchestrator/conversation قد تُخرج envelopes من نوع `status/response/route_id` أو NDJSON نصي.
- **CONFIRMED:** عبارة `"Error: No response received from AI service."` تُكتب تلقائيًا عند عدم تجميع أي chunks نصية، حتى لو كان البث احتوى أحداث dict (مثل `assistant_delta`/`RUN_STARTED`)؛ هذا ينتج مظهر "نجاح بث" مع "فشل تاريخ".
- **HIGH-CONFIDENCE:** نجاح الدردشة العادية واختلال Super Agent يمكن أن يحدثا معًا لأنهما لا يمرّان دائمًا بنفس التنفيذ/البروتوكول/التخزين.
- **UNKNOWN:** أي Control-Plane هو الحي فعليًا في البيئة المصابة الآن (Gateway→Orchestrator/Conversation أم اتصال مباشر بالمونوليث) غير مثبت من الكود وحده بدون telemetry/runtime traces.
- **FALSE CONFIDENCE / UNPROVEN ASSUMPTION:** نجاح اختبارات حالية لا يثبت نجاح Super Agent الحقيقي End-to-End؛ كثير من الاختبارات تعتمد على mocking لـ`ChatOrchestrator.dispatch/process` أو على مسارات بدون mission_complex.

## 2. Confirmed Live Control-Plane Truth

### Admin Ordinary Chat
- **CONFIRMED (Monolith Path):**
  1. `app/api/routers/admin.py::chat_stream_ws`
  2. `ChatOrchestrator.dispatch` → `ChatRoleDispatcher.dispatch`
  3. `AdminChatBoundaryService.orchestrate_chat_stream`
  4. `AdminChatStreamer.stream_response`
  5. `ChatOrchestrator.process` (non-mission intent) → handlers/AI output → JSON events (`delta/complete`).

### Customer Ordinary Chat
- **CONFIRMED (Monolith Path):**
  1. `app/api/routers/customer_chat.py::chat_stream_ws`
  2. `ChatOrchestrator.dispatch` → `ChatRoleDispatcher.dispatch`
  3. `CustomerChatBoundaryService.orchestrate_chat_stream`
  4. `CustomerChatStreamer.stream_response`
  5. `ChatOrchestrator.process` (non-mission intent) → JSON events.

### Admin Super Agent
- **CONFIRMED (Monolith Path):** نفس سلسلة admin أعلاه، ثم داخل `ChatOrchestrator.process` يتم override intent من `metadata.mission_type` إلى `MISSION_COMPLEX`، ثم `MissionComplexHandler.execute`.
- **CONFIRMED (Gateway/Microservice Alternative Path):** `microservices/api_gateway/main.py::admin_chat_ws_proxy` → `websocket_proxy` → `microservices/orchestrator_service/src/api/routes.py::admin_chat_ws_stategraph` → mission_complex branch.

### Customer Super Agent
- **CONFIRMED (Monolith Path):** نفس customer chain مع mission override ثم `MissionComplexHandler`.
- **CONFIRMED (Gateway/Microservice Alternative Path):** `microservices/api_gateway/main.py::chat_ws_proxy` → `websocket_proxy` → `orchestrator_service::chat_ws_stategraph` → mission_complex branch.

### Exact First Divergence Point
- **CONFIRMED (Monolith):** `app/services/chat/orchestrator.py::process` عند منطق override للـ intent باستخدام `metadata["mission_type"]` ثم اختيار Strategy handler.
- **CONFIRMED (Orchestrator Service):** `microservices/orchestrator_service/src/api/routes.py::{chat_ws_stategraph,admin_chat_ws_stategraph}` عند شرط mission_complex قبل `_run_chat_langgraph`.

### Active path classification
- **CONFIRMED:** الكود يدعم `API Gateway → orchestrator-service` و`API Gateway → conversation-service` عبر canary.
- **CONFIRMED:** الكود يدعم أيضًا مسار monolith مباشر لنفس WebSocket endpoints.
- **HIGH-CONFIDENCE:** هذه بنية mixed/split-brain-capable.
- **UNKNOWN:** أي مسار فعلي مستخدم في incident الحالي بدون أدلة runtime.

## 3. Confirmed Persistence Ownership Truth

- **Conversation row creation owner (Monolith): CONFIRMED**
  - Admin: `AdminChatPersistence.get_or_create_conversation`
  - Customer: `CustomerChatPersistence.get_or_create_conversation`
- **User message save owner (Monolith): CONFIRMED**
  - Admin: `AdminChatBoundaryService.orchestrate_chat_stream` → `save_message(..., MessageRole.USER, ...)`
  - Customer: `CustomerChatBoundaryService.orchestrate_chat_stream` → `save_message(..., MessageRole.USER, ...)`
- **Assistant message save owner (Monolith): CONFIRMED**
  - Admin: `AdminChatStreamer._persist_response`.
  - Customer: `CustomerChatStreamer._persist_response`.
- **Assistant error save owner: HIGH-CONFIDENCE (not typed separately)**
  - لا يوجد جدول/دور مستقل لـ`assistant_error`; يتم حفظ نص fallback/error كرسالة `MessageRole.ASSISTANT` في `_persist_response` بعد الاستثناءات أو الفراغ.
- **Mission linkage owner: UNKNOWN for active runtime / CONFIRMED legacy-only artifact**
  - الربط الصريح (`linked_mission_id`) موجود نظريًا في `AdminConversation`.
  - التنفيذ الوحيد في `mission_handler._link_mission_to_conversation` غير مربوط بالمسار الحالي (لا استدعاءات).
- **Ordinary chat persistence same as runtime execution?**
  - **CONFIRMED (Monolith):** نعم، نفس boundary/streamer path.
  - **UNKNOWN (Gateway→Orchestrator/Conversation):** لا يوجد إثبات في repo أن orchestrator/conversation يكتبان نفس جداول تاريخ المونوليث.
- **Super Agent persistence same as runtime execution?**
  - **HIGH-CONFIDENCE:** ليس دائمًا؛ التنفيذ قد يكون orchestrator mission events بينما الحفظ النهائي يبقى monolith assistant text fallback.
- **UI history read from same source as runtime writes?**
  - **CONFIRMED (Monolith tests):** نعم، تاريخ `/api/chat/conversations/*` و`/admin/api/conversations/*` يقرأ ما حفظه streamer.
  - **UNKNOWN (Microservice runtime):** غير مثبت وجود source-of-truth موحد بين runtime microservice وhistory APIs في المونوليث.

## 4. WebSocket Event Contract Reality

- **Ordinary chat event format (Monolith): CONFIRMED**
  - أحداث JSON بهيكل `{type, payload}` مثل `conversation_init`, `delta`, `complete`, `error`.
- **Super Agent event format (Monolith): CONFIRMED**
  - يمرر dict events مثل `assistant_delta`, `RUN_STARTED`, `PHASE_*`, `assistant_final`, `assistant_error`.
- **Ordinary chat format (Orchestrator/Conversation WS): CONFIRMED**
  - `send_json` envelope: `{status, response, run_id..., route_id...}` بدون `type` في المسار العادي.
- **Super Agent format (Orchestrator WS): CONFIRMED**
  - `send_text` لأسطر NDJSON (`json + "\n"`) من `handle_mission_complex_stream`.
- **Backend transport modes: CONFIRMED**
  - يوجد `send_json` و`send_text` معًا في orchestrator-service WS.
  - API Gateway proxy ينقل كل رسائل upstream كـtext (`client_ws.send_text(message)`).
- **UI expectation: CONFIRMED**
  - `frontend/app/hooks/useAgentSocket.js` يعتمد أساسًا على `type`-driven FSM (`delta/assistant_delta/assistant_final/complete/error...`).
- **Protocol incompatibility as failure cause: HIGH-CONFIDENCE**
  - ordinary envelope بدون `type` قد لا يُعرض كنص assistant في UI hook.
  - NDJSON mission lines قد تعمل إذا كل line JSON صالح، لكن غياب complete/contract parity يبقى مخاطرة.
- **UI contract ambiguity: UNKNOWN**
  - سلوك الواجهة الفعلية في incident (legacy-app أم Next hook) غير مثبت من الكود وحده.

## 5. Mission Dispatch Contract Reality

- **Where mission_type expected: CONFIRMED**
  - Monolith routers: root payload `mission_type` فقط، ثم يُعاد تغليفه إلى `request.metadata.mission_type`.
  - Monolith orchestrator logic: يقرأ `metadata.mission_type`.
  - Orchestrator-service WS: يقبل root `mission_type` أو `metadata.mission_type`.
- **Where mission_type actually sent: CONFIRMED**
  - `frontend/app/components/ChatInterface.jsx` يرسل `{ mission_type: selectedMode }` كـroot key عبر `useAgentSocket.sendMessage`.
- **conversation_id truth: CONFIRMED**
  - يُمرّر من UI إلى routers ثم إلى `ChatDispatchRequest` ثم إلى `ChatOrchestrator.process`.
  - **HIGH-CONFIDENCE:** لا يُستخدم لربط mission في مسار `MissionComplexHandler` (start_mission لا يستقبله ولا يربطه).
- **fallback truth: HIGH-CONFIDENCE**
  - في monolith، إن فشل mission dispatch داخل `MissionComplexHandler` يُنتج `assistant_error` نصي `Dispatch Failed`.
  - لا يوجد دليل صريح على fallback تلقائي من mission_complex إلى ordinary chat داخل نفس الطلب.
- **mission-complex routing hit in live path: UNKNOWN**
  - الكود يسمح ويختبر تمرير metadata/root، لكن لا يوجد evidence runtime في المستودع أن المسار الحي المصاب يمر فعليًا عبر هذا الفرع حتى النهاية.

## 6. Failure Surface Map

- **"Dispatch Failed"**
  - **Source:** `app/services/chat/handlers/strategy_handlers.py::MissionComplexHandler.execute`.
  - **Trigger:** استثناء عند `start_mission(...)`.
  - **Owner:** Monolith MissionComplexHandler.
  - **Classification:** **CONFIRMED**.

- **"No response received from AI service"**
  - **Source:** `AdminChatStreamer._persist_response` و`CustomerChatStreamer._persist_response`.
  - **Trigger:** `full_response` فارغ عند نهاية البث.
  - **Owner:** Monolith persistence-finalization layer.
  - **Classification:** **CONFIRMED**.

- **empty-stream behavior**
  - **Source:** streamers تجمع النصوص فقط؛ dict events لا تدخل `full_response`.
  - **Trigger:** مسار Super Agent يرسل mostly dict events.
  - **Owner:** Monolith streamer design.
  - **Classification:** **HIGH-CONFIDENCE**.

- **timeout behavior**
  - **Source (legacy):** `app/services/chat/handlers/mission_handler.py` يحتوي timeout messaging.
  - **Trigger:** timeout أثناء create/poll في handler legacy.
  - **Owner:** Legacy monolith mission handler.
  - **Classification:** **UNKNOWN** (لا دليل أنه يُستدعى في المسار الحالي).

- **"assistant_error" event**
  - **Source:**
    - Monolith MissionComplexHandler failure branches.
    - Orchestrator mission_complex utility failure branches.
  - **Trigger:** mission_failed أو exception خلال mission stream.
  - **Owner:** depends on execution path (monolith vs orchestrator-service).
  - **Classification:** **CONFIRMED**.

- **generic/unknown UI failure state**
  - **Source:** `useRealtimeConnection` parse warnings + hook ignoring non-typed envelopes.
  - **Trigger:** receiving payload without `type` or incompatible framing.
  - **Owner:** Frontend event-state machine contract.
  - **Classification:** **HIGH-CONFIDENCE**.

## 7. Legacy Residual Risk Classification

- `app/api/routers/admin.py` WebSocket chat endpoint: **CONFIRMED ACTIVE RISK** (active endpoint overlaps gateway topology).
- `app/api/routers/customer_chat.py` WebSocket chat endpoint: **CONFIRMED ACTIVE RISK**.
- `app/services/chat/handlers/strategy_handlers.py::MissionComplexHandler`: **CONFIRMED ACTIVE RISK** (still in active orchestrator strategy registry).
- `app/services/chat/handlers/mission_handler.py`: **DORMANT BUT REACHABLE** (contains legacy linkage/poll logic but no active references).
- `app/services/overmind/entrypoint.py` (proxy-to-orchestrator bridge): **CONFIRMED ACTIVE RISK** (active dependency bridge).
- `app/infrastructure/clients/orchestrator_client.py`: **CONFIRMED ACTIVE RISK** (core bridge for missions/events/agent chat).
- API Gateway canary to conversation-service (`_resolve_chat_ws_target`): **CONFIRMED ACTIVE RISK** (protocol parity risk).
- `microservices/conversation_service/main.py` synthetic envelopes: **CONFIRMED ACTIVE RISK** (contract mismatch with type-based UI).
- `app/services/chat/websocket_authority.py`: **UNKNOWN** (file path مطلوب في نطاق التحقيق لكنه غير موجود بالمستودع الحالي؛ قد تكون وثيقة قديمة أو حذف غير موثق).

## 8. Test Evidence vs Runtime Evidence

- **Which tests prove ordinary chat works**
  - **CONFIRMED (monolith behavior with mocks):** `tests/api/test_customer_chat_persistence.py::test_customer_chat_stream_delivers_final_message` و`tests/regressions/test_streaming_event_type_bug.py`.
  - **CONFIRMED (microservice non-mission chat):** `tests/microservices/test_orchestrator_chat_stategraph.py`.

- **Which tests prove persistence/history works**
  - **CONFIRMED (monolith):**
    - `tests/api/test_customer_chat_persistence.py::test_customer_chat_persists_conversation_and_messages`
    - `tests/api/test_customer_chat_persistence.py::test_customer_chat_history_endpoint_reads_persisted_websocket_messages`
    - `tests/test_admin_chat_history.py::test_admin_websocket_persists_and_history_reads_same_records`.

- **Which tests prove Super Agent routing works**
  - **HIGH-CONFIDENCE only:** tests assert metadata passing (`mission_type`) إلى `ChatDispatchRequest` عبر patched dispatch.
  - لا يوجد اختبار End-to-End يثبت completion success لـ mission_complex من UI→Gateway→runtime→history.

- **Which tests do NOT prove real Super Agent success**
  - **CONFIRMED:** كل الاختبارات التي patch `ChatOrchestrator.dispatch` أو `ChatOrchestrator.process` (مثل customer/admin persistence suites) لا تثبت التنفيذ الحقيقي للـMissionComplexHandler ولا orchestrator-service mission stream.

- **Which tests still exercise legacy monolith persistence**
  - **CONFIRMED:** اختبارات history/persistence في `tests/api/test_customer_chat_persistence.py` و`tests/test_admin_chat_history.py` كلها ضد جداول المونوليث.

- **False confidence sources**
  - **CONFIRMED:** mocked dispatch/process في اختبارات chat الأساسية.
  - **CONFIRMED:** gateway ws routing tests تتحقق من target URL فقط (monkeypatched `websocket_proxy`) دون contract validation.
  - **HIGH-CONFIDENCE:** نجاح tests على boundaries القديمة يمكن أن يخفي runtime bypass عبر gateway/conversation/orchestrator في بيئات أخرى.

- **Critical runtime fact still unproven by tests**
  - **UNKNOWN:** هل Super Agent mission_complex ينجح end-to-end بنفس contract الذي تتوقعه الواجهة، مع حفظ تاريخ متسق، عند المرور عبر control-plane الحي الحقيقي.

## 9. Highest-Confidence Root Cause

**not yet singularly proven**

- **HIGH-CONFIDENCE interpretation:** الفشل ناتج من **ازدواج control-plane + عدم توحيد event contracts + عدم اتساق ownership بين execution وpersistence**، خصوصًا عندما يسلك Super Agent مسارات event-driven dict/NDJSON بينما بعض طبقات UI/history تتوقع text/delta-complete موحد.

## 10. Remaining Unknowns

1. **أي endpoint فعليًا يستقبِل WebSocket في البيئة المصابة الآن؟**
   - المفقود: traces/ingress routing/headers/runtime logs.
   - لماذا الأدلة غير كافية: المستودع يعرّف أكثر من path حي لنفس URI.

2. **هل مسار gateway canary يوجّه sessions المصابة إلى orchestrator-service أم conversation-service؟**
   - المفقود: قيم إعدادات rollout الفعلية + runtime bucket identities.
   - لماذا الأدلة غير كافية: القرار يعتمد environment values غير موجودة في الكود الثابت.

3. **أي واجهة عميل كانت مستخدمة وقت الفشل (legacy-app أم Next hooks)؟**
   - المفقود: frontend deployment/version evidence.
   - لماذا الأدلة غير كافية: المستودع يحتوي أكثر من client behavior.

4. **هل mission events تصل كاملة للعميل عند المرور عبر gateway proxy النصي؟**
   - المفقود: packet-level capture أو integration run حقيقي.
   - لماذا الأدلة غير كافية: الاختبارات الحالية لا تتحقق من mission_complex stream framing end-to-end.

5. **هل persistence المطلوب للـSuper Agent يجب أن يحفظ timeline/events أم فقط final assistant text؟**
   - المفقود: contract decision product/backend.
   - لماذا الأدلة غير كافية: التنفيذ الحالي يحفظ نصًا نهائيًا فقط وقد يكتب fallback رغم وجود events.

6. **هل أي جزء من mission linkage (`linked_mission_id`) مستخدم إنتاجيًا خارج المسارات المرئية؟**
   - المفقود: runtime calls/telemetry references.
   - لماذا الأدلة غير كافية: الكود يظهر artifact موجودًا بلا استدعاء مباشر.

## 11. Most Dangerous Unknown

- **UNKNOWN (single most dangerous):** هوية الـ**live control-plane** الفعلي المستخدم وقت incident (Monolith WS vs Gateway→Orchestrator/Conversation).
  - خطورته: أي إصلاح مبني على افتراض مسار خاطئ قد "ينجح اختباريًا" لكنه يزيد الانقسام ويؤخر العلاج.
  - القرار الخاطئ المحتمل: دمج إصلاحات protocol/persistence في خدمة ليست أصل التنفيذ الحي، ثم إعلان "حل" بينما العطل يستمر في المسار الآخر.

## 12. Final Conclusion

المؤكد الآن هو أن النظام يحمل مسارات تشغيل متعددة ومتزامنة للدردشة وSuper Agent، مع عقود WebSocket غير موحدة بالكامل وحدود ملكية تنفيذ/تخزين غير محكومة end-to-end؛ لذلك يمكن أن تبدو الدردشة العادية سليمة بينما يفشل Super Agent أو يظهر كتاريخ متناقض. قبل أي إصلاح نهائي أو merge آمن، يجب إثبات control-plane الحي فعليًا في runtime ثم التحقق على نفس المسار من contract موحد بين التنفيذ والبث والحفظ.
