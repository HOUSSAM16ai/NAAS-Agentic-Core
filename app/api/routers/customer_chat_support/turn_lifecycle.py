"""D-173 Stage 3 (2026-08-13): دورة الدور الكاملة لمسار WS العميل — سُلّخت حرفيًّا من
`customer_chat.py:chat_stream_ws` (669 سطراً، تعقيد 69 — CodeScene hotspot).

يحمل هذا الملف كل منطق الدور الواحد: افتتاح الجلسة (get_or_create + حفظ سؤال
الطالب)، قراءة صورة المتعلم، مهمة BKT الخلفية، بثّ تيار الـ orchestrator وتوجيهه،
قرار الكتابة الأحادي (single-writer)، بطاقات Generative UI، الإطار النهائي،
تحديث tutor_state — بلا أي تغيير سلوكي. الـ router يبقى قشرة استقبال فقط
(`receive_json` + heartbeats + تفويض الدور)، فينزل تعقيد الدالة الحية إلى
مستوىٍ تُختبَر فيه كل مرحلة وحدةً مستقلة.

قواعد D-168/D-173: هذه الوحدة لا تستورد `customer_chat` أبداً؛ الـ router يعيد
تصدير رموزها (re-export) فيبقى كل monkeypatch على `customer_chat.<name>`
فعّالاً لكل نداء يصدر من الـ handler (قانون late-binding).
"""

import asyncio
import contextlib
import uuid

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.api.routers.customer_chat_support.frames import (
    _bind_stream_metadata,
    _emit_terminal_frames,
    _extract_client_context_messages,
    _merge_history_with_client_context,
    _try_build_math_ui_component,
)
from app.api.routers.customer_chat_support.pedagogy import (
    _apply_complete_response_firewall,
    _apply_final_answer_redaction,
    _build_pedagogy_directive,
    _evaluate_bkt_cards,
    _persist_ui_component_cards,
    _semantic_tutor_enabled,
    _strip_display_garbage,
)
from app.api.routers.customer_chat_support.transport import (
    _is_text_event,
    _locked_send_json,
    _run_turn_keepalive,
    _ws_is_connected,
)
from app.api.routers.ws_auth import WsActor
from app.core.database import async_session_factory
from app.core.di import get_logger
from app.core.domain.chat import MessageRole
from app.infrastructure.clients.orchestrator_client import orchestrator_client
from app.services.analytics.product_events import record_product_event
from app.services.analytics.tutor_state_service import TutorStateService
from app.services.boundaries.customer_chat_boundary_service import (
    CustomerChatBoundaryService,
)
from app.telemetry.path_observer import close_ws_turn, open_ws_turn
from shared.analytics import EventName
from shared.chat_protocol.event_protocol import normalize_streaming_event

logger = get_logger(__name__)

#: D-157 (ISS-124): محاولات الحفظ البديل — لا انتظار طويل تحت ضغط Supabase.
_TURN_PERSIST_ATTEMPTS = 2


# ───────────────────────────── دورة الدور ─────────────────────────────


