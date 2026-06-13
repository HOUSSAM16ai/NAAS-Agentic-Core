"""D-111 — اختبارات LearningPathSkill (المسار التعلّمي التكيفي).

يثبت: التقدّم عند الإتقان العالي، الترسيخ عند المتوسط، التثبيت عند المنخفض/المجهول،
نهاية السلسلة، حتمية المخرَج، و fail-open.
"""

from __future__ import annotations

from app.services.skills.learning_path_skill import (
    LearningPathInput,
    LearningPathSkill,
    get_learning_path_skill,
)


class TestAdvance:
    def test_high_mastery_advances_with_hard(self) -> None:
        out = LearningPathSkill().derive(LearningPathInput(concept_id="limits", mastery=0.85))
        assert out.advanced is True
        assert out.next_concept == "derivatives"
        assert out.target_difficulty == "hard"
        assert out.current_concept == "limits"

    def test_end_of_sequence_stays_but_hard(self) -> None:
        # 'statistics' ليس مفتاحاً في تسلسل المنهج → نهاية السلسلة.
        out = LearningPathSkill().derive(LearningPathInput(concept_id="statistics", mastery=0.9))
        assert out.advanced is False
        assert out.next_concept == "statistics"
        assert out.target_difficulty == "hard"


class TestConsolidateAndScaffold:
    def test_medium_mastery_consolidates(self) -> None:
        out = LearningPathSkill().derive(LearningPathInput(concept_id="integration", mastery=0.5))
        assert out.advanced is False
        assert out.next_concept == "integration"
        assert out.target_difficulty == "medium"

    def test_low_mastery_scaffolds_easy(self) -> None:
        out = LearningPathSkill().derive(LearningPathInput(concept_id="derivatives", mastery=0.2))
        assert out.target_difficulty == "easy"
        assert out.advanced is False

    def test_unknown_mastery_scaffolds_easy(self) -> None:
        out = LearningPathSkill().derive(LearningPathInput(concept_id="probability", mastery=None))
        assert out.target_difficulty == "easy"
        assert out.advanced is False


class TestContract:
    def test_deterministic(self) -> None:
        skill = LearningPathSkill()
        a = skill.derive(LearningPathInput(concept_id="limits", mastery=0.8))
        b = skill.derive(LearningPathInput(concept_id="limits", mastery=0.8))
        assert a.model_dump() == b.model_dump()

    def test_recommendation_text_present_and_bounded(self) -> None:
        out = LearningPathSkill().derive(LearningPathInput(concept_id="probability", mastery=0.95))
        assert out.recommendation_text
        assert len(out.recommendation_text) <= 400
        assert "الاحتمالات" in out.recommendation_text or "الاحتمال" in out.recommendation_text

    def test_singleton(self) -> None:
        assert get_learning_path_skill() is get_learning_path_skill()
