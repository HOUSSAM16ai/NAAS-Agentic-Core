"""
اختبارات D-WS-002: CORS origins و ALLOWED_HOSTS و WebSocket auth contract.

تمنع هذه الاختبارات رجوع الأخطاء التالية:
- BACKEND_CORS_ORIGINS لا يشمل port 5000 → login يفشل من frontend
- ALLOWED_HOSTS لا يشمل Gitpod/Ona hosts → TrustedHostMiddleware يرفض بـ 400
- websocket.close() قبل accept() → uvicorn يُرجع HTTP 403 بدلاً من رسالة JSON
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.settings.base import AppSettings

# ─── اختبارات AppSettings defaults ──────────────────────────────────────────


class TestCorsOriginsDefaults:
    """يتحقق من أن BACKEND_CORS_ORIGINS الافتراضي يشمل port 5000."""

    def test_includes_localhost_5000(self) -> None:
        """port 5000 هو منفذ frontend في Codespaces/Gitpod/Ona."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "http://localhost:5000" in s.BACKEND_CORS_ORIGINS

    def test_includes_localhost_3000(self) -> None:
        """port 3000 للـ local dev."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "http://localhost:3000" in s.BACKEND_CORS_ORIGINS

    def test_includes_127_0_0_1_5000(self) -> None:
        """127.0.0.1:5000 للـ local dev بدون DNS."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "http://127.0.0.1:5000" in s.BACKEND_CORS_ORIGINS

    def test_result_is_list(self) -> None:
        """field_validator يُحوِّل القيمة إلى list[str] دائماً."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert isinstance(s.BACKEND_CORS_ORIGINS, list)
        assert all(isinstance(o, str) for o in s.BACKEND_CORS_ORIGINS)

    def test_csv_env_var_parsed_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CSV في env var يُحوَّل إلى list صحيحة."""
        monkeypatch.setenv(
            "BACKEND_CORS_ORIGINS",
            "http://localhost:3000,http://localhost:5000,https://myapp.gitpod.io",
        )
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "http://localhost:5000" in s.BACKEND_CORS_ORIGINS
        assert "https://myapp.gitpod.io" in s.BACKEND_CORS_ORIGINS


class TestAllowedHostsDefaults:
    """يتحقق من أن ALLOWED_HOSTS الافتراضي يشمل Gitpod/Ona/Codespaces."""

    def test_includes_localhost(self) -> None:
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "localhost" in s.ALLOWED_HOSTS

    def test_includes_gitpod_wildcard(self) -> None:
        """*.gitpod.io يسمح لـ TrustedHostMiddleware بقبول Gitpod hosts."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "*.gitpod.io" in s.ALLOWED_HOSTS

    def test_includes_ws_eu_gitpod(self) -> None:
        """*.ws-eu.gitpod.io للـ EU Gitpod workspaces."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "*.ws-eu.gitpod.io" in s.ALLOWED_HOSTS

    def test_includes_github_codespaces(self) -> None:
        """*.app.github.dev للـ GitHub Codespaces."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "*.app.github.dev" in s.ALLOWED_HOSTS

    def test_includes_replit(self) -> None:
        """*.replit.dev للـ Replit."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "*.replit.dev" in s.ALLOWED_HOSTS

    def test_result_is_list(self) -> None:
        """field_validator يُحوِّل القيمة إلى list[str] دائماً."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert isinstance(s.ALLOWED_HOSTS, list)
        assert all(isinstance(h, str) for h in s.ALLOWED_HOSTS)

    def test_csv_env_var_parsed_correctly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CSV في env var يُحوَّل إلى list صحيحة."""
        monkeypatch.setenv(
            "ALLOWED_HOSTS",
            "localhost,127.0.0.1,*.gitpod.io,*.app.github.dev",
        )
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "*.gitpod.io" in s.ALLOWED_HOSTS
        assert "*.app.github.dev" in s.ALLOWED_HOSTS


class TestFrontendUrlDefault:
    """يتحقق من أن FRONTEND_URL الافتراضي هو port 5000."""

    def test_default_is_port_5000(self) -> None:
        """D-WS-002: port 5000 هو المنفذ الافتراضي للـ frontend."""
        s = AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")
        assert "5000" in s.FRONTEND_URL


# ─── اختبارات WebSocket auth contract ───────────────────────────────────────


class TestWebSocketAuthContract:
    """
    يتحقق من أن WebSocket endpoints تُرجع رسالة JSON عند فشل المصادقة
    بدلاً من HTTP 403 (الذي يحدث عند close() قبل accept()).

    D-WS-002: close() قبل accept() → uvicorn يُرجع HTTP 403.
    الإصلاح: accept() أولاً ثم send_json(error) ثم close(4401).
    """

    @pytest.fixture()
    def app(self) -> FastAPI:
        from app.kernel import RealityKernel

        kernel = RealityKernel(
            settings={
                "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
                "ENVIRONMENT": "testing",
                "SECRET_KEY": "test-secret-key-for-ws-auth-tests",
            },
            enable_static_files=False,
        )
        return kernel.get_app()

    def test_customer_ws_no_token_returns_json_not_403(self, app: FastAPI) -> None:
        """
        بدون token: يجب أن يصل رسالة JSON بـ type=error وليس HTTP 403.
        HTTP 403 يحدث عند close() قبل accept() — هذا هو الخلل الذي نمنع رجوعه.
        """
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/api/chat/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            payload = data.get("payload", {})
            assert payload.get("code") == "WS_AUTH_MISSING"
            assert payload.get("status_code") == 4401

    def test_admin_ws_no_token_returns_json_not_403(self, app: FastAPI) -> None:
        """نفس الاختبار للـ admin WebSocket endpoint."""
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/admin/api/chat/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            payload = data.get("payload", {})
            assert payload.get("code") == "WS_AUTH_MISSING"

    def test_customer_ws_invalid_token_returns_json_not_403(self, app: FastAPI) -> None:
        """token غير صالح: يجب أن يصل رسالة JSON بـ code=WS_AUTH_INVALID."""
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/api/chat/ws?token=invalid.jwt.token") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            payload = data.get("payload", {})
            assert payload.get("code") == "WS_AUTH_INVALID"

    def test_admin_ws_invalid_token_returns_json_not_403(self, app: FastAPI) -> None:
        """نفس الاختبار للـ admin WebSocket endpoint."""
        client = TestClient(app, raise_server_exceptions=False)
        with client.websocket_connect("/admin/api/chat/ws?token=invalid.jwt.token") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            payload = data.get("payload", {})
            assert payload.get("code") == "WS_AUTH_INVALID"


# ─── اختبارات CORS middleware ────────────────────────────────────────────────


class TestCorsMiddlewarePort5000:
    """يتحقق من أن CORS يسمح بـ Origin: http://localhost:5000."""

    @pytest.fixture()
    def client(self) -> TestClient:
        from app.kernel import RealityKernel

        kernel = RealityKernel(
            settings={
                "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
                "ENVIRONMENT": "testing",
                "SECRET_KEY": "test-secret",
            },
            enable_static_files=False,
        )
        return TestClient(kernel.get_app())

    def test_cors_allows_port_5000(self, client: TestClient) -> None:
        """Origin: http://localhost:5000 يجب أن يحصل على Access-Control-Allow-Origin."""
        response = client.get("/health", headers={"Origin": "http://localhost:5000"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5000"

    def test_cors_allows_port_3000(self, client: TestClient) -> None:
        """Origin: http://localhost:3000 يجب أن يحصل على Access-Control-Allow-Origin."""
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
