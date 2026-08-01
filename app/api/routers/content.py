from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from shared.retrieval import RankedDocument, RetrievalError, rank_documents

COMPATIBILITY_FACADE_MODE = True
CANONICAL_EXECUTION_AUTHORITY = "research-agent-content-domain"

router = APIRouter(prefix="/v1/content", tags=["content"])


class ContentItemResponse(BaseModel):
    id: str
    type: str
    title: str | None = None
    level: str | None = None
    subject: str | None = None
    year: int | None = None
    lang: str | None = None
    # D-200: كلّ نتيجة تحمل **سبب** ظهورها. صندوقٌ أسود في البحث يعني أنّ نتيجةً
    # سيّئة لا يمكن تشخيصها — لا من الطالب ولا من المُصحِّح.
    relevance: float | None = Field(
        None, ge=0.0, le=1.0, description="ثقة مُطبَّعة — تُملأ فقط عند وجود استعلام"
    )
    matched_terms: list[str] = Field(default_factory=list)


class ContentSearchResponse(BaseModel):
    items: list[ContentItemResponse]
    #: كيف رُتِّبت هذه النتائج — يظهر في العقد فلا يُخمِّن المستهلك.
    ranking: str = Field(
        "deterministic_lexical",
        description="deterministic_lexical (مُرشَّح مُرتَّب) | unranked (تصفّح بلا استعلام)",
    )


@router.get("/search", response_model=ContentSearchResponse)
async def search_content(
    q: str | None = Query(None, description="Search query"),
    level: str | None = None,
    subject: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    يبحث في عناصر المحتوى ويُرتِّبها **بالصلة**.

    D-200 — كان هذا `title LIKE '%q%' OR md_content LIKE '%q%'` ثمّ `LIMIT 50`، بثلاثة
    أعطاب في سطر: لا ترتيب إطلاقاً (النتائج بترتيب الإدراج، وأوّلها الأقدم لا الأنسب،
    والطالب يقرأ الأولى)، ومطابقة داخل الكلمات («شعاع» تُطابق «الإشعاعي» — صنف D-193
    عائداً من باب البحث)، وبلا تطبيع عربي («الأعداد المركبة» لا تُطابق «الاعداد المركبه»).

    البنية الآن: SQL يُرشِّح بالحقول المفهرسة ويُوسِّع بشبكة `LIKE` **مُرشَّحاً فقط**،
    ثمّ الترتيب الحتمي في `shared/retrieval` يقرّر. المتّجهات ستضيف مُرشِّحاً ثانياً فوق
    نفس الواجهة، بلا تغيير هذا العقد.
    """
    query_str = (
        "SELECT id, type, title, level, subject, year, lang, md_content "
        "FROM content_items WHERE 1=1"
    )
    params: dict[str, object] = {}

    if level:
        query_str += " AND level = :level"
        params["level"] = level

    if subject:
        query_str += " AND subject = :subject"
        params["subject"] = subject

    # المُرشِّح واسعٌ عمداً: تضييقه بـ`LIKE` يُسقِط ما يختلف تطبيعه عن نصّ الطالب،
    # والترتيب هو ما يفصل. السقف يحمي من مسحٍ غير محدود.
    query_str += " LIMIT 500"

    rows = (await db.execute(text(query_str), params)).fetchall()
    by_id = {row[0]: row for row in rows}

    if not q or not q.strip():
        # تصفّح بلا استعلام: لا صلة تُحسَب، ولا تُدَّعى.
        return ContentSearchResponse(
            ranking="unranked",
            items=[_to_item(row) for row in rows[:50]],
        )

    documents = [
        RankedDocument(doc_id=row[0], title=row[2] or "", body=row[7] or "") for row in rows
    ]
    try:
        matches = rank_documents(q, documents, limit=50)
    except RetrievalError:
        # استعلام بلا كلمات قابلة للبحث (رموز فقط) — قائمة فارغة صادقة لا نتائج عشوائية.
        return ContentSearchResponse(ranking="deterministic_lexical", items=[])

    return ContentSearchResponse(
        ranking="deterministic_lexical",
        items=[
            _to_item(
                by_id[match.doc_id],
                relevance=match.confidence,
                matched_terms=list(match.matched_terms),
            )
            for match in matches
        ],
    )


def _to_item(
    row: object, *, relevance: float | None = None, matched_terms: list[str] | None = None
) -> ContentItemResponse:
    """يحوّل صفّاً إلى عنصر استجابة."""
    return ContentItemResponse(
        id=row[0],
        type=row[1],
        title=row[2],
        level=row[3],
        subject=row[4],
        year=row[5],
        lang=row[6],
        relevance=relevance,
        matched_terms=matched_terms or [],
    )


@router.get("/{id}")
async def get_content(id: str, db: AsyncSession = Depends(get_db)):
    """
    Get content metadata and raw content.
    """
    result = await db.execute(
        text(
            "SELECT id, type, title, level, subject, year, lang, md_content FROM content_items WHERE id = :id"
        ),
        {"id": id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Content not found")

    return {
        "id": row[0],
        "type": row[1],
        "title": row[2],
        "level": row[3],
        "subject": row[4],
        "year": row[5],
        "lang": row[6],
        "md_content": row[7],
    }


@router.get("/{id}/raw")
async def get_content_raw(id: str, db: AsyncSession = Depends(get_db)):
    """
    Get raw markdown content.
    """
    result = await db.execute(
        text("SELECT md_content FROM content_items WHERE id = :id"), {"id": id}
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Content not found")

    return {"content": row[0]}


@router.get("/{id}/solution")
async def get_content_solution(id: str, db: AsyncSession = Depends(get_db)):
    """
    Get official solution.
    """
    result = await db.execute(
        text(
            "SELECT solution_md, steps_json, final_answer FROM content_solutions WHERE content_id = :id"
        ),
        {"id": id},
    )
    row = result.fetchone()

    # If no solution found, return 404 or empty structure?
    # User said: "If solution_md is missing... say you don't have a verified solution"
    # The API should simply return 404 or nulls.

    if not row:
        raise HTTPException(status_code=404, detail="Solution not found")

    return {"solution_md": row[0], "steps_json": row[1], "final_answer": row[2]}
