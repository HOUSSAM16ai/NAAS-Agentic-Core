"""Shared error type for the general reasoning layer.

Mirrors ``app.core.foundations.errors.FoundationsError``: every reasoning
primitive raises ``ReasoningError`` (a ``ValueError`` subclass) on a structural
violation — an unknown node, a cyclic dependency where a DAG is required, an
empty instance set — so a caller catches one exception type instead of a bare
``KeyError`` / ``IndexError`` leaking through.
"""

from __future__ import annotations


class ReasoningError(ValueError):
    """A reasoning primitive was called with structurally invalid input."""


def require_non_empty(value: object, name: str) -> None:
    """Raise ``ReasoningError`` if ``value`` is empty (len 0) or ``None``."""
    if value is None or (hasattr(value, "__len__") and len(value) == 0):  # type: ignore[arg-type]
        raise ReasoningError(f"{name} must be non-empty")
