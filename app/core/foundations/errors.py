"""Shared error type for the foundational reasoning layer.

Every primitive raises ``FoundationsError`` (a ``ValueError`` subclass) on a
domain violation — negative counts, k > n, empty distributions, etc. — so callers
can catch one exception type and never see a bare ``ZeroDivisionError`` or
``math`` domain error leak through.
"""

from __future__ import annotations


class FoundationsError(ValueError):
    """A theoretical-reasoning primitive was called with invalid input."""


def require_non_negative_int(value: int, name: str) -> int:
    """Return ``value`` if it is a non-negative int, else raise ``FoundationsError``."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise FoundationsError(f"{name} must be an int, got {type(value).__name__}")
    if value < 0:
        raise FoundationsError(f"{name} must be >= 0, got {value}")
    return value
