from __future__ import annotations

from pathlib import Path

"""
M10-S2.1 (ISS-121 / D-154) — معلّم الاحتمالات الحتمي داخل الـ orchestrator.

أول خطوة هجرة roadmap M10-S2: port مستقل (stdlib فقط، صفر import متقاطع) لسُلّم
الكشف التدريجي — خلف علم `ORCHESTRATOR_PROB_TUTOR_ENABLED` (FLAGGED حتى التحقق
الحي في Codespaces — قاعدة الصدق §6.6).
"""

from microservices.orchestrator_service.src.services.overmind.probability_tutor import (
    build_diagnostic_probe,
    build_purpose_answer,
    build_symbolic_step,
    detect_naming_question,
    detect_purpose_question,
    deterministic_turn,
    fmt_comb,
    has_prior_tutoring_step,
    is_question_not_answer,
    norm_for_dedup,
    parse_composition,
    pending_focus_from_history,
    verify_numeric_answer,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_OFFICIAL = (
    _REPO_ROOT / "knowledge_base" / "bac2024_math_experimental_subject1_ex1_ex2.md"
).read_text(encoding="utf-8")


class TestPortIndependence:
    def test_no_cross_imports(self):
        src = (
            _REPO_ROOT
            / "microservices"
            / "orchestrator_service"
            / "src"
            / "services"
            / "overmind"
            / "probability_tutor.py"
        ).read_text(encoding="utf-8")
        assert "from app" not in src and "import app" not in src

    def test_flag_gated_in_synthesizer(self):
        src = (
            _REPO_ROOT
            / "microservices"
            / "orchestrator_service"
            / "src"
            / "services"
            / "overmind"
            / "graph"
            / "search.py"
        ).read_text(encoding="utf-8")
        assert "ORCHESTRATOR_PROB_TUTOR_ENABLED" in src
        assert "probability_tutor" in src


class TestCompositionParsing:
    def test_full_official_content_solution_immune(self):
        comp = parse_composition(_OFFICIAL)
        assert comp is not None
        assert (comp["n"], comp["k"], comp["total"], comp["same"]) == (11, 3, 165, 14)
        labels = {g["label"] for g in comp["groups"]}
        assert labels == {"كرة حمراء", "كرة بيضاء", "كرة خضراء"}

    def test_poisoned_total_rejected_by_denominator_gate(self):
        poisoned = (
            "يحتوي كيس على 14 كرة: أربع كرات حمراء و كرتان بيضاوان و خمس كرات خضراء "
            r"نسحب 3 كرات دفعة واحدة. علماً أن P(B) = \frac{56}{165}"
        )
        assert parse_composition(poisoned) is None

    def test_non_probability_returns_none(self):
        assert parse_composition("ادرس الدالة f(x) = x^2 على المجال [0,1]") is None


class TestProgressiveLadder:
    def test_four_turns_distinct_zero_final_answer(self):
        history: list[str] = []
        texts: list[str] = []
        for turn in ("كيف", "لم أفهم", "لم أفهم", "لم أفهم"):
            t = deterministic_turn(turn, _OFFICIAL, history=history)
            assert t, f"no ladder text for turn {len(texts) + 1}"
            assert "من كل 165" not in t and "14/165" not in t
            for prev in texts:
                assert norm_for_dedup(t) != norm_for_dedup(prev), "verbatim duplicate"
            texts.append(t)
            history.append(t)

    def test_rich_explanation_request_left_to_llm(self):
        rich = (
            "اشرح لي السؤال الأول بالتفصيل الممل مع كل الخطوات والمبررات النظرية "
            "لكل خطوة حتى أفهم المنهجية كاملة ثم اربطها بالدرس"
        )
        assert deterministic_turn(rich, _OFFICIAL) is None

    def test_latex_fmt(self):
        out = fmt_comb(5, 3, 10)
        assert out.startswith("$") and "C_{5}^{3}" in out and "\\dfrac" in out


class TestStatefulTutoring:
    """D-163 (Stage 2): النصف التربوي المُرحَّل — سدّ فجوة split-brain.

    الـ port صار يعترف بالإجابة الرقمية الصحيحة ويتقدّم، ويشخّص قبل المحتوى،
    ويحترم مستوى الدعم — نظائر D-155/D-115 — لا يبثّ السُّلّم فقط.
    """

    def _comp(self):
        c = parse_composition(_OFFICIAL)
        assert c is not None
        return c

    def test_probe_first_on_first_help_request(self):
        # أول طلب مساعدة عام ⇒ سؤال تشخيصي (صفر قيم محسوبة، لا 165).
        probe = deterministic_turn("كيف احل التمرين", _OFFICIAL, history=[])
        assert probe and "أيّ الألوان" in probe
        assert "165" not in probe and "=" not in probe

    def test_correct_final_ratio_acknowledged_and_advances(self):
        # «هل هي 14 من 165» (الإجابة الصحيحة) ⇒ اعتراف + انتقال (لا يُعاد السؤال).
        hist = ["Assistant: أيّ الألوان يمكن أن تعطينا 3 كرات من نفس اللون؟"]
        out = deterministic_turn("هل هي 14 من 165", _OFFICIAL, history=hist)
        assert out and "أحسنت" in out and "جداء" in out

    def test_verify_numeric_answer_uses_symbolic_numbers(self):
        comp = self._comp()
        assert verify_numeric_answer("14 من 165", comp, None) == "final_ratio"
        assert verify_numeric_answer("165", comp, "denominator") == "step_correct"
        assert verify_numeric_answer("11", comp, "denominator") == "direction"
        # سؤال يحمل أرقاماً ليس إجابة (بوّابة الفعل الكلامي — D-162).
        assert verify_numeric_answer("ماذا نسمي حساب 4 و 10", comp, None) is None
        # «هل» تبقى إجابة (D-155).
        assert verify_numeric_answer("هل هي 14 و 165", comp, None) == "final_ratio"

    def test_pending_focus_derived_from_our_templates(self):
        hist = ["User: نعم", "Assistant: كم عدد كل الطرق الممكنة لسحب 3 كرات من 11؟"]
        assert pending_focus_from_history(hist) == "denominator"
        assert pending_focus_from_history(["User: مرحبا"]) is None
        assert pending_focus_from_history([]) is None

    def test_diagnostic_probe_zero_reveal(self):
        probe = build_diagnostic_probe(self._comp())
        assert "أيّ الألوان" in probe
        # صفر كشف بنيوي: لا نتيجة، لا مساواة، لا نسبة نهائية.
        assert "165" not in probe and "14" not in probe and "=" not in probe

    def test_symbolic_step_acknowledge_survives_redaction(self):
        step = build_symbolic_step(self._comp(), None, acknowledge=True)
        assert step.startswith("إجابتك في الطريق الصحيح")
        # يَنجو من حجب D-113: النسبة النهائية لا تُطبع (نمط _fmt_comb + سؤال).
        assert "من كل 165" not in step and "14/165" not in step

    def test_has_prior_tutoring_step(self):
        assert has_prior_tutoring_step(["Assistant: نحسب الحالات الملائمة لكل لون"])
        assert not has_prior_tutoring_step(["User: كيف احل", "Assistant: مرحبا بك"])

    def test_support_level_shapes_ladder_no_rung_dropped(self):
        # منخفض ⇒ يبدأ بخطوة البسط الكاملة؛ عالٍ ⇒ تلميح افتتاحي أخفّ يسبقها.
        low = deterministic_turn("لم أفهم", _OFFICIAL, history=[], support_level=1)
        high = deterministic_turn("لم أفهم", _OFFICIAL, history=[], support_level=5)
        assert low and high and low != high
        assert "الحالات الملائمة" in low
        assert "تلميح خفيف" in high
        # لا رُتبة مُسقَطة: الطالب الواثق يصل خطوة البسط في الدور التالي.
        nxt = deterministic_turn("لم أفهم", _OFFICIAL, history=[high], support_level=5)
        assert nxt and "الحالات الملائمة" in nxt

    def test_speech_act_gate_and_naming_parity(self):
        # عقود متكافئة مع monolith (بوّابة split-brain) تعمل فعلاً على الـ port.
        assert is_question_not_answer("ماذا نسمي هذا الحساب")
        assert not is_question_not_answer("14 من 165")
        assert detect_naming_question("ماذا نسمي حساب 4 و 10", self._comp())


class TestExercisePurposeMirror:
    """D-165 (ISS-129): مرآة «غاية التمرين» في الـ port — تكافؤ split-brain فعلي."""

    def test_catastrophe_purpose_answered_not_probed(self):
        """«ماذا نستفيد كن هذا التمرين» ⇒ إجابة الغاية، لا probe، لا سقوط للـ LLM."""
        t = deterministic_turn("ماذا نستفيد كن هذا التمرين", _OFFICIAL, history=[])
        assert t is not None
        assert "لنبدأ من فهمك أنت" not in t
        assert "معنى الحادثة" in t and "فضاء العيّنة" in t

    def test_detector_matrix(self):
        assert detect_purpose_question("ما الفائدة من هذا التمرين")
        assert detect_purpose_question("واش نستافدو من التمرين")
        assert detect_purpose_question("ماذا نتعلم من التمرين")
        # أسماء الغاية بلا مرجع تمرين ⇒ ليست سؤال غاية (تبقى للـ LLM/المفاهيمي).
        assert not detect_purpose_question("ما الهدف من الحادثة A")
        assert not detect_purpose_question("ما فائدة 14")
        assert not detect_purpose_question("كيف احل السؤال الأول")

    def test_purpose_answer_no_final_ratio_and_data_driven(self):
        comp = parse_composition(_OFFICIAL)
        text = build_purpose_answer(comp)
        assert "14/165" not in text and "14 من 165" not in text and "\\boxed" not in text
        assert f"المجموع {comp['n']}" in text  # مؤرَّض من comp لا نص مُصلَّب

    def test_dedup_no_verbatim_repeat(self):
        t = deterministic_turn("ماذا نستفيد من هذا التمرين", _OFFICIAL, history=[])
        assert t
        again = deterministic_turn("ماذا نستفيد من هذا التمرين", _OFFICIAL, history=[t])
        assert again is None

    def test_kayf_still_gets_probe(self):
        t = deterministic_turn("كيف احل السؤال الأول", _OFFICIAL, history=[])
        assert t and "لنبدأ من فهمك أنت" in t
