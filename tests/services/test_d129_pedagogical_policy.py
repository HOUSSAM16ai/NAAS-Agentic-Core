"""
D-129 — Pedagogical Policy Engine (الطبقة 4) regression tests.

يثبت أن السياسة تكسر «حلقة الاستجواب اللانهائي» (الكارثة بعد D-128):
  • كشف إجابات الطالب القصيرة («نفس اللون»/«2»/«أقل من ثلاثة»/«التوافيق»).
  • السقراطية محدودة بميزانية (MAX_SOCRATIC) ⇒ بعدها حلّ رمزي.
  • الاعتراف بالإجابة عند student_answered.
  • القرار حتمي تماماً (نفس المدخلات ⇒ نفس المخرجات).
  • مخرج _build_symbolic_reveal يَنجو من حجب D-113.
  • التوصيل في orchestrator_client (لا ZOMBIE) + اتّساق الـ manifest.
"""

from __future__ import annotations

from pathlib import Path

from app.services.skills.pedagogical_policy_skill import (
    MAX_SOCRATIC,
    PedagogicalPolicySkill,
    PolicyInput,
    PolicyOutput,
    count_socratic_questions,
    definition_already_given,
    is_answer_message,
    student_answered,
)

ROOT = Path(__file__).resolve().parent.parent.parent


def _q(text: str) -> dict[str, str]:
    return {"role": "assistant", "content": text}


