"""Calculus — numerical derivative, integral, limit, and root finding.

Dependency-free numerical calculus over plain Python callables ``f: float -> float``.
These are teaching-grade approximations (central differences, composite Simpson,
Newton's method) — good to ~1e-6 on smooth functions — not a symbolic CAS. The
platform's *exact* truth comes from the symbolic engines; this module gives the
tutor a verified numeric substrate for reasoning about change and accumulation.

Every primitive raises :class:`FoundationsError` on a domain violation (zero step,
non-positive interval count, non-convergent root) rather than returning NaN.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from app.core.foundations.errors import FoundationsError

RealFunction = Callable[[float], float]


def derivative(f: RealFunction, x: float, h: float = 1e-6) -> float:
    """f'(x) via the symmetric central difference ``(f(x+h) − f(x−h)) / 2h``."""
    if h <= 0:
        raise FoundationsError(f"derivative: step h must be > 0, got {h}")
    return (f(x + h) - f(x - h)) / (2 * h)


def nth_derivative(f: RealFunction, x: float, order: int, h: float = 1e-4) -> float:
    """Approximate the ``order``-th derivative by iterated central differences."""
    if not isinstance(order, int) or isinstance(order, bool) or order < 1:
        raise FoundationsError(f"nth_derivative: order must be a positive int, got {order!r}")
    if h <= 0:
        raise FoundationsError(f"nth_derivative: step h must be > 0, got {h}")
    if order == 1:
        return derivative(f, x, h)
    return derivative(lambda t: nth_derivative(f, t, order - 1, h), x, h)


def definite_integral(f: RealFunction, a: float, b: float, intervals: int = 1000) -> float:
    """∫ₐᵇ f(x) dx via composite Simpson's rule (``intervals`` must be a positive even int)."""
    if not isinstance(intervals, int) or isinstance(intervals, bool) or intervals <= 0:
        raise FoundationsError(
            f"definite_integral: intervals must be a positive int, got {intervals!r}"
        )
    if intervals % 2 != 0:
        intervals += 1  # Simpson needs an even number of subintervals
    if a == b:
        return 0.0
    lo, hi = (a, b) if a < b else (b, a)
    step = (hi - lo) / intervals
    total = f(lo) + f(hi)
    for i in range(1, intervals):
        weight = 4 if i % 2 else 2
        total += weight * f(lo + i * step)
    result = total * step / 3
    return result if a < b else -result


def limit(f: RealFunction, x: float, h: float = 1e-5) -> float:
    """Two-sided limit estimate at ``x``; raises when the one-sided limits disagree.

    A jump discontinuity is a real fact about the function, so a disagreement
    between the left and right approach raises :class:`FoundationsError` rather
    than averaging two different values into a misleading number.
    """
    if h <= 0:
        raise FoundationsError(f"limit: probe h must be > 0, got {h}")
    left = f(x - h)
    right = f(x + h)
    if not math.isclose(left, right, rel_tol=1e-3, abs_tol=1e-6):
        raise FoundationsError(
            f"limit: left ({left}) and right ({right}) approaches disagree at x={x}"
        )
    return (left + right) / 2


def newton_root(f: RealFunction, x0: float, tol: float = 1e-10, max_iter: int = 100) -> float:
    """A root of ``f`` near ``x0`` via Newton's method (numeric derivative)."""
    if tol <= 0:
        raise FoundationsError(f"newton_root: tol must be > 0, got {tol}")
    x = x0
    for _ in range(max_iter):
        fx = f(x)
        if abs(fx) < tol:
            return x
        dfx = derivative(f, x)
        if abs(dfx) < 1e-14:
            raise FoundationsError("newton_root: derivative vanished — Newton step undefined")
        x -= fx / dfx
    raise FoundationsError(f"newton_root: did not converge within {max_iter} iterations")


def taylor_coefficients(f: RealFunction, x: float, order: int) -> list[float]:
    """Taylor coefficients ``fⁿ(x)/n!`` for degrees ``0..order`` about ``x``."""
    if not isinstance(order, int) or isinstance(order, bool) or order < 0:
        raise FoundationsError(
            f"taylor_coefficients: order must be a non-negative int, got {order!r}"
        )
    coeffs = [f(x)]
    for n in range(1, order + 1):
        coeffs.append(nth_derivative(f, x, n) / math.factorial(n))
    return coeffs
