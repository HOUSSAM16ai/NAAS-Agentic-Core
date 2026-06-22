"""
D-132 — Generalized Concept Understanding (ready for new questions) regression tests.

يثبت:
  • تغطية مفاهيم التمرين الأخرى (random_variable/expected_value/conditional) بتعريفات حتمية.
  • السيناريو الحرفي للمالك: «ماذا نقصد بالمتغير العشوائي» ⇒ تعريف X (لا «نفس اللون» الخاطئ).
  • `interpret_or_define` + `define_concept` (الـ LLM Listener-Definer للأسئلة الجديدة).
  • فحص بنيوي: لا default `same_color`/`event_meaning` مُجمَّد؛ preempt يسبق الالتقاط السقراطي.
  • metric `source` label.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.services.skills.semantic_property_skill import (
    PROPERTY_REGISTRY,
    get_semantic_property_skill,
)

ROOT = Path(__file__).resolve().parent.parent.parent


class TestExerciseConceptCoverage:
    def setup_method(self) -> None:
        self.skill = get_semantic_property_skill()

    def test_random_variable(self) -> None:
        out = self.skill.interpret("ماذا نقصد بالمتغير العشوائي")
        assert out is not None
        assert out.property_id == "random_variable"
        assert out.concept_id == "random_variable"
        # تعريف المالك: قاعدة تُعطي لكل نتيجة عدداً؛ X = عدد الكرات الزوجية
        assert "قاعدة" in out.definition and "زوجي" in out.definition
        assert "نفس اللون" not in out.definition  # ليس تعريف A الخاطئ

    def test_expected_value(self) -> None:
        out = self.skill.interpret("ماذا نقصد بالأمل الرياضي")
        assert out is not None and out.property_id == "expected_value"
        assert "متوسط" in out.definition or "المتوقَّعة" in out.definition

    def test_conditional_probability(self) -> None:
        out = self.skill.interpret("ماذا نقصد بالاحتمال الشرطي")
        assert out is not None and out.property_id == "conditional_probability"
        assert "بعلم" in out.definition or "بشرط" in out.definition

    def test_confusion_about_named_concept(self) -> None:
        # «لم افهم المتغير العشوائي» ⇒ interpret يجد random_variable (لا «نفس اللون»).
        out = self.skill.interpret("لم افهم المتغير العشوائي")
        assert out is not None and out.property_id == "random_variable"

    def test_random_variable_never_same_color(self) -> None:
        for q in ("ماذا نقصد بالمتغير العشوائي", "لم افهم المتغير العشوائي", "المتغير العشوائي X"):
            out = self.skill.interpret(q)
            assert out is not None and out.property_id != "same_color"


class TestInterpretOrDefine:
    def setup_method(self) -> None:
        self.skill = get_semantic_property_skill()

    def test_definitions_carry_no_final_probability(self) -> None:
        joined = " ".join(s.definition for s in PROPERTY_REGISTRY.values())
        assert not re.search(r"14\s*/\s*165|56\s*/\s*165", joined)

    def test_methods_exist(self) -> None:
        assert hasattr(self.skill, "interpret_or_define")
        assert hasattr(self.skill, "define_concept")


# ── فحص بنيوي: لا default مُجمَّد + ترتيب preempt ────────────────────────────
class TestNoFrozenDefault:
    def _client(self) -> str:
        return (ROOT / "app/infrastructure/clients/orchestrator_client.py").read_text(
            encoding="utf-8"
        )

    def test_definitional_preempt_precedes_socratic(self) -> None:
        src = self._client()
        defp = src.find("interpret_or_define(question)")
        socp = src.find("_in_socratic_dialogue(question")
        assert defp != -1 and socp != -1
        assert defp < socp, "definitional preempt must precede socratic capture (D-132)"

    def test_event_meaning_same_color_is_conditional(self) -> None:
        src = self._client()
        i = src.find('if concept == "event_meaning":')
        assert i != -1
        seg = src[i : i + 1500]
        # الافتراض A مشروط بسؤال حدثي صريح، لا default مُجمَّد (D-132 قاعدة 3)
        assert "any(m in _q" in seg

    def test_skill_has_definer_with_guard(self) -> None:
        skill = (ROOT / "app/services/skills/semantic_property_skill.py").read_text(
            encoding="utf-8"
        )
        assert "def define_concept" in skill
        assert "redact_final_answers" in skill  # سقف الـ LLM: محروس

    def test_no_regression_d130_order(self) -> None:
        src = self._client()
        # D-130: socratic capture still before indexed retrieval (D-137: `self.`-form, lf-robust)
        assert src.find("self._in_socratic_dialogue(") < src.find("self._has_indexed_match(")

    def test_metric_source_label(self) -> None:
        from app.services.skills import tutor_metrics

        # fail-open + source label
        tutor_metrics.record_definitional_answer("random_variable", True, source="deterministic")
        tutor_metrics.record_definitional_answer("novel", True, source="llm")


class TestDoctrine:
    def test_version_bumped(self) -> None:
        from app.services.skills.doctrine import (
            SEMANTIC_PROPERTY_DOCTRINE,
            SEMANTIC_PROPERTY_DOCTRINE_VERSION,
            SKILL_DOCTRINE_MANIFEST,
        )

        # D-137: السجلّ تطوّر (1.1.0 → 1.2.0 D-136 → 1.3.0 D-137) — نتحقّق ≥ 1.1.0 + الاتّساق.
        major, minor, *_ = (int(x) for x in SEMANTIC_PROPERTY_DOCTRINE_VERSION.split("."))
        assert (major, minor) >= (1, 1)
        entry = SKILL_DOCTRINE_MANIFEST["semantic_property"]
        assert entry["version"] == SEMANTIC_PROPERTY_DOCTRINE_VERSION
        assert entry["rules_count"] == len(SEMANTIC_PROPERTY_DOCTRINE)
