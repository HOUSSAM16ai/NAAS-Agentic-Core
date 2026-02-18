import os
from unittest.mock import AsyncMock, patch

# Set required environment variable before importing settings
os.environ["SECRET_KEY"] = "test_secret_key"

from fastapi.testclient import TestClient

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
    # Mock the return value to be a valid StreamingResponse-like object or just pass
    # Since forward returns a StreamingResponse, we need to mock that if the view uses it.
    # But the view just returns whatever forward returns.
    # Let's mock a simple response.
    from fastapi.responses import JSONResponse

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
def test_security_route_proxies_to_monolith(mock_forward):
    """
    Verify that requests to /api/security/login are forwarded to the Core Kernel.
    """
    from fastapi.responses import JSONResponse

    mock_forward.return_value = JSONResponse(content={"status": "ok"})

    response = client.post("/api/security/login", json={"email": "test", "password": "pw"})

    assert response.status_code == 200
    assert mock_forward.called
    args, _ = mock_forward.call_args
    # Should point to core-kernel and include full path
    assert "http://core-kernel:8000" in args
    assert "api/security/login" in args


@patch.object(proxy_handler, "forward", new_callable=AsyncMock)
def test_chat_route_proxies_to_monolith(mock_forward):
    """
    Verify that requests to /api/chat/* are forwarded to the Core Kernel.
    """
    from fastapi.responses import JSONResponse
    mock_forward.return_value = JSONResponse(content={"status": "ok"})

    response = client.get("/api/chat/conversations")

    assert response.status_code == 200
    assert mock_forward.called
    args, _ = mock_forward.call_args
    assert "http://core-kernel:8000" in args
    assert "api/chat/conversations" in args


@patch.object(proxy_handler, "forward", new_callable=AsyncMock)
def test_admin_route_proxies_to_monolith(mock_forward):
    """
    Verify that requests to /admin/* are forwarded to the Core Kernel.
    """
    from fastapi.responses import JSONResponse
    mock_forward.return_value = JSONResponse(content={"status": "ok"})

    response = client.get("/admin/users")

    assert response.status_code == 200
    assert mock_forward.called
    args, _ = mock_forward.call_args
    assert "http://core-kernel:8000" in args
    assert "admin/users" in args


@patch.object(proxy_handler, "forward", new_callable=AsyncMock)
def test_unknown_route_returns_404(mock_forward):
    """
    Verify that requests to unknown routes return 404 and are NOT forwarded.
    """
    # Mock response for the catch-all case (if it runs)
    from fastapi.responses import JSONResponse

    mock_forward.return_value = JSONResponse(content={"status": "fallback"})

    response = client.get("/unknown/route")

    # We assert 404 because that is the Goal state.
    assert response.status_code == 404, "Route was forwarded to Monolith instead of 404!"
    assert not mock_forward.called