async def handle_turn(
    *,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    actor: WsActor,
    payload: dict[str, object],
) -> None:
    """يعالج سؤالاً واحداً من أول جلسة DB إلى الإطار النهائي الواحد.

    السلوك مطابق حرفيّاً لدورة `chat_stream_ws` السابقة:
    1. افتتاح/استعادة المحادثة + حفظ رسالة الطالب (WRITE_DECISION) + حدث الاحتفاظ.
    2. القراءة التربوية (support_level يقود عمق التلميح السقراطي).
    3. مهمة BKT خلفية (D-119: خلف الكواليس — لا بطاقة للطالب).
    4. بثّ تيار orchestrator مع فلترة noop/rewriting للتسلسل المحلي
       + تجميع النص + جمع بطاقات ui_component (ISS-106).
    5. كتلة الإغلاق الحتمية: بطاقة رياضية + قرار الكتابة الأحادي (orchestrator
       persisted ⇒ SKIP وإلا FAIL-SAFE write)، بطاقات UI المستقلة، الإطار
       النهائي، انتظار BKT، تحديث tutor_state (D-142 Phase 2)، إغلاق span.
    """
    request_id_value = payload.get("client_request_id")
    client_request_id = str(request_id_value).strip() if request_id_value is not None else None
    if client_request_id == "":
        client_request_id = None
    stream_request_id = client_request_id or str(uuid.uuid4())

    question = str(payload.get("question", "")).replace("\x00", "").strip()
    if not question:
        await _locked_send_json(
            websocket,
            send_lock,
            _bind_stream_metadata(
                normalize_streaming_event(
                    {"type": "error", "payload": {"details": "Question is required."}},
                ),
                None,
                stream_request_id,
            ),
        )
        return

    mission_type = payload.get("mission_type")
    metadata: dict[str, object] = {}
    if mission_type:
        metadata["mission_type"] = mission_type
    client_context_messages = _extract_client_context_messages(payload)
    if client_context_messages:
        metadata["client_context_messages"] = client_context_messages

    original_conversation_id = payload.get("conversation_id")
    local_conversation_id: int | None = None
    history_messages: list[dict[str, str]] = []
    pedagogy_snapshot = None

    turn_span = open_ws_turn(
        user_id=actor.id,
        conversation_id=None,
        is_admin=False,
        question=question,
        request_id=stream_request_id,
    )

    try:
        async with async_session_factory() as db:
            persistence_service = CustomerChatBoundaryService(db)
            local_conversation = await persistence_service.get_or_create_conversation(
                actor,
                question,
                original_conversation_id,
            )
            local_conversation_id = local_conversation.id
            turn_span.set_conversation_id(local_conversation_id)
            logger.info(
                "[WRITE_DECISION] conversation_id=%s role=user action=WRITE",
                local_conversation_id,
            )
            await persistence_service.save_message(
                local_conversation_id,
                MessageRole.USER,
                question,
            )
            # D-197: تعريف «طالبٌ نشِط» — دورُه. هذا الحدث أساس كلّ رقم احتفاظ.
            await record_product_event(
                event_name=EventName.CHAT_TURN_STARTED,
                user_id=actor.id,
                session_id=local_conversation_id,
            )
            history_messages = await persistence_service.get_chat_history(
                local_conversation_id,
                limit=50,
            )
            history_messages = _merge_history_with_client_context(
                history_messages,
                client_context_messages,
            )
        await _locked_send_json(
            websocket,
            send_lock,
            normalize_streaming_event(
                {
                    "type": "conversation_init",
                    "payload": {
                        "conversation_id": local_conversation_id,
                        "request_id": stream_request_id,
                    },
                }
            ),
        )
    except Exception as persist_exc:
        if isinstance(persist_exc, HTTPException):
            await _locked_send_json(
                websocket,
                send_lock,
                _bind_stream_metadata(
                    normalize_streaming_event(
                        {
                            "type": "error",
                            "payload": {
                                "details": str(persist_exc.detail),
                                "status_code": persist_exc.status_code,
                            },
                        }
                    ),
                    local_conversation_id,
                    stream_request_id,
                ),
            )
        else:
            logger.error(
                f"Failed to persist customer user message locally: {persist_exc}",
                exc_info=True,
            )
            await _locked_send_json(
                websocket,
                send_lock,
                _bind_stream_metadata(
                    normalize_streaming_event(
                        {
                            "type": "error",
                            "payload": {
                                "details": "Failed to save your message locally.",
                                "status_code": 500,
                            },
                        }
                    ),
                    local_conversation_id,
                    stream_request_id,
                ),
            )
        turn_span.set_terminal("error")
        close_ws_turn(turn_span, status="ERROR")
        return

    # ── قراءة صورة المتعلم (D-104/D-114) ──────────────────────────────
    pedagogy_snapshot = await _build_pedagogy_directive(
        user_id=actor.id,
        question=question,
        history_messages=history_messages,
    )
    pedagogy_directive = pedagogy_snapshot.directive_text
    support_level = pedagogy_snapshot.support_level

    # ── مهمة BKT خلفية (D-157: بعد حساب support_level) ────────────────
    _bkt_task = asyncio.create_task(
        _evaluate_bkt_cards(
            user_id=actor.id,
            conversation_id=local_conversation_id,
            question=question,
            history_messages=history_messages,
            support_level=support_level,
        )
    )
    _bkt_task.add_done_callback(
        lambda t: logger.debug("bkt_task_done err=%s", t.exception()) if t.exception() else None
    )

    # ── ذاكرة التدريس الدائمة (D-142 Phase 2 — خلف العلم، fail-open) ──
    tutor_state_ctx: dict[str, object] | None = None
    if _semantic_tutor_enabled() and local_conversation_id is not None:
        with contextlib.suppress(Exception):
            async with async_session_factory() as _ts_db:
                tutor_state_ctx = await TutorStateService(_ts_db).load(local_conversation_id)

    # ── البثّ والتوجيه نحو الواجهة ────────────────────────────────────
    (
        complete_ai_response,
        assistant_message_persisted,
        orchestrator_persisted,
        pending_terminal_event,
        captured_ui_components,
        stream_error,
    ) = await _stream_and_wait(
        websocket=websocket,
        send_lock=send_lock,
        actor=actor,
        question=question,
        local_conversation_id=local_conversation_id,
        metadata=metadata,
        history_messages=history_messages,
        stream_request_id=stream_request_id,
        pedagogy_directive=pedagogy_directive,
        support_level=support_level,
        tutor_state_ctx=tutor_state_ctx,
    )

    # ── كتلة الإغلاق الحتمية للدور (finally السابق حرفيّاً) ────────────
    await _close_turn(
        websocket=websocket,
        send_lock=send_lock,
        local_conversation_id=local_conversation_id,
        stream_request_id=stream_request_id,
        complete_ai_response=complete_ai_response,
        assistant_message_persisted=assistant_message_persisted,
        orchestrator_persisted=orchestrator_persisted,
        pending_terminal_event=pending_terminal_event,
        captured_ui_components=captured_ui_components,
        stream_error=stream_error,
        support_level=support_level,
        bkt_task=_bkt_task,
        pedagogy_snapshot=pedagogy_snapshot,
        actor=actor,
        turn_span=turn_span,
        tutor_state_ctx=tutor_state_ctx,
    )


