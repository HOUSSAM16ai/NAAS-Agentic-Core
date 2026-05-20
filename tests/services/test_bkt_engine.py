"""اختبارات BKTEngine — Skill تتبّع المعرفة البايزي (Protocol V6.0)."""

from __future__ import annotations

import pytest

from app.services.skills.bkt_engine import (
    DEFAULT_P_L0,
    BKTEngine,
    BKTEvaluation,
    BKTEvaluationInput,
    classify_concept,
    estimate_cognitive_load,
    get_bkt_engine,
    infer_correctness_signal,
    update_mastery,
)


class TestClassifyConcept:
    def test_conditional_probability(self) -> None:
        assert classify_concept("احسب الاحتمال المشروط P(B بشرط A)") == "conditional_probability"

    def test_probability(self) -> None:
        assert classify_concept("ما هو احتمال الحادثة العشوائية؟") == "probability"

    def test_integration(self) -> None:
        assert classify_concept("احسب تكامل الدالة") == "integration"

    def test_derivatives(self) -> None:
        assert classify_concept("ما هي مشتقة الدالة f؟") == "derivatives"

    def test_limits(self) -> None:
        assert classify_concept("احسب نهاية الدالة عند اللانهاية") == "limits"

    def test_default_general(self) -> None:
        assert classify_concept("مرحبا كيف حالك") == "general"

    def test_empty(self) -> None:
        assert classify_concept("") == "general"


class TestCognitiveLoad:
    def test_low_for_short_simple(self) -> None:
        assert estimate_cognitive_load("ما هو التكامل؟") == "low"

    def test_high_for_advanced_terms(self) -> None:
        q = (
            "ادرس الدالة باستخدام مبرهنة لوبيتال ثم احسب التكامل بالتجزئة "
            "بالتفصيل خطوة بخطوة في الجزء أ والجزء ب" + "x" * 200
        )
        assert estimate_cognitive_load(q) == "high"

    def test_medium_for_detail_request(self) -> None:
        load = estimate_cognitive_load("اشرح لي بالتفصيل حل هذه المسألة الطويلة " + "x" * 180)
        assert load in {"medium", "high"}

    def test_empty_is_low(self) -> None:
        assert estimate_cognitive_load("") == "low"


class TestCorrectnessSignal:
    def test_confusion_is_false(self) -> None:
        assert infer_correctness_signal("ماذا نقصد بدالة أصلية؟") is False
        assert infer_correctness_signal("لا أفهم هذه الخطوة") is False
        assert infer_correctness_signal("اشرح لي") is False

    def test_mastery_is_true(self) -> None:
        assert infer_correctness_signal("أعتقد أن الحل هو 5 إذن النتيجة صحيحة") is True

    def test_default_false(self) -> None:
        assert infer_correctness_signal("تمرين") is False


class TestUpdateMastery:
    def test_correct_raises_mastery(self) -> None:
        prior = 0.3
        new = update_mastery(prior, correct=True)
        assert new > prior
        assert 0.0 <= new <= 1.0

    def test_incorrect_lowers_or_keeps_low(self) -> None:
        prior = 0.6
        new = update_mastery(prior, correct=False)
        # posterior after wrong answer must be below prior before transition lift
        assert new < prior
        assert 0.0 <= new <= 1.0

    def test_clamped_to_unit_interval(self) -> None:
        assert update_mastery(1.5, correct=True) <= 1.0
        assert update_mastery(-0.5, correct=False) >= 0.0

    def test_monotonic_accumulation_on_repeated_correct(self) -> None:
        m = DEFAULT_P_L0
        seq = []
        for _ in range(5):
            m = update_mastery(m, correct=True)
            seq.append(m)
        assert seq == sorted(seq)  # non-decreasing
        assert seq[-1] > DEFAULT_P_L0


class TestBKTEngine:
    def test_evaluate_returns_typed_output(self) -> None:
        engine = BKTEngine()
        result = engine.evaluate(
            BKTEvaluationInput(
                question="ارسم شجرة الاحتمالات بشرط الحادثة A واحتمال 0.3",
            )
        )
        assert isinstance(result, BKTEvaluation)
        assert result.concept_id == "conditional_probability"
        assert result.cognitive_load_estimate in {"low", "medium", "high"}
        assert 0.0 <= result.student_mastery_probability <= 1.0

    def test_prior_is_used(self) -> None:
        engine = BKTEngine()
        low_prior = engine.evaluate(
            BKTEvaluationInput(question="اشرح لي التكامل", prior_mastery=0.1)
        )
        high_prior = engine.evaluate(
            BKTEvaluationInput(question="اشرح لي التكامل", prior_mastery=0.8)
        )
        assert high_prior.student_mastery_probability > low_prior.student_mastery_probability

    def test_singleton(self) -> None:
        assert get_bkt_engine() is get_bkt_engine()

    def test_rejects_out_of_range_prior(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            BKTEvaluationInput(question="x", prior_mastery=1.5)
