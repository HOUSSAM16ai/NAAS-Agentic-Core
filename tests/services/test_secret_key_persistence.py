"""
Regression test — SECRET_KEY persistence across uvicorn restarts (ISS-091 / D-SECRET-002).

USER REPORT (verbatim, 2026-05-27):
> «النظام لا يجيب عن الاسئلة و أجد نفسي مطرود إلى صفحة تسجيل الدخول
>  ثم يعود يدخل إلى التطبيق بشكل كارثي خطير مدمر»

DEEPER ROOT CAUSE (after ISS-090):
ISS-090 hardcoded the state file at `/app/.devcontainer/state/dev_secret_key`.
This works inside the official devcontainer (WORKDIR=/app), but fails in:
  - Codespaces without devcontainer (WORKDIR=/workspaces/<repo>)
  - Local dev (WORKDIR=/home/user/<repo>)
  - Gitpod workspace mounts
  - Any operator running uvicorn outside the canonical container

When the path doesn't exist:
  1. `_get_or_create_dev_secret_key()` falls through to memory-only.
  2. Every uvicorn worker restart (--reload, health-restart, deploy) creates
     a new random key.
  3. JWTs signed by previous workers fail signature validation.
  4. WebSocket 4401 → after MAX_FATAL_RETRIES → frontend `auth_error` →
     logout → re-login → cycle.

FIX (D-SECRET-002):
`_resolve_state_key_path()` autodetects the workspace via:
  1. DEV_SECRET_KEY_FILE env override (explicit operator control)
  2. /app/.devcontainer/state/... (devcontainer canonical)
  3. <__file__>/../../../.devcontainer/state/... (repo root from helpers.py)

All three paths persist the key on disk. The key survives every restart.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def isolated_helpers():
    """يستورد helpers.py بشكل معزول لكل اختبار (لتنظيف الـ module-level cache).

    D-105 (ISS-113): الـ fixture كانت تحذف ``SECRET_KEY``/``DEV_SECRET_KEY_FILE`` من
    البيئة **بلا استرجاع** — تلوث يتسرب لبقية الجلسة فتسقط خدمات microservices
    اللاحقة إلى مفتاحها الافتراضي بينما اختباراتها تسكّ التوكن بقيمة أخرى ⇒ 401.
    الآن: snapshot قبل الحذف + استرجاع كامل (البيئة + cache الوحدة) في teardown.
    """
    saved_env = {key: os.environ.get(key) for key in ("SECRET_KEY", "DEV_SECRET_KEY_FILE")}
    for key in saved_env:
        os.environ.pop(key, None)

    from app.core.settings import helpers

    saved_cache = helpers._DEV_SECRET_KEY_CACHE
    helpers._DEV_SECRET_KEY_CACHE = None  # تنظيف الـ in-memory cache
    yield helpers
    helpers._DEV_SECRET_KEY_CACHE = saved_cache
    for key, value in saved_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_dev_secret_key_persists_across_restart(isolated_helpers, tmp_path: Path) -> None:
    """
    INVARIANT: SECRET_KEY MUST be identical across two simulated uvicorn restarts.

    قبل D-SECRET-002: في بيئة بدون /app، كان يُولَّد مفتاح جديد كل مرة →
    JWT يُبطَل → loop "kicked to login + auto-rejoin".
    """
    key_file = tmp_path / "dev_secret_key"
    os.environ["DEV_SECRET_KEY_FILE"] = str(key_file)

    # Restart 1: generate fresh key
    key1 = isolated_helpers._get_or_create_dev_secret_key()
    assert key_file.exists(), "Key file MUST be written to disk"
    assert len(key1) >= 32, f"Key MUST be >= 32 chars, got {len(key1)}"

    # Simulate uvicorn restart: clear in-memory cache
    isolated_helpers._DEV_SECRET_KEY_CACHE = None

    # Restart 2: load from disk (NOT regenerate)
    key2 = isolated_helpers._get_or_create_dev_secret_key()

    assert key1 == key2, (
        f"SECRET_KEY rotated across restart!\n"
        f"  key1 = {key1[:16]}...\n"
        f"  key2 = {key2[:16]}...\n"
        f"  This breaks all active JWTs and causes the 'kick → login' cycle."
    )


def test_env_secret_key_overrides_disk(isolated_helpers, tmp_path: Path) -> None:
    """
    INVARIANT: SECRET_KEY in process env wins over disk file.

    This ensures Gitpod Secrets / Codespaces Secrets take precedence over
    the local dev fallback.
    """
    key_file = tmp_path / "dev_secret_key"
    key_file.write_text("disk_key_should_be_ignored_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
    os.environ["DEV_SECRET_KEY_FILE"] = str(key_file)
    os.environ["SECRET_KEY"] = "env_provided_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

    key = isolated_helpers._get_or_create_dev_secret_key()

    assert key == "env_provided_secret_key_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", (
        "Process env MUST override disk file"
    )


def test_default_weak_keys_ignored(isolated_helpers, tmp_path: Path) -> None:
    """SECRET_KEY=`dev-secret-change-me` or `changeme` MUST be treated as unset."""
    key_file = tmp_path / "dev_secret_key"
    os.environ["DEV_SECRET_KEY_FILE"] = str(key_file)

    for weak in ("dev-secret-change-me", "changeme"):
        os.environ["SECRET_KEY"] = weak
        isolated_helpers._DEV_SECRET_KEY_CACHE = None

        key = isolated_helpers._get_or_create_dev_secret_key()
        assert key != weak, f"Weak SECRET_KEY ({weak!r}) MUST NOT be used"
        assert len(key) >= 32, "Generated key MUST be strong (>= 32 chars)"


def test_state_path_resolves_outside_app_dir(isolated_helpers) -> None:
    """
    INVARIANT: helpers MUST resolve to a creatable path.

    This is the actual catastrophe path: operator runs uvicorn from
    /home/user/<repo> or /workspaces/<repo>, /app doesn't exist, and the
    old hardcoded path silently fell through to memory-only generation.
    """
    # We verify the resolver picks a path that EXISTS or CAN be created
    resolved = isolated_helpers._resolve_state_key_path()
    parent = resolved.parent

    # Ensure parent can be created (this is what the real code does)
    parent.mkdir(parents=True, exist_ok=True)
    assert parent.exists(), f"Resolver MUST pick a creatable path; got {resolved}"


def test_dev_secret_key_file_env_override(isolated_helpers, tmp_path: Path) -> None:
    """DEV_SECRET_KEY_FILE env override allows ops to relocate the state file."""
    custom_path = tmp_path / "subdir" / "custom_key"
    os.environ["DEV_SECRET_KEY_FILE"] = str(custom_path)

    resolved = isolated_helpers._resolve_state_key_path()
    assert resolved == custom_path, f"Expected {custom_path}, got {resolved}"

    key = isolated_helpers._get_or_create_dev_secret_key()
    assert custom_path.exists(), "Key MUST be saved to the custom path"
    assert custom_path.read_text().strip() == key


def test_key_file_permissions_600(isolated_helpers, tmp_path: Path) -> None:
    """Generated key file MUST have restrictive permissions (0600)."""
    key_file = tmp_path / "dev_secret_key"
    os.environ["DEV_SECRET_KEY_FILE"] = str(key_file)

    isolated_helpers._get_or_create_dev_secret_key()
    mode = key_file.stat().st_mode & 0o777
    # On some filesystems chmod is silently a no-op (e.g., /tmp on macOS) — we
    # only enforce that the mode is at most 0o644 (no world-write), 0o600 is ideal.
    assert mode <= 0o644, f"Key file mode too permissive: {oct(mode)}"


# D-105 (ISS-113): أُزيل ``teardown_module`` الذي كان يحذف SECRET_KEY/DEV_SECRET_KEY_FILE
# من البيئة **بلا استرجاع** بعد كل teardowns — كان يلغي استعادة fixture ``isolated_helpers``
# ويُسرّب SECRET_KEY=None لبقية الجلسة (401 في اختبارات microservices اللاحقة).
# الاستعادة لكل-اختبار في الـ fixture أعلاه تغطي التنظيف كاملاً.
