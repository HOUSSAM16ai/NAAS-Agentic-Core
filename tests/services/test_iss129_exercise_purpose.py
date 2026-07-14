from __future__ import annotations

"""
ISS-129 (D-165) — سؤال «غاية التمرين» يُجاب + السؤال لا يُختطف بالـ probe.

الكارثة الحيّة (transcript BAC-2024، post-D-164): الطالب طلب تمرين الاحتمالات 2024
ثم سأل «**ماذا نستفيد كن هذا التمرين**» (سؤال meta عن الغاية التعليمية — typo «كن»
كما ورد حرفياً)، فتجاهله النظام كلياً وأطلق الـ probe التشخيصي («لنبدأ من فهمك
أنت — أيّ الألوان...»).

الجذران:
1. **S3 probe يسبق بوّابة هروب الأسئلة** في `_cognitive_turn` (بوّابة D-162 كانت
   بعد S3) — فأول سؤال غير-كيف يُختطف بالـ probe. المفارقة: port الخدمة المصغرة
   كان يضع البوّابة **قبل** الـ probe — افتراق split-brain حي.
2. **صفر كاشف لنية «الغاية»**: «نستفيد» غير موجودة في أي marker، ولا بانٍ حتمي.

الإصلاح (D-165): بوّابة الهروب قبل S3 (Fix A — مواءمة مع الـ port) + كاشف
`_detect_exercise_purpose_question` + بانٍ `exercise_purpose_summary` من المكوّنات
المعرفية (data-driven من combo — عقد ملايير التمارين) + مرآة الـ port + بوّابة
تكافؤ موسَّعة.
"""

from types import SimpleNamespace

import pytest

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.infrastructure.clients.orchestrator_client import OrchestratorClient
from app.services.skills.answer_redaction_skill import redact_final_answers
from app.services.skills.understanding_state_skill import get_understanding_state_skill

#: رسالة الكارثة الحرفية من transcript المالك (بالـ typo «كن»).
_CATASTROPHE_Q = "ماذا نستفيد كن هذا التمرين"

#: نص الـ probe التشخيصي (D-155) — يجب ألا يظهر رداً على سؤال الغاية.
_PROBE_MARK = "لنبدأ من فهمك أنت"


def _combo() -> SimpleNamespace:
    """تركيبة تمرين الاحتمالات BAC-2024 الرسمية (11 كرة، سحب 3)."""
    return SimpleNamespace(
        n=11,
        k=3,
        total_combinations=165,
        same_group_favorable=14,
        groups=[
            SimpleNamespace(
                color="red", label="كرة حمراء", count=4, is_possible=True, favorable_combinations=4
            ),
            SimpleNamespace(
                color="white",
                label="كرة بيضاء",
                count=2,
                is_possible=False,
                favorable_combinations=0,
            ),
            SimpleNamespace(
                color="green",
                label="كرة خضراء",
                count=5,
                is_possible=True,
                favorable_combinations=10,
            ),
        ],
    )


def _other_combo() -> SimpleNamespace:
    """تركيبة تمرين مختلف تماماً (عقد ملايير التمارين — لا أرقام مُصلَّبة)."""
    return SimpleNamespace(
        n=9,
        k=2,
        total_combinations=36,
        same_group_favorable=13,
        groups=[
            SimpleNamespace(
                color="blue", label="كرة زرقاء", count=3, is_possible=True, favorable_combinations=3
            ),
            SimpleNamespace(
                color="green",
                label="كرة خضراء",
                count=5,
                is_possible=True,
                favorable_combinations=10,
            ),
            SimpleNamespace(
                color="yellow",
                label="كرة صفراء",
                count=1,
                is_possible=False,
                favorable_combinations=0,
            ),
        ],
    )


def _exercise_history() -> list[dict[str, str]]:
    """محاكاة أمينة: الطالب طلب التمرين والمساعد طبعه (المحتوى الرسمي)."""
    from app.services.capabilities.exercise_retrieval import (
        ExerciseRetrievalRequest,
        detect_exercise_retrieval,
        load_exercise_content,
    )

    d = detect_exercise_retrieval(ExerciseRetrievalRequest(question="اعطني تمرين الاحتمالات 2024"))
    assert d.recognized and d.matched_entry is not None
    return [
        {"role": "user", "content": "اعطني تمرين الاحتمالات 2024"},
        {"role": "assistant", "content": load_exercise_content(d.matched_entry)[:3000]},
    ]


class TestPurposeDetector:
    """كاشف نية «غاية التمرين» — حتمي، مُطبَّع، لا يبتلع أسئلة D-125."""

    @pytest.mark.parametrize(
        "q",
        [
            _CATASTROPHE_Q,  # الكارثة الحرفية (typo «كن»)
            "ماذا نستفيد من هذا التمرين",
            "ما الفائدة من هذا التمرين",
            "ماذا نتعلم من التمرين",
            "ماذا يعلمنا هذا التمرين",
            "ما الهدف من التمرين",
            "ما الغرض من هذا التمرين",
            "واش نستافدو من التمرين",
            "ما اهمية هذا الدرس",
        ],
    )
    def test_positive(self, q: str):
        assert OrchestratorClient._detect_exercise_purpose_question(q) is True

    @pytest.mark.parametrize(
        "q",
        [
            # أسماء الغاية بلا مرجع تمرين ⇒ تبقى لطبقة D-125 المفاهيمية.
            "ما الهدف من الحادثة A",
            "ما فائدة 14",
            "ما الهدف من 165",
            # ليست أسئلة غاية إطلاقاً.
            "كيف احل السؤال الأول",
            "14 على 165",
            "نفس اللون",
            "",
        ],
    )
    def test_negative(self, q: str):
        assert OrchestratorClient._detect_exercise_purpose_question(q) is False


