"""Tests for final remaining gaps in API routers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routers.customer_chat import get_db
from app.api.routers.customer_chat import router as customer_router
from app.api.routers.ws_auth import (
    _extract_token_from_protocols,
    _parse_protocol_header,
    extract_websocket_auth,
)
from app.core.domain.user import User


@pytest.fixture
def customer_app():
    app = FastAPI()
    app.include_router(customer_router)
    return app


# --- Customer Chat Tests ---
def test_customer_ws_auth_fail(customer_app):
    # D-WS-002: accept() → send_json(error) → close(4401). No WebSocketDisconnect raised.
    client = TestClient(customer_app)
    with patch("app.api.routers.customer_chat.extract_websocket_auth", return_value=(None, None)):
        with client.websocket_connect("/api/chat/ws") as ws:
            data = ws.receive_json()
            assert data["type"] == "error"
            assert data["payload"]["code"] == "WS_AUTH_MISSING"


def test_customer_ws_decode_fail(customer_app):
    # D-WS-002: invalid token → accept() → send_json(WS_AUTH_INVALID) → close(4401).
    client = TestClient(customer_app)
    with patch(
        "app.api.routers.customer_chat.extract_websocket_auth", return_value=("token", "jwt")
    ):
        with patch("app.api.routers.customer_chat.decode_user_id", side_effect=HTTPException(401)):
            with client.websocket_connect("/api/chat/ws") as ws:
                data = ws.receive_json()
                assert data["type"] == "error"
                assert data["payload"]["code"] == "WS_AUTH_INVALID"


def test_customer_ws_admin(customer_app):
    # D-WS-002: admin on customer endpoint → accept() → send_json(WS_AUTH_FORBIDDEN) → close(4403).
    client = TestClient(customer_app)
    mock_user = MagicMock(spec=User)
    mock_user.is_active = True
    mock_user.is_admin = True
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user
    customer_app.dependency_overrides[get_db] = lambda: mock_db

    with patch(
        "app.api.routers.customer_chat.extract_websocket_auth", return_value=("token", "jwt")
    ):
        with patch("app.api.routers.customer_chat.decode_user_id", return_value=1):
            with client.websocket_connect("/api/chat/ws") as ws:
                data = ws.receive_json()
                assert data["type"] == "error"
                assert data["payload"]["status_code"] in (4401, 4403)


def test_customer_ws_empty_question(customer_app):
    # D-WS-002: inactive/missing user → accept() → send_json(error) → close(4401).
    client = TestClient(customer_app)
    mock_user = MagicMock(spec=User)
    mock_user.is_active = True
    mock_user.is_admin = False
    mock_db = AsyncMock()
    mock_db.get.return_value = mock_user
    customer_app.dependency_overrides[get_db] = lambda: mock_db

    with patch(
        "app.api.routers.customer_chat.extract_websocket_auth", return_value=("token", "jwt")
    ):
        with patch("app.api.routers.customer_chat.decode_user_id", return_value=1):
            with client.websocket_connect("/api/chat/ws") as ws:
                data = ws.receive_json()
                assert data["type"] == "error"
                assert data["payload"]["status_code"] in (4401, 4403)


# --- WS Auth Tests ---
def test_parse_protocol_header():
    assert _parse_protocol_header("jwt, token") == ["jwt", "token"]
    assert _parse_protocol_header("") == []


def test_extract_token_from_protocols():
    assert _extract_token_from_protocols(["jwt"]) is None
    assert _extract_token_from_protocols(["other"]) is None


def test_extract_websocket_auth_fallback_prod():
    """ISS-WS-001: query param يعمل في production (HTTPS يُشفِّر الـ URL)."""
    mock_ws = MagicMock()
    mock_ws.headers = {}
    mock_ws.query_params.get = lambda key, default="": "fallback" if key == "token" else default

    with patch("app.api.routers.ws_auth.get_settings") as mock_settings:
        mock_settings.return_value.ENVIRONMENT = "production"
        token, _source = extract_websocket_auth(mock_ws)
        # ISS-WS-001: query token مُفعَّل في production — يجب أن يُرجع الـ token
        assert token == "fallback"


def test_extract_websocket_auth_success():
    """يتحقق من استخراج token من sec-websocket-protocol."""
    mock_ws = MagicMock()
    mock_ws.headers = {"sec-websocket-protocol": "jwt, my_secret_token"}
    mock_ws.query_params.get = lambda _key, default="": default

    token, _source = extract_websocket_auth(mock_ws)
    assert token == "my_secret_token"
