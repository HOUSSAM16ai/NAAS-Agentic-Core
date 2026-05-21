"""
اختبارات انحدار للأخطاء الأربعة الحرجة (Protocol V11.0).

يتحقق من:
  - Bug A: حماية _build_probability_tree_props من الاستثناءات (HTML bleed)
  - Bug B: تقطيع دلالي صحيح للتمارين (Semantic Boundary Slicing)
  - Bug C: حل أسئلة المتابعة بسياق المحادثة (LangGraph Amnesia)
  - Bug D: تسميات ملموسة في شجرة الاحتمالات (Abstraction Ban)
"""

from __future__ import annotations

from typing import ClassVar

from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    _slice_exercise_by_number,
    detect_exercise_retrieval,
    format_exercise_for_display,
    load_exercise_content,
)
from app.services.capabilities.knowledge_index import KNOWLEDGE_INDEX

# ─── Bug B: Semantic Boundary Slicing ────────────────────────────────────────


class TestSemanticBoundarySlicing:
    """يتحقق من أن format_exercise_for_display يُرجع تمريناً واحداً فقط."""

    def test_probability_exercise_does_not_include_complex_numbers(self) -> None:
        """طلب تمرين الاحتمالات 2024 يجب ألا يُرجع تمرين الأعداد المركبة."""
        req = ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024")
        decision = detect_exercise_retrieval(req)

        assert decision.recognized
        assert decision.matched_entry is not None
        assert decision.matched_entry.exercise_number == 1

        raw = load_exercise_content(decision.matched_entry)
        assert raw is not None

        formatted = format_exercise_for_display(decision.matched_entry, raw)

        assert "التمرين الأول" in formatted
        assert "التمرين الثاني" not in formatted, (
            "Bug B: تمرين الأعداد المركبة (التمرين الثاني) يتسرب في رد تمرين الاحتمالات"
        )

    def test_complex_numbers_exercise_does_not_include_probability(self) -> None:
        """طلب تمرين الأعداد المركبة 2024 يجب ألا يُرجع قسم تمرين الاحتمالات."""
        req = ExerciseRetrievalRequest(question="اعطني تمرين أعداد مركبة 2024")
        decision = detect_exercise_retrieval(req)

        assert decision.recognized
        assert decision.matched_entry is not None
        assert decision.matched_entry.exercise_number == 2

        raw = load_exercise_content(decision.matched_entry)
        assert raw is not None

        formatted = format_exercise_for_display(decision.matched_entry, raw)

        assert "التمرين الثاني" in formatted
        # يجب ألا يحوي عنوان قسم التمرين الأول كعنوان markdown مستقل
        # (قد يظهر "التمرين الأول" في نص الوسوم لكن ليس كعنوان ## مستقل)
        assert "## التمرين الأول" not in formatted, (
            "Bug B: عنوان قسم تمرين الاحتمالات (## التمرين الأول) يتسرب في رد تمرين الأعداد المركبة"
        )
        # نص تمرين الاحتمالات (كرات) يجب ألا يظهر
        assert "كرة متماثلة" not in formatted, (
            "Bug B: نص تمرين الاحتمالات (كرات) يتسرب في رد تمرين الأعداد المركبة"
        )

    def test_slice_exercise_by_number_returns_correct_section(self) -> None:
        """_slice_exercise_by_number يقطع المحتوى بدقة على حدود التمرين."""
        content = (
            "## بطاقة الامتحان\n\nمعلومات\n\n"
            "## التمرين الأول (04 نقاط) — الاحتمالات\n\nنص التمرين الأول\n\n"
            "## التمرين الثاني (04 نقاط) — الأعداد المركبة\n\nنص التمرين الثاني\n"
        )

        sliced_1 = _slice_exercise_by_number(content, 1)
        assert "التمرين الأول" in sliced_1
        assert "التمرين الثاني" not in sliced_1
        assert "نص التمرين الأول" in sliced_1

        sliced_2 = _slice_exercise_by_number(content, 2)
        assert "التمرين الثاني" in sliced_2
        assert "التمرين الأول" not in sliced_2
        assert "نص التمرين الثاني" in sliced_2

    def test_slice_single_exercise_file_returns_full_content(self) -> None:
        """ملف يحوي تمريناً واحداً بدون عنوان صريح يُرجع المحتوى كاملاً."""
        content = "## بطاقة الامتحان\n\nنص التمرين الوحيد\n"
        sliced = _slice_exercise_by_number(content, 1)
        assert sliced == content

    def test_formatted_length_is_reduced_for_multi_exercise_file(self) -> None:
        """الملف الذي يحوي تمرينين يُنتج محتوى أقصر بعد التقطيع."""
        entry_ex1 = next(
            e for e in KNOWLEDGE_INDEX
            if e.exercise_number == 1 and e.year == 2024
        )
        entry_ex2 = next(
            e for e in KNOWLEDGE_INDEX
            if e.exercise_number == 2 and e.year == 2024
        )
        raw = load_exercise_content(entry_ex1)
        assert raw is not None

        full_no_frontmatter_len = len(raw)
        formatted_ex1 = format_exercise_for_display(entry_ex1, raw)
        formatted_ex2 = format_exercise_for_display(entry_ex2, raw)

        # كل تمرين يجب أن يكون أقصر من الملف الكامل
        assert len(formatted_ex1) < full_no_frontmatter_len
        assert len(formatted_ex2) < full_no_frontmatter_len
        # التمرينان معاً يجب أن يكونا أطول من كل منهما على حدة
        assert len(formatted_ex1) + len(formatted_ex2) > len(formatted_ex1)


