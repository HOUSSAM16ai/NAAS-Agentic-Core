"""
واجهة برمجة تطبيقات محادثة العملاء القياسيين.

توفر نقاط النهاية الخاصة بالمستخدمين القياسيين للوصول إلى محادثة تعليمية
مع فرض سياسات الأمان والملكية.

## V46.0 — جدار الحماية المزدوج للقنوات

يُطبَّق OutputFirewall على complete_ai_response المُجمَّع قبل الحفظ في DB.
هذا يضمن أن أي HTML/JSX تسرَّب من LLM يُنظَّف قبل الوصول للطالب أو قاعدة البيانات.

D-086 (2026-05-23): تطبيق Protocol V46.0.
"""

import asyncio
import contextlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.routers.ws_auth import WsActor, extract_websocket_auth
from app.api.schemas.customer_chat import (
    CustomerConversationDetails,
    CustomerConversationSummary,
)
from app.core.config import get_settings
from app.core.database import async_session_factory, get_db
from app.core.di import get_logger
from app.core.domain.chat import MessageRole
from app.core.domain.user import User
from app.deps.auth import CurrentUser, require_permissions
from app.infrastructure.clients.orchestrator_client import orchestrator_client
from app.services.analytics.product_events import record_product_event
from app.services.analytics.tutor_state_service import TutorStateService
from app.services.auth.token_decoder import decode_token_payload
from app.services.boundaries.customer_chat_boundary_service import (
    CustomerChatBoundaryService,
)
from app.services.rbac import ADMIN_ROLE, QA_SUBMIT
from app.services.skills.ws_heartbeat_skill import handle_control_message
from app.telemetry.path_observer import close_ws_turn, open_ws_turn
from shared.analytics import EventName
from shared.chat_protocol.event_protocol import normalize_streaming_event

logger = get_logger(__name__)


# ── D-173 Stage 2b: الأشرطة المساعدة استُخرجت حرفياً إلى customer_chat_support/ ──
# الـ re-export يُبقي monkeypatch على `customer_chat.<name>` فعّالاً (المستدعي
# chat_stream_ws يعيش هنا فيحلّ الأسماء من globals هذه الوحدة — قانون D-168).
from app.api.routers.customer_chat_support.frames import (
    _bind_local_conversation_id,  # noqa: F401 — re-export (D-168 late-binding)
    _bind_stream_metadata,
    _emit_terminal_frames,
    _extract_client_context_messages,
    _merge_history_with_client_context,
    _try_build_math_ui_component,
)
from app.api.routers.customer_chat_support.pedagogy import (  # noqa: F401
    _apply_complete_response_firewall,
    _apply_final_answer_redaction,
    _build_pedagogy_directive,
    _count_confusion_signals,
    _derive_correctness_override,
    _evaluate_bkt_cards,
    _PedagogySnapshot,
    _persist_ui_component_cards,
    _semantic_tutor_enabled,
    _strip_display_garbage,
)
from app.api.routers.customer_chat_support.transport import (  # noqa: F401
    _TURN_KEEPALIVE_INTERVAL_SECONDS,
    TEXT_EVENT_TYPES,
    _is_text_event,
    _locked_send_json,
    _run_turn_keepalive,
    _ws_is_connected,
)

COMPATIBILITY_FACADE_MODE = True
# تنبيه معماري: هذا المسار واجهة توافقية فقط ويُمنع فيه أي تنفيذ محلي لمنطق الدردشة.
CANONICAL_EXECUTION_AUTHORITY = "orchestrator-service:/agent/chat"
LEGACY_LOCAL_EXECUTION_BLOCKED = True

router = APIRouter(
    prefix="/api/chat",
    tags=["Customer Chat"],
)


def get_chat_actor(
    current: CurrentUser = Depends(require_permissions(QA_SUBMIT)),
) -> CurrentUser:
    """تبعية تضمن امتلاك صلاحية الأسئلة التعليمية."""
    return current


