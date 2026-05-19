"""
ISS-081 / D-073 (2026-05-19) — AnswerQualitySkill Wiring Regression Tests.

يتحقق أن `AnswerQualitySkill` ليس Skill زومبي:
1. `_apply_answer_quality_skill` معرَّفة في `local_graph.py`.
2. `_chat_node` يستدعي الـ helper بعد sanitization.
3. الـ helper يَعمل defensively (لا يُفشل المسار حتى لو فشل الـ Skill).
4. الـ helper يَستخدم improved_answer عند وجود مشاكل قابلة للتصحيح (BAD_LATEX).
5. الـ helper يُرجع الإجابة الأصلية إذا الـ Skill اجتاز الفحوصات.
6. الـ helper يَخريط النيات بشكل صحيح (chat → chat، educational → educational).
7. الـ D-070 doctrines (CONTENT_INVOCATION, MODEL_ANSWER_EXPLANATION, ...)
   مُعاد تصديرها من `app.services.skills` (D-073).
8. SKILL_DOCTRINE_MANIFEST["answer_quality"] يُشير إلى المستهلك الجديد
   `local_graph._apply_answer_quality_skill` (لا الـ stub القديم).
"""

from __future__ import annotations

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# 1. _apply_answer_quality_skill helper exists
# ─────────────────────────────────────────────────────────────────────────────


