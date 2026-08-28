import os
from unittest import mock

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import Response
from starlette.routing import Route

from app.middleware.remove_blocking_headers import RemoveBlockingHeadersMiddleware


async def _homepage(request):
    """Endpoint that sets every header the middleware is asked to judge.

    Declared once and wired through `routes=[Route(...)]`: Starlette removed the
    `@app.route` decorator in 1.0 (deprecated since 0.13), and FastAPI 0.141
    resolves to Starlette 1.6, so the decorator form now raises AttributeError.
    """
    return Response(
        "ok",
        headers={
            "Server": "TestServer/1.0",
            "X-Powered-By": "TestFramework",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
        },
    )


def test_dev_frame_middleware_development():
    """Verify that RemoveBlockingHeadersMiddleware removes blocked headers."""
    with mock.patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
        app = Starlette(
            middleware=[Middleware(RemoveBlockingHeadersMiddleware)],
            routes=[Route("/", _homepage)],
        )

        client = TestClient(app)
        response = client.get("/")

        # Assertions - RemoveBlockingHeadersMiddleware only removes specific headers
        assert "server" not in response.headers
        assert "x-powered-by" not in response.headers
        # X-Frame-Options and CSP are NOT removed by this middleware
        assert "x-frame-options" in response.headers
        assert "content-security-policy" in response.headers


def test_dev_frame_middleware_production():
    """Verify that RemoveBlockingHeadersMiddleware works the same in production."""
    with mock.patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
        app = Starlette(
            middleware=[Middleware(RemoveBlockingHeadersMiddleware)],
            routes=[Route("/", _homepage)],
        )

        client = TestClient(app)
        response = client.get("/")

        # Assertions: Middleware removes blocked headers regardless of environment
        assert "server" not in response.headers
        assert "x-powered-by" not in response.headers
        assert response.headers["x-frame-options"] == "DENY"
        assert (
            response.headers["content-security-policy"]
            == "default-src 'self'; frame-ancestors 'none'"
        )
