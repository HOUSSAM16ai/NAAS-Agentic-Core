"""شرائح البحث للرسم الموحَّد (D-262).

نمط D-164/D-168/D-261: شريحة نقية تحمّل عقد البحث عند توفر التبعيات
وتعيد بدائل آمنة (passthrough) عند غيابها — مطابقة حرفية لسلوك
`_load_search_nodes` الأصلي في القشرة.
"""

from __future__ import annotations


class _PassthroughNode:
    """عقدة بديلة آمنة — تعيد الحالة كما هي (D-262 · مطابقة حرفية للأصل)."""

    def __call__(self, state: dict) -> dict:
        return state


def load_search_nodes() -> tuple[type, type, type, type, type]:
    """يحمّل عقد البحث عند توفر التبعيات ويعيد بدائل آمنة عند غيابها.

    السلوك مطابقٌ حرفًا لـ`_load_search_nodes` الأصلي (D-262): نفس ترتيب
    الخماسية (QueryAnalyzerNode · InternalRetrieverNode · RerankerNode ·
    WebSearchFallbackNode · SynthesizerNode) ونفس البديل الآمن.
    """
    try:
        from microservices.orchestrator_service.src.services.overmind.graph.search import (
            InternalRetrieverNode,
            QueryAnalyzerNode,
            RerankerNode,
            SynthesizerNode,
            WebSearchFallbackNode,
        )

        return (
            QueryAnalyzerNode,
            InternalRetrieverNode,
            RerankerNode,
            WebSearchFallbackNode,
            SynthesizerNode,
        )
    except Exception:
        return (
            _PassthroughNode,
            _PassthroughNode,
            _PassthroughNode,
            _PassthroughNode,
            _PassthroughNode,
        )
