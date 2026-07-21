"""search_engine — استيراد كسول (D-173): استيراد الحزمة لا يجرّ محرك الاسترجاع
الثقيل (llama-index-embeddings-huggingface + sentence-transformers). الرموز
الخفيفة (models) تبقى قابلة للاستيراد مستقلةً؛ المحرك يُحمَّل عند أول استخدام فعلي."""

from __future__ import annotations

from typing import Any

__all__ = ["LlamaIndexRetriever", "get_refined_query", "get_retriever"]


def __getattr__(name: str) -> Any:
    if name == "get_refined_query":
        from .query_refiner import get_refined_query

        return get_refined_query
    if name in ("LlamaIndexRetriever", "get_retriever"):
        from . import retriever

        return getattr(retriever, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
