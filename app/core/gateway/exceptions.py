"""
AI Gateway Exceptions.
Part of the Atomic Modularization Protocol.
"""


class AIError(Exception):
    """Base class for AI Gateway errors."""


class AIProviderError(AIError):
    """Upstream provider returned an error."""


class AICircuitOpenError(AIError):
    """The circuit breaker is open; request rejected fast."""


class AIConnectionError(AIError):
    """Network or connection failure."""


class AIAllModelsExhaustedError(AIError):
    """All available AI models in the Neural Mesh have failed."""


class AIRateLimitError(AIConnectionError):
    """Specific error for rate limits (429) to trigger distinct handling.

    Carries the provider-advertised ``retry_after`` (seconds) so the fallback
    loop can schedule a bounded second pass over rate-limited models instead of
    dropping straight to the safety net (D-177 — "answer every question").
    """

    def __init__(self, message: str = "", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class StreamInterruptedError(AIError):
    """Stream severed mid-transmission; safe failover is impossible."""
