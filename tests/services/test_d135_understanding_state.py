"""
D-135 — محرّك حالة الفهم (Understanding State Engine) regression tests.

يثبت نقد المالك الرباعي:
  • Knowledge Gap لا رقم: «لماذا قسمنا على 3!» (بلا رقم) ⇒ kc_factorial؛ «كيف وصلنا ل 10» ⇒ kc_combination.
  • تكرار دلالي لا حرفي: مكوّن مفهوم لا يُعاد؛ الحالة على مستوى المكوّن.
  • الفهم ببرهان لا صحة: «فهمت» وحدها ⇒ explained لا understood؛ برهان مرتبط ⇒ understood.
  • استباقي: مكوّن شُرح بلا فهم ⇒ تمثيل أعلى (لا تكرار).
  • الاعتراف والتقدّم: برهان ⇒ advance للمكوّن التالي.
  • الأرقام من المحرك الرمزي؛ نجاة حجب D-113؛ فحص بنيوي للتوصيل.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.services.skills.understanding_state_skill import (
    UnderstandingStateSkill,
    get_understanding_state_skill,
)

ROOT = Path(__file__).resolve().parent.parent.parent


# ── combo مزيّف (يحاكي CombinationsModelOutput لتمرين 2024) ──────────────────
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


def _skill() -> UnderstandingStateSkill:
    return get_understanding_state_skill()


def _combo() -> _Combo:
    return _Combo()


# ── A) المكوّنات المعرفية مُشتقّة من combo ────────────────────────────────────
class TestKnowledgeComponents:
    def test_six_components_from_combo(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        ids = {kc.kc_id for kc in kcs}
        assert ids == {
            "kc_event_meaning",
            "kc_favorable_cases",
            "kc_combination",
            "kc_factorial",
            "kc_sample_space",
            "kc_ratio",
        }

    def test_numbers_from_symbolic_engine(self) -> None:
        kcs = {kc.kc_id: kc for kc in _skill().knowledge_components(_combo())}
        # الأرقام (165، C(5,3)=10) من combo لا مكتوبة يدوياً.
        assert "165" in kcs["kc_sample_space"].representations[0]
        assert "10" in kcs["kc_combination"].representations[0]


# ── B) مُشخِّص الفجوة (semantic, not number) ──────────────────────────────────
class TestDetectGap:
    def test_factorial_gap_without_number(self) -> None:
        # نقد 1: «لماذا قسمنا على 3!» — لا رقم 10/14/165 إطلاقاً.
        kcs = _skill().knowledge_components(_combo())
        gap = _skill().detect_gap("لماذا قسمنا على 3! ولا نضرب مباشرة؟", kcs)
        assert gap is not None and gap.kc_id == "kc_factorial"

    def test_combination_gap(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        for q in ("كيف وصلنا ل 10", "لماذا اخترنا 3 من 5", "من أين جاءت التأليفات"):
            gap = _skill().detect_gap(q, kcs)
            assert gap is not None and gap.kc_id == "kc_combination", q

    def test_sample_space_gap(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        gap = _skill().detect_gap("ما هي كل الطرق الممكنة؟", kcs)
        assert gap is not None and gap.kc_id == "kc_sample_space"

    def test_no_gap_for_unrelated(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        assert _skill().detect_gap("مرحبا كيف حالك", kcs) is None


# ── C) الفهم ببرهان لا صحة (نقد 3) ────────────────────────────────────────────
class TestUnderstandingEvidence:
    def test_bare_acknowledgment_is_not_understood(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        history = [
            {"role": "assistant", "content": "C(5,3) يعني عدد طرق اختيار 3 دون اهتمام بالترتيب."},
            {"role": "user", "content": "فهمت"},  # إقرار مجرّد — لا برهان
        ]
        states = _skill().understanding_state(history, kcs)
        assert states["kc_combination"] == "explained"  # شُرح لكن لم يُبرهن

    def test_evidence_marks_understood(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        history = [
            {"role": "assistant", "content": "C(5,3) يعني عدد طرق اختيار 3 دون اهتمام بالترتيب."},
            {"role": "user", "content": "آه، نختار 3 من 5 بدون ترتيب"},  # برهان مرتبط
        ]
        states = _skill().understanding_state(history, kcs)
        assert states["kc_combination"] == "understood"

    def test_not_addressed_when_no_explanation(self) -> None:
        kcs = _skill().knowledge_components(_combo())
        states = _skill().understanding_state([], kcs)
        assert all(s == "not_addressed" for s in states.values())


# ── D) تمثيل استباقي + E) القرار ─────────────────────────────────────────────
class TestDecide:
    def test_gap_question_explains_kc(self) -> None:
        d = _skill().decide(question="لماذا قسمنا على 3!", history=[], combo=_combo())
        assert d is not None and d.kc_id == "kc_factorial"
        assert d.action in ("explain", "re_represent")

    def test_proactive_escalation_no_repeat(self) -> None:
        # نقد 4: شُرح مرّة بلا فهم ⇒ تمثيل مختلف (مستوى أعلى)، لا تكرار.
        kc_combo = _combo()
        explained_once = [
            {"role": "user", "content": "كيف وصلنا ل 10"},
            {
                "role": "assistant",
                "content": "C(5,3) عدد طرق اختيار دون اهتمام بالترتيب: C(5,3) = (5×4×3)/(3×2×1) = 10.",
            },
            {"role": "user", "content": "لم أفهم"},
        ]
        d = _skill().decide(question="لم أفهم", history=explained_once, combo=kc_combo)
        assert d is not None and d.kc_id == "kc_combination"
        assert d.representation_level >= 1  # تصاعد — لا المستوى 0 نفسه

    def test_evidence_advances_to_next(self) -> None:
        # نقد 3 + الاعتراف والتقدّم: برهان فهم ⇒ advance لمكوّن آخر.
        history = [
            {"role": "assistant", "content": "الحادثة A: 3 كرات من نفس اللون."},
        ]
        d = _skill().decide(
            question="نفس اللون، الأحمر والأخضر فقط", history=history, combo=_combo()
        )
        assert d is not None and d.action in ("advance", "mastered")

    def test_returns_none_for_no_combo(self) -> None:
        assert _skill().decide(question="أي شيء", history=[], combo=None) is None


# ── نجاة حجب D-113 + فحص بنيوي للتوصيل ───────────────────────────────────────
class TestRedactionAndWiring:
    def test_representations_survive_d113(self) -> None:
        # نمط _expand_comb «(num)/(den) = fav» يَنجو من حجب الإجابة (RHS ليس عدداً صرفاً بعد =).
        kcs = _skill().knowledge_components(_combo())
        from app.services.skills.answer_redaction_skill import redact_final_answers

        for kc in kcs:
            for rep in kc.representations:
                redacted, _ = redact_final_answers(rep, support_level=5)
                # الصيغة المُقوَّسة لا تُحجب بالكامل (تبقى C(...) مرئية للتعليم).
                if "C(" in rep:
                    assert "C(" in redacted

    def test_skill_is_llm_free(self) -> None:
        src = (ROOT / "app/services/skills/understanding_state_skill.py").read_text(
            encoding="utf-8"
        )
        assert "send_message" not in src and "get_ai_client" not in src

    def test_wired_in_orchestrator(self) -> None:
        src = (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )
        assert "get_understanding_state_skill" in src
        assert "_is_short_answer_in_dialogue" in src

    def test_manifest_entry(self) -> None:
        from app.services.skills.doctrine import (
            SKILL_DOCTRINE_MANIFEST,
            UNDERSTANDING_STATE_DOCTRINE,
            UNDERSTANDING_STATE_DOCTRINE_VERSION,
        )

        entry = SKILL_DOCTRINE_MANIFEST["understanding_state"]
        assert entry["version"] == UNDERSTANDING_STATE_DOCTRINE_VERSION
        assert entry["rules_count"] == len(UNDERSTANDING_STATE_DOCTRINE)