# ──────────────────────── البثّ والانتظار ────────────────────────


async def _stream_and_wait(
    *,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    actor: WsActor,
    question: str,
    local_conversation_id: int | None,
    metadata: dict[str, object],
    history_messages: list[dict[str, str]],
    stream_request_id: str,
    pedagogy_directive: str,
    support_level: int,
    tutor_state_ctx: dict[str, object] | None,
) -> tuple[str, bool, bool, dict[str, object] | None, list[dict[str, object]], object | None]:
    """يشغّل تيار orchestrator ويوجّه كل حدث نحو الواجهة حتى الإغلاق.

    يُرجِع: (نص الإجابة المكتمل، حفظ محلي قبل الإغلاق، orchestrator persisted،
    الحدث النهائي المعلّق، بطاقات UI المجمّعة، خطأ التيار إن وجد).
    """
    complete_ai_response = ""
    assistant_message_persisted = False
    orchestrator_persisted = False
    pending_terminal_event: dict[str, object] | None = None
    captured_ui_components: list[dict[str, object]] = []
    stream_error: object | None = None

    async def _forward_event(event: dict[str, object]) -> None:
        nonlocal orchestrator_persisted
        nonlocal pending_terminal_event

        normalized_event = normalize_streaming_event(event)

        # ISS-STREAM-001: تصفية أحداث noop (أحداث غير معروفة من orchestrator).
        if normalized_event.get("type") == "noop":
            return

        # منع انتهاك FK «Split-Brain»: إعادة كتابة أو حذف conversation_id
        # الذي يبعثه orchestrator كيلا تستبدل الواجهة تسلسلها المحلي بتسلسل غريب.
        if normalized_event.get("type") == "conversation_init" and isinstance(
            normalized_event.get("payload"), dict
        ):
            if local_conversation_id is not None:
                normalized_event["payload"]["conversation_id"] = local_conversation_id
            else:
                normalized_event["payload"].pop("conversation_id", None)

        event_type = normalized_event.get("type")
        if event_type in {"complete", "assistant_final"}:
            if normalized_event.get("persisted") is True:
                orchestrator_persisted = True
            pending_terminal_event = _bind_stream_metadata(
                normalized_event, local_conversation_id, stream_request_id
            )
            return

        # ISS-106 (D-WS-CARD-PERSIST-001): اجمع بطاقات ui_component المستقلة
        # لحفظها لاحقاً (تبقى بعد إعادة الدخول).
        if event_type == "ui_component" and isinstance(normalized_event.get("payload"), dict):
            captured_ui_components.append(dict(normalized_event["payload"]))

        # D-115: مطهّر العرض المصفّح على كل delta نصّي — شبكة أمان فوق تنظيف
        # الـ orchestrator (لا ⟦⟧ ولا تعليمات مسرَّبة).
        display_event = normalized_event
        if _is_text_event(normalized_event) and isinstance(normalized_event.get("payload"), dict):
            chunk_text = normalized_event["payload"].get("content")
            if isinstance(chunk_text, str) and chunk_text:
                display_event = {
                    **normalized_event,
                    "payload": {
                        **normalized_event["payload"],
                        "content": _strip_display_garbage(chunk_text),
                    },
                }
        # D-096: send_lock يمنع التزامن مع keepalive.
        await _locked_send_json(
            websocket,
            send_lock,
            _bind_stream_metadata(display_event, local_conversation_id, stream_request_id),
        )

    async def _accumulate_text(event: dict[str, object]) -> None:
        """تراكم نظيف لنص الإجابة (لا غارباج في النسخة المحفوظة — D-115)."""
        nonlocal complete_ai_response
        if _is_text_event(event) and isinstance(event.get("payload"), dict):
            chunk_text = event["payload"].get("content")
            if isinstance(chunk_text, str) and chunk_text:
                # D-115: التراكم النظيف (لا غارباج في النسخة المحفوظة).
                complete_ai_response += _strip_display_garbage(chunk_text)

    async def stream_and_forward() -> None:
        async for event in orchestrator_client.chat_with_agent(
            question=question,
            user_id=actor.id,
            conversation_id=local_conversation_id,
            history_messages=history_messages,
            context={
                "chat_scope": "customer",
                "metadata": metadata,
                "compatibility_facade": True,
                "pedagogy_directive": pedagogy_directive,
                "support_level": support_level,
                # D-142 Phase 2: الحالة الدائمة (None عند العلم OFF).
                "tutor_state": tutor_state_ctx,
            },
        ):
            # D-WS-FLAP-001: إجهاض التيار إذا انقطع العميل منتصف الدور —
            # بدونه RuntimeError يهرب ويفسد حالة كتلة الإغلاق.
            if not _ws_is_connected(websocket):
                logger.info(
                    "customer_chat.stream_aborted: client disconnected mid-stream "
                    "(conversation_id=%s)",
                    local_conversation_id,
                )
                return
            await _forward_event(event)
            await _accumulate_text(event)

    stream_task: asyncio.Task[None] | None = None
    keepalive_task: asyncio.Task[None] | None = None
    try:
        stream_task = asyncio.create_task(stream_and_forward())
        # ISS-098 (D-WS-FLAP-005): keepalive متزامن يمنع false
        # heartbeat-timeout على العميل أثناء الأدوار الطويلة.
        keepalive_task = asyncio.create_task(_run_turn_keepalive(websocket, send_lock))
        try:
            await stream_task
        finally:
            keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await keepalive_task
    except HTTPException as http_exc:
        stream_error = http_exc
        logger.error(f"HTTPException in compatibility facade stream: {http_exc}", exc_info=True)
        # HTTPException تُنقل كما هي إلى الإطار النهائي (_emit_terminal_frames)
        # الذي يُخرج status_code الأصلي — مطابق لسلوك main قبل التفكيك.
    except Exception as exc:
        stream_error = exc
        logger.error(f"Error in compatibility facade stream: {exc}", exc_info=True)
        # D-096: locked send + فحص حالة الاتصال
        if (
            not isinstance(exc, WebSocketDisconnect)
            and websocket.client_state == WebSocketState.CONNECTED
        ):
            try:
                await _locked_send_json(
                    websocket,
                    send_lock,
                    normalize_streaming_event(
                        {"type": "error", "payload": {"details": str(exc), "status_code": 500}},
                    ),
                )
            except (WebSocketDisconnect, RuntimeError) as _send_err:
                logger.debug("customer_chat.error_send_failed: %s", type(_send_err).__name__)
    finally:
        if stream_task is not None and not stream_task.done():
            stream_task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                logger.info("Cancelled customer stream task after disconnect/finalization")

    return (
        complete_ai_response,
        assistant_message_persisted,
        orchestrator_persisted,
        pending_terminal_event,
        captured_ui_components,
        stream_error,
    )


