"""Combinatorics — exact counting primitives.

All results are exact Python integers (arbitrary precision). Domain violations
raise ``FoundationsError`` rather than returning a misleading 0 — the same
pedagogical rule the probability engine follows (never emit ``C(2,3)=0`` as if it
were a real count; the impossibility is the teachable fact).
"""

from __future__ import annotations

import math

from microservices.foundations_service.src.foundations.errors import (
    FoundationsError,
    require_non_negative_int,
)


def factorial(n: int) -> int:
    """n! — the number of orderings of ``n`` distinct items."""
    require_non_negative_int(n, "n")
    return math.factorial(n)


def permutations(n: int, k: int) -> int:
    """nPr — ordered selections of ``k`` from ``n`` distinct items (order matters)."""
    require_non_negative_int(n, "n")
    require_non_negative_int(k, "k")
    if k > n:
        raise FoundationsError(f"permutations: k ({k}) > n ({n}) — no such arrangement exists")
    return math.perm(n, k)


def combinations(n: int, k: int) -> int:
    """nCr — unordered selections of ``k`` from ``n`` distinct items (order ignored)."""
    require_non_negative_int(n, "n")
    require_non_negative_int(k, "k")
    if k > n:
        raise FoundationsError(f"combinations: k ({k}) > n ({n}) — no such subset exists")
    return math.comb(n, k)


def multinomial(*group_sizes: int) -> int:
    """Multinomial coefficient — orderings of ``sum(group_sizes)`` items with repeats.

    ``multinomial(2, 1)`` = arrangements of AAB = 3. Equal to
    ``(sum k_i)! / prod(k_i!)``.
    """
    if not group_sizes:
        raise FoundationsError("multinomial: at least one group size is required")
    total = 0
    denominator = 1
    for i, size in enumerate(group_sizes):
        require_non_negative_int(size, f"group_sizes[{i}]")
        total += size
        denominator *= math.factorial(size)
    return math.factorial(total) // denominator


def catalan(n: int) -> int:
    """The n-th Catalan number — balanced-parenthesis / binary-tree counts."""
    require_non_negative_int(n, "n")
    return math.comb(2 * n, n) // (n + 1)


def stirling_second(n: int, k: int) -> int:
    """Stirling number of the second kind — partitions of ``n`` items into ``k`` non-empty subsets."""
    require_non_negative_int(n, "n")
    require_non_negative_int(k, "k")
    if k == 0:
        return 1 if n == 0 else 0
    if k > n:
        return 0
    total = 0
    for j in range(k + 1):
        total += (-1) ** j * math.comb(k, j) * (k - j) ** n
    return total // math.factorial(k)
