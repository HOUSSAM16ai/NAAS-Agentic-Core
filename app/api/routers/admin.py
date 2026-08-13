# app/api/routers/admin.py
"""
واجهة برمجة تطبيقات المسؤول (Admin API).
---------------------------------------------------------
توفر هذه الوحدة نقاط النهاية (Endpoints) الخاصة بالمسؤولين،
وتعتمد بشكل كامل على خدمة `AdminChatBoundaryService` لفصل المسؤوليات.
تتبع نمط "Presentation Layer" فقط، ولا تحتوي على أي منطق عمل.
المعايير:
- توثيق شامل باللغة العربية.
- صرامة في تحديد الأنواع (Strict Typing).
- اعتماد كامل على حقن التبعيات (Dependency Injection).

D-249 (2026-08-13) — جراحة النقطة الساخنة (CodeScene X-Ray):
`chat_stream_ws` كان Complexity=440 و 32 commit و 51 churn (hotspot الأول).
قُسمت إلى دوال صغيرة نقية (auth / turn persistence / streaming / persistence
decision / terminal frames) دون أي تغيير سلوكي — كل مسار خطأ وحدث وتوقيت
مطابق تماماً لما قبل الجراحة (نمط D-164: zero-behavioural-change refactoring).
`_emit_terminal_frames` (Complexity=71 · 9 args → PLR0917) يُمرَّر الآن كسياق
واحد `_TurnFinalizationContext`.
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import typing as _t
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.routers.ws_auth import WsActor, extract_websocket_auth
from app.api.schemas.admin import (
    ConversationDetailsResponse,
    ConversationSummaryResponse,
)
from app.core.config import get_settings
from app.core.database import async_session_factory, get_db
from app.core.di import get_logger
from app.core.domain.chat import MessageRole
from app.core.domain.user import User
from app.deps.auth import CurrentUser, get_current_user, require_roles
from app.infrastructure.clients.orchestrator_client import orchestrator_client
from app.infrastructure.clients.user_client import user_client
from app.services.auth.token_decoder import decode_token_payload
from app.services.boundaries.admin_chat_boundary_service import AdminChatBoundaryService
from app.services.rbac import ADMIN_ROLE
from app.services.skills.ws_heartbeat_skill import handle_control_message
from app.telemetry.path_observer import close_ws_turn, open_ws_turn
from shared.chat_protocol.event_protocol import normalize_streaming_event

logger = get_logger(__name__)

COMPATIBILITY_FACADE_MODE = True

# تنبيه معماري: هذا المسار واجهة توافقية فقط ويُمنع فيه أي تنفيذ محلي لمنطق الدردشة.
CANONICAL_EXECUTION_AUTHORITY = "orchestrator-service:/agent/chat"
LEGACY_LOCAL_EXECUTION_BLOCKED = True

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)

TEXT_EVENT_TYPES = {"delta", "assistant_delta", "assistant_final"}

# -----------------------------------------------------------------------------
# DTOs
# -----------------------------------------------------------------------------


class AdminUserCountResponse(BaseModel):
    count: int


# -----------------------------------------------------------------------------
# WebSocket primitives (unchanged behaviour — D-WS-FLAP / ISS-098 guards)
# -----------------------------------------------------------------------------


def _is_text_event(event: dict[str, object]) -> bool:
    """يتحقق من أن الحدث نصي ومسموح بتجميعه داخل مخزن النص النهائي."""
    return str(event.get("type", "")) in TEXT_EVENT_TYPES


def _ws_is_connected(websocket: WebSocket) -> bool:
    """يتحقق من أن WebSocket لا يزال في حالة CONNECTED قبل أي send_json.

    D-WS-FLAP-001: يمنع RuntimeError عند محاولة الإرسال على socket مغلق،
    وهو السبب الجذري لنمط الـ flapping (يعمل → يتعطل → يعود).
    """
    return websocket.client_state == WebSocketState.CONNECTED


async def _locked_send_json(
    websocket: WebSocket,
    lock: asyncio.Lock,
    payload: dict[str, object],
) -> None:
    """يُسلسل كل عمليات send_json على نفس الـ WebSocket عبر قفل واحد.

    D-096 (parity مع customer_chat): Starlette `WebSocket.send_json` ليس
    آمناً عند الاستدعاء المتزامن من أكثر من coroutine (مثلاً مهمة البثّ
    + مهمة الـ keepalive لـ ISS-098). بدون القفل تتداخل أُطر ASGI →
    إغلاق صامت → reconnect → طرد. القفل يضمن إرسالاً ذرياً واحداً تلو الآخر.
    """
    async with lock:
        await websocket.send_json(payload)


async def _send_ws_error(
    websocket: WebSocket,
    lock: asyncio.Lock | None,
    details: str,
    *,
    code: int | None = None,
    status_code: int,
    error_code: str | None = None,
    subprotocol: str | None = None,
) -> None:
    """D-WS-002: قبول أولاً ثم رسالة خطأ JSON ثم إغلاق — يمنع HTTP 403.

    موحّد هنا لأن النمط (accept → error JSON → close) كان مكرَّراً 3 مرات
    في `chat_stream_ws` قبل الجراحة (D-249). لا تغيير سلوكي إطلاقاً.

    ملاحظة السلوك المطابق للأصل: القبول يتم عبر ``accept(subprotocol=...)``
    فقط عندما يكون المقبس لم يقبل بعد؛ بعد القبول يُرسل الحدث مباشرة على
    القفل المعطى (أو دونه) ثم الإغلاق — إعادة القبول على مقبس مقبول
    كانت سبب ``RuntimeError: Expected websocket.send`` في الاختبارات.
    """
    payload: dict[str, object] = {"type": "error", "payload": {"details": details}}
    error_payload = payload["payload"]
    if status_code:
        error_payload["status_code"] = status_code
    if error_code is not None:
        error_payload["code"] = error_code
    if not _ws_is_connected(websocket):
        await websocket.accept(subprotocol=subprotocol)
    await (
        _locked_send_json(websocket, lock, normalize_streaming_event(payload))
        if lock is not None
        else websocket.send_json(normalize_streaming_event(payload))
    )
    if code is not None:
        await websocket.close(code=code)


# ISS-098 (D-WS-FLAP-005 — 2026-05-29): فاصل الـ keepalive أثناء بثّ الدور.
_TURN_KEEPALIVE_INTERVAL_SECONDS = 20.0


async def _run_turn_keepalive(websocket: WebSocket, lock: asyncio.Lock) -> None:
    """يُرسل إطار pong خفيفاً كل ~20s أثناء بثّ دور محادثة المسؤول.

    نفس جذر ISS-098 في customer_chat: حلقة الاستقبال محجوبة طوال
    `await stream_task`، فلا يُرسل pong → دور طويل (زمن Supabase) يتجاوز
    HEARTBEAT_TIMEOUT على العميل → close(1001) كاذب → reconnect → ضياع
    الإجابة. الـ keepalive يُبقي العميل حياً عبر `send_lock`. لا يرفع أبداً.
    """
    try:
        while True:
            await asyncio.sleep(_TURN_KEEPALIVE_INTERVAL_SECONDS)
            if not _ws_is_connected(websocket):
                return
            try:
                await _locked_send_json(
                    websocket, lock, {"type": "pong", "payload": {"keepalive": True}}
                )
            except (WebSocketDisconnect, RuntimeError):
                return
            except Exception as exc:  # pragma: no cover - دفاعي
                logger.debug("admin_chat.keepalive_send_failed: %s", type(exc).__name__)
                return
    except asyncio.CancelledError:
        return


def _bind_local_conversation_id(
    event: dict[str, object], conversation_id: int | None
) -> dict[str, object]:
    """يربط معرف المحادثة المحلي بأحداث البث لحماية سياق المسؤول من التلوث."""
    if conversation_id is None:
        return event
    payload = event.get("payload")
    if isinstance(payload, dict):
        payload["conversation_id"] = conversation_id
    else:
        event["payload"] = {"conversation_id": conversation_id}
    return event


def _bind_stream_metadata(
    event: dict[str, object],
    conversation_id: int | None,
    request_id: str | None,
) -> dict[str, object]:
    """يربط معرف المحادثة ومعرف الطلب في الحدث لعزل الدفق الإداري."""
    bound_event = _bind_local_conversation_id(event, conversation_id)
    if not request_id:
        return bound_event
    payload = bound_event.get("payload")
    if isinstance(payload, dict):
        payload["request_id"] = request_id
    else:
        bound_event["payload"] = {"request_id": request_id}
    return bound_event


def _extract_client_context_messages(payload: dict[str, object]) -> list[dict[str, str]]:
    """استخراج سياق محادثة الواجهة مع تنظيف الأدوار والمحتوى."""
    raw_context = payload.get("client_context_messages")
    if not isinstance(raw_context, list):
        return []

    sanitized: list[dict[str, str]] = []
    for item in raw_context:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"}:
            continue
        if not isinstance(content, str):
            continue
        text = content.strip()
        if not text:
            continue
        sanitized.append({"role": role, "content": text})
        if len(sanitized) >= 50:
            break
    return sanitized


def _find_tail_overlap_index(
    persisted_tail: list[dict[str, str]], client_context: list[dict[str, str]]
) -> int | None:
    """تحديد موضع بداية ذيل `persisted_tail` داخل `client_context` (آخر تطابق).

    D-249: استُخرج من `_merge_history_with_client_context` لتخفيض تعقيده
    (33 → أقل) — نفس الخوارزمية نفسها بايتاً: بحث عكسي عن نافذة مطابقة.
    """
    max_start = len(client_context) - len(persisted_tail)
    for start in range(max_start, -1, -1):
        window = client_context[start : start + len(persisted_tail)]
        if window == persisted_tail:
            return start + len(persisted_tail)
    return None


def _merge_history_with_client_context(
    persisted_history: list[dict[str, str]],
    client_context: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    دمج تاريخ المحادثة المخزّن مع سياق العميل مع منع تسريب رسائل محادثات أخرى.

    يعتمد على كشف التداخل بين ذيل persisted_history وبداية client_context
    لضمان أن الرسائل المضافة تنتمي فعلاً لنفس المحادثة.
    """
    if not client_context:
        return persisted_history
    if not persisted_history:
        return []

    persisted_tail = persisted_history[-3:] if len(persisted_history) >= 3 else persisted_history
    overlap_index = _find_tail_overlap_index(persisted_tail, client_context)
    if overlap_index is None:
        return persisted_history

    safe_client_tail = client_context[overlap_index:][-12:]
    merged_history = list(persisted_history)
    for message in safe_client_tail:
        if message not in merged_history:
            merged_history.append(message)
    return merged_history[-80:]


