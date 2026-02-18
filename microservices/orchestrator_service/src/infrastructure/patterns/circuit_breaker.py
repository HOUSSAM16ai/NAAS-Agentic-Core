"""Circuit Breaker pattern implementation."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from functools import wraps
from typing import TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = auto()  # Normal operation
    OPEN = auto()  # Failing, reject requests
    HALF_OPEN = auto()  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    expected_exception: type[Exception] = Exception


class CircuitBreakerError(Exception):
    """Circuit breaker is open."""


class CircuitBreaker:
    """Circuit breaker for fault tolerance."""

    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0.0

    def call(
        self,
        func: Callable[..., T],
        *args: dict[str, str | int | bool],
        **kwargs: dict[str, str | int | bool],
    ) -> T:
        """Execute function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.failure_count >= self.config.failure_threshold:
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time passed to attempt reset."""
        return (time.time() - self.last_failure_time) >= self.config.timeout_seconds

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0

    def get_state(self) -> CircuitState:
        """Get current state."""
        return self.state


def circuit_breaker(
    failure_threshold: int = 5,
    timeout_seconds: float = 60.0,
    expected_exception: type[Exception] = Exception,
) -> None:
    """Decorator for circuit breaker pattern."""

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            timeout_seconds=timeout_seconds,
            expected_exception=expected_exception,
        )
        breaker = CircuitBreaker(config)

        @wraps(func)
        def wrapper(*args: dict[str, str | int | bool], **kwargs: dict[str, str | int | bool]) -> T:
            return breaker.call(func, *args, **kwargs)

        wrapper.circuit_breaker = breaker  # type: ignore
        return wrapper

    return decorator
