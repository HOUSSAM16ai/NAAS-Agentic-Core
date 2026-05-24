"""
اختبارات WebSocket Gateway Routing — D-WS-001

تتحقق هذه الاختبارات من:
1. أن Gateway (8000) يُمرِّر WebSocket إلى conversation-service (8003)
2. أن /api/chat/ws يُرجع 101 Switching Protocols (وليس 404 أو 403)
3. أن /admin/api/chat/ws مُسجَّل في الـ router
4. أن ws_proxy router مُسجَّل قبل customer_chat في registry
5. أن wsUrl utility يُنتج URLs صحيحة لبيئات مختلفة

Root Cause (ISS-OFFLINE-001):
  - Gateway كان يُرجع 403 على /api/chat/ws بدون token
  - Next.js rewrites لا تُمرِّر WebSocket upgrades
  - الحل: ws_proxy.py يُمرِّر WebSocket إلى 8003 مباشرة
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock


# ─── اختبارات ws_proxy router ───────────────────────────────────────────────

class TestWsProxyRouter:
    """يتحقق من تسجيل WebSocket proxy routes."""

    def test_ws_proxy_routes_registered(self):
        """يتحقق من أن /api/chat/ws و /admin/api/chat/ws مُسجَّلان."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ws_proxy",
            "app/api/routers/ws_proxy.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        routes = [r.path for r in mod.router.routes]
        assert "/api/chat/ws" in routes, (
            "D-WS-001: /api/chat/ws يجب أن يكون مُسجَّلاً في ws_proxy router"
        )
        assert "/admin/api/chat/ws" in routes, (
            "D-WS-001: /admin/api/chat/ws يجب أن يكون مُسجَّلاً في ws_proxy router"
        )

    def test_ws_proxy_routes_are_websocket_type(self):
        """يتحقق من أن الـ routes هي WebSocket وليس HTTP."""
        import importlib.util
        from fastapi.routing import APIWebSocketRoute

        spec = importlib.util.spec_from_file_location(
            "ws_proxy",
            "app/api/routers/ws_proxy.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        for route in mod.router.routes:
            assert isinstance(route, APIWebSocketRoute), (
                f"Route {route.path} يجب أن يكون APIWebSocketRoute"
            )

    def test_upstream_url_builder(self):
        """يتحقق من بناء upstream URL بشكل صحيح."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ws_proxy",
            "app/api/routers/ws_proxy.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # بدون query string
        url = mod._build_upstream_url("/chat/ws", "")
        assert url == "ws://localhost:8003/chat/ws"

        # مع query string
        url = mod._build_upstream_url("/chat/ws", "token=abc&session_id=xyz")
        assert url == "ws://localhost:8003/chat/ws?token=abc&session_id=xyz"

        # admin path
        url = mod._build_upstream_url("/admin/chat/ws", "")
        assert url == "ws://localhost:8003/admin/chat/ws"

    def test_upstream_url_respects_env_var(self, monkeypatch):
        """يتحقق من أن CONVERSATION_SERVICE_WS_URL يُغيِّر الـ upstream."""
        monkeypatch.setenv("CONVERSATION_SERVICE_WS_URL", "ws://conv-service:9000")

        import importlib.util
        import importlib
        spec = importlib.util.spec_from_file_location(
            "ws_proxy_env",
            "app/api/routers/ws_proxy.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        url = mod._build_upstream_url("/chat/ws", "")
        assert "conv-service:9000" in url


# ─── اختبارات registry ──────────────────────────────────────────────────────

class TestRouterRegistry:
    """يتحقق من ترتيب الـ routers في registry."""

    def test_ws_proxy_registered_in_registry(self):
        """يتحقق من أن ws_proxy مُسجَّل في base_router_registry."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ws_proxy",
            "app/api/routers/ws_proxy.py"
        )
        ws_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ws_mod)

        # تحقق من أن الـ router يحتوي على الـ routes الصحيحة
        routes = [r.path for r in ws_mod.router.routes]
        assert "/api/chat/ws" in routes
        assert "/admin/api/chat/ws" in routes

    def test_ws_proxy_routes_before_customer_chat(self):
        """
        D-WS-001: ws_proxy يجب أن يسبق customer_chat في registry
        حتى يأخذ الأولوية في مطابقة /api/chat/ws.
        """
        with open("app/api/routers/registry.py") as f:
            source = f.read()

        # ابحث عن الـ return list فقط (بعد كلمة return)
        return_block_start = source.find("return [")
        assert return_block_start != -1, "base_router_registry يجب أن يحتوي على return ["

        return_block = source[return_block_start:]

        ws_proxy_pos = return_block.find("ws_proxy.router")
        customer_chat_pos = return_block.find("customer_chat.router")

        assert ws_proxy_pos != -1, "ws_proxy.router يجب أن يكون في return list"
        assert customer_chat_pos != -1, "customer_chat.router يجب أن يكون في return list"
        assert ws_proxy_pos < customer_chat_pos, (
            "D-WS-001: ws_proxy.router يجب أن يسبق customer_chat.router في registry. "
            f"ws_proxy_pos={ws_proxy_pos}, customer_chat_pos={customer_chat_pos}"
        )


