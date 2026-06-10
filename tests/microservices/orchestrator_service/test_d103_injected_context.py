"""D-103 — اختبارات حقن محتوى التمرين في الرسم + استشارة reasoning-agent.

Change A: حقن ``exercise_content`` من الـ monolith ⇒ الرسم يتجاوز retriever-ه
كلياً ويستخدم المحتوى المحقون كمصدر وحيد (يُحيّد سبب منع D-052 بالبناء).

Change B: ``SynthesizerNode`` يستشير reasoning-agent للأسئلة الرياضية المعقدة —
fail-open مطلق: أي خطأ/مهلة/تعطيل ⇒ "" والتوليف يتابع.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
GRAPH_MAIN = (
    REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/graph/main.py"
).read_text(encoding="utf-8")
GRAPH_SEARCH = (
    REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/graph/search.py"
).read_text(encoding="utf-8")
ROUTES_SRC = (REPO_ROOT / "microservices/orchestrator_service/src/api/routes.py").read_text(
    encoding="utf-8"
)


# ─────────────────────────────────────────────────────────────────────────────
# Change A — البنية: الحقل والحُرّاس موجودون في المصدر
# ─────────────────────────────────────────────────────────────────────────────
class TestInjectedContextStructure:
    def test_agent_state_has_exercise_content_field(self):
        assert "exercise_content: str" in GRAPH_MAIN, (
            "D-103 broken: AgentState lost the exercise_content field"
        )

    def test_supervisor_forces_educational_on_injection(self):
        """SupervisorNode يفرض educational حتمياً قبل أي DSPy عند الحقن."""
        sup_start = GRAPH_MAIN.index("class SupervisorNode")
        sup_end = GRAPH_MAIN.index("class ChatFallbackSignature")
        sup_src = GRAPH_MAIN[sup_start:sup_end]
        guard_pos = sup_src.index('state.get("exercise_content")')
        dspy_pos = sup_src.index("self.dspy_classifier, history=")
        assert guard_pos < dspy_pos, "injection guard must run BEFORE the DSPy classifier"
        assert (
            '"intent"] = "educational"'
            in sup_src.replace("updates[", '"intent"] = ').replace(
                '"intent"] = "intent"] = ', '"intent"] = '
            )
            or 'updates["intent"] = "educational"' in sup_src
        )

    def test_query_rewriter_skips_on_injection(self):
        qr_start = GRAPH_MAIN.index("class QueryRewriterNode")
        qr_end = GRAPH_MAIN.index("class ToolExecutorNode")
        assert 'state.get("exercise_content")' in GRAPH_MAIN[qr_start:qr_end]

    def test_query_analyzer_skips_on_injection(self):
        qa_start = GRAPH_SEARCH.index("class QueryAnalyzerNode")
        qa_end = GRAPH_SEARCH.index("class InternalRetrieverNode")
        assert 'state.get("exercise_content")' in GRAPH_SEARCH[qa_start:qa_end]

    def test_retriever_bypasses_semantic_search_on_injection(self):
        """الحارس يجب أن يسبق أي استدعاء لـ research_client."""
        rt_start = GRAPH_SEARCH.index("class InternalRetrieverNode")
        rt_end = GRAPH_SEARCH.index("class RerankerNode")
        rt_src = GRAPH_SEARCH[rt_start:rt_end]
        guard_pos = rt_src.index('state.get("exercise_content")')
        client_pos = rt_src.index("research_client.semantic_search")
        assert guard_pos < client_pos, "injection guard must precede research_client call"
        assert "محتوى التمرين المرفق" in rt_src

    def test_reranker_passthrough_on_injection(self):
        rr_start = GRAPH_SEARCH.index("class RerankerNode")
        rr_end = GRAPH_SEARCH.index("class WebSearchFallbackNode")
        assert 'state.get("exercise_content")' in GRAPH_SEARCH[rr_start:rr_end]

    def test_routes_declare_and_plumb_exercise_content(self):
        assert "exercise_content: str" in ROUTES_SRC, "ChatRunContext lost exercise_content"
        assert "_extract_injected_exercise" in ROUTES_SRC
        # موضعا التوصيل: HTTP (_run_chat_langgraph) + WS (_runner)
        assert ROUTES_SRC.count('inputs["exercise_content"]') >= 2, (
            "exercise_content must be plumbed into graph inputs on BOTH HTTP and WS paths"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Change A — سلوك العقد مع state محقون (بدون شبكة / بدون LLM)
# ─────────────────────────────────────────────────────────────────────────────
class TestInjectedContextBehavior:
    @pytest.fixture()
    def injected_state(self) -> dict:
        return {
            "messages": [],
            "query": "اشرح السؤال الأول من التمرين",
            "exercise_content": "## تمرين الدوال 2016\ng(x) = 1 + (x^2+x-1)e^{-x} ...",
        }

    def test_supervisor_returns_educational(self, injected_state):
        from microservices.orchestrator_service.src.services.overmind.graph.main import (
            SupervisorNode,
        )

        result = asyncio.run(SupervisorNode()(injected_state))
        assert result["intent"] == "educational"

    def test_retriever_returns_injected_doc_only(self, injected_state):
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            InternalRetrieverNode,
        )

        result = asyncio.run(InternalRetrieverNode()(injected_state))
        docs = result["retrieved_docs"]
        assert len(docs) == 1
        assert "تمرين الدوال 2016" in docs[0].text
        assert docs[0].metadata["source"] == "محتوى التمرين المرفق"

    def test_reranker_passthrough(self, injected_state):
        from llama_index.core.schema import Document as LlamaDocument

        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            RerankerNode,
        )

        doc = LlamaDocument(text="x", metadata={"source": "محتوى التمرين المرفق", "score": 1.0})
        injected_state["retrieved_docs"] = [doc]
        result = asyncio.run(RerankerNode()(injected_state))
        assert result["reranked_docs"] == [doc]

    def test_query_analyzer_returns_plain_filters(self, injected_state):
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            QueryAnalyzerNode,
        )

        result = asyncio.run(QueryAnalyzerNode()(injected_state))
        filters = result["filters"]
        assert filters.question == injected_state["query"]
        assert filters.year is None

    def test_extract_injected_exercise_validation(self):
        from microservices.orchestrator_service.src.api.routes import (
            _INJECTED_EXERCISE_MAX_CHARS,
            _extract_injected_exercise,
        )

        assert _extract_injected_exercise(None) == ""
        assert _extract_injected_exercise({}) == ""
        assert _extract_injected_exercise({"exercise_content": 42}) == ""
        assert _extract_injected_exercise({"exercise_content": "  نص  "}) == "نص"
        long = "x" * (_INJECTED_EXERCISE_MAX_CHARS + 100)
        assert len(_extract_injected_exercise({"exercise_content": long})) == (
            _INJECTED_EXERCISE_MAX_CHARS
        )


# ─────────────────────────────────────────────────────────────────────────────
# Change B — استشارة reasoning-agent (حتمية + fail-open)
# ─────────────────────────────────────────────────────────────────────────────
class TestReasoningConsult:
    def test_complex_math_detector_positive(self):
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            _is_complex_math_query,
        )

        for q in (
            "احسب تكامل x ln(x) بالتجزئة",
            "ادرس الدالة f(x) = (x^2-1)/(x+2) واشرح تغيراتها",
            "برهن أن المتتالية متقاربة",
            "ما نهاية sin(2x)/x عندما x تؤول إلى الصفر؟",
            "حل المعادلة في مجموعة الأعداد المركبة z^2 + z + 1 = 0",
        ):
            assert _is_complex_math_query(q), f"should be complex math: {q}"

    def test_complex_math_detector_negative(self):
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            _is_complex_math_query,
        )

        for q in ("", "مرحبا", "تكامل", "ما هي عاصمة الجزائر؟", "اشرح قانون نيوتن الثاني للحركة"):
            assert not _is_complex_math_query(q), f"should NOT be complex math: {q}"

    def test_consult_disabled_by_flag(self, monkeypatch):
        from microservices.orchestrator_service.src.services.overmind.graph import search

        monkeypatch.setenv("ORCHESTRATOR_REASONING_CONSULT_ENABLED", "0")
        result = asyncio.run(search._consult_reasoning_agent("احسب تكامل x ln(x) بالتجزئة"))
        assert result == ""

    def test_consult_skips_non_math(self, monkeypatch):
        from microservices.orchestrator_service.src.services.overmind.graph import search

        monkeypatch.setenv("ORCHESTRATOR_REASONING_CONSULT_ENABLED", "1")
        result = asyncio.run(search._consult_reasoning_agent("ما هي عاصمة الجزائر؟"))
        assert result == ""

    def test_consult_fail_open_on_client_error(self, monkeypatch):
        """خطأ من reasoning_client ⇒ "" — لا استثناء يتسرّب للتوليف."""
        from microservices.orchestrator_service.src.infrastructure.clients import (
            reasoning_client as rc_module,
        )
        from microservices.orchestrator_service.src.services.overmind.graph import search

        monkeypatch.setenv("ORCHESTRATOR_REASONING_CONSULT_ENABLED", "1")

        async def _boom(query: str) -> dict:
            return {"error": "connection refused"}

        monkeypatch.setattr(rc_module.reasoning_client, "reason_deeply", _boom)
        result = asyncio.run(search._consult_reasoning_agent("احسب تكامل x ln(x) بالتجزئة"))
        assert result == ""

    def test_consult_success_returns_capped_hint(self, monkeypatch):
        from microservices.orchestrator_service.src.infrastructure.clients import (
            reasoning_client as rc_module,
        )
        from microservices.orchestrator_service.src.services.overmind.graph import search

        monkeypatch.setenv("ORCHESTRATOR_REASONING_CONSULT_ENABLED", "1")

        async def _ok(query: str) -> dict:
            return {"answer": "الناتج هو " + "خ" * 5000, "logic_trace": "خطوة 1"}

        monkeypatch.setattr(rc_module.reasoning_client, "reason_deeply", _ok)
        result = asyncio.run(search._consult_reasoning_agent("احسب تكامل x ln(x) بالتجزئة"))
        assert result.startswith("الناتج هو")
        assert len(result) <= search._REASONING_HINT_MAX_CHARS

    def test_consult_timeout_fail_open(self, monkeypatch):
        from microservices.orchestrator_service.src.infrastructure.clients import (
            reasoning_client as rc_module,
        )
        from microservices.orchestrator_service.src.services.overmind.graph import search

        monkeypatch.setenv("ORCHESTRATOR_REASONING_CONSULT_ENABLED", "1")
        monkeypatch.setenv("ORCHESTRATOR_REASONING_CONSULT_TIMEOUT", "1")

        async def _slow(query: str) -> dict:
            await asyncio.sleep(5)
            return {"answer": "متأخر"}

        monkeypatch.setattr(rc_module.reasoning_client, "reason_deeply", _slow)
        result = asyncio.run(search._consult_reasoning_agent("احسب تكامل x ln(x) بالتجزئة"))
        assert result == ""

    def test_weave_reasoning_hint(self):
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            _weave_reasoning_hint,
        )

        assert _weave_reasoning_hint("سؤال", "") == "سؤال"
        woven = _weave_reasoning_hint("سؤال", "تحليل")
        assert woven.startswith("سؤال")
        assert "تحليل استدلالي مساعد" in woven
        assert woven.endswith("تحليل")

    def test_synthesizer_wires_consult_and_metric_exists(self):
        """SynthesizerNode يستدعي الاستشارة + metric له مُصدِر حقيقي (§6.21)."""
        syn_start = GRAPH_SEARCH.index("class SynthesizerNode")
        syn_src = GRAPH_SEARCH[syn_start:]
        assert "_consult_reasoning_agent(query)" in syn_src
        # المواضع الثلاثة للحقن
        assert syn_src.count("_weave_reasoning_hint(") >= 3
        prom_src = (
            REPO_ROOT / "microservices/orchestrator_service/src/core/prom_metrics.py"
        ).read_text(encoding="utf-8")
        assert "cogniforge_reasoning_consult_total" in prom_src
        assert "def record_reasoning_consult" in prom_src