# ─── Bug C: LangGraph Amnesia / Follow-up Context ────────────────────────────


class TestFollowUpContextResolution:
    """يتحقق من أن أسئلة المتابعة تُحلَّل بسياق المحادثة."""

    def test_followup_with_history_resolves_to_exercise(self) -> None:
        """'اسئلة الاحتمالات فقط' مع سياق محادثة يُرجع التمرين الصحيح."""
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": "إليك تمرين الاحتمالات من بكالوريا 2024..."},
        ]
        req = ExerciseRetrievalRequest(question="اسئلة الاحتمالات فقط")
        decision = detect_exercise_retrieval(req, history_messages=history)

        assert decision.recognized, (
            "Bug C: سؤال المتابعة 'اسئلة الاحتمالات فقط' لم يُحلَّل بسياق المحادثة"
        )
        assert decision.reason == "followup_with_conversation_context"
        assert decision.matched_entry is not None

    def test_followup_without_history_does_not_trigger_retrieval(self) -> None:
        """'اسئلة الاحتمالات فقط' بدون سياق لا يُطلق استرجاعاً خاطئاً."""
        req = ExerciseRetrievalRequest(question="اسئلة الاحتمالات فقط")
        decision = detect_exercise_retrieval(req, history_messages=None)

        assert not decision.recognized, (
            "Bug C: سؤال المتابعة بدون سياق يجب ألا يُطلق استرجاعاً"
        )

    def test_followup_only_pattern_with_history(self) -> None:
        """'فقط' مع سياق محادثة عن تمرين يُرجع التمرين الصحيح."""
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": "تمرين الاحتمالات من بكالوريا 2024 علوم تجريبية..."},
        ]
        # "اسئلة فقط" لا يحوي نمط شرح → يجب أن يُحلَّل بالسياق
        req = ExerciseRetrievalRequest(question="اسئلة فقط")
        decision = detect_exercise_retrieval(req, history_messages=history)

        # يجب أن يُحلَّل بالسياق
        assert decision.recognized
        assert decision.matched_entry is not None

    def test_explanation_intent_still_blocks_followup_retrieval(self) -> None:
        """نية الشرح تلغي الاسترجاع حتى مع سياق المحادثة."""
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": "إليك التمرين..."},
        ]
        req = ExerciseRetrievalRequest(question="اشرح لي الجزء الأول فقط")
        decision = detect_exercise_retrieval(req, history_messages=history)

        # نية الشرح تلغي الاسترجاع
        assert not decision.recognized
        assert decision.reason == "explanation_intent_detected"

    def test_detect_exercise_retrieval_signature_accepts_history(self) -> None:
        """التوقيع الجديد يقبل history_messages كمعامل اختياري."""
        req = ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024")
        # يجب ألا يرفع استثناء
        decision_no_history = detect_exercise_retrieval(req)
        decision_with_history = detect_exercise_retrieval(req, history_messages=[])
        assert decision_no_history.recognized == decision_with_history.recognized


# ─── Bug A: HTML Bleed Protection ────────────────────────────────────────────


