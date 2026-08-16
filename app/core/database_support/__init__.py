"""شرائح قاعدة البيانات (D-261 — تفكيك hotspot `app/core/database.py` — CodeScene X-Ray 2026-08-16).
`app/core/database.py` كان hotspotًا في CodeScene X-Ray job 72: `create_db_engine`
بـ 86 سطرًا وتعقيد F(11)/radon C(12) وتردد تغيير 8 (Complex Method) — مع churn=12
على `get_db` ناتجًا عن مسارٍ تربوي زومبي (ISS-172). فُكِّك إلى قشرةٍ تفويضٍ
في `app/core/database.py` + حزمة شرائح نقية هنا — صفر تغيير سلوكي.

القاعدة المعمارية (نمط D-252→D-260): القشرة تبقى المرجع التنفيذي الوحيد؛
الشرائح دوالٌ نقيةٌ بلا حالةٍ (تحويلات URL · سياق SSL · تكوينات الـ pool)
تُستورد وتفوَّض إليها القشرة بالاسم نفسه (لا أسماء أعيد تعريفها —
no shadowing) ليبقى كل monkeypatch واختبارٍ قديم فعالًا.
المانيفست المركّب `DATABASE_SOURCE_FILES` (نمط D-164/D-173/D-255/D-258/D-260)
يغذّي كل بوابة نصية تقرأ سلوك المصنع نصًّيا — إضافة شريحةٍ جديدة = سطرٌ واحد هنا.
"""

from app.core.database_support._pools import build_pool_kwargs
from app.core.database_support._sources import (
    DATABASE_SOURCE_FILES,
    read_database_source,
)
from app.core.database_support._ssl import build_ssl_connect_args
from app.core.database_support._url import (
    _is_supabase_url,
    _rewrite_supabase_port,
    _strip_ssl_query,
    _upgrade_drivername,
)

__all__ = [
    "DATABASE_SOURCE_FILES",
    "_is_supabase_url",
    "_rewrite_supabase_port",
    "_strip_ssl_query",
    "_upgrade_drivername",
    "build_pool_kwargs",
    "build_ssl_connect_args",
    "read_database_source",
]
