"""الهوية والوصول — session/thread/conversation resolution + JWT + admin access.

مستخرَجة حرفياً من ``routes.py`` (D-168 Slice A2). تعتمد على ``chat_types`` فقط
من الأشقاء — لا تستورد من ``routes`` أبداً (طبقات باتجاه واحد).
"""

from __future__ import annotations

import logging
import os
import re

import jwt
from fastapi import Header, HTTPException

from microservices.orchestrator_service.src.core.config import get_settings
from microservices.orchestrator_service.src.core.security import extract_bearer_token

from .chat_types import ChatRunContext

logger = logging.getLogger(__name__)


def _resolve_session_id_from_incoming(incoming: dict[str, object]) -> str | None:
    """يستخرج session_id بشكل صريح من الحمولة أو من context لدعم تشخيص ثبات الهوية."""
    direct_session = incoming.get("session_id")
    if isinstance(direct_session, str) and direct_session.strip():
        return direct_session.strip()

    context_payload = incoming.get("context")
    if isinstance(context_payload, dict):
        context_session = context_payload.get("session_id")
        if isinstance(context_session, str) and context_session.strip():
            return context_session.strip()
    return None


def _emit_identity_diagnostic_log(
    *,
    route_name: str,
    conversation_id: int | str,
    thread_id: str | None,
    session_id: str | None,
) -> None:
    """يسجل بصمة الهوية لكل رسالة مع معلومات الحاوية لتأكيد تغيّر المسار أو ثباته."""
    orchestrator_instance_id = os.getenv("ORCHESTRATOR_INSTANCE_ID", "").strip() or "unset"
    hostname = os.getenv("HOSTNAME", "").strip() or "unknown"
    container_id = hostname
    logger.info(
        "[IDENTITY_DIAGNOSTIC] route=%s conversation_id=%s thread_id=%s session_id=%s "
        "orchestrator_instance_id=%s hostname=%s container_id=%s",
        route_name,
        conversation_id,
        thread_id or "missing",
        session_id or "missing",
        orchestrator_instance_id,
        hostname,
        container_id,
    )


def _is_admin_payload(payload: dict[str, object]) -> bool:
    """يتحقق من صلاحيات الإدارة داخل حمولة JWT وفق مبدأ أقل صلاحية وfail-closed."""
    role = str(payload.get("role", "")).lower().strip()
    scope_text = str(payload.get("scope", "")).lower()
    has_admin_role = role in {"admin", "super_admin", "superadmin"}
    has_admin_flag = payload.get("is_admin") is True
    has_admin_scope = "admin" in scope_text and "tool" in scope_text
    return has_admin_role or has_admin_flag or has_admin_scope


def _coerce_admin_state(payload: dict[str, object] | None = None) -> dict[str, object]:
    """يبني حالة إدارة ضيقة ومتوافقة لعقدة التحكم دون توسيع الواجهة العامة."""

    safe_payload = payload or {}
    role = str(safe_payload.get("role", "")).strip().lower()
    scope = str(safe_payload.get("scope", "")).strip().lower()
    is_admin = _is_admin_payload(safe_payload)
    return {
        "is_admin": is_admin,
        "user_role": role,
        "scope": scope,
    }


def _merge_admin_inputs(
    base_inputs: dict[str, object], admin_payload: dict[str, object] | None
) -> dict[str, object]:
    """يحقن غلاف الإدارة الموحد فقط عند الحاجة، مع إبقاء المسارات الأخرى دون تغيير."""

    if admin_payload is None:
        return base_inputs
    return {**base_inputs, **_coerce_admin_state(admin_payload)}


