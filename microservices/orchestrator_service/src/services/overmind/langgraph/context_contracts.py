from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class RefineResult:
    """
    نتيجة تنقيح الهدف بصورة صريحة.
    """

    refined_objective: str
    metadata: dict[str, object]


@dataclass(frozen=True, slots=True)
class Snippet:
    """
    مقتطف سياقي موحّد مع بيانات وصفية.
    """

    text: str
    metadata: dict[str, object]


class ObjectiveRefiner(Protocol):
    """
    بروتوكول تنقيح الهدف وفق عقد واضحة.
    """

    async def refine(self, objective: str) -> RefineResult:
        """
        تنقيح الهدف وإرجاع النتيجة.
        """


class SnippetRetriever(Protocol):
    """
    بروتوكول استرجاع المقتطفات السياقية.
    """

    async def retrieve(
        self,
        query: str,
        *,
        context: dict[str, object],
        metadata: dict[str, object],
        max_snippets: int,
    ) -> list[Snippet]:
        """
        استرجاع مقتطفات سياقية بناءً على الاستعلام.
        """