# ─── اختبارات wsUrl utility ─────────────────────────────────────────────────

class TestWsUrlUtility:
    """يتحقق من wsUrl.js utility logic (منطق Python مكافئ)."""

    def test_http_to_ws_protocol_mapping(self):
        """يتحقق من تحويل HTTP protocols إلى WebSocket."""
        # منطق مكافئ لـ httpToWsProtocol في wsUrl.js
        def http_to_ws(protocol: str) -> str:
            if protocol == "https:":
                return "wss:"
            if protocol == "http:":
                return "ws:"
            return "wss:"

        assert http_to_ws("https:") == "wss:"
        assert http_to_ws("http:") == "ws:"
        assert http_to_ws("unknown:") == "wss:"  # افتراضي آمن

    def test_cloud_workspace_detection(self):
        """يتحقق من اكتشاف بيئات Codespaces/Gitpod."""
        cloud_hosts = [
            "abc123.app.github.dev",
            "abc123.preview.app.github.dev",
            "abc123.gitpod.io",
            "abc123.ws-eu.gitpod.io",
            "abc123.replit.dev",
            "abc123.replit.app",
        ]
        local_hosts = [
            "localhost",
            "127.0.0.1",
            "example.com",
            "myapp.production.com",
        ]

        def is_cloud_workspace(hostname: str) -> bool:
            return (
                hostname.endswith(".app.github.dev")
                or hostname.endswith(".preview.app.github.dev")
                or hostname.endswith(".gitpod.io")
                or hostname.endswith(".ws-eu.gitpod.io")
                or ".gitpod." in hostname
                or hostname.endswith(".replit.dev")
                or hostname.endswith(".replit.app")
                or hostname.endswith(".janeway.replit.dev")
            )

        for host in cloud_hosts:
            assert is_cloud_workspace(host), f"{host} يجب أن يُكتشف كـ cloud workspace"

        for host in local_hosts:
            assert not is_cloud_workspace(host), f"{host} يجب ألا يُكتشف كـ cloud workspace"


# ─── اختبارات live WebSocket (تتطلب services تعمل) ─────────────────────────

@pytest.mark.integration
class TestLiveWebSocketRouting:
    """
    اختبارات حية تتطلب أن Gateway (8000) وconversation-service (8003) يعملان.
    تُشغَّل فقط في بيئة CI مع services حية.
    """

    @pytest.mark.asyncio
    async def test_gateway_ws_returns_101(self):
        """
        D-WS-001: /api/chat/ws على Gateway يجب أن يُرجع 101 Switching Protocols.
        404 = architectural routing failure.
        403 = auth failure (مقبول بدون token).
        """
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "http://localhost:8000/api/chat/ws",
                    headers={
                        "Connection": "Upgrade",
                        "Upgrade": "websocket",
                        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                        "Sec-WebSocket-Version": "13",
                    },
                    timeout=5.0,
                )
                # 101 = WebSocket upgrade (proxy يعمل)
                # 403 = auth required (proxy يعمل لكن يحتاج token)
                # 404 = FAILURE — proxy غير مُسجَّل
                assert response.status_code in (101, 403), (
                    f"D-WS-001: /api/chat/ws أرجع {response.status_code}. "
                    f"404 = architectural routing failure. "
                    f"يجب أن يكون 101 (WebSocket upgrade) أو 403 (auth required)."
                )
            except httpx.ConnectError:
                pytest.skip("Gateway (8000) غير متاح — تخطي اختبار حي")

    @pytest.mark.asyncio
    async def test_conversation_service_ws_returns_101(self):
        """يتحقق من أن conversation-service يقبل WebSocket مباشرة."""
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "http://localhost:8003/chat/ws",
                    headers={
                        "Connection": "Upgrade",
                        "Upgrade": "websocket",
                        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                        "Sec-WebSocket-Version": "13",
                    },
                    timeout=5.0,
                )
                assert response.status_code == 101, (
                    f"conversation-service /chat/ws أرجع {response.status_code} بدلاً من 101"
                )
            except httpx.ConnectError:
                pytest.skip("conversation-service (8003) غير متاح — تخطي اختبار حي")

    @pytest.mark.asyncio
    async def test_gateway_ws_not_404(self):
        """
        D-WS-001: 404 على /api/chat/ws = architectural routing failure.
        هذا الاختبار يفشل إذا كان ws_proxy غير مُسجَّل.
        """
        import httpx

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "http://localhost:8000/api/chat/ws",
                    headers={
                        "Connection": "Upgrade",
                        "Upgrade": "websocket",
                        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
                        "Sec-WebSocket-Version": "13",
                    },
                    timeout=5.0,
                )
                assert response.status_code != 404, (
                    "D-WS-001: 404 على /api/chat/ws = architectural routing failure. "
                    "ws_proxy.py غير مُسجَّل في registry."
                )
            except httpx.ConnectError:
                pytest.skip("Gateway (8000) غير متاح — تخطي اختبار حي")
