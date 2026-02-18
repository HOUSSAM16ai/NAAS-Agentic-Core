"""يمثل عقدة في شبكة التوجيه مع معلومات التحكم في التدفق."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from microservices.orchestrator_service.src.core.gateway.circuit_breaker import CircuitBreaker


@dataclass
class NeuralNode:
    """عقدة شبكة تحتوي على بيانات النموذج والسياسات المرتبطة."""

    model_id: str
    circuit_breaker: CircuitBreaker
    rate_limit_cooldown_until: float = 0.0
    semaphore: AbstractAsyncContextManager[None] | None = None


__all__ = ["NeuralNode"]
