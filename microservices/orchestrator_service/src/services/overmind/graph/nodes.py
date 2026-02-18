from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from enum import Enum

from microservices.orchestrator_service.src.core.ai_gateway import AIClient, get_ai_client

logger = logging.getLogger(__name__)


class AgentState(Enum):
    IDLE = "IDLE"
    WORKING = "WORKING"
    WAITING = "WAITING"
    ERROR = "ERROR"


@dataclass
class AgentMessage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    target_id: str = ""
    content: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)


class AgentNode:
    """
    Represents an Autonomous Agent Node in the Decentralized Graph.
    Part of Pillar 3: Decentralized Multi-Agent Graph Architecture.
    """

    def __init__(self, agent_id: str, role: str, description: str):
        self.agent_id = agent_id
        self.role = role
        self.description = description
        self.state = AgentState.IDLE
        self.inbox: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self.ai_client: AIClient = get_ai_client()
        self.neighbors: list[str] = []  # IDs of connected agents

    def connect(self, other_agent_id: str) -> None:
        """Connects this agent to another agent in the graph."""
        if other_agent_id not in self.neighbors:
            self.neighbors.append(other_agent_id)

    async def receive(self, message: AgentMessage) -> None:
        """Receives a message into the inbox."""
        await self.inbox.put(message)

    async def process_next(self) -> AgentMessage | None:
        """Processes the next message in the inbox."""
        if self.inbox.empty():
            return None

        self.state = AgentState.WORKING
        message = await self.inbox.get()

        try:
            result = await self._execute_core_logic(message)
            self.state = AgentState.IDLE
            return result
        except Exception as e:
            logger.error(f"Agent {self.agent_id} failed to process message: {e}")
            self.state = AgentState.ERROR
            return None

    async def _execute_core_logic(self, message: AgentMessage) -> AgentMessage:
        """
        The 'Brain' of the agent.
        In a full implementation, this would use the AI Client to decide actions.
        For the foundation, we implement a simple echo/pass-through or basic LLM call.
        """
        logger.info(f"Agent [{self.agent_id}] processing: {message.content.get('task')}")

        # Simple simulation of work
        response_content = {
            "processed_by": self.agent_id,
            "original_task": message.content.get("task"),
            "status": "completed",
            "output": f"Processed {message.content.get('task')} via {self.role}",
        }

        return AgentMessage(
            sender_id=self.agent_id,
            target_id=message.sender_id,  # Reply back
            content=response_content,
        )
