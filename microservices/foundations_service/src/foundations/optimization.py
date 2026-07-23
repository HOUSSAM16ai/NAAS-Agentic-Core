"""Optimization — 1-D minimization, root bracketing, and small linear programs.

Dependency-free teaching-grade optimizers: gradient descent on a differentiable
1-D objective, golden-section search for a unimodal minimum on an interval,
bisection root-finding on a sign-changing bracket, and a two-variable linear
program solved by feasible-vertex enumeration (the geometry a first LP course
teaches — the optimum sits at a corner of the feasible polygon).

Every primitive raises :class:`FoundationsError` on a domain violation
(non-decreasing bracket, no sign change, infeasible/unbounded program).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from microservices.foundations_service.src.foundations.errors import FoundationsError

RealFunction = Callable[[float], float]

_GOLDEN_RATIO = (5**0.5 - 1) / 2  # 1/φ ≈ 0.618


def gradient_descent(
    f: RealFunction,
    x0: float,
    learning_rate: float = 0.01,
    max_iter: int = 10_000,
    tol: float = 1e-9,
    h: float = 1e-6,
) -> float:
    """Minimize a differentiable 1-D ``f`` from ``x0`` via numeric-gradient descent."""
    if learning_rate <= 0:
        raise FoundationsError(f"gradient_descent: learning_rate must be > 0, got {learning_rate}")
    if h <= 0:
        raise FoundationsError(f"gradient_descent: step h must be > 0, got {h}")
    x = x0
    for _ in range(max_iter):
        grad = (f(x + h) - f(x - h)) / (2 * h)
        step = learning_rate * grad
        x -= step
        if abs(step) < tol:
            break
    return x


def golden_section_search(
    f: RealFunction, a: float, b: float, tol: float = 1e-8, max_iter: int = 1000
) -> float:
    """The minimizer of a unimodal ``f`` on ``[a, b]`` (golden-section search)."""
    if a >= b:
        raise FoundationsError(f"golden_section_search: require a < b, got a={a}, b={b}")
    if tol <= 0:
        raise FoundationsError(f"golden_section_search: tol must be > 0, got {tol}")
    lo, hi = a, b
    c = hi - _GOLDEN_RATIO * (hi - lo)
    d = lo + _GOLDEN_RATIO * (hi - lo)
    fc, fd = f(c), f(d)
    for _ in range(max_iter):
        if hi - lo < tol:
            break
        if fc < fd:
            hi, d, fd = d, c, fc
            c = hi - _GOLDEN_RATIO * (hi - lo)
            fc = f(c)
        else:
            lo, c, fc = c, d, fd
            d = lo + _GOLDEN_RATIO * (hi - lo)
            fd = f(d)
    return (lo + hi) / 2


def bisection_root(
    f: RealFunction, a: float, b: float, tol: float = 1e-12, max_iter: int = 200
) -> float:
    """A root of ``f`` on ``[a, b]`` — requires a sign change ``f(a)·f(b) ≤ 0``."""
    if a >= b:
        raise FoundationsError(f"bisection_root: require a < b, got a={a}, b={b}")
    fa, fb = f(a), f(b)
    if fa == 0:
        return a
    if fb == 0:
        return b
    if fa * fb > 0:
        raise FoundationsError("bisection_root: f(a) and f(b) must bracket a sign change")
    lo, hi = a, b
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < tol or (hi - lo) / 2 < tol:
            return mid
        if fa * fm < 0:
            hi = mid
        else:
            lo, fa = mid, fm
    return (lo + hi) / 2


def linear_program_2var(
    objective: tuple[float, float],
    constraints: Sequence[tuple[float, float, float]],
    *,
    maximize: bool = True,
    non_negative: bool = True,
) -> dict[str, float]:
    """Optimize ``c₁x + c₂y`` over ``a·x + b·y ≤ c`` constraints (vertex enumeration).

    ``constraints`` are ``(a, b, c)`` triples meaning ``a·x + b·y ≤ c``. With
    ``non_negative`` the axes ``x ≥ 0, y ≥ 0`` are added. Returns the optimal
    ``{x, y, value}``; raises when the feasible region is empty.
    """
    c1, c2 = objective
    lines = list(constraints)
    if non_negative:
        lines = [*lines, (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)]
    if len(lines) < 2:
        raise FoundationsError("linear_program_2var: need at least 2 constraints to bound vertices")

    def _feasible(x: float, y: float) -> bool:
        return all(a * x + b * y <= c + 1e-9 for a, b, c in lines)

    best: dict[str, float] | None = None
    n = len(lines)
    for i in range(n):
        for j in range(i + 1, n):
            a1, b1, c1c = lines[i]
            a2, b2, c2c = lines[j]
            det = a1 * b2 - a2 * b1
            if abs(det) < 1e-12:
                continue  # parallel — no unique intersection
            x = (c1c * b2 - c2c * b1) / det
            y = (a1 * c2c - a2 * c1c) / det
            if not _feasible(x, y):
                continue
            value = c1 * x + c2 * y
            if (
                best is None
                or (maximize and value > best["value"])
                or (not maximize and value < best["value"])
            ):
                best = {"x": x, "y": y, "value": value}
    if best is None:
        raise FoundationsError(
            "linear_program_2var: no feasible vertex — region empty or unbounded"
        )
    return best
