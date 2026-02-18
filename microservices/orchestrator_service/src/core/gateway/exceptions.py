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
    """Specific error for rate limits (429) to trigger distinct handling."""


class StreamInterruptedError(AIError):
    """Stream severed mid-transmission; safe failover is impossible."""
