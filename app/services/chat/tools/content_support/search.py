"""شريحة منطق البحث العميق والتحقق (D-255).

فُكِّكت من `tools.content.search_content` (C(14) · 112 سطرًا · طريق وعر):
بناء سياق الاستعلام والقلب البحثي + كشف «الفشل اللين» (خطأ على شكل بيانات).

**صفر تغيير سلوكي**: كل النصوص والعتبات والسياسات (Fail-Fast — RFC 001)
مطابقة حرفًا للسلالة الأصلية.
"""

from __future__ import annotations

import dataclasses
import difflib
import json

from app.core.logging import get_logger
from app.domain.constants import BRANCH_MAP

logger = get_logger("content-tools")

#: ترجمة المفاتيح canonical إلى تسميات عربية معروضة (سلالة D-255).
_BRANCH_LABELS: dict[str, str] = {
    "experimental_sciences": "علوم تجريبية",
    "math_tech": "تقني رياضي",
    "mathematics": "رياضيات",
    "foreign_languages": "لغات أجنبية",
    "literature_philosophy": "آداب وفلسفة",
}

#: عتبة القرب الأدنى لقبول أقرب مطابقة (نفس عتبة الدستور الأصلية).
_CLOSE_MATCH_CUTOFF: float = 0.6

#: الحد الأدنى لطول البديل ليعتبر احتواءه في المدخل مطابقة (نفس القاعدة الأصلية).
_MIN_VARIANT_LENGTH: int = 3


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


def _scan_dict_error(data: dict) -> str | None:
    """يفحص القاموس: خطأ مباشر أو أول خطأ في قيمه (مسار خروج واحد)."""
    if data.get("type") == "error":
        return str(data.get("content") or data.get("error") or "Unknown Error")
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


def scan_for_error(data: object) -> str | None:
    """يبحث بشكل عميق عن أي مفاتيح خطأ (تطابق حرفي للسلالة الأصلية).

    القشرة الحتمية تُفوض لثلاث مراحل نقية — لا فروع متناثرة (Bumpy Road).
    """
    if isinstance(data, dict):
        return _scan_dict_error(data)

    if isinstance(data, list):
        return _scan_iter_error(data)

    if isinstance(data, str) and '"type": "error"' in data and data.strip().startswith("{"):
        return _scan_json_string_error(data)

    return None


# ---------------------------------------------------------------------------
# 2) توحيد اسم الشعبة (منطق الخدمة الموحد — نفس الأولويات الأصلية)
# ---------------------------------------------------------------------------


def _build_branch_indexes() -> tuple[dict[str, str], list[str]]:
    """الفهرس العكسي (بديل -> مفتاح canonical) وقائمة البدائل — نفس الترتيب الأصلي."""
    reverse_map: dict[str, str] = {}
    all_variants: list[str] = []
    for key, variants in BRANCH_MAP.items():
        for variant in variants:
            reverse_map[variant] = key
            all_variants.append(variant)
    return reverse_map, all_variants


def _resolve_branch_by_value(normalized: str) -> str | None:
    """أقرب مطابقة (cutoff 0.6) أو احتواء بديل بطول > 3 — مسار خروج واحد."""
    reverse_map, all_variants = _build_branch_indexes()

    matches = difflib.get_close_matches(normalized, all_variants, n=1, cutoff=_CLOSE_MATCH_CUTOFF)
    if matches:
        return _BRANCH_LABELS.get(reverse_map[matches[0]], reverse_map[matches[0]])

    for variant in all_variants:
        if len(variant) > _MIN_VARIANT_LENGTH and variant in normalized:
            return _BRANCH_LABELS.get(reverse_map[variant], reverse_map[variant])

    return None


def normalize_branch(value: str | None) -> str | None:
    """توحيد اسم الشعبة: تطابق حرفي ⇒ أقرب مطابقة ⇒ احتواء ⇒ الأصل."""
    if not value:
        return None

    normalized = value.strip().lower()
    for key, variants in BRANCH_MAP.items():
        if normalized in variants:
            return _BRANCH_LABELS.get(key, key)

    return _resolve_branch_by_value(normalized) or value


# ---------------------------------------------------------------------------
# 3) بناء سياق الاستعلام الكامل
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
