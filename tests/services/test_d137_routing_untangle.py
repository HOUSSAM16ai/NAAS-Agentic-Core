"""
D-137 — فكّ تشابك التوجيه: «ما هو X» تعريف موثوق + كبح D-135 عن أسئلة المفهوم.

يُعيد transcript الـ8 أدوار الحرفي (الكارثة الحية) عبر المنطق الحقيقي للـ skills:
  T1 «ما هو الاحتمال الشرطي»      ⇒ تعريف conditional_probability (لا «14 من 165»).
  T2 «ماذا نقصد بالحالات الملائمة» ⇒ تعريف favorable_cases (مُسجَّل الآن).
  T3 «اعطني مثال»                  ⇒ مثال favorable_cases (المفهوم النشط، لا conditional).
  T4 «لم أفهم»                     ⇒ إعادة إشراك المفهوم النشط (لا الحادثة A).
  T7 «ما هو المتغير العشوائي»      ⇒ تعريف random_variable (لا الحادثة A).

الفصل الصارم: المفهوم ⇒ semantic_property؛ خطوة الحساب ⇒ understanding_state (D-135).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.skills.semantic_property_skill import get_semantic_property_skill
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


# ── A) «ما هو X» تعريف موثوق (يحلّ T1/T7) ─────────────────────────────────────
class TestDefinitionalMarkers:
    def test_bare_ma_huwa_is_definitional(self) -> None:
        sps = get_semantic_property_skill()
        assert sps.is_definitional("ما هو الاحتمال الشرطي")
        assert sps.is_definitional("ما هو المتغير العشوائي")
        assert sps.is_definitional("ما هي الحالات الملائمة")

    def test_conditional_interpreted_deterministically(self) -> None:
        # T1: «ما هو الاحتمال الشرطي» ⇒ conditional_probability (لا سقوط لـ D-135).
        out = get_semantic_property_skill().interpret("ما هو الاحتمال الشرطي")
        assert out is not None and out.property_id == "conditional_probability"
        assert "14" not in out.definition  # لا تسرّب نتيجة

    def test_random_variable_interpreted(self) -> None:
        # T7: «ما هو المتغير العشوائي» ⇒ random_variable (لا الحادثة A).
        out = get_semantic_property_skill().interpret("ما هو المتغير العشوائي")
        assert out is not None and out.property_id == "random_variable"

    def test_compute_question_not_definitional(self) -> None:
        # حارس الفصل: سؤال حساب ليس تعريفياً (لا يختطف مسار التعريف).
        assert not get_semantic_property_skill().is_definitional("كيف نحسب عدد التأليفات")


# ── B) كبح D-135 عن أسئلة المفهوم (يحلّ T1) ───────────────────────────────────
class TestUnderstandingStateNoConceptHijack:
    def test_ratio_gap_signals_free_of_bare_probability(self) -> None:
        kcs = get_understanding_state_skill().knowledge_components(_Combo())
        ratio = next(c for c in kcs if c.kc_id == "kc_ratio")
        assert "الاحتمال" not in ratio.gap_signals  # العنصر المجرّد محذوف

    def test_detect_gap_does_not_match_conditional_question(self) -> None:
        skill = get_understanding_state_skill()
        kcs = skill.knowledge_components(_Combo())
        # «ما هو الاحتمال الشرطي» يجب ألا يُطابق أي مكوّن حساب (لا اختطاف ⇒ لا 14/165).
        assert skill.detect_gap("ما هو الاحتمال الشرطي", kcs) is None

    def test_detect_gap_still_matches_real_computation_step(self) -> None:
        # لا انحدار: «لماذا نقسم على 3!» ما زال يُطابق kc_factorial.
        skill = get_understanding_state_skill()
        kcs = skill.knowledge_components(_Combo())
        gap = skill.detect_gap("لماذا نقسم على 3!", kcs)
        assert gap is not None and gap.kc_id == "kc_factorial"


# ── C) «الحالات الملائمة» مفهوم مُسجَّل (يحلّ T2/T3) ───────────────────────────
class TestFavorableCasesConcept:
    def test_favorable_cases_registered(self) -> None:
        out = get_semantic_property_skill().interpret("ماذا نقصد بالحالات الملائمة")
        assert out is not None and out.property_id == "favorable_cases"
        assert out.example.strip()

    def test_example_request_after_favorable_uses_favorable(self) -> None:
        # T3: «اعطني مثال» بعد تعريف الحالات الملائمة ⇒ المفهوم النشط = favorable_cases.
        history = [
            {"role": "user", "content": "ماذا نقصد بالحالات الملائمة"},
            {"role": "assistant", "content": "الحالات الملائمة هي عدد النتائج التي تُحقّق الحادثة."},
        ]
        out = get_semantic_property_skill().detect_active_concept("اعطني مثال", history)
        assert out is not None and out.property_id == "favorable_cases"


# ── D/E) الحيرة تُعيد إشراك المفهوم النشط + حارس التركيز (يحلّ T4/T8) ──────────
class TestConfusionReengagesActiveConcept:
    def test_active_concept_is_last_defined_not_event_a(self) -> None:
        # T4: «لم أفهم» بعد شرح الاحتمال الشرطي ⇒ المفهوم النشط = conditional (لا الحادثة A).
        history = [
            {"role": "user", "content": "ما هو الاحتمال الشرطي"},
            {
                "role": "assistant",
                "content": "## مثال ملموس\n\nلو علمتَ أن الكرات من نفس اللون، نحسب داخل هذه الحالة.",
            },
        ]
        out = get_semantic_property_skill().detect_active_concept("لم أفهم", history)
        assert out is not None and out.property_id == "conditional_probability"

    def test_focus_ignores_concept_example_artifact(self) -> None:
        # حارس E: آخر رسالة مساعد = مثال مفهوم (يذكر «نفس اللون» عابراً) ⇒ لا قفل على kc_event_meaning.
        skill = get_understanding_state_skill()
        kcs = skill.knowledge_components(_Combo())
        history = [
            {
                "role": "assistant",
                "content": "## مثال ملموس\n\nلو كانت الكرات من نفس اللون (تحقّقت A) نحسب داخلها.",
            },
        ]
        assert skill._current_focus_kc(kcs, history) is None
