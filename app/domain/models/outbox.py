from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlmodel import JSON, Field, SQLModel


class MissionOutbox(SQLModel, table=True):
    """
    Transactional Outbox for reliable event publishing.
    """

    __tablename__ = "mission_outbox"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    event_type: str = Field(index=True)
    payload: dict[str, Any] = Field(sa_type=JSON)
    status: str = Field(default="PENDING", index=True)  # PENDING, PROCESSED, FAILED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: datetime | None = Field(default=None)
    retry_count: int = Field(default=0)
