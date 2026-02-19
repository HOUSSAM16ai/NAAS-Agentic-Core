import os
from unittest.mock import AsyncMock, patch

# Set required environment variable before importing settings
os.environ["SECRET_KEY"] = "test_secret_key"

from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from microservices.api_gateway.config import settings
from microservices.api_gateway.main import app, proxy_handler
from microservices.api_gateway.security import verify_gateway_request

client = TestClient(app)


# Override security dependency
async def override_verify_gateway_request():
    return {"sub": "test-user"}


app.dependency_overrides[verify_gateway_request] = override_verify_gateway_request


@patch.object(proxy_handler, "forward", new_callable=AsyncMock)
def test_planning_route_proxies_correctly(mock_forward):
    """
    Verify that requests to /api/v1/planning/* are correctly forwarded to the planning agent.
    """
    mock_forward.return_value = JSONResponse(content={"status": "ok"})

    response = client.get("/api/v1/planning/test")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Verify forward was called with correct args
    # args: request, target_url, path, service_token
    # We can check target_url
    assert mock_forward.called
    args, _ = mock_forward.call_args
    assert "http://planning-agent:8000" in args  # target_url
    assert "test" in args  # path (stripped prefix)


@patch.object(proxy_handler, "forward", new_callable=AsyncMock)
def test_unknown_route_returns_404(mock_forward):
    """
    Verify that requests to unknown routes return 404 and are NOT forwarded.
    """
    response = client.get("/unknown/route")

    # Verify response
    assert response.status_code == 404
    assert response.json() == {
        "detail": "Route not found in API Gateway. Please verify the URL or check if the service is registered.",
        "path": "/unknown/route",
    }

    # Verify forward was NOT called
    assert not mock_forward.called


@patch.object(proxy_handler, "forward", new_callable=AsyncMock)
def test_legacy_route_proxies_to_monolith(mock_forward):
    """
    Verify that whitelisted legacy routes (e.g. /admin) are forwarded to the Core Kernel.
    """
    mock_forward.return_value = JSONResponse(content={"status": "legacy_ok"})

    response = client.get("/admin/users")

    assert response.status_code == 200
    assert response.json() == {"status": "legacy_ok"}

    assert mock_forward.called
    args, _ = mock_forward.call_args
    assert settings.CORE_KERNEL_URL in args
    # Route is /admin/{path}, so path should be appended
    # The current implementation calls forward with f"admin/{path}"
    # So if path is "users", it sends "admin/users"
    assert "admin/users" in args
