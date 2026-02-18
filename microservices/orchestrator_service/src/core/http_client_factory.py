"""
HTTP CLIENT FACTORY — CENTRALIZED HTTP CLIENT MANAGEMENT
=========================================================

Single source of truth for HTTP client creation and management.
Eliminates the 8 duplicate HTTP client implementations found in:
- app/core/ai_gateway.py
- app/core/rate_limiter.py
- app/core/superhuman_performance_optimizer.py
- app/services/ai_model_metrics_service.py
- app/services/api_config_secrets_service.py
- app/services/api_developer_portal_service.py
- app/services/distributed_resilience_service.py
- app/services/llm_client_service.py

RESPONSIBILITIES:
✅ HTTP client creation and pooling
✅ Connection management and reuse
✅ Timeout configuration
✅ Header management

DOES NOT:
❌ Implement retry logic (see resilience module)
❌ Implement circuit breakers (see resilience module)
❌ Implement telemetry (see observability)
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Thread-safe singleton management
_CLIENT_LOCK = threading.Lock()
_HTTP_CLIENTS: dict[str, object] = {}


@dataclass
class HTTPClientConfig:
    """
    HTTP Client Configuration Object.
    تكوين عميل HTTP - يتبع Config Object Pattern.

    Replaces 6 parameters with a single config object (KISS + SOLID).
    """

    name: str = "default"
    timeout: float = 30.0
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    use_cache: bool = True

    def get_cache_key(self) -> str:
        """Generate cache key for this config."""
        return f"{self.name}:{self.timeout}:{self.max_connections}"


class HTTPClientFactory:
    """
    Factory for creating and managing HTTP clients.

    Provides connection pooling and reuse for better performance.
    """

    @staticmethod
    def create_client(
        config: HTTPClientConfig | None = None, **kwargs
    ) -> dict[str, str | int | bool]:
        """
        Create or retrieve an HTTP client.
        إنشاء أو استرجاع عميل HTTP.

        Args:
            config: HTTP client configuration object
            **kwargs: Individual parameters (for backward compatibility)

        Returns:
            HTTP client instance (httpx.AsyncClient)
        """
        # Create config from kwargs if not provided
        if config is None:
            config = HTTPClientConfig(**kwargs) if kwargs else HTTPClientConfig()

        cache_key = config.get_cache_key()

        # Check cache first
        cached_client = HTTPClientFactory._get_cached_client(cache_key, config)
        if cached_client is not None:
            return cached_client

        # Create new client with thread safety
        return HTTPClientFactory._create_new_client(config, cache_key)

    @staticmethod
    def _get_cached_client(cache_key: str, config: HTTPClientConfig) -> object | None:
        """
        Get cached HTTP client if available and caching is enabled.
        استرجاع عميل HTTP من الذاكرة المؤقتة.
        """
        if config.use_cache and cache_key in _HTTP_CLIENTS:
            logger.debug(f"Returning cached HTTP client '{config.name}'")
            return _HTTP_CLIENTS[cache_key]
        return None

    @staticmethod
    def _create_new_client(config: HTTPClientConfig, cache_key: str) -> object:
        """
        Create a new HTTP client with thread-safe locking.
        إنشاء عميل HTTP جديد بأمان.
        """
        with _CLIENT_LOCK:
            # Double-check after acquiring lock
            cached = HTTPClientFactory._get_cached_client(cache_key, config)
            if cached is not None:
                return cached

            # Create and configure client
            client = HTTPClientFactory._build_http_client(config)

            # Cache if enabled
            if config.use_cache:
                _HTTP_CLIENTS[cache_key] = client

            HTTPClientFactory._log_client_creation(config)
            return client

    @staticmethod
    def _build_http_client(config: HTTPClientConfig) -> object:
        """
        Build httpx client with configuration.
        بناء عميل httpx بالإعدادات المحددة.
        """
        try:
            import httpx

            limits = httpx.Limits(
                max_connections=config.max_connections,
                max_keepalive_connections=config.max_keepalive_connections,
                keepalive_expiry=config.keepalive_expiry,
            )

            return httpx.AsyncClient(
                timeout=httpx.Timeout(config.timeout),
                limits=limits,
                follow_redirects=True,
            )

        except ImportError:
            logger.error("httpx not available, cannot create HTTP client")
            return HTTPClientFactory._create_mock_http_client(config.name)

    @staticmethod
    def _log_client_creation(config: HTTPClientConfig) -> None:
        """Log HTTP client creation."""
        logger.info(
            f"Created HTTP client '{config.name}' with timeout={config.timeout}s, "
            f"max_connections={config.max_connections}"
        )

    @staticmethod
    async def close_client(name: str = "default") -> None:
        """Close a specific HTTP client"""
        # More efficient: find keys directly without creating list
        with _CLIENT_LOCK:
            keys_to_remove = [k for k in _HTTP_CLIENTS if k.startswith(f"{name}:")]

            for key in keys_to_remove:
                client = _HTTP_CLIENTS.pop(key, None)
                if client:
                    try:
                        await client.aclose()
                        logger.info(f"Closed HTTP client '{key}'")
                    except Exception as e:
                        logger.error(f"Error closing HTTP client '{key}': {e}")

    @staticmethod
    async def close_all() -> None:
        """Close all HTTP clients"""
        with _CLIENT_LOCK:
            for key, client in list(_HTTP_CLIENTS.items()):
                try:
                    await client.aclose()
                    logger.debug(f"Closed HTTP client '{key}'")
                except Exception as e:
                    logger.error(f"Error closing HTTP client '{key}': {e}")

            _HTTP_CLIENTS.clear()
            logger.info("All HTTP clients closed")

    @staticmethod
    def get_cached_clients() -> dict[str, object]:
        """Get information about cached clients"""
        return {key: {"created": True} for key in _HTTP_CLIENTS}

    @staticmethod
    def _create_mock_http_client(name: str) -> dict[str, str | int | bool]:
        """Create a mock HTTP client for testing/development when httpx unavailable"""

        class MockHTTPClient:
            """Mock HTTP client for development"""

            def __init__(self, name: str):
                self.name = name
                self._closed = False
                self._is_mock_client = True  # Protocol marker for detection

            async def get(self, url: str, **kwargs) -> None:
                """Mock GET request"""
                raise RuntimeError("httpx not available - mock client only")

            async def post(self, url: str, **kwargs) -> None:
                """Mock POST request"""
                raise RuntimeError("httpx not available - mock client only")

            async def aclose(self) -> None:
                """Mock close"""
                self._closed = True

            def __repr__(self):
                return f"MockHTTPClient(name={self.name})"

        return MockHTTPClient(name)


# =============================================================================
# PUBLIC API
# =============================================================================


def get_http_client(
    config: HTTPClientConfig | None = None, **kwargs
) -> dict[str, str | int | bool]:
    """
    Get an HTTP client instance.
    الحصول على عميل HTTP.

    This is the primary function to use for obtaining HTTP clients
    throughout the application.

    Args:
        config: HTTP client configuration object (recommended)
        **kwargs: Individual parameters (for backward compatibility):
            - name: Unique name for the client
            - timeout: Request timeout in seconds
            - max_connections: Maximum number of connections
            - max_keepalive_connections: Maximum keepalive connections
            - keepalive_expiry: Keepalive expiry time in seconds
            - use_cache: Whether to use cached client

    Returns:
        HTTP client instance

    Examples:
        # New pattern (recommended):
        config = HTTPClientConfig(name="api", timeout=60.0)
        client = get_http_client(config)

        # Old pattern (still supported):
        client = get_http_client(name="api", timeout=60.0)
    """
    return HTTPClientFactory.create_client(config=config, **kwargs)


async def close_http_client(name: str = "default") -> None:
    """Close a specific HTTP client"""
    await HTTPClientFactory.close_client(name)


async def close_all_http_clients() -> None:
    """Close all HTTP clients"""
    await HTTPClientFactory.close_all()


def get_http_client_stats() -> dict[str, object]:
    """Get statistics about cached HTTP clients"""
    return HTTPClientFactory.get_cached_clients()


__all__ = [
    "HTTPClientConfig",
    # Classes
    "HTTPClientFactory",
    # Functions
    "close_all_http_clients",
    "close_http_client",
    "get_http_client",
    "get_http_client_stats",
]
