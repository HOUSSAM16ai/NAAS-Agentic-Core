"""Tests for FoundationsComputeSkill + compose_reasoning wiring (D-183).

Proves the deterministic "first roots" compute Skill dispatches to the verified
engines on the happy path, fails open (never raises) on bad args / unknown ops,
is a proper BaseSkill singleton, and is reachable through the reasoning composer.
"""

from __future__ import annotations

import math

from app.services.skills.base import BaseSkill
from app.services.skills.foundations_compute_skill import (
    FoundationsComputeInput,
    FoundationsComputeSkill,
    get_foundations_compute_skill,
)
from app.services.skills.registry import compose_reasoning, get_skill_registry


def _compute(domain: str, operation: str, **args):
    skill = get_foundations_compute_skill()
    return skill.compute(FoundationsComputeInput(domain=domain, operation=operation, args=args))


class TestFoundationsComputeSkill:
    def test_is_base_skill_singleton(self):
        assert issubclass(FoundationsComputeSkill, BaseSkill)
        assert get_foundations_compute_skill() is get_foundations_compute_skill()
        assert FoundationsComputeSkill.name == "foundations_compute"

    def test_domains_property(self):
        domains = get_foundations_compute_skill().domains
        for expected in (
            "linear_algebra",
            "calculus",
            "statistics",
            "optimization",
            "graph_theory",
            "formal_languages",
            "computability",
            "complexity",
        ):
            assert expected in domains

    def test_run_delegates_to_compute(self):
        out = get_foundations_compute_skill().run(
            FoundationsComputeInput(
                domain="complexity", operation="is_polynomial", args={"label": "O(n)"}
            )
        )
        assert out.ok and out.result is True

    def test_linear_algebra(self):
        out = _compute("linear_algebra", "solve", matrix=[[2, 1], [1, 3]], b=[3, 4])
        assert out.ok and math.isclose(out.result[0], 1.0) and math.isclose(out.result[1], 1.0)
        assert _compute("linear_algebra", "determinant", matrix=[[1, 2], [3, 4]]).result == -2.0
        assert _compute("linear_algebra", "rank", matrix=[[1, 2], [2, 4]]).result == 1
        assert _compute("linear_algebra", "dot", a=[1, 2], b=[3, 4]).result == 11

    def test_calculus(self):
        # f(x) = x^2 → coeffs [0,0,1]
        assert math.isclose(
            _compute("calculus", "derivative", coeffs=[0, 0, 1], x=3).result, 6, abs_tol=1e-4
        )
        assert math.isclose(
            _compute("calculus", "integral", coeffs=[0, 0, 1], a=0, b=3).result, 9, abs_tol=1e-6
        )
        # f(x) = x^2 - 2 → coeffs [-2, 0, 1]
        assert math.isclose(
            _compute("calculus", "root", coeffs=[-2, 0, 1], x0=1).result, math.sqrt(2), abs_tol=1e-6
        )

    def test_statistics(self):
        assert math.isclose(
            _compute("statistics", "correlation", xs=[1, 2, 3], ys=[2, 4, 6]).result, 1.0
        )
        reg = _compute("statistics", "regression", xs=[1, 2, 3], ys=[2, 4, 6]).result
        assert math.isclose(reg["slope"], 2.0)
        ci = _compute("statistics", "confidence_interval", data=[1, 2, 3, 4, 5]).result
        assert ci[0] < 3 < ci[1]
        assert _compute("statistics", "percentile", data=[1, 2, 3, 4], p=50).result == 2.5

    def test_optimization(self):
        assert math.isclose(
            _compute("optimization", "minimize", coeffs=[4, -4, 1], a=-5, b=5).result,
            2,
            abs_tol=1e-4,
        )
        assert math.isclose(
            _compute("optimization", "root", coeffs=[-2, 1], a=0, b=5).result, 2, abs_tol=1e-6
        )
        lp = _compute(
            "optimization", "linear_program", objective=[3, 2], constraints=[[1, 1, 4], [1, 3, 6]]
        ).result
        assert lp["value"] > 0

    def test_graph_theory(self):
        assert _compute(
            "graph_theory", "topological_sort", graph={"a": ["b"], "b": ["c"], "c": []}
        ).result == ["a", "b", "c"]
        assert (
            _compute(
                "graph_theory", "has_cycle", graph={"a": ["b"], "b": ["a"]}, directed=True
            ).result
            is True
        )
        assert (
            _compute("graph_theory", "is_bipartite", graph={"a": ["b"], "b": ["a"]}).result is True
        )
        mst = _compute(
            "graph_theory", "mst", edges=[["a", "b", 1], ["b", "c", 2], ["a", "c", 3]]
        ).result
        assert len(mst) == 2
        assert _compute("graph_theory", "components", graph={"a": ["b"], "c": ["d"]}).result == [
            ["a", "b"],
            ["c", "d"],
        ]

    def test_formal_languages(self):
        assert (
            _compute("formal_languages", "matches_regex", pattern="a(b|c)*d", text="abccbd").result
            is True
        )
        assert _compute("formal_languages", "is_balanced", text="([]{})").result is True
        assert (
            _compute(
                "formal_languages", "derives", grammar={"S": ["aSb", ""]}, start="S", target="aabb"
            ).result
            is True
        )

    def test_computability_and_complexity(self):
        assert _compute("computability", "ackermann", m=2, n=2).result == 7
        assert _compute("computability", "busy_beaver", n=4).result == 13
        assert _compute("complexity", "compare_growth", a="O(n)", b="O(n^2)").result == -1
        assert _compute("complexity", "is_polynomial", label="O(n log n)").result is True
        assert _compute("complexity", "class_info", name="P").result["tractable"] is True

    def test_unknown_operation_fails_open(self):
        out = _compute("linear_algebra", "eigen_decomposition_9000", matrix=[[1]])
        assert not out.ok and "unknown operation" in out.error
        out2 = _compute("bogus_domain", "nope")
        assert not out2.ok

    def test_bad_args_fails_open(self):
        out = _compute("linear_algebra", "solve", matrix=[[1, 1], [1, 1]], b=[2, 3])  # singular
        assert not out.ok and out.error
        out2 = _compute("linear_algebra", "solve")  # missing keys → KeyError, reported not raised
        assert not out2.ok
        out3 = _compute("computability", "busy_beaver", n=99)  # uncomputed
        assert not out3.ok
        out4 = _compute("calculus", "derivative", coeffs=[], x=1)  # empty polynomial
        assert not out4.ok and out4.error


