#!/usr/bin/env python3
"""
CI gate — verify SECRET_KEY consistency across all service-launch blocks in
supervisor.sh.

D-WS-SECRET-KEY-001 (2026-05-26): The catastrophic 4401 cycle that haunted
the user for days was caused by ONE line in supervisor.sh:

    # user-service block (BEFORE):
    SECRET_KEY="${SECRET_KEY:-cogniforge-user-service-dev-key}"  ❌ unique default

    # monolith / orchestrator (always):
    SECRET_KEY="${SECRET_KEY:-dev-secret-change-me}"             ✓ shared default

When Codespaces users don't set SECRET_KEY as a secret, services diverged
silently. user-service signed JWTs with one key; monolith verified with
another. Every WS handshake → 4401 → kick → cycle.

This gate prevents that drift from ever returning. It greps supervisor.sh
for SECRET_KEY assignments and asserts:
  1. All non-trivial defaults are the same literal.
  2. The canonical default is `dev-secret-change-me`.

Exit codes:
  0 — all good
  1 — drift detected
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SUPERVISOR = ROOT / ".devcontainer" / "supervisor.sh"
CANONICAL_DEFAULT = "dev-secret-change-me"


def main() -> int:
    if not SUPERVISOR.is_file():
        print(f"❌ supervisor.sh not found at {SUPERVISOR}")
        return 1

    text = SUPERVISOR.read_text()
    # Skip shell comment lines so we only inspect actual code.
    code_lines: list[tuple[int, str]] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        if raw.lstrip().startswith("#"):
            continue
        code_lines.append((i, raw))

    # Pattern A: direct inline default — SECRET_KEY="${SECRET_KEY:-<default>}"
    inline_pattern = re.compile(r'SECRET_KEY="\$\{SECRET_KEY:-([^}]+)\}"')
    # Pattern B: shared variable — local shared_<name>_secret="${SECRET_KEY:-<default>}"
    # This catches ALL Skills Pipeline services (orchestrator, user, planning,
    # research, reasoning) that funnel their SECRET_KEY through a local
    # variable for defensive double-export.
    shared_pattern = re.compile(r'(?:local\s+)?shared_[a-z_]*secret="\$\{SECRET_KEY:-([^}]+)\}"')
    defaults_found: list[tuple[int, str]] = []
    for line_no, line in code_lines:
        for m in inline_pattern.finditer(line):
            defaults_found.append((line_no, m.group(1)))
        for m in shared_pattern.finditer(line):
            defaults_found.append((line_no, m.group(1)))

    print("=" * 70)
    print("D-WS-SECRET-KEY-001 — SECRET_KEY consistency gate")
    print("=" * 70)
    print()

    if not defaults_found:
        print("⚠️  No SECRET_KEY default assignments found in supervisor.sh.")
        print("    Either supervisor.sh changed format, or all services rely")
        print("    purely on injected env. Cannot verify consistency statically.")
        return 0

    print(f"Found {len(defaults_found)} SECRET_KEY default assignment(s):")
    for line_no, default in defaults_found:
        marker = "✓" if default == CANONICAL_DEFAULT else "✗"
        print(f"  {marker} line {line_no}: default = `{default}`")
    print()

    unique_defaults = {d for _, d in defaults_found}
    if len(unique_defaults) > 1:
        print(f"❌ DRIFT DETECTED: {len(unique_defaults)} distinct defaults:")
        for d in sorted(unique_defaults):
            print(f"     - `{d}`")
        print()
        print("All services sharing JWTs MUST use the same default. The canonical")
        print(f"default is `{CANONICAL_DEFAULT}`.")
        return 1

    (only,) = unique_defaults
    if only != CANONICAL_DEFAULT:
        print(f"❌ Non-canonical default in use: `{only}`")
        print(f"   Expected: `{CANONICAL_DEFAULT}`")
        return 1

    print(f"✅ All {len(defaults_found)} default(s) agree on `{CANONICAL_DEFAULT}`.")
    print()
    print("D-WS-SECRET-KEY-001 invariants verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
