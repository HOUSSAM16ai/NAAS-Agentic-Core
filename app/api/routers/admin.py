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
"""

import asyncio
import contextlib
import inspect
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.api.routers.ws_auth import extract_websocket_auth
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
from app.services.auth.token_decoder import decode_user_id
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


def _is_text_event(event: dict[str, object]) -> bool:
    """يتحقق من أن الحدث نصي ومسموح بتجميعه داخل مخزن النص النهائي."""
    return str(event.get("type", "")) in TEXT_EVENT_TYPES


def _ws_is_connected(websocket: WebSocket) -> bool:
    """يتحقق من أن WebSocket لا يزال في حالة CONNECTED قبل أي send_json.

    D-WS-FLAP-001: يمنع RuntimeError عند محاولة الإرسال على socket مغلق،
    وهو السبب الجذري لنمط الـ flapping (يعمل → يتعطل → يعود).
    """
    return websocket.client_state == WebSocketState.CONNECTED


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
    overlap_index: int | None = None
    max_start = len(client_context) - len(persisted_tail)
    for start in range(max_start, -1, -1):
        window = client_context[start : start + len(persisted_tail)]
        if window == persisted_tail:
            overlap_index = start + len(persisted_tail)
            break

    if overlap_index is None:
        return persisted_history

    safe_client_tail = client_context[overlap_index:][-12:]
    merged_history = list(persisted_history)
    for message in safe_client_tail:
        if message not in merged_history:
            merged_history.append(message)
    return merged_history[-80:]


async def _emit_terminal_frames(
    *,
    websocket: WebSocket,
    pending_terminal_event: dict[str, object] | None,
    assistant_message_persisted: bool,
    complete_ai_response: str,
    stream_error: HTTPException | Exception | None,
    local_conversation_id: int | None,
    stream_request_id: str,
) -> None:
    """
    يضمن إرسال إطار نهائي واحد فقط لكل دور (assistant_final أو error)
    وإطار 'persisted' فقط بعد حفظ فعلي. لا يُسمح بالفشل الصامت
    الذي يبقي واجهة المستخدم في حالة تحميل أبدية (ISS-016/ISS-017).
    """
    if assistant_message_persisted:
        if pending_terminal_event is not None:
            await websocket.send_json(pending_terminal_event)
        else:
            await websocket.send_json(
                _bind_stream_metadata(
                    normalize_streaming_event(
                        {"type": "assistant_final", "payload": {"content": ""}}
                    ),
                    local_conversation_id,
                    stream_request_id,
                )
            )
        await websocket.send_json(
            _bind_stream_metadata(
                normalize_streaming_event({"type": "persisted"}),
                local_conversation_id,
                stream_request_id,
            )
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

    await websocket.send_json(
        _bind_stream_metadata(
            normalize_streaming_event(
                {
                    "type": "error",
                    "payload": {"details": details, "status_code": status_code},
                }
            ),
            local_conversation_id,
            stream_request_id,
        )
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

    يوفر هذا التابع طبقة تجريد تُمكِّن من تجاوز التحقق في الاختبارات عبر
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
    """
    token, selected_protocol = extract_websocket_auth(websocket)
    if not token:
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

    try:
        user_id = decode_user_id(token, get_settings().SECRET_KEY)
    except HTTPException:
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

    async with async_session_factory() as db:
        # D-WS-KICK-001 (ISS-097): الـ token فُكَّ بنجاح. فشل جلب المستخدم هنا
        # خلل خادم *عابر* لا فشل مصادقة — أغلق بـ 1013 القابل لإعادة المحاولة،
        # لا 4401 (الذي تُترجمه الواجهة إلى تسجيل خروج).
        try:
            actor = await db.get(User, user_id)
        except Exception as lookup_exc:
            logger.warning(
                "admin_chat.ws_user_lookup_transient: %s (closing 1013, not 4401)",
                lookup_exc,
            )
            await websocket.accept(subprotocol=selected_protocol)
            with contextlib.suppress(Exception):
                await websocket.send_json(
                    normalize_streaming_event(
                        {
                            "type": "error",
                            "payload": {
                                "details": "Service temporarily unavailable. Reconnecting.",
                                "code": "WS_BACKEND_TRANSIENT",
                                "status_code": 1013,
                            },
                        }
                    )
                )
            await websocket.close(code=1013)
            return
        if actor is None or not actor.is_active:
            await websocket.accept(subprotocol=selected_protocol)
            await websocket.send_json(
                normalize_streaming_event(
                    {
                        "type": "error",
                        "payload": {
                            "details": "User account not found or inactive.",
                            "code": "WS_AUTH_USER_INACTIVE",
                            "status_code": 4401,
                        },
                    }
                )
            )
            await websocket.close(code=4401)
            return

        # Expunge the actor so we can use it after the session is closed
        db.expunge(actor)

    await websocket.accept(subprotocol=selected_protocol)

    if not actor.is_admin:
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

    # D-WS-FLAP-003 (2026-05-26): primer event — يُرسَل فور الـ accept لإجبار
    # كل الـ proxies على المسار (server.js, Codespaces edge, mobile carrier-NAT)
    # على الاحتفاظ بـ session نشط بدلاً من idle-timeout سريع.
    try:
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
        logger.debug("admin_chat.primer_failed: %s", exc)

    try:
        while True:
            payload = await websocket.receive_json()

            # D-WS-FLAP-002 (ISS-WS-FLAP-002): heartbeat موحَّد كـ Skill.
            # ping/heartbeat/noop يُعالَجون هنا قبل اعتبار الحمولة سؤالاً —
            # بدون هذا الفحص يُعاد للعميل خطأ «Question is required» بدل pong
            # → timeout 10s → close(1001) → flapping cycle.
            if await handle_control_message(websocket, payload):
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
            local_conversation_id: int | None = None
            history_messages: list[dict[str, str]] = []

            turn_span = open_ws_turn(
                user_id=actor.id,
                conversation_id=None,
                is_admin=True,
                question=question,
                request_id=stream_request_id,
            )

            try:
                async with async_session_factory() as db:
                    persistence_service = AdminChatBoundaryService(db)
                    local_conversation = await persistence_service.get_or_create_conversation(
                        actor,
                        question,
                        original_conversation_id,
                    )
                    local_conversation_id = local_conversation.id
                    turn_span.set_conversation_id(local_conversation_id)
                    await persistence_service.save_message(
                        local_conversation_id,
                        MessageRole.USER,
                        question,
                    )
                    history_messages = await persistence_service.get_chat_history(
                        local_conversation_id,
                        limit=50,
                    )
                    history_messages = _merge_history_with_client_context(
                        history_messages,
                        client_context_messages,
                    )
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
                    )
                )
                turn_span.set_terminal("error")
                close_ws_turn(turn_span, status="ERROR")
                continue

            complete_ai_response = ""
            assistant_message_persisted = False
            orchestrator_persisted = False
            pending_terminal_event: dict[str, object] | None = None
            stream_task: asyncio.Task[None] | None = None
            stream_error: HTTPException | Exception | None = None

            try:

                async def stream_and_forward(
                    q=question,
                    lc_id=local_conversation_id,
                    meta=metadata,
                    history=history_messages,
                    request_id=stream_request_id,
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
                            "chat_scope": "admin",
                            "metadata": meta,
                            "compatibility_facade": True,
                        },
                    ):
                        # D-WS-FLAP-001: abort stream if client disconnected mid-turn.
                        # Without this check, send_json raises RuntimeError which
                        # escapes the task and corrupts the outer finally block state.
                        if not _ws_is_connected(websocket):
                            logger.info(
                                "admin_chat.stream_aborted: client disconnected mid-stream "
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
                            await websocket.send_json(
                                _bind_stream_metadata(normalized_event, lc_id, request_id)
                            )

                        if _is_text_event(normalized_event) and isinstance(
                            normalized_event.get("payload"), dict
                        ):
                            chunk_text = normalized_event["payload"].get("content")
                            if isinstance(chunk_text, str) and chunk_text:
                                complete_ai_response += chunk_text

                stream_task = asyncio.create_task(stream_and_forward())
                await stream_task
            except HTTPException as http_exc:
                stream_error = http_exc
            except Exception as exc:
                stream_error = exc
                if not isinstance(exc, WebSocketDisconnect):
                    await websocket.send_json(
                        normalize_streaming_event(
                            {
                                "type": "error",
                                "payload": {"details": str(exc), "status_code": 500},
                            }
                        )
                    )
            finally:
                if stream_task is not None and not stream_task.done():
                    stream_task.cancel()
                    try:
                        await stream_task
                    except asyncio.CancelledError:
                        logger.info("Cancelled admin stream task after disconnect/finalization")
                # ── Persistence decision (single-writer coordination) ──
                # Monolith owns the message. If Orchestrator already persisted
                # (signaled via persisted=True on terminal event), skip local write;
                # otherwise fail-safe write. Absence of signal is treated as failure.
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
                        for _attempt in range(2):
                            try:
                                async with async_session_factory() as db:
                                    persistence_service = AdminChatBoundaryService(db)
                                    await persistence_service.save_message(
                                        conversation_id=local_conversation_id,
                                        role=MessageRole.ASSISTANT,
                                        content=complete_ai_response.replace("\x00", ""),
                                    )
                                    assistant_message_persisted = True
                                    logger.info(
                                        "[DATA_LOSS_PREVENTED] Fallback persistence succeeded."
                                    )
                                break
                            except Exception as persistence_exc:
                                logger.error(
                                    (
                                        "Failed to persist admin assistant message locally "
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
                        pending_terminal_event=pending_terminal_event,
                        assistant_message_persisted=assistant_message_persisted,
                        complete_ai_response=complete_ai_response,
                        stream_error=stream_error,
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
