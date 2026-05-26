"""
اختبارات WebSocketHeartbeatSkill — D-WS-FLAP-002 / ISS-WS-FLAP-002.

السيناريو الكارثي (مكتشف بالتجريب الحي 2026-05-26 على GitHub Codespaces):
1. Frontend يرسل `{"type": "ping"}` كل 25 ثانية كـ application-level heartbeat
2. Backend WS loop يعالج كل رسالة كـ «سؤال» → `payload.get("question", "")` = ""
3. Backend يرد بـ `{"type": "error", "payload": {"details": "Question is required"}}`
4. Frontend ينتظر `{"type": "pong"}` لمدة 10s — لا يصل
5. Frontend يُغلق الـ socket بـ code 1001 → reconnect
6. Cycle يتكرر كل ~35s → flapping pattern (متصل → إعادة الاتصال → غير متصل)

هذا الـ Skill يحل المشكلة بمعالج موحَّد لكل رسائل التحكم:
- `{"type": "ping"}` → `{"type": "pong", "ts": <iso>}`
- `{"type": "heartbeat"}` → `{"type": "heartbeat_ack", "ts": <iso>}`
- `{"type": "noop"}` → silent swallow
- `{"type": "anything_else"}` → passthrough (لم تُعالَج)
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.services.skills.ws_heartbeat_skill import (
    handle_control_message,
    is_control_message,
)

# ── Fake WebSocket ───────────────────────────────────────────────────────────


class FakeWebSocket:
    """واجهة WebSocket مُزيَّفة لاختبار handle_control_message."""

    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self._raise_on_send: bool = False

    async def send_json(self, data: dict[str, Any]) -> None:
        if self._raise_on_send:
            raise RuntimeError("Connection closed")
        self.sent.append(data)


# ── is_control_message ───────────────────────────────────────────────────────


class TestIsControlMessage:
    def test_ping_is_control(self) -> None:
        assert is_control_message({"type": "ping"}) is True

    def test_heartbeat_is_control(self) -> None:
        assert is_control_message({"type": "heartbeat"}) is True

    def test_noop_is_control(self) -> None:
        assert is_control_message({"type": "noop"}) is True

    def test_uppercase_ping_is_control(self) -> None:
        assert is_control_message({"type": "PING"}) is True

    def test_chat_question_is_not_control(self) -> None:
        assert is_control_message({"question": "ما هو التكامل؟"}) is False

    def test_type_chat_message_is_not_control(self) -> None:
        # نوع شائع آخر — لا يُعتبر تحكماً
        assert is_control_message({"type": "message", "content": "..."}) is False

    def test_empty_dict_is_not_control(self) -> None:
        assert is_control_message({}) is False

    def test_none_is_not_control(self) -> None:
        assert is_control_message(None) is False

    def test_string_is_not_control(self) -> None:
        assert is_control_message("ping") is False

    def test_list_is_not_control(self) -> None:
        assert is_control_message(["ping"]) is False

    def test_int_type_is_not_control(self) -> None:
        assert is_control_message({"type": 42}) is False


# ── handle_control_message — happy paths ─────────────────────────────────────


@pytest.mark.asyncio
class TestHandlePingPong:
    async def test_ping_replies_with_pong(self) -> None:
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {"type": "ping"})
        assert handled is True
        assert len(ws.sent) == 1
        assert ws.sent[0]["type"] == "pong"
        assert "ts" in ws.sent[0]
        # ISO-8601 format check
        assert (
            ws.sent[0]["ts"].endswith("+00:00")
            or "Z" in ws.sent[0]["ts"]
            or "+" in ws.sent[0]["ts"]
        )

    async def test_pong_serialized_correctly(self) -> None:
        """Verify the pong reply is JSON-serializable and frontend-compatible."""
        ws = FakeWebSocket()
        await handle_control_message(ws, {"type": "ping"})
        serialized = json.dumps(ws.sent[0])
        # Frontend checks: event.data.includes('"type":"pong"')
        assert '"type":"pong"' in serialized.replace(" ", "")

    async def test_heartbeat_replies_with_ack(self) -> None:
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {"type": "heartbeat"})
        assert handled is True
        assert ws.sent[0]["type"] == "heartbeat_ack"

    async def test_noop_swallowed_silently(self) -> None:
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {"type": "noop"})
        assert handled is True
        assert ws.sent == []  # لا رد

    async def test_ping_correlation_id_preserved(self) -> None:
        """لو أرسل العميل id، يجب أن يُضمَّن في الـ pong لـ tracing."""
        ws = FakeWebSocket()
        await handle_control_message(ws, {"type": "ping", "id": "client-abc-123"})
        assert ws.sent[0]["type"] == "pong"
        assert ws.sent[0]["id"] == "client-abc-123"

    async def test_ping_with_request_id(self) -> None:
        ws = FakeWebSocket()
        await handle_control_message(ws, {"type": "ping", "request_id": "req-42"})
        assert ws.sent[0]["id"] == "req-42"

    async def test_ping_uppercase_normalized(self) -> None:
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {"type": "PING"})
        assert handled is True
        assert ws.sent[0]["type"] == "pong"


# ── handle_control_message — non-control passthrough ─────────────────────────


@pytest.mark.asyncio
class TestPassthrough:
    async def test_question_passes_through(self) -> None:
        """رسالة سؤال عادية يجب أن تمر — يعالجها الـ caller كسؤال."""
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {"question": "ما التكامل؟"})
        assert handled is False
        assert ws.sent == []  # لا رد heartbeat — passthrough

    async def test_empty_dict_passes_through(self) -> None:
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {})
        assert handled is False
        assert ws.sent == []

    async def test_other_type_passes_through(self) -> None:
        ws = FakeWebSocket()
        handled = await handle_control_message(ws, {"type": "subscribe", "topic": "foo"})
        assert handled is False
        assert ws.sent == []


# ── handle_control_message — fail-open guarantees ────────────────────────────


@pytest.mark.asyncio
class TestFailOpen:
    async def test_send_failure_does_not_raise(self) -> None:
        """لو فشل send_json (client closed mid-handshake)، يجب أن يُرجع True بهدوء."""
        ws = FakeWebSocket()
        ws._raise_on_send = True
        # لا exception — يُرجع True
        handled = await handle_control_message(ws, {"type": "ping"})
        assert handled is True

    async def test_send_failure_does_not_propagate_to_caller(self) -> None:
        """قاعدة الذهبية: heartbeat skill لا يكسر الـ loop أبداً."""
        ws = AsyncMock()
        ws.send_json.side_effect = Exception("Network unreachable")
        handled = await handle_control_message(ws, {"type": "heartbeat"})
        assert handled is True


# ── Integration: simulate full flapping scenario ─────────────────────────────


@pytest.mark.asyncio
class TestFlappingPreventionScenario:
    """يحاكي السيناريو الكارثي الأصلي ويُثبت أن الـ Skill يحلّه."""

    async def test_simulated_heartbeat_cycle(self) -> None:
        """
        السيناريو: الواجهة ترسل ping كل 25s، تتوقع pong خلال 10s.
        قبل D-WS-FLAP-002: الـ backend يُرجع error → no pong → close → flap.
        بعد D-WS-FLAP-002: الـ backend يُرجع pong → no flap.
        """
        ws = FakeWebSocket()

        # محاكاة 3 دورات heartbeat (= 75 ثانية في الواقع)
        for cycle in range(3):
            payload = {"type": "ping", "id": f"hb-{cycle}"}
            handled = await handle_control_message(ws, payload)
            assert handled is True, f"cycle {cycle}: should be handled as control"

        # 3 pong replies received — frontend's pong-timeout will be cleared 3 times
        assert len(ws.sent) == 3
        for cycle, reply in enumerate(ws.sent):
            assert reply["type"] == "pong"
            assert reply["id"] == f"hb-{cycle}"

    async def test_chat_after_heartbeat_still_works(self) -> None:
        """التأكد من أن السؤال الحقيقي بعد ping يعمل بشكل طبيعي."""
        ws = FakeWebSocket()

        # 1. heartbeat ping
        assert await handle_control_message(ws, {"type": "ping"}) is True
        # 2. سؤال حقيقي
        assert await handle_control_message(ws, {"question": "ما الجواب؟"}) is False
        # 3. heartbeat آخر
        assert await handle_control_message(ws, {"type": "ping"}) is True

        # ws.sent يحوي pong مرتين (السؤال لم يُعالَج هنا)
        assert len([m for m in ws.sent if m["type"] == "pong"]) == 2

    async def test_pong_format_matches_frontend_expectation(self) -> None:
        """
        Frontend code:
            if (event.data.includes('"type":"pong"')) { clearTimeout(...); }

        Verify the pong JSON contains exactly that substring.
        """
        ws = FakeWebSocket()
        await handle_control_message(ws, {"type": "ping"})
        serialized = json.dumps(ws.sent[0])
        # Frontend uses string includes() — must match exactly
        normalized = serialized.replace(" ", "")
        assert '"type":"pong"' in normalized
