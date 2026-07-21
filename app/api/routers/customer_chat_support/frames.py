"""Client-context merge + terminal frames — sliced verbatim from customer_chat.py (D-173 Stage 2b).

قواعد D-168: هذه الوحدة لا تستورد `customer_chat` أبداً؛ الـ router يعيد
استيراد الرموز (re-export) فيبقى monkeypatch على `customer_chat.<name>`
فعّالاً لكل نداء يصدر من الـ handler (قانون late-binding).
"""

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

from fastapi import HTTPException, WebSocket

from app.core.di import get_logger
from shared.chat_protocol.event_protocol import normalize_streaming_event

logger = get_logger(__name__)


from app.api.routers.customer_chat_support.transport import _locked_send_json


def _bind_local_conversation_id(
    event: dict[str, object], conversation_id: int | None
) -> dict[str, object]:
    """يربط معرف المحادثة المحلي بجميع أحداث البث لمنع اختلاط السياق في الواجهة."""
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
    """يربط بيانات التتبع القياسية بكل حدث بث لعزل السياق بين الطلبات."""
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
    """استخراج سياق المحادثة المرسل من الواجهة بشكل آمن ومحدود الحجم."""
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
    دمج تاريخ قاعدة البيانات مع سياق العميل مع منع تسريب رسائل محادثات أخرى.

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


def _try_build_math_ui_component(response_text: str) -> dict | None:
    """
    مُعطَّل عمداً (ISS-108 / D-097 — قرار المستخدم: «إيقاف التقطيع + بطاقات محقَّقة فقط»).

    كان يُمرِّر **نص الإجابة الحر** إلى ``math_pipeline._build_ui_component`` الذي
    يُقطّع النثر بـ regex فضفاضة فيُنتج «خطوات» عشوائية بلا معنى (مؤكَّد حياً على
    بيانات الإنتاج msg 3411: «بالعربي»، «أتمنى أن تكون الفكرة الآن واضحة») ويُصنّف
    شرح الاحتمالات كـ«معادلات». بطاقة ``math_explanation_card`` صالحة فقط لمخرَج
    محتوم منظَّم — لا لنثر LLM حر. البطاقات البصرية المحقَّقة (probability_tree /
    combinations_visualizer / full_exercise_story) تأتي من المسار المنفصل
    ``orchestrator_client._build_calculated_ui`` وتبقى عاملة.

    القاعدة الدائمة (D-097): ممنوع تقطيع نثر LLM حر إلى بطاقة خطوات. أي بطاقة
    Generative UI يجب أن تُبنى من بيانات محتومة مُتحقَّقة، لا من نص مُولَّد.
    """
    return None


async def _emit_terminal_frames(
    *,
    websocket: WebSocket,
    send_lock: asyncio.Lock,
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

    D-096: يستخدم send_lock لمنع التزامن مع BKT task و stream_and_forward.
    """
    if assistant_message_persisted:
        # بناء ui_component من النص المكتمل — لا يكسر المسار عند الفشل
        ui_component = _try_build_math_ui_component(complete_ai_response)

        if pending_terminal_event is not None:
            # حقن ui_component في الـ payload الموجود
            if ui_component and isinstance(pending_terminal_event.get("payload"), dict):
                pending_terminal_event["payload"]["ui_component"] = ui_component
            await _locked_send_json(websocket, send_lock, pending_terminal_event)
        else:
            payload: dict = {"content": ""}
            if ui_component:
                payload["ui_component"] = ui_component
            await _locked_send_json(
                websocket,
                send_lock,
                _bind_stream_metadata(
                    normalize_streaming_event({"type": "assistant_final", "payload": payload}),
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
