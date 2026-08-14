"""حواجز معمارية لمنع توسع split-brain في مسارات chat وملكية نماذج mission."""

from __future__ import annotations

from pathlib import Path


def test_chat_routers_keep_compatibility_facade_and_canonical_authority() -> None:
    """يثبت أن مسارات chat في التطبيق تبقى واجهات توافقية وتفويضها للمنسق الرسمي."""

    admin_router = Path("app/api/routers/admin.py").read_text(encoding="utf-8")
    customer_router = Path("app/api/routers/customer_chat.py").read_text(encoding="utf-8")

    assert "COMPATIBILITY_FACADE_MODE = True" in admin_router
    assert "COMPATIBILITY_FACADE_MODE = True" in customer_router
    assert 'CANONICAL_EXECUTION_AUTHORITY = "orchestrator-service:/agent/chat"' in admin_router
    assert 'CANONICAL_EXECUTION_AUTHORITY = "orchestrator-service:/agent/chat"' in customer_router


def test_gateway_remains_canonical_runtime_entry_for_chat_paths() -> None:
    """يثبت أن البوابة تملك نقاط الدخول العامة لمسارات chat (HTTP/WS) بشكل صريح.

    D-254: تحولت المسارات من decorators نصية إلى ROUTE_REGISTRY تصريحية +
    استدعاءات ``application.api_route(...)`` برمجية، لذا يفحص الحاجز نص المصدر
    للروابط التصريحية (``_HttpRoute(..., "/api/chat/{path:path}")`` و
    ``_WsRoute(..., "/api/chat/ws")``) والسلوك الفعلي للتطبيق بدلًا من
    ``@app.api_route(`` الحرفية.
    """

    from fastapi.routing import APIRoute, APIWebSocketRoute

    from microservices.api_gateway.main import app as gateway_app

    gateway_main = Path("microservices/api_gateway/main.py").read_text(encoding="utf-8")

    # Source-level: the declarative registry entries that own the chat paths.
    assert '"/api/chat/ws"' in gateway_main or "'/api/chat/ws'" in gateway_main
    assert '"/admin/api/chat/ws"' in gateway_main or "'/admin/api/chat/ws'" in gateway_main
    assert '"/api/chat/{path:path}"' in gateway_main or "'/api/chat/{path:path}'" in gateway_main

    # Behaviour-level: the app must actually expose chat as the public entry.
    paths = {
        (r.path, type(r))
        for r in gateway_app.routes
        if isinstance(r, (APIRoute, APIWebSocketRoute))
    }
    assert ("/api/chat/ws", APIWebSocketRoute) in paths
    assert ("/admin/api/chat/ws", APIWebSocketRoute) in paths
    assert ("/api/chat/{path:path}", APIRoute) in paths
    # Customer-facing chat HTTP paths must remain routed through the gateway
    # (the modern /api/chat path plus the original legacy /api/chat/* suffix
    # used before the rewrite split).


def test_orchestrator_state_uses_microservice_mission_models_only() -> None:
    """يمنع توسيع ازدواجية الملكية عبر تثبيت مصدر النماذج داخل خدمة orchestrator."""

    state_module = Path(
        "microservices/orchestrator_service/src/services/overmind/state.py"
    ).read_text(encoding="utf-8")

    assert "from microservices.orchestrator_service.src.models.mission import (" in state_module
    assert "from app.core.domain.mission import" not in state_module


def test_orchestrator_routes_do_not_import_monolith_api_surfaces() -> None:
    """يمنع توسيع split-brain عبر استيراد واجهات monolith داخل مسارات orchestrator.

    D-168: يمسح كل ملفات ``API_SOURCE_FILES`` (routes.py + الوحدات المستخرَجة) —
    الحاجز يمتد تلقائياً لأي وحدة جديدة تُضاف للمانيفست. الوحدات المستخرَجة
    ممنوعة أيضاً من الاستيراد العكسي من routes (طبقات باتجاه واحد — درء الدورات).
    """

    from microservices.orchestrator_service.src.api.api_sources import API_SOURCE_FILES

    for rel in API_SOURCE_FILES:
        module_src = Path(rel).read_text(encoding="utf-8")
        assert "from app.api" not in module_src, rel
        assert "from app.services.chat" not in module_src, rel
        if not rel.endswith("/routes.py"):
            assert "from .routes" not in module_src, f"{rel}: extracted module imports routes"
            assert ".api.routes import" not in module_src, f"{rel}: extracted module imports routes"