class TestComposeReasoningWiring:
    def test_registry_has_foundations_compute(self):
        reg = get_skill_registry()
        descriptor = reg.get("foundations_compute")
        assert descriptor is not None
        assert descriptor.consumed_by  # not a ZOMBIE
        assert "api.routers.skills.compute_endpoint" in descriptor.consumed_by

    def test_compose_reasoning_invokes_foundations(self):
        composition = compose_reasoning(
            "حلّ الجملة الخطية",
            {
                "compute": {
                    "domain": "linear_algebra",
                    "operation": "determinant",
                    "args": {"matrix": [[1, 2], [3, 4]]},
                }
            },
        )
        assert "foundations_compute" in composition.modes
        assert composition.results["foundations_compute"]["ok"] is True
        assert composition.results["foundations_compute"]["result"] == -2.0

    def test_compose_reasoning_without_compute_key(self):
        composition = compose_reasoning("سؤال عادي بدون حساب")
        assert "foundations_compute" not in composition.modes
        assert "decomposition" in composition.modes  # always runs


class TestComputeRoute:
    async def test_compute_endpoint_ok(self):
        from app.api.routers.skills import ComputeRequest, compute_endpoint

        req = ComputeRequest(
            domain="linear_algebra", operation="determinant", args={"matrix": [[1, 2], [3, 4]]}
        )
        out = await compute_endpoint(req, _="user")
        assert out.ok and out.result == -2.0
        assert out.domain == "linear_algebra"

    async def test_compute_endpoint_fail_open(self):
        from app.api.routers.skills import ComputeRequest, compute_endpoint

        req = ComputeRequest(domain="nope", operation="nope", args={})
        out = await compute_endpoint(req, _="user")
        assert not out.ok and out.error

    async def test_reason_endpoint_forwards_compute(self):
        from app.api.routers.skills import ReasonRequest, reason_endpoint

        req = ReasonRequest(
            question="حلّل ثم احسب",
            compute={
                "domain": "linear_algebra",
                "operation": "determinant",
                "args": {"matrix": [[1, 2], [3, 4]]},
            },
        )
        out = await reason_endpoint(req, _="user")
        assert "foundations_compute" in out.modes
        assert out.results["foundations_compute"]["result"] == -2.0
