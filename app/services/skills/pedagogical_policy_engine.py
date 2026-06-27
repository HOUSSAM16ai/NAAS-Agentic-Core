from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.skills.dialogue_manager_skill import (
    DialogueInput,
    get_dialogue_manager_skill,
)

logger = logging.getLogger("cogniforge.skills.pedagogical_policy")


@dataclass
class PolicyObservation:
    """الملاحظات التي يجمعها المحرك التربوي من الدور الحالي."""

    question: str
    active_concept: str
    is_correct: bool = False
    is_frustrated: bool = False
    has_misconception: bool = False
    detected_misconception: str = ""


@dataclass
class PolicyDecision:
    """القرار التربوي النهائي."""

    next_action: str
    learning_stage: str
    representation: str
    focus: str | None
    reason: str


class PedagogicalPolicyEngine:
    """
    السلطة العليا للقرار التربوي.
    تنفذ خوارزمية: Observe -> Update State -> Estimate Mastery -> Choose Lowest Useful Intervention
    """

    def _estimate_mastery(self, obs: PolicyObservation, current_mastery: float) -> float:
        """يُقدّر الإتقان بناءً على الملاحظات الحالية."""
        delta = 0.0
        if obs.is_correct:
            delta += 0.2
        if obs.has_misconception:
            delta -= 0.15
        if obs.is_frustrated:
            delta -= 0.1

        new_mastery = current_mastery + delta
        return max(0.0, min(1.0, new_mastery))

    def _determine_learning_stage(self, mastery: float, state: dict[str, Any]) -> str:
        """يحدد المرحلة التعليمية بناءً على الإتقان والتدخلات السابقة لمنع التكرار (Architectural Guard)."""
        current_stage = state.get("learning_stage", "definition")
        interventions_used = state.get("interventions_used", [])
        dead_ends = state.get("dead_ends", [])

        stages = ["definition", "example", "procedure", "application", "assessment"]

        # If the current stage is a dead end or fully exhausted, force progression
        if (
            current_stage in dead_ends
            or len([i for i in interventions_used if i.startswith(current_stage)]) > 2
        ):
            current_idx = stages.index(current_stage) if current_stage in stages else 0
            if current_idx < len(stages) - 1:
                return stages[current_idx + 1]

        # Otherwise, map mastery to stage smoothly
        if mastery < 0.2:
            return "definition"
        if mastery < 0.4:
            return "example"
        if mastery < 0.6:
            return "procedure"
        if mastery < 0.8:
            return "application"
        return "assessment"

    def _choose_intervention(
        self, state: dict[str, Any], mastery: float, obs: PolicyObservation
    ) -> PolicyDecision:
        """يختار أقل تدخل مفيد بناءً على حالة الطالب وإتقانه."""
        learning_stage = self._determine_learning_stage(mastery, state)
        representation = "text"  # Default

        if obs.is_frustrated:
            representation = "micro_simulation"
        elif obs.has_misconception:
            representation = "analogy"

        # delegate to DialogueManagerSkill for the specific tactical action within the chosen stage
        dm_skill = get_dialogue_manager_skill()
        dm_input = DialogueInput(
            concept=obs.active_concept,
            ability=mastery,
            understood=obs.is_correct,
            verified_correct=obs.is_correct,
            socratic_count=int(
                state.get("socratic_count_by_concept", {}).get(obs.active_concept, 0)
            ),
            candidate_text="",  # Not evaluating candidate text here yet
            last_step_emitted=str(state.get("last_step_emitted", "")),
        )

        dm_decision = dm_skill.decide(dm_input)

        return PolicyDecision(
            next_action=dm_decision.action,
            learning_stage=learning_stage,
            representation=representation,
            focus=dm_decision.focus,
            reason=f"policy_engine_directed: {dm_decision.reason}",
        )

    def evaluate_turn(self, state: dict[str, Any], obs: PolicyObservation) -> PolicyDecision:
        """النقطة المركزية لتقييم الدور وإصدار القرار."""
        # 1. Observe (Already done, passed as obs)

        # 2. Estimate Mastery
        current_mastery = float(state.get("mastery_score", 0.0))
        new_mastery = self._estimate_mastery(obs, current_mastery)

        # 3. Choose Lowest Useful Intervention
        return self._choose_intervention(state, new_mastery, obs)

        # The Orchestrator Client will handle updating the state via TutorStateService.record_turn
        # based on this decision and the generated response.
