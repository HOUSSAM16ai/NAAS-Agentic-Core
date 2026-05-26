import os
from unittest.mock import patch

import pytest

from app.core.settings.base import (
    AppSettings,
    BaseServiceSettings,
    _normalize_csv_or_list,
    get_settings,
)


class TestCoreConfig:
    """Test suite for the unified configuration system."""

    def test_settings_defaults(self, monkeypatch):
        """Verify default settings are correct."""
        get_settings.cache_clear()
        monkeypatch.setenv("ENVIRONMENT", "development")
        settings = get_settings()
        assert settings.SERVICE_NAME == "CogniForge-Core"
        assert settings.ENVIRONMENT == "development"
        assert settings.DEBUG is False
        assert settings.API_V1_STR == "/api/v1"

    def test_csv_parsing(self):
        """Verify CSV string parsing for lists."""
        assert _normalize_csv_or_list(None) == []
        assert _normalize_csv_or_list("") == []
        assert _normalize_csv_or_list("foo,bar") == ["foo", "bar"]
        assert _normalize_csv_or_list(" foo , bar ") == ["foo", "bar"]
        assert _normalize_csv_or_list(["foo", "bar"]) == ["foo", "bar"]
        assert _normalize_csv_or_list('["foo", "bar"]') == ["foo", "bar"]

    def test_database_url_fallback(self):
        """Verify DB URL fallback logic.

        Two sources can inject DATABASE_URL even when env vars are cleared:
        1. base.py sets os.environ["DATABASE_URL"] from APP_DATABASE_URL at
           module import time (before patch.dict runs).
        2. pydantic-settings reads .env file directly via model_config env_file.

        We bypass both by passing DATABASE_URL=None explicitly and overriding
        model_config to skip .env loading for this test instance.
        """
        clean_env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("DATABASE_URL", "APP_DATABASE_URL")
        }
        with patch.dict(os.environ, clean_env, clear=True):
            os.environ.pop("DATABASE_URL", None)
            os.environ.pop("APP_DATABASE_URL", None)
            # Bypass .env file loading by constructing with _env_file=None
            settings = AppSettings(
                ENVIRONMENT="testing",
                DATABASE_URL=None,
                _env_file=None,  # type: ignore[call-arg]
            )
            assert "sqlite" in settings.DATABASE_URL
            assert ":memory:" in settings.DATABASE_URL

    def test_production_security_check(self):
        """Verify production security guardrails."""
        from pydantic import ValidationError

        # Should fail if DEBUG is True in Prod
        with pytest.raises(ValidationError, match="DEBUG must be False"):
            BaseServiceSettings(
                SERVICE_NAME="test",
                ENVIRONMENT="production",
                DEBUG=True,
                SECRET_KEY="x" * 64,
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            )

        # Should fail if weak secret (length) - Enforced globally by Pydantic
        with pytest.raises(ValidationError, match="Production SECRET_KEY is too weak"):
            BaseServiceSettings(
                SERVICE_NAME="test",
                ENVIRONMENT="production",
                DEBUG=False,
                SECRET_KEY="weak",
                DATABASE_URL="postgresql+asyncpg://user:pass@localhost/db",
            )

    def test_base_service_settings(self):
        """Verify BaseServiceSettings works for microservices."""
        settings = BaseServiceSettings(SERVICE_NAME="UserService", ENVIRONMENT="testing")
        assert settings.SERVICE_NAME == "UserService"
        assert settings.ENVIRONMENT == "testing"
        # Testing usually falls back to in-memory sqlite
        assert ":memory:" in settings.DATABASE_URL