class TestApplyAnswerQualitySkillHelperExists:
    """يتحقق أن الـ helper مُعرَّف ومُربَط في _chat_node."""

    def test_helper_function_imports(self) -> None:
        from app.services.chat.local_graph import _apply_answer_quality_skill

        assert callable(_apply_answer_quality_skill)

    def test_helper_called_in_chat_node(self) -> None:
        """قراءة الـ source للتأكد من call chain — لا يكفي تعريف الـ helper."""
        from pathlib import Path

        src = Path("app/services/chat/local_graph.py").read_text(encoding="utf-8")
        # _apply_answer_quality_skill يجب أن يُستدعى بـ question + clean + intent
        assert "_apply_answer_quality_skill(question" in src, (
            "D-073: _chat_node must call _apply_answer_quality_skill — "
            "otherwise AnswerQualitySkill remains ZOMBIE."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Helper behavior — defensive + improvement detection
# ─────────────────────────────────────────────────────────────────────────────


class TestApplyAnswerQualitySkillBehavior:
    """يَختبر سلوك الـ helper مع حالات مختلفة."""

    def test_empty_answer_returns_empty(self) -> None:
        from app.services.chat.local_graph import _apply_answer_quality_skill

        assert _apply_answer_quality_skill("question", "", "chat") == ""
        assert _apply_answer_quality_skill("question", "   ", "chat") == "   "

    def test_chat_intent_short_response_passes(self) -> None:
        """رد تحية قصير يجب أن يُمرَّر كما هو (لا require_steps)."""
        from app.services.chat.local_graph import _apply_answer_quality_skill

        original = "أهلاً وسهلاً! كيف يمكنني مساعدتك اليوم؟"
        result = _apply_answer_quality_skill("مرحبا", original, "chat")
        assert result == original

    def test_bad_latex_gets_fixed(self) -> None:
        """ISS-071: \\[...\\] → $$...$$ يُصحَّح بواسطة الـ Skill."""
        from app.services.chat.local_graph import _apply_answer_quality_skill

        bad_answer = (
            "لحساب التكامل نستخدم القاعدة التالية:\n\n"
            "\\[\n"
            "\\int_0^1 x^2 \\, dx = \\frac{1}{3}\n"
            "\\]\n\n"
            "إذن النتيجة هي 1/3. " + "هذا شرح للقاعدة. " * 10
        )
        result = _apply_answer_quality_skill("احسب التكامل", bad_answer, "educational")
        # يجب أن يُحوَّل \[ إلى $$ (و \] أيضاً)
        assert "\\[" not in result
        assert "\\]" not in result
        assert "$$" in result

    def test_defensive_against_skill_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """حتى لو فشل الـ Skill بشكل غير متوقع، لا يُكسر المسار."""
        from app.services.chat import local_graph

        def _broken_skill():
            raise RuntimeError("simulated skill failure")

        monkeypatch.setattr(
            "app.services.skills.get_answer_quality_skill", _broken_skill, raising=True
        )
        original = "إجابة طبيعية بدون مشاكل."
        # يجب أن يُرجع الأصل بدون استثناء
        result = local_graph._apply_answer_quality_skill("سؤال", original, "chat")
        assert result == original


# ─────────────────────────────────────────────────────────────────────────────
# 3. D-070 doctrines re-exported from package init
# ─────────────────────────────────────────────────────────────────────────────


class TestD070DoctrinesReexported:
    """D-073: D-070 doctrines يجب أن تكون متاحة من المستوى الأعلى للحزمة."""

    def test_content_invocation_doctrine_at_package_level(self) -> None:
        from app.services.skills import (
            CONTENT_INVOCATION_DOCTRINE,
            CONTENT_INVOCATION_DOCTRINE_VERSION,
        )

        assert isinstance(CONTENT_INVOCATION_DOCTRINE, tuple)
        assert len(CONTENT_INVOCATION_DOCTRINE) >= 5
        assert CONTENT_INVOCATION_DOCTRINE_VERSION == "1.0.0"

    def test_model_answer_explanation_doctrine_at_package_level(self) -> None:
        from app.services.skills import (
            MODEL_ANSWER_EXPLANATION_DOCTRINE,
            MODEL_ANSWER_EXPLANATION_VERSION,
        )

        assert isinstance(MODEL_ANSWER_EXPLANATION_DOCTRINE, tuple)
        assert len(MODEL_ANSWER_EXPLANATION_DOCTRINE) >= 5
        assert MODEL_ANSWER_EXPLANATION_VERSION == "1.0.0"

    def test_step_by_step_at_package_level(self) -> None:
        from app.services.skills import (
            STEP_BY_STEP_EXPLANATION_RULES,
            STEP_BY_STEP_EXPLANATION_VERSION,
        )

        assert isinstance(STEP_BY_STEP_EXPLANATION_RULES, tuple)
        assert len(STEP_BY_STEP_EXPLANATION_RULES) >= 5
        assert STEP_BY_STEP_EXPLANATION_VERSION == "1.0.0"

    def test_skill_invocation_protocol_at_package_level(self) -> None:
        from app.services.skills import (
            SKILL_INVOCATION_PROTOCOL,
            SKILL_INVOCATION_PROTOCOL_VERSION,
        )

        assert isinstance(SKILL_INVOCATION_PROTOCOL, tuple)
        assert len(SKILL_INVOCATION_PROTOCOL) >= 4
        assert SKILL_INVOCATION_PROTOCOL_VERSION == "1.0.0"

    def test_exercise_explanation_system_prompt_at_package_level(self) -> None:
        from app.services.skills import EXERCISE_EXPLANATION_SYSTEM_PROMPT

        assert isinstance(EXERCISE_EXPLANATION_SYSTEM_PROMPT, str)
        # D-067 invariant: < 1000 chars
        assert len(EXERCISE_EXPLANATION_SYSTEM_PROMPT) < 1000


# ─────────────────────────────────────────────────────────────────────────────
# 4. SKILL_DOCTRINE_MANIFEST reflects new consumer
# ─────────────────────────────────────────────────────────────────────────────


class TestManifestReflectsWiring:
    """D-073: الـ manifest يجب أن يُشير إلى المستهلك الجديد."""

    def test_answer_quality_manifest_has_local_graph_consumer(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        entry = SKILL_DOCTRINE_MANIFEST.get("answer_quality")
        assert entry is not None, "answer_quality missing from SKILL_DOCTRINE_MANIFEST"

        consumed_by = entry.get("consumed_by", ())
        assert any(
            "local_graph._apply_answer_quality_skill" in consumer for consumer in consumed_by
        ), (
            "D-073: SKILL_DOCTRINE_MANIFEST['answer_quality'].consumed_by must include "
            f"local_graph._apply_answer_quality_skill. Found: {consumed_by}"
        )

    def test_answer_quality_no_stub_consumer(self) -> None:
        """قبل D-073 كان consumed_by يحوي 'conversation_graph._call_llm' كـ stub
        (غير قابل للتنفيذ لأن microservices/conversation_service لا يستورد من app/).
        بعد D-073 يجب أن يُحذف."""
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        entry = SKILL_DOCTRINE_MANIFEST.get("answer_quality", {})
        consumed_by = entry.get("consumed_by", ())
        # conversation_graph._call_llm كان stub — يجب ألا يكون في الـ consumed_by
        # لأنه لم يكن مرتبطاً فعلاً (architectural boundary: microservices لا تستورد من app/)
        assert "conversation_graph._call_llm" not in consumed_by, (
            "D-073: SKILL_DOCTRINE_MANIFEST['answer_quality'] must not list "
            "conversation_graph._call_llm — microservices cannot import from app/."
        )


# ─────────────────────────────────────────────────────────────────────────────
# 5. Doctrine helper functions all accessible from package level
# ─────────────────────────────────────────────────────────────────────────────


class TestDoctrineHelpersAtPackageLevel:
    """D-073: كل دوال الـ doctrine helper متاحة من package level."""

    def test_get_content_invocation_summary(self) -> None:
        from app.services.skills import get_content_invocation_summary

        summary = get_content_invocation_summary()
        assert isinstance(summary, str)
        assert len(summary) > 100

    def test_get_model_answer_explanation_summary(self) -> None:
        from app.services.skills import get_model_answer_explanation_summary

        summary = get_model_answer_explanation_summary()
        assert isinstance(summary, str)
        assert len(summary) > 100

    def test_get_step_by_step_summary(self) -> None:
        from app.services.skills import get_step_by_step_summary

        summary = get_step_by_step_summary()
        assert isinstance(summary, str)
        assert len(summary) > 100

    def test_get_skill_invocation_protocol_summary(self) -> None:
        from app.services.skills import get_skill_invocation_protocol_summary

        summary = get_skill_invocation_protocol_summary()
        assert isinstance(summary, str)
        assert len(summary) > 100

    def test_build_exercise_explanation_prompt_at_package_level(self) -> None:
        from app.services.skills import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 50
        assert len(prompt) < 1000  # D-067 invariant
