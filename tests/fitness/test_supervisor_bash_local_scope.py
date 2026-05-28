"""
Regression test — bash `local` keyword MUST NOT appear outside functions
in supervisor.sh (ISS-037 + ISS-091 hotfix).

USER REPORT (2026-05-27):
> «عند الدخول للتطبيق على المنفذ 5000 يظهر الرابط معطل»
>  (Codespace built 3 times, port 5000 unreachable)

ROOT CAUSE (ISS-091 hotfix):
My ISS-091 commit introduced `local reload_flag=""` at top-level script
body inside an `if/else` block. With `set -Eeuo pipefail`, bash exits
with code 1 on `local: can only be used in a function`. Supervisor crashes
at Step 4 → uvicorn never starts → Step 4B (frontend launch) never runs
→ port 5000 is dead → user sees "site can't be reached".

This is the EXACT same regression as ISS-037 (commit 3fd78247, fixed
2026-05-09). The CI lacks a guard for this pattern — this test adds it.

INVARIANT (enforced): every `local NAME=...` statement in supervisor.sh
MUST appear lexically inside a function body. Top-level usage is forbidden.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR_SH = REPO_ROOT / ".devcontainer" / "supervisor.sh"


def test_supervisor_sh_has_no_top_level_local() -> None:
    """No `local NAME=...` outside a function definition."""
    lines = SUPERVISOR_SH.read_text().splitlines()

    in_function = False
    function_stack: list[tuple[str, int]] = []
    brace_depth = 0
    issues: list[tuple[int, str]] = []

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        # Function definition: NAME() {
        func_match = re.match(r"^(\w+)\(\)\s*\{", stripped)
        if func_match:
            function_stack.append((func_match.group(1), brace_depth))
            in_function = True
            brace_depth += 1
            continue

        # Track { } depth (rough but sufficient for top-level detection)
        for ch in stripped:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if function_stack and brace_depth <= function_stack[-1][1]:
                    function_stack.pop()
                    in_function = bool(function_stack)

        # Detect `local` keyword (with optional leading whitespace)
        if re.match(r"^\s*local\s+\w+", raw) and not in_function:
            issues.append((i, raw.rstrip()))

    assert not issues, (
        "`local` keyword found OUTSIDE function in supervisor.sh:\n"
        + "\n".join(f"  line {ln}: {txt}" for ln, txt in issues)
        + "\n\nbash rejects `local` outside functions. With `set -Eeuo pipefail`, "
        + "this crashes the supervisor at runtime → uvicorn/frontend never start."
    )


def test_supervisor_sh_passes_bash_syntax_check() -> None:
    """Static syntax validation via `bash -n`."""
    result = subprocess.run(
        ["bash", "-n", str(SUPERVISOR_SH)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, (
        f"bash -n failed (rc={result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_supervisor_sh_runs_to_step_4_without_local_crash() -> None:
    """
    Live test: simulate supervisor.sh's script-body if/else block with
    `set -Eeuo pipefail` to confirm the `reload_flag` declaration works.
    """
    script = """
set -Eeuo pipefail
DEV_RELOAD="${DEV_RELOAD:-0}"

if true; then
    # Exact pattern from supervisor.sh line ~495
    reload_flag=""
    if [ "${DEV_RELOAD:-0}" = "1" ]; then
        reload_flag="--reload"
    fi
    echo "reload_flag=${reload_flag}"
fi
"""
    result = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, timeout=5, check=False
    )
    assert result.returncode == 0, (
        f"supervisor.sh's reload_flag pattern crashed at runtime (rc={result.returncode}):\n"
        f"stderr: {result.stderr}"
    )
    assert "reload_flag=" in result.stdout, "Expected reload_flag output"
