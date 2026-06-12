"""تحقق يدوي لمنطق SuperSearchOrchestrator (بـ mocks كاملة — بلا شبكة).

D-105 (ISS-113): كل حقن sys.modules هنا مُسيَّج بـ ``patch.dict`` يستعيد الحالة
الأصلية عند الخروج. الحقن العاري على مستوى الوحدة كان يسمّم جلسة pytest كاملة
(mock.Document يتسرب لكل مستورد لاحق) — ممنوع نهائياً (بوابة check_test_hygiene).
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path
sys.path.append(os.path.join(os.getcwd(), "microservices/research_agent/src"))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# Define dummy classes for isinstance checks
class MockTavilyClient:
    pass


class MockFirecrawlApp:
    pass


def _build_mock_modules() -> dict:
    """يبني خريطة الموديولات الوهمية — تُحقن فقط داخل سياق patch.dict."""
    mock_logger = MagicMock()

    def log_side_effect(msg, *args):
        print(f"[LOG] {msg} {args}")

    mock_logger.info.side_effect = log_side_effect
    mock_logger.warning.side_effect = log_side_effect
    mock_logger.error.side_effect = log_side_effect

    mock_modules = {
        name: MagicMock()
        for name in (
            "langchain_community.utilities",
            "langchain_core.prompts",
            "langchain_openai",
            "bs4",
            "microservices.research_agent.src.logging",
            "flupy",
            "llama_index",
            "llama_index.core",
            "llama_index.core.schema",
            "llama_index.core.retrievers",
            "llama_index.core.indices",
            "llama_index.core.vector_stores",
            "llama_index.embeddings",
            "llama_index.embeddings.huggingface",
            "llama_index.retrievers.bm25",
            "llama_index.vector_stores",
            "llama_index.vector_stores.supabase",
        )
    }

    # tavily/firecrawl يحتاجان classes حقيقية لفحوصات isinstance
    mock_tavily = MagicMock()
    mock_tavily.TavilyClient = MockTavilyClient
    mock_modules["tavily"] = mock_tavily

    mock_firecrawl = MagicMock()
    mock_firecrawl.FirecrawlApp = MockFirecrawlApp
    mock_modules["firecrawl"] = mock_firecrawl

    mock_modules["microservices.research_agent.src.logging"].get_logger.return_value = mock_logger
    return mock_modules


async def test_search_pipeline():
    print("Testing SuperSearchOrchestrator Logic (Mocked)...")

    # الحقن مُسيَّج: patch.dict يلتقط snapshot لـ sys.modules ويستعيدها كاملة عند
    # الخروج — أي استيراد يحدث داخل النافذة (بما فيه super_search) يُمحى أثره.
    with patch.dict(sys.modules, _build_mock_modules()):
        # إخلاء وحدات search_engine المخبأة (إن وُجدت) ليُعاد استيرادها تحت الـ mocks؛
        # patch.dict يعيد النسخ الحقيقية المخبأة عند الخروج.
        for cached in [
            m for m in sys.modules if m.startswith("microservices.research_agent.src.search_engine")
        ]:
            sys.modules.pop(cached, None)

        from microservices.research_agent.src.search_engine.super_search import (
            ResearchPlan,
            SuperSearchOrchestrator,
        )

        # Mock components
        mock_llm = AsyncMock()
        mock_search = MagicMock()
        # Explicitly delete 'results' so hasattr(mock_search, 'results') is False
        # This ensures the orchestrator doesn't treat it as DuckDuckGo wrapper
        del mock_search.results

        mock_scraper = MagicMock()

        # Configure Scraper to be Async-friendly
        mock_scraper.scrape = AsyncMock()
        long_content = "A" * 200 + " Synthesized Answer Source Content"
        mock_scraper.scrape.return_value = long_content

        # Configure Search to be Async-friendly
        mock_search.search = AsyncMock()
        mock_search.search.return_value = [{"url": "http://test.com", "content": "test content"}]

        # Setup orchestrator
        orchestrator = SuperSearchOrchestrator(
            llm=mock_llm, search_tool=mock_search, web_scraper=mock_scraper
        )

        # 1. Test Planning
        print("- Testing Planning Phase...")
        orchestrator._create_plan = AsyncMock(
            return_value=ResearchPlan(sub_queries=["q1", "q2"], required_info=["info1"])
        )

        # 2. Test Execution
        print("- Testing Execution...")
        mock_response = MagicMock()
        mock_response.content = "Synthesized Answer"
        mock_llm.ainvoke.return_value = mock_response

        result = await orchestrator.execute("test query")

        print(f"Result: {result}")
        assert "Synthesized Answer" in result
        print("✅ SuperSearchOrchestrator Pipeline Verified.")


if __name__ == "__main__":
    asyncio.run(test_search_pipeline())
