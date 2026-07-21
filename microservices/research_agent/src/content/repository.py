import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from microservices.research_agent.src.content.domain import (
    ContentDetail,
    ContentFilter,
    ContentSummary,
)

logger = logging.getLogger(__name__)

# Global cached model (loaded lazily)
_EMBEDDING_MODEL = None
_EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"


def _get_model():
    # D-172/D-173: استيراد كسول لـ sentence-transformers — الوحدة تُستورَد بلا التبعية
    # الثقيلة (fail-open)؛ النموذج يُحمَّل فقط عند أول استخدام فعلي للتضمين.
    global _EMBEDDING_MODEL
    if _EMBEDDING_MODEL is None:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading Semantic Model: {_EMBEDDING_MODEL_NAME}")
        _EMBEDDING_MODEL = SentenceTransformer(_EMBEDDING_MODEL_NAME)
    return _EMBEDDING_MODEL


class ContentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(self, filters: ContentFilter) -> list[ContentSummary]:
        """
        Executes a Semantic Hybrid search query against content_items and content_search.
        Uses Vectors (pgvector) + Metadata Filters.
        """
        # Base Query
        # We select items. If search query exists, we calculate distance.
        select_cols = (
            "i.id, i.title, i.type, i.level, i.subject, i.branch, i.set_name, i.year, i.lang"
        )

        query_str = f"""
            SELECT {select_cols}
            FROM content_items i
            LEFT JOIN content_search cs ON i.id = cs.content_id
            WHERE 1=1
        """
        params = {}
        order_clause = "ORDER BY i.year DESC NULLS LAST, i.id ASC"

        # 1. Semantic / Keyword Search
        if filters.q:
            query_text = filters.q.strip()

            # --- Vector Search Logic ---
            try:
                loop = asyncio.get_running_loop()
                # Run embedding in thread pool to avoid blocking async loop
                model = await loop.run_in_executor(None, _get_model)
                embedding = await loop.run_in_executor(
                    None, lambda: model.encode(f"query: {query_text}").tolist()
                )

                # Pass vector as string literal with explicit cast to handle asyncpg/sqlalchemy types robustly
                # This ensures pgvector works even if the driver binding is tricky
                vec_str = str(embedding)

                # Update Select to include distance (for ordering/debugging if needed)
                # But here we mainly filter/sort.
                # We rank by distance (lower is better)

                # We use the vector distance in the ORDER BY clause
                # We assume pgvector extension is enabled and column is vector

                # Note: We prioritize semantic match highly
                order_clause = f"ORDER BY (cs.embedding <=> '{vec_str}'::vector) ASC, i.year DESC"

                # Optional: We could add a WHERE clause cutoff for distance, but strict filtering is usually metadata based.

            except Exception as e:
                logger.error(f"Vector generation failed, falling back to keyword: {e}")
                # Fallback to Keyword logic if model fails
                terms = query_text.split()
                conds = []
                for i, term in enumerate(terms):
                    p_key = f"q_{i}"
                    conds.append(f"(i.title LIKE :{p_key} OR cs.plain_text LIKE :{p_key})")
                    params[p_key] = f"%{term}%"
                if conds:
                    query_str += " AND " + " AND ".join(conds)

        # 2. Metadata Filters
        if filters.level:
            query_str += " AND i.level = :level"
            params["level"] = filters.level

        if filters.subject:
            query_str += " AND i.subject = :subject"
            params["subject"] = filters.subject

        if filters.branch:
            # EXACT MATCH on the new column
            query_str += " AND i.branch = :branch"
            params["branch"] = filters.branch

        if filters.set_name:
            query_str += " AND i.set_name = :set_name"
            params["set_name"] = filters.set_name

        if filters.year:
            query_str += " AND i.year = :year"
            params["year"] = filters.year

        if filters.type:
            query_str += " AND i.type = :type"
            params["type"] = filters.type

        if filters.lang:
            query_str += " AND i.lang = :lang"
            params["lang"] = filters.lang

        # Ordering and Limiting
        query_str += f" {order_clause} LIMIT :limit"
        params["limit"] = filters.limit

        try:
            result = await self.session.execute(text(query_str), params)
            rows = result.fetchall()
        except Exception as e:
            logger.error(f"Repository Search Failed: {e}")
            return []

        # Map to Domain Objects
        items = []
        seen = set()
        for row in rows:
            if row.id in seen:
                continue
            seen.add(row.id)
            items.append(
                ContentSummary(
                    id=row.id,
                    title=row.title,
                    type=row.type,
                    level=row.level,
                    subject=row.subject,
                    branch=row.branch,
                    set_name=row.set_name,
                    year=row.year,
                    lang=row.lang,
                )
            )

        return items

    async def get_content_detail(self, content_id: str) -> ContentDetail | None:
        """
        Retrieves raw markdown content and solution.
        """
        query_str = """
            SELECT i.id, i.md_content, s.solution_md, i.title
            FROM content_items i
            LEFT JOIN content_solutions s ON i.id = s.content_id
            WHERE i.id = :id
        """
        try:
            result = await self.session.execute(text(query_str), {"id": content_id})
            row = result.fetchone()
        except Exception as e:
            logger.error(f"Get Content Detail Failed: {e}")
            return None

        if not row:
            return None

        return ContentDetail(
            id=row.id,
            content_md=row.md_content,
            solution_md=row.solution_md,
            metadata={"title": row.title},
        )

    async def get_tree_items(self, level: str | None = None) -> list[object]:
        """
        Fetch items for curriculum tree construction.
        """
        query_str = """
            SELECT id, title, type, level, subject, branch, set_name, year
            FROM content_items
            WHERE 1=1
        """
        params = {}
        if level:
            query_str += " AND level = :level"
            params["level"] = level

        query_str += " ORDER BY subject, level, set_name, id"

        try:
            result = await self.session.execute(text(query_str), params)
            return result.fetchall()
        except Exception as e:
            logger.error(f"Get Tree Items Failed: {e}")
            return []
