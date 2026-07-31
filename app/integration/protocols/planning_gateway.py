"""عقد بوّابة التخطيط (ACL) — مُصنَّف بلا `Any` (D-192 · roadmap D1)."""

from typing import Protocol, runtime_checkable

from app.integration.models import PlanResult


@runtime_checkable
class PlanningGatewayProtocol(Protocol):
    """
    Protocol for Planning Agent capabilities.
    Acts as an ACL to the Planning Domain.
    """

    async def generate_plan(
        self,
        goal: str,
        context: str = "",
    ) -> PlanResult:
        """Generate a cognitive plan for a goal. Returns a typed :class:`PlanResult`."""
        ...
