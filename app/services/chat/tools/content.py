"""قشرة استقبال أدوات المحتوى (D-255).

فُكِّك hotspot هذا الملف (173 سطرًا · `search_content` C(14) · 112 سطرًا ·
تردد تغيير 40) إلى قشرة استقبال + حزمة شرائح `content_support/` (نمط D-252):

- القشرة هنا: استقبال الوسائط · التحقق من المخطط (Fail-Fast — RFC 001) ·
  التفويض النصي الحرفي إلى الشرائح — **صفر منطق دور**.
- الشرائح في `content_support/search.py` تحمل: توحيد الشعبة · كشف «الفشل
  اللين» (Error-as-Data) · بناء سياق الاستعلام · صياغة التقرير.

**صفر تغيير سلوكي على المستوى العام**: كل التوقيعات العامة (`search_content`
بتسعة الوسائط + `**kwargs`) والأسماء الخاصة القديمة (`_normalize_branch` ·
`_scan_for_error` · `_BRANCH_LABELS`) باقية حرفيًا كقشور تفويض ليبقى كل
اختبار وmonkeypatch فعالًا (قانون late-binding من D-252).
"""

import dataclasses

from app.core.logging import get_logger
from app.infrastructure.clients.research_client import research_client
from app.services.chat.tools import content_support as _content_support_shard
from app.services.chat.tools.schemas import SearchContentSchema

logger = get_logger("content-tools")


@dataclasses.dataclass(frozen=True)
class ContentSearchArgs:
    """وسائط البحث التسعة المجمّعة في كائن سياق واحد (D-255 — يقتل PLR0917
    مع الحفاظ على التوقيع العام `search_content` كما هو — نمط D-249).

    تبقى جميع الحقول public بنفس الأسماء الأصلية حتى لا يُكسر أي استدعاء
    مباشر أو monkeypatch على الوسائط الأصلية.
    """

    q: str | None = None
    level: str | None = None
    subject: str | None = None
    branch: str | None = None
    set_name: str | None = None
    year: int | None = None
    type: str | None = None
    lang: str | None = None
    limit: int = 10


# ---------------------------------------------------------------------------
# Late-binding للأسماء القديمة (D-252 · صفر تغيير سلوكي):
# الاختبارات القائمة (tests/unit/test_content_branch_logic.py ·
# test_content_tool_logic.py) تستورد `_normalize_branch` و`_scan_for_error`
# و`_BRANCH_LABELS` من هذه القشرة — تبقى قشور تفويض حرفية ليبقى كل
# monkeypatch واختبار على الأسماء القديمة فعالًا.
# ---------------------------------------------------------------------------

normalize_branch = _content_support_shard.normalize_branch


def _normalize_branch(value: str | None) -> str | None:
    """قشرة late-binding للأصل المفكك (لا تُلمس — تحفظ الاختبارات القديمة)."""
    return normalize_branch(value)


def _scan_for_error(data: object) -> str | None:
    """قشرة late-binding للأصل المفكك (لا تُلمس — تحفظ الاختبارات القديمة)."""
    return _content_support_shard.scan_for_error(data)


_BRANCH_LABELS: dict[str, str] = {
    "experimental_sciences": "علوم تجريبية",
    "math_tech": "تقني رياضي",
    "mathematics": "رياضيات",
    "foreign_languages": "لغات أجنبية",
    "literature_philosophy": "آداب وفلسفة",
}


async def get_curriculum_structure(
    level: str | None = None,
) -> dict[str, object]:
    """Get curriculum structure for a level."""
    try:
        return await research_client.get_curriculum_structure(level)
    except Exception as e:
        logger.error(f"Failed to fetch curriculum structure: {e}")
        return {}


# ---------------------------------------------------------------------------
# قلب الأدوات الناقلة (Cognitive Research Infrastructure)
# ---------------------------------------------------------------------------


async def _execute_search(validated: SearchContentSchema) -> list[dict[str, object]]:
    """قلب التنفيذ النصي (Layers B..D — السلالة الأصلية حرفًا).

    Branch normalization + query context + deep research + error scanning +
    report building — كلها شرائح نقية في content_support:
    """
    # Normalize branch if provided (التفويض للشريحة — نفس المنطق حرفًا)
    normalized_branch = (
        _content_support_shard.normalize_branch(validated.branch)
        if validated.branch
        else validated.branch
    )

    # Build query context (التفويض للشريحة — فلاتر معلنة)
    full_query = _content_support_shard.build_search_context(
        _content_support_shard.SearchFilters(
            q=validated.q,
            subject=validated.subject,
            branch=normalized_branch,
            year=validated.year,
            level=validated.level,
            type=validated.type,
        )
    )

    # Direct execution to enforce Fail-Fast (Fixes Root Cause D)
    # Exceptions propagate to TaskExecutor -> Mission Status FAILED
    report = await research_client.deep_research(full_query)

    # Scan for nested error payloads (Anti-Pattern: Error-as-Data / Soft Failures)
    error_msg = _content_support_shard.scan_for_error(report)
    if error_msg:
        raise ValueError(f"Research Tool Error: {error_msg}")

    return _content_support_shard.build_search_report(validated.q, full_query, report)


