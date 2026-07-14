"""
D-138 — Adaptive Pedagogical Escalation: Matrix + Understanding-Signal + Misconception-Check.

يُثبت إصلاح الكارثة الحيّة (الاحتمال الشرطي): «لم أفهم»/«كيف»/«اعطني مثال عددي» كانت تُعيد نص
الحادثة A حرفياً بلا تصعيد. الآن مصفوفة تصعيدية تكيّفية:
  • تعريف → مثال → محاكاة مصغّرة (concept-scoped، لا انحراف لـ event-A).
  • «اعطني مثال عددي» ⇒ محاكاة مصغّرة حتمية (L3).
  • «لم أفهم» ⇒ تصعيد للمستوى التالي (لا تكرار)؛ استنفاد L3 ⇒ تسليم لطيف.
  • مُعايَرة بالقدرة (support_level): منخفضة ⇒ أسرع للمحاكاة، عالية ⇒ رُتبة أخف.
  • Understanding Signal ⇒ توقّف (mastered)؛ Misconception ⇒ تدخّل مُوجَّه.
"""

from __future__ import annotations

from pathlib import Path

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.services.skills.answer_redaction_skill import redact_final_answers
from app.services.skills.micro_simulation_skill import (
    APPLY_STEPS,
    MICRO_SIM_MAX_CHARS,
    MICRO_SIMULATIONS,
    get_micro_simulation_skill,
)
from app.services.skills.pedagogical_escalation_skill import (
    L1_DEFINITION,
    L2_ANALOGY,
    L3_MICRO_SIMULATION,
    EscalationInput,
    get_pedagogical_escalation_skill,
)
from app.services.skills.semantic_property_skill import PROPERTY_REGISTRY

ROOT = Path(__file__).resolve().parent.parent.parent

_SPEC = PROPERTY_REGISTRY["conditional_probability"]
_MICRO = get_micro_simulation_skill().get_micro_simulation(_SPEC.concept_id)


def _inp(intent: str, history: list[dict], *, sup=None, mis=None, mtype=None) -> EscalationInput:
    return EscalationInput(
        concept_id=_SPEC.concept_id,
        title=_SPEC.title,
        definition=_SPEC.definition,
        example=_SPEC.example,
        micro_sim=_MICRO,
        intent=intent,
        history=history,
        support_level=sup,
        evidence_markers=_SPEC.evidence_markers,
        misconception_intervention=mis,
        misconception_mtype=mtype,
    )


def _asst(text: str) -> dict[str, str]:
    return {"role": "assistant", "content": text}


