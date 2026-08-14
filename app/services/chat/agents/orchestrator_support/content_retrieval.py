"""شريحة استرجاع المحتوى (D-253).

فُكِّكت من `OrchestratorAgent._handle_content_retrieval` (C(14))
إلى مراحل نقية: تصنيف النوع، القرار الصلاحي للحل، دلتات التسليم.
**صفر تغيير سلوكي**: كل النصوص والعتبات مطابقة حرفًا.
"""

from __future__ import annotations

# دلتات المحتوى الثابتة (نفس ترقيم السلالة الأصلية حرفًا).
CONTENT_FOUND_PREFIX = "✅ **تم العثور على:**"
CONTENT_SEPARATOR = "---\n\n"
CONTENT_TRAILER = "\n\n---\n\n"
NO_CONTENT_FOUND = "عذراً، تعذر تحميل نص المحتوى."
TRY_FIRST_ASK = "هل ترغب أن أقدّم الحل أو تفضّل المحاولة أولاً؟"
NO_CONTENT_FOUND_LOG = "No content found for query, falling back to smart tutor."

CONTENT_TYPE_EXERCISE = "exercise"
CONTENT_TYPE_LESSON = "lesson"


def classify_content_type(raw_type: str | None) -> str:
    """يوحّد نوع المحتوى إلى exercise/lesson (نفس قواعد الفرز الأصلية)."""
    if not raw_type:
        return CONTENT_TYPE_LESSON
    lowered = raw_type.lower()
    if CONTENT_TYPE_EXERCISE in lowered or "exam" in lowered or "quiz" in lowered:
        return CONTENT_TYPE_EXERCISE
    return CONTENT_TYPE_LESSON


def select_best_candidate(candidates: list[dict[str, object]] | None) -> dict[str, object] | None:
    """يختار المرشح الأفضل (منطق: Top 1) — منطق الاختيار الأصلي: أول مرشح."""
    if not candidates:
        return None
    return candidates[0]


def should_request_solution(
    writer_intent_value: object, writer_intent: object
) -> tuple[bool, bool]:
    """(include_solution, exclude_solution) من نية الكاتب — نفس الشروط الأصلية.

    ملاحظة: النية النهائية تُحسَب خارج الدالة؛ هنا نطبّق نفس قواعد التحويل.
    """
    include_solution = writer_intent in (
        writer_intent_value.SOLUTION_REQUEST,
        writer_intent_value.GRADING_REQUEST,
    )
    exclude_solution = writer_intent == writer_intent_value.QUESTION_ONLY_REQUEST
    return include_solution, exclude_solution
