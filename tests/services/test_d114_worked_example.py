"""D-114 / ISS-116 — المثال المحلول المُتدرّج المُقيَّد بالإتقان.

يثبت أن النظام (جانب المونوليث):
1. `WorkedExampleSkill` يكشف فقط للمبتدئ المطلق (support_level==1) أو الحيرة
   المتكرّرة (confusion≥2)؛ ويبني خريطة منهجية + توجيه LLM ملفوف بالفواصل.
2. الحجب الواعي بالفواصل (app port): يُعفي ما داخل الفواصل عند support_level==1،
   ويحجب ما عداها (fail-closed) عند الغياب/المستويات الأخرى.
3. الـ doctrine + manifest + الـ registry متّسقة (no-ZOMBIE).
4. `UIComponentPayload` يقبل `worked_example_card`.

الكارثة (transcript حي): طالب بإتقان 14% حار وسأل «لو جاء يوم الامتحان لا أستطيع
حله؟» فردّ النظام بحلقة سقراطية فارغة بلا مثال محلول → غرق ورسب. D-113 طُبِّق
بإفراط فحرم المبتدئ من المخطط الذهني (worked-example effect, Sweller).
"""

from __future__ import annotations

import pytest


# ── 1. WorkedExampleSkill — بوّابة الكشف ──────────────────────────────────────
class TestWorkedExampleGating:
    def test_reveals_for_absolute_novice(self) -> None:
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        out = get_worked_example_skill().derive(
            WorkedExampleInput(concept_id="probability", mastery=0.14, support_level=1)
        )
        assert out.should_reveal is True
        assert out.card_title
        assert len(out.steps) >= 3
        assert out.bridge_text
        assert out.prompt_directive

    def test_reveals_on_repeated_confusion(self) -> None:
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        # حتى مع support_level أعلى، الحيرة المتكرّرة تكشف
        out = get_worked_example_skill().derive(
            WorkedExampleInput(concept_id="integration", support_level=3, confusion_count=2)
        )
        assert out.should_reveal is True

    def test_withholds_for_competent_student(self) -> None:
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        out = get_worked_example_skill().derive(
            WorkedExampleInput(concept_id="probability", mastery=0.9, support_level=5)
        )
        assert out.should_reveal is False
        assert out.steps == ()
        assert out.prompt_directive == ""

    def test_deterministic(self) -> None:
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        skill = get_worked_example_skill()
        payload = WorkedExampleInput(concept_id="derivatives", support_level=1)
        a = skill.derive(payload)
        b = skill.derive(payload)
        assert a.model_dump() == b.model_dump()

    def test_directive_wraps_in_sentinels(self) -> None:
        from app.services.skills.doctrine import (
            WORKED_EXAMPLE_CLOSE,
            WORKED_EXAMPLE_OPEN,
        )
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        out = get_worked_example_skill().derive(
            WorkedExampleInput(concept_id="probability", support_level=1)
        )
        assert WORKED_EXAMPLE_OPEN in out.prompt_directive
        assert WORKED_EXAMPLE_CLOSE in out.prompt_directive
        # المثال على مسألة مماثلة لا تمرين الطالب
        assert "مماثل" in out.prompt_directive

    def test_steps_carry_concrete_subgoals_and_colors(self) -> None:
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        out = get_worked_example_skill().derive(
            WorkedExampleInput(concept_id="probability", support_level=1)
        )
        for step in out.steps:
            assert step.subgoal_label  # تسمية ملموسة (لا رمز مجرّد)
            assert step.subgoal_color.startswith("#")
            assert step.self_explanation_prompt  # سؤال «لماذا؟»

    def test_unknown_concept_uses_default_methodology(self) -> None:
        from app.services.skills.worked_example_skill import (
            WorkedExampleInput,
            get_worked_example_skill,
        )

        out = get_worked_example_skill().derive(
            WorkedExampleInput(concept_id="totally_unknown_xyz", support_level=1)
        )
        assert out.should_reveal is True
        assert len(out.steps) >= 3


