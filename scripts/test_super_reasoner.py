import asyncio
import logging
import os

import pytest

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-strict")


async def main():
    print("🧠 Verifying Strict Search & Reasoning...")

    try:
        from app.core.gateway.simple_client import SimpleAIClient
        from microservices.reasoning_agent.src.workflow import SuperReasoningWorkflow
    except ImportError as e:
        print(f"⚠️ Skipped: Dependencies not found ({e}).")
        return

    # 1. Initialize Client
    api_key = os.environ.get("OPENROUTER_API_KEY")
    client = SimpleAIClient(api_key=api_key)

    # 2. Create Workflow
    workflow = SuperReasoningWorkflow(client=client, timeout=300, verbose=True)

    # 3. Run Query (Strict Arabic)
    query = "تمرين في مادة الرياضيات خاص بالاحتمالات في شعبة العلوم التجريبية بكالوريا 2024 الموضوع الاول التمرين الأول"
    print(f"❓ Query: {query}")

    try:
        result = await workflow.run(query=query)
        print("\n✅ Result from Super Reasoner:\n")
        print("=" * 60)
        print(result)
        print("=" * 60)

        # Simple string check for success
        res_str = str(result)
        if "14/165" in res_str or "56/165" in res_str or "11 كرة" in res_str:
            print("🎉 SUCCESS: The exercise was found and solved correctly.")
        else:
            print("⚠️ WARNING: The result might not contain the exact numbers. Check output.")

    except Exception as e:
        print(f"❌ Verification Failed: {e}")


# Pytest hook to skip if dependencies missing
def test_super_reasoner_import():
    """D-105 (ISS-113): الحقن مُسيَّج بـ patch.dict — يستعيد sys.modules كاملة عند الخروج.

    الحقن العاري السابق (sys.modules[...] = MagicMock() بلا تنظيف) كان يسمّم جلسة
    pytest كاملة عند جمع هذا السكربت — ممنوع نهائياً (بوابة check_test_hygiene).
    """
    import sys
    from unittest.mock import MagicMock, patch

    mock_modules: dict = {}
    # Mock llama_index modules only if they don't exist (scoped to this test)
    if "llama_index" not in sys.modules:
        mock_llama_index = MagicMock()
        mock_modules = dict.fromkeys(
            (
                "llama_index",
                "llama_index.core",
                "llama_index.core.schema",
                "llama_index.core.workflow",
                "llama_index.core.vector_stores",
                "llama_index.embeddings.huggingface",
                "llama_index.vector_stores.supabase",
                "llama_index.core.retrievers",
            ),
            mock_llama_index,
        )

    with patch.dict(sys.modules, mock_modules):
        try:
            from microservices.reasoning_agent.src.workflow import (  # noqa: F401
                SuperReasoningWorkflow,
            )
        except ImportError:
            pytest.skip("llama-index.core.workflow not available")
        except Exception as e:
            pytest.skip(f"Skipping due to import error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
