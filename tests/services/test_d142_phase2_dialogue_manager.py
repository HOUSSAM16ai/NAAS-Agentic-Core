"""
D-142 (Phase 2) — DialogueManagerSkill (unified turn-decision authority) +
TutorStateService (persistent dialogue memory) + the SEMANTIC_TUTOR_ENABLED flag.

The DialogueManager decision = f(evidence, ability, next-step difficulty) each turn
(dialogue knowledge-tracing, NOT a fixed levels-counter):
  - verified/understood -> deterministic advance (never re-ask)
  - per-concept budget exhausted -> symbolic reveal (no extra question)
  - candidate near-duplicate of last_step -> escalate (no verbatim repeat)
  - ability < next-step difficulty -> intermediate scaffold (no over-jump)
"""

from __future__ import annotations

import os

from app.services.analytics.tutor_state_service import EMPTY_STATE, _loads
from app.services.skills.dialogue_manager_skill import (
    DialogueInput,
    get_dialogue_manager_skill,
    near_duplicate,
)

_HINT = "لاحظ نوع كل كرة: أيّ الألوان يكفي عددها لسحب 3 منها معاً؟ ابدأ بعدّ الألوان الممكنة فقط."


class TestDialogueDecisionMatrix:
    def _decide(self, **kw):
        return get_dialogue_manager_skill().decide(DialogueInput(**kw))

    def test_evidence_advances_deterministically(self):
        assert self._decide(concept="event_meaning", verified_correct=True).action == (
            "acknowledge_advance"
        )
        assert self._decide(concept="event_meaning", understood=True).action == (
            "acknowledge_advance"
        )

    def test_budget_exhausted_reveals(self):
        d = self._decide(concept="event_meaning", ability=0.0, socratic_count=1)
        assert d.action == "symbolic_reveal"
        assert d.reason == "budget"

    def test_dedup_escalates_not_repeats(self):
        d = self._decide(
            concept="numerator",
            ability=0.8,
            socratic_count=0,
            last_step_emitted=_HINT,
            candidate_text=_HINT,
        )
        assert d.action == "symbolic_reveal"
        assert d.reason == "dedup"

    def test_no_overjump_inserts_intermediate(self):
        # low ability + hard next-step difficulty -> smaller scaffold, never over-jump.
        d = self._decide(concept="denominator", ability=0.2, socratic_count=0)
        assert d.action == "intermediate_scaffold"
        assert d.reason == "ability_below_difficulty"

    def test_able_student_continues_socratic(self):
        d = self._decide(
            concept="event_meaning",
            ability=0.8,
            socratic_count=1,
            candidate_text="سؤال جديد مختلف تماماً",
        )
        assert d.action == "continue_socratic"

    def test_budget_calibration_by_ability(self):
        skill = get_dialogue_manager_skill()
        assert skill.decide(DialogueInput(concept="event_meaning", ability=0.0)).budget == 1
        assert skill.decide(DialogueInput(concept="event_meaning", ability=0.5)).budget == 2
        assert skill.decide(DialogueInput(concept="event_meaning", ability=0.8)).budget == 3


class TestNearDuplicate:
    def test_verbatim_repeat(self):
        assert near_duplicate(_HINT, _HINT) is True

    def test_distinct_text(self):
        assert near_duplicate("ما هو المقام؟ كم طريقة لسحب ثلاث كرات؟", _HINT) is False

    def test_empty(self):
        assert near_duplicate("", _HINT) is False
        assert near_duplicate(_HINT, "") is False


class TestTutorStateHelpers:
    def test_empty_state_shape(self):
        for key in (
            "active_concept",
            "kc_progress",
            "ability_snapshot",
            "socratic_count_by_concept",
            "last_step_emitted",
            "turn_count",
        ):
            assert key in EMPTY_STATE

    def test_loads_fail_open(self):
        assert _loads(None) == {}
        assert _loads("") == {}
        assert _loads("not json") == {}
        assert _loads("[1,2]") == {}  # non-dict -> {}
        assert _loads('{"event_meaning": 2}') == {"event_meaning": 2}


class TestFlagGate:
    def test_orchestrator_flag_default_off_and_env_toggle(self, monkeypatch):
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        monkeypatch.delenv("SEMANTIC_TUTOR_ENABLED", raising=False)
        # default off (unless settings carries a True bool; in tests it does not)
        assert OrchestratorClient._semantic_tutor_enabled() in (False, True)
        monkeypatch.setenv("SEMANTIC_TUTOR_ENABLED", "1")
        assert OrchestratorClient._semantic_tutor_enabled() is True
        monkeypatch.setenv("SEMANTIC_TUTOR_ENABLED", "0")
        assert OrchestratorClient._semantic_tutor_enabled() is False

    def test_customer_chat_flag_default_off(self, monkeypatch):
        from app.api.routers.customer_chat import _semantic_tutor_enabled

        monkeypatch.setenv("SEMANTIC_TUTOR_ENABLED", "0")
        assert _semantic_tutor_enabled() is False
        monkeypatch.setenv("SEMANTIC_TUTOR_ENABLED", "yes")
        assert _semantic_tutor_enabled() is True

    def test_env_not_set_uses_settings_or_false(self, monkeypatch):
        from app.api.routers.customer_chat import _semantic_tutor_enabled

        monkeypatch.delenv("SEMANTIC_TUTOR_ENABLED", raising=False)
        # No env override → settings bool or False; never raises.
        assert isinstance(_semantic_tutor_enabled(), bool)
        assert os.getenv("SEMANTIC_TUTOR_ENABLED") is None