class TestPurposeAnswer:
    """بانٍ إجابة الغاية — data-driven من combo، صفر LLM، يَنجو من حجب D-113."""

    def test_data_driven_from_any_combo(self):
        """عقد ملايير التمارين: الإجابة تُبنى من combo أي تمرين، لا أرقام مُصلَّبة."""
        text = get_understanding_state_skill().exercise_purpose_summary(_other_combo())
        assert text
        assert "سحب 2 كرات" in text  # k من combo الآخر
        assert "زرقاء" in text and "صفراء" in text  # مجموعات combo الآخر
        assert "معنى الحادثة" in text and "فضاء العيّنة" in text  # عناوين الـ KCs

    def test_survives_d113_redaction(self):
        """عناوين فقط بلا نسبة نهائية ⇒ الحجب لا يلمسها (صفر كشف بالبناء)."""
        for combo in (_combo(), _other_combo()):
            text = get_understanding_state_skill().exercise_purpose_summary(combo)
            red, n = redact_final_answers(text)
            assert n == 0 and red == text

    def test_no_final_ratio_leak(self):
        text = get_understanding_state_skill().exercise_purpose_summary(_combo())
        assert "14/165" not in text and "14 من 165" not in text
        assert "\\boxed" not in text

    def test_malformed_combo_fails_open(self):
        assert get_understanding_state_skill().exercise_purpose_summary(None) is None
        assert OrchestratorClient._build_exercise_purpose_answer(None) is None


class TestCognitiveTurnRouting:
    """السلوك الكامل عبر `_cognitive_turn` — سيناريو الكارثة الحرفي."""

    def test_catastrophe_purpose_answered_not_probed(self):
        """«ماذا نستفيد كن هذا التمرين» ⇒ إجابة الغاية، صفر probe-hijack."""
        hist = _exercise_history()
        ts: dict = {"kc_progress": {}, "turn_count": 0}
        text, delta = OrchestratorClient._cognitive_turn(_CATASTROPHE_Q, hist, ts)
        assert text is not None
        assert _PROBE_MARK not in text
        assert "معنى الحادثة" in text and "فضاء العيّنة" in text
        assert delta is not None  # exercise_purpose سُجِّلت في kc_progress

    def test_kayf_still_gets_probe_d155(self):
        """D-155 محفوظ: «كيف احل السؤال الأول» أول دور ⇒ probe تشخيصي."""
        hist = _exercise_history()
        ts: dict = {"kc_progress": {}, "turn_count": 0}
        text, _ = OrchestratorClient._cognitive_turn("كيف احل السؤال الأول", hist, ts)
        assert text is not None and _PROBE_MARK in text

    def test_unanswered_question_escapes_before_probe(self):
        """Fix A: سؤال غير-كيف بلا إجابة حتمية في أول دور ⇒ يهرب (None)، لا probe."""
        hist = _exercise_history()
        ts: dict = {"kc_progress": {}, "turn_count": 0}
        text, _ = OrchestratorClient._cognitive_turn("ما هو الاحتمال الشرطي", hist, ts)
        assert text is None

    def test_no_verbatim_repeat_on_second_ask(self):
        """dedup: نفس سؤال الغاية مرتين ⇒ لا تكرار حرفي (يهرب لطبقات الإجابة)."""
        hist = _exercise_history()
        ts: dict = {"kc_progress": {}, "turn_count": 0}
        text, _ = OrchestratorClient._cognitive_turn(_CATASTROPHE_Q, hist, ts)
        assert text
        hist2 = [
            *hist,
            {"role": "user", "content": _CATASTROPHE_Q},
            {"role": "assistant", "content": text},
        ]
        ts2: dict = {"kc_progress": {}, "turn_count": 1}
        t2, _ = OrchestratorClient._cognitive_turn(_CATASTROPHE_Q, hist2, ts2)
        assert t2 is None or t2 != text

    def test_answer_survives_redaction_end_to_end(self):
        hist = _exercise_history()
        ts: dict = {"kc_progress": {}, "turn_count": 0}
        text, _ = OrchestratorClient._cognitive_turn(_CATASTROPHE_Q, hist, ts)
        red, n = redact_final_answers(text)
        assert n == 0 and red == text


class TestStructuralOrder:
    """قفل بنيوي (source-order عبر المانيفست — D-164): لا عودة للاختطاف."""

    def test_escape_gate_precedes_probe_in_cognitive_turn(self):
        src = read_tutor_source()
        body = src.split("def _cognitive_turn(", 1)[1].split("def _cognitive_turn_event_b(", 1)[0]
        p_escape = body.find('if _is_q and not _qg.startswith(("كيف", "كيفاش")):')
        p_probe = body.find("_build_diagnostic_probe(combo)")
        assert -1 < p_escape < p_probe, "question-escape must precede the S3 probe (D-165 Fix A)"

    def test_purpose_wiring_precedes_probe(self):
        src = read_tutor_source()
        body = src.split("def _cognitive_turn(", 1)[1].split("def _cognitive_turn_event_b(", 1)[0]
        p_purpose = body.find("_detect_exercise_purpose_question(question)")
        p_probe = body.find("_build_diagnostic_probe(combo)")
        assert -1 < p_purpose < p_probe, "purpose answer must precede the probe (D-165 Fix B)"
