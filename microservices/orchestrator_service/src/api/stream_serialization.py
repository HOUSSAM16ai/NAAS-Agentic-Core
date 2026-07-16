"""تسلسل البثّ — NDJSON frames + استخراج النص البشري (ISS-056) + telemetry line.

مستخرَجة حرفياً من ``routes.py`` (D-168 Slice A2). تعتمد على ``chat_types`` فقط
من الأشقاء — لا تستورد من ``routes`` أبداً (طبقات باتجاه واحد).
"""

from __future__ import annotations

import json

import anyio

from .chat_types import StreamFrame


async def _append_telemetry_line(line: str) -> None:
    """يكتب سطر تتبع حرج إلى ملف أدلة قابل للفحص خارج مخرجات الطرفية."""
    import os

    import anyio

    def write_sync():
        path = os.path.join(os.getenv("STATE_DIR", "/app"), "telemetry_evidence.txt")
        with open(path, "a", encoding="utf-8") as telemetry_file:
            telemetry_file.write(f"{line}\n")

    await anyio.to_thread.run_sync(write_sync)


async def _serialize_json_async(payload: object) -> str:
    """يُسلسل الحمولة إلى JSON داخل خيط منفصل لحماية حلقة الأحداث من الحجب."""
    return await anyio.to_thread.run_sync(lambda p: json.dumps(p, ensure_ascii=False), payload)


# ─────────────────────────────────────────────────────────────────────────────
# ISS-056 (D-049 — JSON Envelope Anti-Leak Doctrine):
# SynthesizerNode في graph/search.py يُرجِع `final_response` كـ dict بمظروف:
#   {"المصدر": ..., "مستوى_الثقة": ..., "التمرين": <نص حقيقي للطالب>,
#    "السنة": ..., "الشعبة": ..., "المادة": ..., "رقم_التمرين": ...}
#
# قبل الإصلاح: `_serialize_json_async(final_resp)` كان يُسلسل المظروف كاملاً كـ
# JSON ويرسله للطالب → كارثة تظهر فيها {"المصدر":"معرفة مادة"... } مكشوفة.
#
# بعد الإصلاح: نستخرج الحقل البشري (`التمرين`/`الإجابة`/`response`) فقط.
# هذه الدالة **يجب** أن تُستخدم في كل مكان يُحوَّل فيه `final_response` إلى نص
# للمستخدم النهائي. لا تُسلسل dict خام كـ JSON إلى assistant_delta/final أبداً.
# ─────────────────────────────────────────────────────────────────────────────
_HUMAN_RESPONSE_FIELDS: tuple[str, ...] = (
    "التمرين",  # SynthesizerNode envelope
    "الإجابة",  # AdminAgentNode / RenderAnswerNode envelope
    "response",
    "answer",
    "content",
    "text",
    "final_response",  # nested fallback
)


def _extract_human_readable_response(final_resp: object) -> str:
    """يستخرج النص البشري من `final_response` بدون تسريب مظروف JSON.

    يحل ISS-056 — JSON Envelope Leak Catastrophe.

    قواعد دائمة:
    - dict مع حقل بشري معروف (`التمرين`/`الإجابة`/…) → النص فقط
    - dict مع حقل خطأ (`خطأ`) → رسالة خطأ نظيفة بالعربية
    - dict بدون حقل بشري → "لا توجد تفاصيل متاحة." (لا dump للمظروف)
    - str → التنظيف فقط
    - None → الـ fallback الافتراضي
    """
    if isinstance(final_resp, dict):
        # حالة الخطأ من RenderAnswerNode — رسالة نظيفة، لا dump
        error_msg = final_resp.get("خطأ")
        if isinstance(error_msg, str) and error_msg.strip():
            action = str(final_resp.get("الإجراء", "")).strip()
            tail = f"\n\n{action}" if action else ""
            return f"حدث خطأ أثناء معالجة طلبك: {error_msg.strip()}{tail}"

        for key in _HUMAN_RESPONSE_FIELDS:
            value = final_resp.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            # حالة nested: قد يكون response_json داخل response_json
            if isinstance(value, dict):
                nested = _extract_human_readable_response(value)
                if nested and nested != "لا توجد تفاصيل متاحة.":
                    return nested

        # dict بدون حقل بشري معروف — لا تكشف المظروف الداخلي للطالب
        return "لا توجد تفاصيل متاحة."

    if final_resp is None:
        return "لا توجد تفاصيل متاحة."

    text = str(final_resp).strip()
    return text or "لا توجد تفاصيل متاحة."


async def _serialize_stream_frame(payload: object) -> str:
    """يبني NDJSON صارمًا لضمان عدم تسريب dict خام إلى عميل البث النصي."""
    return _serialize_stream_frame_sync(payload)


def _serialize_stream_frame_sync(payload: object) -> str:
    """سريع، متزامن، آمن لـ event loop."""
    if isinstance(payload, dict):
        frame = StreamFrame.model_validate(payload).model_dump()
    else:
        frame = StreamFrame(type="assistant_delta", payload={"content": str(payload)}).model_dump()
    return json.dumps(frame, ensure_ascii=False) + "\n"
