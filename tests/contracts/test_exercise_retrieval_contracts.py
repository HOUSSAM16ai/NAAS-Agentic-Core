"""اختبارات عقود قدرة استرجاع التمارين لضمان السلوك المتوافق."""

from __future__ import annotations

import pytest

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    make_result,
)


def test_detect_exercise_retrieval_arabic() -> None:
    """يتعرف على الطلبات العربية الصريحة للتمارين."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question="أعطني تمرين احتمالات"))
    assert decision.recognized is True


def test_detect_exercise_retrieval_mixed_language() -> None:
    """يدعم الطلبات المختلطة عربي/إنجليزي."""
    decision = detect_exercise_retrieval(
        ExerciseRetrievalRequest(question="أريد probability exercise with steps")
    )
    assert decision.recognized is True


def test_make_result_handles_no_result() -> None:
    """يعطي فشلًا حتميًا عند غياب نتيجة الاسترجاع."""
    result = make_result(None)
    assert result.success is False
    assert result.message is None


def test_make_result_keeps_message_when_available() -> None:
    """يحافظ على رسالة الاسترجاع كما هي لضمان التوافق."""
    result = make_result("تم العثور على تمرين.")
    assert result.success is True
    assert result.message == "تم العثور على تمرين."


# ─────────────────────────────────────────────────────────────────────────────
# اختبارات regression — ISS-038
# كلمة "تمرين" في سياق الشرح كانت تُطلق استرجاع تمرين الاحتمالات بشكل ثابت.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("question", [
    "اشرح الجزء أ من هذا التمرين",
    "اشرح لي هذا التمرين",
    "كيف أحل هذا التمرين",
    "ساعدني في حل هذا التمرين",
    "ما هو مفهوم التمرين في الرياضيات",
    "ما هو الفرق بين التمرين والمسألة",
    "وضح لي الجزء الأول",
    "ما هي الاحتمالات",
    "اشرح درس الاحتمالات",
    "فسر لي هذا السؤال",
    "help me with this exercise",
    "explain part a",
    "what is probability",
])
def test_explanation_context_does_not_trigger_retrieval(question: str) -> None:
    """
    ISS-038 regression: سياق الشرح لا يُطلق الاسترجاع حتى لو ذُكر "تمرين".
    قبل الإصلاح، كانت هذه الأسئلة تجلب تمرين الاحتمالات بشكل ثابت.
    """
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is False, (
        f"سياق الشرح أطلق الاسترجاع خطأً: '{question}' — reason={decision.reason}"
    )


@pytest.mark.parametrize("question", [
    "أريد تمرين بكالوريا",
    "أعطني تمرين احتمالات",
    "التمرين الأول من الموضوع الأول",
    "تمرين بكالوريا 2024",
    "الموضوع الثاني رياضيات",
    "exercise 1",
    "exercise 2 probability",
    "ابحث عن تمرين احتمالات",
])
def test_explicit_retrieval_intent_triggers_retrieval(question: str) -> None:
    """طلبات الجلب الصريحة تُطلق الاسترجاع بشكل صحيح."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is True, (
        f"طلب جلب صريح لم يُطلق الاسترجاع: '{question}' — reason={decision.reason}"
    )
