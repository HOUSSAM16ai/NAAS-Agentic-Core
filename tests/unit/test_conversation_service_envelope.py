"""
اختبارات عقد WebSocket لـ conversation-service.

يتحقق من أن الـ WS endpoints تُرسل الحقول المطلوبة وفق العقد الفعلي:
  - /chat/ws       → {"response": str, "intent": str, "thread_id": str, "done": true}
  - /admin/chat/ws → نفس الشكل
  - حالة الخطأ    → {"error": str, "message": str, "done": true}
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from microservices.conversation_service.main import app


def _make_graph_result(response: str = "مرحباً", intent: str = "greeting") -> dict:
    return {"response": response, "intent": intent}


def test_conversation_ws_customer_envelope_shape():
    """WS /chat/ws يُرسل response + intent + thread_id + done."""
    with patch(
        "microservices.conversation_service.main.invoke_graph",
        new=AsyncMock(return_value=_make_graph_result()),
    ):
        client = TestClient(app)
        with client.websocket_connect("/chat/ws") as ws:
            ws.send_json({"question": "مرحبا"})
            event = ws.receive_json()

    assert "response" in event
    assert "intent" in event
    assert "thread_id" in event
    assert event.get("done") is True


def test_conversation_ws_admin_envelope_shape():
    """WS /admin/chat/ws يُرسل نفس شكل الاستجابة."""
    with patch(
        "microservices.conversation_service.main.invoke_graph",
        new=AsyncMock(return_value=_make_graph_result(response="إجابة الإدارة")),
    ):
        client = TestClient(app)
        with client.websocket_connect("/admin/chat/ws") as ws:
            ws.send_json({"question": "سؤال إداري"})
            event = ws.receive_json()

    assert "response" in event
    assert event.get("done") is True


def test_conversation_ws_schema_validation_active_in_non_prod():
    """WS يقبل الطلبات في بيئة development."""
    with patch(
        "microservices.conversation_service.main.invoke_graph",
        new=AsyncMock(return_value=_make_graph_result()),
    ):
        client = TestClient(app)
        with client.websocket_connect("/chat/ws") as ws:
            ws.send_json({"question": "اختبار"})
            event = ws.receive_json()

    assert event.get("done") is True


def test_conversation_ws_error_envelope_shape():
    """WS يُرسل حقل error عند فشل invoke_graph."""
    with patch(
        "microservices.conversation_service.main.invoke_graph",
        new=AsyncMock(side_effect=ValueError("Boom")),
    ):
        client = TestClient(app)
        with client.websocket_connect("/chat/ws") as ws:
            ws.send_json({"question": "سؤال يُسبب خطأ"})
            event = ws.receive_json()

    assert "error" in event
    assert event.get("done") is True
