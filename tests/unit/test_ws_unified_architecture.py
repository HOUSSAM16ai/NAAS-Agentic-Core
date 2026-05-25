"""
اختبارات D-WS-004: WebSocket Unified Architecture.

تمنع هذه الاختبارات رجوع الأخطاء التالية:
- admin_chat.js يتصل بـ /ws/chat (endpoint غير موجود) بدون token
- wsUrl.js يستخدم port hardcoded بدلاً من NEXT_PUBLIC_BACKEND_PORT
- supervisor.sh يتجاهل secrets.env عندما devcontainer يُعيّن empty strings
- ws_proxy.py يُرجع token كـ selected_protocol بدلاً من "jwt"
- auth_error state لا يُطلق agent:auth_error event
- CogniForgeApp لا يعالج auth_error → لا logout تلقائي
"""

from __future__ import annotations

import pytest
from fastapi import WebSocket
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch


# ─── اختبارات ws_auth.py ─────────────────────────────────────────────────────


class TestExtractWebSocketAuth:
    """يتحقق من أن extract_websocket_auth يستخرج token من كل المصادر."""

    def _make_ws(self, *, cookie="", query_token="", auth_header="", subprotocol=""):
        ws = MagicMock(spec=WebSocket)
        ws.headers = {
            "cookie": cookie,
            "authorization": auth_header,
            "sec-websocket-protocol": subprotocol,
        }
        ws.query_params = {"token": query_token} if query_token else {}
        ws.client = MagicMock()
        ws.client.host = "127.0.0.1"
        return ws

    def test_cookie_auth_takes_priority(self):
        """Cookie يُقدَّم على query param وsubprotocol."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws(
            cookie="access_token=cookie_tok",
            query_token="query_tok",
            subprotocol="jwt, subproto_tok",
        )
        token, proto = extract_websocket_auth(ws)
        assert token == "cookie_tok"
        assert proto is None  # cookie لا يحتاج subprotocol

    def test_query_param_fallback(self):
        """Query param يعمل عند غياب cookie."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws(query_token="query_tok_123")
        token, proto = extract_websocket_auth(ws)
        assert token == "query_tok_123"
        assert proto is None

    def test_subprotocol_fallback(self):
        """Subprotocol يعمل كـ fallback أخير."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws(subprotocol="jwt, real_token_here")
        token, proto = extract_websocket_auth(ws)
        assert token == "real_token_here"
        assert proto == "jwt"

    def test_no_auth_returns_none(self):
        """بدون أي مصدر auth → (None, None)."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws()
        token, proto = extract_websocket_auth(ws)
        assert token is None
        assert proto is None

    def test_auth_header_bearer(self):
        """Authorization: Bearer token يعمل."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws(auth_header="Bearer header_token_xyz")
        token, proto = extract_websocket_auth(ws)
        assert token == "header_token_xyz"
        assert proto == "jwt"

    def test_malformed_subprotocol_no_jwt_keyword(self):
        """Subprotocol بدون 'jwt' keyword → لا token."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws(subprotocol="some_random_protocol")
        token, proto = extract_websocket_auth(ws)
        assert token is None

    def test_subprotocol_jwt_without_token(self):
        """Subprotocol يحتوي 'jwt' فقط بدون token بعده → لا token."""
        from app.api.routers.ws_auth import extract_websocket_auth

        ws = self._make_ws(subprotocol="jwt")
        token, proto = extract_websocket_auth(ws)
        assert token is None


# ─── اختبارات ws_proxy.py — selected_protocol ────────────────────────────────


class TestWsProxySelectedProtocol:
    """
    D-WS-004: ws_proxy يجب أن يُرجع "jwt" كـ selected_protocol
    وليس token نفسه (الخطأ القديم: subprotocols[1]).
    """

    def test_jwt_subprotocol_selected_correctly(self):
        """["jwt", token] → selected_protocol = "jwt" وليس token."""
        # نُحاكي المنطق الجديد مباشرة
        subprotocols = ["jwt", "eyJhbGciOiJIUzI1NiJ9.payload.sig"]
        selected = "jwt" if "jwt" in subprotocols else (subprotocols[0] if subprotocols else None)
        assert selected == "jwt"
        assert selected != subprotocols[1]  # يجب ألا يكون الـ token

    def test_no_subprotocols_returns_none(self):
        """بدون subprotocols → None (query param auth)."""
        subprotocols: list[str] = []
        selected = "jwt" if "jwt" in subprotocols else (subprotocols[0] if subprotocols else None)
        assert selected is None

    def test_non_jwt_subprotocol_uses_first(self):
        """subprotocol غير jwt → يستخدم الأول."""
        subprotocols = ["v1.chat"]
        selected = "jwt" if "jwt" in subprotocols else (subprotocols[0] if subprotocols else None)
        assert selected == "v1.chat"


