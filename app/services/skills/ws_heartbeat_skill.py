"""
WebSocketHeartbeatSkill — معالج بروتوكول heartbeat لطبقة WebSocket.

## المشكلة (ISS-WS-FLAP-002)

كل WS router في النظام (`customer_chat.py`, `admin.py`, `conversation_service.main`)
يفترض أن كل رسالة واردة هي «سؤال». الواجهة ترسل `{type: "ping"}` كل 25 ثانية كـ
application-level heartbeat، ثم تنتظر `{type: "pong"}` لمدة 10 ثوانٍ. الخادم
لا يرد بـ pong → الواجهة تُغلق الاتصال (code 1001) → reconnect → flapping.

هذه الـ Skill تُوفِّر معالج موحَّداً لكل WS endpoints:

```python
from app.services.skills.ws_heartbeat_skill import handle_control_message

# داخل WS message loop:
payload = await websocket.receive_json()
if await handle_control_message(websocket, payload):
    continue  # كانت رسالة تحكم (ping/heartbeat) — لا تُعالجها كسؤال
# ... تابع المعالجة العادية
```

## أنواع الرسائل المُتعرَّف عليها

- `{"type": "ping"}` → يرد بـ `{"type": "pong", "ts": <iso-utc>}`
- `{"type": "heartbeat"}` → يرد بـ `{"type": "heartbeat_ack", "ts": <iso-utc>}`
- `{"type": "noop"}` → يبتلع الرسالة بصمت (لا رد)

أي نوع آخر → `False` → يتابع المتصل المعالجة العادية.

## ضمانات

- لا يفشل أبداً: أي خطأ في الإرسال يُسجَّل ويُرجع `True` (يُعالَج كرسالة تحكم).
- لا يكسر مسار البث: لا يتفاعل مع أي state للمحادثة.
- متوافق مع كل WebSocket frameworks: FastAPI/Starlette + websockets library.
- يحترم D-WS-004 unified WS architecture.

## القاعدة الذهبية (D-WS-FLAP-002)

> أي WS endpoint يجب أن يستدعي `handle_control_message` قبل معالجة الرسالة
> كسؤال. هذا قانون معماري لا يُكسَر بدون ADR.

D-WS-FLAP-002 (2026-05-26): إنشاء Skill رسمي لمعالجة WS heartbeat protocol.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Protocol

logger = logging.getLogger(__name__)


# ── Prometheus metrics — defensive import ─────────────────────────────────────
try:
    from prometheus_client import Counter

    _HEARTBEAT_INVOCATIONS = Counter(
        "cogniforge_skill_ws_heartbeat_invocations_total",
        "عدد استدعاءات معالج heartbeat",
        ["message_type", "result"],
    )
    _HEARTBEAT_SEND_ERRORS = Counter(
        "cogniforge_skill_ws_heartbeat_send_errors_total",
        "عدد أخطاء إرسال pong/ack (client disconnected during reply)",
        ["message_type"],
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False


def _record_invocation(message_type: str, result: str) -> None:
    if _METRICS_AVAILABLE:
        _HEARTBEAT_INVOCATIONS.labels(message_type=message_type, result=result).inc()


def _record_send_error(message_type: str) -> None:
    if _METRICS_AVAILABLE:
        _HEARTBEAT_SEND_ERRORS.labels(message_type=message_type).inc()


# ── أنواع رسائل التحكم ────────────────────────────────────────────────────────

# الأنواع التي تعمل كـ heartbeat application-level
_CONTROL_MESSAGE_TYPES = frozenset({"ping", "heartbeat", "noop"})

# الردود لكل نوع
_RESPONSE_MAP: dict[str, str | None] = {
    "ping": "pong",
    "heartbeat": "heartbeat_ack",
    # noop = تُبتلع بدون رد (لا flooding)
    "noop": None,
}


class WebSocketLike(Protocol):
    """عقد بنيوي: أي شيء يدعم async send_json يعمل."""

    async def send_json(self, data: Any) -> None: ...


# ── الواجهة العامة ────────────────────────────────────────────────────────────


def is_control_message(payload: Any) -> bool:
    """
    يتحقق ما إذا كانت الحمولة رسالة تحكم WS (ping/heartbeat/noop).

    Args:
        payload: ما تم استقباله من websocket.receive_json().

    Returns:
        True إذا كانت رسالة تحكم يجب التعامل معها بشكل خاص.
    """
    if not isinstance(payload, dict):
        return False
    msg_type = payload.get("type")
    if not isinstance(msg_type, str):
        return False
    return msg_type.lower() in _CONTROL_MESSAGE_TYPES


async def handle_control_message(
    websocket: WebSocketLike,
    payload: Any,
    send_lock: Any = None,
) -> bool:
    """
    يعالج رسالة WebSocket التحكم (ping/heartbeat/noop).

    إذا كانت الحمولة رسالة تحكم:
    - يرسل الرد المناسب (pong/heartbeat_ack)
    - يُسجِّل مقياس Prometheus
    - يُرجع True (= استهلكت الرسالة، لا تُعالج كسؤال)

    إذا لم تكن رسالة تحكم:
    - لا يفعل شيئاً
    - يُرجع False (= يجب معالجتها بشكل طبيعي)

    لا يرفع استثناء أبداً — أي فشل في الإرسال (client disconnected) يُسجَّل
    كـ DEBUG ويُرجع True (المتصل لا يحتاج لمعالجة الرسالة كسؤال على أي حال).

    Args:
        websocket: كائن WebSocket (FastAPI/Starlette).
        payload: ما تم استقباله من receive_json().

    Returns:
        True إذا تمت معالجتها كرسالة تحكم — تابع loop بـ `continue`.
        False إذا لم تكن رسالة تحكم — تابع المعالجة العادية.
    """
    if not is_control_message(payload):
        return False

    msg_type = payload.get("type", "").lower()
    response_type = _RESPONSE_MAP.get(msg_type)

    if response_type is None:
        # noop — ابتلاع صامت بدون رد
        _record_invocation(msg_type, "swallowed")
        return True

    # بناء الرد مع timestamp ISO-8601 UTC
    response: dict[str, Any] = {
        "type": response_type,
        "ts": datetime.now(UTC).isoformat(),
    }

    # احتفظ بـ correlation id لو أرسله العميل (مفيد لـ tracing مستقبلاً)
    if isinstance(payload, dict):
        corr_id = payload.get("id") or payload.get("request_id")
        if corr_id is not None:
            response["id"] = corr_id

    try:
        # D-096: استخدم send_lock إذا تم تمريره — يمنع التزامن مع stream/BKT
        if send_lock is not None:
            async with send_lock:
                await websocket.send_json(response)
        else:
            await websocket.send_json(response)
        _record_invocation(msg_type, "replied")
    except Exception as exc:
        # العميل ربما أغلق الاتصال بين receive و send — هذا طبيعي.
        # لا نُفشل المتصل: نُرجع True لأن الرسالة كانت تحكماً، ولن نحاول
        # معالجتها كسؤال (والـ socket المغلق سيُكتشَف في receive_json التالي).
        _record_send_error(msg_type)
        logger.debug(
            "ws_heartbeat.send_failed type=%s err=%s (client likely closed)",
            msg_type,
            exc,
        )

    return True


__all__ = [
    "handle_control_message",
    "is_control_message",
]
