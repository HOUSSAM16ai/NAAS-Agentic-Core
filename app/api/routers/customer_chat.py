"""
واجهة برمجة تطبيقات محادثة العملاء القياسيين.

توفر نقاط النهاية الخاصة بالمستخدمين القياسيين للوصول إلى محادثة تعليمية
مع فرض سياسات الأمان والملكية.

## V46.0 — جدار الحماية المزدوج للقنوات

يُطبَّق OutputFirewall على complete_ai_response المُجمَّع قبل الحفظ في DB.
هذا يضمن أن أي HTML/JSX تسرَّب من LLM يُنظَّف قبل الوصول للطالب أو قاعدة البيانات.

D-086 (2026-05-23): تطبيق Protocol V46.0.

## D-173 Stage 3 (2026-08-13): تفكيك hotspot

كانت `chat_stream_ws` تحوي 669 سطراً (CodeScene hotspot: التعقيد 69، تردد تغيير 53)
— الدالة الأسوأ في المستودع كله. القرار المعماري (D-173 S3): الدالة هنا تبقى «قشرة
استقبال» فقط — اتصال/مصادقة/accept/primer وحلقة receive واحدة — وكل منطق الدور
يُفوَّض إلى وحدة واحدة `customer_chat_support.turn_lifecycle.handle_turn`
(افتتاح DB ⇒ قراءة بيداغوجية ⇒ BKT ⇒ بثّ وتوجيه ⇒ كتلة الإغلاق الحتمية).
السلوك مطابق حرفيًّا للنسخة السابقة بلا أي تغيير سلوكي، وكل الشواهد المعمارية
(D-* / ISS-*) محفوظة في مواضعها عبر إعادة التصدير (re-export، قانون late-binding D-168).
"""

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

# ── D-173 Stage 3: منطق الدور في `customer_chat_support/turn_lifecycle.py` (compound source) ──
from app.api.routers.customer_chat_support.turn_lifecycle import (  # noqa: F401 (D-252: إعادة تصدير لاختبارات patch النصية على القشرة)
    _semantic_tutor_enabled,
    handle_turn,
)
from app.api.routers.ws_auth import WsActor, extract_websocket_auth
from app.api.schemas.customer_chat import (
    CustomerConversationDetails,
    CustomerConversationSummary,
)
from app.core.config import get_settings
from app.core.database import (
    async_session_factory,  # noqa: F401 (D-252: إعادة تصدير لاختبار error contract)
    get_db,
)
from app.core.di import get_logger
from app.core.domain.user import User
from app.deps.auth import CurrentUser, require_permissions
from app.infrastructure.clients.orchestrator_client import (
    orchestrator_client,  # noqa: F401 (D-252: إعادة تصدير لاختبار D-045 patch)
)
from app.services.auth.token_decoder import decode_token_payload
from app.services.boundaries.customer_chat_boundary_service import (
    CustomerChatBoundaryService,
)
from app.services.rbac import ADMIN_ROLE, QA_SUBMIT
from app.services.skills.ws_heartbeat_skill import handle_control_message
from shared.chat_protocol.event_protocol import normalize_streaming_event

logger = get_logger(__name__)

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

    D-173 Stage 3: الدالة قشرة استقبال فقط — كل منطق الدور مفوَّض إلى
    `customer_chat_support.turn_lifecycle.handle_turn`.
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
    # الواجهة تعيد الاتصال → يفشل ثانية → تأرجح مستمر؛ الاتصال لا يثبت أبداً
    # فلا تُعالَج حتى رسالة «السلام عليكم». الهوية (المعرف + is_admin) موجودة
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
    # بدون اشتقاق الدور كان كل توكن حقيقي يعطي is_admin=False → دردشة الإدمن
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
    # يمنع التزامن بين BKT background task و stream_and_forward و
    # _emit_terminal_frames و handle_control_message.
    # السبب: Starlette WebSocket.send_json لا يضمن coroutine-safety
    # عند استدعاءات متزامنة → corruption → silent close → kick.
    send_lock = asyncio.Lock()

    # D-WS-FLAP-003 (2026-05-26): primer event — يُرسل فور الـ accept لإجبار
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
                # D-ISS-092: receive_json() يطلق RuntimeError عند إغلاق Codespaces proxy
                # للاتصال بشكل مفاجئ. نعيد الـ raise ليمسكه الـ except الخارجي بشكل نظيف.
                raise

            # D-WS-FLAP-002 (ISS-WS-FLAP-002): معالج heartbeat موحَّد كـ Skill.
            # رسائل التحكم (ping/heartbeat/noop) تُعالَج هنا قبل أي محاولة
            # لاعتبار الحمولة سؤالاً. بدون هذا الفحص، ping يعاد إليه «Question is
            # required» بدلاً من pong → timeout بعد 10s → close(1001) → flapping.
            if await handle_control_message(websocket, payload, send_lock=send_lock):
                continue

            # D-173 Stage 3: كل منطق الدور (DB + بيداغوجيا + BKT + بثّ + إغلاق
            # حتمي) مفوَّض إلى وحدة دورة الدور الواحدة — الدالة هنا تستقبل فقط.
            await handle_turn(
                websocket=websocket,
                send_lock=send_lock,
                actor=actor,
                payload=payload,
            )

    except (WebSocketDisconnect, RuntimeError) as exc:
        # RuntimeError: "WebSocket is not connected" — يحدث عندما يُغلق Codespaces proxy
        # الاتصال بشكل مفاجئ قبل أن يُكمل receive_json(). بدون هذا الـ catch،
        # الـ exception يهرب إلى ASGI layer ويُسبب "Exception in ASGI application"
        # مما يعيد تشغيل الـ connection loop في الـ frontend → kick-to-login flapping.
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
