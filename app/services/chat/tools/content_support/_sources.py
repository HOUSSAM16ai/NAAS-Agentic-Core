"""CONTENT_TOOLS_SOURCE_FILES — manifest (D-255، نمط D-164/D-173/D-252).

أي بوّابة/اختبار يقرأ مصدر أدوات المحتوى `content.py` نصيًا (حراس العقيدة ·
legacy noop · canonical/ownership fences) يقرأ المُركَّب عبر
`read_content_tools_source()` — إضافة شريحة جديدة = سطر واحد هنا.

**لماذا هذه البوابة موجودة:** كان منطق البحث العميق وتوحيد الشعبة وكشف
الفشل اللين (خطأ على شكل بيانات) متكدّسًا في `content.py` — hotspot
بتردد تغييرٍ عالٍ (40) وتعقيدٍ متجاوز حد الدستور (D-255). فُكِّك إلى
هذه الحزمة، والمانيفست يضمن أن كل حاجزٍ نصي يقرأ السلوك المفكك كاملًا
لا القشرة فقط.
"""

from __future__ import annotations

from pathlib import Path

_TOOLS = Path(__file__).resolve().parents[2]

CONTENT_TOOLS_SOURCE_FILES: tuple[str, ...] = (
    # القشرة: الاستقبال + التحقق من المخطط + التفويض (D-255).
    "tools/content.py",
    # D-255 (2026-08-14): شرائح أدوات المحتوى — البحث العميق + سياق الاستعلام.
    "tools/content_support/search.py",
    # D-255 (2026-08-14): شرائح أدوات المحتوى — توحيد اسم الشعبة.
    "tools/content_support/branch.py",
)


def read_content_tools_source() -> str:
    """المصدر المُركَّب لأدوات المحتوى (للبوابات النصية)."""
    return "\n".join(
        (_TOOLS / name).read_text(encoding="utf-8") for name in CONTENT_TOOLS_SOURCE_FILES
    )
