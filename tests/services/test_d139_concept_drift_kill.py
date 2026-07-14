"""
D-139 — قتل انحراف المفهوم إلى الحادثة A نهائياً (كل أسئلة المفهوم تُمسَك قبل D-135).

يُعيد transcript الكارثة الحرفي عبر المنطق الحقيقي:
  «ما هو السحب على التوالي بدون إرجاع» ⇒ تعريف السحب (لا event-A).
  «كيف نضيق الإمكانيات» ⇒ conditional (لا event-A).
  «كيف نحصل على ثلاث كرات معدومة» ⇒ product_zero (لا event-A).
  «لم أفهم» المتكرّرة (بعد تلوّث event-A) ⇒ conditional (لا انحراف).
  detect_active_concept لا ينجرف من إفراغ تمرين طويل؛ «احسب احتمال A» لا تُفعَّل المصفوفة.
"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.services.skills.micro_simulation_skill import (
    MICRO_SIM_MAX_CHARS,
    get_micro_simulation_skill,
)
from app.services.skills.semantic_property_skill import (
    PROPERTY_REGISTRY,
    get_semantic_property_skill,
)
from app.services.skills.student_state_skill import StudentStateInput, get_student_state_skill

ROOT = Path(__file__).resolve().parent.parent.parent
_SPS = get_semantic_property_skill()
_SS = get_student_state_skill()

# نسخة من إفراغ التمرين (رسالة مساعد ضخمة تحوي «نفس اللون»/«الحادثة A») — مصدر الانحراف القديم.
_EXERCISE_DUMP = (
    "التمرين الأول (04 نقاط) — الاحتمالات. يحتوي كيس على 11 كرة. نسحب عشوائيًا 3 كرات دفعة واحدة. "
    "A: الحصول على 3 كرات من نفس اللون. B: جداء أرقامها فردي. احسب احتمال الحادثة A. " * 3
)
# تمثيل kc_event_meaning (D-135) — نص الحادثة A العابر الذي كان يلوّث المحادثة.
_EVENT_A_TEXT = "تخيّل أنك سحبت 3 كرات: لو كانت كلها خضراء ⇒ تحقّقت A؛ لو اختلطت الألوان ⇒ لم تتحقّق."

_CONCEPT_TEACH = frozenset(
    {"definition", "example_request", "confusion", "procedure", "hint_request"}
)
_COMPUTE = ("احسب", "أحسب", "كم ", "اوجد", "أوجد", "بيّن", "بين ان", "استنتج")
_FOLLOWUP = (
    "كيف",
    "لماذا",
    "علاش",
    "وضح",
    "اشرح",
    "بسط",
    "؟",
    "مثال",
    "لم افهم",
    "لم أفهم",
    "مفهمتش",
)


def _u(t):
    return {"role": "user", "content": t}


def _a(t):
    return {"role": "assistant", "content": t}


def _route_concept(question: str, history: list[dict]) -> str | None:
    """يُحاكي بوّابة بلوك المصفوفة (D-138/D-139، Fix B) — أيّ مفهوم تُمسَك به (None=لا تُمسَك)."""
    state = _SS.read(StudentStateInput(question=question, history=history))
    ql = question.lower()
    compute = any(m in ql for m in _COMPUTE)
    followup = any(m in ql for m in _FOLLOWUP)
    teach_ok = state.primary_intent in _CONCEPT_TEACH or (
        state.primary_intent == "unknown" and (followup or _SPS.interpret(question) is not None)
    )
    if teach_ok and not compute:  # سياق الاحتمالات مفترض (history فيه التمرين)
        active = _SPS.detect_active_concept(question, history)
        return active.concept_id if active else None
    return None


# ── A) تحصين detect_active_concept (kill drift) ───────────────────────────────
class TestDriftKilled:
    def test_new_concept_question_no_drift_to_event_a(self) -> None:
        # «ما هو السحب على التوالي» مع إفراغ تمرين ⇒ sequential (لا same_color/event_meaning).
        hist = [_u("اعطني تمرين الاحتمالات 2024"), _a(_EXERCISE_DUMP)]
        out = _SPS.detect_active_concept("ما هو السحب على التوالي بدون إرجاع", hist)
        assert out is not None and out.concept_id == "sequential_without_replacement"

    def test_unregistered_definitional_returns_none(self) -> None:
        # «ما هو الوسيط» (غير مُسجَّل) ⇒ None (لا انجراف) ⇒ LLM Listener-Definer.
        hist = [_u("اعطني تمرين"), _a(_EXERCISE_DUMP)]
        assert _SPS.detect_active_concept("ما هو الوسيط", hist) is None

    def test_followup_finds_student_named_concept_over_event_a_pollution(self) -> None:
        # «كيف نضيق الإمكانيات» بعد سؤال الطالب عن conditional + تلوّث event-A ⇒ conditional.
        hist = [
            _u("اعطني تمرين"),
            _a(_EXERCISE_DUMP),
            _u("ما هو الاحتمال الشرطي"),
            _a("## ماذا نقصد بالاحتمال الشرطي؟\n\nالاحتمال الشرطي هو..."),
            _u("لم أفهم"),
            _a(_EVENT_A_TEXT),
        ]
        out = _SPS.detect_active_concept("كيف نضيق الإمكانيات", hist)
        assert out is not None and out.concept_id == "conditional_probability"

    def test_full_history_user_scan_not_truncated_at_6(self) -> None:
        # سؤال الطالب عن conditional خارج نافذة [-6:] ⇒ user-scan كامل التاريخ يجده.
        hist = [_u("ما هو الاحتمال الشرطي"), _a("تعريف الشرطي")]
        hist += [_u("حسناً"), _a("جيد")] * 4  # حشو > 6 رسائل
        out = _SPS.detect_active_concept("لم افهم", hist)
        assert out is not None and out.concept_id == "conditional_probability"

    def test_exercise_dump_alone_does_not_set_active_concept(self) -> None:
        # متابعة بلا سؤال طالب عن مفهوم + فقط إفراغ تمرين ⇒ لا انجراف لـ same_color.
        hist = [_u("اعطني تمرين"), _a(_EXERCISE_DUMP)]
        assert _SPS.detect_active_concept("لم افهم", hist) is None


# ── B) بوّابة المصفوفة: أسئلة المفهوم تُمسَك، الحساب لا ────────────────────────
class TestEscalationGate:
    def _conditional_hist(self):
        return [
            _u("اعطني تمرين"),
            _a(_EXERCISE_DUMP),
            _u("ما هو الاحتمال الشرطي"),
            _a("## ماذا نقصد بالاحتمال الشرطي؟\n\nالاحتمال الشرطي هو..."),
        ]

    def test_how_question_unknown_intent_caught_by_matrix(self) -> None:
        # «كيف نضيق الإمكانيات» (unknown intent + followup) ⇒ تُمسَك بالمصفوفة = conditional.
        assert (
            _route_concept("كيف نضيق الإمكانيات", self._conditional_hist())
            == "conditional_probability"
        )

    def test_how_get_zero_caught_as_product_zero(self) -> None:
        # «كيف نحصل على ثلاث كرات معدومة» ⇒ product_zero (يُسمّيه «معدوم»)، لا event-A.
        assert (
            _route_concept("كيف نحصل على ثلاث كرات معدومة", self._conditional_hist())
            == "product_zero"
        )

    def test_compute_question_not_caught(self) -> None:
        # «احسب احتمال الحادثة A» ⇒ لا تُفعَّل المصفوفة (تبقى للمسار الحسابي).
        assert _route_concept("احسب احتمال الحادثة A", self._conditional_hist()) is None

    def test_sequential_definition_caught(self) -> None:
        assert (
            _route_concept("ما هو السحب على التوالي بدون إرجاع", self._conditional_hist())
            == "sequential_without_replacement"
        )


# ── C) نمطا السحب: تعريف حتمي + micro-sim ──────────────────────────────────────
class TestDrawingModeConcepts:
    def test_registered(self) -> None:
        assert "sequential_without_replacement" in PROPERTY_REGISTRY
        assert "simultaneous_draw" in PROPERTY_REGISTRY

    def test_definitions_concrete_no_event_a(self) -> None:
        seq = PROPERTY_REGISTRY["sequential_without_replacement"]
        assert "لا تُعاد" in seq.definition and "كلها خضراء" not in seq.definition
        sim = PROPERTY_REGISTRY["simultaneous_draw"]
        assert "معاً" in sim.definition and "كلها خضراء" not in sim.definition

    def test_micro_sims_within_limit(self) -> None:
        ms = get_micro_simulation_skill()
        for cid in ("sequential_without_replacement", "simultaneous_draw"):
            sim = ms.get_micro_simulation(cid)
            assert sim and len(sim) <= MICRO_SIM_MAX_CHARS


# ── D) حارس D-135 (لا حادثة A لمفهوم غير-حدثي) ─────────────────────────────────
class TestUnderstandingStateGuard:
    def test_non_confused_how_question_returns_none(self) -> None:
        # حارس دفاع عميق: «كيف نضيق» (غير حيرة، بلا gap) ⇒ decide=None (لا default لـ event-A).
        from dataclasses import dataclass

        from app.services.skills.understanding_state_skill import get_understanding_state_skill

        @dataclass
        class _G:
            label: str
            count: int
            favorable_combinations: int
            is_possible: bool

        @dataclass
        class _Combo:
            n: int = 11
            k: int = 3
            total_combinations: int = 165
            same_group_favorable: int = 14
            groups: tuple = (
                _G("كرة حمراء", 4, 4, True),
                _G("كرة بيضاء", 2, 0, False),
                _G("كرة خضراء", 5, 10, True),
            )

        us = get_understanding_state_skill()
        # history تجعل kc_event_meaning «explained» (إفراغ التمرين)، لكن السؤال غير حيرة.
        hist = [_u("اعطني تمرين"), _a(_EXERCISE_DUMP)]
        d = us.decide(question="كيف نضيق الإمكانيات", history=hist, combo=_Combo())
        assert d is None  # لا نص الحادثة A الافتراضي


# ── فحص بنيوي للتوصيل ─────────────────────────────────────────────────────────
class TestWiring:
    CLIENT = read_tutor_source()
    SPS = (ROOT / "app/services/skills/semantic_property_skill.py").read_text(encoding="utf-8")
    US = (ROOT / "app/services/skills/understanding_state_skill.py").read_text(encoding="utf-8")

    def test_compute_guard_wired(self) -> None:
        assert "_esc_compute" in self.CLIENT and "_esc_followup" in self.CLIENT

    def test_detect_active_concept_new_definitional_guard(self) -> None:
        assert "_EXERCISE_DUMP_MARKERS" in self.SPS
        assert "if self.is_definitional(question)" in self.SPS

    def test_understanding_state_guard(self) -> None:
        assert "elif _confused:" in self.US
