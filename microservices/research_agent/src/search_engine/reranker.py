from llama_index.core.schema import NodeWithScore

from microservices.research_agent.src.logging import get_logger

logger = get_logger(__name__)

# Singleton instance
_RERANKER_INSTANCE = None


class Reranker:
    """
    محرك إعادة الترتيب (Reranker) لتحسين نتائج البحث الدلالي.
    يستخدم نموذج Cross-Encoder لإعادة تقييم الصلة بين الاستعلام والوثائق المسترجعة.
    """

    def __init__(self, model_name: str = "BAAI/bge-reranker-base"):
        self.model_name = model_name
        try:
            # D-172/D-173: استيراد كسول (fail-open) — الوحدة تُستورَد بلا sentence-transformers؛
            # النموذج يُحمَّل عند الإنشاء فقط، وأي فشل يُبقي self.model = None بأمان.
            from sentence_transformers import CrossEncoder

            # We trust the environment to have the model cached or download it.
            self.model = CrossEncoder(model_name)
            logger.info(f"Reranker model {model_name} loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Reranker model {model_name}: {e}")
            self.model = None

    def rerank(self, query: str, nodes: list[NodeWithScore], top_n: int = 5) -> list[NodeWithScore]:
        """
        إعادة ترتيب قائمة الوثائق بناءً على صلتها بالاستعلام.
        """
        if not self.model or not nodes:
            return nodes[:top_n]

        try:
            # Prepare pairs for Cross-Encoder
            # We access the text content of the node
            doc_texts = [n.node.get_content() for n in nodes]
            pairs = [[query, doc_text] for doc_text in doc_texts]

            scores = self.model.predict(pairs)

            # Update scores and resort
            for i, node in enumerate(nodes):
                # Ensure score is a float
                node.score = float(scores[i])

            # Sort by new score descending
            nodes.sort(key=lambda x: x.score if x.score is not None else -1.0, reverse=True)

            return nodes[:top_n]

        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Fallback: return original order
            return nodes[:top_n]


def get_reranker() -> Reranker:
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        _RERANKER_INSTANCE = Reranker()
    return _RERANKER_INSTANCE
