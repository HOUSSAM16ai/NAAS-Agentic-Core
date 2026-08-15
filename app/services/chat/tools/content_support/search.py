"""شريحة منطق البحث العميق والسياق (D-255).

فُكِّكت من `tools.content.search_content` (C(14) · 112 سطرًا · طريق وعر):
بناء سياق الاستعلام والقلب البحثي + كشف «الفشل اللين» (خطأ على شكل بيانات).

**صفر تغيير سلوكي**: كل النصوص والعتبات والسياسات (Fail-Fast — RFC 001)
مطابقة حرفًا للسلالة الأصلية.

**توحيد الشعبة في شريحة `branch.py` المستقلة (D-259)** — إزالة ازدواجية
الكود (Code Duplication — CodeScene) بعد أن كان المنطق مكررًا في هذه
الشريحة و`content.py`: هذا الملف يستوردها ولا يعيد تعريفها.
"""

from __future__ import annotations

import dataclasses
import json

from app.core.logging import get_logger
from app.services.chat.tools.content_support.branch import normalize_branch

__all__ = [
    "SearchFilters",
    "build_search_context",
    "build_search_report",
    "normalize_branch",
    "scan_for_error",
]

logger = get_logger("content-tools")


# ---------------------------------------------------------------------------
# 0) فلاتر البحث المعلنة (قانون late-binding من D-252)
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class SearchFilters:
    """فلاتر البحث المجمّعة في بيانات معلنة واحدة (D-255)."""

    q: str
    subject: str | None = None
    branch: str | None = None
    year: int | None = None
    level: str | None = None
    type: str | None = None


# ---------------------------------------------------------------------------
# 1) التحقق من الأخطاء المتداخلة (كسر Anti-Pattern: Error-as-Data)
# ---------------------------------------------------------------------------

# جدول تحويل نوع المدخل إلى الشريحة المسؤولة عن فحصه (مسار قرار واحد —
# يُزيل Bumpy Road الذي رصده CodeScene في `_scan_for_error` الأصلية):
# كل حالة نوع لها شريحة حتمية واحدة، والقشرة مجرد جدول تحويل بلا فروع.


def _dict_error_message(data: dict) -> str:
    """رسالة الخطأ المباشر للقاموس (سلالة أصلية حرفًا)."""
    return str(data.get("content") or data.get("error") or "Unknown Error")


def _scan_dict_error(data: dict) -> str | None:
    """يفحص القاموس: خطأ مباشر أو أول خطأ في قيمه (مسار خروج واحد)."""
    if data.get("type") == "error":
        return _dict_error_message(data)
    return next((err for v in data.values() if (err := scan_for_error(v))), None)


def _scan_iter_error(items) -> str | None:
    """يفحص تسلسلًا ويُعيد أول خطأ متداخل (مسار خروج واحد)."""
    return next((err for item in items if (err := scan_for_error(item))), None)


def _scan_json_string_error(raw: str) -> str | None:
    """يحاول تفسير السلسلة كـ JSON ويبحث فيها عن خطأ (مسار خروج واحد)."""
    try:
        return scan_for_error(json.loads(raw))
    except json.JSONDecodeError:
        return None


def _is_error_json_string(data: object) -> bool:
    """هل السلسلة JSON مرشّحة لمفاتيح خطأ؟ (شرطان حتميان بلا `and` متسلسل)."""
    if not isinstance(data, str):
        return False
    trimmed = data.strip()
    if not trimmed.startswith("{"):
        return False
    return '"type": "error"' in trimmed


def _lookup_scan_shard(data: object):
    """يُعيد الشريحة المسؤولة عن نوع المدخل، أو `None` إن لم يُفحص."""
    if isinstance(data, dict):
        return _scan_dict_error
    if isinstance(data, list):
        return _scan_iter_error
    if _is_error_json_string(data):
        return _scan_json_string_error
    return None


def scan_for_error(data: object) -> str | None:
    """يبحث بشكل عميق عن أي مفاتيح خطأ (تطابق حرفي للسلالة الأصلية).

    قشرة تحويل واحدة: نوع المدخل ⇒ شريحة حتمية ⇒ نتيجة. لا فروع متناثرة
    (Bumpy Road — CodeScene).
    """
    shard = _lookup_scan_shard(data)
    return shard(data) if shard else None


# ---------------------------------------------------------------------------
# 2) بناء سياق الاستعلام الكامل
# ---------------------------------------------------------------------------

# ترتيب فلاتر سياق الاستعلام الثابت (سلالة D-255 حرفًا).
_CONTEXT_FILTERS: tuple[tuple[str, str], ...] = (
    ("Subject", "subject"),
    ("Branch", "branch"),
    ("Year", "year"),
    ("Level", "level"),
    ("Type", "type"),
)


def _collect_context_parts(filters: dict[str, object]) -> list[str]:
    """يجمع أجزاء السياق النشطة فقط (مسار خروج واحد)."""
    return [f"{label}: {filters[raw]}" for label, raw in _CONTEXT_FILTERS if filters.get(raw)]


def build_search_context(filters: SearchFilters) -> str:
    """يركب سطر سياق الفلاتر ويلحقه بالاستعلام الأساسي (سلالة D-255 حرفيًا)."""
    context_parts = _collect_context_parts(dataclasses.asdict(filters))
    return f"{filters.q} ({', '.join(context_parts)})" if context_parts else filters.q


def build_search_report(q: str, full_query: str, report: object) -> list[dict[str, object]]:
    """صياغة تقرير البحث الموحد (نفس الشكل الأصلي حرفيًا)."""
    return [
        {
            "id": "research_report",
            "title": f"Research Report: {q}",
            "content": report,
            "type": "report",
            "metadata": {"query": full_query, "source": "SuperSearchOrchestrator"},
        }
    ]
