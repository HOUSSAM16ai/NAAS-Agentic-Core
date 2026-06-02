"""
مخططات محادثة العملاء القياسيين (Customer Chat Schemas).
"""

from pydantic import Field

from app.core.schemas import RobustBaseModel


class CustomerChatRequest(RobustBaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    conversation_id: int | None = None


class CustomerConversationSummary(RobustBaseModel):
    id: int
    conversation_id: int
    title: str
    created_at: str
    updated_at: str | None = None


class CustomerMessageOut(RobustBaseModel):
    role: str
    content: str
    created_at: str
    policy_flags: dict[str, str] | None = None
    # ISS-106 (D-WS-CARD-PERSIST-001): persisted generative-UI card, so it
    # re-renders after logout/login instead of disappearing.
    ui_component: dict | None = None


class CustomerConversationDetails(RobustBaseModel):
    conversation_id: int
    title: str
    messages: list[CustomerMessageOut]
