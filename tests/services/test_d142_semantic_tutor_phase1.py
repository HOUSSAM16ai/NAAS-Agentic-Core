"""
D-142 (Phase 1) — Surgical root-cause fixes for the "repeats / drifts / ignores
correct answers" probability-tutor catastrophe.

Replays the exact failing transcript signals through the real skills:
  1A: symbolic authority — a verifiably-correct answer ("الخضراء و الحمراء فقط",
      "لونين 2 فقط") evaluates understood=True even if the flaky LLM says False.
  1B: repetition guard — a near-duplicate of an already-emitted hint is detected so
      the caller escalates instead of repeating verbatim.
  1D: concept-drift guard — a bare confusion ("ماذا نقصد لم أفهم") keeps the active
      concept instead of resetting to "which concept?"; a newly-named concept resets.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from app.services.skills.semantic_property_skill import get_semantic_property_skill
from app.services.skills.socratic_evaluator_skill import (
    SocraticEvaluatorInput,
    SocraticEvaluatorSkill,
    deterministically_correct,
    get_socratic_evaluator_skill,
)


def _g(label: str, is_possible: bool):
    return type("G", (), {"label": label, "is_possible": is_possible})()


class _Combo:
    """Duck-typed CombinationsModelOutput for the orchestrator helpers."""

    n = 11
    k = 3
    total_combinations = 165
    same_group_favorable = 14
    groups: ClassVar = [
        _g("كرة حمراء", True),
        _g("كرة خضراء", True),
        _g("كرة بيضاء", False),
    ]


# ── 1A: deterministic symbolic authority ──────────────────────────────────────
class TestDeterministicCorrect:
    def test_transcript_correct_answers_are_verified(self):
        assert deterministically_correct("الخضراء و الحمراء فقط", "event_meaning") is True
        assert deterministically_correct("لونين 2 فقط", "event_meaning") is True
        assert deterministically_correct("الخضراء و الحمراء فقط", "numerator") is True

    def test_hamza_alef_robust(self):
        # «الأحمر/الأخضر» (with hamza) must match «احمر/اخضر» signals.
        assert deterministically_correct("نفس اللون الأحمر والأخضر", "color_white") is True

    def test_no_signal_is_false(self):
        assert deterministically_correct("لا أعرف", "event_meaning") is False
        assert deterministically_correct("", "event_meaning") is False

    def test_unverifiable_concept_defers_to_llm(self):
        # No symbolic verification available → False (let the LLM decide).
        assert deterministically_correct("المقام هو 165", "denominator") is False


@pytest.mark.asyncio
class TestEvaluatorSymbolicAuthority:
    async def test_verified_correct_overrides_flaky_llm_downgrade(self, monkeypatch):
        """The LLM saying understood=False must NOT override a verified-correct answer."""

        async def _fake_llm(cls, payload):
            return (False, "محاولة جيدة")  # flaky downgrade

        monkeypatch.setattr(SocraticEvaluatorSkill, "_evaluate_with_llm", classmethod(_fake_llm))
        out = await get_socratic_evaluator_skill().evaluate(
            SocraticEvaluatorInput(
                student_answer="الخضراء و الحمراء فقط",
                concept="event_meaning",
                verified_correct=True,
            )
        )
        assert out.understood is True

    async def test_verified_correct_via_fallback_when_llm_unavailable(self, monkeypatch):
        async def _no_llm(cls, payload):
            return None  # LLM unreachable → deterministic fallback

        monkeypatch.setattr(SocraticEvaluatorSkill, "_evaluate_with_llm", classmethod(_no_llm))
        out = await get_socratic_evaluator_skill().evaluate(
            SocraticEvaluatorInput(
                student_answer="لونين 2 فقط",
                concept="event_meaning",
                verified_correct=True,
            )
        )
        assert out.understood is True
        assert out.source == "fallback"

    async def test_llm_may_upgrade_unverified_answer(self, monkeypatch):
        async def _fake_llm(cls, payload):
            return (True, "")

        monkeypatch.setattr(SocraticEvaluatorSkill, "_evaluate_with_llm", classmethod(_fake_llm))
        out = await get_socratic_evaluator_skill().evaluate(
            SocraticEvaluatorInput(
                student_answer="ربما المقام", concept="denominator", verified_correct=False
            )
        )
        assert out.understood is True


# ── 1B: repetition guard + 1A combo verification (orchestrator helpers) ────────
class TestOrchestratorHelpers:
    def _client_cls(self):
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        return OrchestratorClient

    def test_verify_answer_against_combo(self):
        cls = self._client_cls()
        combo = _Combo()
        assert cls._verify_answer_against_combo("الخضراء و الحمراء فقط", combo) is True
        assert cls._verify_answer_against_combo("لونين 2 فقط", combo) is True
        assert cls._verify_answer_against_combo("احمر فقط", combo) is True
        assert cls._verify_answer_against_combo("لا أعرف", combo) is False

    def test_recently_emitted_detects_verbatim_repeat(self):
        cls = self._client_cls()
        hint = (
            "لاحظ نوع كل كرة: أيّ الألوان يكفي عددها لسحب 3 منها معاً؟ ابدأ بعدّ الألوان الممكنة فقط."
        )
        hist = [{"role": "assistant", "content": hint}]
        assert cls._recently_emitted(hint, hist) is True

    def test_recently_emitted_allows_distinct_text(self):
        cls = self._client_cls()
        hint = "ابدأ بعدّ الألوان الممكنة فقط."
        hist = [{"role": "assistant", "content": hint}]
        assert cls._recently_emitted(
            "ما هو المقام؟ كم طريقة لسحب ثلاث كرات من إحدى عشرة؟", hist
        ) is (False)

    def test_recently_emitted_empty_history(self):
        cls = self._client_cls()
        assert cls._recently_emitted("أي نص", []) is False
        assert cls._recently_emitted("أي نص", None) is False


# ── 1D: concept-drift guard ───────────────────────────────────────────────────
class TestConceptDriftGuard:
    def test_bare_confusion_is_detected(self):
        sp = get_semantic_property_skill()
        assert sp._is_bare_confusion_definitional("ماذا نقصد لم أفهم") is True
        assert sp._is_bare_confusion_definitional("لم أفهم") is True

    def test_named_concept_is_not_bare(self):
        sp = get_semantic_property_skill()
        assert sp._is_bare_confusion_definitional("ما هو الاحتمال الشرطي") is False
        assert sp._is_bare_confusion_definitional("ما معنى المتغير العشوائي") is False

    def test_bare_confusion_keeps_active_concept(self):
        sp = get_semantic_property_skill()
        hist = [
            {"role": "user", "content": "ما هو الاحتمال الشرطي"},
            {"role": "assistant", "content": "الاحتمال الشرطي هو احتمال حادثة بعلم وقوع أخرى."},
        ]
        res = sp.detect_active_concept("ماذا نقصد لم أفهم", hist)
        assert res is not None
        assert res.concept_id == "conditional_probability"

    def test_new_concept_does_not_drift_to_old(self):
        sp = get_semantic_property_skill()
        hist = [
            {"role": "user", "content": "ما هو الاحتمال الشرطي"},
            {"role": "assistant", "content": "الاحتمال الشرطي ..."},
        ]
        res = sp.detect_active_concept("ما هو المتغير العشوائي", hist)
        # Either resolves to random_variable or is handed to the LLM-Definer (None) —
        # but must NOT drift back to the previous concept.
        assert res is None or res.concept_id != "conditional_probability"
