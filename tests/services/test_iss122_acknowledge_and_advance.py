from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

"""
ISS-122 (D-155) — «الاعتراف والتقدّم»: حلقة تربوية تقرأ الطالب فعلاً.

الكارثة الحيّة (transcript، post-D-154):
1. «هل هي 14 من 165» (الإجابة الصحيحة!) ⇒ أُعيد سؤال ما أُجيب للتو — الإجابة
   الرقمية كانت غير مرئية لكل طبقات التحقّق (ألوان فقط).
2. «لم افهم العلاقة بين 14 و 165» / «لماذا حصلنا على 14 و 165» ⇒ ابتلعها
   الاعتراض السقراطي وسقطت في سُلّم بدائل أصمّ — D-125 لا يُبلَغ.
3. «كيف احل السؤال الأول» ⇒ حساب البسط كاملاً بلا سؤال تشخيصي واحد.
4. الـ reveal (superset) كان أول بدائل السُّلّم ⇒ تكرار مُقنَّع.
"""

from app.infrastructure.clients.orchestrator_client import OrchestratorClient

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _combo() -> SimpleNamespace:
    return SimpleNamespace(
        n=11,
        k=3,
        total_combinations=165,
        same_group_favorable=14,
        groups=[
            SimpleNamespace(label="كرة حمراء", count=4, is_possible=True, favorable_combinations=4),
            SimpleNamespace(
                label="كرة بيضاء", count=2, is_possible=False, favorable_combinations=0
            ),
            SimpleNamespace(
                label="كرة خضراء", count=5, is_possible=True, favorable_combinations=10
            ),
        ],
    )


def _client_src() -> str:
    return (_REPO_ROOT / "app" / "infrastructure" / "clients" / "orchestrator_client.py").read_text(
        encoding="utf-8"
    )


class TestNumericVerification:
    """Fix 1: الحقيقة الرمزية تحكم إجابة الطالب الرقمية (الأرقام من combo حصراً)."""

    @pytest.mark.parametrize(
        "answer",
        ["هل هي 14 من 165", "هي 14 على 165", "14/165", "الجواب 14 و 165", "١٤ من ١٦٥"],
    )
    def test_final_ratio_recognized_any_phrasing(self, answer):
        assert OrchestratorClient._verify_numeric_answer(answer, _combo(), "ratio") == "final_ratio"

    def test_final_ratio_recognized_even_without_pending(self):
        # الطالب يركّب النسبة النهائية في أي لحظة ⇒ تُعترف.
        assert (
            OrchestratorClient._verify_numeric_answer("هي 14 على 165", _combo(), None)
            == "final_ratio"
        )

    def test_denominator_step_correct(self):
        assert (
            OrchestratorClient._verify_numeric_answer("165", _combo(), "denominator")
            == "step_correct"
        )

    def test_direction_same_thing_with_11(self):
        # الدور 4 في الترانسكريبت: «نفس الشئ مع 11» — اتجاه صحيح.
        assert (
            OrchestratorClient._verify_numeric_answer("نفس الشئ مع 11", _combo(), "denominator")
            == "direction"
        )

    def test_numerator_step_correct(self):
        assert OrchestratorClient._verify_numeric_answer("14", _combo(), None) == "step_correct"
        assert (
            OrchestratorClient._verify_numeric_answer("4 و 10", _combo(), "numerator")
            == "step_correct"
        )

    def test_wrong_ratio_left_to_evaluator(self):
        # إجابة خاطئة («20 من 165») ⇒ None — تُترك للمُقيّم (لا اعتراف زائف).
        assert OrchestratorClient._verify_numeric_answer("20 من 165", _combo(), "ratio") is None

    def test_no_numbers_returns_none(self):
        assert OrchestratorClient._verify_numeric_answer("الحمراء والخضراء", _combo(), None) is None


