import logging
import sys
from unittest.mock import MagicMock

import pytest

from app.telemetry.otel_setup import _try_instrument_httpx, is_enabled


def test_is_enabled_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert is_enabled() is False


def test_is_enabled_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    assert is_enabled() is False


def test_is_enabled_when_whitespace_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "   \n\t  ")
    assert is_enabled() is False


def test_is_enabled_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
    assert is_enabled() is True


def test_try_instrument_httpx_fallback(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that _try_instrument_httpx swallows ImportError and logs gracefully."""
    # Force an ImportError for the opentelemetry instrumentor
    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.httpx", None)

    with caplog.at_level(logging.DEBUG):
        _try_instrument_httpx()

    # Assert that it doesn't crash and the correct debug log is emitted
    assert "otel_setup.httpx_skip" in caplog.text


def test_try_instrument_httpx_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that _try_instrument_httpx successfully calls instrument() on the mock."""
    mock_module = MagicMock()
    mock_instrumentor = MagicMock()
    mock_module.HTTPXClientInstrumentor = mock_instrumentor

    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.httpx", mock_module)
    monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation", MagicMock())
    monkeypatch.setitem(sys.modules, "opentelemetry", MagicMock())

    _try_instrument_httpx()

    # Assert that instrument was called on the instance
    assert mock_instrumentor.return_value.instrument.called