async def search_content(
    q: str | None = None,
    level: str | None = None,
    subject: str | None = None,
    branch: str | None = None,
    set_name: str | None = None,
    year: int | None = None,
    type: str | None = None,
    lang: str | None = None,
    limit: int = 10,
    **kwargs,
) -> list[dict[str, object]]:
    """
    Cognitive Research Infrastructure (CRI).
    Advanced deep-research engine. Use this for ALL information retrieval.
    It performs multi-step reasoning, scraping, and fact-checking using
    autonomous agents (Tavily/Firecrawl).
    Returns a detailed research report.
    """
    return await _search_pipeline(
        ContentSearchArgs(
            q=q,
            level=level,
            subject=subject,
            branch=branch,
            set_name=set_name,
            year=year,
            type=type,
            lang=lang,
            limit=limit,
        ),
        kwargs,
    )


async def _search_pipeline(args: ContentSearchArgs, kwargs: dict) -> list[dict[str, object]]:
    """قشرة Layers A..D (السلالة الأصلية حرفًا) — تفويضٌ نصي للشريحة.

    - Layer A: Schema Adapter & Validation (Fail-Fast — RFC 001)
    - Layers B..D: Branch · Context · Execution · Error-scan · Report
    """
    # --- Layer A: Schema Adapter & Validation (نفس السلالة الأصلية حرفًا) ---
    try:
        explicit_args = dataclasses.asdict(args)
        filtered_args = {k: v for k, v in explicit_args.items() if v is not None}
        raw_args = {**filtered_args, **kwargs}

        # Log unexpected args for debugging but don't crash
        known_keys = set(explicit_args.keys()) | {"query"}
        unexpected = set(raw_args.keys()) - known_keys
        if unexpected:
            logger.warning(f"search_content received unexpected args (ignored): {unexpected}")

        # Validate against the Pydantic Schema (Adapts aliases like 'query' -> 'q')
        validated_data = SearchContentSchema(**raw_args)

    except Exception as e:
        logger.error(f"Schema Validation Failed in search_content: {e}")
        # Strict Fail-Fast Policy (RFC 001)
        # We must propagate exceptions to the TaskExecutor to ensure honest outcome reporting.
        raise

    # --- Layers B..D: Branch · Context · Execution · Error-scan · Report
    # (نفس السلالة الأصلية حرفًا — كل الدوال هنا نصية تفويضٌ للشريحة) ---
    return await _execute_search(validated_data)


async def get_content_raw(
    exercise_id: str, include_solution: bool = False
) -> dict[str, object] | None:
    """Get raw content for an exercise."""
    try:
        return await research_client.get_content_raw(exercise_id, include_solution=include_solution)
    except Exception as e:
        logger.error(f"Failed to fetch raw content: {e}")
        return None


async def get_solution_raw(exercise_id: str) -> dict[str, object] | None:
    """Get solution for an exercise."""
    try:
        raw = await research_client.get_content_raw(exercise_id, include_solution=True)
        if not raw:
            return None
        return {"exercise_id": exercise_id, "solution_md": raw.get("solution")}
    except Exception as e:
        logger.error(f"Failed to fetch solution: {e}")
        return None


def register_content_tools(tool_registry) -> None:
    """Register all content tools with the given registry."""
    tool_registry.register_tool(
        name="search_content",
        description="Cognitive Research Infrastructure (CRI): Advanced deep-research engine",
        schema=SearchContentSchema,
        fn=search_content,
    )
    tool_registry.register_tool(
        name="get_curriculum_structure",
        description="Get curriculum structure",
        fn=get_curriculum_structure,
    )
    tool_registry.register_tool(
        name="get_content_raw",
        description="Get raw content for an exercise",
        fn=get_content_raw,
    )
    tool_registry.register_tool(
        name="get_solution_raw",
        description="Get solution for an exercise",
        fn=get_solution_raw,
    )
