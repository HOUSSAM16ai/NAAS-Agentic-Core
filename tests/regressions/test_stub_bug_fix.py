from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_chat_stream_is_real_implementation():
    """
    Verifies that the WebSocket chat endpoint enforces authentication.

    D-WS-002: accept() → send_json(WS_AUTH_MISSING) → close(4401).
    A stub would accept unauthenticated connections without sending an error.
    """
    with client.websocket_connect("/admin/api/chat/ws") as ws:
        data = ws.receive_json()
        assert data["type"] == "error", (
            f"Expected error message, got: {data}. "
            "The stub implementation might still be active."
        )
        assert data["payload"]["status_code"] == 4401, (
            f"Expected 4401 Unauthorized, but got {data['payload'].get('status_code')}. "
            "The stub implementation might still be active."
        )