def _usr(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


def _skill():
    return get_pedagogical_escalation_skill()


# ── إعادة transcript الكارثة (التصعيد لا التكرار) ─────────────────────────────
class TestCatastropheReplay:
    def test_definition_then_example_then_micro_sim(self) -> None:
        s = _skill()
        h: list[dict] = []
        d1 = s.decide(_inp("definition", h))
        assert d1.action == "teach" and d1.strategy_level == L1_DEFINITION
        h += [_usr("ما هو الاحتمال الشرطي"), _asst(d1.text)]

        d2 = s.decide(_inp("example_request", h))
        assert d2.action == "teach" and d2.strategy_level == L2_ANALOGY
        h += [_usr("اعطني مثال"), _asst(d2.text)]

        # «اعطني مثال عددي» ⇒ محاكاة مصغّرة حتمية (L3) — قلب الإصلاح.
        d3 = s.decide(_inp("example_request", [*h, _usr("اعطني مثال عددي")]))
        assert d3.action == "teach" and d3.strategy_level == L3_MICRO_SIMULATION
        assert "محاكاة" in d3.text and "10 طلاب" in d3.text  # المحاكاة الحتمية
        assert "كلها خضراء" not in d3.text  # صفر انحراف لـ event-A

    def test_confusion_escalates_not_repeats(self) -> None:
        # «لم أفهم» بعد L1+L2 ⇒ L3 (تصعيد)، لا تكرار نص الحادثة A.
        s = _skill()
        h = [_usr("ما هو"), _asst(s.decide(_inp("definition", [])).text)]
        h += [_usr("اعطني مثال"), _asst(s.decide(_inp("example_request", h)).text)]
        d = s.decide(_inp("confusion", h))
        assert d.action == "teach" and d.strategy_level == L3_MICRO_SIMULATION
        assert "محاكاة" in d.text

    def test_ladder_exhausted_handoff_not_repeat(self) -> None:
        # بعد L1+L2+L3، «لم أفهم»/«كيف» ⇒ تسليم لطيف (لا تكرار، لا event-A).
        s = _skill()
        h = [_usr("ما هو"), _asst(s.decide(_inp("definition", [])).text)]
        h += [_usr("اعطني مثال"), _asst(s.decide(_inp("example_request", h)).text)]
        h += [
            _usr("اعطني مثال عددي"),
            _asst(s.decide(_inp("example_request", [*h, _usr("اعطني مثال عددي")])).text),
        ]
        d = s.decide(_inp("confusion", h))
        assert d.action == "exhausted" and d.text_kind == "handoff"
        assert "كلها خضراء" not in d.text


# ── الإشارات الثلاث (نقد المالك النهائي) ──────────────────────────────────────
class TestThreeSignals:
    def test_understanding_signal_stops_escalation(self) -> None:
        # دليل فهم الآلية ⇒ mastered (لا تصعيد) — التصعيد على الأثر لا عدّ «لم أفهم».
        d = _skill().decide(_inp("confusion", [_usr("اها فهمت، تقلص الفضاء فنقسم على عدد اقل")]))
        assert d.action == "mastered" and d.text_kind == "ack"

    def test_bare_acknowledgement_is_not_evidence(self) -> None:
        # «فهمت» المجرّدة (بلا آلية) ليست برهاناً ⇒ لا mastered.
        d = _skill().decide(_inp("confusion", [_usr("فهمت")]))
        assert d.action != "mastered"

    def test_misconception_targets_intervention(self) -> None:
        d = _skill().decide(
            _inp(
                "confusion",
                [_usr("يعني نضرب الاحتمالين؟")],
                mis="الاحتمال الشرطي ليس ضرب احتمالين",
                mtype="rule_property",
            )
        )
        assert d.action == "target_misconception" and d.text_kind == "intervention"
        assert "ليس ضرب احتمالين" in d.text


# ── المعايرة بالقدرة (Ability + Step-Difficulty) ──────────────────────────────
class TestAbilityCalibration:
    def _h_l1_l2(self):
        s = _skill()
        h = [_usr("ما هو"), _asst(s.decide(_inp("definition", [])).text)]
        h += [_usr("اعطني مثال"), _asst(s.decide(_inp("example_request", h)).text)]
        return h

    def test_low_ability_reaches_micro_sim(self) -> None:
        # قدرة منخفضة (sup=2) + حيرة بعد L1+L2 ⇒ L3 (سقالة، لا تخطّي لـ exhausted).
        d = _skill().decide(_inp("confusion", self._h_l1_l2(), sup=2))
        assert d.strategy_level == L3_MICRO_SIMULATION

    def test_high_ability_lighter_rung_first(self) -> None:
        # قدرة عالية (sup=5) + حيرة بعد L1 فقط ⇒ L2 (رُتبة أخف، student agency) لا قفز لـ L3.
        s = _skill()
        h = [_usr("ما هو"), _asst(s.decide(_inp("definition", [])).text)]
        d = s.decide(_inp("confusion", h, sup=5))
        assert d.strategy_level == L2_ANALOGY

    def test_same_intent_different_ability_different_rung(self) -> None:
        # نفس النيّة + طالب مختلف ⇒ رُتبة مختلفة (مرونة لا جمود).
        s = _skill()
        h = [_usr("ما هو"), _asst(s.decide(_inp("definition", [])).text)]
        low = s.decide(_inp("confusion", h, sup=2)).strategy_level
        high = s.decide(_inp("confusion", h, sup=5)).strategy_level
        assert low >= high  # المنخفض يُصعِّد أسرع


# ── Micro-Simulation: حتمي، قصير، يَنجو من D-113 ──────────────────────────────
class TestMicroSimulation:
    def test_all_within_length_limit(self) -> None:
        for cid, sim in MICRO_SIMULATIONS.items():
            assert len(sim) <= MICRO_SIM_MAX_CHARS, f"{cid} too long ({len(sim)})"

    def test_survives_d113_no_exercise_answer(self) -> None:
        for cid, sim in MICRO_SIMULATIONS.items():
            redacted, _ = redact_final_answers(sim, support_level=5)
            assert redacted.strip(), f"{cid} fully redacted"
            assert "14/165" not in sim and "14 من 165" not in sim, f"{cid} leaks answer"

    def test_unknown_concept_returns_none(self) -> None:
        assert get_micro_simulation_skill().get_micro_simulation("no_such_concept") is None

    def test_conditional_has_micro_sim(self) -> None:
        assert get_micro_simulation_skill().get_micro_simulation("conditional_probability")


# ── فحص بنيوي للتوصيل (no-ZOMBIE + concept-scoped + ترتيب) ─────────────────────
class TestWiring:
    CLIENT_SRC = read_tutor_source()

    def test_escalation_invoked_and_concept_scoped(self) -> None:
        assert "get_pedagogical_escalation_skill" in self.CLIENT_SRC
        assert "get_micro_simulation_skill" in self.CLIENT_SRC
        assert "detect_active_concept" in self.CLIENT_SRC  # concept-scoped

    def test_escalation_precedes_definitional_preempt(self) -> None:
        # المصفوفة (المسار الأساسي) تسبق preempt التعريف العام (للمفاهيم الجديدة).
        esc = self.CLIENT_SRC.find("get_pedagogical_escalation_skill")
        defp = self.CLIENT_SRC.find("interpret_or_define(question)")
        assert esc != -1 and defp != -1 and esc < defp

    def test_doctrine_manifest_consistent(self) -> None:
        from app.services.skills.doctrine import (
            MICRO_SIMULATION_DOCTRINE,
            MICRO_SIMULATION_DOCTRINE_VERSION,
            PEDAGOGICAL_ESCALATION_DOCTRINE,
            PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )

        e = SKILL_DOCTRINE_MANIFEST["pedagogical_escalation"]
        assert e["version"] == PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION
        assert e["rules_count"] == len(PEDAGOGICAL_ESCALATION_DOCTRINE)
        m = SKILL_DOCTRINE_MANIFEST["micro_simulation"]
        assert m["version"] == MICRO_SIMULATION_DOCTRINE_VERSION
        assert m["rules_count"] == len(MICRO_SIMULATION_DOCTRINE)

    def test_registry_registers_both(self) -> None:
        from app.services.skills.registry import get_skill_registry

        names = set(get_skill_registry().names())
        assert "pedagogical_escalation" in names
        assert "micro_simulation" in names


# ── D-147: نفاد السُّلّم ⇒ سؤال تطبيق مرتبط بالتمرين بدل الـ punt العام ────────────
class TestApplyStepOnExhaustion:
    def _exhausted_history(self) -> list[dict]:
        s = _skill()
        h = [_usr("ما هو"), _asst(s.decide(_inp("definition", [])).text)]
        h += [_usr("اعطني مثال"), _asst(s.decide(_inp("example_request", h)).text)]
        h += [
            _usr("اعطني مثال عددي"),
            _asst(s.decide(_inp("example_request", [*h, _usr("اعطني مثال عددي")])).text),
        ]
        return h

    def test_exhaustion_with_apply_step_leads_not_punts(self) -> None:
        # عند توفّر apply_step (مثل مسار الأورقستريتور الحيّ) ⇒ سؤال تطبيق ملموس لا punt عام.
        s = _skill()
        h = self._exhausted_history()
        d = s.decide(
            EscalationInput(
                concept_id=_SPEC.concept_id,
                title=_SPEC.title,
                definition=_SPEC.definition,
                example=_SPEC.example,
                micro_sim=_MICRO,
                apply_step=APPLY_STEPS["conditional_probability"],
                intent="confusion",
                history=h,
                evidence_markers=_SPEC.evidence_markers,
            )
        )
        assert d.action == "exhausted" and d.text_kind == "apply"
        assert d.rationale == "apply_to_exercise"
        assert "أيّ خطوة تريد" not in d.text  # لا punt عام
        assert "الفضاء الجديد" in d.text  # سؤال تطبيق ملموس مرتبط بالتمرين

    def test_exhaustion_without_apply_step_falls_back_to_handoff(self) -> None:
        # المفهوم غير المُغطّى (apply_step=None) ⇒ التسليم العامّ القديم (لا انحدار).
        s = _skill()
        d = s.decide(_inp("confusion", self._exhausted_history()))
        assert d.action == "exhausted" and d.text_kind == "handoff"

    def test_expected_value_apply_step_is_x_domain_question(self) -> None:
        # قلب كارثة E(X): يقود لقيم X لا «أيّ خطوة تريد؟».
        step = get_micro_simulation_skill().get_apply_step("expected_value")
        assert step and "ما القيم التي يمكن أن يأخذها X" in step

    def test_all_apply_steps_survive_d113_redaction(self) -> None:
        # كل خطوة تطبيق سؤال لا جواب ⇒ صفر حجب (لا تسريب نتيجة نهائية).
        for cid, txt in APPLY_STEPS.items():
            out, n = redact_final_answers(txt)
            assert n == 0 and out == txt, f"{cid} leaked under redaction"

    def test_registry_light_and_concept_scoped(self) -> None:
        # خفيف ومحدّد بالمفاهيم (نقد المالك #1+#3): المفاتيح ⊆ MICRO_SIMULATIONS.
        assert set(APPLY_STEPS).issubset(set(MICRO_SIMULATIONS))
        assert len(APPLY_STEPS) <= 10

    def test_orchestrator_passes_apply_step(self) -> None:
        # wiring: مسار الأورقستريتور يمرّر apply_step فعلاً.
        src = read_tutor_source()
        assert "get_apply_step(" in src
