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
    # D-173 Stage 3 (2026-08-13): شريحة دورة الدور — hotspot `chat_stream_ws` (669
    # سطراً / تعقيد 69 / تردد 53) فُكِّك إلى هذه الوحدة؛ البوّابات النصية تقرأ
    # المصدر المركّب عبرها فيبقى كل حاجز معماري فعّالاً على السلوك المفكك.
    "customer_chat_support/turn_lifecycle.py",
)


def read_customer_chat_source() -> str:
    """المصدر المُركَّب لمسار WS العميل (للبوّابات النصية)."""
    return "\n".join(
        (_ROUTERS / name).read_text(encoding="utf-8") for name in CUSTOMER_CHAT_SOURCE_FILES
    )
