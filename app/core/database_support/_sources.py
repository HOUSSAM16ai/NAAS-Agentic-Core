"""DATABASE_SOURCE_FILES — المانيفست المركّب (D-261 — نمط D-164/D-173/D-252/D-255/D-258/D-260).
أي بوّابة/اختبار يقرأ مصدر مصنع قاعدة البيانات `app/core/database.py` نصًّيا
(runtime truth · حراس العقيدة) يقرأ المركّب عبر `read_database_source()` —
إضافة شريحةٍ جديدة = سطرٌ واحد هنا.

**لماذا هذا المانيفست موجود:** كان منطق المصنع (إقلاع الـ URL · SSL · PgBouncer ·
تكوينات الـ pool) متكدّسًا في دالةٍ واحدةٍ بـ 86 سطرًا وتعقيدٍ C(12) — hotspot
في CodeScene X-Ray job 72 (D-261 · ISS-172). فُكِّك إلى حزمة شرائح نقية هنا،
والمانيفست يضمن أن كل حاجزٍ نصي يقرأ السلوك المفكك كاملًا لا القشرة فقط.
"""

from __future__ import annotations

import pathlib

_APP = pathlib.Path(__file__).resolve().parents[2]
_SUPPORT = _APP / "core" / "database_support"

DATABASE_SOURCE_FILES: tuple[str, ...] = (
    # القشرة: المصنع الكنسي (Canonical Database Factory) — تفويض فقط (D-261).
    "core/database.py",
    # D-261 (2026-08-16): شريحة تحويلات الـ URL — كشف Supabase · إعادة كتابة
    # المنفذ (PgBouncer 6543 → جلسة 5432 · D-WS-FLAP-001) · ترقية البروتوكول ·
    # تجريد معاملات SSL من الاستعلام.
    "core/database_support/_url.py",
    # D-261 (2026-08-16): شريحة سياق SSL — بناء ssl.SSLContext لكل نمطٍ
    # (require/verify-ca/verify-full).
    "core/database_support/_ssl.py",
    # D-261 (2026-08-16): شريحة تكوينات الـ pool — Supabase الصغير (D-WS-FLAP-001)
    # · التطوير · الإنتاج · SQLite.
    "core/database_support/_pools.py",
)


def read_database_source() -> str:
    """المصدر المركّب لمصنع قاعدة البيانات (للبوابات النصية — runtime truth)."""
    parts: list[str] = []
    for name in DATABASE_SOURCE_FILES:
        source = (_APP / name).read_text(encoding="utf-8")
        parts.append(f"# === SHELL/SHARD: {name} ===\n" + source)
    return "\n".join(parts)
