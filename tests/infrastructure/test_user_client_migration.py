from __future__ import annotations

import httpx
import pytest

from app.infrastructure.clients.user_client import UserServiceClient


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    async def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> httpx.Response:
        self.calls.append(("POST", url, headers))
        if url.endswith("/api/v1/auth/login"):
            return httpx.Response(404, request=httpx.Request("POST", url))
        return httpx.Response(
            200,
            json={"status": "success", "access_token": "token", "user": {"id": 1}},
            request=httpx.Request("POST", url),
        )

    async def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
        self.calls.append(("GET", url, headers))
        return httpx.Response(
            200,
            json={"id": 1, "full_name": "Tester", "email": "t@example.com", "is_admin": False},
            request=httpx.Request("GET", url),
        )


@pytest.mark.asyncio
async def test_login_uses_microservice_path_then_fallback_and_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = UserServiceClient(base_url="http://user-service:8000")
    fake_client = _FakeClient()

    async def _mock_get_client() -> _FakeClient:
        return fake_client

    monkeypatch.setattr(client, "_get_client", _mock_get_client)

    response = await client.login_user("test@example.com", "pw", user_agent="pytest")

    assert response["status"] == "success"
    assert fake_client.calls[0][1].endswith("/api/v1/auth/login")
    assert fake_client.calls[1][1].endswith("/api/security/login")
    assert fake_client.calls[0][2]["X-Service-Token"]
    assert fake_client.calls[0][2]["User-Agent"] == "pytest"


@pytest.mark.asyncio
async def test_get_me_sends_service_token_and_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = UserServiceClient(base_url="http://user-service:8000")
    fake_client = _FakeClient()

    async def _mock_get_client() -> _FakeClient:
        return fake_client

    monkeypatch.setattr(client, "_get_client", _mock_get_client)

    response = await client.get_me("jwt-token")

    assert response["email"] == "t@example.com"
    method, called_url, headers = fake_client.calls[0]
    assert method == "GET"
    assert called_url.endswith("/api/v1/auth/user/me")
    assert headers["Authorization"] == "Bearer jwt-token"
    assert headers["X-Service-Token"]



class _GatewayOnlyClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, str]]] = []

    async def post(self, url: str, json: dict[str, object], headers: dict[str, str]) -> httpx.Response:
        self.calls.append(("POST", url, headers))
        if url.endswith("/api/security/login"):
            return httpx.Response(
                200,
                json={"status": "success", "access_token": "gw-token", "user": {"id": 9}},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(404, request=httpx.Request("POST", url))

    async def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
        self.calls.append(("GET", url, headers))
        return httpx.Response(404, request=httpx.Request("GET", url))


@pytest.mark.asyncio
async def test_login_supports_gateway_security_route_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    client = UserServiceClient(base_url="http://api-gateway:8000")
    fake_client = _GatewayOnlyClient()

    async def _mock_get_client() -> _GatewayOnlyClient:
        return fake_client

    monkeypatch.setattr(client, "_get_client", _mock_get_client)

    response = await client.login_user("test@example.com", "pw")

    assert response["status"] == "success"
    called_urls = [call[1] for call in fake_client.calls]
    assert called_urls[0].endswith("/api/v1/auth/login")
    assert called_urls[1].endswith("/api/security/login")


@pytest.mark.asyncio
async def test_login_remembers_preferred_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    client = UserServiceClient(base_url="http://user-service:8000")
    fake_client = _FakeClient()

    async def _mock_get_client() -> _FakeClient:
        return fake_client

    monkeypatch.setattr(client, "_get_client", _mock_get_client)

    first_response = await client.login_user("test@example.com", "pw")
    assert first_response["status"] == "success"

    fake_client.calls.clear()

    second_response = await client.login_user("test@example.com", "pw")
    assert second_response["status"] == "success"

    assert fake_client.calls[0][1].endswith("/api/security/login")
