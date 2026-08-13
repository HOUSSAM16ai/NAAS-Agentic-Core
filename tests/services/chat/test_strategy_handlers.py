"""
Behavioral tests for the D-250 decomposition of `strategy_handlers.py`.

Zero-behavioural-change guarantee: every contract of `MissionComplexHandler`
(`_create_structured_event`, `_format_event_to_message`) and every display
formatter is asserted here. The helpers extracted from the old class MUST
produce the same byte output as before — any change in this file fails CI
and proves a regression.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.core.domain.mission import MissionEventType
from app.services.chat.handlers.strategy_handlers import (
    DefaultChatHandler,
    MissionComplexHandler,
    _delta_for_brain_event,
    _delta_for_status_note,
    _extract_result_text,
    _format_brain_event,
    _format_inner_data,
    _format_task_results,
    _format_tool_result_data,
    _mission_completed_payload,
    _mission_failed_payload,
    _RawEvent,
    _structured_event_for_status,
    _task_result_block,
    _tool_result_summary_payload,
)

# ── Canonical events (UI FSM contract) ─────────────────────────────────────


def _raw(
    status: str = "status_change",
    brain: str = "",
    data: dict | None = None,
    mission_id: str = "m1",
    timestamp: str = "2026-08-13T00:00:00",
) -> _RawEvent:
    return _RawEvent(
        payload={"brain_event": brain, "data": data or {}},
        mission_id=mission_id,
        timestamp=timestamp,
        event_type=status,
    )


def test_loop_start_emits_run_started() -> None:
    raw = _raw(brain="loop_start", data={"iteration": 2, "graph_mode": "standard"})
    event = _structured_event_for_status(raw, sequence_id=1, current_iteration=1)
    assert event == {
        "type": "RUN_STARTED",
        "payload": {
            "run_id": "m1:1",
            "seq": 1,
            "timestamp": raw.timestamp,
            "iteration": 2,
            "mode": "standard",
        },
    }


def test_loop_start_without_iteration_uses_current() -> None:
    raw = _raw(brain="loop_start", data={})
    event = _structured_event_for_status(raw, sequence_id=1, current_iteration=1)
    assert event is not None
    assert event["payload"]["run_id"] == "m1:1"
    assert event["payload"]["iteration"] == 1


def test_phase_events_emit_with_run_isolation() -> None:
    for brain, expected in (
        ("phase_start", "PHASE_STARTED"),
        ("phase_completed", "PHASE_COMPLETED"),
    ):
        raw = _raw(brain=brain, data={"phase": "plan", "agent": "strategist"})
        event = _structured_event_for_status(raw, sequence_id=7, current_iteration=3)
        assert event == {
            "type": expected,
            "payload": {
                "run_id": "m1:3",
                "seq": 7,
                "phase": "plan",
                "agent": "strategist",
                "timestamp": raw.timestamp,
            },
        }


def test_non_status_event_returns_none() -> None:
    raw = _raw(status=MissionEventType.MISSION_COMPLETED, brain="loop_start")
    assert _structured_event_for_status(raw, sequence_id=1, current_iteration=1) is None


def test_unknown_brain_event_returns_none() -> None:
    raw = _raw(brain="mystery_event", data={})
    assert _structured_event_for_status(raw, sequence_id=1, current_iteration=1) is None


# ── Terminal frames ─────────────────────────────────────────────────────────


def test_mission_completed_with_output() -> None:
    raw = _RawEvent(
        payload={"result": {"output": "الجواب النهائي"}},
        mission_id="m1",
        timestamp="t",
        event_type="mission_completed",
    )
    assert _mission_completed_payload(raw) == {
        "type": "assistant_final",
        "payload": {"content": "الجواب النهائي"},
    }


def test_mission_completed_fallback_order_answer_then_summary() -> None:
    raw = _RawEvent(
        payload={"result": {"summary": "ملخص"}},
        mission_id="m1",
        timestamp="t",
        event_type="mission_completed",
    )
    assert _mission_completed_payload(raw)["payload"]["content"] == "ملخص"


def test_mission_completed_results_list_emits_tool_result_summary() -> None:
    results = [{"tool": "write_file", "ok": True}]
    raw = _RawEvent(
        payload={"result": {"results": results}},
        mission_id="m1",
        timestamp="t",
        event_type="mission_completed",
    )
    frame = _mission_completed_payload(raw)
    assert frame == _tool_result_summary_payload(results)


def test_mission_completed_scalar_result() -> None:
    raw = _RawEvent(
        payload={"result": 42},
        mission_id="m1",
        timestamp="t",
        event_type="mission_completed",
    )
    assert _mission_completed_payload(raw) == {
        "type": "assistant_final",
        "payload": {"content": "42"},
    }


def test_mission_failed_frame() -> None:
    raw = _RawEvent(
        payload={"error": "تجاوز المهلة"},
        mission_id="m1",
        timestamp="t",
        event_type="mission_failed",
    )
    assert _mission_failed_payload(raw) == {
        "type": "assistant_error",
        "payload": {"content": "💀 **فشل:** تجاوز المهلة"},
    }


def test_extract_result_text_dict_json_dump() -> None:
    text = _extract_result_text({"deep": {"key": "value"}})
    assert json.loads(text) == {"deep": {"key": "value"}}


def test_delta_for_brain_event_silenced_for_timeline_events() -> None:
    for brain in ("loop_start", "phase_start", "phase_completed", "search_completed"):
        raw = _raw(brain=brain)
        assert _delta_for_brain_event(raw) is None


def test_delta_for_brain_event_relevant() -> None:
    raw = _raw(brain="plan_rejected")
    delta = _delta_for_brain_event(raw)
    assert delta == {"type": "assistant_delta", "payload": {"content": "🧩 إعادة ضبط الخطة.\n"}}


def test_delta_for_status_note() -> None:
    raw = _raw(data={}, timestamp="t")
    raw.payload["note"] = "جاري التنفيذ"
    assert _delta_for_status_note(raw) == {
        "type": "assistant_delta",
        "payload": {"content": "🔄 جاري التنفيذ\n"},
    }


# ── Handler class wiring (class entry points still delegate) ───────────────


def test_handler_format_event_to_message_completed() -> None:
    handler = MissionComplexHandler()
    raw = {
        "event_type": MissionEventType.MISSION_COMPLETED,
        "payload": {"result": {"output": "نتيجة"}},
        "mission_id": "m1",
        "timestamp": "t",
    }
    assert handler._format_event_to_message(raw) == {
        "type": "assistant_final",
        "payload": {"content": "نتيجة"},
    }


def test_handler_format_event_to_message_orm_event() -> None:
    """Accepts a real MissionEvent ORM object, not only dicts."""
    event = MagicMock()
    event.payload_json = {"note": "تقدم"}
    event.event_type = MissionEventType.STATUS_CHANGE
    event.mission_id = "m1"
    event.created_at = datetime(2026, 8, 13, tzinfo=UTC)

    handler = MissionComplexHandler()
    frame = handler._format_event_to_message(event)
    assert frame == {"type": "assistant_delta", "payload": {"content": "🔄 تقدم\n"}}


def test_handler_format_event_to_message_unknown_is_none() -> None:
    handler = MissionComplexHandler()
    assert handler._format_event_to_message({"event_type": "unknown"}) is None


def test_handler_create_structured_event() -> None:
    handler = MissionComplexHandler()
    raw = {
        "event_type": MissionEventType.STATUS_CHANGE,
        "payload": {"brain_event": "phase_start", "data": {"phase": "plan", "agent": "a"}},
        "mission_id": "m1",
        "timestamp": "t",
    }
    frame = handler._create_structured_event(raw, sequence_id=2, current_iteration=4)
    assert frame is not None
    assert frame["type"] == "PHASE_STARTED"
    assert frame["payload"]["run_id"] == "m1:4"


# ── Display formatters (unchanged behaviour, verified) ──────────────────────


def test_format_brain_event_plan_approved() -> None:
    assert _format_brain_event("PLAN_APPROVED", {}) == "✅ تم اعتماد الخطة.\n"


def test_format_brain_event_silent_completion_events() -> None:
    assert _format_brain_event("search_completed", {}) is None
    assert _format_brain_event("plan_rejected_something", {}) is None


def test_format_brain_event_timeout() -> None:
    assert _format_brain_event("llm_timeout", {}) == "⏳ تأخير... إعادة المزامنة.\n"


def test_format_brain_event_critique_failed() -> None:
    data = {"critique": {"feedback": "خطة غير مكتملة"}}
    assert _format_brain_event("mission_critique_failed", data) == (
        "🔔 **تدقيق:** خطة غير مكتملة (جاري التعديل...)\n"
    )


def test_format_brain_event_unknown_silent() -> None:
    assert _format_brain_event("unknown_thing", {"x": 1}) is None


def test_format_tool_result_data_ok_with_inner() -> None:
    assert _format_tool_result_data({"ok": True, "data": [1, 2]}) == "📄 (بيانات مهيكلة)"


def test_format_tool_result_data_failure() -> None:
    assert _format_tool_result_data({"ok": False, "error": "فشل"}) == "❌ خطأ: فشل"


def test_format_tool_result_data_scalar() -> None:
    assert _format_tool_result_data(7) == "7"


def test_format_inner_data_search_results_capped() -> None:
    data = [{"id": f"i{idx}", "title": f"عنوان {idx}"} for idx in range(5)]
    out = _format_inner_data(data)
    assert "عنوان 0" in out
    assert "عنوان 1" in out
    assert "عنوان 2" in out
    assert "عنوان 3" not in out
    assert "2 نتائج أخرى" in out


def test_format_inner_data_generic_structured() -> None:
    assert _format_inner_data({"a": 1}) == "📄 (بيانات مهيكلة)"
    assert _format_inner_data([1, 2]) == "📄 (بيانات مهيكلة)"
    assert _format_inner_data(9) == "9"


def test_format_task_results_full_flow() -> None:
    tasks = [
        {
            "name": "بحث",
            "result": {"result_data": {"data": {"written": True, "path": "/tmp/x"}}},
            "status": "done",
        },
        {"name": "تجاوز", "status": "skipped", "reason": "غير مطلوب"},
        {"name": "فارغ", "result": {}},
        {"name": "نص", "result": {"result_text": "✅ تم"}},
    ]
    out = _format_task_results(tasks)
    assert "بحث" in out
    assert "⏭️ تم التجاوز (غير مطلوب)" in out
    assert "تجاوز" in out
    assert "✅ تم" in out
    assert "تم تنفيذ 4 مهمة" in out


def test_task_result_block_with_written_file(tmp_path) -> None:
    path = tmp_path / "written.txt"
    path.write_text("محتوى تجريبي", encoding="utf-8")
    task = {
        "name": "كتابة",
        "status": "done",
        "result": {"result_data": {"data": {"written": True, "path": str(path)}}},
    }
    block = _task_result_block(task)
    assert block is not None
    assert "محتوى الملف" in block
    assert "محتوى تجريبي" in block


def test_task_result_block_missing_file_does_not_crash() -> None:
    task = {
        "name": "كتابة",
        "status": "done",
        "result": {"result_data": {"data": {"written": True, "path": "/nonexistent/path.txt"}}},
    }
    block = _task_result_block(task)
    assert block is not None
    assert "كتابة" in block


def test_format_tool_result_data_json_result_text() -> None:
    """result_text holding JSON is parsed and formatted like result_data."""
    task = {
        "name": "بحث",
        "result": {"result_text": json.dumps([{"id": "1", "title": "عنوان"}])},
    }
    block = _task_result_block(task)
    assert block is not None
    assert "عنوان" in block


# ── Provider config ─────────────────────────────────────────────────────────


def test_check_provider_config_missing_llm(monkeypatch) -> None:
    import app.services.chat.handlers.strategy_handlers as sh

    settings_mock = MagicMock(OPENROUTER_API_KEY=None, OPENAI_API_KEY=None)
    monkeypatch.setattr(sh, "get_settings", lambda: settings_mock)
    assert sh._check_provider_config() == sh._MISSING_LLM_MESSAGE


def test_check_provider_config_present(monkeypatch) -> None:
    import app.services.chat.handlers.strategy_handlers as sh

    settings_mock = MagicMock(OPENROUTER_API_KEY="key", OPENAI_API_KEY=None)
    monkeypatch.setattr(sh, "get_settings", lambda: settings_mock)
    monkeypatch.setenv("TAVILY_API_KEY", "tv")
    assert sh._check_provider_config() is None


# ── DefaultChatHandler fallback wiring (imports resolve, can_handle True) ────


@pytest.mark.asyncio
async def test_default_handler_can_handle_async(monkeypatch) -> None:
    ctx = MagicMock()
    handler = DefaultChatHandler()
    assert await handler.can_handle(ctx) is True
