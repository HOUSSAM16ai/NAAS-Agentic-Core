"""مُحوِّل بوّابة التخطيط (ACL) — يُصنِّف حمولة الخدمة عند الحدّ (D-192 · roadmap D1)."""

from app.core.logging import get_logger
from app.infrastructure.clients.planning_client import planning_client
from app.integration.models import PlanResult
from app.integration.protocols.planning_gateway import PlanningGatewayProtocol

logger = get_logger(__name__)


class RemotePlanningGateway(PlanningGatewayProtocol):
    """
    Remote Adapter for the Planning Agent.
    Implements the PlanningGatewayProtocol by using the HTTP Client.
    """

    async def generate_plan(
        self,
        goal: str,
        context: str = "",
    ) -> PlanResult:
        try:
            # Convert context string to list as expected by the microservice
            context_list = [context] if context else []
            # D-192 (roadmap D2): كان هنا `planning_client.generate_plan(...)` —
            # **تابعٌ غير موجود**؛ العميل يملك `create_plan` وحده. أي أن كل نداءٍ
            # لهذه البوّابة كان ينتهي بـ`AttributeError` يبتلعه `except` فيُعاد رفعه.
            # عطبٌ سابقٌ لهذه الجولة كشفه **أوّل تشغيل لـmypy** — وهو بالضبط سبب
            # إدخاله بوّابةً: بلا فحص أنواع يبقى «strict typing» شعاراً.
            raw = await planning_client.create_plan(goal, context_list)
        except Exception as e:
            logger.error(f"Error in generate_plan: {e}")
            raise
        payload: dict[str, object] = raw if isinstance(raw, dict) else {}
        return PlanResult.model_validate({"goal": goal, **payload, "raw": payload})


# Alias for backward compatibility if needed, but we should update imports
LocalPlanningGateway = RemotePlanningGateway