def get_current_user_id(current: CurrentUser = Depends(get_chat_actor)) -> int:
    """إرجاع معرف المستخدم الحالي بعد تحقق الصلاحيات."""
    return current.user.id


async def get_actor_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    جلب كائن المستخدم الفعلي بعد التحقق من الحالة.
    """
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")
    await db.refresh(user)
    db.expunge(user)
    return user


def get_customer_service(
    db: AsyncSession = Depends(get_db),
) -> CustomerChatBoundaryService:
    """تبعية للحصول على خدمة حدود محادثة العملاء."""
    return CustomerChatBoundaryService(db)


@router.websocket("/ws")
async def chat_stream_ws(
    websocket: WebSocket,
) -> None:
    """
    قناة WebSocket لبث محادثة تعليمية للمستخدم القياسي.

    D-WS-002: يجب استدعاء accept() قبل close() دائماً.
    استدعاء close() قبل accept() يُنتج HTTP 403 من uvicorn بدلاً من
    رسالة خطأ واضحة — هذا يُربك المتصفح ويُسبب reconnect loop.
    الحل: accept() أولاً ثم إرسال رسالة خطأ JSON ثم close().
    """
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
        # D-WS-002: accept() أولاً لتجنب HTTP 403 من uvicorn
        await websocket.accept(subprotocol=selected_protocol)
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Authentication required. Please log in.",
                        "code": "WS_AUTH_MISSING",
                        "status_code": 4401,
                    },
                }
            )
        )
        await websocket.close(code=4401)
        return

    # ISS-100 (D-WS-CONN-001 — 2026-05-29): الهوية من الـ JWT فقط — بلا أي
    # استعلام لقاعدة البيانات عند الاتصال.
    #
    # الكارثة المُصلَحة (تأرجح متصل/غير متصل + لا إجابة حتى للتحية في الثواني
    # الأولى): الكود السابق كان ينفّذ ``db.get(User)`` على Supabase عند كل اتصال.
    # تحت ضغط Supabase (استنفاد pool / بطء / انقطاع) كان يفشل → إغلاق 1013 →
    # الواجهة تُعيد الاتصال → يفشل ثانية → تأرجح مستمر؛ الاتصال لا يثبت أبداً
    # فلا تُعالَج حتى رسالة «السلام عليكم». الهوية (المعرّف + is_admin) موجودة
    # في الـ JWT الموقّع، فلا داعي لقاعدة البيانات لإنشاء الاتصال. عمل قاعدة
    # البيانات يحدث لكل دور داخل جلسته الخاصة مع معالجة أخطائه دون إسقاط الاتصال.
    try:
        claims = decode_token_payload(token, get_settings().SECRET_KEY)
        user_id = int(claims["sub"])
    except (HTTPException, KeyError, TypeError, ValueError):
        await websocket.accept(subprotocol=selected_protocol)
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Invalid or expired token. Please log in again.",
                        "code": "WS_AUTH_INVALID",
                        "status_code": 4401,
                    },
                }
            )
        )
        await websocket.close(code=4401)
        return

    # ISS-103 (D-WS-CONN-002): is_admin يُشتق من claim ``is_admin`` صراحةً أو من
    # دور ``ADMIN`` ضمن ``roles`` (رمز الوصول الحقيقي يحمل ``roles`` لا ``is_admin``).
    # بدون اشتقاق الدور كان كل توكن حقيقي يُعطي is_admin=False → دردشة الإدمن
    # مرفوضة دائماً (admin.py: "Standard accounts must use the customer chat endpoint").
    _claim_roles = claims.get("roles") or []
    is_admin_claim = bool(claims.get("is_admin", False)) or (
        ADMIN_ROLE in _claim_roles if isinstance(_claim_roles, list) else False
    )
    actor = WsActor(id=user_id, is_admin=is_admin_claim)

    await websocket.accept(subprotocol=selected_protocol)

    if actor.is_admin:
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Admin accounts must use the admin chat endpoint.",
                        "status_code": 403,
                    },
                }
            )
        )
        await websocket.close(code=4403)
        return

    # D-096 (2026-05-28): قفل تسلسلي للـ WebSocket sends.
    # يُمنع التزامن بين BKT background task و stream_and_forward و
    # _emit_terminal_frames و handle_control_message.
    # السبب: Starlette WebSocket.send_json لا يضمن coroutine-safety
    # عند استدعاءات متزامنة → corruption → silent close → kick.
    send_lock = asyncio.Lock()

    # D-WS-FLAP-003 (2026-05-26): primer event — يُرسَل فور الـ accept لإجبار
    # كل الـ proxies على المسار (server.js, Codespaces edge, mobile carrier-NAT)
    # على فتح/الاحتفاظ بـ session نشط بدلاً من idle-timeout سريع.
    # الواجهة تتجاهل النوع غير المعروف (useAgentSocket لا يعالج "session_ready").
    try:
        async with send_lock:
            await websocket.send_json(
                {
                    "type": "session_ready",
                    "payload": {
                        "user_id": actor.id,
                        "ts": datetime.now(UTC).isoformat(),
                    },
                }
            )
    except Exception as exc:
        # primer non-fatal — لو فشل، السبب أن الـ socket أُغلق فوراً.
        logger.debug("customer_chat.primer_failed: %s", exc)

    try:
        while True:
            try:
                payload = await websocket.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                # D-ISS-092: receive_json() يُطلق RuntimeError عند إغلاق Codespaces proxy
                # للاتصال بشكل مفاجئ. نُعيد الـ raise ليُمسكه الـ except الخارجي بشكل نظيف.
                raise

            # D-WS-FLAP-002 (ISS-WS-FLAP-002): معالج heartbeat موحَّد كـ Skill.
            # رسائل التحكم (ping/heartbeat/noop) تُعالَج هنا قبل أي محاولة
            # لاعتبار الحمولة سؤالاً. بدون هذا الفحص، ping يُعاد إليه «Question is
            # required» بدلاً من pong → timeout بعد 10s → close(1001) → flapping.
            if await handle_control_message(websocket, payload, send_lock=send_lock):
                continue

            request_id_value = payload.get("client_request_id")
            client_request_id = (
                str(request_id_value).strip() if request_id_value is not None else None
            )
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
                            {
                                "type": "error",
                                "payload": {"details": "Question is required."},
                            }
                        ),
                        None,
                        stream_request_id,
                    ),
                )
                continue

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
                    # D-197: تعريف «طالبٌ نشِط» — دورُه. هذا الحدث هو أساس كلّ رقم
                    # احتفاظ. الكتابة معزولة ولا ترفع (التحليلات لا تكسر دوراً).
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
            except HTTPException as http_exc:
                await _locked_send_json(
                    websocket,
                    send_lock,
                    _bind_stream_metadata(
                        normalize_streaming_event(
                            {
                                "type": "error",
                                "payload": {
                                    "details": str(http_exc.detail),
                                    "status_code": http_exc.status_code,
                                },
                            }
                        ),
                        local_conversation_id,
                        stream_request_id,
                    ),
                )
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")
                continue
            except Exception as exc:
                logger.error(
                    f"Failed to persist customer user message locally: {exc}",
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
                continue

            # D-157 (ISS-124): تقييم BKT مؤجَّل إلى ما بعد حساب support_level +
            # الإشارة الرمزية (أدناه) — كان يُطلَق هنا فارغاً (support_level=None)
            # فيتجمّد durable على 0 وتُصبح فجوة الوهم بلا معنى. يبقى background task
            # (D-WS-FLAP-001) لكنه الآن يقرأ prior بعد قراءة البيداغوجيا له (يزيل
            # سباق read/write) ويحمل support_level + الأوراكل الرمزي.
            complete_ai_response = ""
            assistant_message_persisted = False
            orchestrator_persisted = False
            pending_terminal_event: dict[str, object] | None = None
            stream_task: asyncio.Task[None] | None = None
            stream_error: HTTPException | Exception | None = None
            # ISS-106 (D-WS-CARD-PERSIST-001): اجمع كل بطاقات ui_component المستقلة
            # المبثوثة خلال الدور (شجرة احتمالات، بطاقة شرح، قصة تمرين...) لحفظها
            # كصفوف مستقلة فتبقى بعد إعادة الدخول.
            captured_ui_components: list[dict[str, object]] = []

            # D-104/D-114: صورة المتعلم تقود عمق التدريس — التوجيه التربوي التكيفي
            # يُقرأ من إتقان BKT (fail-open، سقف 2s، جلسة DB معزولة) ويُمرَّر عبر
            # context ليُسبق في سؤال الـ LLM (orchestrator + fallbacks). support_level
            # يعبر السلسلة كاملةً ويحكم بوّابة المثال المحلول + إعفاء الحجب.
            pedagogy_snapshot = await _build_pedagogy_directive(
                user_id=actor.id,
                question=question,
                history_messages=history_messages,
            )
            pedagogy_directive = pedagogy_snapshot.directive_text
            support_level = pedagogy_snapshot.support_level

            # D-157: تقييم BKT الآن (بعد حساب support_level) — background task فلا يُحجب
            # البثّ (D-WS-FLAP-001)، ويحسب durable + فجوة الوهم (M9). الأوراكل الرمزي
            # (A1b) يُحسَب داخل المهمة (خلف الكواليس، خارج المسار الحيّ — D-119).
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
                lambda t: (
                    logger.debug("bkt_task_done err=%s", t.exception()) if t.exception() else None
                )
            )

            # D-142 Phase 2: ذاكرة جلسة التدريس الدائمة (خلف العلم SEMANTIC_TUTOR_ENABLED —
            # افتراضي OFF ⇒ صفر I/O جديد على المسار الحيّ). تُحمَّل قبل الدور وتُمرَّر عبر
            # context فينجو حارس التكرار/الانحراف من نافذة الـ50 رسالة. fail-open مطلق.
            tutor_state_ctx: dict[str, object] | None = None
            if _semantic_tutor_enabled() and local_conversation_id is not None:
                with contextlib.suppress(Exception):
                    async with async_session_factory() as _ts_db:
                        tutor_state_ctx = await TutorStateService(_ts_db).load(
                            local_conversation_id
                        )

            # D-115: التوليد التعليمي يحدث حصراً في الـ orchestrator (السلطة الوحيدة).
            # support_level يُمرَّر ليحكم عمق التلميح السقراطي هناك (لا مثال مكشوف
            # ولا توجيه LLM محقون — يَعكِس D-114 الذي تسبّب بالغارباج).

            try:

                async def stream_and_forward(
                    q=question,
                    lc_id=local_conversation_id,
                    meta=metadata,
                    history=history_messages,
                    request_id=stream_request_id,
                    captured=captured_ui_components,
                    pedagogy=pedagogy_directive,
                    sup_level=support_level,
                    tstate=tutor_state_ctx,
                ) -> None:
                    nonlocal pending_terminal_event
                    nonlocal complete_ai_response
                    nonlocal orchestrator_persisted
                    async for event in orchestrator_client.chat_with_agent(
                        question=q,
                        user_id=actor.id,
                        conversation_id=lc_id,
                        history_messages=history,
                        context={
                            "chat_scope": "customer",
                            "metadata": meta,
                            "compatibility_facade": True,
                            "pedagogy_directive": pedagogy,
                            "support_level": sup_level,
                            # D-142 Phase 2: الحالة الدائمة (None عند العلم OFF).
                            "tutor_state": tstate,
                        },
                    ):
                        # D-WS-FLAP-001: abort stream if client disconnected mid-turn.
                        # Without this check, send_json raises RuntimeError which
                        # escapes the task and corrupts the outer finally block state.
                        if not _ws_is_connected(websocket):
                            logger.info(
                                "customer_chat.stream_aborted: client disconnected mid-stream "
                                "(conversation_id=%s)",
                                lc_id,
                            )
                            return

                        normalized_event = normalize_streaming_event(event)

                        # ISS-STREAM-001: تصفية أحداث noop (أحداث غير معروفة من orchestrator)
                        if normalized_event.get("type") == "noop":
                            continue

                        # Prevent "Split-Brain" DB FK violation:
                        # Intercept Orchestrator's conversation_init and rewrite/strip conversation_id
                        # so the local frontend doesn't overwrite its local sequence with Orchestrator's sequence.
                        if normalized_event.get("type") == "conversation_init" and isinstance(
                            normalized_event.get("payload"), dict
                        ):
                            if lc_id is not None:
                                # Rewrite to the established local sequence
                                normalized_event["payload"]["conversation_id"] = lc_id
                            else:
                                # Strip it to avoid overwriting local state with a foreign ID
                                normalized_event["payload"].pop("conversation_id", None)

                        event_type = normalized_event.get("type")
                        if event_type in {"complete", "assistant_final"}:
                            # Detect orchestrator persistence signal
                            if normalized_event.get("persisted") is True:
                                orchestrator_persisted = True
                            pending_terminal_event = _bind_stream_metadata(
                                normalized_event, lc_id, request_id
                            )
                        else:
                            # ISS-106 (D-WS-CARD-PERSIST-001): اجمع بطاقات ui_component
                            # المستقلة لحفظها لاحقاً (تبقى بعد إعادة الدخول).
                            if event_type == "ui_component" and isinstance(
                                normalized_event.get("payload"), dict
                            ):
                                captured.append(dict(normalized_event["payload"]))
                            # D-115: مُطهّر العرض المُصفّح على كل delta نصّي — شبكة
                            # أمان فوق تنظيف الـ orchestrator (لا ⟦⟧ ولا تعليمات مُسرَّبة).
                            display_event = normalized_event
                            if _is_text_event(normalized_event) and isinstance(
                                normalized_event.get("payload"), dict
                            ):
                                _disp = normalized_event["payload"].get("content")
                                if isinstance(_disp, str) and _disp:
                                    display_event = {
                                        **normalized_event,
                                        "payload": {
                                            **normalized_event["payload"],
                                            "content": _strip_display_garbage(_disp),
                                        },
                                    }
                            # D-096: send_lock يمنع التزامن مع BKT task
                            await _locked_send_json(
                                websocket,
                                send_lock,
                                _bind_stream_metadata(display_event, lc_id, request_id),
                            )

                        if _is_text_event(normalized_event) and isinstance(
                            normalized_event.get("payload"), dict
                        ):
                            chunk_text = normalized_event["payload"].get("content")
                            if isinstance(chunk_text, str) and chunk_text:
                                # D-115: التراكم النظيف (لا غارباج في النسخة المحفوظة).
                                complete_ai_response += _strip_display_garbage(chunk_text)

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
                logger.error(
                    f"HTTPException in compatibility facade stream: {http_exc}", exc_info=True
                )
            except Exception as exc:
                stream_error = exc
                logger.error(f"Error in compatibility facade stream: {exc}", exc_info=True)
                # D-096: locked send + state check
                if (
                    not isinstance(exc, WebSocketDisconnect)
                    and websocket.client_state == WebSocketState.CONNECTED
                ):
                    try:
                        await _locked_send_json(
                            websocket,
                            send_lock,
                            normalize_streaming_event(
                                {
                                    "type": "error",
                                    "payload": {"details": str(exc), "status_code": 500},
                                }
                            ),
                        )
                    except (WebSocketDisconnect, RuntimeError) as _send_err:
                        logger.debug(
                            "customer_chat.error_send_failed: %s", type(_send_err).__name__
                        )
            finally:
                if stream_task is not None and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        logger.info("Cancelled customer stream task after disconnect/finalization")

                # ── Persistence decision (single-writer coordination) ──
                # Monolith owns the message. If Orchestrator already persisted
                # (signaled via persisted=True on terminal event), skip local write;
                # otherwise fail-safe write. Absence of signal is treated as failure.
                # D-086 (V46.0): تطبيق OutputFirewall على الإجابة المكتملة
                # قبل الحفظ في DB — يضمن نقاء القناة B في السجل الدائم.
                if complete_ai_response:
                    complete_ai_response = _apply_complete_response_firewall(complete_ai_response)
                    # D-113/D-115: حجب الإجابة النهائية على النسخة المحفوظة — شبكة أمان
                    # حتمية ضد كشف الجواب (لا كشف في التدفّق العادي؛ الكشف لوضع مراجعة منفصل).
                    complete_ai_response = _apply_final_answer_redaction(
                        complete_ai_response, support_level
                    )

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
                        _assistant_card = _try_build_math_ui_component(
                            complete_ai_response.replace("\x00", "")
                        )
                        for _attempt in range(2):
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
                                    logger.info(
                                        "[DATA_LOSS_PREVENTED] Fallback persistence succeeded."
                                    )
                                break
                            except Exception as persistence_exc:
                                logger.error(
                                    (
                                        "Failed to persist customer assistant message locally "
                                        f"for conversation {local_conversation_id} "
                                        f"(attempt {_attempt + 1}/2): {persistence_exc}"
                                    ),
                                    exc_info=True,
                                )

                        if not assistant_message_persisted:
                            logger.error(
                                "[CRITICAL_DATA_LOSS] Fallback persistence completely failed for "
                                f"conversation {local_conversation_id}."
                            )

                # ── Persist standalone generative-UI cards (ISS-106) ──
                # كل بطاقة ui_component مستقلة بُثَّت خلال الدور (شجرة احتمالات، قصة
                # تمرين، بطاقة شرح...) تُحفظ كصف مساعد content="" لتُصيَّر من التاريخ
                # بعد إعادة الدخول. غير حرج: أي فشل يُسجَّل ولا يكسر إنهاء الدور.
                if captured_ui_components and local_conversation_id is not None:
                    await _persist_ui_component_cards(
                        conversation_id=local_conversation_id,
                        cards=captured_ui_components,
                    )

                # ── Guaranteed terminal frame ──
                # Exactly one terminal event (assistant_final or error) per turn,
                # so the UI never hangs. `persisted` is emitted only after a real save.
                # D-WS-FLAP-001: wrapped in try/except — if the client disconnected
                # mid-stream, send_json raises RuntimeError/WebSocketDisconnect.
                # Without this guard the exception escapes finally, the loop retries
                # receive_json on a dead socket, and the client sees a flapping pattern.
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

                # ── D-119: التتبّع المعرفي خلف الكواليس — لا بطاقة للطالب ──
                # نضمن اكتمال كتابة BKT التحليلية (append-only — D-074، تغذّي
                # support_level) + تسجيل المسار التعلّمي قبل إنهاء الدور. لا
                # بطاقات تُبثّ أو تُحفظ للطالب (قرار المالك D-119: «تتبّع المعرفة»
                # و«ترسيخ المهارة» خلف الكواليس، لا في سطح الطالب). معزول كلياً.
                with contextlib.suppress(Exception):
                    await _bkt_task

                # D-142 Phase 2: تحديث ذاكرة جلسة التدريس الدائمة (خلف العلم، fail-open).
                # يضبط آخر خطوة عُرضت (مرساة منع التكرار تنجو من النافذة) + المفهوم النشط +
                # ميزانية المفهوم + قدرة الطالب (من BKT) — صف حيّ واحد لكل محادثة (upsert).
                if (
                    _semantic_tutor_enabled()
                    and local_conversation_id is not None
                    and complete_ai_response
                ):
                    with contextlib.suppress(Exception):
                        _is_socratic_q = complete_ai_response.rstrip().endswith(("؟", "?"))
                        async with async_session_factory() as _ts_db2:
                            # D-144: Pull policy_decision injected by OrchestratorClient
                            policy_decision = (
                                tutor_state_ctx.get("policy_decision") if tutor_state_ctx else None
                            )

                            learning_stage = (
                                policy_decision.learning_stage if policy_decision else "definition"
                            )
                            representation_used = (
                                policy_decision.representation if policy_decision else "text"
                            )
                            interventions_used = (
                                tutor_state_ctx.get("interventions_used", [])
                                if tutor_state_ctx
                                else []
                            )

                            # Log intervention
                            if policy_decision:
                                interventions_used.append(
                                    f"{learning_stage}_{policy_decision.next_action}"
                                )

                            # D-158: دلتا تقدّم المكوّنات المعرفية (يبنيها _cognitive_turn،
                            # يحقنها في dict tutor_state المشترك). المصدر الوحيد لِـ
                            # representations_delivered / _pending الذي يقتل التكرار عبر الكتل.
                            _kc_delta = (
                                tutor_state_ctx.get("kc_progress_delta")
                                if tutor_state_ctx
                                else None
                            )
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

                # Close path-aware span exactly once per turn — final event type
                # mirrors what `_emit_terminal_frames` actually sent.
                if assistant_message_persisted:
                    turn_span.set_terminal("assistant_final")
                    close_ws_turn(turn_span, status="OK")
                else:
                    turn_span.set_terminal("error")
                    close_ws_turn(turn_span, status="ERROR")

    except (WebSocketDisconnect, RuntimeError) as exc:
        # RuntimeError: "WebSocket is not connected" — يحدث عندما يُغلق Codespaces proxy
        # الاتصال بشكل مفاجئ قبل أن يُكمل receive_json(). بدون هذا الـ catch،
        # الـ exception يهرب إلى ASGI layer ويُسبب "Exception in ASGI application"
        # مما يُعيد تشغيل الـ connection loop في الـ frontend → kick-to-login flapping.
        if isinstance(exc, RuntimeError):
            logger.info("customer_chat.ws_runtime_disconnect: %s", exc)
        else:
            logger.info("Customer WebSocket disconnected")


@router.get(
    "/latest",
    summary="استرجاع آخر محادثة",
    response_model=CustomerConversationDetails | None,
)
async def get_latest_chat(
    actor: User = Depends(get_actor_user),
    service: CustomerChatBoundaryService = Depends(get_customer_service),
) -> CustomerConversationDetails | None:
    conversation_data = await service.get_latest_conversation_details(actor)
    if not conversation_data:
        return None
    return CustomerConversationDetails.model_validate(conversation_data)


@router.get(
    "/conversations",
    summary="سرد المحادثات",
    response_model=list[CustomerConversationSummary],
)
async def list_conversations(
    actor: User = Depends(get_actor_user),
    service: CustomerChatBoundaryService = Depends(get_customer_service),
) -> list[CustomerConversationSummary]:
    results = await service.list_user_conversations(actor)
    return [CustomerConversationSummary.model_validate(r) for r in results]


@router.get(
    "/conversations/{conversation_id}",
    summary="تفاصيل محادثة",
    response_model=CustomerConversationDetails,
    description="استرجاع تفاصيل محادثة محددة.",
    operation_id="chatConversationGet",
)
async def get_conversation(
    conversation_id: int,
    actor: User = Depends(get_actor_user),
    service: CustomerChatBoundaryService = Depends(get_customer_service),
) -> CustomerConversationDetails:
    data = await service.get_conversation_details(actor, conversation_id)
    return CustomerConversationDetails.model_validate(data)
