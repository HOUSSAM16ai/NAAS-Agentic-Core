"""FoundationsComputeSkill — deterministic access to the "first roots" engines (D-183).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill». This skill is the single
call surface over the dependency-free foundation engines (``app/core/foundations``)
— the verified computational substrate the platform reasons *from* rather than
guessing at (CLAUDE.md §0: "symbolic truth before language"). It never calls an
LLM: every number/structure it returns comes from a deterministic engine.

## المسؤولية الواحدة
Dispatch a structured request ``{domain, operation, args}`` to the matching
foundation primitive and return a JSON-serialisable result. Fail-open — a domain
violation is reported in ``error`` (never raised), so a caller (route or the
reasoning composer) always gets a well-formed answer.

Functions for calculus/optimization are passed as **polynomial coefficient lists**
(``[c0, c1, c2] → c0 + c1·x + c2·x²``) so the whole surface stays JSON-safe and
deterministic — no ``eval`` of caller-supplied expressions.

## القياس (Prometheus)
- ``cogniforge_skill_foundations_compute_total{domain, status}`` (counter)
- ``cogniforge_skill_foundations_compute_duration_seconds`` (histogram)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, ClassVar

from pydantic import Field

from app.core.foundations import (
    calculus,
    complexity,
    computability,
    formal_languages,
    graph_theory,
    linear_algebra,
    optimization,
    statistics,
)
from app.core.foundations.errors import FoundationsError
from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram

_INVOCATIONS = skill_counter(
    "cogniforge_skill_foundations_compute_total",
    "FoundationsComputeSkill invocations",
    ("domain", "status"),
)
_DURATION = skill_histogram(
    "cogniforge_skill_foundations_compute_duration_seconds",
    "FoundationsComputeSkill duration (seconds)",
)


class FoundationsComputeInput(RobustBaseModel):
    """طلب حساب حتمي — مجال + عملية + وسائط مُهيكَلة (JSON)."""

    domain: str = Field(..., min_length=1, max_length=40)
    operation: str = Field(..., min_length=1, max_length=40)
    args: dict[str, Any] = Field(default_factory=dict)


class FoundationsComputeOutput(RobustBaseModel):
    """مخرج الحساب — النتيجة الحتمية أو رسالة الخطأ (لا يرفع استثناءً)."""

    domain: str
    operation: str
    ok: bool
    result: Any = None
    error: str | None = None


def _poly(coeffs: list[float]) -> Callable[[float], float]:
    """Build ``f(x) = Σ cᵢ·xⁱ`` from a coefficient list (JSON-safe, no eval)."""
    if not coeffs:
        raise FoundationsError("polynomial: coeffs must be non-empty")

    def f(x: float) -> float:
        return sum(c * x**i for i, c in enumerate(coeffs))

    return f


# ── Dispatch table: (domain, operation) -> handler(args) -> JSON-safe result ──


def _dispatch() -> dict[tuple[str, str], Callable[[dict[str, Any]], Any]]:
    return {
        # --- linear algebra ---
        ("linear_algebra", "solve"): lambda a: linear_algebra.solve_linear_system(
            a["matrix"], a["b"]
        ),
        ("linear_algebra", "determinant"): lambda a: linear_algebra.determinant(a["matrix"]),
        ("linear_algebra", "rank"): lambda a: linear_algebra.matrix_rank(a["matrix"]),
        ("linear_algebra", "matmul"): lambda a: linear_algebra.matmul(a["a"], a["b"]),
        ("linear_algebra", "dot"): lambda a: linear_algebra.dot(a["a"], a["b"]),
        ("linear_algebra", "transpose"): lambda a: linear_algebra.transpose(a["matrix"]),
        # --- calculus (polynomial coefficient lists) ---
        ("calculus", "derivative"): lambda a: calculus.derivative(_poly(a["coeffs"]), a["x"]),
        ("calculus", "integral"): lambda a: calculus.definite_integral(
            _poly(a["coeffs"]), a["a"], a["b"]
        ),
        ("calculus", "root"): lambda a: calculus.newton_root(_poly(a["coeffs"]), a.get("x0", 1.0)),
        # --- statistics ---
        ("statistics", "correlation"): lambda a: statistics.correlation(a["xs"], a["ys"]),
        ("statistics", "regression"): lambda a: statistics.linear_regression(a["xs"], a["ys"]),
        ("statistics", "percentile"): lambda a: statistics.percentile(a["data"], a["p"]),
        ("statistics", "confidence_interval"): lambda a: list(
            statistics.confidence_interval_mean(a["data"], a.get("confidence", 0.95))
        ),
        # --- optimization ---
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
        # --- graph theory ---
        ("graph_theory", "topological_sort"): lambda a: graph_theory.topological_sort(a["graph"]),
        ("graph_theory", "components"): lambda a: graph_theory.connected_components(a["graph"]),
        ("graph_theory", "has_cycle"): lambda a: graph_theory.has_cycle(
            a["graph"], directed=a.get("directed", False)
        ),
        ("graph_theory", "mst"): lambda a: graph_theory.minimum_spanning_tree(
            [tuple(e) for e in a["edges"]]
        ),
        ("graph_theory", "is_bipartite"): lambda a: graph_theory.is_bipartite(a["graph"]),
        # --- formal languages ---
        ("formal_languages", "matches_regex"): lambda a: formal_languages.matches_regex(
            a["pattern"], a["text"]
        ),
        ("formal_languages", "is_balanced"): lambda a: formal_languages.is_balanced(a["text"]),
        ("formal_languages", "derives"): lambda a: formal_languages.derives(
            a["grammar"], a["start"], a["target"]
        ),
        # --- computability ---
        ("computability", "ackermann"): lambda a: computability.ackermann(a["m"], a["n"]),
        ("computability", "busy_beaver"): lambda a: computability.busy_beaver(a["n"]),
        # --- complexity ---
        ("complexity", "compare_growth"): lambda a: complexity.compare_growth(a["a"], a["b"]),
        ("complexity", "is_polynomial"): lambda a: complexity.is_polynomial(a["label"]),
        ("complexity", "class_info"): lambda a: complexity.class_info(a["name"]),
    }


class FoundationsComputeSkill(BaseSkill[FoundationsComputeInput, FoundationsComputeOutput]):
    """يُوجِّه طلب حساب حتمي إلى محرّك الأسس المناسب — رمزي، بلا LLM (D-183)."""

    name: ClassVar[str] = "foundations_compute"
    version: ClassVar[str] = "1.0.0"

    def __init__(self) -> None:
        self._table = _dispatch()

    @property
    def domains(self) -> list[str]:
        """قائمة المجالات المدعومة (للاكتشاف/الرصد)."""
        return sorted({domain for domain, _op in self._table})

    def run(self, payload: FoundationsComputeInput) -> FoundationsComputeOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`compute`."""
        return self.compute(payload)

    def compute(self, payload: FoundationsComputeInput) -> FoundationsComputeOutput:
        """يُنفّذ العملية حتمياً — لا يرفع استثناءً (الخطأ يُبلَّغ في `error`)."""
        t0 = time.perf_counter()
        handler = self._table.get((payload.domain, payload.operation))
        if handler is None:
            _record(payload.domain, "unknown", time.perf_counter() - t0)
            return FoundationsComputeOutput(
                domain=payload.domain,
                operation=payload.operation,
                ok=False,
                error=f"unknown operation '{payload.domain}.{payload.operation}'",
            )
        try:
            result = handler(payload.args)
            _record(payload.domain, "ok", time.perf_counter() - t0)
            return FoundationsComputeOutput(
                domain=payload.domain, operation=payload.operation, ok=True, result=result
            )
        except (FoundationsError, KeyError, TypeError, ValueError) as exc:
            _record(payload.domain, "error", time.perf_counter() - t0)
            return FoundationsComputeOutput(
                domain=payload.domain,
                operation=payload.operation,
                ok=False,
                error=f"{type(exc).__name__}: {exc}",
            )


def _record(domain: str, status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(domain=domain, status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_foundations_compute_skill() -> FoundationsComputeSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return FoundationsComputeSkill.instance()


__all__ = [
    "FoundationsComputeInput",
    "FoundationsComputeOutput",
    "FoundationsComputeSkill",
    "get_foundations_compute_skill",
]
