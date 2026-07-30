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


@pytest.mark.parametrize(
    "question",
    [
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
    ],
)
def test_explanation_context_does_not_trigger_retrieval(question: str) -> None:
    """
    ISS-038 regression: سياق الشرح لا يُطلق الاسترجاع حتى لو ذُكر "تمرين".
    قبل الإصلاح، كانت هذه الأسئلة تجلب تمرين الاحتمالات بشكل ثابت.
    """
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is False, (
        f"سياق الشرح أطلق الاسترجاع خطأً: '{question}' — reason={decision.reason}"
    )


@pytest.mark.parametrize(
    "question",
    [
        "أريد تمرين بكالوريا",
        "أعطني تمرين احتمالات",
        "التمرين الأول من الموضوع الأول",
        "تمرين بكالوريا 2024",
        "الموضوع الثاني رياضيات",
        "exercise 1",
        "exercise 2 probability",
        "ابحث عن تمرين احتمالات",
    ],
)
def test_explicit_retrieval_intent_triggers_retrieval(question: str) -> None:
    """طلبات الجلب الصريحة تُطلق الاسترجاع بشكل صحيح."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is True, (
        f"طلب جلب صريح لم يُطلق الاسترجاع: '{question}' — reason={decision.reason}"
    )


# ── ISS-140: تدوين الدوال ليس نيّة استرجاع، وطلب العمل المباشر يُلغيه ────────────────
#
# البرهان الحيّ (2026-07-29، مونوليث حقيقي + OpenRouter حقيقي عبر WebSocket): الطالب سأل
# «احسب تكامل الدالة f(x) = x^2 + 3x من 0 إلى 2» فتلقّى **تمرين «الدوال العددية» المخزَّن**
# (2,328 حرفاً عن g(x)=1+(x²+x−1)e^−x) — أي إجابةً عن سؤالٍ لم يطرحه. الجذر: `f(x)` و
# `الدالة f` كانت **أنماط استرجاع مستقلّة**، وهي تظهر في كل سؤال تفاضل/تكامل تقريباً.
# هذا صنف ISS-038 عائداً بمفتاحٍ آخر: علامةٌ مسطَّحة تتجاهل النيّة.


@pytest.mark.parametrize(
    "question",
    [
        "احسب تكامل الدالة f(x) = x^2 + 3x من 0 إلى 2",
        "أوجد مشتقة f(x) = sin(x)",
        "احسب نهاية f(x) عند 0",
        "برهن أن الدالة f متزايدة",
        "بيّن أن g(x) موجبة",
        "حل المعادلة f(x) = 0",
        "ادرس تغيّرات الدالة h",
    ],
)
def test_direct_work_on_student_expression_never_fetches_a_stored_exercise(
    question: str,
) -> None:
    """طلب عملٍ مباشر على تعبير الطالب لا يُرجِع تمريناً مخزَّناً (ISS-140)."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is False, (
        f"طلب عمل مباشر أطلق الاسترجاع خطأً: '{question}' — reason={decision.reason}"
    )


@pytest.mark.parametrize(
    "question",
    [
        "ما هي نهاية الدالة f عند اللانهاية؟",
        "f(x) تساوي كم عندما x=1؟",
        "ماذا يعني g(x) هنا؟",
    ],
)
def test_bare_function_notation_alone_is_not_retrieval_intent(question: str) -> None:
    """تدوين الدالة وحده تدوينٌ لا نيّة — لا يُطلق استرجاعاً بلا قرينة (ISS-140)."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is False, (
        f"تدوين دالة وحده أطلق الاسترجاع: '{question}' — reason={decision.reason}"
    )


@pytest.mark.parametrize(
    "question",
    [
        "هات تمرين الدالة f",
        "أعطني تمرين f(x) من بكالوريا 2024",
        "تمرين الدوال العددية 2024",
    ],
)
def test_function_notation_with_a_retrieval_cue_still_retrieves(question: str) -> None:
    """التدوين **مع** قرينة استرجاع (تمرين/سنة/بكالوريا) يبقى استرجاعاً — لا تراجع."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is True, (
        f"تدوين + قرينة استرجاع لم يُطلق الاسترجاع: '{question}' — reason={decision.reason}"
    )


@pytest.mark.parametrize(
    "question",
    [
        "احسب تمرين البكالوريا 2024",
        "أوجد حل التمرين الأول",
    ],
)
def test_explicit_stored_exercise_request_outranks_direct_work(question: str) -> None:
    """طلبٌ صريح لتمرينٍ مخزَّن يتقدّم على فعل الحساب — لا نُفرِط في الإلغاء."""
    decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=question))
    assert decision.recognized is True, (
        f"طلب تمرين مخزَّن صريح أُلغي خطأً: '{question}' — reason={decision.reason}"
    )