async def require_internal_admin_access(
    authorization: str | None = Header(default=None),
    x_internal_admin_key: str | None = Header(default=None),
) -> int:
    """يفرض مصادقة وتفويضاً مغلقين لمسارات الأدوات عبر مفتاح داخلي أو JWT إداري صريح."""
    settings = get_settings()

    if (
        x_internal_admin_key
        and settings.ADMIN_TOOL_API_KEY
        and x_internal_admin_key == settings.ADMIN_TOOL_API_KEY
    ):
        return 0

    token = extract_bearer_token(authorization)
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc

    if not _is_admin_payload(payload):
        raise HTTPException(status_code=403, detail="forbidden")

    user_id = int(payload.get("sub", payload.get("user_id", 0)) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=403, detail="forbidden")
    return user_id


def _safe_assistant_error(request_id: str) -> str:
    """يبني رسالة خطأ آمنة للمستخدم دون أي تسريب تشخيصي داخلي."""
    return f"تعذر معالجة طلب الدردشة حالياً. رقم المتابعة: {request_id}"


def _safe_conversation_id(raw_value: object) -> int | None:
    """يحوّل conversation_id بشكل آمن لدعم int أو string رقمي مع تتبع تشخيصي واضح."""
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return raw_value
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if not stripped:
            return None
        try:
            parsed = int(stripped)
            logger.warning(
                "[CONV_ID_TYPE] Received conversation_id as string '%s' and converted to int=%s",
                raw_value,
                parsed,
            )
            return parsed
        except ValueError:
            logger.error(
                "[CONV_ID_TYPE] Invalid numeric conversion for conversation_id='%s'; using None",
                raw_value,
            )
            return None

    logger.error(
        "[CONV_ID_TYPE] Unexpected conversation_id type=%s; using None",
        type(raw_value).__name__,
    )
    return None


def _resolve_effective_conversation_id(
    *, incoming_value: object, sticky_value: int | None
) -> int | None:
    """يحدّد conversation_id النهائي مع أولوية للطلب الحالي ثم ذاكرة الاتصال."""
    parsed = _safe_conversation_id(incoming_value)
    if parsed is not None:
        return parsed
    return sticky_value


def _safe_thread_id(raw_value: object) -> str | None:
    """يطبّع thread_id لدعم int/str مع رفض القيم الفارغة."""
    if raw_value is None:
        return None
    if isinstance(raw_value, int):
        return str(raw_value)
    if isinstance(raw_value, str):
        normalized = raw_value.strip()
        if normalized:
            return normalized
    return None


def _resolve_thread_id(context: ChatRunContext, fallback_conversation_id: int | str) -> str:
    """يستخرج thread_id ثابتًا من السياق مع عزل المستخدم."""
    explicit = _safe_thread_id(context.get("thread_id"))
    if explicit:
        return explicit

    conv_id = context.get("conversation_id", fallback_conversation_id)
    user_id = context.get("user_id")
    if user_id is None:
        raise ValueError(
            f"[THREAD_RESOLUTION] user_id required for safe thread binding. conv_id={conv_id!r}"
        )
    return f"u{user_id}:c{conv_id}"


def _build_conversation_thread_id(user_id: int, conversation_id: int | str) -> str:
    """يبني معرف خيط حتمي خاص بالمحادثة لضمان ثبات checkpointer بين الأدوار."""
    return f"u{user_id}:c{conversation_id}"


def _conversation_id_from_scoped_thread(thread_id: str, user_id: int) -> int | None:
    """يستخرج conversation_id من thread_id مقيّد بالمستخدم: u<uid>:c<cid>."""
    normalized = thread_id.strip()
    match = re.fullmatch(r"u(\d+):c(\d+)", normalized)
    if not match:
        return None
    scoped_user_id = int(match.group(1))
    if scoped_user_id != user_id:
        return None
    return int(match.group(2))


def _decode_auth_payload_or_401(authorization: str | None) -> tuple[int, dict[str, object]]:
    """يفك JWT من ترويسة Authorization ويعيد user_id والحمولة مع فشل مغلق."""
    token = extract_bearer_token(authorization)
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    user_id = int(payload.get("sub", payload.get("user_id", 0)) or 0)
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid user")
    return user_id, payload