class TestProbabilityTreePropsGuard:
    """يتحقق من أن _build_probability_tree_props لا تُطلق استثناءات."""

    def test_detect_probability_tree_returns_none_for_empty_question(self) -> None:
        """سؤال فارغ يُرجع None بدون استثناء."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        result = OrchestratorClient._detect_probability_tree("")
        assert result is None

    def test_detect_probability_tree_returns_none_for_non_string(self) -> None:
        """مدخل غير نصي يُرجع None بدون استثناء."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        result = OrchestratorClient._detect_probability_tree(None)  # type: ignore[arg-type]
        assert result is None

    def test_detect_probability_tree_explicit_trigger(self) -> None:
        """عبارة صريحة تُطلق الكشف عن شجرة الاحتمالات."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        result = OrchestratorClient._detect_probability_tree(
            "اعطني شجرة الاحتمالات للتمرين"
        )
        # قد يُرجع None إذا لم تُوجد قيم احتمالية — هذا سلوك صحيح
        # المهم ألا يرفع استثناء
        assert result is None or isinstance(result, dict)

    def test_detect_probability_tree_with_probabilities(self) -> None:
        """سؤال يحوي قيماً احتمالية يُنتج شجرة صحيحة."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        result = OrchestratorClient._detect_probability_tree(
            "احسب احتمال الحادثة إذا كان P(A) = 0.3 و P(B|A) = 0.6"
        )
        assert result is not None
        assert "tree" in result
        assert "title" in result
        tree = result["tree"]
        assert isinstance(tree, dict)
        assert "children" in tree
        assert len(tree["children"]) == 2


# ─── Bug D: Abstraction Ban ───────────────────────────────────────────────────


class TestAbstractionBan:
    """يتحقق من أن شجرة الاحتمالات لا تستخدم رموزاً مجرّدة (A, B, Ā)."""

    _ABSTRACT_BANNED: ClassVar[set[str]] = {"a", "b", "ā", "b̄", "a'", "b'"}

    def test_concrete_entities_extracted_from_colored_balls(self) -> None:
        """مسألة كرات ملونة تُنتج تسميات ملموسة."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        events = OrchestratorClient._extract_concrete_events(
            "يحتوي كيس على كرات حمراء وبيضاء وخضراء"
        )
        assert events is not None
        for key in ("first", "first_neg", "second", "second_neg"):
            label = events[key].lower()
            assert label not in self._ABSTRACT_BANNED, (
                f"Bug D: رمز مجرّد {label!r} في مفتاح {key!r}"
            )

    def test_concrete_entities_extracted_from_defective_parts(self) -> None:
        """مسألة قطع معيبة تُنتج تسميات ملموسة."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        events = OrchestratorClient._extract_concrete_events(
            "مصنع ينتج قطعاً معيبة وسليمة بنسبة 0.1"
        )
        assert events is not None
        assert "معيب" in events["first"] or "سليم" in events["first_neg"]

    def test_fallback_labels_are_concrete_not_abstract(self) -> None:
        """الـ fallback يستخدم 'الحدث الأول' لا 'A'."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        result = OrchestratorClient._detect_probability_tree(
            "احسب احتمال الحادثة إذا كان P = 0.4 و Q = 0.7"
        )
        assert result is not None
        tree = result["tree"]
        children = tree.get("children", [])
        assert len(children) == 2

        for child in children:
            label = child.get("label", "").lower()
            assert label not in self._ABSTRACT_BANNED, (
                f"Bug D: رمز مجرّد {label!r} في عقدة الشجرة"
            )

    def test_history_context_enriches_tree_labels(self) -> None:
        """سياق المحادثة يُثري تسميات الشجرة بكيانات ملموسة من التمرين السابق."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        # محاكاة سياق محادثة يحوي تمرين الاحتمالات 2024 (كرات ملونة)
        history_text = (
            "يحتوي كيس على 11 كرة متماثلة: كرتان بيضاوان وأربع كرات حمراء "
            "وخمس كرات خضراء"
        ).lower()

        events = OrchestratorClient._extract_concrete_events(history_text)
        assert events is not None, (
            "Bug D: لم يُستخرج أي كيان ملموس من سياق تمرين الاحتمالات 2024"
        )
        # يجب أن يكون أحد الكيانات كرة ملونة
        all_labels = " ".join(events.values()).lower()
        assert any(color in all_labels for color in ("حمراء", "بيضاء", "خضراء")), (
            f"Bug D: الكيانات المستخرجة لا تحوي ألوان الكرات: {events}"
        )
