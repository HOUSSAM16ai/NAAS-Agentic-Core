"""D-176: the hexagonal port layer carries no vestigial (unconsumed) abstraction.

Mirrors `scripts/fitness/check_abstraction_consumed.py` as a pytest so the
anti-ZOMBIE-for-abstraction invariant is enforced in the normal test run too.
Pure stdlib — no app imports.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_PATH = _REPO_ROOT / "scripts" / "fitness" / "check_abstraction_consumed.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("check_abstraction_consumed", _GATE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_passes_on_real_repository():
    gate = _load_gate()
    assert gate.main() == 0


def test_every_port_is_active_or_allowlisted():
    gate = _load_gate()
    ports = gate._port_classes()
    registered = gate._registered_categories()
    assert ports, "no ABC ports discovered — parser or contracts moved"
    for port in ports:
        is_active = gate._category_of(port) in registered
        is_dormant = port in gate.KNOWN_DORMANT
        assert is_active != is_dormant, (
            f"{port} must be exactly one of ACTIVE (driver-backed) or KNOWN_DORMANT"
        )


def test_known_dormant_entries_are_real_ports():
    gate = _load_gate()
    ports = gate._port_classes()
    assert ports >= gate.KNOWN_DORMANT, "KNOWN_DORMANT has a stale entry (allowlist only shrinks)"


def test_the_four_capability_ports_are_active():
    # Regression anchor: workflow/retrieval/prompt/ranking must stay driver-backed.
    gate = _load_gate()
    registered = gate._registered_categories()
    for category in ("workflow", "retrieval", "prompt", "ranking"):
        assert category in registered, f"{category} driver must be registered (D-176)"
