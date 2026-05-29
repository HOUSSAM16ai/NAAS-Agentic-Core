"""
Integration test — verify WS routers wire the heartbeat skill correctly.

This is the **regression baseline** for D-WS-FLAP-002.
كان قبل الإصلاح: ping → "Question is required" → no pong → flap.
بعد الإصلاح: ping → pong → no flap.

We verify by static inspection of the router source code that:
1. `handle_control_message` is imported in `customer_chat.py`.
2. `handle_control_message` is imported in `admin.py`.
3. The call to `handle_control_message` happens BEFORE the `question` check.
4. `conversation_service.main` has an inline equivalent (since microservices can't
   import from `app.*` per architectural constitution §0.5).
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_file(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


class TestCustomerChatWiring:
    def test_import_present(self) -> None:
        source = _read_file("app/api/routers/customer_chat.py")
        assert "from app.services.skills.ws_heartbeat_skill import handle_control_message" in source

    def test_call_before_question_check(self) -> None:
        """الـ heartbeat handler يجب أن يُستدعى قبل `payload.get("question", ...)`."""
        source = _read_file("app/api/routers/customer_chat.py")

        # ابحث عن أول استدعاء داخل while-loop للـ chat_stream_ws
        ws_section_match = re.search(
            r"async def chat_stream_ws\b.*?(?=\n@router\.|\Z)",
            source,
            re.DOTALL,
        )
        assert ws_section_match is not None, "chat_stream_ws function not found"
        ws_section = ws_section_match.group(0)

        # تحقق من ترتيب الاستدعاءات داخل while-loop.
        # D-096 أضاف وسيط send_lock للنداء (customer_chat فقط)، لذا نطابق البادئة
        # بدون قوس الإغلاق حتى نتحمّل التوقيع المُطوَّر (2-arg أو 3-arg).
        handle_idx = ws_section.find("handle_control_message(websocket, payload")
        question_idx = ws_section.find('payload.get("question"')

        assert handle_idx > 0, "handle_control_message call not found"
        assert question_idx > 0, "question check not found"
        assert handle_idx < question_idx, (
            "D-WS-FLAP-002: handle_control_message MUST be called BEFORE question check, "
            "otherwise ping messages get treated as empty questions and trigger flapping."
        )

    def test_continue_after_control(self) -> None:
        source = _read_file("app/api/routers/customer_chat.py")
        # ابحث عن النمط المحدد: if await handle_control_message(...): continue
        # D-096: نسمح بوسائط إضافية (send_lock) قبل قوس الإغلاق عبر [^)]*.
        pattern = (
            r"if\s+await\s+handle_control_message\(websocket,\s*payload[^)]*\)\s*:\s*\n\s*continue"
        )
        assert re.search(pattern, source), (
            "handle_control_message must be followed by `continue` to skip question processing."
        )


class TestAdminWiring:
    def test_import_present(self) -> None:
        source = _read_file("app/api/routers/admin.py")
        assert "from app.services.skills.ws_heartbeat_skill import handle_control_message" in source

    def test_call_before_question_check(self) -> None:
        source = _read_file("app/api/routers/admin.py")
        # ابحث عن الـ ws endpoint
        ws_section_match = re.search(
            r"@router\.websocket\(['\"]/api/chat/ws['\"]\).*?(?=\n@router\.|\Z)",
            source,
            re.DOTALL,
        )
        assert ws_section_match is not None, "admin /api/chat/ws endpoint not found"
        ws_section = ws_section_match.group(0)

        handle_idx = ws_section.find("handle_control_message(websocket, payload)")
        question_idx = ws_section.find('payload.get("question"')

        assert handle_idx > 0, "handle_control_message call not found in admin WS"
        assert question_idx > 0, "question check not found in admin WS"
        assert handle_idx < question_idx, (
            "D-WS-FLAP-002: admin WS must call handle_control_message BEFORE question check."
        )


class TestConversationServiceWiring:
    """conversation_service ممنوع له استيراد من app.* — يجب وجود نسخة inline."""

    def test_inline_control_handler_present(self) -> None:
        source = _read_file("microservices/conversation_service/main.py")
        assert "_handle_control_message" in source, (
            "conversation_service must have inline _handle_control_message "
            "(cannot import from app.* per architectural §0.5)"
        )

    def test_inline_handler_recognizes_ping(self) -> None:
        source = _read_file("microservices/conversation_service/main.py")
        # تحقق من أن الـ control types مذكورة
        assert '"ping"' in source or "'ping'" in source
        assert '"pong"' in source or "'pong'" in source
        assert '"heartbeat"' in source or "'heartbeat'" in source

    def test_no_app_imports(self) -> None:
        """confirm conversation_service does not violate microservice isolation."""
        source = _read_file("microservices/conversation_service/main.py")
        # ابحث عن أي `from app.` import (يجب ألا يوجد)
        offending = re.findall(r"^from app\.[a-z_.]+ import", source, re.MULTILINE)
        assert not offending, (
            f"conversation_service must not import from app.* — found: {offending}"
        )


class TestDoctrineRegistration:
    def test_realtime_protocol_doctrine_registered(self) -> None:
        source = _read_file("app/services/skills/doctrine.py")
        assert "REALTIME_PROTOCOL_DOCTRINE" in source
        assert "REALTIME_PROTOCOL_DOCTRINE_VERSION" in source
        assert '"realtime_protocol"' in source, "doctrine manifest must register realtime_protocol"

    def test_manifest_lists_real_consumers(self) -> None:
        from app.services.skills.doctrine import SKILL_DOCTRINE_MANIFEST

        assert "realtime_protocol" in SKILL_DOCTRINE_MANIFEST
        entry = SKILL_DOCTRINE_MANIFEST["realtime_protocol"]
        consumers = entry["consumed_by"]
        assert "ws_heartbeat_skill.handle_control_message" in consumers
        assert "customer_chat.chat_stream_ws" in consumers
        assert "admin.admin_chat_stream_ws" in consumers
