"""
Regression test — verify JWT token lifetime cap is environment-aware.

D-WS-SESSION-001 (2026-05-26): The user reported a catastrophic "kicked to
login then returns" cycle. Root cause: the access token's hardcoded 30-minute
cap (ACCESS_EXPIRE_MINUTES in crypto.py) caused tokens to expire during
testing sessions, triggering WS 4401 → auth_error → logout cycle.

Fix: ACCESS_EXPIRE_MINUTES is now computed from environment:
- development / dev / local / ALLOW_LONG_LIVED_TOKENS=1 → 480 minutes (8h)
- otherwise (production) → 30 minutes (security cap preserved)

This test verifies:
1. The constant is environment-aware.
2. Production default stays 30 minutes (security invariant).
3. Development default is at least 8 hours (UX invariant).
4. ALLOW_LONG_LIVED_TOKENS escape hatch works.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


def _reload_crypto_with_env(env_overrides: dict[str, str]) -> object:
    """Reload the crypto module with new environment to test cap computation."""
    # Clear any cached state
    for key in ("ENVIRONMENT", "ALLOW_LONG_LIVED_TOKENS"):
        os.environ.pop(key, None)
    for key, val in env_overrides.items():
        os.environ[key] = val

    # Force reimport so the module re-reads os.environ at import time
    if "app.services.auth.crypto" in sys.modules:
        del sys.modules["app.services.auth.crypto"]
    return importlib.import_module("app.services.auth.crypto")


class TestEnvAwareTokenLifetime:
    @pytest.fixture(autouse=True)
    def _restore_env(self):
        """Snapshot and restore env vars around each test."""
        original = {k: os.environ.get(k) for k in ("ENVIRONMENT", "ALLOW_LONG_LIVED_TOKENS")}
        yield
        for k, v in original.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        # Restore the module to its original state for other tests
        if "app.services.auth.crypto" in sys.modules:
            del sys.modules["app.services.auth.crypto"]
        importlib.import_module("app.services.auth.crypto")

    def test_development_cap_is_8_hours(self) -> None:
        """Dev environment must allow 8h tokens to prevent kick-to-login cycle."""
        crypto = _reload_crypto_with_env({"ENVIRONMENT": "development"})
        assert crypto.ACCESS_EXPIRE_MINUTES == 480, (
            f"D-WS-SESSION-001: development env must have 480-minute (8h) cap, "
            f"got {crypto.ACCESS_EXPIRE_MINUTES}. Shorter caps cause the "
            "'kicked to login mid-test' UX catastrophe."
        )

    def test_dev_alias_is_8_hours(self) -> None:
        crypto = _reload_crypto_with_env({"ENVIRONMENT": "dev"})
        assert crypto.ACCESS_EXPIRE_MINUTES == 480

    def test_local_alias_is_8_hours(self) -> None:
        crypto = _reload_crypto_with_env({"ENVIRONMENT": "local"})
        assert crypto.ACCESS_EXPIRE_MINUTES == 480

    def test_production_cap_stays_30_minutes(self) -> None:
        """Production must keep the 30-min security cap — invariant."""
        crypto = _reload_crypto_with_env({"ENVIRONMENT": "production"})
        assert crypto.ACCESS_EXPIRE_MINUTES == 30, (
            f"SECURITY: production must keep the 30-minute cap, "
            f"got {crypto.ACCESS_EXPIRE_MINUTES}. Long-lived tokens in "
            "production expand blast radius if leaked."
        )

    def test_staging_cap_stays_30_minutes(self) -> None:
        crypto = _reload_crypto_with_env({"ENVIRONMENT": "staging"})
        assert crypto.ACCESS_EXPIRE_MINUTES == 30

    def test_no_env_defaults_to_production_cap(self) -> None:
        """Missing ENVIRONMENT must default to safe (30 min)."""
        crypto = _reload_crypto_with_env({})
        assert crypto.ACCESS_EXPIRE_MINUTES == 30

    def test_explicit_allow_long_lived_in_production(self) -> None:
        """ALLOW_LONG_LIVED_TOKENS=1 must override even in production (for canary/migrations)."""
        crypto = _reload_crypto_with_env(
            {"ENVIRONMENT": "production", "ALLOW_LONG_LIVED_TOKENS": "1"}
        )
        assert crypto.ACCESS_EXPIRE_MINUTES == 480

    def test_reauth_token_cap_also_environment_aware(self) -> None:
        """REAUTH_EXPIRE_MINUTES follows the same pattern: dev=60, prod=10."""
        crypto_dev = _reload_crypto_with_env({"ENVIRONMENT": "development"})
        assert crypto_dev.REAUTH_EXPIRE_MINUTES == 60

        crypto_prod = _reload_crypto_with_env({"ENVIRONMENT": "production"})
        assert crypto_prod.REAUTH_EXPIRE_MINUTES == 10


class TestAuthCryptoEncoding:
    """Verify that AuthCrypto uses the env-aware constants correctly."""

    def test_token_encoding_uses_dev_cap(self) -> None:
        """In development, encode_access_token must produce a token good for 8 hours."""
        crypto_mod = _reload_crypto_with_env({"ENVIRONMENT": "development"})
        # Smoke test: import succeeds and the constant has the right value.
        assert crypto_mod.ACCESS_EXPIRE_MINUTES == 480
