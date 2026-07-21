#!/usr/bin/env python3
"""check_model_chain_parity — cross-brain model-chain parity gate (D-013 → machine-enforced).

The two brains each declare the active OpenRouter model + fallback chain:

    * monolith:     app/core/ai_config.py                              (ActiveModels)
    * orchestrator: microservices/orchestrator_service/src/core/ai_config.py

Historically D-013 kept them in sync by a prose "edit both copies" rule, and no
check verified the two chains were actually **equal** — a change to one brain's
fallback order could silently diverge from the other. This gate closes that
split-brain hole: it statically resolves each brain's ordered chain
``[PRIMARY, GATEWAY_FALLBACK_1..5]`` **from source via `ast`** (no imports, no app
deps) and asserts both equal the canonical chain declared in
``shared/ai_models/model_chain.py``.

The safety-critical per-file literal pins (``check_legacy_invariants.py`` +
``test_iss079_catastrophic_fixes.py``) are untouched and remain the defense-in-depth
guard for each file individually; this gate adds the missing cross-brain equality.

Usage:
    python scripts/fitness/check_model_chain_parity.py            # verify parity
    python scripts/fitness/check_model_chain_parity.py --check    # same (CI alias)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from shared.ai_models.model_chain import MODEL_CHAIN

BRAINS: tuple[tuple[str, str], ...] = (
    ("monolith", "app/core/ai_config.py"),
    ("orchestrator", "microservices/orchestrator_service/src/core/ai_config.py"),
)

_CHAIN_ATTRS: tuple[str, ...] = (
    "PRIMARY",
    "GATEWAY_FALLBACK_1",
    "GATEWAY_FALLBACK_2",
    "GATEWAY_FALLBACK_3",
    "GATEWAY_FALLBACK_4",
    "GATEWAY_FALLBACK_5",
)


def _string_constants(class_node: ast.ClassDef) -> dict[str, str]:
    """Map ``NAME = "literal"`` assignments in a class body to their string values."""
    out: dict[str, str] = {}
    for stmt in class_node.body:
        if (
            isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    out[tgt.id] = stmt.value.value
    return out


def _resolve_value(node: ast.expr, available: dict[str, str]) -> str | None:
    """Statically resolve a chain RHS to its string value (no execution).

    Handles: a string literal, ``AvailableModels.NAME`` (via the `available` map),
    and ``_resolve_primary_model(<arg>)`` where ``<arg>`` is one of the former.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        # e.g. AvailableModels.GPT_OSS_20B_FREE
        return available.get(node.attr)
    if isinstance(node, ast.Call) and node.args:
        # e.g. _resolve_primary_model("...") / _resolve_primary_model(AvailableModels.X)
        return _resolve_value(node.args[0], available)
    return None


def resolve_chain_from_source(rel_path: str) -> list[str]:
    """Return the ordered ``[PRIMARY, FALLBACK_1..5]`` chain declared in a brain file."""
    source = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    classes = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    available = (
        _string_constants(classes["AvailableModels"]) if "AvailableModels" in classes else {}
    )
    active = classes.get("ActiveModels")
    if active is None:
        raise ValueError(f"{rel_path}: no `ActiveModels` class found")

    assigned: dict[str, ast.expr] = {}
    for stmt in active.body:
        if isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if isinstance(tgt, ast.Name):
                    assigned[tgt.id] = stmt.value

    chain: list[str] = []
    for attr in _CHAIN_ATTRS:
        if attr not in assigned:
            raise ValueError(f"{rel_path}: ActiveModels is missing `{attr}`")
        value = _resolve_value(assigned[attr], available)
        if value is None:
            raise ValueError(f"{rel_path}: could not statically resolve `{attr}`")
        chain.append(value)
    return chain


def main(argv: list[str] | None = None) -> int:
    # `argv=None` parses sys.argv when run as a script; callers (tests) pass an
    # explicit list (e.g. []) so pytest's own argv never leaks into argparse.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="CI alias (default behavior).")
    parser.parse_args(argv)

    canonical = list(MODEL_CHAIN)
    print("=== Model-Chain Parity Gate (D-013 → machine-enforced) ===")
    print(f"canonical (shared/ai_models/model_chain.py): {canonical}")

    ok = True
    for label, rel_path in BRAINS:
        try:
            chain = resolve_chain_from_source(rel_path)
        except Exception as exc:  # surface a clear gate failure
            print(f"❌ {label} ({rel_path}): {type(exc).__name__}: {exc}")
            ok = False
            continue
        if chain != canonical:
            print(f"❌ {label} ({rel_path}) drifts from canonical:\n     {chain}")
            ok = False
        else:
            print(f"✅ {label} ({rel_path}) matches canonical chain")

    if not ok:
        print(
            "\nModel chains diverged. Update shared/ai_models/model_chain.py first, then "
            "mirror the gate-pinned literals into both ai_config.py files (D-013)."
        )
        return 1
    print("✅ both brains agree with the canonical model chain (single source of truth)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
