"""
Decision Kernel & Sovereignty.
------------------------------
This module defines the "Brain" of the architecture.
It centralizes the concept of a "Decision" to prevent Orchestration Drift.

Key Concepts:
- DecisionRecord: The immutable artifact of a choice.
- Policy: The logic that produces a Decision.
- Intent: The input triggering a decision.
"""

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import Field

from .contracts import GovernanceModel
from .errors import FailureClass

# Generic Input Type (The Context)
ContextT = TypeVar("ContextT", bound=GovernanceModel)
# Generic Output Type (The Action/Result)
ResultT = TypeVar("ResultT", bound=GovernanceModel)


class DecisionIntent(GovernanceModel):
    """
    Represents the "Why" - the trigger for a decision.
    """

    intent_key: str = Field(..., description="Unique key for this intent type")
    source: str = Field(..., description="Who requested this?")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DecisionRecord[ResultT](GovernanceModel):
    """
    The Immutable Artifact of a Decision.
    Traceable proof of why the system did what it did.
    """

    decision_id: str = Field(..., description="Unique ID for this specific decision instance")
    policy_name: str = Field(..., description="Name of the policy that made this decision")
    status: str = Field(..., description="Outcome status (e.g. SUCCESS, FAILED)")
    failure_class: FailureClass | None = Field(
        None, description="Taxonomy of failure if applicable"
    )
    result: ResultT | None = Field(None, description="The resulting action/value")
    reasoning: str = Field(..., description="Human-readable explanation of the choice")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Policy[ContextT, ResultT](ABC):
    """
    Abstract Base Class for all Decision Policies.
    A Policy is a pure function (conceptually) that maps Context -> Decision.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of this policy."""
        pass

    @abstractmethod
    def evaluate(self, context: ContextT) -> DecisionRecord[ResultT]:
        """
        Execute the policy logic.
        MUST NOT raise naked exceptions.
        MUST return a DecisionRecord with failure_class if things go wrong.
        """
        pass
