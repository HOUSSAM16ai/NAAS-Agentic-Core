"""ISS-114 (D-106) — كاشف نية «توليد واجهة» يوجّه للأداة البصرية لا للـ LLM.

«قم بتوليد واجهة تشرح الحادثة P(A)» كان يسقط للـ LLM فيكتب HTML خاماً. الآن
يُفعِّل المسار البصري المُهيكل (MODE_B)؛ وطلب موضوع آخر صريح يبقى محجوباً.
"""

from __future__ import annotations

from app.services.skills.probability_skill import ProbabilityCalculatorSkill


class TestIsVisualRequest:
    def test_positive_markers(self) -> None:
        for q in (
            "قم بتوليد واجهة تشرح الحادثة P(A)",
            "أنشئ واجهة توضح المتغير العشوائي",
            "اعمل لي واجهة تفاعلية للاحتمالات",
            "صمم واجهة تشرح فضاء العيّنة",
        ):
            assert ProbabilityCalculatorSkill.is_visual_request(q) is True

    def test_negative_markers(self) -> None:
        for q in (
            "احسب احتمال الحادثة A",
            "اشرح لي قانون نيوتن الثاني",
            "ما هو التكامل بالتجزئة",
        ):
            assert ProbabilityCalculatorSkill.is_visual_request(q) is False


class TestVisualRequestRouting:
    def test_fresh_conversation_visual_request_reaches_strategy(self) -> None:
        """طلب واجهة + إشارة احتمالية في السؤال يمرّ بوابة السياق بلا history."""
        from app.services.skills.probability_skill import ProbabilityInput

        out = ProbabilityCalculatorSkill().analyze(
            ProbabilityInput(
                question="قم بتوليد واجهة تشرح الحادثة P(A) في كيس فيه 4 كرات حمراء و7 خضراء"
            )
        )
        # لم يعد يسقط على بوابة «no_probability_context».
        assert getattr(out, "reason", None) != "no_probability_context"

    def test_visual_request_with_probability_history_routes_mode_b(self) -> None:
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        client = OrchestratorClient()
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات"},
            {
                "role": "assistant",
                "content": "كيس فيه أربع كرات حمراء وخمس كرات خضراء وكرتان بيضاوان، نسحب 3 كرات دفعة واحدة",
            },
        ]
        event = client._build_calculated_ui(
            "قم بتوليد واجهة تشرح الحادثة P(A)", history_messages=history
        )
        assert event is not None
        assert event.get("routing_mode") == "MODE_B"

    def test_topic_switch_visual_request_blocked(self) -> None:
        """«اعمل لي واجهة للدوال العددية» → None (حاجب تبديل الموضوع D-101 صامد)."""
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        client = OrchestratorClient()
        history = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات"},
            {"role": "assistant", "content": "كيس فيه أربع كرات حمراء وخمس خضراء"},
        ]
        event = client._build_calculated_ui(
            "اعمل لي واجهة للدوال العددية", history_messages=history
        )
        assert event is None
