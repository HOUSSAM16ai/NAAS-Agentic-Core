"""Computational logic — propositional truth tables, tautology, satisfiability.

A formula is any Python callable taking a dict ``{var: bool}`` and returning a
bool (built from ``and``/``or``/``not`` or the helpers here). These primitives
enumerate the 2^n assignments, so they are exact for the small formulas a logic
lesson uses. Helpers ``implies`` / ``iff`` express the connectives students meet.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from itertools import product

from app.core.foundations.errors import FoundationsError

Formula = Callable[[dict[str, bool]], bool]


def implies(p: bool, q: bool) -> bool:
    """Material implication ``p → q`` (false only when p is true and q is false)."""
    return (not p) or q


def iff(p: bool, q: bool) -> bool:
    """Biconditional ``p ↔ q`` (true when both sides share a truth value)."""
    return p == q


def xor(p: bool, q: bool) -> bool:
    """Exclusive or ``p ⊕ q``."""
    return p != q


def _assignments(variables: Sequence[str]) -> Iterable[dict[str, bool]]:
    for combo in product((False, True), repeat=len(variables)):
        yield dict(zip(variables, combo, strict=True))


def truth_table(formula: Formula, variables: Sequence[str]) -> list[tuple[dict[str, bool], bool]]:
    """Return ``[(assignment, result), ...]`` over all 2^n assignments."""
    if not variables:
        raise FoundationsError("truth_table: at least one variable is required")
    if len(set(variables)) != len(variables):
        raise FoundationsError(f"truth_table: duplicate variable names in {variables}")
    return [(dict(a), bool(formula(a))) for a in _assignments(variables)]


def is_tautology(formula: Formula, variables: Sequence[str]) -> bool:
    """True iff the formula is true under every assignment."""
    return all(result for _, result in truth_table(formula, variables))


def is_satisfiable(formula: Formula, variables: Sequence[str]) -> bool:
    """True iff some assignment makes the formula true."""
    return any(result for _, result in truth_table(formula, variables))


def is_contradiction(formula: Formula, variables: Sequence[str]) -> bool:
    """True iff no assignment makes the formula true."""
    return not is_satisfiable(formula, variables)


def equivalent(f: Formula, g: Formula, variables: Sequence[str]) -> bool:
    """True iff ``f`` and ``g`` agree on every assignment (logical equivalence)."""
    return all(bool(f(a)) == bool(g(a)) for a in _assignments(variables))


def entails(premises: Sequence[Formula], conclusion: Formula, variables: Sequence[str]) -> bool:
    """True iff every assignment satisfying all premises also satisfies the conclusion."""
    for a in _assignments(variables):
        if all(bool(p(a)) for p in premises) and not bool(conclusion(a)):
            return False
    return True
