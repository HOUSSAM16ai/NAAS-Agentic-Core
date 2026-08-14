"""حزمة شرائح أدوات المحتوى (D-255).

شرائح نقية بلا حالة تحمل منطق البحث العميق وتوحيد الشعبة وكشف
«الفشل اللين» (خطأ على شكل بيانات) — مفككة من `tools/content.py`.
القشرة `content.py` تستورد هذه الشرائح وتفوض إليها؛ تبقى التوقيعات
العامة كما هي (صفر تغيير سلوكي).
"""

from app.services.chat.tools.content_support._sources import (
    CONTENT_TOOLS_SOURCE_FILES,
    read_content_tools_source,
)
from app.services.chat.tools.content_support.search import (
    SearchFilters,
    build_search_context,
    build_search_report,
    normalize_branch,
    scan_for_error,
)

__all__ = [
    "CONTENT_TOOLS_SOURCE_FILES",
    "SearchFilters",
    "build_search_context",
    "build_search_report",
    "normalize_branch",
    "read_content_tools_source",
    "scan_for_error",
]
