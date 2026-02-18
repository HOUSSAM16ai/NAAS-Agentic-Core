# app/services/overmind/domain/enums.py
"""
Enumerations for the Overmind Domain.
Addresses Meaning Connascence by centralizing string literals.
"""

from enum import StrEnum


class CognitivePhase(StrEnum):
    """Phases of the SuperBrain cognitive loop."""

    PLANNING = "PLANNING"
    REVIEW_PLAN = "REVIEW_PLAN"
    DESIGN = "DESIGN"
    EXECUTION = "EXECUTION"
    REFLECTION = "REFLECTION"
    RE_PLANNING = "RE-PLANNING"


class OvermindMessage(StrEnum):
    """Standard status messages for Overmind operations."""

    CONVENING_COUNCIL = "Council of Wisdom Convening"
    MISSION_ACCOMPLISHED = "Mission Accomplished by Super Agent"
    AI_SERVICE_UNAVAILABLE = "AI service unavailable. Please configure OPENROUTER_API_KEY."


class CognitiveEvent(StrEnum):
    """Event types for internal cognitive logging."""

    LOOP_START = "loop_start"
    PLAN_REJECTED = "plan_rejected"
    PLAN_APPROVED = "plan_approved"
    MISSION_SUCCESS = "mission_success"
    MISSION_CRITIQUE_FAILED = "mission_critique_failed"
    PHASE_ERROR = "phase_error"
    PHASE_START = "phase_start"
