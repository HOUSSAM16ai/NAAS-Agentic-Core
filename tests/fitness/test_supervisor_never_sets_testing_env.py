"""
Regression test — supervisor.sh MUST NEVER auto-set ENVIRONMENT=testing
(ISS-094 round 2 / D-095).

USER REPORT (2026-05-28):
> «النظام لا يجيب عن الأسئلة و أجد نفسي مطرود إلى صفحة تسجيل الدخول
>  ثم يعود يدخل إلى التطبيق بشكل كارثي خطير مدمر»
> (No response to questions + kicked to login + auto re-enter)

ROOT CAUSE:
When `.devcontainer/secrets.env` is missing AND Codespaces Secrets are not
configured, supervisor.sh used to fall back to:
    DATABASE_URL=sqlite+aiosqlite:///:memory:
    ENVIRONMENT=testing
    TESTING=1

The ENVIRONMENT=testing setting causes `app/services/auth/crypto.py:36-40`
to compute `ACCESS_EXPIRE_MINUTES=30` at module import time. After 30 minutes
of session activity, every JWT becomes invalid → WS connection returns 4401
→ frontend fires `agent:auth_error` → logout → kick-to-login.

INVARIANT (enforced by this test):
The string `_set_env_key "ENVIRONMENT" "testing"` MUST NOT appear in
supervisor.sh. The only allowed automatic ENVIRONMENT values are
"development" or "production" (manually configured).

TESTING=1 may still be set as an independent flag for code paths that
need it (LLM mocking, fixture isolation, etc.), but it does NOT affect
JWT lifetime.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR_SH = REPO_ROOT / ".devcontainer" / "supervisor.sh"


def _strip_comments(text: str) -> str:
    """Remove bash comment lines (whole-line `# ...`) so we don't false-positive
    on documentation strings inside the script."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        # Remove trailing comments — bash trailing comments start with ` # `
        # (space-hash-space) to avoid stripping `#` inside quoted strings.
        # Conservative: only strip if a # appears outside any quote.
        lines.append(line)
    return "\n".join(lines)


def test_supervisor_never_auto_sets_environment_testing() -> None:
    """The supervisor must NEVER set ENVIRONMENT=testing automatically (D-095)."""
    src = SUPERVISOR_SH.read_text()
    src_no_comments = _strip_comments(src)

    forbidden_patterns = [
        # Standard form
        r'_set_env_key\s+"ENVIRONMENT"\s+"testing"',
        # Without _set_env_key wrapper
        r"^\s*ENVIRONMENT=testing\s*$",
        # Export form
        r"^\s*export\s+ENVIRONMENT=testing\s*$",
    ]

    failures: list[tuple[str, list[int]]] = []
    for pattern in forbidden_patterns:
        matches: list[int] = []
        for i, line in enumerate(src_no_comments.splitlines(), start=1):
            if re.search(pattern, line):
                matches.append(i)
        if matches:
            failures.append((pattern, matches))

    assert not failures, (
        "D-095 VIOLATION: supervisor.sh contains forbidden ENVIRONMENT=testing setter.\n"
        "This causes JWT lifetime to drop to 30 minutes, triggering kick-to-login\n"
        "after 30 minutes of session activity.\n\n"
        "Use ENVIRONMENT=development with TESTING=1 if you need test-mode behavior\n"
        "without breaking session lifetime.\n\n"
        "Matches:\n" + "\n".join(f"  pattern={p!r}\n  lines={lines}" for p, lines in failures)
    )


def test_supervisor_keeps_development_in_sqlite_fallback() -> None:
    """When DB falls back to SQLite, ENVIRONMENT must remain 'development' (D-095).

    Locates the SQLite fallback block (must contain
    'sqlite+aiosqlite:///:memory:') and verifies the adjacent `_set_env_key
    "ENVIRONMENT" "..."` call sets it to "development", not "testing".
    """
    src = SUPERVISOR_SH.read_text()
    lines = src.splitlines()

    # Find the SQLite fallback line
    sqlite_line_idx: int | None = None
    for i, line in enumerate(lines):
        if "sqlite+aiosqlite:///:memory:" in line and "_set_env_key" in line:
            sqlite_line_idx = i
            break

    assert sqlite_line_idx is not None, (
        "Could not find SQLite fallback in supervisor.sh — test logic broken or "
        "code structure changed"
    )

    # Look for ENVIRONMENT setting within 15 lines after sqlite line
    env_set_lines = [
        (i, line)
        for i, line in enumerate(
            lines[sqlite_line_idx : sqlite_line_idx + 15], start=sqlite_line_idx
        )
        if re.search(r'_set_env_key\s+"ENVIRONMENT"', line) and not line.strip().startswith("#")
    ]

    assert env_set_lines, (
        "After SQLite fallback line, no _set_env_key 'ENVIRONMENT' found within "
        "15 lines — supervisor structure unexpected"
    )

    # All ENVIRONMENT settings in this region must be "development"
    for idx, line in env_set_lines:
        # Extract the value
        m = re.search(r'_set_env_key\s+"ENVIRONMENT"\s+"([^"]+)"', line)
        if m:
            value = m.group(1)
            assert value == "development", (
                f"D-095 VIOLATION at line {idx + 1}: ENVIRONMENT must be 'development' "
                f"in SQLite fallback block (found {value!r}).\n"
                f"Line: {line.rstrip()}\n\n"
                f"Setting ENVIRONMENT to anything other than 'development' (e.g. 'testing')\n"
                f"causes JWT lifetime to drop to 30 minutes → kick-to-login catastrophe."
            )