# -----------------------------------------------------------------------------
# Turn finalization — D-249: 9 kwargs → single context object (kills PLR0917)
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class _TurnFinalizationContext:
    """سياق إغلاق الدور: يجمع كل حالة البث في قيمة واحدة بدل 9 وسائط.

    D-249: `_emit_terminal_frames` كان يخالف PLR0917 (too-many-positional-
    arguments — نشط في CI منذ ruff 0.16) بتسعة وسائط keyword-only. نفس
    المنطق، نفس الترتيب الزمني للأُطر، صفر تغيير سلوكي.
    """

    websocket: WebSocket
    send_lock: asyncio.Lock
    pending_terminal_event: dict[str, object] | None
    assistant_message_persisted: bool
    complete_ai_response: str
    stream_error: BaseException | None
    local_conversation_id: int | None
    stream_request_id: str


async def _emit_terminal_frames(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    *,
    pending_terminal_event: dict[str, object] | None,
    assistant_message_persisted: bool,
    complete_ai_response: str,
    stream_error: BaseException | None,
    local_conversation_id: int | None,
    stream_request_id: str,
) -> None:
    """
    يضمن إرسال إطار نهائي واحد فقط لكل دور (assistant_final أو error)
    وإطار 'persisted' فقط بعد حفظ فعلي. لا يُسمح بالفشل الصامت
    الذي يبقي واجهة المستخدم في حالة تحميل أبدية (ISS-016/ISS-017).

    D-096: كل الإرسال عبر send_lock لتفادي التداخل مع مهمة الـ keepalive.
    """
    if assistant_message_persisted:
        if pending_terminal_event is not None:
            await _locked_send_json(websocket, send_lock, pending_terminal_event)
        else:
            await _locked_send_json(
                websocket,
                send_lock,
                _bind_stream_metadata(
                    normalize_streaming_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    ),
                    local_conversation_id,
                    stream_request_id,
                ),
            )
        await _locked_send_json(
            websocket,
            send_lock,
            _bind_stream_metadata(
                normalize_streaming_event({"type": "persisted"}),
                local_conversation_id,
                stream_request_id,
            ),
        )
        return

    if isinstance(stream_error, HTTPException):
        details = str(stream_error.detail)
        status_code = stream_error.status_code
    elif complete_ai_response or pending_terminal_event is not None:
        details = "Failed to confirm assistant persistence before completion."
        status_code = 500
    elif stream_error is not None:
        details = "Stream interrupted before assistant response completed."
        status_code = 500
    else:
        details = "Assistant produced no response."
        status_code = 500

    await _locked_send_json(
        websocket,
        send_lock,
        _bind_stream_metadata(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {"details": details, "status_code": status_code},
                }
            ),
            local_conversation_id,
            stream_request_id,
        ),
    )


