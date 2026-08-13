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


def test_supervisor_refuses_to_boot_without_real_database() -> None:
    """D-246 (2026-08-13): NO silent SQLite fallback — boot REFUSES without a
    real DATABASE_URL, and the refusal dies for real (not inside an `if`/`||`).

    The OLD behaviour (write sqlite+aiosqlite:///:memory: and boot normally,
    with /health lying green) was the root cause of ISS-158: "new account,
    no saved messages" — everything lived only in process memory and vanished
    on every restart.

    After D-246 the script must:
    1. never `_set_env_key "DATABASE_URL" "sqlite+aiosqlite:///:memory:"`;
    2. print a loud FATAL message + `return 1` when no real URL is present;
    3. be invoked as a bare statement — `set -Eeuo pipefail` + ERR trap turn
       the `return 1` into a real process exit (measured: EXIT=1). Guarding
       the call with if/|| would silently disarm it.
    """
    src = SUPERVISOR_SH.read_text()
    lines = src.splitlines()

    # 1) No silent fallback URL ever written to .env
    fallback_lines = [
        i
        for i, line in enumerate(lines)
        if "sqlite+aiosqlite:///:memory:" in line
        and "_set_env_key" in line
        and "DATABASE_URL" in line
        and not line.strip().startswith("#")
    ]
    assert not fallback_lines, (
        f"D-246 VIOLATION at line(s) {fallback_lines}: supervisor.sh must never\n"
        f"write sqlite+aiosqlite:///:memory: as the DATABASE_URL — the app\n"
        f"then boots green while every account and message lives only in the\n"
        f"process memory and vanishes on every restart (ISS-158)."
    )

    # 2) Loud FATAL refusal exists when no real DB URL is available
    fatal_idx: int | None = None
    for i, line in enumerate(lines):
        if re.search(r"FATAL: no real DATABASE_URL", line):
            fatal_idx = i
            break
    assert fatal_idx is not None, (
        "Could not find 'FATAL: no real DATABASE_URL' refusal in supervisor.sh —\n"
        "D-246 requires a loud refusal (lifecycle_error + return 1), never a\n"
        "silent boot with /health lying that everything is healthy."
    )

    # 3) The refusal returns 1 within the next 60 lines
    after = lines[fatal_idx : fatal_idx + 60]
    assert any(re.search(r"\breturn 1\b", ln) and not ln.strip().startswith("#") for ln in after), (
        "After the FATAL refusal, no 'return 1' found within 60 lines — the\n"
        "script would fall through to booting instead of refusing."
    )

    # 4) The call site is a bare statement, never guarded by if/||/&/;
    call_site = re.search(r"^_inject_env_secrets\s*$", src, re.M)
    assert call_site is not None, "Call site '_inject_env_secrets' as a bare statement not found"
    cs_line_no = src[: call_site.start()].count("\n") + 1
    prev = lines[cs_line_no - 2].strip() if cs_line_no >= 2 else ""
    nxt = lines[cs_line_no].strip() if cs_line_no < len(lines) else ""
    assert not prev.endswith((";", "&&", "||")), (
        f"Line before the _inject_env_secrets call (line {cs_line_no - 1}: {prev})\n"
        f"ends with a command-chain operator — a `return 1` inside if/||/&&/;\n"
        f"would NOT exit the process (D-246 requires an unguarded bare call)."
    )
    assert not nxt.startswith(("if ", "then", "&&", "||")), (
        f"Line after the _inject_env_secrets call (line {cs_line_no + 1}: {nxt})\n"
        f"guards the invocation — this would silently disarm the fail-hard exit."
    )
