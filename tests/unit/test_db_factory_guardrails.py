import os
from unittest.mock import patch

import pytest
from pydantic_settings import SettingsConfigDict

from app.core.database import create_db_engine
from app.core.settings.base import BaseServiceSettings

# -----------------------------------------------------------------------------
# GUARDRAIL: DATABASE CONNECTION SECURITY & STABILITY
# -----------------------------------------------------------------------------
# This test suite is a NON-NEGOTIABLE LAW against the "Supabase Transaction Pooler"
# disaster. It enforces strict handling of:
# 1. URL-encoded passwords (e.g. '%40' for '@').
# 2. 'sslmode' stripping for 'asyncpg' compatibility.
# 3. Correct SSLContext injection for secure connections.
# 4. Supabase Pooler Cache Settings (statement_cache_size=0).
#
# DO NOT MODIFY OR DELETE WITHOUT ARCHITECT APPROVAL.
# -----------------------------------------------------------------------------


class MockSettings(BaseServiceSettings):
    DATABASE_URL: str = "postgresql://user:pass%40word@host:5432/db?sslmode=require"
    APP_DATABASE_URL: str | None = None  # prevent .env override
    SERVICE_NAME: str = "guardrail_test_service"
    ENVIRONMENT: str = "testing"

    model_config = SettingsConfigDict(env_file=None, extra="ignore")  # type: ignore[assignment]


@pytest.mark.asyncio
@patch("app.core.database.create_async_engine")
async def test_guardrail_db_url_password_encoding(mock_create_engine, monkeypatch):
    """
    CRITICAL: Verifies that special characters in passwords (URL encoded) are NOT
    lost or double-decoded during the `make_url` -> `render_as_string` roundtrip.
    """
    # Remove real DB URLs from env so MockSettings.DATABASE_URL field default is used.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)

    settings = MockSettings()
    create_db_engine(settings)

    args, _ = mock_create_engine.call_args
    db_url = args[0]

    # STRICT CHECK 1: Password must retain encoding
    assert "pass%40word" in db_url, (
        f"❌ CATASTROPHIC FAILURE: Password encoding lost. Expected 'pass%40word' in '{db_url}'"
    )
    assert "***" not in db_url


@pytest.mark.asyncio
@patch("app.core.database.create_async_engine")
async def test_guardrail_ssl_mode_handling(mock_create_engine):
    """
    CRITICAL: Verifies that 'sslmode' is stripped from the URL (causing asyncpg crashes)
    and correctly converted to a Python SSLContext.
    """
    with patch.dict(os.environ, {}, clear=True):
        settings = MockSettings()
        create_db_engine(settings)

        args, kwargs = mock_create_engine.call_args
        db_url = args[0]
        connect_args = kwargs.get("connect_args", {})

        assert "sslmode" not in db_url
        assert "ssl" in connect_args

        ssl_ctx = connect_args["ssl"]
        assert ssl_ctx.check_hostname is False


@pytest.mark.asyncio
@patch("app.core.database.create_async_engine")
async def test_guardrail_supabase_pooler_compatibility(mock_create_engine):
    """
    CRITICAL: Verifies that statement caching is DISABLED for Supabase Poolers.
    Poolers running in transaction mode do not support prepared statements properly.
    """
    with patch.dict(os.environ, {}, clear=True):
        settings = MockSettings()
        create_db_engine(settings)

        _, kwargs = mock_create_engine.call_args
        connect_args = kwargs.get("connect_args", {})

        # STRICT CHECK 6: Statement cache size must be 0
        assert connect_args.get("statement_cache_size") == 0, (
            "❌ FAILURE: statement_cache_size must be 0 for Supabase Pooler compatibility."
        )
        assert connect_args.get("prepared_statement_cache_size") == 0, (
            "❌ FAILURE: prepared_statement_cache_size must be 0 for Supabase Pooler compatibility."
        )
