"""DOCTRINE_SOURCE_FILES — manifest of the doctrine package (D-173 Stage 2a).

نمط D-164/D-168: أي بوّابة/اختبار يقرأ مصدر الـ doctrine نصياً يقرأ المُركَّب
عبر `read_doctrine_source()` — إضافة شريحة جديدة = سطر واحد هنا.
"""

from __future__ import annotations

from pathlib import Path

_PKG = Path(__file__).resolve().parent

DOCTRINE_SOURCE_FILES: tuple[str, ...] = (
    "exercise_core.py",
    "invocation.py",
    "pedagogy.py",
    "probability.py",
    "platform_layer.py",
    "manifest_registry.py",
    "__init__.py",
)


def read_doctrine_source() -> str:
    """المصدر المُركَّب للحزمة كاملة (للبوّابات النصية)."""
    return "\n".join((_PKG / name).read_text(encoding="utf-8") for name in DOCTRINE_SOURCE_FILES)