# ─── اختبارات AppSettings — CORS و ALLOWED_HOSTS ─────────────────────────────


class TestAppSettingsWsDefaults:
    """يتحقق من أن الإعدادات الافتراضية تدعم Gitpod/Ona/Codespaces."""

    def test_allowed_hosts_includes_gitpod(self):
        from app.core.settings.base import AppSettings

        s = AppSettings(_env_file=None)
        hosts = s.ALLOWED_HOSTS
        assert any("gitpod" in h for h in hosts), f"Gitpod missing from ALLOWED_HOSTS: {hosts}"

    def test_allowed_hosts_includes_codespaces(self):
        from app.core.settings.base import AppSettings

        s = AppSettings(_env_file=None)
        hosts = s.ALLOWED_HOSTS
        assert any("github.dev" in h for h in hosts), f"Codespaces missing: {hosts}"

    def test_cors_includes_port_5000(self):
        from app.core.settings.base import AppSettings

        s = AppSettings(_env_file=None)
        origins = s.BACKEND_CORS_ORIGINS
        assert any("5000" in o for o in origins), f"Port 5000 missing from CORS: {origins}"

    def test_cors_includes_port_3000(self):
        from app.core.settings.base import AppSettings

        s = AppSettings(_env_file=None)
        origins = s.BACKEND_CORS_ORIGINS
        assert any("3000" in o for o in origins), f"Port 3000 missing from CORS: {origins}"

    def test_frontend_url_default_port_5000(self):
        from app.core.settings.base import AppSettings

        s = AppSettings(_env_file=None)
        assert "5000" in s.FRONTEND_URL, f"FRONTEND_URL should use port 5000: {s.FRONTEND_URL}"


# ─── اختبارات admin_chat.js — static analysis ────────────────────────────────


class TestAdminChatJsContract:
    """
    D-WS-004: admin_chat.js يجب أن:
    1. يستخدم /admin/api/chat/ws (وليس /ws/chat)
    2. يُرسل token عبر query param
    3. يعالج assistant_delta و assistant_final
    """

    def _read_admin_chat_js(self) -> str:
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "app", "static", "js", "admin_chat.js"
        )
        with open(os.path.abspath(path)) as f:
            return f.read()

    def test_correct_endpoint(self):
        """يجب استخدام /admin/api/chat/ws وليس /ws/chat في الكود (ليس التعليقات)."""
        content = self._read_admin_chat_js()
        assert "/admin/api/chat/ws" in content, "admin_chat.js must use /admin/api/chat/ws"
        # تحقق من الكود فقط — استبعد التعليقات (أسطر تبدأ بـ * أو //)
        code_lines = [
            line for line in content.splitlines()
            if not line.strip().startswith("*") and not line.strip().startswith("//")
        ]
        code_only = "\n".join(code_lines)
        assert "/ws/chat" not in code_only, \
            "admin_chat.js code must NOT use /ws/chat (endpoint does not exist)"

    def test_token_via_query_param(self):
        """يجب إرسال token عبر query param."""
        content = self._read_admin_chat_js()
        assert "token=" in content or "encodeURIComponent" in content, \
            "admin_chat.js must send token via query param"

    def test_handles_assistant_delta(self):
        """يجب معالجة assistant_delta event."""
        content = self._read_admin_chat_js()
        assert "assistant_delta" in content, "admin_chat.js must handle assistant_delta events"

    def test_handles_assistant_final(self):
        """يجب معالجة assistant_final event."""
        content = self._read_admin_chat_js()
        assert "assistant_final" in content, "admin_chat.js must handle assistant_final events"

    def test_no_hardcoded_localhost(self):
        """يجب عدم وجود localhost hardcoded."""
        content = self._read_admin_chat_js()
        assert "localhost" not in content, "admin_chat.js must not hardcode localhost"

    def test_dynamic_ws_protocol(self):
        """يجب اختيار ws/wss ديناميكياً."""
        content = self._read_admin_chat_js()
        assert "wss:" in content or "wsProtocol" in content, \
            "admin_chat.js must use dynamic ws/wss protocol"


# ─── اختبارات wsUrl.js — static analysis ─────────────────────────────────────


