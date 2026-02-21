from microservices.orchestrator_service.src.core.logging import get_logger
from microservices.orchestrator_service.src.services.overmind.agents.base import AgentResponse

logger = get_logger("data-access-agent")


class DataAccessAgent:
    """
    Checks data ownership and access paths.
    """

    async def process(self, input_data: dict[str, object]) -> AgentResponse:
        """
        Verifies that data access adheres to microservice boundaries.
        """
        entity = input_data.get("entity")
        operation = input_data.get("operation")
        access_method = input_data.get("access_method")
        purpose = input_data.get("purpose")

        logger.info(f"Checking data access for {entity}::{operation}")

        if entity == "user":
            # Enforce that User data must be accessed via User Service
            if access_method == "direct_db" and purpose != "admin_analytics":
                return AgentResponse(
                    success=False,
                    message="User data must be accessed via User Service API unless explicitly required for admin analytics.",
                )
            return AgentResponse(success=True, message="User access routed correctly.")

        return AgentResponse(success=True, message="Data access check passed.")
