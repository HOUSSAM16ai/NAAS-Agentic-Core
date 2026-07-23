"""Deterministic dispatch over the vendored foundation engines (D-183).

The API-first core of foundations-service: map a ``{domain, operation, args}``
request to the matching verified engine and return a JSON-serialisable result.
No LLM, no ``app`` import, no sibling-service import — pure deterministic compute.

Functions (calculus/optimization) are passed as polynomial coefficient lists
``[c0, c1, c2] → c0 + c1·x + c2·x²`` so the whole surface stays JSON-safe.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from microservices.foundations_service.src.foundations import (
    calculus,
    complexity,
    computability,
    formal_languages,
    graph_theory,
    linear_algebra,
    optimization,
    statistics,
)
from microservices.foundations_service.src.foundations.errors import FoundationsError


class ComputeError(Exception):
    """Raised when an unknown operation is requested (mapped to HTTP 400 upstream)."""


def _poly(coeffs: list[float]) -> Callable[[float], float]:
    if not coeffs:
        raise FoundationsError("polynomial: coeffs must be non-empty")

    def f(x: float) -> float:
        return sum(c * x**i for i, c in enumerate(coeffs))

    return f


_TABLE: dict[tuple[str, str], Callable[[dict[str, Any]], Any]] = {
    ("linear_algebra", "solve"): lambda a: linear_algebra.solve_linear_system(a["matrix"], a["b"]),
    ("linear_algebra", "determinant"): lambda a: linear_algebra.determinant(a["matrix"]),
    ("linear_algebra", "rank"): lambda a: linear_algebra.matrix_rank(a["matrix"]),
    ("linear_algebra", "matmul"): lambda a: linear_algebra.matmul(a["a"], a["b"]),
    ("linear_algebra", "dot"): lambda a: linear_algebra.dot(a["a"], a["b"]),
    ("linear_algebra", "transpose"): lambda a: linear_algebra.transpose(a["matrix"]),
    ("calculus", "derivative"): lambda a: calculus.derivative(_poly(a["coeffs"]), a["x"]),
    ("calculus", "integral"): lambda a: calculus.definite_integral(
        _poly(a["coeffs"]), a["a"], a["b"]
    ),
    ("calculus", "root"): lambda a: calculus.newton_root(_poly(a["coeffs"]), a.get("x0", 1.0)),
    ("statistics", "correlation"): lambda a: statistics.correlation(a["xs"], a["ys"]),
    ("statistics", "regression"): lambda a: statistics.linear_regression(a["xs"], a["ys"]),
    ("statistics", "percentile"): lambda a: statistics.percentile(a["data"], a["p"]),
    ("statistics", "confidence_interval"): lambda a: list(
        statistics.confidence_interval_mean(a["data"], a.get("confidence", 0.95))
    ),
    ("optimization", "minimize"): lambda a: optimization.golden_section_search(
        _poly(a["coeffs"]), a["a"], a["b"]
    ),
    ("optimization", "root"): lambda a: optimization.bisection_root(
        _poly(a["coeffs"]), a["a"], a["b"]
    ),
    ("optimization", "linear_program"): lambda a: optimization.linear_program_2var(
        tuple(a["objective"]),
        [tuple(c) for c in a["constraints"]],
        maximize=a.get("maximize", True),
    ),
    ("graph_theory", "topological_sort"): lambda a: graph_theory.topological_sort(a["graph"]),
    ("graph_theory", "components"): lambda a: graph_theory.connected_components(a["graph"]),
    ("graph_theory", "has_cycle"): lambda a: graph_theory.has_cycle(
        a["graph"], directed=a.get("directed", False)
    ),
    ("graph_theory", "mst"): lambda a: graph_theory.minimum_spanning_tree(
        [tuple(e) for e in a["edges"]]
    ),
    ("graph_theory", "is_bipartite"): lambda a: graph_theory.is_bipartite(a["graph"]),
    ("formal_languages", "matches_regex"): lambda a: formal_languages.matches_regex(
        a["pattern"], a["text"]
    ),
    ("formal_languages", "is_balanced"): lambda a: formal_languages.is_balanced(a["text"]),
    ("formal_languages", "derives"): lambda a: formal_languages.derives(
        a["grammar"], a["start"], a["target"]
    ),
    ("computability", "ackermann"): lambda a: computability.ackermann(a["m"], a["n"]),
    ("computability", "busy_beaver"): lambda a: computability.busy_beaver(a["n"]),
    ("complexity", "compare_growth"): lambda a: complexity.compare_growth(a["a"], a["b"]),
    ("complexity", "is_polynomial"): lambda a: complexity.is_polynomial(a["label"]),
    ("complexity", "class_info"): lambda a: complexity.class_info(a["name"]),
}


def supported_domains() -> list[str]:
    """Sorted list of the compute domains this service exposes (for discovery)."""
    return sorted({domain for domain, _op in _TABLE})


def compute(domain: str, operation: str, args: dict[str, Any]) -> Any:
    """Run one deterministic operation. Raises :class:`ComputeError` if unknown,
    or :class:`FoundationsError`/``KeyError``/``TypeError``/``ValueError`` on bad args.
    """
    handler = _TABLE.get((domain, operation))
    if handler is None:
        raise ComputeError(f"unknown operation '{domain}.{operation}'")
    return handler(args)