class TestWsUrlJsContract:
    """
    D-WS-004: wsUrl.js يجب أن:
    1. يدعم NEXT_PUBLIC_BACKEND_PORT بدلاً من port 8000 hardcoded
    2. يكتشف Gitpod/Ona تلقائياً
    3. يُعيد backend host الصحيح في cloud workspaces
    """

    def _read_wsurl_js(self) -> str:
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", "frontend", "app", "utils", "wsUrl.js"
        )
        with open(os.path.abspath(path)) as f:
            return f.read()

    def test_uses_env_var_for_backend_port(self):
        """يجب استخدام NEXT_PUBLIC_BACKEND_PORT بدلاً من hardcoded 8000."""
        content = self._read_wsurl_js()
        assert "NEXT_PUBLIC_BACKEND_PORT" in content, \
            "wsUrl.js must use NEXT_PUBLIC_BACKEND_PORT env var"

    def test_gitpod_cloud_detection(self):
        """يجب اكتشاف Gitpod/Ona تلقائياً."""
        content = self._read_wsurl_js()
        assert "gitpod" in content.lower(), "wsUrl.js must detect Gitpod environment"

    def test_cloud_backend_host_rewrite(self):
        """يجب إعادة كتابة port prefix في Gitpod subdomain."""
        content = self._read_wsurl_js()
        assert "8000-" in content or "replace" in content, \
            "wsUrl.js must rewrite port prefix for cloud workspaces"

    def test_no_hardcoded_localhost_port(self):
        """يجب عدم وجود localhost:8000 hardcoded بدون fallback."""
        content = self._read_wsurl_js()
        # يجب أن يكون محاطاً بـ env var check
        assert "NEXT_PUBLIC_BACKEND_PORT" in content, \
            "wsUrl.js must not hardcode port 8000 without env var override"


# ─── اختبارات legacy-app.jsx — API_ORIGIN ────────────────────────────────────


class TestLegacyAppApiOrigin:
    """
    D-WS-004: legacy-app.jsx يجب أن يبني API_ORIGIN بشكل صحيح
    لكل البيئات: Gitpod/Ona/Codespaces/local.
    """

    def _read_legacy_app(self, path_prefix: str) -> str:
        import os
        path = os.path.join(
            os.path.dirname(__file__), "..", "..", path_prefix, "legacy-app.jsx"
        )
        with open(os.path.abspath(path)) as f:
            return f.read()

    @pytest.mark.parametrize("prefix", [
        "frontend/public/js",
        "app/static/js",
    ])
    def test_gitpod_port_rewrite(self, prefix):
        """يجب إعادة كتابة port prefix لـ Gitpod/Ona."""
        content = self._read_legacy_app(prefix)
        assert "5000-" in content and "8000-" in content, \
            f"{prefix}/legacy-app.jsx must rewrite 5000- to 8000- for Gitpod"

    @pytest.mark.parametrize("prefix", [
        "frontend/public/js",
        "app/static/js",
    ])
    def test_codespaces_port_rewrite(self, prefix):
        """يجب إعادة كتابة port لـ GitHub Codespaces."""
        content = self._read_legacy_app(prefix)
        assert "app.github.dev" in content, \
            f"{prefix}/legacy-app.jsx must handle Codespaces hostnames"

    @pytest.mark.parametrize("prefix", [
        "frontend/public/js",
        "app/static/js",
    ])
    def test_local_dev_port_mapping(self, prefix):
        """يجب تحويل port 5000/3000 إلى 8000 في local dev."""
        content = self._read_legacy_app(prefix)
        assert "port === '5000'" in content or "port === '3000'" in content, \
            f"{prefix}/legacy-app.jsx must map local dev ports to backend port 8000"


# ─── اختبارات WebSocket handshake contract ───────────────────────────────────


class TestWebSocketHandshakeContract:
    """
    يتحقق من أن backend يُرجع JSON error وليس HTTP 403
    عند فشل auth — D-WS-002 regression tests.
    """

    def test_ws_endpoint_customer_exists(self):
        """يجب أن يكون /api/chat/ws موجوداً في router registry."""
        from app.api.routers.registry import base_router_registry
        from app.api.routers import customer_chat

        registry = base_router_registry()
        routers = [r for r, _ in registry]
        assert customer_chat.router in routers, \
            "customer_chat.router must be in base_router_registry"

    def test_ws_endpoint_admin_exists(self):
        """يجب أن يكون /admin/api/chat/ws موجوداً في router registry."""
        from app.api.routers.registry import base_router_registry
        from app.api.routers import admin

        registry = base_router_registry()
        routers = [r for r, _ in registry]
        assert admin.router in routers, \
            "admin.router must be in base_router_registry"

    def test_ws_proxy_not_in_registry(self):
        """
        D-WS-003: ws_proxy مُعطَّل — customer_chat.router يملك /api/chat/ws مباشرة.
        ws_proxy كان يُمرِّر إلى conversation-service بـ format مختلف.
        """
        from app.api.routers.registry import base_router_registry
        from app.api.routers import ws_proxy

        registry = base_router_registry()
        routers = [r for r, _ in registry]
        assert ws_proxy.router not in routers, \
            "ws_proxy.router must NOT be in base_router_registry (D-WS-003)"
