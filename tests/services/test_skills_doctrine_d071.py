"""
D-071 (2026-05-19) — Skills Doctrine Integration Tests.

يتحقق من:
1. `build_exercise_explanation_prompt()` تبني prompt صحيح من الـ doctrine.
2. `EXERCISE_EXPLANATION_SYSTEM_PROMPT` يحترم قيود D-067 (< 1000 حرف، لا box-drawing).
3. `local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT` مشتق من doctrine مباشرة.
4. الـ prompt يحتوي على الـ anchors الإلزامية من EXPLANATION_DOCTRINE.
5. تكامل CONTENT_INVOCATION_DOCTRINE مع BACExerciseSkill.
6. تكامل MODEL_ANSWER_EXPLANATION_DOCTRINE مع الـ prompt.
7. عدم وجود box-drawing chars في أي prompt.
8. SKILL_DOCTRINE_MANIFEST يعكس الـ doctrines الجديدة.
"""

from __future__ import annotations

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# 1. build_exercise_explanation_prompt
# ─────────────────────────────────────────────────────────────────────────────


class TestBuildExerciseExplanationPrompt:
    """يتحقق من دالة بناء الـ prompt من الـ doctrine."""

    def test_returns_string(self) -> None:
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        result = build_exercise_explanation_prompt()
        assert isinstance(result, str)
        assert len(result) > 50

    def test_under_1000_chars(self) -> None:
        """D-067: prompt > 1000 حرف يُسبب reasoning-mode في النماذج المجانية."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert len(prompt) < 1000, (
            f"Prompt is {len(prompt)} chars — exceeds D-067 limit of 1000. "
            "Free models enter reasoning-mode with long prompts."
        )

    def test_no_box_drawing_chars(self) -> None:
        """D-067: box-drawing chars (U+2500–U+257F) تُربك tokenizers النماذج المجانية."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        box_chars = [c for c in prompt if "\u2500" <= c <= "\u257f"]
        assert not box_chars, (
            f"Prompt contains {len(box_chars)} box-drawing chars: "
            f"{set(box_chars)} — forbidden by D-067."
        )

    def test_contains_arabic(self) -> None:
        """الـ prompt يجب أن يكون بالعربية."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        arabic_chars = [c for c in prompt if "\u0600" <= c <= "\u06ff"]
        assert len(arabic_chars) > 20, "Prompt has too few Arabic characters."

    def test_contains_model_answer_anchor(self) -> None:
        """الإجابة النموذجية يجب أن تُذكر — قاعدة الاعتماد على النموذج."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert "الإجابة النموذجية" in prompt

    def test_contains_latex_anchor(self) -> None:
        """LaTeX إلزامي في كل شرح رياضي."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert "LaTeX" in prompt

    def test_contains_no_verbatim_copy_anchor(self) -> None:
        """لا نسخ حرفي من الإجابة النموذجية."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert "حرفياً" in prompt

    def test_contains_methodology_section(self) -> None:
        """منهجية الشرح يجب أن تكون موجودة."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        prompt = build_exercise_explanation_prompt()
        assert "منهجية" in prompt or "مرحلة" in prompt

    def test_deterministic(self) -> None:
        """الدالة حتمية — نفس المدخلات = نفس المخرجات."""
        from app.services.skills.doctrine import build_exercise_explanation_prompt

        assert build_exercise_explanation_prompt() == build_exercise_explanation_prompt()


# ─────────────────────────────────────────────────────────────────────────────
# 2. EXERCISE_EXPLANATION_SYSTEM_PROMPT constant
# ─────────────────────────────────────────────────────────────────────────────


class TestExerciseExplanationSystemPrompt:
    """يتحقق من الثابت المُصدَّر."""

    def test_exported_from_doctrine(self) -> None:
        from app.services.skills import doctrine as doc_mod

        assert hasattr(doc_mod, "EXERCISE_EXPLANATION_SYSTEM_PROMPT")

    def test_equals_build_result(self) -> None:
        """الثابت يجب أن يساوي نتيجة الدالة — single source of truth."""
        from app.services.skills.doctrine import (
            EXERCISE_EXPLANATION_SYSTEM_PROMPT,
            build_exercise_explanation_prompt,
        )

        assert build_exercise_explanation_prompt() == EXERCISE_EXPLANATION_SYSTEM_PROMPT

    def test_in_all_list(self) -> None:
        """EXERCISE_EXPLANATION_SYSTEM_PROMPT مُدرَج في __all__."""
        import app.services.skills.doctrine as mod

        assert "EXERCISE_EXPLANATION_SYSTEM_PROMPT" in mod.__all__

    def test_build_function_in_all_list(self) -> None:
        """build_exercise_explanation_prompt مُدرَجة في __all__."""
        import app.services.skills.doctrine as mod

        assert "build_exercise_explanation_prompt" in mod.__all__


# ─────────────────────────────────────────────────────────────────────────────
# 3. local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT مشتق من doctrine
# ─────────────────────────────────────────────────────────────────────────────


class TestLocalGraphPromptBinding:
    """D-071: local_graph يجب أن يستورد الـ prompt من doctrine — لا تعريف محلي."""

    def test_local_graph_imports_doctrine(self) -> None:
        """local_graph.py يستورد من doctrine module."""
        from pathlib import Path

        src = (
            Path(__file__).parent.parent.parent / "app" / "services" / "chat" / "local_graph.py"
        ).read_text(encoding="utf-8")
        assert "from app.services.skills.doctrine import" in src, (
            "local_graph.py must import from doctrine module (D-071)."
        )

    def test_local_graph_uses_doctrine_prompt(self) -> None:
        """local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT مُعيَّن من doctrine."""
        from pathlib import Path

        src = (
            Path(__file__).parent.parent.parent / "app" / "services" / "chat" / "local_graph.py"
        ).read_text(encoding="utf-8")
        assert "EXERCISE_EXPLANATION_SYSTEM_PROMPT" in src, (
            "local_graph.py must reference EXERCISE_EXPLANATION_SYSTEM_PROMPT (D-071)."
        )

    def test_local_graph_prompt_equals_doctrine(self) -> None:
        """قيمة الـ prompt في local_graph تساوي قيمة doctrine."""
        from app.services.chat.local_graph import _EXERCISE_EXPLANATION_SYSTEM_PROMPT
        from app.services.skills.doctrine import EXERCISE_EXPLANATION_SYSTEM_PROMPT

        assert _EXERCISE_EXPLANATION_SYSTEM_PROMPT == EXERCISE_EXPLANATION_SYSTEM_PROMPT, (
            "local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT has drifted from "
            "doctrine.EXERCISE_EXPLANATION_SYSTEM_PROMPT (D-071)."
        )

    def test_local_graph_prompt_under_1000_chars(self) -> None:
        """D-067: الـ prompt في local_graph < 1000 حرف."""
        from app.services.chat.local_graph import _EXERCISE_EXPLANATION_SYSTEM_PROMPT

        assert len(_EXERCISE_EXPLANATION_SYSTEM_PROMPT) < 1000

    def test_local_graph_prompt_no_box_drawing(self) -> None:
        """D-067: لا box-drawing chars في الـ prompt."""
        from app.services.chat.local_graph import _EXERCISE_EXPLANATION_SYSTEM_PROMPT

        box_chars = [c for c in _EXERCISE_EXPLANATION_SYSTEM_PROMPT if "\u2500" <= c <= "\u257f"]
        assert not box_chars


# ─────────────────────────────────────────────────────────────────────────────
# 4. CONTENT_INVOCATION_DOCTRINE
# ─────────────────────────────────────────────────────────────────────────────


class TestContentInvocationDoctrine:
    """يتحقق من doctrine استدعاء المحتوى."""

    def test_has_7_steps(self) -> None:
        """CONTENT_INVOCATION_DOCTRINE يجب أن يحتوي على 7 خطوات."""
        from app.services.skills.doctrine import CONTENT_INVOCATION_DOCTRINE

        assert len(CONTENT_INVOCATION_DOCTRINE) == 7

    def test_step1_intent_classification(self) -> None:
        """الخطوة 1: تحديد النية."""
        from app.services.skills.doctrine import CONTENT_INVOCATION_DOCTRINE

        assert "النية" in CONTENT_INVOCATION_DOCTRINE[0] or "نية" in CONTENT_INVOCATION_DOCTRINE[0]

    def test_step4_single_file_load(self) -> None:
        """الخطوة 4: تحميل ملف واحد فقط — لا scan على المجلد."""
        from app.services.skills.doctrine import CONTENT_INVOCATION_DOCTRINE

        step4 = CONTENT_INVOCATION_DOCTRINE[3]
        assert "ملف" in step4 or "file" in step4.lower()

    def test_step7_context_injection(self) -> None:
        """الخطوة 7: حقن السياق للـ LLM فقط — لا إرسال للمستخدم."""
        from app.services.skills.doctrine import CONTENT_INVOCATION_DOCTRINE

        step7 = CONTENT_INVOCATION_DOCTRINE[6]
        assert "LLM" in step7 or "سياق" in step7

    def test_version_set(self) -> None:
        from app.services.skills.doctrine import CONTENT_INVOCATION_DOCTRINE_VERSION

        assert CONTENT_INVOCATION_DOCTRINE_VERSION == "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# 5. MODEL_ANSWER_EXPLANATION_DOCTRINE
# ─────────────────────────────────────────────────────────────────────────────


class TestModelAnswerExplanationDoctrine:
    """يتحقق من doctrine شرح الإجابة النموذجية."""

    def test_has_phases(self) -> None:
        """يجب أن يحتوي على مراحل الشرح."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        assert len(MODEL_ANSWER_EXPLANATION_DOCTRINE) >= 5

    def test_understanding_phase(self) -> None:
        """مرحلة الفهم موجودة."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        combined = " ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)
        assert "فهم" in combined or "يطلب" in combined

    def test_verification_phase(self) -> None:
        """مرحلة التحقق موجودة."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        combined = " ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)
        assert "تحقق" in combined

    def test_interpretation_phase(self) -> None:
        """مرحلة التفسير موجودة."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        combined = " ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)
        assert "تفسير" in combined or "تعني" in combined

    def test_math_latex_rule(self) -> None:
        """قاعدة LaTeX للرياضيات موجودة."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        combined = " ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)
        assert "LaTeX" in combined or "boxed" in combined

    def test_physics_rule(self) -> None:
        """قاعدة الفيزياء موجودة."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        combined = " ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)
        assert "فيزياء" in combined or "وحدة" in combined

    def test_adaptation_rule(self) -> None:
        """قاعدة التكيف مع مستوى الطالب موجودة."""
        from app.services.skills.doctrine import MODEL_ANSWER_EXPLANATION_DOCTRINE

        combined = " ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)
        assert "لم أفهم" in combined or "أعِد" in combined or "أبسط" in combined


# ─────────────────────────────────────────────────────────────────────────────
# 6. STEP_BY_STEP_EXPLANATION_RULES
# ─────────────────────────────────────────────────────────────────────────────


class TestStepByStepExplanationRules:
    """يتحقق من قواعد الشرح خطوة بخطوة."""

    def test_has_rules(self) -> None:
        from app.services.skills.doctrine import STEP_BY_STEP_EXPLANATION_RULES

        assert len(STEP_BY_STEP_EXPLANATION_RULES) >= 7

    def test_numbering_rule(self) -> None:
        """الترقيم إلزامي."""
        from app.services.skills.doctrine import STEP_BY_STEP_EXPLANATION_RULES

        combined = " ".join(STEP_BY_STEP_EXPLANATION_RULES)
        assert "ترقيم" in combined or "الخطوة" in combined

    def test_transition_words(self) -> None:
        """كلمات الانتقال موجودة."""
        from app.services.skills.doctrine import STEP_BY_STEP_EXPLANATION_RULES

        combined = " ".join(STEP_BY_STEP_EXPLANATION_RULES)
        assert "إذن" in combined or "ومنه" in combined

    def test_conclusion_rule(self) -> None:
        """الخاتمة الإلزامية موجودة."""
        from app.services.skills.doctrine import STEP_BY_STEP_EXPLANATION_RULES

        combined = " ".join(STEP_BY_STEP_EXPLANATION_RULES)
        assert "الخلاصة" in combined or "خلاصة" in combined


# ─────────────────────────────────────────────────────────────────────────────
# 7. SKILL_DOCTRINE_MANIFEST — يعكس الـ doctrines الجديدة
# ─────────────────────────────────────────────────────────────────────────────


class TestSkillDoctrineManifest:
    """يتحقق من أن الـ manifest يعكس كل الـ doctrines."""

    def test_has_content_invocation_entry(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        assert "content_invocation" in SKILL_DOCTRINE_MANIFEST

    def test_has_model_answer_explanation_entry(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        assert "model_answer_explanation" in SKILL_DOCTRINE_MANIFEST

    def test_has_step_by_step_entry(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        assert "step_by_step_explanation" in SKILL_DOCTRINE_MANIFEST

    def test_has_skill_invocation_protocol_entry(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        assert "skill_invocation_protocol" in SKILL_DOCTRINE_MANIFEST

    def test_all_entries_have_version_and_rules_count(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        for key, entry in SKILL_DOCTRINE_MANIFEST.items():
            assert "version" in entry, f"Manifest entry '{key}' missing 'version'"
            assert "rules_count" in entry, f"Manifest entry '{key}' missing 'rules_count'"
            assert isinstance(entry["rules_count"], int), (
                f"Manifest entry '{key}' rules_count must be int"
            )
            assert entry["rules_count"] > 0, (
                f"Manifest entry '{key}' has 0 rules — doctrine is empty"
            )

    def test_manifest_counts_match_actual(self) -> None:
        """rules_count في الـ manifest يطابق الطول الفعلي للـ tuple."""
        from app.services.skills.doctrine import (
            CONTENT_INVOCATION_DOCTRINE,
            CONTENT_INVOCATION_DOCTRINE_VERSION,
            MODEL_ANSWER_EXPLANATION_DOCTRINE,
            MODEL_ANSWER_EXPLANATION_VERSION,
            SKILL_DOCTRINE_MANIFEST,
            STEP_BY_STEP_EXPLANATION_RULES,
            STEP_BY_STEP_EXPLANATION_VERSION,
        )

        checks = [
            (
                "content_invocation",
                CONTENT_INVOCATION_DOCTRINE_VERSION,
                len(CONTENT_INVOCATION_DOCTRINE),
            ),
            (
                "model_answer_explanation",
                MODEL_ANSWER_EXPLANATION_VERSION,
                len(MODEL_ANSWER_EXPLANATION_DOCTRINE),
            ),
            (
                "step_by_step_explanation",
                STEP_BY_STEP_EXPLANATION_VERSION,
                len(STEP_BY_STEP_EXPLANATION_RULES),
            ),
        ]
        for key, ver, count in checks:
            entry = SKILL_DOCTRINE_MANIFEST[key]
            assert entry["version"] == ver, f"{key}: version mismatch"
            assert entry["rules_count"] == count, f"{key}: rules_count mismatch"


# ─────────────────────────────────────────────────────────────────────────────
# 8. BACSkillExplanationOutput.methodology_handle
# ─────────────────────────────────────────────────────────────────────────────


class TestMethodologyHandle:
    """يتحقق من أن methodology_handle يحمل إصدار الـ doctrine الحالي."""

    def test_default_handle_matches_version(self) -> None:
        from app.services.skills.bac_exercise_skill import BACSkillExplanationOutput
        from app.services.skills.doctrine import EXPLANATION_DOCTRINE_VERSION

        # نبني instance بحد أدنى من الحقول
        try:
            from app.services.capabilities.exercise_retrieval import ExerciseEntry

            entry = ExerciseEntry(
                file_path="test.md",
                year=2016,
                session=1,
                subject_number=1,
                exercise_number=1,
                branch="math",
                topics=("test",),
                tags=("test",),
            )
            out = BACSkillExplanationOutput(
                matched_entry=entry,
                display_content="d",
                full_content="f",
            )
            expected = f"explanation_doctrine_v{EXPLANATION_DOCTRINE_VERSION}"
            assert out.methodology_handle == expected, (
                f"methodology_handle={out.methodology_handle!r} != {expected!r}"
            )
        except (ImportError, TypeError):
            pytest.skip("ExerciseEntry not constructible in this env")

    def test_handle_format(self) -> None:
        """الـ handle يجب أن يتبع نمط explanation_doctrine_vX.Y.Z."""
        import re

        from app.services.skills.doctrine import (
            EXPLANATION_DOCTRINE_VERSION,
            build_exercise_explanation_prompt,
        )

        handle = f"explanation_doctrine_v{EXPLANATION_DOCTRINE_VERSION}"
        assert re.match(r"explanation_doctrine_v\d+\.\d+\.\d+", handle)
        # الـ prompt يُبنى بنجاح (لا exception)
        prompt = build_exercise_explanation_prompt()
        assert len(prompt) > 0
