"""
سجل موجهات API كمصدر حقيقة موحّد.
"""

from fastapi import APIRouter

from app.api.routers import (
    admin,
    aek,
    content,
    customer_chat,
    data_mesh,
    observability,
    security,
    system,
    ums,
    visual_pedagogy,
    ws_proxy,
)

type RouterSpec = tuple[APIRouter, str]


def base_router_registry() -> list[RouterSpec]:
    """
    يبني سجل الموجهات الأساسية للتطبيق بدون موجه البوابة.

    D-WS-001: ws_proxy يجب أن يكون أول router مُسجَّل حتى يأخذ
    الأولوية على customer_chat.router في مطابقة /api/chat/ws.
    """
    return [
        # WebSocket proxy — يجب أن يسبق customer_chat لأخذ الأولوية
        (ws_proxy.router, ""),
        (system.root_router, ""),
        (system.router, ""),
        (admin.router, ""),
        (security.router, "/api/security"),
        (data_mesh.router, "/api/v1/data-mesh"),
        (ums.router, "/api/v1"),
        (customer_chat.router, ""),
        (content.router, ""),
        (observability.router, "/api/v1/observability"),
        (visual_pedagogy.router, ""),
        (aek.router, ""),
    ]
