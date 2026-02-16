from uuid import UUID, uuid4
from typing import Optional

from sqlmodel import JSON, Field, SQLModel
from pydantic import BaseModel


class PlanStep(BaseModel):
    """
    خطوة واحدة في الخطة الاستراتيجية.
    """
    name: str
    description: str
    tool_hint: Optional[str] = None


class Plan(SQLModel, table=True):
    """
    نموذج الخطة الاستراتيجية لقاعدة البيانات.
    """

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    goal: str = Field(index=True)
    strategy_name: str = Field(default="Strategic Plan")
    reasoning: str = Field(default="")
    steps: list[dict] = Field(default_factory=list, sa_type=JSON)  # Stores list[PlanStep] as dicts