class TestPendingFocusDerivation:
    """Fix 1: السؤال المعلّق يُشتق من قوالبنا في أحدث رسالة مساعد (بلا حالة جديدة)."""

    def _hist(self, assistant_text: str) -> list[dict[str, str]]:
        return [
            {"role": "user", "content": "كيف احل السؤال الأول"},
            {"role": "assistant", "content": assistant_text},
        ]

    def test_numerator_step_pends_denominator(self):
        step = OrchestratorClient._build_symbolic_step(_combo(), None)
        assert OrchestratorClient._pending_focus_from_history(self._hist(step)) == "denominator"

    def test_ratio_step_pends_ratio(self):
        step = OrchestratorClient._build_symbolic_step(_combo(), "ratio")
        assert OrchestratorClient._pending_focus_from_history(self._hist(step)) == "ratio"

    def test_generation_prompt_pends_ratio(self):
        gen = (
            "أنت تملك الآن كل المعطيات — جرّب بنفسك: ركّب البسط على المقام، "
            "وأخبرني ما قيمة P(A) التي حصلت عليها، وسأخبرك إن أصبت."
        )
        assert OrchestratorClient._pending_focus_from_history(self._hist(gen)) == "ratio"

    def test_diagnostic_probe_pends_colors(self):
        probe = OrchestratorClient._build_diagnostic_probe(_combo())
        assert OrchestratorClient._pending_focus_from_history(self._hist(probe)) == "colors"

    def test_markers_survive_redaction_of_saved_copy(self):
        # النسخة المحفوظة تمرّ بحجب D-113 (أرقام ⇒ «؟») — قوالب الأسئلة بلا أرقام
        # حاسمة فتبقى قابلة للاشتقاق.
        from app.services.skills.answer_redaction_skill import redact_final_answers

        step = OrchestratorClient._build_symbolic_step(_combo(), None)
        redacted, _ = redact_final_answers(step, 5)
        assert OrchestratorClient._pending_focus_from_history(self._hist(redacted)) == "denominator"


class TestAcknowledgeAndAdvance:
    """Fix 2: الإجابة النهائية الصحيحة ⇒ اعتراف صريح + تقدّم للحادثة B (لا إعادة سؤال)."""

    def test_confirmation_text_present_and_advances(self):
        src = _client_src()
        assert "أحسنت! ✅ إجابتك صحيحة تماماً" in src
        seg = src.split("أحسنت! ✅ إجابتك صحيحة تماماً", 1)[1][:600]
        assert "الحادثة B" in seg  # التقدّم للسؤال الفرعي التالي
        assert "متى يكون جداء ثلاثة أعداد فردياً" in seg  # سؤال تشخيصي واحد

    def test_confirmation_survives_redaction(self):
        from app.services.skills.answer_redaction_skill import redact_final_answers

        text = (
            "أحسنت! ✅ إجابتك صحيحة تماماً — ركّبت احتمال الحادثة A بنفسك: "
            "الحالات الملائمة على كل الحالات الممكنة.\n\n"
            "ننتقل للسؤال التالي في التمرين — **الحادثة B**: جداء الأرقام "
            "عدد فردي. قبل أي حساب، سؤال واحد: متى يكون جداء ثلاثة أعداد فردياً؟"
        )
        redacted, n_redactions = redact_final_answers(text, 5)
        assert n_redactions == 0 and redacted == text

    def test_numeric_verdict_bypasses_dialogue_manager(self):
        # الحكم الرقمي الحتمي نهائي — الـ DM لا يُعيد تشكيله (وإلا استبدل التأكيد بخطوة).
        src = _client_src()
        assert "self._semantic_tutor_enabled() and _numeric is None and result is not None" in src

    def test_partial_step_advances_to_next_unanswered(self):
        src = _client_src()
        seg = src.split('elif _numeric in ("step_correct", "direction"):', 1)
        assert len(seg) == 2, "partial-step acknowledge branch missing"
        tail = seg[1][:700]
        assert '_build_symbolic_step(combo, "ratio", acknowledge=True)' in tail
        assert "أحسنت — هذا هو عدد الحالات الملائمة" in tail


