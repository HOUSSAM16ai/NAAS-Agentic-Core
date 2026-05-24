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
)

type RouterSpec = tuple[APIRouter, str]


def base_router_registry() -> list[RouterSpec]:
    """
    يبني سجل الموجهات الأساسية للتطبيق بدون موجه البوابة.

    D-WS-003 (2026-05-24): ws_proxy مُعطَّل مؤقتاً.
    customer_chat.router يملك /api/chat/ws مباشرة ويُرسل events بالـ format
    الصحيح (assistant_delta, assistant_final, conversation_init).
    ws_proxy كان يُمرِّر إلى conversation-service الذي يُرجع format مختلف.
    """
    return [
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
