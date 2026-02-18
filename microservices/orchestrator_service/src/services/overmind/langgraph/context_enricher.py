from __future__ import annotations

from dataclasses import dataclass

from microservices.orchestrator_service.src.services.overmind.langgraph.context_contracts import (
    ObjectiveRefiner,
    Snippet,
    SnippetRetriever,
)
from microservices.orchestrator_service.src.services.overmind.langgraph.context_providers import (
    build_default_refiner,
    build_default_retriever,
)


@dataclass(frozen=True, slots=True)
class ContextEnrichmentResult:
    """
    نتيجة إثراء السياق لمعالجة الهدف قبل تشغيل LangGraph.
    """

    refined_objective: str
    metadata: dict[str, object]
    snippets: list[dict[str, object]]


class ContextEnricher:
    """
    خدمة إثراء سياق مبنية على مزودات قابلة للتبديل.

    تعتمد على تنقيح الهدف عبر مزود مخصص ثم استرجاع مقتطفات داعمة
    من مصدر خارجي دون اقتران مباشر على تفاصيل التنفيذ.
    """

    def __init__(
        self,
        *,
        max_snippets: int = 4,
        refiner: ObjectiveRefiner | None = None,
        retriever: SnippetRetriever | None = None,
    ) -> None:
        self.max_snippets = max_snippets
        self.refiner = refiner or build_default_refiner()
        self.retriever = retriever or build_default_retriever()

    async def enrich(self, objective: str, context: dict[str, object]) -> ContextEnrichmentResult:
        """
        تنفيذ خط إثراء السياق وإرجاع النتيجة المجمعة.
        """
        refine_result = await self.refiner.refine(objective)
        snippets = await self.retriever.retrieve(
            refine_result.refined_objective,
            context=context,
            metadata=refine_result.metadata,
            max_snippets=self.max_snippets,
        )
        return ContextEnrichmentResult(
            refined_objective=refine_result.refined_objective,
            metadata=refine_result.metadata,
            snippets=[_serialize_snippet(snippet) for snippet in snippets],
        )


def _serialize_snippet(snippet: Snippet) -> dict[str, object]:
    """
    تحويل المقتطف إلى قاموس قابل للإرسال.
    """
    return {"text": snippet.text, "metadata": snippet.metadata}
