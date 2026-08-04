"""D-226 — التدخّل يستهدف الجذر عبر **رسم المنهاج**، لا طبقةً واحدة منه.

## العطب المقيس

`diagnose_root` هو محرّك «التدخّل يستهدف الجذر لا العرَض» (D-159)، وكان يقرأ
`MISCONCEPTION_EDGES` وحدها: **عشر** حوافّ من طبقة الاحتمالات الدقيقة. أمّا
`shared/curriculum` فيحمل **ستّاً وعشرين** حافّة شرطٍ مسبق حقيقية — والتقاطع بين
المجموعتين كان **صفراً**.

فكان المحرّك أعمى بنيويّاً عن السلسلة التي وُجد لأجلها:

    limits → derivatives → numerical_functions → exponential → logarithm

طالبٌ يتعثّر في اللوغاريتم في آخر السنة وجذرُ عطبه في النهايات في أوّلها، كان يتلقّى
`None` — لا لأن الجذر غير موجود، بل لأن الحافّة تعيش في الرسم الذي لا يقرؤه.
"""

from __future__ import annotations

import pytest

from app.services.skills.semantic_property_skill import diagnose_root

WEAK = {"state": "explained", "evidence": "unverified"}


class TestCurriculumChain:
    def test_root_is_found_four_hops_back(self) -> None:
        """الحالة التي كانت تُرجِع `None`: تعثّرٌ متأخّر وجذرٌ مبكر."""
        result = diagnose_root("logarithm", {"limits": WEAK})
        assert result is not None
        assert result.root_concept_id == "limits"

    def test_the_intervention_names_the_root_in_arabic(self) -> None:
        result = diagnose_root("logarithm", {"limits": WEAK})
        assert result is not None
        assert "النهايات" in result.intervention_text

    def test_no_definition_means_a_question_not_an_invented_explanation(self) -> None:
        """⛔ لا يُخترَع شرحٌ لمفهومٍ بلا نصّ تدخّل — يُسمّى الجذر ويُسأل الطالب (§0)."""
        result = diagnose_root("logarithm", {"limits": WEAK})
        assert result is not None
        assert "ما الذي تتذكّره" in result.intervention_text

    def test_one_hop_still_works(self) -> None:
        assert diagnose_root("derivatives", {"limits": WEAK}) is not None

    @pytest.mark.parametrize(
        ("concept", "weak_root"),
        [
            # acid_base ← chemical_equilibrium ← chemical_kinetics
            ("acid_base", "chemical_kinetics"),
            # differential_equations ← integration ← numerical_functions ← derivatives ← limits
            ("differential_equations", "limits"),
            # electric_field_motion ← mechanics_newton
            ("electric_field_motion", "mechanics_newton"),
        ],
    )
    def test_other_subjects_traverse_too(self, concept: str, weak_root: str) -> None:
        """الفيزياء والعلوم لا تُستثنى — الرسم واحد لكل المواد."""
        result = diagnose_root(concept, {weak_root: WEAK})
        assert result is not None
        assert result.root_concept_id == weak_root


class TestNoRegression:
    def test_the_micro_probability_layer_still_works(self) -> None:
        """الرسمان يعملان على حبيبتين مختلفتين — والاتّحاد لا يُلغي أيّاً منهما."""
        result = diagnose_root("conditional_probability", {"event_meaning": WEAK})
        assert result is not None
        assert result.root_concept_id == "event_meaning"

    def test_a_concept_with_no_weak_prerequisite_gets_no_intervention(self) -> None:
        """⛔ لا تدخّل أعمى: مفهومٌ بلا سجلٍّ ليس «ضعيفاً» (D-159)."""
        assert (
            diagnose_root("logarithm", {"limits": {"state": "explained", "evidence": "verified"}})
            is None
        )
        assert diagnose_root("logarithm", {}) is None

    def test_an_unknown_concept_degrades_quietly(self) -> None:
        """مفهومٌ لا يعرفه أيّ رسم ⇒ `None` بلا رفع (fail-open — مسار طالب)."""
        assert diagnose_root("not_a_real_concept", {"limits": WEAK}) is None

    def test_a_cycle_cannot_hang_the_traversal(self) -> None:
        assert diagnose_root("limits", {"limits": WEAK}) is None
