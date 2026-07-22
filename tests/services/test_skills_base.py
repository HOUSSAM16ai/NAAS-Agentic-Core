"""Runtime evidence for the BaseSkill OOP consolidation (D-179).

Proves the new abstraction is real (import + call chain + runtime evidence — the
anti-ZOMBIE doctrine of CLAUDE.md §6.6), not just present in the tree.
"""

from __future__ import annotations

import importlib

import pytest

from app.services.skills.base import BaseSkill, skill_counter, skill_histogram


def test_baseskill_is_abstract() -> None:
    """BaseSkill cannot be instantiated directly (true ABC)."""
    with pytest.raises(TypeError):
        BaseSkill()  # type: ignore[abstract]


def test_concrete_skill_instantiable_and_runs() -> None:
    class _Echo(BaseSkill):
        name = "echo"

        def run(self, payload):
            return payload

    skill = _Echo()
    assert skill.name == "echo"
    assert skill.version == "1.0.0"
    assert skill.run("hi") == "hi"


def test_instance_is_cached_per_class() -> None:
    class _A(BaseSkill):
        name = "a"

        def run(self, *a, **k):
            return "a"

    class _B(BaseSkill):
        name = "b"

        def run(self, *a, **k):
            return "b"

    a1, a2 = _A.instance(), _A.instance()
    b1 = _B.instance()
    assert a1 is a2  # same object across calls
    assert a1 is not b1  # subclasses do not share a cached instance
    assert isinstance(a1, _A) and isinstance(b1, _B)


def test_run_supports_heterogeneous_signatures() -> None:
    """run() is untyped so a skill whose action is 'align' can delegate to it."""

    class _Aligner(BaseSkill):
        name = "aligner"

        def align(self, text: str) -> str:
            return text.upper()

        def run(self, *args, **kwargs):
            return self.align(*args, **kwargs)

    assert _Aligner.instance().run("ok") == "OK"


def test_skill_counter_is_reimport_safe() -> None:
    """skill_counter registers once and never raises on duplicate registration."""
    c1 = skill_counter("cogniforge_test_base_probe_total", "probe counter", ("status",))
    # Second call with the same name must not raise Duplicated timeseries.
    c2 = skill_counter("cogniforge_test_base_probe_total", "probe counter", ("status",))
    # Both are usable (real Counter or no-op) — the fluent API never raises.
    c1.labels(status="ok").inc()
    c2.labels(status="ok").inc()


def test_skill_histogram_is_reimport_safe() -> None:
    h1 = skill_histogram("cogniforge_test_base_hist_seconds", "probe hist", ("kind",))
    h2 = skill_histogram("cogniforge_test_base_hist_seconds", "probe hist", ("kind",))
    h1.labels(kind="x").observe(0.1)
    h2.labels(kind="x").observe(0.2)


def test_base_module_reexported_from_package() -> None:
    """BaseSkill and helpers are importable from the skills package root."""
    pkg = importlib.import_module("app.services.skills")
    assert getattr(pkg, "BaseSkill", None) is BaseSkill
    assert callable(getattr(pkg, "skill_counter", None))
