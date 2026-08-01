"""طبقة الاسترجاع المشتركة — ترتيب حتمي وشفّاف (D-200)."""

from __future__ import annotations

from .ranking import (
    RankedDocument,
    RetrievalError,
    ScoredMatch,
    rank_documents,
    score_document,
    tokenize,
)

__all__ = [
    "RankedDocument",
    "RetrievalError",
    "ScoredMatch",
    "rank_documents",
    "score_document",
    "tokenize",
]