# ── 2. الحجب الواعي بالفواصل (app port) ───────────────────────────────────────
class TestSentinelAwareRedaction:
    def test_exempt_inside_redact_outside(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers
        from app.services.skills.doctrine import (
            WORKED_EXAMPLE_CLOSE,
            WORKED_EXAMPLE_OPEN,
        )

        text = (
            "مقدمة. "
            + WORKED_EXAMPLE_OPEN
            + "مثال مماثل: P(A)=4/9 إذن النتيجة = 0.44"
            + WORKED_EXAMPLE_CLOSE
            + " طبّق على تمرينك. (تسريب) P(B)=14/165"
        )
        out, _ = redact_final_answers(text, support_level=1)
        assert "4/9" in out, "inside-sentinel worked example must survive"
        assert "14/165" not in out, "leaked graded answer outside must be redacted"
        assert WORKED_EXAMPLE_OPEN not in out and WORKED_EXAMPLE_CLOSE not in out

    def test_full_redaction_without_sentinels(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out, _ = redact_final_answers("الجواب: P(A)=3/7", support_level=1)
        assert "3/7" not in out, "no sentinels => fail-closed full redaction"

    def test_level_5_redacts_even_inside_sentinels(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers
        from app.services.skills.doctrine import (
            WORKED_EXAMPLE_CLOSE,
            WORKED_EXAMPLE_OPEN,
        )

        text = WORKED_EXAMPLE_OPEN + "P(A)=4/9" + WORKED_EXAMPLE_CLOSE
        out, _ = redact_final_answers(text, support_level=5)
        assert "4/9" not in out
        assert WORKED_EXAMPLE_OPEN not in out

    def test_backward_compatible_signature(self) -> None:
        """الاستدعاء القديم بلا support_level يبقى يعمل (D-113 callers)."""
        from app.services.skills.answer_redaction_skill import redact_final_answers

        out, n = redact_final_answers("إذن P(A)=14/165")
        assert "14/165" not in out and n >= 1

    def test_input_carries_support_level(self) -> None:
        from app.services.skills.answer_redaction_skill import (
            AnswerRedactionInput,
            get_answer_redaction_skill,
        )
        from app.services.skills.doctrine import (
            WORKED_EXAMPLE_CLOSE,
            WORKED_EXAMPLE_OPEN,
        )

        text = WORKED_EXAMPLE_OPEN + "P(A)=4/9" + WORKED_EXAMPLE_CLOSE
        out = get_answer_redaction_skill().redact(AnswerRedactionInput(text=text, support_level=1))
        assert "4/9" in out.redacted_text


# ── 3. الـ doctrine + manifest + registry ─────────────────────────────────────
class TestDoctrineAndRegistry:
    def test_doctrine_versions_bumped(self) -> None:
        from app.services.skills.doctrine import (
            ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
            ANSWER_REDACTION_DOCTRINE_VERSION,
            EXPLANATION_DOCTRINE_VERSION,
            WORKED_EXAMPLE_DOCTRINE_VERSION,
        )

        assert EXPLANATION_DOCTRINE_VERSION == "3.1.0"
        assert ANSWER_REDACTION_DOCTRINE_VERSION == "1.1.0"
        assert ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION == "1.2.0"
        assert WORKED_EXAMPLE_DOCTRINE_VERSION == "1.0.0"

    def test_manifest_entry_consistent(self) -> None:
        from app.services.skills.doctrine import (
            SKILL_DOCTRINE_MANIFEST,
            WORKED_EXAMPLE_DOCTRINE,
            WORKED_EXAMPLE_DOCTRINE_VERSION,
        )

        entry = SKILL_DOCTRINE_MANIFEST["worked_example"]
        assert entry["version"] == WORKED_EXAMPLE_DOCTRINE_VERSION
        assert entry["rules_count"] == len(WORKED_EXAMPLE_DOCTRINE)
        assert entry["consumed_by"]  # no-ZOMBIE

    def test_explanation_anchors_preserved(self) -> None:
        from app.services.skills.doctrine import EXERCISE_EXPLANATION_SYSTEM_PROMPT

        for anchor in ("الإجابة النموذجية", "LaTeX", "حرفياً"):
            assert anchor in EXERCISE_EXPLANATION_SYSTEM_PROMPT
        assert len(EXERCISE_EXPLANATION_SYSTEM_PROMPT) <= 1000

    def test_skill_registered_not_zombie(self) -> None:
        from app.services.skills.registry import get_skill_registry

        reg = get_skill_registry()
        desc = reg.get("worked_example")
        assert desc is not None
        assert desc.consumed_by  # no-ZOMBIE


# ── 4. عقد الواجهة ────────────────────────────────────────────────────────────
class TestUIComponentContract:
    def test_worked_example_card_whitelisted(self) -> None:
        from app.contracts.streaming import KNOWN_UI_COMPONENTS

        assert "worked_example_card" in KNOWN_UI_COMPONENTS

    def test_ui_payload_accepts_worked_example_card(self) -> None:
        from app.contracts.streaming import UIComponentPayload

        payload = UIComponentPayload.model_validate(
            {
                "component": "worked_example_card",
                "props": {"concept_id": "probability", "steps": []},
                "fallback_text": "مثال محلول",
            }
        )
        assert payload.component == "worked_example_card"

    def test_ui_payload_rejects_unknown(self) -> None:
        from pydantic import ValidationError

        from app.contracts.streaming import UIComponentPayload

        with pytest.raises(ValidationError):
            UIComponentPayload.model_validate(
                {"component": "totally_unknown_card", "props": {}, "fallback_text": "x"}
            )
