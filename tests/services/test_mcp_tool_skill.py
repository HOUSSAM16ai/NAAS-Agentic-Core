import logging
import sys
from importlib import reload


def test_mcp_tool_skill_telemetry_disabled_prometheus_unavailable(monkeypatch):
    """Smoke test: monkeypatch prometheus_client to raise during import."""

    # We need to mock logging.getLogger to capture the warning,
    # but we must accept optional arguments to avoid breaking pytest's internal logging hook.
    from unittest.mock import MagicMock

    mock_logger = MagicMock()
    original_get_logger = logging.getLogger

    def mock_get_logger(name=None):
        if name == "cogniforge.skills.mcp_tool":
            return mock_logger
        return original_get_logger(name)

    monkeypatch.setattr(logging, "getLogger", mock_get_logger)

    import app.services.skills.mcp_tool_skill as mcp_mod

    try:
        # Force prometheus_client to not be found
        monkeypatch.setitem(sys.modules, "prometheus_client", None)

        # reset mock before reload in case it was imported before
        mock_logger.reset_mock()
        reload(mcp_mod)

        # Ensure _rec is defined
        assert hasattr(mcp_mod, "_rec")

        # Verify logger.warning was called once
        assert mock_logger.warning.call_count == 1

        # Verify the argument to the warning call
        args, kwargs = mock_logger.warning.call_args
        assert args[0] == "mcp_telemetry_disabled_prometheus_unavailable"
        assert "error_type" in kwargs["extra"]
        assert "error" in kwargs["extra"]

    finally:
        # Restore module state
        monkeypatch.undo()
        # Reloading after removing monkeypatch to restore normal functionality
        reload(mcp_mod)
