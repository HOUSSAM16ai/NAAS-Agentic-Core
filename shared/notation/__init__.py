"""الحزمة القانونية لرموز الرياضيات — المصدر الوحيد للمونوليث والخدمة المصغّرة (D-185)."""

from __future__ import annotations

from shared.notation.registry import (
    NOTATION_REGISTRY,
    REGISTRY_VERSION,
    NotationEntry,
    all_symbols,
    define,
    normalize,
    resolve,
)

__all__ = [
    "NOTATION_REGISTRY",
    "REGISTRY_VERSION",
    "NotationEntry",
    "all_symbols",
    "define",
    "normalize",
    "resolve",
]
