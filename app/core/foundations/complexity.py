"""Complexity — growth-rate ordering and the classic complexity classes.

The theory-of-computation layer that reasons about *how hard* a solvable problem
is. Provides a canonical ordering of asymptotic growth-rate labels (so two big-O
classes can be compared and dominance decided) and a small, data-first catalogue
of the standard complexity classes (P, NP, NP-complete, PSPACE, EXPTIME) with the
open ``P vs NP`` question named honestly rather than resolved.

Complements the empirical ``classify_growth`` in ``algorithms.py``: that fits
measured samples, this reasons symbolically about the labels themselves. Every
primitive raises :class:`FoundationsError` on an unknown label.
"""

from __future__ import annotations

from typing import Any

from app.core.foundations.errors import FoundationsError

#: Asymptotic growth-rate labels, slowest-growing first.
GROWTH_ORDER: tuple[str, ...] = (
    "O(1)",
    "O(log n)",
    "O(sqrt n)",
    "O(n)",
    "O(n log n)",
    "O(n^2)",
    "O(n^3)",
    "O(2^n)",
    "O(n!)",
)

#: Data-first catalogue of the standard complexity classes.
COMPLEXITY_CLASSES: dict[str, dict[str, Any]] = {
    "P": {
        "name": "Polynomial time",
        "description": "Decidable by a deterministic TM in polynomial time.",
        "tractable": True,
    },
    "NP": {
        "name": "Nondeterministic polynomial time",
        "description": "Solutions verifiable in polynomial time; P ⊆ NP.",
        "tractable": None,  # open — depends on P vs NP
    },
    "NP-complete": {
        "name": "NP-complete",
        "description": "Hardest problems in NP; every NP problem reduces to them.",
        "tractable": None,
    },
    "PSPACE": {
        "name": "Polynomial space",
        "description": "Decidable using polynomial memory; NP ⊆ PSPACE.",
        "tractable": None,
    },
    "EXPTIME": {
        "name": "Exponential time",
        "description": "Decidable in exponential time; strictly contains P.",
        "tractable": False,
    },
}

#: Canonical NP-complete problems (Karp / Cook–Levin lineage).
NP_COMPLETE_EXAMPLES: tuple[str, ...] = (
    "SAT",
    "3-SAT",
    "Traveling Salesman (decision)",
    "Vertex Cover",
    "Subset Sum",
    "Graph Coloring",
    "Hamiltonian Cycle",
    "Knapsack (decision)",
)

#: The central open question of complexity theory.
P_VS_NP: dict[str, Any] = {
    "question": "Is P = NP?",
    "status": "open",
    "note": "Unresolved since 1971 (Cook–Levin). Widely conjectured P ≠ NP.",
}


def _rank(label: str) -> int:
    if label not in GROWTH_ORDER:
        raise FoundationsError(
            f"complexity: unknown growth label {label!r} — expected one of {GROWTH_ORDER}"
        )
    return GROWTH_ORDER.index(label)


def compare_growth(a: str, b: str) -> int:
    """Return -1/0/1 as ``a`` grows slower/equal/faster than ``b`` asymptotically."""
    ra, rb = _rank(a), _rank(b)
    return (ra > rb) - (ra < rb)


def dominates(a: str, b: str) -> bool:
    """True when ``a`` grows strictly faster than ``b`` (``a`` dominates ``b``)."""
    return compare_growth(a, b) > 0


def is_polynomial(label: str) -> bool:
    """True when the growth label is polynomial (``O(1)`` … ``O(n^3)``) — tractable."""
    _rank(label)  # validates the label
    return label in {"O(1)", "O(log n)", "O(sqrt n)", "O(n)", "O(n log n)", "O(n^2)", "O(n^3)"}


def class_info(name: str) -> dict[str, Any]:
    """Return the catalogue entry for a complexity class; raise if unknown."""
    if name not in COMPLEXITY_CLASSES:
        raise FoundationsError(
            f"complexity: unknown class {name!r} — expected one of {tuple(COMPLEXITY_CLASSES)}"
        )
    return dict(COMPLEXITY_CLASSES[name])
