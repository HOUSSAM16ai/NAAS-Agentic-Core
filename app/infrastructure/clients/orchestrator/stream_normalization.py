"""Stream-event normalization mixin (D-164 Slice 1 — extracted verbatim from the God-file).

Single responsibility: turn raw orchestrator/fallback stream events into the safe, typed
envelope the WS routers forward to the browser — control events pass through, unknown types
are dropped (`noop`), Generative-UI payloads are validated against the strict contract, and
the orchestrator `persisted` signal is preserved for write coordination (D-006). Also owns
the user-safe error frame and the structured-event recovery guard.

Mixed into `OrchestratorClient` via inheritance; `self._sanitize_text_for_user` and the rest
resolve through the MRO — behaviour is byte-identical to the pre-extraction God-file.
"""

from __future__ import annotations

import json
import logging
from ast import literal_eval

from shared.chat_protocol.chat_events import ChatEventEnvelope, ChatEventPayload, ChatEventType

logger = logging.getLogger("orchestrator-client")


class StreamNormalizationMixin:
    """Normalize stream events + emit user-safe error/recovery frames (D-164)."""

    # ISS-STREAM-001: أنواع الأحداث التي تُمرَّر مباشرة بدون تحويل إلى assistant_delta.
    # أي نوع غير مدرج هنا ولا في _TEXT_EVENT_TYPES يُتجاهل (لا يُرسل للواجهة).
    _PASSTHROUGH_EVENT_TYPES: frozenset[str] = frozenset(
        {
            "conversation_init",
            "persisted",
            "complete",
            "phase_start",
            "phase_completed",
            "RUN_STARTED",
            "context_missing",
            # Generative UI — يُمرَّر للواجهة لتصيير مكوّن React تفاعلي.
            "ui_component",
        }
    )
    _TEXT_EVENT_TYPES: frozenset[str] = frozenset(
        {"assistant_delta", "assistant_final", "assistant_error", "status"}
    )

    def _normalize_stream_event(self, raw_event: object) -> dict[str, object]:
        """
        يوحد شكل أحداث التدفق ويضمن عدم تسريب تفاصيل داخلية.

        ISS-STREAM-001: الإصلاح الجراحي — الأحداث غير النصية (phase_start,
        RUN_STARTED, إلخ) تُمرَّر كما هي بدل تحويلها إلى assistant_delta
        مما كان يُسبب ظهور نصوص غريبة في الواجهة.
        """
        if not isinstance(raw_event, dict):
            # نص خام → delta
            return {
                "type": ChatEventType.ASSISTANT_DELTA.value,
                "payload": {"content": self._sanitize_text_for_user(str(raw_event))},
            }

        raw_type = str(raw_event.get("type", ChatEventType.ASSISTANT_DELTA.value))

        # Generative UI: نتحقق من الحمولة عبر العقد الصارم. أي مكوّن مجهول أو
        # حمولة مشوَّهة → noop (تُسقَط) بدل تمرير بيانات غير موثوقة للواجهة.
        if raw_type == "ui_component":
            return self._normalize_ui_component_event(raw_event)

        # أحداث التحكم تُمرَّر مباشرة بدون تحويل
        if raw_type in self._PASSTHROUGH_EVENT_TYPES:
            result = dict(raw_event)
            if "persisted" in raw_event:
                result["persisted"] = bool(raw_event["persisted"])
            return result

        # أحداث غير معروفة → تُتجاهل (لا تُرسل للواجهة كـ delta)
        if raw_type not in self._TEXT_EVENT_TYPES:
            return {"type": "noop", "payload": {}}

        payload = raw_event.get("payload")
        if not isinstance(payload, dict):
            payload = {"content": str(raw_event)}

        safe_payload = {
            "content": self._sanitize_text_for_user(str(payload.get("content", "")))
            if payload.get("content") is not None
            else None,
            "details": self._sanitize_text_for_user(str(payload.get("details", "")))
            if payload.get("details") is not None
            else None,
            "status_code": payload.get("status_code")
            if isinstance(payload.get("status_code"), int)
            else None,
            "request_id": str(payload.get("request_id"))
            if payload.get("request_id") is not None
            else None,
            "retry_hint": str(payload.get("retry_hint"))
            if payload.get("retry_hint") is not None
            else None,
        }

        event_type_map = {
            "assistant_delta": ChatEventType.ASSISTANT_DELTA,
            "assistant_final": ChatEventType.ASSISTANT_FINAL,
            "assistant_error": ChatEventType.ASSISTANT_ERROR,
            "status": ChatEventType.STATUS,
        }
        envelope = ChatEventEnvelope(
            type=event_type_map.get(raw_type, ChatEventType.ASSISTANT_DELTA),
            payload=ChatEventPayload(**safe_payload),
        )
        result = envelope.model_dump(exclude_none=True)
        # Preserve orchestrator persistence signal for conditional-write coordination
        if "persisted" in raw_event:
            result["persisted"] = bool(raw_event["persisted"])
        return result

    def _normalize_ui_component_event(self, raw_event: dict) -> dict[str, object]:
        """يتحقق من حمولة مكوّن UI توليدي ويعيد مغلفاً نظيفاً أو noop عند الفشل.

        أي مكوّن مجهول (خارج القائمة البيضاء) أو حمولة مشوَّهة أو ضخمة → noop
        (تُسقَط) — لا نمرر للواجهة بيانات غير موثوقة. هذا خط الدفاع الأول قبل
        React Error Boundary.
        """
        from pydantic import ValidationError

        from app.contracts.streaming import UIComponentPayload

        payload = raw_event.get("payload")
        if not isinstance(payload, dict):
            return {"type": "noop", "payload": {}}
        try:
            validated = UIComponentPayload.model_validate(payload)
        except ValidationError:
            logger.warning("ui_component_event_rejected", exc_info=True)
            return {"type": "noop", "payload": {}}
        # حماية ضد الحمولات الضخمة (cap التسلسل عند 16KB)
        try:
            if len(json.dumps(validated.props, default=str)) > 16000:
                logger.warning("ui_component_props_too_large")
                return {"type": "noop", "payload": {}}
        except (TypeError, ValueError):
            return {"type": "noop", "payload": {}}
        return {
            "type": "ui_component",
            "payload": {
                "component": validated.component,
                "props": validated.props,
                "fallback_text": self._sanitize_text_for_user(validated.fallback_text),
            },
        }

    @staticmethod
    def _sanitize_error_for_user(*, request_id: str) -> dict[str, object]:
        """ينتج رسالة خطأ آمنة للمستخدم بدون أي تفاصيل طوبولوجيا أو تشخيص داخلي."""
        return {
            "type": "assistant_error",
            "payload": {
                "content": "تعذر إتمام طلبك حالياً بسبب ضغط أو عطل مؤقت في خدمة المحادثة. حاول مرة أخرى بعد لحظات.",
                "request_id": request_id,
                "retry_hint": "يمكنك إعادة المحاولة بعد دقيقة.",
            },
        }

    @staticmethod
    def _recover_structured_event(raw_line: str) -> dict[str, object] | None:
        """يحاول استعادة حدث هيكلي من تمثيل dict نصي لمنع تسريب البنية إلى الدردشة."""
        candidate = raw_line.strip()
        if not (candidate.startswith("{") and candidate.endswith("}")):
            return None
        try:
            parsed = literal_eval(candidate)
        except (SyntaxError, ValueError):
            return None
        if not isinstance(parsed, dict):
            return None
        if not isinstance(parsed.get("type"), str):
            return None
        payload = parsed.get("payload")
        if payload is not None and not isinstance(payload, dict):
            return None
        return parsed
