"""
Overmind Domain Primitives.
---------------------------
Defines the core data structures and protocols for the Cognitive Domain.
Separating these allows for clean architecture and avoids circular dependencies.
"""

from typing import Protocol

from pydantic import BaseModel, Field

from microservices.orchestrator_service.src.services.overmind.domain.enums import CognitivePhase


# Protocol for event logging
class EventLogger(Protocol):
    async def __call__(self, event_type: str, payload: dict[str, object]) -> None: ...


class AgentUnitOfWork(BaseModel):
    """
    تمثيل الوكيل كوحدة عمل مستقلة يمكن قياسها وتتبّعها.

    يُستخدم هذا النموذج لتوحيد مخرجات الوكلاء وإبراز
    أن كل وكيل يعمل كوحدة عمل قابلة للمراقبة والقياس.
    """

    unit_id: str = Field(..., description="معرف وحدة العمل")
    agent: str = Field(..., description="اسم الوكيل المسؤول")
    phase: CognitivePhase = Field(..., description="المرحلة المعرفية المرتبطة")
    summary: str = Field(..., description="ملخص موجز لمهام الوحدة")
    input_keys: list[str] = Field(default_factory=list, description="مفاتيح المدخلات")
    output_keys: list[str] = Field(default_factory=list, description="مفاتيح المخرجات")
    status: str = Field(default="running", description="حالة التنفيذ")


class CognitiveCritique(BaseModel):
    """
    Model representing the result of a review/critique.
    """

    approved: bool = Field(..., description="Has the work been approved?")
    feedback: str = Field(..., description="Review feedback or rejection reasons")
    score: float = Field(0.0, description="Quality score from 0.0 to 1.0")


class CognitiveState(BaseModel):
    """
    Holds the current cognitive state of the mission.
    Acts as the 'Blackboard' for the Council of Wisdom.
    """

    mission_id: int
    objective: str
    plan: dict[str, object] | None = None
    design: dict[str, object] | None = None
    execution_result: dict[str, object] | None = None
    critique: CognitiveCritique | None = None
    iteration_count: int = Field(0, description="Current iteration count")
    max_iterations: int = Field(5, description="Maximum self-correction iterations")
    current_phase: CognitivePhase = CognitivePhase.PLANNING

    # Cumulative Memory for Loop Detection
    history_hashes: list[str] = Field(default_factory=list, description="History of plan hashes")
