"""CUSTOMER_CHAT_SOURCE_FILES — manifest (D-173 Stage 2b، نمط D-164/D-168).

أي بوّابة/اختبار يقرأ مصدر مسار WS للعميل نصياً يقرأ المُركَّب عبر
`read_customer_chat_source()` — إضافة شريحة جديدة = سطر واحد هنا.
"""

from __future__ import annotations

from pathlib import Path

_ROUTERS = Path(__file__).resolve().parents[1]

CUSTOMER_CHAT_SOURCE_FILES: tuple[str, ...] = (
    "customer_chat.py",
    "customer_chat_support/transport.py",
    "customer_chat_support/pedagogy.py",
    "customer_chat_support/frames.py",
)


def read_customer_chat_source() -> str:
    """المصدر المُركَّب لمسار WS العميل (للبوّابات النصية)."""
    return "\n".join(
        (_ROUTERS / name).read_text(encoding="utf-8") for name in CUSTOMER_CHAT_SOURCE_FILES
    )
