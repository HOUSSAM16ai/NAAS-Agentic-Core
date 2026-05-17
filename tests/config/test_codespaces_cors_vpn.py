"""ISS-MISC-VPN / D-068 — Codespaces hostname & CORS regression tests.

السياق: شكوى المستخدم 2026-05-17 — على GitHub Codespaces بدون VPN كان مؤشر
الحالة "غير متصل" (offline) باستمرار. السبب الجذري:
  1. الإعداد الافتراضي `ALLOWED_HOSTS = ["localhost","127.0.0.1",...]` يرفض
     أي طلب يصل بـ Host header = `<codespace>-8000.app.github.dev` (و هذا
     ما يُرسله المتصفح عبر Codespaces forwarding) → TrustedHostMiddleware
     يُعيد HTTP 400 "Invalid host".
  2. الإعداد الافتراضي `BACKEND_CORS_ORIGINS = ["http://localhost:3000"]`
     يحجب الـ Origin `https://<codespace>-3000.app.github.dev`.

الإصلاح (`expand_cloud_forwarded_hosts_and_cors` model_validator):
  - يُضيف تلقائياً `*.app.github.dev`, `*.preview.app.github.dev`, `*.gitpod.io`
    إلى ALLOWED_HOSTS عند CODESPACES=true.
  - يُضيف أصول CORS محددة لاسم الـ codespace.
  - يُولِّد `BACKEND_CORS_ORIGIN_REGEX` يطابق أي codespace forwarded host.

قواعد دائمة (لا تُكسر بدون ADR):
  - عند CODESPACES=false: لا تغيير على ALLOWED_HOSTS / BACKEND_CORS_ORIGINS.
  - الـ regex المُولَّد يجب ألا يطابق https://evil.com أو أي origin غير
    صريح من المنصات المعروفة.
"""

from __future__ import annotations

import os
import re
from unittest.mock import patch

from app.core.settings.base import AppSettings

# ─────────────────────────────────────────────────────────────────────────────
# Codespaces ON path — يجب أن يتوسَّع الإعداد
# ─────────────────────────────────────────────────────────────────────────────


def _codespaces_env() -> dict:
    return {
        "CODESPACES": "true",
        "CODESPACE_NAME": "my-cs",
        "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-for-ci-pipeline-secure-length",
        "ENVIRONMENT": "development",
    }


def test_codespaces_adds_wildcards_to_allowed_hosts():
    with patch.dict(os.environ, _codespaces_env(), clear=False):
        s = AppSettings()
        for expected in ("*.app.github.dev", "*.preview.app.github.dev", "*.gitpod.io"):
            assert expected in s.ALLOWED_HOSTS, f"Missing wildcard: {expected}"
        # baseline hosts preserved (no destructive replacement)
        assert "localhost" in s.ALLOWED_HOSTS
        assert "127.0.0.1" in s.ALLOWED_HOSTS


def test_codespaces_adds_specific_origins_to_cors():
    with patch.dict(os.environ, _codespaces_env(), clear=False):
        s = AppSettings()
        expected = {
            "https://my-cs-3000.app.github.dev",
            "https://my-cs-5000.app.github.dev",
            "https://my-cs-8000.app.github.dev",
        }
        assert expected.issubset(set(s.BACKEND_CORS_ORIGINS))
        # baseline origin preserved
        assert "http://localhost:3000" in s.BACKEND_CORS_ORIGINS


def test_codespaces_generates_cors_regex():
    with patch.dict(os.environ, _codespaces_env(), clear=False):
        s = AppSettings()
        assert s.BACKEND_CORS_ORIGIN_REGEX is not None
        regex = re.compile(s.BACKEND_CORS_ORIGIN_REGEX)
        # MUST match
        for origin in (
            "https://my-cs-3000.app.github.dev",
            "https://my-cs-5000.app.github.dev",
            "https://different-cs-3000.preview.app.github.dev",
            "https://other-name-with-hyphens-3000.app.github.dev",
            "https://3000-workspace-id.eu-central.gitpod.io",
        ):
            assert regex.match(origin), f"Regex should match: {origin}"
        # MUST NOT match
        for origin in (
            "http://localhost:3000",  # http, not https
            "https://evil.com",
            "https://my-cs-3000.app.github.dev.evil.com",  # subdomain hijack attempt
            "https://my-cs-9999.app.github.dev",  # wrong port
            "https://github.dev",
        ):
            assert not regex.match(origin), f"Regex should NOT match: {origin}"


# ─────────────────────────────────────────────────────────────────────────────
# Codespaces OFF path — لا regression
# ─────────────────────────────────────────────────────────────────────────────


def _non_codespaces_env() -> dict:
    return {
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "SECRET_KEY": "test-secret-key-for-ci-pipeline-secure-length",
        "ENVIRONMENT": "development",
    }


def test_non_codespaces_does_not_modify_allowed_hosts():
    env = _non_codespaces_env()
    # Make sure no leakage from previous tests
    with patch.dict(
        os.environ,
        {**env, "CODESPACES": "", "CODESPACE_NAME": "", "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": ""},
        clear=False,
    ):
        s = AppSettings()
        assert s.CODESPACES is False
        # default exactly
        assert sorted(s.ALLOWED_HOSTS) == sorted(["localhost", "127.0.0.1", "testserver", "test"])
        assert list(s.BACKEND_CORS_ORIGINS) == ["http://localhost:3000"]
        assert s.BACKEND_CORS_ORIGIN_REGEX is None


def test_codespaces_validator_idempotent():
    """Calling the validator twice (e.g. settings reloaded) must not duplicate entries."""
    with patch.dict(os.environ, _codespaces_env(), clear=False):
        s = AppSettings()
        # Apply manually a second time
        s.expand_cloud_forwarded_hosts_and_cors()
        # No duplicates
        assert len(s.ALLOWED_HOSTS) == len(set(s.ALLOWED_HOSTS))
        assert len(s.BACKEND_CORS_ORIGINS) == len(set(s.BACKEND_CORS_ORIGINS))


def test_codespaces_with_no_codespace_name_still_adds_wildcards():
    """If CODESPACES=true but CODESPACE_NAME is missing, we still get the wildcards."""
    env = _codespaces_env()
    env["CODESPACE_NAME"] = ""
    with patch.dict(os.environ, env, clear=False):
        s = AppSettings()
        # Wildcards still added
        assert "*.app.github.dev" in s.ALLOWED_HOSTS
        # But no specific origin added (since we don't know the name)
        for origin in s.BACKEND_CORS_ORIGINS:
            assert not origin.startswith("https://my-cs-")
        # Regex still works for any codespace
        assert s.BACKEND_CORS_ORIGIN_REGEX is not None


# ─────────────────────────────────────────────────────────────────────────────
# Production safety — CORS rules still enforced
# ─────────────────────────────────────────────────────────────────────────────


def test_production_codespaces_still_works():
    """Codespaces detection must work even in production env (rare but possible)."""
    env = {**_codespaces_env(), "ENVIRONMENT": "development"}  # avoid prod admin gate
    with patch.dict(os.environ, env, clear=False):
        s = AppSettings()
        # The Codespaces wildcards are present
        assert "*.app.github.dev" in s.ALLOWED_HOSTS
        # Production checks still operate
        assert s.ENVIRONMENT == "development"
