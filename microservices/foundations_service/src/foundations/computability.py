"""Computability — decidable predicates, reductions, and documented limits.

The theory-of-computation layer that reasons about *what can be computed at all*.
Provides computable illustrations (Ackermann's non-primitive-recursive growth,
finite-domain decidability, many-one reductions) alongside first-class,
documented **limits of solvability** — the Halting Problem and the Busy-Beaver
function are undecidable/uncomputable, and this module names them as facts rather
than pretending to evaluate them (CLAUDE.md §0: unknown is better than fake
certainty).

Every primitive raises :class:`FoundationsError` on a domain violation.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from microservices.foundations_service.src.foundations.errors import FoundationsError

#: The Halting Problem is undecidable (Turing, 1936): no algorithm decides, for
#: every program+input, whether it halts. Named here as a documented limit.
HALTING_PROBLEM: dict[str, Any] = {
    "name": "Halting Problem",
    "decidable": False,
    "proof": "Turing 1936 — diagonalization; a decider H yields a paradoxical program D.",
}

#: Σ(n), the Busy-Beaver function, is uncomputable and grows faster than any
#: computable function. Only the first few values are known.
BUSY_BEAVER: dict[int, int] = {0: 0, 1: 1, 2: 4, 3: 6, 4: 13}


def ackermann(m: int, n: int) -> int:
    """The Ackermann–Péter function — total but **not** primitive recursive.

    A computable function whose value grows explosively; a canonical witness that
    the total computable functions strictly contain the primitive recursive ones.
    Guarded to small ``m`` because the value blows up past ``m = 3``.
    """
    for name, value in (("m", m), ("n", n)):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise FoundationsError(f"ackermann: {name} must be a non-negative int, got {value!r}")
    if m > 3:
        raise FoundationsError(
            "ackermann: m > 3 is astronomically large — refused (unbounded growth)"
        )

    def _ack(a: int, b: int) -> int:
        while a != 0:
            b = 1 if b == 0 else _ack(a, b - 1)
            a -= 1
        return b + 1

    return _ack(m, n)


def is_decidable_by_table(predicate: Callable[[Any], bool], domain: Iterable[Any]) -> bool:
    """A predicate over a **finite** domain is trivially decidable (enumerate it).

    Returns ``True`` after confirming ``predicate`` terminates on every element —
    the finite-domain guarantee that separates decidable finite questions from
    the undecidable ones over infinite domains.
    """
    items = list(domain)
    if not items:
        raise FoundationsError("is_decidable_by_table: domain must be non-empty")
    for item in items:
        result = predicate(item)
        if not isinstance(result, bool):
            raise FoundationsError("is_decidable_by_table: predicate must return bool")
    return True


def many_one_reduction(
    reduce_fn: Callable[[Any], Any],
    source_domain: Iterable[Any],
    target_decider: Callable[[Any], bool],
    source_membership: Callable[[Any], bool],
) -> bool:
    """Verify ``reduce_fn`` is a valid many-one reduction on a finite sample.

    A reduction ``f`` from problem A to problem B satisfies
    ``x ∈ A ⇔ f(x) ∈ B``. This checks that identity over a finite ``source_domain``
    — the core technique for transferring (un)decidability between problems.
    """
    items = list(source_domain)
    if not items:
        raise FoundationsError("many_one_reduction: source_domain must be non-empty")
    return all(source_membership(x) == target_decider(reduce_fn(x)) for x in items)


def busy_beaver(n: int) -> int:
    """Return the known Busy-Beaver value Σ(n); raise for uncomputed/large ``n``.

    Σ is uncomputable, so only tabulated values are returned — a larger ``n``
    raises rather than fabricating a number.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n < 0:
        raise FoundationsError(f"busy_beaver: n must be a non-negative int, got {n!r}")
    if n not in BUSY_BEAVER:
        raise FoundationsError(
            f"busy_beaver: Σ({n}) is unknown/uncomputable — the function grows "
            "faster than any computable function"
        )
    return BUSY_BEAVER[n]