# ──────────────────────── كتلة الإغلاق الحتمية ────────────────────────


async def _close_turn(
    *,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    local_conversation_id: int | None,
    stream_request_id: str,
    complete_ai_response: str,
    assistant_message_persisted: bool,
    orchestrator_persisted: bool,
    pending_terminal_event: dict[str, object] | None,
    captured_ui_components: list[dict[str, object]],
    stream_error: object | None,
    support_level: int,
    bkt_task: asyncio.Task[None],
    pedagogy_snapshot,
    actor: WsActor,
    turn_span,
    tutor_state_ctx: dict[str, object] | None,
) -> None:
    """الإغلاق الحتمي للدور — مطابق لـ finally السابق حرفيّاً:

    بطاقة رياضية ⇒ قرار الكتابة الأحادي (single-writer) ⇒ بطاقات UI ⇒
    الإطار النهائي الواحد ⇒ انتظار BKT ⇒ تحديث tutor_state ⇒ إغلاق span.
    """
    # D-086 (V46.0): OutputFirewall على الإجابة المكتملة قبل الحفظ —
    # يضمن نقاء القناة B في السجل الدائم.
    if complete_ai_response:
        complete_ai_response = _apply_complete_response_firewall(complete_ai_response)
        # D-113/D-115: حجب الإجابة النهائية على النسخة المحفوظة — شبكة أمان
        # حتمية ضد كشف الجواب (لا كشف في التدفّق العادي؛ الكشف لوضع مراجعة منفصل).
        complete_ai_response = _apply_final_answer_redaction(complete_ai_response, support_level)

    # ── Persistence decision (single-writer coordination) ─────────────
    # المونوليث يملك الرسالة. إن سبق orchestrator الحفظ (persisted=True) ⇒ SKIP،
    # وإلا fail-safe write. غياب الإشارة يُعامَل كفشل.
    if (
        not assistant_message_persisted
        and complete_ai_response
        and local_conversation_id is not None
    ):
        if orchestrator_persisted:
            logger.info(
                "[WRITE_DECISION] conversation_id=%s role=assistant "
                "orchestrator_persisted=True action=SKIP",
                local_conversation_id,
            )
            assistant_message_persisted = True
        else:
            logger.warning(
                "[WRITE_DECISION] conversation_id=%s role=assistant "
                "orchestrator_persisted=False action=WRITE (Fail-Safe) "
                "- Absence of signal treated as failure.",
                local_conversation_id,
            )
            # ISS-106 (D-WS-CARD-PERSIST-001): البطاقة الرياضية تُبنى من
            # النص المكتمل وتُرفق برسالة المساعد لتبقى بعد إعادة الدخول.
            _assistant_card = _try_build_math_ui_component(complete_ai_response.replace("\x00", ""))
            for _attempt in range(_TURN_PERSIST_ATTEMPTS):
                try:
                    async with async_session_factory() as db:
                        persistence_service = CustomerChatBoundaryService(db)
                        await persistence_service.save_message(
                            conversation_id=local_conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=complete_ai_response.replace("\x00", ""),
                            ui_component=_assistant_card,
                        )
                        assistant_message_persisted = True
                        logger.info("[DATA_LOSS_PREVENTED] Fallback persistence succeeded.")
                    break
                except Exception as persistence_exc:
                    logger.error(
                        (
                            "Failed to persist customer assistant message locally "
                            f"for conversation {local_conversation_id} "
                            f"(attempt {_attempt + 1}/{_TURN_PERSIST_ATTEMPTS}): "
                            f"{persistence_exc}"
                        ),
                        exc_info=True,
                    )

            if not assistant_message_persisted:
                logger.error(
                    "[CRITICAL_DATA_LOSS] Fallback persistence completely failed for "
                    f"conversation {local_conversation_id}."
                )

    # ── Persist standalone generative-UI cards (ISS-106) ──────────────
    # كل بطاقة ui_component مستقلة بُثّت خلال الدور (شجرة احتمالات، قصة
    # تمرين، بطاقة شرح...) تُحفظ كصف مساعد content="" لتُصيَّر من التاريخ
    # بعد إعادة الدخول. غير حرج: أي فشل يُسجَّل ولا يكسر إنهاء الدور.
    if captured_ui_components and local_conversation_id is not None:
        await _persist_ui_component_cards(
            conversation_id=local_conversation_id,
            cards=captured_ui_components,
        )

    # ── Guaranteed terminal frame ─────────────────────────────────────
    # إطار نهائي واحد فقط لكل دور (assistant_final أو error) كيلا تعلق
    # الواجهة. `persisted` لا يُبعَث إلا بعد حفظ حقيقي.
    # D-WS-FLAP-001: محاط بحارس — إن انقطع العميل قفزنا عن الإطار لا عن الحلقة.
    try:
        await _emit_terminal_frames(
            websocket=websocket,
            send_lock=send_lock,  # D-096
            pending_terminal_event=pending_terminal_event,
            assistant_message_persisted=assistant_message_persisted,
            complete_ai_response=complete_ai_response,
            stream_error=stream_error,
            local_conversation_id=local_conversation_id,
            stream_request_id=stream_request_id,
        )
    except (WebSocketDisconnect, RuntimeError) as _ws_close_err:
        logger.info(
            "customer_chat.terminal_frame_skipped: client already disconnected "
            "(conversation_id=%s err=%s)",
            local_conversation_id,
            type(_ws_close_err).__name__,
        )

    # ── D-119: التتبّع المعرفي خلف الكواليس — لا بطاقة للطالب ─────────
    # نضمن اكتمال كتابة BKT التحليلية (append-only — D-074) + تسجيل المسار
    # التعلّمي قبل إنهاء الدور. لا بطاقات تُبثّ أو تُحفظ للطالب (قرار المالك
    # D-119: «تتبّع المعرفة» و«ترسيخ المهارة» خلف الكواليس، لا في سطح الطالب).
    with contextlib.suppress(Exception):
        await bkt_task

    # D-142 Phase 2: تحديث ذاكرة جلسة التدريس الدائمة (خلف العلم، fail-open).
    # يضبط آخر خطوة عُرضت (مرساة منع التكرار تنجو من النافذة) + المفهوم النشط +
    # ميزانية المفهوم + قدرة الطالب (من BKT) — صف حيّ واحد لكل محادثة (upsert).
    if _semantic_tutor_enabled() and local_conversation_id is not None and complete_ai_response:
        with contextlib.suppress(Exception):
            _is_socratic_q = complete_ai_response.rstrip().endswith(("؟", "?"))
            async with async_session_factory() as _ts_db2:
                # D-144: policy_decision تحقنها OrchestratorClient
                policy_decision = (
                    tutor_state_ctx.get("policy_decision") if tutor_state_ctx else None
                )
                learning_stage = policy_decision.learning_stage if policy_decision else "definition"
                representation_used = policy_decision.representation if policy_decision else "text"
                interventions_used = (
                    tutor_state_ctx.get("interventions_used", []) if tutor_state_ctx else []
                )
                # Log intervention
                if policy_decision:
                    interventions_used.append(f"{learning_stage}_{policy_decision.next_action}")
                # D-158: دلتا تقدّم المكوّنات المعرفية (يبنيها _cognitive_turn،
                # يحقنها في dict tutor_state المشترك). المصدر الوحيد لِـ
                # representations_delivered / _pending الذي يقتل التكرار عبر الكتل.
                _kc_delta = tutor_state_ctx.get("kc_progress_delta") if tutor_state_ctx else None
                await TutorStateService(_ts_db2).record_turn(
                    conversation_id=local_conversation_id,
                    user_id=actor.id,
                    active_concept=pedagogy_snapshot.concept_id,
                    assistant_text=complete_ai_response,
                    is_socratic_question=_is_socratic_q,
                    ability_snapshot=pedagogy_snapshot.mastery,
                    learning_stage=learning_stage,
                    representation_used=representation_used,
                    interventions_used=interventions_used,
                    kc_progress=_kc_delta if isinstance(_kc_delta, dict) else None,
                )

    # إغلاق span path-aware مرة واحدة لكل دور — نوع الحدث النهائي يعكس ما
    # بعثه `_emit_terminal_frames` فعلاً.
    if assistant_message_persisted:
        turn_span.set_terminal("assistant_final")
        close_ws_turn(turn_span, status="OK")
    else:
        turn_span.set_terminal("error")
        close_ws_turn(turn_span, status="ERROR")
