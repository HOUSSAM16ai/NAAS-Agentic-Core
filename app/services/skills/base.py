"""BaseSkill — canonical OOP base for every CogniForge skill (D-179).

CLAUDE.md §0.5 mandates that every AI capability be a *Skill*: an independent,
measurable, testable, replaceable unit. Historically each skill hand-rolled the
same three cross-cutting concerns:

1. **Identity** — an ad-hoc ``name`` / ``_skill_name`` / ``version`` attribute.
2. **Lazy singleton** — a module-level ``_x_singleton`` plus a ``get_x_skill()``
   accessor (repeated in ~16 skill modules).
3. **Prometheus metrics** — the verbose, re-import-safe
   ``try: from prometheus_client import REGISTRY, Counter ...`` guard block
   (repeated in ~13 skill modules).

``BaseSkill`` consolidates (1) and (2) into a small abstract base, and
``skill_counter`` / ``skill_histogram`` consolidate (3) into two helpers. This is
pure OOP structure — it changes no skill's behaviour, contracts, or metric names.

Design rules (kept deliberately narrow so the skills-layer stays clean):

* **Dependency-free** beyond the standard library and an *optional* lazy import of
  ``prometheus_client``. When prometheus is unavailable the helpers return a
  no-op object, so metrics never raise.
* **Never creates a new ``CollectorRegistry``** — the helpers register on the
  default global ``REGISTRY`` exactly as the existing skills do (the "never share
  a CollectorRegistry across microservices" rule is about *microservices*; inside
  the monolith the default registry is the single shared one).
* **No cross-service imports, no heavy ``app.*`` imports** — importing this module
  must stay cheap so any skill can adopt it.
"""

from __future__ import annotations

import abc
from typing import Any, ClassVar

__all__ = ["BaseSkill", "skill_counter", "skill_histogram"]


class _NoopMetric:
    """Stand-in returned when ``prometheus_client`` is absent or registration fails.

    Mirrors the ``Counter``/``Histogram`` fluent surface so call sites
    (``.labels(...).inc()`` / ``.observe(...)``) never raise.
    """

    def labels(self, *args: Any, **kwargs: Any) -> _NoopMetric:
        return self

    def inc(self, *args: Any, **kwargs: Any) -> None:
        return None

    def observe(self, *args: Any, **kwargs: Any) -> None:
        return None


def _existing_collector(name: str) -> Any | None:
    """Return the already-registered collector for ``name`` (re-import safe)."""
    try:
        from prometheus_client import REGISTRY
    except Exception:  # pragma: no cover - prometheus not installed
        return None
    mapping = getattr(REGISTRY, "_names_to_collectors", {})
    # A Counter registered as ``x_total`` is indexed under several timeseries
    # names; try the exact name and the common ``_total`` suffix variants.
    for key in (name, f"{name}_total", name.removesuffix("_total")):
        collector = mapping.get(key)
        if collector is not None:
            return collector
    return None


def skill_counter(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    """Return a Prometheus ``Counter`` registered once on the default REGISTRY.

    Consolidates the re-import-safe guard block duplicated across skill modules:
    the first import registers the counter; a re-import (common in tests) returns
    the *existing* collector instead of raising ``Duplicated timeseries``. When
    ``prometheus_client`` is unavailable, returns a :class:`_NoopMetric`.
    """
    try:
        from prometheus_client import Counter
    except Exception:  # pragma: no cover - prometheus not installed
        return _NoopMetric()
    try:
        return Counter(name, documentation, list(labelnames))
    except ValueError:
        return _existing_collector(name) or _NoopMetric()


def skill_histogram(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Any:
    """Return a Prometheus ``Histogram`` registered once on the default REGISTRY.

    Same re-import-safe semantics as :func:`skill_counter`.
    """
    try:
        from prometheus_client import Histogram
    except Exception:  # pragma: no cover - prometheus not installed
        return _NoopMetric()
    try:
        return Histogram(name, documentation, list(labelnames))
    except ValueError:
        return _existing_collector(name) or _NoopMetric()


class BaseSkill[InT, OutT](abc.ABC):
    """Abstract base for every CogniForge skill.

    Provides shared **identity** (``name`` / ``version``) and a per-concrete-class
    **lazy singleton** (:meth:`instance`) so skills stop re-implementing the
    ``_x_singleton`` + ``get_x_skill()`` pattern. Concrete skills implement
    :meth:`run` as a thin, uniform entry point that routes to their existing
    action method (``invoke`` / ``align`` / ``decide`` / ``evaluate`` / ...),
    enabling polymorphic dispatch (``for skill in registry: skill.run(payload)``)
    without changing any skill's public contract.

    ``BaseSkill`` itself is abstract and cannot be instantiated.
    """

    #: Stable skill identifier (e.g. ``"greeting"``). Concrete skills set this.
    name: ClassVar[str] = ""
    #: Semantic version of the skill's contract.
    version: ClassVar[str] = "1.0.0"

    @classmethod
    def instance(cls) -> BaseSkill:
        """Return a process-wide singleton of the concrete skill class.

        The cache lives on the concrete class (``cls.__dict__``), so each subclass
        gets its own instance and subclasses never share a parent's cached object.
        """
        cached = cls.__dict__.get("_singleton_instance")
        if cached is None:
            cached = cls()
            cls._singleton_instance = cached  # type: ignore[attr-defined]
        return cached

    @abc.abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Primary capability entry point.

        Concrete skills route this to their existing action method. It may return
        a value directly or an awaitable for async skills — callers await when
        needed. Kept intentionally untyped so heterogeneous skill signatures share
        one polymorphic surface.
        """
        raise NotImplementedError
