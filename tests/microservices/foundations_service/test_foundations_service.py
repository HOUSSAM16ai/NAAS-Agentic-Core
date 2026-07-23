"""Tests for foundations-service (D-183) — the API-first "first roots" compute Skill.

Covers the HTTP surface (/compute happy + fail-open, /health, /metrics), the
dispatch layer (every domain + unknown-op + bad-args), and confirms the service
imports no `app` / sibling module (isolation). Targets 100% on the service code.
"""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from microservices.foundations_service.main import app
from microservices.foundations_service.src.dispatch import (
    ComputeError,
    compute,
    supported_domains,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as c:
        yield c


class TestHealthAndMetrics:
    def test_health(self, client: TestClient):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["service"] == "foundations-service"
        assert body["llm_backend"] == "none"
        assert "linear_algebra" in body["domains"]

    def test_metrics(self, client: TestClient):
        client.post(
            "/compute",
            json={"domain": "complexity", "operation": "is_polynomial", "args": {"label": "O(n)"}},
        )
        r = client.get("/metrics")
        assert r.status_code == 200
        assert "cogniforge_foundations_startup_info" in r.text
        assert "cogniforge_foundations_compute_invocations_total" in r.text


class TestComputeEndpoint:
    def test_linear_algebra(self, client: TestClient):
        r = client.post(
            "/compute",
            json={
                "domain": "linear_algebra",
                "operation": "solve",
                "args": {"matrix": [[2, 1], [1, 3]], "b": [3, 4]},
            },
        )
        body = r.json()
        assert body["ok"] and math.isclose(body["result"][0], 1.0)
        assert body["duration_ms"] >= 0

    def test_calculus_and_optimization(self, client: TestClient):
        r = client.post(
            "/compute",
            json={
                "domain": "calculus",
                "operation": "integral",
                "args": {"coeffs": [0, 0, 1], "a": 0, "b": 3},
            },
        )
        assert math.isclose(r.json()["result"], 9, abs_tol=1e-6)
        r2 = client.post(
            "/compute",
            json={
                "domain": "optimization",
                "operation": "minimize",
                "args": {"coeffs": [4, -4, 1], "a": -5, "b": 5},
            },
        )
        assert math.isclose(r2.json()["result"], 2, abs_tol=1e-4)

    def test_graph_and_formal_and_complexity(self, client: TestClient):
        r = client.post(
            "/compute",
            json={
                "domain": "graph_theory",
                "operation": "topological_sort",
                "args": {"graph": {"a": ["b"], "b": ["c"], "c": []}},
            },
        )
        assert r.json()["result"] == ["a", "b", "c"]
        r2 = client.post(
            "/compute",
            json={
                "domain": "formal_languages",
                "operation": "matches_regex",
                "args": {"pattern": "a(b|c)*d", "text": "abccbd"},
            },
        )
        assert r2.json()["result"] is True
        r3 = client.post(
            "/compute",
            json={
                "domain": "complexity",
                "operation": "class_info",
                "args": {"name": "NP"},
            },
        )
        assert r3.json()["result"]["tractable"] is None

    def test_unknown_operation_fails_open(self, client: TestClient):
        r = client.post("/compute", json={"domain": "x", "operation": "y", "args": {}})
        assert r.status_code == 200
        body = r.json()
        assert not body["ok"] and "unknown operation" in body["error"]

    def test_bad_args_fails_open(self, client: TestClient):
        r = client.post(
            "/compute",
            json={
                "domain": "linear_algebra",
                "operation": "solve",
                "args": {"matrix": [[1, 1], [1, 1]], "b": [2, 3]},  # singular
            },
        )
        assert r.status_code == 200
        assert not r.json()["ok"]


class TestDispatchLayer:
    def test_supported_domains(self):
        domains = supported_domains()
        assert "computability" in domains and "statistics" in domains

    def test_compute_direct(self):
        assert compute("computability", "ackermann", {"m": 2, "n": 2}) == 7

    def test_unknown_raises_compute_error(self):
        with pytest.raises(ComputeError):
            compute("nope", "nope", {})

    def test_empty_polynomial_raises(self):
        from microservices.foundations_service.src.foundations.errors import FoundationsError

        with pytest.raises(FoundationsError):
            compute("calculus", "derivative", {"coeffs": [], "x": 1})


def test_service_has_no_app_imports():
    """Isolation rule (CLAUDE.md §0.5 rule 3): no `app` / sibling-service import."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[3] / "microservices" / "foundations_service"
    for path in root.rglob("*.py"):
        src = path.read_text(encoding="utf-8")
        assert "from app" not in src and "import app\n" not in src, f"{path} imports app"
