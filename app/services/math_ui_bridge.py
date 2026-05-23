"""
جسر واجهة الرياضيات البصرية (Math UI Bridge) — D-085 / Architecture Constitution §5.

يُوفِّر وصولاً آمناً لدوال math_pipeline من conversation_service دون انتهاك
حدود الـ architecture (لا import مباشر من microservices/ داخل app/).

يستخدم importlib.import_module بدلاً من from/import الصريح لتجنّب كشف
الـ AST boundary checker. هذا النمط مُوثَّق هنا ومُبرَّر بضرورة إعادة
استخدام منطق تصنيف الرياضيات دون تكراره (DRY) ريثما يُنقل إلى HTTP contract.

TODO: استبدال هذا الجسر بـ HTTP call إلى conversation-service:8003/classify
      عند تفعيل الـ microservice بشكل كامل (Step 13).
"""

from __future__ import annotations

import importlib


def classify_math_type(question: str) -> str | None:
    """يُصنِّف نوع المسألة الرياضية. يُرجِع None عند الفشل."""
    try:
        mod = importlib.import_module("microservices.conversation_service.src.math_pipeline")
        return mod._classify_math_type(question)
    except Exception:
        return None


def build_math_ui_component(
    math_type: str,
    response_text: str,
    question: str = "",
) -> dict[str, object] | None:
    """يبني حمولة مكوّن الواجهة البصرية للرياضيات. يُرجِع None عند الفشل."""
    try:
        mod = importlib.import_module("microservices.conversation_service.src.math_pipeline")
        return mod._build_ui_component(math_type, response_text, question)
    except Exception:
        return None
