"""
ISS-110 (D-101) — Topic-Switch Routing Catastrophe regression gate.

الكارثة الحية (2026-06-10): في محادثة واحدة، بعد استرجاع تمرين الاحتمالات،
طلب «اعطني تمرين الدوال العددية» أرجع combinations_visualizer (كيس التمرين
السابق C(11,3)=165) بدل تمرين الدوال 2016 المُفهرَس.

الجذر المزدوج:
  RC-1: بوابة `_PROBABILITY_CONTEXT` في probability_skill.analyze كانت تفحص
        النص المُدمَج (سؤال + history) — سؤال بلا أي كلمة احتمالية يمرّ لأن
        الـ history يحوي «احتمالات/سحب/كيس»، ثم تُستخرج تركيبة الكيس من الـ history.
  RC-2: `_build_calculated_ui` كان يسبق `_has_indexed_match` في chat_with_agent،
        و MODE_A (terminate_pipeline=True) يُنهي المسار قبل وصول الاسترجاع المُفهرَس.

هذا الملف يحرس الإصلاحين معاً:
  1. ترتيب المصدر: الاسترجاع المُفهرَس قبل الواجهة المحسوبة في chat_with_agent.
  2. `_build_calculated_ui` يُرجع None لطلب موضوع آخر بعد سياق احتمالات.
  3. الاسترجاع المُفهرَس يتعرّف فعلاً على طلب الدوال العددية (ملف bac2016).
"""

from __future__ import annotations

import inspect
from pathlib import Path

from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.capabilities.exercise_retrieval import (
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
)

_PROB_HISTORY = [
    {"role": "user", "content": "اعطني تمرين الاحتمالات"},
    {
        "role": "assistant",
        "content": (
            "يحتوي كيس على 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات "
            "خضراء. نسحب عشوائيًا 3 كرات دفعة واحدة من الكيس. احسب احتمال "
            "الحادثة A: الحصول على 3 كرات من نفس اللون."
        ),
    },
]


class TestPreemptionOrder:
    """RC-2: الاسترجاع المُفهرَس يجب أن يسبق الواجهة المحسوبة في chat_with_agent."""

    def test_indexed_match_precedes_calculated_ui_in_source(self) -> None:
        # D-170: chat_with_agent صار مُنسِّقاً يمشي مراحل sub-generator بالترتيب —
        # عقد ISS-110 يعيش الآن في ترتيب tuple المراحل + محتوى كل مرحلة.
        source = inspect.getsource(OrchestratorClient.chat_with_agent)
        idx_indexed = source.find("self._stage_indexed_retrieval")
        idx_calculated = source.find("self._stage_calculated_ui")
        assert idx_indexed != -1, "indexed retrieval stage missing from chat_with_agent dispatch"
        assert idx_calculated != -1, "calculated UI stage missing from chat_with_agent dispatch"
        assert idx_indexed < idx_calculated, (
            "ISS-110 REGRESSION: _stage_calculated_ui dispatched before "
            "_stage_indexed_retrieval — explicit exercise requests will be "
            "hijacked by the probability UI again."
        )
        # الاستدعاءات الفعلية تعيش داخل المرحلتين (لا في التعليقات).
        assert "self._has_indexed_match(" in inspect.getsource(
            OrchestratorClient._stage_indexed_retrieval
        ), "indexed retrieval call missing from its stage"
        assert "self._build_calculated_ui(" in inspect.getsource(
            OrchestratorClient._stage_calculated_ui
        ), "calculated UI call missing from its stage"

    def test_iss110_comment_anchor_present(self) -> None:
        source = inspect.getsource(OrchestratorClient._stage_indexed_retrieval)
        assert "ISS-110" in source


class TestCalculatedUiTopicSwitchGuard:
    """RC-1: طلب موضوع آخر بعد سياق احتمالات لا يبني أي واجهة احتمالات."""

    def test_numerical_functions_request_returns_none(self) -> None:
        event = OrchestratorClient._build_calculated_ui(
            "اعطني تمرين الدوال العددية", history_messages=_PROB_HISTORY
        )
        assert event is None

    def test_numerical_functions_with_year_returns_none(self) -> None:
        event = OrchestratorClient._build_calculated_ui(
            "اعطني تمرين الدوال العددية لسنة 2016", history_messages=_PROB_HISTORY
        )
        assert event is None

    def test_complex_numbers_request_returns_none(self) -> None:
        event = OrchestratorClient._build_calculated_ui(
            "اعطني تمرين الأعداد المركبة", history_messages=_PROB_HISTORY
        )
        assert event is None

    def test_confused_about_other_topic_returns_none(self) -> None:
        # حتى مع إشارة حيرة، ذكر موضوع آخر صريح يحجب واجهة الاحتمالات.
        event = OrchestratorClient._build_calculated_ui(
            "لم أفهم تمرين الدوال العددية", history_messages=_PROB_HISTORY
        )
        assert event is None

    def test_probability_confusion_followup_still_fires(self) -> None:
        # regression: حيرة احتمالية حقيقية بعد التمرين تبقى تُفعِّل الأداة البصرية.
        event = OrchestratorClient._build_calculated_ui(
            "مفهمتش كيفاش حسبنا الاحتمال", history_messages=_PROB_HISTORY
        )
        assert event is not None
        assert event.get("routing_mode") == "MODE_B"

    def test_direct_probability_question_still_fires(self) -> None:
        event = OrchestratorClient._build_calculated_ui(
            "كيس فيه 4 كرات حمراء و7 كرات بيضاء، نسحب كرة. ارسم شجرة الاحتمالات",
            history_messages=None,
        )
        assert event is not None


class TestIndexedRetrievalRecognition:
    """الاسترجاع المُفهرَس يتعرّف على الطلبات التي كانت تُختطف."""

    def test_numerical_functions_request_matches_bac2016(self) -> None:
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question="اعطني تمرين الدوال العددية")
        )
        assert decision.recognized
        assert decision.matched_entry is not None
        assert "numerical_functions" in decision.matched_entry.file_path

    def test_numerical_functions_with_year_matches_bac2016(self) -> None:
        decision = detect_exercise_retrieval(
            ExerciseRetrievalRequest(question="اعطني تمرين الدوال العددية لسنة 2016")
        )
        assert decision.recognized
        assert decision.matched_entry is not None
        assert "bac2016" in Path(decision.matched_entry.file_path).name
