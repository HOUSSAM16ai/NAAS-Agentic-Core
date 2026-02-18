"""
Orchestrator Service Client.
Provides a typed interface to the Orchestrator (Overmind) Microservice.
Decouples the Monolith from the Orchestration Logic, resolving Split-Brain architecture.
"""

from __future__ import annotations

from typing import Any, Final

import httpx

from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.logging import get_logger
from app.core.settings.base import get_settings

logger = get_logger("orchestrator-client")

DEFAULT_ORCHESTRATOR_URL: Final[str] = "http://orchestrator-service:8000"


class OrchestratorClient:
    """
    Client for interacting with the Orchestrator (Overmind) microservice.
    Uses the central HTTPClientFactory for connection pooling and configuration.
    """

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        # Fallback logic: Argument -> Settings -> Default
        resolved_url = base_url or settings.ORCHESTRATOR_SERVICE_URL or DEFAULT_ORCHESTRATOR_URL
        self.base_url = resolved_url.rstrip("/")

        # Configure the client via the factory pattern
        self.config = HTTPClientConfig(
            name="orchestrator-client",
            timeout=60.0,
            max_connections=50,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        return get_http_client(self.config)

    async def create_mission(
        self,
        objective: str,
        initiator_id: int,
        context: dict[str, Any] | None = None,
        force_research: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """
        Start a new mission via the Orchestrator Service.

        Args:
            objective: The mission objective.
            initiator_id: The ID of the user initiating the mission.
            context: Optional context dictionary.
            force_research: Flag to force research mode (passed in context).
            idempotency_key: Optional key to ensure idempotency (X-Correlation-ID).

        Returns:
            dict: The created Mission object (JSON response).
        """
        url = f"{self.base_url}/missions"

        # Prepare context
        safe_context = context or {}
        if force_research:
            safe_context["force_research"] = True

        payload = {
            "objective": objective,
            "context": safe_context,
            # Note: initiator_id is currently not accepted by the microservice body schema
            # but we pass it for forward compatibility if schema updates.
            # "initiator_id": initiator_id
        }

        headers = {}
        if idempotency_key:
            headers["X-Correlation-ID"] = idempotency_key

        # Add Service Token for Security (Zero Trust)
        # Ideally we generate a token here, but for now we rely on the network or Gateway.
        # If we need to sign tokens, we need 'app.core.security' or similar.
        # Given 'app' is the Monolith, it has access to SECRET_KEY.

        client = await self._get_client()
        try:
            logger.info(f"Dispatching mission to Orchestrator: {objective[:50]}...")
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

            return response.json()

        except Exception as e:
            logger.error(f"Orchestrator dispatch failed: {e}", exc_info=True)
            raise


# Singleton instance
orchestrator_client = OrchestratorClient()
