"""
Connection Manager Module.
Part of the Atomic Modularization Protocol.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

BASE_TIMEOUT = 30.0


class ConnectionManager:
    """
    Manages a singleton HTTP client to ensure TCP connection reuse.
    """

    _instance: httpx.AsyncClient | None = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        if cls._instance is None or cls._instance.is_closed:
            logger.info("Initializing new global AI HTTP Client.")
            cls._instance = httpx.AsyncClient(
                timeout=httpx.Timeout(BASE_TIMEOUT, connect=10.0),
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            )
        return cls._instance

    @classmethod
    async def close(cls) -> None:
        if cls._instance and not cls._instance.is_closed:
            await cls._instance.aclose()
