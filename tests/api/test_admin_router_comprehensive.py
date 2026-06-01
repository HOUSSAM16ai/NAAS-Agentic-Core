"""Comprehensive tests for Admin router."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routers.admin import (
    get_current_user_id,
    router,
)
from app.core.database import get_db
from app.core.domain.user import User


def _recv(ws):
    """يستقبل الحدث التالي متجاوزاً primer الـ ``session_ready`` (D-WS-FLAP-003)."""
    while True:
        ev = ws.receive_json()
        if isinstance(ev, dict) and ev.get("type") == "session_ready":
            continue
        return ev


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def mock_db():
    return AsyncMock()


def test_get_actor_user_not_found(client, mock_db):
    client.app.dependency_overrides[get_db] = lambda: mock_db
    client.app.dependency_overrides[get_current_user_id] = lambda: 999
    mock_db.get.return_value = None

    response = client.get("/admin/api/chat/latest")
    assert response.status_code == 401
    assert "User not found" in response.json()["detail"]


def test_get_actor_user_inactive(client, mock_db):
    client.app.dependency_overrides[get_db] = lambda: mock_db
    client.app.dependency_overrides[get_current_user_id] = lambda: 1

    user = MagicMock(spec=User)
    user.is_active = False
    mock_db.get.return_value = user

    response = client.get("/admin/api/chat/latest")
    assert response.status_code == 403
    assert "User inactive" in response.json()["detail"]


def test_get_latest_chat_not_admin(client, mock_db):
    client.app.dependency_overrides[get_db] = lambda: mock_db
    client.app.dependency_overrides[get_current_user_id] = lambda: 1

    user = MagicMock(spec=User)
    user.is_active = True
    user.is_admin = False
    mock_db.get.return_value = user
    # Mock refresh and expunge
    mock_db.refresh = AsyncMock()
    mock_db.expunge = MagicMock()

    response = client.get("/admin/api/chat/latest")
    assert response.status_code == 403
    assert "Admin access required" in response.json()["detail"]


def test_chat_stream_ws_not_admin(app):
    client = TestClient(app)
    mock_actor = MagicMock(spec=User)
    mock_actor.is_active = True
    mock_actor.is_admin = False

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_actor
    # Ensure db.expunge is a synchronous MagicMock, not AsyncMock, because it's called synchronously
    mock_db.expunge = MagicMock()

    mock_session_manager = MagicMock()
    mock_session_manager.__aenter__.return_value = mock_db
    mock_session_manager.__aexit__.return_value = None

    with patch(
        "app.api.routers.admin.async_session_factory",
        return_value=mock_session_manager,
    ):
        # Mock extract_websocket_auth to return a token
        with patch(
            "app.api.routers.admin.extract_websocket_auth",
            return_value=("valid_token", "json"),
        ):
            # D-WS-CONN-001/002: الهوية من الـ JWT (لا decode_user_id ولا db.get).
            # توكن غير إدمن (لا claim is_admin ولا دور ADMIN) → رفض على قناة الإدمن.
            with patch(
                "app.api.routers.admin.decode_token_payload",
                return_value={"sub": "1", "is_admin": False},
            ):
                with client.websocket_connect("/admin/api/chat/ws") as websocket:
                    data = _recv(websocket)
                    assert data["type"] == "error"
                    assert "Standard accounts" in data["payload"]["details"]


def test_chat_stream_ws_empty_question(app):
    client = TestClient(app)
    mock_actor = MagicMock(spec=User)
    mock_actor.is_active = True
    mock_actor.is_admin = True

    mock_db = AsyncMock()
    mock_db.get.return_value = mock_actor
    mock_db.expunge = MagicMock()

    mock_session_manager = MagicMock()
    mock_session_manager.__aenter__.return_value = mock_db
    mock_session_manager.__aexit__.return_value = None

    with patch(
        "app.api.routers.admin.async_session_factory",
        return_value=mock_session_manager,
    ):
        with patch(
            "app.api.routers.admin.extract_websocket_auth",
            return_value=("valid_token", "json"),
        ):
            # D-WS-CONN-001/002: توكن إدمن صالح → session_ready → سؤال فارغ → خطأ واضح.
            with patch(
                "app.api.routers.admin.decode_token_payload",
                return_value={"sub": "1", "is_admin": True},
            ):
                with client.websocket_connect("/admin/api/chat/ws") as websocket:
                    websocket.send_json({"question": ""})
                    data = _recv(websocket)
                    assert data["type"] == "error"
                    assert "Question is required" in data["payload"]["details"]


def test_chat_stream_ws_orchestrator_error(app):
    client = TestClient(app)
    mock_actor = MagicMock()
    mock_actor.is_active = True
    mock_actor.is_admin = True

    mock_db = MagicMock()  # Not AsyncMock because we need sync execute for scalars()

    class MockScalars:
        def all(self):
            return []

    class MockResult:
        def scalars(self):
            return MockScalars()

    async def mock_execute(*args, **kwargs):
        return MockResult()

    mock_db.execute = mock_execute
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.get = AsyncMock(return_value=mock_actor)

    mock_session_manager = MagicMock()
    mock_session_manager.__aenter__.return_value = mock_db
    mock_session_manager.__aexit__.return_value = None

    with (
        patch(
            "app.api.routers.admin.async_session_factory",
            return_value=mock_session_manager,
        ),
        patch(
            "app.api.routers.admin.extract_websocket_auth",
            return_value=("valid_token", "json"),
        ),
        # D-WS-CONN-001/002: الهوية من الـ JWT — توكن إدمن صالح يُشغّل دوراً حقيقياً.
        patch(
            "app.api.routers.admin.decode_token_payload",
            return_value={"sub": "1", "is_admin": True},
        ),
        patch(
            "app.api.routers.admin.orchestrator_client.chat_with_agent",
            side_effect=RuntimeError("Orchestrator error"),
        ),
    ):
        with client.websocket_connect("/admin/api/chat/ws") as websocket:
            websocket.send_json({"question": "test"})
            data = _recv(websocket)
            if data["type"] == "conversation_init":
                data = _recv(websocket)
            assert data["type"] == "error"
            assert "Orchestrator error" in data["payload"]["details"]
