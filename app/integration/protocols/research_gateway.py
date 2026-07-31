"""عقد بوّابة البحث (ACL) — مُصنَّف بلا `Any` (D-192 · roadmap D1)."""

from typing import Protocol, runtime_checkable

from app.integration.models import GatewayStatus, RefinedQuery, RerankedDocument, SearchHit


@runtime_checkable
class ResearchGatewayProtocol(Protocol):
    """
    Protocol for Research Agent capabilities (Search, Refine, Rerank).
    Acts as an ACL to the Research Domain.
    """

    async def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, object] | None = None,
    ) -> list[SearchHit]:
        """Perform semantic search. Returns typed result hits."""
        ...

    async def refine_query(
        self,
        query: str,
        api_key: str | None = None,
    ) -> RefinedQuery:
        """Refine a user query using DSPy/LLM. Returns the refined query + filters."""
        ...

    async def rerank_results(
        self,
        query: str,
        documents: list[str] | list[dict[str, object]],
        top_n: int = 5,
    ) -> list[RerankedDocument]:
        """Rerank documents against the query. Returns the reranked list."""
        ...

    def get_llamaindex_status(self) -> GatewayStatus:
        """Check LlamaIndex availability."""
        ...

    def get_dspy_status(self) -> GatewayStatus:
        """Check DSPy availability."""
        ...

    def get_reranker_status(self) -> GatewayStatus:
        """Check Reranker availability."""
        ...
