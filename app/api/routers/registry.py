"""
سجل موجهات API كمصدر حقيقة موحّد.
"""

from fastapi import APIRouter

from app.api.routers import (
    admin,
    content,
    crud,
    customer_chat,
    data_mesh,
    security,
    system,
)

# DEPRECATED/REMOVED: The following routers have been migrated to microservices
# and are no longer mounted in the Monolith Core to prevent split-brain execution.
# - agents (Planning/Reasoning/Research Agents)
# - missions (Orchestrator Read)
# - observability (Observability Service)
# - overmind (Orchestrator Write)
# - ums (User Management Service)

type RouterSpec = tuple[APIRouter, str]


def base_router_registry() -> list[RouterSpec]:
    """
    يبني سجل الموجهات الأساسية للتطبيق بدون موجه البوابة.
    """
    return [
        (system.root_router, ""),
        (system.router, ""),
        (admin.router, ""),
        # (ums.router, ""),  # Moved to user_service
        (security.router, "/api/security"),
        (data_mesh.router, "/api/v1/data-mesh"),
        # (observability.router, "/api/observability"),  # Moved to observability_service
        (crud.router, "/api/v1"),
        (customer_chat.router, ""),
        # (agents.router, ""),  # Moved to planning_agent/reasoning_agent
        # (overmind.router, ""),  # Moved to orchestrator_service
        # (missions.router, ""),  # Moved to orchestrator_service
        (content.router, ""),
    ]
