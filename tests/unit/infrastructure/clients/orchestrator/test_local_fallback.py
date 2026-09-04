import pytest
import logging
import asyncio
import builtins
import sys

from app.infrastructure.clients.orchestrator.local_fallback import _mark_fallback, LocalFallbackMixin

@pytest.mark.asyncio
async def test_mark_fallback_silenced_exception_logged(monkeypatch, caplog):
    # Monkeypatch the module where it is imported inside the helper

    # We can mock sys.modules to simulate failure of import or mock the function.
    # The helper tries to import `mark_fallback_used` from `app.telemetry.path_observer`.

    class FakePathObserver:
        def mark_fallback_used(self, path):
            raise ValueError("Telemetry broke!")

    monkeypatch.setitem(sys.modules, "app.telemetry.path_observer", FakePathObserver())

    with caplog.at_level(logging.DEBUG):
        _mark_fallback("some_test_stream")

    assert "fallback_telemetry_failed" in caplog.text
    # Ensure it logged at DEBUG level
    assert any(record.levelname == "DEBUG" and "fallback_telemetry_failed" in record.message for record in caplog.records)

    # ensure that extra kwargs are logged. caplog doesn't strictly check `extra` easily without record inspection, but we can check the record.
    record = next(r for r in caplog.records if r.message == "fallback_telemetry_failed")
    assert getattr(record, "path", None) == "some_test_stream"


@pytest.mark.asyncio
async def test_local_retrieval_stream_preserves_behavior_on_telemetry_failure(monkeypatch, caplog):
    class FakePathObserver:
        def mark_fallback_used(self, path):
            raise ValueError("Telemetry broke again!")

    monkeypatch.setitem(sys.modules, "app.telemetry.path_observer", FakePathObserver())

    class FakeClient(LocalFallbackMixin):
        async def _build_local_retrieval_response(self, question, history_messages=None):
            return "Test Response"

        async def _stream_markdown_typing(self, content):
            yield content

    client = FakeClient()

    with caplog.at_level(logging.DEBUG):
        chunks = [chunk async for chunk in client._stream_local_retrieval_response("Q")]

    assert chunks == ["Test Response"]
    assert "fallback_telemetry_failed" in caplog.text