def _a(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


# ── الكاشف: إجابة قصيرة مقابل سؤال جديد ──────────────────────────────────────
class TestIsAnswerMessage:
    def test_short_answers_detected(self) -> None:
        # الإجابات الحقيقية من الكارثة الحيّة
        assert is_answer_message("نفس اللون") is True
        assert is_answer_message("2") is True
        assert is_answer_message("أقل من ثلاثة") is True
        assert is_answer_message("التوافيق") is True
        assert is_answer_message("١٤") is True  # أرقام عربية

    def test_questions_not_answers(self) -> None:
        assert is_answer_message("كيف نحسب") is False
        assert is_answer_message("ما هو البسط") is False
        assert is_answer_message("لماذا نجمع") is False
        assert is_answer_message("هل هذا صحيح؟") is False
        assert is_answer_message("واش راه 14") is False

    def test_empty_and_long_not_answers(self) -> None:
        assert is_answer_message("") is False
        assert is_answer_message("   ") is False
        # > 5 كلمات ⇒ ليس إجابة قصيرة بل شرح/سؤال مطوّل
        assert is_answer_message("أعتقد أن الجواب هو نفس اللون لكنني لست متأكداً") is False


class TestCountSocraticQuestions:
    def test_counts_assistant_questions(self) -> None:
        history = [
            _a("لم أفهم"),
            _q("ما الذي يجمع الكرات الثلاث؟"),
            _a("نفس اللون"),
            _q("كم كرة بيضاء لدينا؟"),
        ]
        assert count_socratic_questions(history) == 2

    def test_ignores_user_and_non_questions(self) -> None:
        history = [_q("هذا تعريف."), _a("ما هذا؟"), _q("لنبدأ.")]
        assert count_socratic_questions(history) == 0

    def test_none_safe(self) -> None:
        assert count_socratic_questions(None) == 0


class TestStudentAnswered:
    def test_answer_after_question(self) -> None:
        history = [_q("ما اللون المشترك؟")]
        assert student_answered("نفس اللون", history) is True

    def test_no_prior_question(self) -> None:
        history = [_q("إليك التعريف.")]
        assert student_answered("نفس اللون", history) is False

    def test_question_after_question_not_answer(self) -> None:
        history = [_q("كم كرة حمراء؟")]
        assert student_answered("لماذا نسأل هذا؟", history) is False


class TestDefinitionAlreadyGiven:
    def test_detects_definition_marker(self) -> None:
        history = [_q("## ما هو البسط\nالبسط هو عدد الطرق الملائمة.")]
        assert definition_already_given(history) is True

    def test_no_definition(self) -> None:
        history = [_q("ما اللون المشترك؟"), _a("نفس اللون")]
        assert definition_already_given(history) is False


# ── القرار الحتمي للسياسة ─────────────────────────────────────────────────────
class TestPolicyDecision:
    def setup_method(self) -> None:
        self.skill = PedagogicalPolicySkill()

    def _decide(self, question: str, history: list[dict[str, str]]) -> PolicyOutput:
        return self.skill.decide(
            PolicyInput(concept="numerator", question=question, history=history)
        )

    def test_first_contact_gets_definition(self) -> None:
        out = self._decide("لم أفهم احتمال الحادثة A", history=[])
        assert out.action == "definition"
        assert out.acknowledge is False

    def test_answer_gets_socratic_with_acknowledge(self) -> None:
        # المساعد قدّم تعريفاً وسأل، الطالب أجاب «نفس اللون»
        history = [_q("## ما هو البسط\nالبسط عدد الطرق. ما اللون المشترك؟")]
        out = self._decide("نفس اللون", history)
        assert out.action == "socratic"
        assert out.acknowledge is True
        assert out.student_answered is True

    def test_budget_exhausted_triggers_symbolic_reveal(self) -> None:
        # سؤالان سقراطيان سابقان ⇒ نفاد الميزانية ⇒ حلّ رمزي
        history = [
            _q("ما اللون المشترك؟"),
            _a("نفس اللون"),
            _q("كم طريقة لاختيار 3 حمراء؟"),
            _a("لا أعرف"),
        ]
        out = self._decide("أقل من ثلاثة", history)
        assert out.socratic_count >= MAX_SOCRATIC
        assert out.action == "symbolic_reveal"
        assert out.acknowledge is True  # أجاب بعد سؤال ⇒ اعتراف

    def test_deterministic(self) -> None:
        history = [_q("ما اللون المشترك؟")]
        a = self._decide("نفس اللون", history)
        b = self._decide("نفس اللون", history)
        assert a.model_dump() == b.model_dump()


class TestCatastropheSequence:
    """السلسلة الكارثية الحرفية: استجواب لا نهائي ⇒ تدرّج مُنتهٍ."""

    def test_full_sequence_terminates(self) -> None:
        skill = PedagogicalPolicySkill()
        history: list[dict[str, str]] = []
        actions: list[str] = []

        steps = [
            ("لم أفهم احتمال الحادثة A", "## ما هو البسط\nالبسط هو عدد الطرق. ما اللون المشترك؟"),
            ("نفس اللون", "أحسنت. والآن كم طريقة لاختيار 3 حمراء؟"),
            ("أقل من ثلاثة", "إجابتك في الطريق الصحيح."),
        ]
        for question, assistant_reply in steps:
            out = skill.decide(
                PolicyInput(concept="numerator", question=question, history=list(history))
            )
            actions.append(out.action)
            history.append(_a(question))
            history.append(_q(assistant_reply))

        # تعريف → سقراطي → حلّ رمزي (لا استجواب لا نهائي)
        assert actions[0] == "definition"
        assert actions[1] == "socratic"
        assert actions[2] == "symbolic_reveal"
        # ضمان عدم وجود حلقة: الوصول لحلّ رمزي خلال 3 خطوات
        assert "symbolic_reveal" in actions


# ── حماية D-113: الحلّ الرمزي يَنجو من حجب الإجابة ────────────────────────────
class TestSymbolicRevealSurvivesRedaction:
    def test_reveal_pattern_survives(self) -> None:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        # نمط مخرج _build_symbolic_reveal (يَنجو: «(» بعد «=»، لا كلمة خلاصة).
        reveal = (
            "إجابتك في الطريق الصحيح — لنُكمل معاً خطوة بخطوة حتى النهاية:\n\n"
            "**الحالات الملائمة** (3 كرات من نفس اللون) — لكل لون:\n\n"
            "- كرة حمراء (العدد 4): C(4,3) = (4×3×2)/(3×2×1) = 4\n"
            "- كرة خضراء (العدد 5): C(5,3) = (5×4×3)/(3×2×1) = 10\n"
            "- كرة بيضاء (العدد 2): مستحيلة (أقل من 3)\n\n"
            "نجمع الحالات الممكنة فقط: 4 + 10 = 14\n\n"
            "**كل الطرق الممكنة** لسحب 3 من 11:\n\n"
            "C(11,3) = (11×10×9)/(3×2×1) = 165\n\n"
            "فاحتمال الحادثة A هو 14 من كل 165."
        )
        redacted, count = redact_final_answers(reveal)
        assert count > 0, f"reveal was redacted ({count}×): {redacted!r}"
        assert "14 من كل 165" not in redacted
        assert "C(4,3) = (4×3×2)/(3×2×1) = 4" not in redacted


# ── التوصيل + الـ manifest (لا ZOMBIE) ────────────────────────────────────────
class TestWiringAndManifest:
    def test_orchestrator_client_wires_policy(self) -> None:
        src = (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )
        assert "get_pedagogical_policy_skill" in src
        assert "_build_symbolic_reveal" in src
        # القرار يفرّع على الأفعال الثلاثة
        assert 'action == "symbolic_reveal"' in src
        assert 'action == "socratic"' in src

    def test_manifest_consistent(self) -> None:
        from app.services.skills.doctrine import (
            PEDAGOGICAL_POLICY_DOCTRINE,
            PEDAGOGICAL_POLICY_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )

        entry = SKILL_DOCTRINE_MANIFEST["pedagogical_policy"]
        assert entry["version"] == PEDAGOGICAL_POLICY_DOCTRINE_VERSION
        assert entry["rules_count"] == len(PEDAGOGICAL_POLICY_DOCTRINE)

    def test_registry_registers_skill(self) -> None:
        from app.services.skills.registry import get_skill_registry

        d = get_skill_registry().get("pedagogical_policy")
        assert d is not None
        assert d.status == "ACTIVE"
        assert d.consumed_by  # no ZOMBIE
        assert d.primary_method == "decide"
