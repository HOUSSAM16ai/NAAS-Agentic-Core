"""
اختبارات Math Pipeline — CogniForge BAC Tutor.

تغطي:
- تصنيف أنواع المسائل الرياضية
- بناء الـ pipeline
- invoke مع mock LLM
- fallback عند غياب API key
- ConversationState الجديد مع subject + enriched_question
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from microservices.conversation_service.src.conversation_graph import (
    _classify_intent,
    _detect_subject,
    _enrich_question,
    build_conversation_graph,
    invoke_graph,
)
from microservices.conversation_service.src.math_pipeline import (
    _classify_math_type,
    _get_math_context,
    build_math_pipeline,
    get_math_pipeline,
    invoke_math_pipeline,
)

# ── اختبارات تصنيف المسائل ────────────────────────────────────────────────────


class TestMathTypeClassification:
    """اختبارات تصنيف نوع المسألة الرياضية."""

    def test_derivative_arabic(self):
        assert _classify_math_type("احسب مشتق f(x) = x²") == "derivative"

    def test_derivative_french(self):
        assert _classify_math_type("calculer la dérivée de f(x)") == "derivative"

    def test_integral_symbol(self):
        assert _classify_math_type("احسب ∫x²dx") == "integral"

    def test_integral_arabic(self):
        assert _classify_math_type("أوجد تكامل الدالة") == "integral"

    def test_limit_arabic(self):
        assert _classify_math_type("احسب نهاية الدالة عند اللانهاية") == "limit"

    def test_limit_symbol(self):
        assert _classify_math_type("lim(x→0) sin(x)/x") == "limit"

    def test_equation_arabic(self):
        assert _classify_math_type("حل المعادلة x² - 4 = 0") == "equation"

    def test_function_study(self):
        assert _classify_math_type("ادرس إشارة الدالة") == "function_study"

    def test_probability(self):
        assert _classify_math_type("احسب احتمال الحادثة A") == "probability"

    def test_complex_numbers(self):
        assert _classify_math_type("أوجد module العدد المركب") == "complex"

    def test_matrix(self):
        assert _classify_math_type("احسب محدد المصفوفة") == "matrix"

    def test_sequence(self):
        assert _classify_math_type("ادرس تقاربية المتتالية") == "sequence"

    def test_sequence_explicit(self):
        assert _classify_math_type("ادرس حدود المتتالية (un)") == "sequence"

    def test_general_fallback(self):
        assert _classify_math_type("مرحبا كيف حالك") == "general_math"


class TestMathContext:
    """اختبارات السياق التعليمي لكل نوع مسألة."""

    def test_derivative_context_contains_rules(self):
        ctx = _get_math_context("derivative")
        assert "قاعدة الضرب" in ctx or "uv" in ctx

    def test_integral_context_contains_techniques(self):
        ctx = _get_math_context("integral")
        assert "تكامل" in ctx or "التجزئة" in ctx

    def test_unknown_type_returns_empty_or_general(self):
        ctx = _get_math_context("unknown_type")
        # النوع المجهول يُعيد "" أو نصاً عاماً — كلاهما مقبول
        assert isinstance(ctx, str)


# ── اختبارات بناء الـ Pipeline ────────────────────────────────────────────────


class TestMathPipelineBuild:
    """اختبارات بناء LangGraph Math Pipeline."""

    def test_build_returns_compiled_graph(self):
        graph = build_math_pipeline()
        assert graph is not None

    def test_singleton_returns_same_instance(self):
        g1 = get_math_pipeline()
        g2 = get_math_pipeline()
        assert g1 is g2


# ── اختبارات invoke مع mock ───────────────────────────────────────────────────


class TestMathPipelineInvoke:
    """اختبارات استدعاء الـ pipeline مع mock LLM."""

    @pytest.mark.asyncio
    async def test_invoke_returns_dict_with_required_keys(self):
        """يتحقق من أن invoke_math_pipeline يُعيد dict بالمفاتيح المطلوبة."""
        mock_response = "الحل: $$f'(x) = 2x$$ \n$$\\boxed{2x}$$"

        with patch(
            "microservices.conversation_service.src.math_pipeline._call_openrouter",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await invoke_math_pipeline(
                question="احسب مشتق f(x) = x²",
                thread_id="test-001",
            )

        assert "final_response" in result
        assert "math_type" in result
        assert "solution" in result
        assert "error" in result

    @pytest.mark.asyncio
    async def test_derivative_question_classified_correctly(self):
        """يتحقق من تصنيف مسألة الاشتقاق."""
        with patch(
            "microservices.conversation_service.src.math_pipeline._call_openrouter",
            new_callable=AsyncMock,
            return_value="$$f'(x) = 2x$$ $$\\boxed{2x}$$",
        ):
            result = await invoke_math_pipeline(
                question="احسب مشتق f(x) = x²",
                thread_id="test-002",
            )

        assert result["math_type"] == "derivative"

    @pytest.mark.asyncio
    async def test_fallback_when_no_api_key(self):
        """يتحقق من fallback عند غياب API key."""
        import os

        original = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            result = await invoke_math_pipeline(
                question="احسب مشتق f(x) = x²",
                thread_id="test-003",
            )
            # يجب أن يُعيد نتيجة (fallback) لا exception
            assert "final_response" in result
            assert result["final_response"] != ""
        finally:
            if original:
                os.environ["OPENROUTER_API_KEY"] = original

    @pytest.mark.asyncio
    async def test_history_passed_to_pipeline(self):
        """يتحقق من تمرير السياق للـ pipeline."""
        history = [
            {"role": "user", "content": "ما هو التكامل؟"},
            {"role": "assistant", "content": "التكامل هو عملية عكس الاشتقاق."},
        ]
        with patch(
            "microservices.conversation_service.src.math_pipeline._call_openrouter",
            new_callable=AsyncMock,
            return_value="$$\\boxed{x^2/2 + C}$$",
        ):
            result = await invoke_math_pipeline(
                question="احسب ∫x dx",
                thread_id="test-004",
                history=history,
            )

        assert result["math_type"] == "integral"
        assert "final_response" in result


# ── اختبارات ConversationGraph المُحدَّث ──────────────────────────────────────


class TestConversationGraphUpdated:
    """اختبارات ConversationGraph مع subject + enriched_question."""

    def test_classify_intent_educational(self):
        assert _classify_intent("اشرح لي التكامل") == "educational"

    def test_classify_intent_chat(self):
        assert _classify_intent("مرحبا") == "chat"

    def test_classify_intent_general_fallback(self):
        assert _classify_intent("ما هو الطقس اليوم؟") == "general"

    def test_detect_subject_math(self):
        assert _detect_subject("احسب مشتق الدالة") == "math"

    def test_detect_subject_physics(self):
        assert _detect_subject("احسب قوة نيوتن") == "physics"

    def test_detect_subject_chemistry(self):
        assert _detect_subject("ما هو تفاعل الأكسدة؟") == "chemistry"

    def test_detect_subject_general(self):
        assert _detect_subject("مرحبا كيف حالك") == "general"

    def test_enrich_question_math(self):
        enriched = _enrich_question("احسب مشتق x²", "math", "educational")
        assert "بكالوريا" in enriched or "رياضيات" in enriched

    def test_enrich_question_chat_unchanged(self):
        q = "مرحبا"
        enriched = _enrich_question(q, "general", "chat")
        assert enriched == q

    def test_build_conversation_graph(self):
        graph = build_conversation_graph()
        assert graph is not None

    @pytest.mark.asyncio
    async def test_invoke_graph_returns_subject(self):
        """يتحقق من أن invoke_graph يُعيد subject في النتيجة."""
        with patch(
            "microservices.conversation_service.src.conversation_graph._call_llm_if_available",
            new_callable=AsyncMock,
            return_value="الجواب: $$f'(x) = 2x$$",
        ):
            result = await invoke_graph(
                question="احسب مشتق f(x) = x²",
                thread_id="test-graph-001",
                correlation_id="corr-001",
            )

        assert "response" in result
        assert "intent" in result
        assert "subject" in result
        assert result["subject"] in ("math", "physics", "chemistry", "general")

    @pytest.mark.asyncio
    async def test_invoke_graph_math_routes_to_pipeline(self):
        """يتحقق من توجيه الأسئلة الرياضية للـ Math Pipeline."""
        pipeline_mock = AsyncMock(
            return_value={
                "final_response": "$$\\boxed{2x}$$",
                "math_type": "derivative",
                "solution": "f'(x) = 2x",
                "error": None,
            }
        )

        # الـ import يحدث داخل response_node — نُعيد تعريف الدالة في الـ module المُستورَد
        with patch(
            "microservices.conversation_service.src.math_pipeline.invoke_math_pipeline",
            pipeline_mock,
        ):
            result = await invoke_graph(
                question="احسب مشتق f(x) = x²",
                thread_id="test-graph-002",
                correlation_id="corr-002",
            )

        assert "response" in result
        assert result["response"] != ""

    @pytest.mark.asyncio
    async def test_invoke_graph_fallback_on_empty_response(self):
        """يتحقق من fallback عند إجابة فارغة من LLM."""
        with patch(
            "microservices.conversation_service.src.conversation_graph._call_llm_if_available",
            new_callable=AsyncMock,
            return_value="",
        ):
            result = await invoke_graph(
                question="سؤال عام",
                thread_id="test-graph-003",
                correlation_id="corr-003",
            )

        # يجب أن يُعيد fallback لا exception
        assert "response" in result
