"""Information theory — Shannon entropy and its relatives (base-2 bits by default).

All measures take probability distributions as sequences (or a joint matrix for
mutual information) and validate that masses are in [0, 1] and sum to 1. The base
is configurable; the default (2) yields bits.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.core.foundations.errors import FoundationsError


def _validate(dist: Sequence[float], name: str) -> None:
    if not dist:
        raise FoundationsError(f"{name}: distribution must be non-empty")
    for p in dist:
        if not 0 <= p <= 1:
            raise FoundationsError(f"{name}: probability {p} is outside [0, 1]")
    total = math.fsum(dist)
    if not math.isclose(total, 1.0, abs_tol=1e-9):
        raise FoundationsError(f"{name}: probabilities sum to {total}, expected 1")


def entropy(dist: Sequence[float], base: float = 2.0) -> float:
    """Shannon entropy H(X) = −Σ p·log(p). Zero-probability terms contribute 0."""
    _validate(dist, "entropy")
    return -math.fsum(p * math.log(p, base) for p in dist if p > 0)


def cross_entropy(p: Sequence[float], q: Sequence[float], base: float = 2.0) -> float:
    """Cross-entropy H(p, q) = −Σ p·log(q). Requires ``q[i] > 0`` wherever ``p[i] > 0``."""
    _validate(p, "cross_entropy(p)")
    _validate(q, "cross_entropy(q)")
    if len(p) != len(q):
        raise FoundationsError("cross_entropy: p and q must have equal length")
    total = 0.0
    for pi, qi in zip(p, q, strict=True):
        if pi > 0:
            if qi <= 0:
                raise FoundationsError("cross_entropy: q has 0 mass where p is positive (diverges)")
            total += pi * math.log(qi, base)
    return -total


def kl_divergence(p: Sequence[float], q: Sequence[float], base: float = 2.0) -> float:
    """Kullback–Leibler divergence D(p‖q) = Σ p·log(p/q) ≥ 0 (0 iff p == q)."""
    return cross_entropy(p, q, base) - entropy(p, base)


def joint_entropy(joint: Sequence[Sequence[float]], base: float = 2.0) -> float:
    """H(X, Y) from a joint distribution matrix whose entries sum to 1."""
    flat = [cell for row in joint for cell in row]
    _validate(flat, "joint_entropy")
    return entropy(flat, base)


def mutual_information(joint: Sequence[Sequence[float]], base: float = 2.0) -> float:
    """I(X; Y) = H(X) + H(Y) − H(X, Y) from a joint distribution matrix."""
    flat = [cell for row in joint for cell in row]
    _validate(flat, "mutual_information")
    px = [math.fsum(row) for row in joint]
    py = [math.fsum(col) for col in zip(*joint, strict=True)]
    return entropy(px, base) + entropy(py, base) - joint_entropy(joint, base)
