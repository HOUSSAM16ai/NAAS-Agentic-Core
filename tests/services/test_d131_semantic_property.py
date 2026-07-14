"""
D-131 — Semantic Property Layer + Misconception Graph regression tests.

يثبت:
  • طبقة دلالية عامة data-driven (لا special-casing): «جداء معدوم/فردي/زوجي» + «نفس اللون».
  • التعريفات الصحيحة (معدوم→الرقم 0؛ فردي→كلها فردية؛ زوجي→واحدة زوجية؛ same_color).
  • **الثلاثة طلاب**: نفس السؤال ⇒ misconceptions مختلفة ⇒ تدخّلات مختلفة (mtype + bkt_concept).
  • كل عقدة لها `mtype` من التصنيف الثلاثي + `bkt_concept` (لا عقدة بلا أثر).
  • السيناريو الحرفي للمالك + لا special-casing (فحص بنيوي) + صفر أرقام نهائية في التعريفات.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.infrastructure.clients.orchestrator.tutor_sources import read_tutor_source
from app.services.skills.semantic_property_skill import (
    MISCONCEPTION_GRAPH,
    MISCONCEPTION_TYPES,
    PROPERTY_REGISTRY,
    concept_for,
    get_semantic_property_skill,
)

ROOT = Path(__file__).resolve().parent.parent.parent


# ── الطبقة الدلالية: توجيه data-driven ────────────────────────────────────────
class TestPropertyInterpretation:
    def setup_method(self) -> None:
        self.skill = get_semantic_property_skill()

    def test_product_zero(self) -> None:
        out = self.skill.interpret("ماذا نقصد بجداء أرقامها معدوم؟")
        assert out is not None
        assert out.property_id == "product_zero"
        assert out.concept_id == "product_zero"
        assert out.domain == "arithmetic_property"
        assert "الرقم 0" in out.definition  # الجواب الصحيح: كرة واحدة على الأقل تحمل 0

    def test_product_odd(self) -> None:
        out = self.skill.interpret("ماذا نقصد بجداء فردي؟")
        assert out is not None and out.property_id == "product_odd"
        assert "كلها فردية" in out.definition

    def test_product_even(self) -> None:
        out = self.skill.interpret("ماذا نقصد بجداء زوجي؟")
        assert out is not None and out.property_id == "product_even"
        assert "زوجياً" in out.definition

    def test_same_color(self) -> None:
        out = self.skill.interpret("ماذا نقصد بالحادثة A؟")
        assert out is not None and out.property_id == "same_color"
        assert "نفس اللون" in out.definition

    def test_event_letters_route(self) -> None:
        assert self.skill.interpret("الحادثة D").property_id == "product_zero"
        assert self.skill.interpret("الحادثة B").property_id == "product_odd"
        assert self.skill.interpret("الحادثة C").property_id == "product_even"

    def test_no_match_returns_none(self) -> None:
        # سؤال عام بلا خاصية ⇒ None (الافتراض A يُطبَّق في cognitive response)
        assert self.skill.interpret("ما هو الطقس اليوم") is None

    def test_definitional_intent(self) -> None:
        assert self.skill.is_definitional("ماذا نقصد بجداء معدوم") is True
        assert self.skill.is_definitional("احسب احتمال الحادثة A") is False


# ── Misconception Graph: الثلاثة طلاب (القفزة) ────────────────────────────────
class TestMisconceptionGraph:
    def setup_method(self) -> None:
        self.skill = get_semantic_property_skill()

    def test_three_students_same_question_different_misconceptions(self) -> None:
        # نفس المفهوم (product_zero)، إجابات مختلفة ⇒ عقد مختلفة ⇒ تدخّلات مختلفة.
        s1 = self.skill.diagnose_misconception("product_zero", "لا أعرف ماذا يفعل الصفر في الضرب")
        s2 = self.skill.diagnose_misconception("product_zero", "هل الجداء يعني نجمع الأرقام؟")
        s3 = self.skill.diagnose_misconception("product_zero", "لا أعرف أي كرة تحمل الرقم 0")
        assert s1 is not None and s2 is not None and s3 is not None
        # عقد مختلفة
        assert {s1.node_id, s2.node_id, s3.node_id} == {
            "unknown_zero_property",
            "unknown_product_meaning",
            "unknown_ball_mapping",
        }
        # أنواع مختلفة (التصنيف الثلاثي)
        assert {s1.mtype, s2.mtype, s3.mtype} == {
            "rule_property",
            "symbol_meaning",
            "example_linking",
        }
        # تدخّلات مختلفة
        assert len({s1.intervention, s2.intervention, s3.intervention}) == 3
        # bkt_concept مختلف (لا عقدة بلا أثر)
        assert len({s1.bkt_concept, s2.bkt_concept, s3.bkt_concept}) == 3

    def test_ambiguous_returns_none_then_probe(self) -> None:
        # رد بلا إشارة واضحة ⇒ None ⇒ يُصدَر probe تشخيصي
        assert self.skill.diagnose_misconception("product_zero", "لا أعرف") is None
        probe = self.skill.first_probe("product_zero")
        assert probe and "؟" in probe

    def test_every_node_has_type_and_bkt_concept(self) -> None:
        for concept_id, nodes in MISCONCEPTION_GRAPH.items():
            for node in nodes:
                assert node.mtype in MISCONCEPTION_TYPES, f"{node.id}: bad mtype"
                assert node.bkt_concept, f"{node.id} ({concept_id}): no bkt_concept (no effect)"
                assert node.probe and node.intervention


class TestConceptMapping:
    def test_concept_for(self) -> None:
        assert concept_for("product_zero") == "product_zero"
        assert concept_for("same_color") == "event_meaning"
        assert concept_for("unknown") == "event_meaning"  # fallback


# ── السيناريو الحرفي للمالك + لا أرقام نهائية ─────────────────────────────────
class TestOwnerScenario:
    def test_owner_literal_question(self) -> None:
        # «ماذا نقصد بجداء أرقامها معدوم؟» ⇒ تعريف D الملموس، لا «نفس اللون» الخاطئ، لا حساب.
        out = get_semantic_property_skill().interpret("ماذا نقصد بجداء أرقامها معدوم؟")
        assert out is not None
        assert "نفس اللون" not in out.definition  # ليس تعريف A الخاطئ
        assert "الرقم 0" in out.definition

    def test_definitions_carry_no_final_probability(self) -> None:
        joined = " ".join(s.definition for s in PROPERTY_REGISTRY.values())
        assert not re.search(r"14\s*/\s*165|56\s*/\s*165", joined)


# ── لا special-casing + التوصيل (فحص بنيوي) ──────────────────────────────────
class TestNoSpecialCasing:
    def test_cognitive_response_single_semantic_call(self) -> None:
        # D-163: عقل الاحتمالات استُخرج للوحدة المستقلة — نضمّ الاثنين ليصمد أي pin.
        src = read_tutor_source()
        i = src.find('if concept == "event_meaning":')
        assert i != -1
        seg = src[i : i + 1400]
        # نداء واحد للطبقة الدلالية، لا فرع if/elif لكل حادثة B/C/D
        assert "get_semantic_property_skill" in seg
        assert seg.count("if ") <= 4

    def test_registry_registers_skill(self) -> None:
        from app.services.skills.registry import get_skill_registry

        d = get_skill_registry().get("semantic_property")
        assert d is not None
        assert d.status == "ACTIVE"
        assert d.consumed_by
        assert d.primary_method == "interpret"

    def test_manifest_consistent(self) -> None:
        from app.services.skills.doctrine import (
            SEMANTIC_PROPERTY_DOCTRINE,
            SEMANTIC_PROPERTY_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )

        entry = SKILL_DOCTRINE_MANIFEST["semantic_property"]
        assert entry["version"] == SEMANTIC_PROPERTY_DOCTRINE_VERSION
        assert entry["rules_count"] == len(SEMANTIC_PROPERTY_DOCTRINE)


# ── طبقة القياس السلوكي (§5) ──────────────────────────────────────────────────
class TestBehavioralMetrics:
    def test_metric_functions_exist_and_fail_open(self) -> None:
        from app.services.skills import tutor_metrics

        # fail-open: لا ترفع استثناءً أبداً
        tutor_metrics.record_repetition_avoided()
        tutor_metrics.record_definitional_answer("product_zero", True)
        tutor_metrics.record_intervention("rule_property")
        tutor_metrics.record_progress("advanced")


class TestBktClassification:
    def test_product_concepts_recognized(self) -> None:
        from app.services.skills.bkt_engine import classify_concept

        assert classify_concept("ماذا نقصد بجداء معدوم") == "product_zero"
        assert classify_concept("جداء فردي") == "product_odd"
        assert classify_concept("جداء زوجي") == "product_even"
