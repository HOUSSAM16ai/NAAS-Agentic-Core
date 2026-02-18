"""Design patterns implementations."""

from .chain_of_responsibility import (
    AuthenticationHandler,
    AuthorizationHandler,
    Handler,
    RateLimitHandler,
    RequestContext,
    ValidationHandler,
    build_request_pipeline,
)
from .circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState, circuit_breaker
from .dependency_injection import DIContainer, get_container, inject
from .event_bus import Event, EventBus, get_event_bus

__all__ = [
    "AuthenticationHandler",
    "AuthorizationHandler",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitState",
    "DIContainer",
    "Event",
    "EventBus",
    "Handler",
    "RateLimitHandler",
    "RequestContext",
    "ValidationHandler",
    "build_request_pipeline",
    "circuit_breaker",
    "get_container",
    "get_event_bus",
    "inject",
]
