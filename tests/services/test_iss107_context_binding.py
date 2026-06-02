"""ISS-107 — اختبارات ربط سياق التمرين للأسئلة المتابِعة.

يثبت أن «لم افهم التكامل» و«اشرح بالعربية» بعد عرض تمرين 2016 تبقى مربوطة
بالتمرين (لا تسقط للـ LLM العام → هلوسة كيمياء)، وأنّ غياب التمرين من السياق
لا يُفعّل الربط (لا false positive).
"""

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    _is_followup_explanation_request,
    detect_explanation_with_context,
)

_HISTORY_2016 = [
    {
        "role": "user",
        "content": "تمرين 2016 الدورة الأولى الموضوع الثاني التمرين الرابع الدوال العددية",
    },
    {
        "role": "assistant",
        "content": (
            "التمرين الرابع (الدوال العددية): I. g(x)=1+(x^2+x-1)e^{-x} ... "
            "II. f(x)=-x+(x^2+3x+2)e^{-x} ... III. h(x)=x+f(x) و A(λ)=∫_0^λ h(x)dx"
        ),
    },
]


class TestFollowupMarkers:
    def test_confusion_markers(self):
        assert _is_followup_explanation_request("لم افهم التكامل")
        assert _is_followup_explanation_request("مفهمتش")
        assert _is_followup_explanation_request("كيفاش نحسب")

    def test_bare_explain_and_arabic(self):
        assert _is_followup_explanation_request("اشرح بالعربية")
        assert _is_followup_explanation_request("وضّح لي")
        assert _is_followup_explanation_request("explain in arabic")

    def test_non_followup(self):
        assert not _is_followup_explanation_request("كم عدد الطلاب")


class TestContextBinding:
    def test_confusion_binds_to_exercise(self):
        d = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="لم افهم التكامل"), history_messages=_HISTORY_2016
        )
        assert d.recognized is True
        assert d.matched_entry is not None
        assert "bac2016" in d.matched_entry.file_path

    def test_explain_in_arabic_binds_to_exercise(self):
        # هذا هو السيناريو الكارثي الأصلي (كان يهلوس كيمياء)
        d = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="اشرح بالعربية"), history_messages=_HISTORY_2016
        )
        assert d.recognized is True
        assert d.matched_entry is not None
        assert "bac2016" in d.matched_entry.file_path
        assert d.reason == "bac_explanation_with_conversation_context"

    def test_no_exercise_in_history_does_not_bind(self):
        d = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="اشرح بالعربية"), history_messages=[]
        )
        assert d.recognized is False

    def test_full_content_loaded_for_binding(self):
        d = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="وضّح لي الجزء الثالث"), history_messages=_HISTORY_2016
        )
        assert d.recognized is True
        assert d.full_content and len(d.full_content) > 500