class TestConceptualEscapesSocratic:
    """Fix 3: سؤال مفاهيمي/استفهامي أثناء الحوار ⇒ D-125، ليس إجابةً تُقيَّم."""

    def test_transcript_questions_detected_conceptual(self):
        assert OrchestratorClient._detect_conceptual_question("لم افهم العلاقة بين 14 و 165")
        assert OrchestratorClient._detect_conceptual_question("لماذا حصلنا على 14 و 165")

    def test_socratic_gate_excludes_conceptual_and_interrogative(self):
        src = _client_src()
        gate = src.split("self._in_socratic_dialogue(question, history_messages)\n", 1)
        assert len(gate) == 2
        head = gate[1][:400]
        assert "_detect_conceptual_question(question)" in head
        assert "_QUESTION_OPENERS_NOT_ANSWERS" in head

    def test_hal_is_still_an_answer_opener(self):
        # «هل هي 14 من 165» إجابة تطلب تأكيداً — «هل» ليست في بادئات الأسئلة.
        assert "هل" not in OrchestratorClient._QUESTION_OPENERS_NOT_ANSWERS

    def test_conceptual_short_circuits_inside_block(self):
        # داخل كتلة D-124: المفاهيمي يذهب لشرح العلاقة مباشرة (قبل حالة الفهم/السياسة).
        src = _client_src()
        seg = src.split("# D-127: الاستجابة المدفوعة بالمفهوم أولاً", 1)[1][:900]
        assert "if _conceptual:" in seg
        assert "_build_probability_direct_explanation(question, history_messages)" in seg


class TestDiagnosisFirst:
    """Fix 5: «التشخيص قبل الشرح» — probe واحد بلا قيم محسوبة، ثم انتظار."""

    def test_probe_has_no_computed_values(self):
        probe = OrchestratorClient._build_diagnostic_probe(_combo())
        assert "C_" not in probe and "=" not in probe and "165" not in probe and "14" not in probe
        assert probe.rstrip().endswith("؟")
        # يعرض التركيبة الخام فقط (معطيات التمرين، ليست نتائج).
        assert "4 حمراء" in probe and "2 بيضاء" in probe and "5 خضراء" in probe

    def test_probe_survives_redaction(self):
        from app.services.skills.answer_redaction_skill import redact_final_answers

        probe = OrchestratorClient._build_diagnostic_probe(_combo())
        redacted, n_redactions = redact_final_answers(probe, 5)
        assert n_redactions == 0 and redacted == probe

    def test_prior_tutoring_step_detection(self):
        fresh = [
            {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
            {"role": "assistant", "content": "التمرين الأول (04 نقاط) — الاحتمالات ..."},
        ]
        assert OrchestratorClient._has_prior_tutoring_step(fresh) is False
        after_step = [
            *fresh,
            {
                "role": "assistant",
                "content": OrchestratorClient._build_symbolic_step(_combo(), None),
            },
        ]
        assert OrchestratorClient._has_prior_tutoring_step(after_step) is True
        after_probe = [
            *fresh,
            {"role": "assistant", "content": OrchestratorClient._build_diagnostic_probe(_combo())},
        ]
        assert OrchestratorClient._has_prior_tutoring_step(after_probe) is True

    @pytest.mark.parametrize(
        "q,expected",
        [
            ("كيف افهم للتمرين", True),
            ("كيف أحل السؤال الأول", True),
            ("من أين أبدأ", True),
            ("اعطني تمرين الاحتمالات 2024", False),
            ("هي 14 على 165", False),
        ],
    )
    def test_first_help_detector(self, q, expected):
        assert OrchestratorClient._is_first_help_request(q) is expected

    def test_procedure_branch_probes_first(self):
        src = _client_src()
        block = src.split("else:  # procedure — ISS-121 (D-154): سُلّم لا تفريغ", 1)[1][:1300]
        probe_i = block.find("_build_diagnostic_probe(_proc_combo)")
        step_i = block.find("_build_symbolic_step(_proc_combo, None)")
        assert 0 <= probe_i < step_i
        assert "_has_prior_tutoring_step(history_messages)" in block


class TestRevealLastInLadders:
    """Fix 4: الإنقاذ الكامل (reveal superset) آخر بدائل السُّلّم — يقتل التكرار المُقنَّع."""

    @pytest.mark.parametrize(
        "closure", ["def _is_dup(t: str) -> bool:", "def _d153_dup(t: str) -> bool:"]
    )
    def test_reveal_is_last_alternative(self, closure):
        src = _client_src()
        tail = src.split(closure, 1)[1][:2900]
        rev = tail.find("_build_symbolic_reveal")
        gen = tail.find("جرّب بنفسك: ركّب البسط")
        assert 0 <= gen < rev, f"reveal must come after the generation prompt in {closure!r}"
