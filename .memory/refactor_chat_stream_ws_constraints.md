# قيود إعادة هيكلة chat_stream_ws (خريطة قرارات — تُقرأ قبل أي تغيير)

الحالة (CodeScene X-Ray، 2026-08-13): `customer_chat.py` ملف ساخن — `chat_stream_ws`
بـ **669 سطراً وتعقيد 69** (الأسوأ في المستودع كله، تردد تغيير 53). الهدف: تفكيك
الدالة إلى وحدات صغيرة تُختبَر فردياً، مع بقاء كل الشواهد (D-* و ISS-*) في مواضعها.

## القيود الصلبة (من البوابات والاختبارات — أي انتهاك = CI أحمر)

1. **التوقيع**: `async def chat_stream_ws(websocket)` — وحيد الوسيطات (`test_iss100`).
2. **نقطة الدخول**: `_ws_handler_source` يقطع من `async def chat_stream_ws` إلى أول
   `while True` في **customer_chat.py مباشرة** — اتصال JWT/accept/primer يجب أن يبقى
   حرفياً داخل `chat_stream_ws` حتى `while True` (لا قبله).
3. **نص الـ router فقط**: `test_iss098_keepalive` يتحقق عبر `inspect.getsource(customer_chat.chat_stream_ws)`
   أن `"_run_turn_keepalive"` و`"keepalive_task"` و`"keepalive_task.cancel()"` موجودة
   **داخل جسم الدالة** — helper يعاد تصديره عبر re-export يفي (`hasattr` + re-export).
4. **الترتيب الحي**: `if await handle_control_message(websocket, payload...): continue`
   يجب أن يبقى **نصياً داخل chat_stream_ws** قبل `payload.get("question"` (`test_ws_router_heartbeat_integration`
   يقرأ customer_chat.py نصياً).
5. **المصدر المركّب**: `_sources.py` + `read_customer_chat_source()` يجمع
   `customer_chat.py + support/{transport,pedagogy,frames}.py` — أي شريحة جديدة
   تُضاف سطراً في manifest (`check_skills_doctrine`, `test_persistence_authority`,
   `check_router_domain_logic`).
6. **البوابات النصية على المركّب** (check_skills_doctrine على `router_src`):
   - `"_evaluate_bkt_cards("` و`"await _bkt_task"` موجودان.
   - `"_build_pedagogy_directive"` موجود.
   - `'"pedagogy_directive": pedagogy'` و`'"support_level": sup_level'` موجودان.
   - `"get_learning_path_skill"` موجود.
   - لا `_maybe_emit_worked_example` ولا `worked_example_card` في المركّب.
7. **test_persistence_authority**: `'"compatibility_facade": True'` و
   `'normalized_event.get("persisted") is True'` و`"orchestrator_persisted = True"`
   يجب أن تبقى داخل **customer_chat.py نفسه** (يقرأ الملف مباشرة لا المركّب).
   كذلك `"[CRITICAL_DATA_LOSS]"` و`"[WRITE_DECISION]"`.
8. **check_router_domain_logic**:债务 مجمّد customer_chat.py = 6 نداءات نطاق
   (`async_session_factory`/`TutorStateService`/`select`) — لا ينمو ولا ينكمش
   (تتقلّص فقط، وعند التخفيض يجب `--update` بقرار مكتوب). إعادة الهيكلة إلى
   `customer_chat_support/turn_*.py` تُنقص الرقم ⇒ يجب تحديث الملف + سطر قرار.
9. **check_endpoint_complexity** (microservices/orchestrator فقط): لا يخص monolith
   مباشرة — لا أثر.
10. **monkeypatch late-binding** (D-168): الدوال تُستدعى من globals الـ router،
    لذا re-export في customer_chat.py يكفل بقاء monkeypatch على `customer_chat._X`
    فعّالاً.

## الشواهد التي يجب أن تحيا بعد التفكيك (تُستدعى باسمها من المركّب)

- `_emit_terminal_frames`, `_bind_stream_metadata`, `_locked_send_json`,
  `_run_turn_keepalive`, `_TURN_KEEPALIVE_INTERVAL_SECONDS`, `_is_text_event`,
  `_ws_is_connected`, `_extract_client_context_messages`,
  `_merge_history_with_client_context`, `_try_build_math_ui_component`,
  `_apply_complete_response_firewall`, `_apply_final_answer_redaction`,
  `_strip_display_garbage`, `_persist_ui_component_cards`, `_evaluate_bkt_cards`,
  `_build_pedagogy_directive`, `_semantic_tutor_enabled`, `_count_confusion_signals`,
  `_derive_correctness_override`, `_PedagogySnapshot`.

## مخطط التفكيك المعتمد (D-173 Stage 3 — التفكيك النهائي للدالة)

- `customer_chat.py` ⇒ «قشرة»: اتصال/مصادقة/accept/primer + حلقة receive واحدة
  تستدعي وحدة دوران واحدة: **`customer_chat_support/turn_lifecycle.py`**
  (دورة الدور الكاملة: persistence initiation ⇒ pedagogy ⇒ BKT task ⇒
  stream_and_forward ⇒ finally block كاملاً).
- حلقة while تبقى نصياً في router (`receive_json` + control check + تفويض الدور).
- `turn_lifecycle.py` جديد ⇒ manifest + `--update` للدين.
- كل استدعاء في router عبر re-export من الوحدة الجديدة (late-binding).

## قرارات الدَّين المُحدَّث (بعد التنفيذ)

- `router_domain_debt.json`: customer_chat.py ينخفض من 6 (قرار مكتوب: التفكيك D-173 S3).
- `check_router_domain_logic --update` لا يستخدم هنا — القرار يدوي مكتوب.
