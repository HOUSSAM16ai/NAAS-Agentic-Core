"""KERNEL_SOURCE_FILES — مانيفست المركّب (نمط D-164/D-173/D-252/D-255/D-258/D-260).

أي بوّابة/اختبار يقرأ مصدر النواة `app/kernel.py` نصيًا (runtime truth ·
حراس العقيدة) يقرأ المركّب عبر `read_kernel_source()` — إضافة شريحةٍ جديدة
= سطر واحد هنا.
"""

from __future__ import annotations

import pathlib

_APP = pathlib.Path(__file__).resolve().parents[2]
_SUPPORT = _APP / "core" / "kernel_support"

KERNEL_SOURCE_FILES: tuple[str, ...] = (
    # القشرة: التركيب الوظيفي (Functional Composition) والتفويض (D-260).
    "kernel.py",
    # D-260 (2026-08-15): شريحة دورة الحياة — إقلاع وإيقاف صادقان (D-245/D-201).
    "core/kernel_support/lifecycle.py",
    # D-260 (2026-08-15): شريحة العقود — مطابقة OpenAPI/AsyncAPI ضد runtime.
    "core/kernel_support/contracts.py",
    # D-260 (2026-08-15): شريحة OTel — SDK bootstrap + per-app instrumentation.
    "core/kernel_support/otel.py",
    # D-260 (2026-08-15): شريحة التركيب — middleware/routers/static combinators.
    "core/kernel_support/compose.py",
)


def read_kernel_source() -> str:
    """المصدر المركّب للنواة (للبوابات النصية — runtime truth)."""
    parts: list[str] = []
    for name in KERNEL_SOURCE_FILES:
        source = (_APP / name).read_text(encoding="utf-8")
        parts.append(f"# === SHELL/SHARD: {name} ===\n" + source)
    return "\n".join(parts)
