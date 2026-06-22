"""
D-130 — Socratic Evaluator (active listener) regression tests.

يثبت أن النظام يكسر «الخيانة البيداغوجية» (إعادة طباعة التمرين بدل تقييم إجابة الطالب):
  • Concern 1 — كشف الإجابة بالفعل الكلامي لا بالطول (`is_response_to_socratic`).
  • Concern 2 — ميزانية سقراطية تكيّفية حسب المفهوم/الحالة (`socratic_budget`).
  • المُقيّم (الطبقة 1): hidden goals + next-focus + fallback حتمي + parse JSON محروس.
  • التسليم الرمزي المتدرّج يَنجو من حجب D-113.
  • التوصيل المبكر في chat_with_agent **قبل** الاسترجاع المُفهرَس (لا إعادة طباعة).
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.skills.pedagogical_policy_skill import (
    is_response_to_socratic,
    socratic_budget,
    student_answered,
)
from app.services.skills.socratic_evaluator_skill import (
    HIDDEN_GOALS,
    SocraticEvaluatorSkill,
    _heuristic_understood,
    get_socratic_evaluator_skill,
    hidden_goal_for,
    next_focus_for,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def _q(text: str) -> dict[str, str]:
    return {"role": "assistant", "content": text}


def _a(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


_PENDING_SOCRATIC = [_q("متى تقول إنها نجحت وحقّقت A؟ أعطني مثالاً")]


# ── Concern 1: كشف الإجابة بالفعل الكلامي لا بالطول ───────────────────────────
class TestSpeechActAnswerDetection:
    PENDING = _PENDING_SOCRATIC

    def test_long_brilliant_answer_is_answer(self) -> None:
        # ~11 كلمة — D-129 (≤5 كلمات) كان يفوّتها؛ D-130 يلتقطها.
        msg = "إذا كانوا من نفس اللون فقط و هذا ينطبق على الحمراء و الخضراء فقط"
        assert is_response_to_socratic(msg, self.PENDING) is True
        assert student_answered(msg, self.PENDING) is True

    def test_short_conceptual_answer_is_answer(self) -> None:
        assert is_response_to_socratic("نفس اللون", self.PENDING) is True
        assert is_response_to_socratic("أقل من ثلاثة", self.PENDING) is True

    def test_explicit_new_exercise_request_not_answer(self) -> None:
        assert is_response_to_socratic("اعطني تمرين الدوال العددية", self.PENDING) is False

    def test_topic_switch_not_answer(self) -> None:
        # دالة/معادلة ≠ احتمالات ⇒ ليست إجابة (حارس D-101)
        assert is_response_to_socratic("اعطني تمرين دالة لوغاريتمية", self.PENDING) is False

    def test_no_pending_question_not_answer(self) -> None:
        assert is_response_to_socratic("نفس اللون", [_q("هذا تعريف.")]) is False

    def test_empty_not_answer(self) -> None:
        assert is_response_to_socratic("", self.PENDING) is False


# ── Concern 2: ميزانية سقراطية تكيّفية ────────────────────────────────────────
class TestAdaptiveBudget:
    def test_concept_base(self) -> None:
        assert socratic_budget("numerator") == 2  # مفاهيمي
        assert socratic_budget("ratio") == 2
        assert socratic_budget("color_white") == 1  # بصيرة سريعة
        assert socratic_budget("combinations") == 1

    def test_struggling_student_reduces(self) -> None:
        assert socratic_budget("numerator", support_level=1) == 1
        assert socratic_budget("color_white", support_level=2) == 1  # clamp min

    def test_strong_student_increases(self) -> None:
        assert socratic_budget("numerator", support_level=5) == 3
        assert socratic_budget("ratio", support_level=4) == 3

    def test_repeated_confusion_escalates_faster(self) -> None:
        assert socratic_budget("numerator", confusion_count=3) == 1  # 2-(3-1)=0 → clamp 1

    def test_clamped_to_range(self) -> None:
        for c in ("numerator", "color_white", "ratio", "full_solution"):
            for s in (None, 1, 2, 3, 4, 5):
                for cc in (0, 1, 2, 5):
                    b = socratic_budget(c, s, cc)
                    assert 1 <= b <= 3

    def test_varies_by_concept_and_state(self) -> None:
        budgets = {
            socratic_budget(c, s)
            for c in ("numerator", "color_white", "ratio")
            for s in (None, 1, 5)
        }
        assert len(budgets) > 1  # ليس سقفاً ثابتاً واحداً


# ── المُقيّم (الطبقة 1): hidden goals + next-focus + fallback ──────────────────
class TestEvaluatorMaps:
    def test_hidden_goals_cover_core_concepts(self) -> None:
        for c in ("numerator", "event_meaning", "denominator", "ratio", "color_white"):
            assert c in HIDDEN_GOALS
            assert hidden_goal_for(c)

    def test_hidden_goal_white_impossible_insight(self) -> None:
        goal = hidden_goal_for("numerator")
        assert "البيضاء" in goal and ("مستحيل" in goal or "2" in goal)

    def test_next_focus_ladder(self) -> None:
        assert next_focus_for("numerator") == "denominator"
        assert next_focus_for("event_meaning") == "denominator"
        assert next_focus_for("denominator") == "ratio"
        assert next_focus_for("ratio") is None

    def test_heuristic_understood_on_brilliant_answer(self) -> None:
        msg = "نفس اللون فقط، الحمراء والخضراء، البيضاء مستحيلة"
        assert _heuristic_understood(msg, "numerator") is True
        assert _heuristic_understood(msg, "event_meaning") is True

    def test_heuristic_empty_not_understood(self) -> None:
        assert _heuristic_understood("", "numerator") is False


class TestParseJson:
    def test_clean_json(self) -> None:
        u, e = SocraticEvaluatorSkill._parse_json('{"understood": true, "encouragement": "ممتاز"}')
        assert u is True and e == "ممتاز"

    def test_json_wrapped_in_text(self) -> None:
        raw = 'إليك التقييم: {"understood": false, "encouragement": "قريب"} انتهى.'
        u, e = SocraticEvaluatorSkill._parse_json(raw)
        assert u is False and e == "قريب"

    def test_garbage_returns_none(self) -> None:
        u, _ = SocraticEvaluatorSkill._parse_json("لا أعرف")
        assert u is None


# ── التسليم الرمزي المتدرّج يَنجو من حجب D-113 ────────────────────────────────
class TestSymbolicStepSurvivesRedaction:
    def test_numerator_step_pattern_survives(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        step = (
            "إجابتك في الطريق الصحيح — بما أننا اقتصرنا على الألوان الممكنة، "
            "نحسب الحالات الملائمة:\n\n"
            "- كرة حمراء: C(4,3) = (4×3×2)/(3×2×1) = 4\n"
            "- كرة خضراء: C(5,3) = (5×4×3)/(3×2×1) = 10\n"
            "- كرة بيضاء: مستحيلة (أقل من 3)\n\n"
            "نجمعها: 4 + 10 = 14\n\n"
            "والآن سؤالٌ يقودنا للخطوة التالية: كم عدد كل الطرق الممكنة لسحب 3 كرات من 11؟"
        )
        redacted, count = redact_final_answers(step)
        assert count == 0, f"symbolic step was redacted ({count}×): {redacted!r}"
        assert "= 14" in redacted
        assert "C(4,3) = (4×3×2)/(3×2×1) = 4" in redacted


# ── التوصيل المبكر (لا إعادة طباعة) + registry ────────────────────────────────
class TestWiring:
    def test_capture_precedes_indexed_retrieval(self) -> None:
        src = (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )
        # D-137: مطابقة صيغة الاستدعاء بـ `self.` — متينة على لفّ الأسطر (ruff قد يلفّ الوسائط).
        eval_pos = src.find("self._in_socratic_dialogue(")
        indexed_pos = src.find("self._has_indexed_match(")
        assert eval_pos != -1 and indexed_pos != -1
        assert eval_pos < indexed_pos, "socratic capture must precede indexed-retrieval (D-130)"

    def test_evaluator_methods_wired(self) -> None:
        src = (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )
        for needle in (
            "get_socratic_evaluator_skill",
            "_stream_socratic_evaluation",
            "_build_symbolic_step",
        ):
            assert needle in src

    def test_no_directive_prepend_regression(self) -> None:
        # D-117 invariant: لا يُسبَق التوجيه التربوي للسؤال.
        src = (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )
        assert 'f"[توجيه تربوي]' not in src

    def test_registry_registers_skill(self) -> None:
        from app.services.skills.registry import get_skill_registry

        d = get_skill_registry().get("socratic_evaluator")
        assert d is not None
        assert d.status == "ACTIVE"
        assert d.consumed_by  # no ZOMBIE
        assert d.primary_method == "evaluate"

    def test_manifest_consistent(self) -> None:
        from app.services.skills.doctrine import (
            SKILL_DOCTRINE_MANIFEST,
            SOCRATIC_EVALUATOR_DOCTRINE,
            SOCRATIC_EVALUATOR_DOCTRINE_VERSION,
        )

        entry = SKILL_DOCTRINE_MANIFEST["socratic_evaluator"]
        assert entry["version"] == SOCRATIC_EVALUATOR_DOCTRINE_VERSION
        assert entry["rules_count"] == len(SOCRATIC_EVALUATOR_DOCTRINE)


class TestEvaluatorSingleton:
    def test_singleton(self) -> None:
        assert get_socratic_evaluator_skill() is get_socratic_evaluator_skill()


def test_no_final_fraction_in_hidden_goals() -> None:
    """الأهداف المستترة لا تحوي النتيجة النهائية (14/165) — الطبقة 1 لا تكشف."""
    joined = " ".join(HIDDEN_GOALS.values())
    assert not re.search(r"14\s*/\s*165|56\s*/\s*165", joined)
