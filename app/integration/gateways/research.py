"""مُحوِّل بوّابة البحث (ACL) — يُصنِّف حمولة الخدمة عند الحدّ (D-192 · roadmap D1)."""

from app.core.logging import get_logger
from app.infrastructure.clients.research_client import research_client
from app.integration.models import GatewayStatus, RefinedQuery, RerankedDocument, SearchHit
from app.integration.protocols.research_gateway import ResearchGatewayProtocol

logger = get_logger(__name__)

_REMOTE = GatewayStatus(status="active", mode="remote-microservice")


def _as_mapping(item: object) -> dict[str, object]:
    """يُطبِّع عنصر حمولةٍ خام إلى قاموس — نصٌّ حرّ يصير حقل ``text``.

    الخدمة قد تُرجِع نصّاً مباشراً أو قاموساً؛ التطبيع هنا يمنع تسرّب ذلك الاختلاف
    إلى نواة التطبيق (وهذا هو عمل الـACL أصلاً).
    """
    if isinstance(item, dict):
        return item
    return {"text": str(item)}


class RemoteResearchGateway(ResearchGatewayProtocol):
    """
    Remote Adapter for the Research Agent.
    Implements the ResearchGatewayProtocol by using the ResearchClient (HTTP).
    This acts as an Anti-Corruption Layer (ACL) preventing direct coupling in the core app.
    """

    async def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        filters: dict[str, object] | None = None,
    ) -> list[SearchHit]:
        """Executes semantic search via the Research Agent microservice."""
        try:
            raw = await research_client.semantic_search(query, top_k=top_k, filters=filters)
        except Exception as e:
            logger.error(f"Error in semantic_search: {e}")
            raise
        return [SearchHit.model_validate(_as_mapping(item)) for item in raw or []]

    async def refine_query(
        self,
        query: str,
        api_key: str | None = None,
    ) -> RefinedQuery:
        """Refines a query using the Research Agent microservice."""
        try:
            raw = await research_client.refine_query(query, api_key=api_key)
        except Exception as e:
            logger.error(f"Error in refine_query: {e}")
            raise
        return RefinedQuery.model_validate(_as_mapping(raw))

    async def rerank_results(
        self,
        query: str,
        documents: list[str] | list[dict[str, object]],
        top_n: int = 5,
    ) -> list[RerankedDocument]:
        """Reranks results using the Research Agent microservice."""
        try:
            raw = await research_client.rerank_results(query, documents, top_n=top_n)
        except Exception as e:
            logger.error(f"Error in rerank_results: {e}")
            raise
        return [
            RerankedDocument.model_validate({"index": index, **_as_mapping(item)})
            for index, item in enumerate(raw or [])
        ]

    def get_llamaindex_status(self) -> GatewayStatus:
        return _REMOTE

    def get_dspy_status(self) -> GatewayStatus:
        return _REMOTE

    def get_reranker_status(self) -> GatewayStatus:
        return _REMOTE


# Alias for backward compatibility
LocalResearchGateway = RemoteResearchGateway