def get_chat_actor(
    current: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """تبعية تُعيد المستخدم الحالي لاستخدام قنوات الدردشة الإدارية."""

    return current


def get_current_user_id(current: CurrentUser = Depends(get_chat_actor)) -> int:
    """
    إرجاع معرف المستخدم الحالي بعد التحقق من صلاحيات الأسئلة التعليمية.

    يعتمد هذا التابع على تبعية `get_chat_actor` لضمان أن المستدعي يملك
    التصاريح اللازمة قبل متابعة أي عمليات بث أو استعلامات خاصة بالمحادثات
    الإدارية.

    Args:
        current: كائن المستخدم الحالي المزود بالأدوار والصلاحيات.

    Returns:
        int: معرف المستخدم الموثق.
    """

    return current.user.id


async def get_actor_user(
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    الحصول على كائن المستخدم الفعلي بالاعتماد على معرفه.

    يوفر هذا التابع طبقة تجريد تُمكِّن من تجاوز التحقق في الاختبارات عبر
    إعادة تعريف `get_current_user_id`، مع الحفاظ على مسار التحقق الأساسي في
    بيئة الإنتاج.

    Args:
        user_id: معرف المستخدم المستخرج من التبعيات السابقة.
        db: جلسة قاعدة البيانات المستخدمة للاستعلام.

    Returns:
        User: كائن المستخدم الفعّال.

    Raises:
        HTTPException: إذا كان المستخدم غير موجود أو غير مفعّل.
    """

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="User inactive")

    # فصل الكائن عن الجلسة لضمان توفر بياناته أثناء البث الطويل دون الاصطدام بإغلاق الجلسة.
    await db.refresh(user)
    expunge_result = db.expunge(user)
    if inspect.isawaitable(expunge_result):
        await expunge_result

    return user


def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminChatBoundaryService:
    """تبعية للحصول على خدمة حدود محادثة المسؤول."""
    return AdminChatBoundaryService(db)


# -----------------------------------------------------------------------------
# Auth path (D-WS-CONN-001/002 — JWT-only connection identity)
# -----------------------------------------------------------------------------


# -----------------------------------------------------------------------------
# Turn persistence (per-turn DB session — errors never drop the connection)
# -----------------------------------------------------------------------------


@dataclass
class _PersistedTurn:
    """نتيجة حفظ دور واحد داخل جلسة DB خاصة به (ISS-100: فشل لا يسقط الاتصال)."""

    conversation_id: int | None = None
    history_messages: list[dict[str, str]] = field(default_factory=list)


async def _persist_user_turn(
    actor: WsActor,
    question: str,
    original_conversation_id: object,
    client_context_messages: list[dict[str, str]],
) -> _PersistedTurn:
    """حفظ المحادثة + رسالة المستخدم + دمج السياق داخل جلسة async_session خاصة.

    يعيد رسالة خطأ جاهزة للبث (`error_event`) عند فشل HTTPException أو خطأ عام —
    ولا يرمي أبداً (caller يختار المتابعة).
    """
    async with async_session_factory() as db:
        persistence_service = AdminChatBoundaryService(db)
        local_conversation = await persistence_service.get_or_create_conversation(
            actor,
            question,
            original_conversation_id,
        )
        conversation_id = local_conversation.id
        await persistence_service.save_message(
            conversation_id,
            MessageRole.USER,
            question,
        )
        history_messages = await persistence_service.get_chat_history(
            conversation_id,
            limit=50,
        )
        history_messages = _merge_history_with_client_context(
            history_messages,
            client_context_messages,
        )
        return _PersistedTurn(
            conversation_id=conversation_id,
            history_messages=history_messages,
        )


def _persist_error_event(
    exception: BaseException,
    *,
    conversation_id: int | None,
    request_id: str,
) -> dict[str, object]:
    """بناء حدث خطأ جاهز للبث من استثناء مرحلة الحفظ."""
    if isinstance(exception, HTTPException):
        details, status_code = str(exception.detail), exception.status_code
    else:
        details, status_code = "Failed to save your message locally.", 500
    return _bind_stream_metadata(
        normalize_streaming_event(
            {
                "type": "error",
                "payload": {
                    "details": details,
                    "status_code": status_code,
                },
            }
        ),
        conversation_id,
        request_id,
    )


# -----------------------------------------------------------------------------
# Orchestrator streaming task
# -----------------------------------------------------------------------------


@dataclass
class _StreamOutcome:
    """مخرجات مهمة البث `stream_and_forward` (D-249: حالة عبر dataclass لا nonlocals
    متناثرة — نفس المتغيرات نفس المعنى)."""

    pending_terminal_event: dict[str, object] | None = None
    complete_ai_response: str = ""
    orchestrator_persisted: bool = False
    stream_error: BaseException | None = None


async def _run_admin_turn_stream(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    actor: WsActor,
    local_conversation_id: int | None,
    question: str,
    history: list[dict[str, str]],
    metadata: dict[str, object],
    request_id: str,
    outcome: _StreamOutcome,
) -> None:
    """يدير مهمة بثّ دورة واحدة مع keepalive المتزامن (ISS-098 / D-WS-FLAP-005).

    د-249: استُخرجت من قلب حلقة `chat_stream_ws` — كانت `async def
    _admin_stream_and_forward` مغلقًا (closure) يأسر 9 متغيرات من الحلقة
    الخارجية، وهو نمط حجب القراءة ويكسر تحليل CodeScene وB023. الآن دالة
    عليا نقية تستقبل كل شيء صراحةً. السلوك مطابق بالبايت: نفس try/except
    الذي يحوّل `HTTPException`/الأخطاء العامة إلى `outcome.stream_error`،
    وفسخ keepalive بعد اكتمال البث، وإرسال حدث خطأ 500 عند الاستثناءات
    غير WebSocketDisconnect مع اتصال قائم.
    """
    try:
        await _stream_and_forward(
            websocket,
            send_lock,
            actor,
            local_conversation_id,
            question,
            history,
            metadata,
            request_id,
            outcome,
        )
    except HTTPException as http_exc:
        outcome.stream_error = http_exc
    except Exception as exc:
        outcome.stream_error = exc
        if not isinstance(exc, WebSocketDisconnect) and _ws_is_connected(websocket):
            with contextlib.suppress(WebSocketDisconnect, RuntimeError):
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


async def _stream_and_forward(
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    actor: WsActor,
    conversation_id: int | None,
    question: str,
    history: list[dict[str, str]],
    metadata: dict[str, object],
    request_id: str,
    outcome: _StreamOutcome,
) -> None:
    """البث من orchestrator مع إعادة التوجيه إلى الـ WebSocket.
    D-WS-FLAP-001: يتوقف فوراً عند انقطاع العميل. ISS-STREAM-001: يفلتر noop.
    يمنع "Split-Brain" عبر إعادة كتابة conversation_init إلى التسلسل المحلي.
    """
    _event_chain = orchestrator_client.chat_with_agent(
        question=question,
        user_id=actor.id,
        conversation_id=conversation_id,
        history_messages=history,
        context={
            "chat_scope": "admin",
            "metadata": metadata,
            "compatibility_facade": True,
        },
    )
    await _process_stream_event_chain(
        _event_chain,
        websocket,
        send_lock,
        actor,
        conversation_id,
        request_id,
        outcome,
    )


def _align_split_brain_event(event: dict[str, object], conversation_id: int | None) -> None:
    """منع انتهاك FK / "Split-Brain": إعادة كتابة أو نزع conversation_id.

    يتلقّى العميل محادثةً عبر تسلسلٍ محلي — إن زُوِّد بـ FK خاص بـ orchestrator
    يُستبدَل تسلسله المحلي بالتسلسل الغريب (D-164). التسلسل المحلي مقدَّس.
    """
    payload = event.get("payload")
    if event.get("type") != "conversation_init" or not isinstance(payload, dict):
        return
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    else:
        payload.pop("conversation_id", None)


def _is_terminal_event(event: dict[str, object]) -> bool:
    return event.get("type") in {"complete", "assistant_final"}


def _accumulate_text(event: dict[str, object], outcome: _StreamOutcome) -> None:
    """جمع نص الـ AI الكامل من أحداث النص — لإرساله إلى الـ orchestrator."""
    payload = event.get("payload")
    if not (_is_text_event(event) and isinstance(payload, dict)):
        return
    chunk_text = payload.get("content")
    if isinstance(chunk_text, str) and chunk_text:
        outcome.complete_ai_response += chunk_text


async def _process_stream_event_chain(
    event_chain: _t.AsyncIterable[object],
    websocket: WebSocket,
    send_lock: asyncio.Lock,
    actor: WsActor,
    conversation_id: int | None,
    request_id: str,
    outcome: _StreamOutcome,
) -> None:
    """حلقة البث الصافية (D-164): اتصال · noop · تصنيف · دمج.

    D-WS-FLAP-001: انقطاع العميل يُوقف الحلقة فوراً — لا RuntimeError هارب.
    ISS-STREAM-001: أحداث noop غير المعروفة تُفلتر.
    """
    async for event in event_chain:
        # D-WS-FLAP-001: انقطاع العميل يُوقف الحلقة فوراً — لا RuntimeError هارب.
        if not _ws_is_connected(websocket):
            logger.info(
                "admin_chat.stream_aborted: client disconnected mid-stream (conversation_id=%s)",
                conversation_id,
            )
            return

        normalized_event = normalize_streaming_event(event)
        if normalized_event.get("type") == "noop":
            continue

        # D-164: منع "Split-Brain" — التسلسل المحلي مقدَّس ولا يُستبدَل بـ FK غريب
        _align_split_brain_event(normalized_event, conversation_id)

        if _is_terminal_event(normalized_event):
            # Detect orchestrator persistence signal
            if normalized_event.get("persisted") is True:
                outcome.orchestrator_persisted = True
            outcome.pending_terminal_event = _bind_stream_metadata(
                normalized_event, conversation_id, request_id
            )
        else:
            await _locked_send_json(
                websocket,
                send_lock,
                _bind_stream_metadata(normalized_event, conversation_id, request_id),
            )

        _accumulate_text(normalized_event, outcome)


# -----------------------------------------------------------------------------
# Persistence decision (single-writer coordination — fail-safe write)
# -----------------------------------------------------------------------------


async def _decide_persistence(
    actor_id: int,
    local_conversation_id: int | None,
    outcome: _StreamOutcome,
) -> bool:
    """قرار الكاتب الواحد: إن لم يُثبِّت orchestrator → فشل-آمن محلي بنسختين.

    يعيد True إذا حُفظت رسالة المساعد (سواء من orchestrator أو محلياً).
    نفس القرار والرسائل السجلية [WRITE_DECISION]/[DATA_LOSS_PREVENTED]/
    [CRITICAL_DATA_LOSS] الموجودة قبل الجراحة — صفر تغيير سلوكي.
    """
    assistant_message_persisted = False
    if outcome.complete_ai_response and local_conversation_id is not None:
        if outcome.orchestrator_persisted:
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
            for attempt in range(2):
                try:
                    async with async_session_factory() as db:
                        persistence_service = AdminChatBoundaryService(db)
                        await persistence_service.save_message(
                            conversation_id=local_conversation_id,
                            role=MessageRole.ASSISTANT,
                            content=outcome.complete_ai_response.replace("\x00", ""),
                        )
                        assistant_message_persisted = True
                        logger.info("[DATA_LOSS_PREVENTED] Fallback persistence succeeded.")
                    break
                except Exception as persistence_exc:
                    logger.error(
                        (
                            "Failed to persist admin assistant message locally "
                            f"for conversation {local_conversation_id} "
                            f"(attempt {attempt + 1}/2): {persistence_exc}"
                        ),
                        exc_info=True,
                    )

            if not assistant_message_persisted:
                logger.error(
                    "[CRITICAL_DATA_LOSS] Fallback persistence completely failed for "
                    f"conversation {local_conversation_id}."
                )
    return assistant_message_persisted


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get(
    "/users/count",
    summary="User Count (Admin)",
    response_model=AdminUserCountResponse,
    dependencies=[Depends(require_roles(ADMIN_ROLE))],
)
async def get_admin_user_count() -> AdminUserCountResponse:
    """
    Retrieve the total number of users in the system.
    Proxies to the User Service.
    """
    try:
        count = await user_client.get_user_count()
        return AdminUserCountResponse(count=count)
    except Exception as e:
        logger.error(f"Failed to retrieve user count: {e}")
        raise HTTPException(status_code=503, detail="User Service unavailable") from e


@router.websocket("/api/chat/ws")
async def chat_stream_ws(
    websocket: WebSocket,
) -> None:
    """
    قناة WebSocket لبث محادثة المسؤول بشكل حي وآمن.

    D-WS-002: accept() قبل close() دائماً لتجنب HTTP 403 من uvicorn.
    D-249: الدالة الآن قشرة رشيقة — المصادقة/الحفظ/البث/الإغلاق في دوال نقية،
    دون أي تغيير سلوكي على مستوى الأُطر والأخطاء والتوقيتات.
    """
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
        await _send_ws_error(
            websocket,
            None,
            "Authentication required. Please log in.",
            code=4401,
            status_code=4401,
            error_code="WS_AUTH_MISSING",
            subprotocol=selected_protocol,
        )
        return

    # ISS-100 (D-WS-CONN-001 — 2026-05-29): الهوية من الـ JWT فقط — بلا استعلام
    # قاعدة بيانات عند الاتصال (نفس إصلاح customer_chat). الاعتماد القديم على
    # ``db.get(User)`` جعل كل اتصال رهيناً بـ Supabase → فشل تحت الضغط → إغلاق
    # 1013 → تأرجح متصل/غير متصل. is_admin يأتي من الـ JWT الموقّع.
    try:
        claims = decode_token_payload(token, get_settings().SECRET_KEY)
        user_id = int(claims["sub"])
    except (HTTPException, KeyError, TypeError, ValueError) as auth_exc:
        if not (isinstance(auth_exc, HTTPException) and auth_exc.status_code == 4401):
            auth_exc = HTTPException(
                status_code=4401,
                detail="Invalid or expired token. Please log in again.",
            )
        await websocket.accept(subprotocol=selected_protocol)
        try:
            await websocket.send_json(
                normalize_streaming_event(
                    {
                        "type": "error",
                        "payload": {
                            "details": "Invalid or expired token. Please log in again.",
                            "status_code": 4401,
                            "code": "WS_AUTH_INVALID",
                        },
                    }
                )
            )
        except Exception as _ws_auth_meta_err:
            logger.debug("admin_chat.ws_auth_meta_failed: %s", _ws_auth_meta_err)
        await websocket.close(code=4401)
        return

    # ISS-103 (D-WS-CONN-002): is_admin من claim ``is_admin`` أو دور ``ADMIN``.
    claim_roles = claims.get("roles") or []
    is_admin_claim = bool(claims.get("is_admin", False)) or (
        ADMIN_ROLE in claim_roles if isinstance(claim_roles, list) else False
    )
    actor = WsActor(id=user_id, is_admin=is_admin_claim)

    await websocket.accept(subprotocol=selected_protocol)

    if not actor.is_admin:
        # D-WS-002: accept() → رسالة خطأ → close(4403) — نفس النمط الموحَّد في
        # `_send_ws_error` لكن مع كود الإغلاق الثابت 4403 صراحةً (ISS-103).
        await websocket.send_json(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {
                        "details": "Standard accounts must use the customer chat endpoint.",
                        "status_code": 403,
                    },
                }
            )
        )
        await websocket.close(code=4403)
        return

    # D-096 (parity مع customer_chat): قفل واحد يُسلسل كل send_json على هذا
    # الـ WebSocket — يحمي ضد تداخل مهمة البثّ مع مهمة الـ keepalive (ISS-098).
    send_lock = asyncio.Lock()

    # D-WS-FLAP-003 (2026-05-26): primer event — يُرسل فور الـ accept لإجبار
    # كل الـ proxies على المسار (server.js, Codespaces edge, mobile carrier-NAT)
    # على الاحتفاظ بـ session نشط بدل idle-timeout سريع.
    try:
        await _locked_send_json(
            websocket,
            send_lock,
            {
                "type": "session_ready",
                "payload": {
                    "user_id": actor.id,
                    "ts": datetime.now(UTC).isoformat(),
                },
            },
        )
    except Exception as exc:
        logger.debug("admin_chat.primer_failed: %s", exc)

    try:
        while True:
            payload = await websocket.receive_json()

            # D-WS-FLAP-002 (ISS-WS-FLAP-002): heartbeat موحَّد كـ Skill.
            # ping/heartbeat/noop يُعالجون هنا قبل اعتبار الحمولة سؤالاً —
            # بدون هذا الفحص يُعاد للعميل خطأ «Question is required» بدل pong
            # → timeout 10s → close(1001) → flapping cycle.
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
                await websocket.send_json(
                    _bind_stream_metadata(
                        normalize_streaming_event(
                            {
                                "type": "error",
                                "payload": {"details": "Question is required."},
                            }
                        ),
                        None,
                        stream_request_id,
                    )
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

            turn_span = open_ws_turn(
                user_id=actor.id,
                conversation_id=None,
                is_admin=True,
                question=question,
                request_id=stream_request_id,
            )

            # ── حفظ رسالة المستخدم داخل جلسة DB خاصة (ISS-100) ──
            try:
                persisted_turn = await _persist_user_turn(
                    actor,
                    question,
                    original_conversation_id,
                    client_context_messages,
                )
                local_conversation_id = persisted_turn.conversation_id
                history = persisted_turn.history_messages
                turn_span.set_conversation_id(local_conversation_id)
                await websocket.send_json(
                    normalize_streaming_event(
                        {
                            "type": "conversation_init",
                            "payload": {
                                "conversation_id": local_conversation_id,
                                "request_id": stream_request_id,
                            },
                        }
                    )
                )
            except HTTPException as http_exc:
                await websocket.send_json(
                    _persist_error_event(
                        http_exc,
                        conversation_id=None,  # فشل قبل إنشاء المحادثة → بلا معرف محلي
                        request_id=stream_request_id,
                    )
                )
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")
                continue
            except Exception as exc:
                logger.error(
                    f"Failed to persist admin user message locally: {exc}",
                    exc_info=True,
                )
                await websocket.send_json(
                    _persist_error_event(
                        exc,
                        conversation_id=local_conversation_id,
                        request_id=stream_request_id,
                    )
                )
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")
                continue

            # ── البث مع keepalive ──
            outcome = _StreamOutcome()

            # ISS-098 (D-WS-FLAP-005): keepalive متزامن يمنع false
            # heartbeat-timeout على العميل أثناء الأدوار الطويلة.
            stream_task: asyncio.Task[None] | None = None
            try:
                stream_task = asyncio.create_task(
                    _run_admin_turn_stream(
                        websocket,
                        send_lock,
                        actor,
                        local_conversation_id,
                        question,
                        history,
                        metadata,
                        stream_request_id,
                        outcome,
                    )
                )
                keepalive_task = asyncio.create_task(_run_turn_keepalive(websocket, send_lock))
                try:
                    await stream_task
                finally:
                    keepalive_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, Exception):
                        await keepalive_task
            finally:
                if stream_task is not None and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        logger.info("Cancelled admin stream task after disconnect/finalization")

            # ── قرار الكاتب الواحد (fail-safe persistence) ──
            assistant_message_persisted = await _decide_persistence(
                actor.id,
                local_conversation_id,
                outcome,
            )

            # ── الإطار النهائي المضمون (دائماً إطار واحد: assistant_final أو error) ──
            # D-WS-FLAP-001: ملفوف بـ try/except — عند انقطاع العميل أثناء البث
            # يرمي send_json RuntimeError/WebSocketDisconnect. بدون هذه الحماية
            # يهرب الاستثناء من finally وتعيد الحلقة receive_json على مقبس ميت
            # فيرى العميل نمط flapping.
            try:
                await _emit_terminal_frames(
                    websocket,
                    send_lock,
                    pending_terminal_event=outcome.pending_terminal_event,
                    assistant_message_persisted=assistant_message_persisted,
                    complete_ai_response=outcome.complete_ai_response,
                    stream_error=outcome.stream_error,
                    local_conversation_id=local_conversation_id,
                    stream_request_id=stream_request_id,
                )
            except (WebSocketDisconnect, RuntimeError) as _ws_close_err:
                logger.info(
                    "admin_chat.terminal_frame_skipped: client already disconnected "
                    "(conversation_id=%s err=%s)",
                    local_conversation_id,
                    type(_ws_close_err).__name__,
                )

            # Close path-aware span exactly once per turn.
            if assistant_message_persisted:
                turn_span.set_terminal("assistant_final")
                close_ws_turn(turn_span, status="OK")
            else:
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")

    except (WebSocketDisconnect, RuntimeError) as exc:
        # RuntimeError: "WebSocket is not connected" — يحدث عندما يُغلق Codespaces proxy
        # الاتصال بشكل مفاجئ. بدون هذا الـ catch، يهرب إلى ASGI → ASGI crash → flapping.
        if isinstance(exc, RuntimeError):
            logger.info("admin_chat.ws_runtime_disconnect: %s", exc)
        else:
            logger.info("Admin WebSocket disconnected")


@router.get(
    "/api/chat/latest",
    summary="استرجاع آخر محادثة (Get Latest Conversation)",
    response_model=ConversationDetailsResponse | None,
)
async def get_latest_chat(
    actor: User = Depends(get_actor_user),
    service: AdminChatBoundaryService = Depends(get_admin_service),
) -> ConversationDetailsResponse | None:
    """
    استرجاع تفاصيل آخر محادثة للمستخدم الحالي.
    مفيد لاستعادة الحالة عند إعادة تحميل الصفحة.
    """
    if not actor.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    conversation_data = await service.get_latest_conversation_details(actor)
    if not conversation_data:
        return None
    return ConversationDetailsResponse.model_validate(conversation_data)


@router.get(
    "/api/conversations",
    summary="سرد المحادثات (List Conversations)",
    response_model=list[ConversationSummaryResponse],
)
async def list_conversations(
    actor: User = Depends(get_actor_user),
    service: AdminChatBoundaryService = Depends(get_admin_service),
) -> list[ConversationSummaryResponse]:
    """
    استرجاع قائمة بجميع محادثات المستخدم.

    الخدمة تعيد البيانات متوافقة مع Schema مباشرة.
    """
    results = await service.list_user_conversations(actor)
    return [ConversationSummaryResponse.model_validate(r) for r in results]


@router.get(
    "/api/conversations/{conversation_id}",
    summary="تفاصيل المحادثة (Conversation Details)",
    response_model=ConversationDetailsResponse,
)
async def get_conversation(
    conversation_id: int,
    actor: User = Depends(get_actor_user),
    service: AdminChatBoundaryService = Depends(get_admin_service),
) -> ConversationDetailsResponse:
    """
    استرجاع الرسائل والتفاصيل لمحادثة محددة.
    """
    data = await service.get_conversation_details(actor, conversation_id)
    return ConversationDetailsResponse.model_validate(data)
