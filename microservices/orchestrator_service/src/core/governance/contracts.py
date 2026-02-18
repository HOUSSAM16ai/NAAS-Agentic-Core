"""
Governance Contracts & Strict Schemas.
--------------------------------------
This module defines the "Immune System" of the architecture.
It provides base Pydantic models that strictly forbid:
1. `Any` (Implicitly, by encouraging typed fields)
2. Extra fields (preventing payload drift)
3. Loose validation

Usage:
All Decision Records, Policies, and Inter-Agent Messages must inherit from GovernanceModel.
"""

from typing import TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class GovernanceModel(BaseModel):
    """
    The Base Model for all Governed Data Structures.
    Enforces strict typing and forbids extra fields to prevent "Contract Drift".
    """

    model_config = ConfigDict(
        extra="forbid",  # Crash if extra fields are sent (Fail Fast)
        strict=True,  # No implicit type coercion (e.g. "123" -> 123)
        validate_assignment=True,
        frozen=True,  # Decisions should be immutable once made
    )


class TolerantGovernanceModel(BaseModel):
    """
    A variant of GovernanceModel for external inputs where we must follow Postel's Law:
    "Be conservative in what you do, be liberal in what you accept from others."

    Used for: Parsing external API responses or Legacy inputs.
    """

    model_config = ConfigDict(
        extra="ignore",
        strict=False,
        frozen=True,
    )
