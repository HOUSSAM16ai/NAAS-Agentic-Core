"""Tests for final remaining gaps in API routers."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api.routers.customer_chat import router as customer_router
from app.api.routers.ws_auth import (
    _extract_token_from_protocols,
    _parse_protocol_header,
    extract_websocket_auth,
)


@pytest.fixture
def customer_app():
    app = FastAPI()
    app.include_router(customer_router)
    return app


def _recv(ws):
    """يستقبل الحدث التالي متجاوزاً primer الـ ``session_ready`` (D-WS-FLAP-003)."""
    while True:
        ev = ws.receive_json()
        if isinstance(ev, dict) and ev.get("type") == "session_ready":
            continue
        return ev


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
        # D-WS-CONN-001: الاتصال يفك الـ JWT عبر decode_token_payload (لا decode_user_id).
        with patch(
            "app.api.routers.customer_chat.decode_token_payload", side_effect=HTTPException(401)
        ):
            with client.websocket_connect("/api/chat/ws") as ws:
                data = _recv(ws)
                assert data["type"] == "error"
                assert data["payload"]["code"] == "WS_AUTH_INVALID"


def test_customer_ws_admin(customer_app):
    # D-WS-CONN-001/002: admin actor on customer endpoint → accept() → error(403) → close(4403).
    # is_admin يأتي من الـ JWT (claim is_admin أو دور ADMIN ضمن roles) — لا استعلام DB.
    client = TestClient(customer_app)

    with patch(
        "app.api.routers.customer_chat.extract_websocket_auth", return_value=("token", "jwt")
    ):
        with patch(
            "app.api.routers.customer_chat.decode_token_payload",
            return_value={"sub": "1", "is_admin": True},
        ):
            with client.websocket_connect("/api/chat/ws") as ws:
                data = _recv(ws)
                assert data["type"] == "error"
                assert data["payload"]["status_code"] == 403
                assert "Admin accounts" in data["payload"]["details"]


def test_customer_ws_empty_question(customer_app):
    # D-WS-CONN-001: valid non-admin connects (session_ready primer) → سؤال فارغ → خطأ واضح.
    client = TestClient(customer_app)

    with patch(
        "app.api.routers.customer_chat.extract_websocket_auth", return_value=("token", "jwt")
    ):
        with patch(
            "app.api.routers.customer_chat.decode_token_payload",
            return_value={"sub": "1", "is_admin": False},
        ):
            with client.websocket_connect("/api/chat/ws") as ws:
                ws.send_json({"question": ""})
                data = _recv(ws)
                assert data["type"] == "error"
                assert "Question is required" in data["payload"]["details"]


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
