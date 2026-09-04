import builtins
from unittest.mock import MagicMock

from app.infrastructure.clients.orchestrator.local_fallback import LocalFallbackMixin


class TestLocalFallbackMixin:
    def test_record_fallback_success(self, monkeypatch):
        # We need to monkeypatch the actual import inside the function
        mock_mark = MagicMock()

        # In sys.modules we can mock the whole module or we can patch the function
        import app.telemetry.path_observer
        monkeypatch.setattr(app.telemetry.path_observer, "mark_fallback_used", mock_mark)

        LocalFallbackMixin._record_fallback("test_fallback_name")

        mock_mark.assert_called_once_with("test_fallback_name")

    def test_record_fallback_swallows_exception(self, monkeypatch):
        mock_mark = MagicMock(side_effect=ValueError("Telemetry failed"))
        import app.telemetry.path_observer
        monkeypatch.setattr(app.telemetry.path_observer, "mark_fallback_used", mock_mark)

        # Should not raise
        LocalFallbackMixin._record_fallback("test_fallback_name")
        mock_mark.assert_called_once_with("test_fallback_name")

    def test_record_fallback_swallows_importerror(self, monkeypatch):
        # We simulate an ImportError by patching the built-in __import__ to raise ImportError
        # if app.telemetry.path_observer is imported

        original_import = builtins.__import__

        def mock_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "app.telemetry.path_observer":
                raise ImportError("No module named app.telemetry.path_observer")
            return original_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        # Should not raise
        LocalFallbackMixin._record_fallback("test_fallback_name")
