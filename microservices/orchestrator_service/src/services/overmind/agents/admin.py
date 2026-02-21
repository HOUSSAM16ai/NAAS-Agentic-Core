"""
Admin Agent (Simplified for Microservice).
"""

from collections.abc import AsyncGenerator

from microservices.orchestrator_service.src.core.logging import get_logger
from microservices.orchestrator_service.src.services.llm.client import AIClient
from microservices.orchestrator_service.src.services.overmind.agents.data_access import (
    DataAccessAgent,
)
from microservices.orchestrator_service.src.services.overmind.agents.refactor import (
    RefactorAgent,
)
from microservices.orchestrator_service.src.services.overmind.utils.tools import ToolRegistry

logger = get_logger("admin-agent")


class AdminAgent:
    """
    Admin Agent Proxy.
    """

    def __init__(
        self,
        tools: ToolRegistry,
        ai_client: AIClient | None = None,
    ) -> None:
        self.tools = tools
        self.ai_client = ai_client
        self.data_agent = DataAccessAgent()
        self.refactor_agent = RefactorAgent()

    async def run(
        self,
        question: str,
        context: dict[str, object] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Handle admin queries.
        For now, returns a message indicating full admin capabilities are in the Monolith.
        """
        # We can implement basic code search if the tool is available
        if "بحث" in question or "search" in question.lower():
            yield "⚠️ البحث في الكود غير مدعوم بالكامل في هذه النسخة المصغرة بعد."
            # We could try self.tools.execute("code_search", ...) if available
            return

        yield "⚠️ أوامر الإدارة (Admin Commands) يجب تنفيذها من لوحة التحكم الرئيسية (Monolith) حالياً."
