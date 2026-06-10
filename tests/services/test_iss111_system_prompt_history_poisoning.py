"""
ISS-111 (D-102) — System-Prompt History Poisoning regression gate.

الكارثة الحية (2026-06-10، مُثبتة بالتجريب الحي على المسار الكامل):
`get_chat_history` يحقن `{"role": "system", "content": get_customer_system_prompt()}`
في رأس كل history. برومبت Overmind الإنجليزي يحوي كلمات عامة ("math", "physics")
كانت تمرّ عبر tag-fallback في `_find_matching_entry` → `_detect_entry_from_history`
يربط **كل** سؤال يحوي «اشرح/وضح/أكمل» بتمرين 2024 — حتى في محادثة جديدة فارغة.

النتيجة المرئية: «ما هو قانون نيوتن الثاني؟ اشرح بإيجاز» → «عذراً، لا يمكنني الخوض
في موضوع غير متعلق بتمرين الرياضيات المذكور أعلاه» + المسار لا يصل للـ orchestrator
أبداً (الـ preempt يخطفه قبل HTTP).

الإصلاح المزدوج:
  1. `_detect_entry_from_history` يفحص رسائل user/assistant فقط (لا system).
  2. الربط بالتاريخ يتطلب تطابقاً بنيوياً (سنة/موضوع/رقم/موضوع مرجعي) —
     `_find_matching_entry(..., allow_tag_fallback=False)`.
"""

from __future__ import annotations

from typing import ClassVar

from app.core.prompts import get_customer_system_prompt
from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    _detect_entry_from_history,
    _find_matching_entry,
    detect_exercise_retrieval,
    detect_explanation_with_context,
)

_NEWTON_Q = "ما هو قانون نيوتن الثاني؟ اشرح بإيجاز مع الصيغة الرياضية"


def _system_history(question: str) -> list[dict[str, str]]:
    """يحاكي بالضبط ما يبنيه get_chat_history لمحادثة جديدة."""
    return [
        {"role": "system", "content": get_customer_system_prompt()},
        {"role": "user", "content": question},
    ]


class TestSystemPromptPoisoning:
    """الكارثة: برومبت النظام في الـ history كان يربط أي سؤال شرح بتمرين 2024."""

    def test_newton_with_fresh_conversation_not_bound(self) -> None:
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question=_NEWTON_Q),
            history_messages=_system_history(_NEWTON_Q),
        )
        assert not decision.recognized, (
            "ISS-111 REGRESSION: a generic physics question in a FRESH conversation "
            "got bound to a BAC exercise via the system prompt in history."
        )

    def test_system_only_history_yields_no_entry(self) -> None:
        entry = _detect_entry_from_history(
            [{"role": "system", "content": get_customer_system_prompt()}]
        )
        assert entry is None

    def test_retrieval_followup_not_poisoned_by_system_prompt(self) -> None:
        # المسار الموازي (ISS-CONV-C في detect_exercise_retrieval) محمي أيضاً.
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question="اعطني الاسئلة فقط"),
            history_messages=_system_history("اعطني الاسئلة فقط"),
        )
        assert decision.matched_entry is None


class TestStructuralOnlyHistoryBinding:
    """الربط بالتاريخ بنيوي فقط — لا tag-fallback على كلمات عامة."""

    def test_generic_words_history_no_binding(self) -> None:
        history = [
            {"role": "user", "content": "أحب الرياضيات والفيزياء والبرمجة"},
            {"role": "assistant", "content": "رائع! العلوم ممتعة فعلاً."},
        ]
        assert _detect_entry_from_history(history) is None

    def test_find_matching_entry_tag_fallback_flag(self) -> None:
        # نص بلا أي إشارة بنيوية لكنه يحوي كلمة وسم عامة
        text = "math exercise educational assistant"
        assert _find_matching_entry(text, allow_tag_fallback=False) is None

    def test_question_path_tag_fallback_preserved(self) -> None:
        # مسار سؤال الطالب المباشر يحتفظ بالـ fallback الافتراضي (سلوك سابق).
        # «تمرين دوال عددية» بنيوي أصلاً — لكن نتأكد أن default=True لم يتغير.
        import inspect

        sig = inspect.signature(_find_matching_entry)
        assert sig.parameters["allow_tag_fallback"].default is True


class TestLegitimateFollowupsStillBind:
    """regressions: ISS-058 / ISS-107 / ISS-108 تبقى تعمل (تطابق بنيوي حقيقي)."""

    _HIST_2016: ClassVar[list[dict[str, str]]] = [
        {"role": "system", "content": "You are Overmind, an educational assistant."},
        {"role": "user", "content": "اعطني تمرين الدوال العددية 2016"},
        {
            "role": "assistant",
            "content": "بكالوريا الرياضيات 2016 — الدورة الأولى — الموضوع الثاني "
            "التمرين الرابع: الدوال العددية...",
        },
    ]

    _HIST_PROB: ClassVar[list[dict[str, str]]] = [
        {"role": "system", "content": "You are Overmind, an educational assistant."},
        {"role": "user", "content": "اعطني تمرين الاحتمالات"},
        {
            "role": "assistant",
            "content": "التمرين الأول (04 نقاط) — الاحتمالات: يحتوي كيس على 11 كرة... "
            "بكالوريا 2024",
        },
    ]

    def test_concept_followup_binds_to_2016(self) -> None:
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="ماذا نقصد بدالة أصلية"),
            history_messages=self._HIST_2016,
        )
        assert decision.recognized
        assert decision.matched_entry is not None
        assert "2016" in decision.matched_entry.file_path

    def test_confusion_followup_binds_iss107(self) -> None:
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="لم افهم التكامل"),
            history_messages=self._HIST_2016,
        )
        assert decision.recognized

    def test_continue_followup_binds_iss108(self) -> None:
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question="أكمل الشرح"),
            history_messages=self._HIST_PROB,
        )
        assert decision.recognized
        assert decision.matched_entry is not None
        assert "2024" in decision.matched_entry.file_path
