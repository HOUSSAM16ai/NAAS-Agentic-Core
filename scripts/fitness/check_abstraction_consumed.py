#!/usr/bin/env python3
"""check_abstraction_consumed — anti-ZOMBIE gate for the hexagonal port layer (D-176).

The integration micro-kernel (`app/core/integration_kernel/contracts.py`) declares
one `ABC` port per capability: WorkflowEngine, RetrievalEngine, PromptEngine,
RankingEngine, ActionEngine. The project's law (§6.6 + the Kagent deletion, D-173):
an abstraction with no live consumer is not "flexibility" — it is dead weight that
must be either wired to a driver or explicitly declared dormant.

This gate enforces, deterministically (stdlib `ast`, no imports), that **every port
is either ACTIVE (a driver is registered for it in `app/services/mcp/integrations.py`)
or explicitly listed in `KNOWN_DORMANT`** — nothing may be silently half-abstract.

`KNOWN_DORMANT` is a frozen allowlist that **may only shrink** (D-105 discipline):
* Adding a NEW port with no driver fails the gate until you either wire a driver
  (promote) or consciously add it here with a comment (documented dormancy).
* Registering a driver for a KNOWN_DORMANT port fails until you REMOVE it from the
  allowlist (promotion must update the honest map).

Usage:
    python scripts/fitness/check_abstraction_consumed.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PORTS_FILE = REPO_ROOT / "app/core/integration_kernel/contracts.py"
REGISTRY_FILE = REPO_ROOT / "app/services/mcp/integrations.py"

# Frozen dormant allowlist — MAY ONLY SHRINK. Each entry is a port with no live
# driver, consciously kept as a documented seam rather than deleted.
#   * ActionEngine — the Kagent action driver was deleted (D-173 Stage 5, ZOMBIE,
#     security-blocked). The port is retained as the documented re-entry seam for a
#     future action capability; no driver is registered, so `act()` is unreachable.
KNOWN_DORMANT: frozenset[str] = frozenset({"ActionEngine"})


def _port_classes() -> set[str]:
    """ABC port classes declared in the integration-kernel contracts."""
    tree = ast.parse(PORTS_FILE.read_text(encoding="utf-8"))
    ports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and any(
            isinstance(base, ast.Name) and base.id == "ABC" for base in node.bases
        ):
            ports.add(node.name)
    return ports


def _registered_categories() -> set[str]:
    """Driver categories registered via ``kernel.register_driver("<category>", ...)``."""
    tree = ast.parse(REGISTRY_FILE.read_text(encoding="utf-8"))
    categories: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "register_driver"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            categories.add(node.args[0].value)
    return categories


def _category_of(port: str) -> str:
    """Map a port class to its kernel category: ``WorkflowEngine`` → ``workflow``."""
    return port.removesuffix("Engine").lower()


def main() -> int:
    ports = _port_classes()
    registered = _registered_categories()
    failures: list[str] = []

    if not ports:
        print(f"❌ no ABC ports found in {PORTS_FILE.relative_to(REPO_ROOT)}")
        return 1

    # Allowlist hygiene: every KNOWN_DORMANT entry must still be a real port.
    for dormant in sorted(KNOWN_DORMANT):
        if dormant not in ports:
            failures.append(
                f"KNOWN_DORMANT '{dormant}' is no longer a declared port — "
                "remove it (the allowlist may only shrink)."
            )

    for port in sorted(ports):
        is_registered = _category_of(port) in registered
        is_dormant = port in KNOWN_DORMANT
        if is_registered and is_dormant:
            failures.append(
                f"{port} has a registered driver but is still in KNOWN_DORMANT — "
                "it was promoted; remove it from the allowlist and update the honest map."
            )
        elif not is_registered and not is_dormant:
            failures.append(
                f"{port} has NO driver in {REGISTRY_FILE.relative_to(REPO_ROOT)} and is "
                "not in KNOWN_DORMANT — wire a driver (promote) or, if truly dead, "
                "delete the port; only add to KNOWN_DORMANT with an explicit rationale."
            )

    if failures:
        print("❌ Abstraction-consumed gate failed (D-176):")
        for f in failures:
            print(f"   • {f}")
        return 1

    active = sorted(p for p in ports if p not in KNOWN_DORMANT)
    print(
        f"✅ abstraction-consumed: {len(active)} ports ACTIVE (driver-backed) "
        f"{active}; {sorted(KNOWN_DORMANT)} documented dormant. No vestigial abstraction."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
