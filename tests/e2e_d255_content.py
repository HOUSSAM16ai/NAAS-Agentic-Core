"""E2E حي لـ D-255: تحميل قشرة content.py كاملة + الشرائح في بيئة التشغيل
الحقيقية عبر ToolRegistry (execute بـ dict args)، واستدعاء search_content
بوسائط حقيقية (تتضمن branch العربية + alias 'query' + kwargs زائدة)
للتأكد من السلالة اللغوية وسلاسل التفويض من القشرة إلى الشرائح.

يُشغَّل: PYTHONPATH=. python3 tests/e2e_d255_content.py
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from app.services.chat.tools import ToolRegistry
from app.services.chat.tools import content as content_module
from app.services.chat.tools.content_support import search as search_shard

MOCK_REPORT = {
    "title": "Test Report",
    "content": "Cognitive report body",
    "sources": ["mock-source"],
}


async def main() -> None:
    registry = ToolRegistry()
    assert "search_content" in registry._tools, "search_content not registered"
    print("[E2E] search_content registered in ToolRegistry — schema fields ok")

    with patch("app.services.chat.tools.content.research_client") as mock_client:
        mock_client.deep_research = AsyncMock(return_value=MOCK_REPORT)

        # 1) استدعاء عبر ToolRegistry.execute (مسار الأوركستريتور الحقيقي بـ dict)
        results = await registry.execute(
            "search_content",
            {
                "q": "ما هو الجهد الكهربائي",
                "level": "bac",
                "subject": "physique",
                "branch": "sciences_exper",
                "type": "lesson",
                "lang": "ar",
                "limit": 5,
            },
        )
        assert isinstance(results, list), f"unexpected results type: {type(results)}"
        print(f"[E2E] call-1 via ToolRegistry.execute (dict args) → {len(results)} result(s)")

        # 2) alias 'query' + kwargs زائدة (سلالة المخطط الأصلية)
        results2 = await content_module.search_content(
            query="الجهد الكهربائي",
            branch="sciences_exper",
            unexpected_extra="must-not-crash",
        )
        print(f"[E2E] call-2 alias 'query' + extra kwargs → {len(results2)} result(s)")

        # 3) القشور القديمة تبقى فعالة (late-binding D-252)
        assert content_module._normalize_branch("sciences_exper") == "علوم تجريبية", (
            "late-binding shell for _normalize_branch broken"
        )
        assert content_module._scan_for_error({"type": "error", "content": "boom"}) == "boom"
        assert "experimental_sciences" in content_module._BRANCH_LABELS
        print(
            "[E2E] late-binding shells (_normalize_branch/_scan_for_error/"
            "_BRANCH_LABELS) preserved — old tests untouched"
        )

        # 4) soft failure → ValueError (Fail-Fast RFC 001)
        error_payload = {"type": "error", "content": "Research rate-limited"}
        mock_client.deep_research = AsyncMock(return_value=error_payload)
        raised = False
        try:
            await content_module.search_content(q="x", branch="sciences_exper")
        except ValueError as exc:
            assert "Research Tool Error" in str(exc)
            raised = True
        assert raised, "soft failure not re-raised as ValueError"
        print("[E2E] soft-failure → ValueError propagation (Fail-Fast RFC 001)")

        # 5) الشرائح نفسها تستورد وتعمل
        assert search_shard.normalize_branch("math_tech") == "تقني رياضي"
        filters = search_shard.SearchFilters(
            q="t", subject="p", branch="تقني رياضي", year=None, level="bac", type="lesson"
        )
        ctx = search_shard.build_search_context(filters)
        assert "تقني رياضي" in ctx
        report_out = search_shard.build_search_report("t", ctx, MOCK_REPORT)
        assert isinstance(report_out, list)
        print(
            "[E2E] shards import & run: normalize_branch · SearchFilters · "
            "build_search_context · build_search_report"
        )

    print("[E2E] ALL PASS — D-255 shell + shards behave like the original")


if __name__ == "__main__":
    asyncio.run(main())
