"""
مُسترجِع تمارين البكالوريا من Supabase — طبقة candidate-generation + rerank قابلة للتوسّع لمليارات التمارين.

> المعمارية: **retrieve-then-rerank** (الأسلوب القياسي للتوسّع).
>   1. استخراج الإشارات البنيوية (سنة/رقم تمرين/موضوع مرجعي) من سؤال الطالب.
>   2. توليد المرشّحين عبر SQL مفهرس على `bac_exercises` (سنة + موضوع ILIKE + raw_text
>      المميِّز عربياً). هذه هي الخطوة القابلة للتوسّع (فلاتر مفهرسة، لا مسح كامل).
>   3. إعادة الترتيب بمُصنِّف متعدد الإشارات (نفس أوزان knowledge_index) → دقة عالية.
>   4. (اختياري) إعادة ترتيب دلالي بـ tsvector/embedding حين توجد — تحسين لا شرط صحّة.

مبدأ السلامة (لا يكسر المحادثة أبداً): أي تعذّر وصول لقاعدة البيانات أو خطأ أو مهلة →
يُرجِع None، فيلجأ المُستدعي إلى الفهرس النصّي (markdown knowledge_index). هذا يجعل المسار
صامداً في البيئات التي تحجب منافذ Postgres (sandbox) ويتفعّل تلقائياً حين يصل التطبيق
إلى Supabase (Codespaces/Production).

الإشارات الدلالية (embedding/tsvector) موجودة اليوم لتمرين الاحتمالات فقط — لذلك التمييز
يعتمد على الإشارات البنيوية (سنة/رقم/موضوع) + raw_text العربي المميِّز، والإشارات الدلالية
طبقة إثراء فوقها لا شرط صحّة. هذا قرار معماري واعٍ يحمي الدقة على نطاق المليارات.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from app.services.capabilities.arabic_normalize import (
    CanonicalTopic,
    normalize_ar,
    primary_canonical_topic,
)

logger = logging.getLogger("cogniforge.bac_db_retriever")

# سنة دراسية (2000–2039) — تشمل 2016 (الدوال العددية)؛ الأرقام العربية مُحوَّلة في normalize_ar
_YEAR_RE = re.compile(r"\b20[0-3]\d\b")

# رقم التمرين الترتيبي (عربي + إنجليزي) — يُطابَق على الصورة المطبَّعة
_EXERCISE_NUMBER_PATTERNS: dict[str, int] = {
    "التمرين الاول": 1,
    "التمرين الثاني": 2,
    "التمرين الثالث": 3,
    "التمرين الرابع": 4,
    "تمرين الاول": 1,
    "تمرين الثاني": 2,
    "تمرين الثالث": 3,
    "تمرين الرابع": 4,
    "exercise 1": 1,
    "exercise 2": 2,
    "exercise 3": 3,
    "exercise 4": 4,
    "exercice 1": 1,
    "exercice 2": 2,
    "exercice 3": 3,
    "exercice 4": 4,
}
_EXERCISE_WITH_DIGIT_RE = re.compile(r"(?:تمرين|exercise|exercice)\s*(\d+)")

# أوزان إعادة الترتيب (مرآة knowledge_index — الموضوع المرجعي يهيمن على السنة)
_W_CANONICAL = 16
_W_YEAR = 10
_W_EXERCISE = 8


@dataclass(frozen=True)
class DBFacets:
    """الإشارات البنيوية المستخرجة من سؤال الطالب لتوليد مرشّحي قاعدة البيانات."""

    year: int | None
    exercise_number: int | None
    canonical: CanonicalTopic | None

    @property
    def is_anchored(self) -> bool:
        """هل توجد إشارة كافية للاستعلام؟ (موضوع أو سنة أو رقم تمرين)."""
        return (
            self.canonical is not None or self.year is not None or self.exercise_number is not None
        )


@dataclass(frozen=True)
class BACDBMatch:
    """تمرين مطابِق من Supabase مع محتواه الخام ودرجته."""

    exercise_id: str
    canonical_id: str | None
    year: int | None
    exercise_number: int | None
    topic: str
    exam_ref: str | None
    session: str | None
    raw_text: str
    score: int
    source: str = "supabase"


def extract_db_facets(query: str) -> DBFacets:
    """يستخرج (سنة، رقم تمرين، موضوع مرجعي) من سؤال الطالب — مطبَّع وصامد أمام «ال»."""
    normalized = normalize_ar(query)
    year_match = _YEAR_RE.search(normalized)
    year = int(year_match.group()) if year_match else None

    exercise_number: int | None = None
    for pattern, number in _EXERCISE_NUMBER_PATTERNS.items():
        if normalize_ar(pattern) in normalized:
            exercise_number = number
            break
    if exercise_number is None:
        digit_match = _EXERCISE_WITH_DIGIT_RE.search(normalized)
        if digit_match:
            exercise_number = int(digit_match.group(1))

    canonical = primary_canonical_topic(query)
    return DBFacets(year=year, exercise_number=exercise_number, canonical=canonical)


def build_candidate_query(facets: DBFacets) -> tuple[str, dict[str, object]]:
    """
    يبني SQL مُعامَل لتوليد مرشّحي `bac_exercises` بفلاتر مفهرسة.

    استراتيجية التوسّع: السنة (مفهرسة) + الموضوع (`topic ILIKE`، مفهرس) تحصران الفضاء؛
    `raw_text LIKE` على المصطلحات العربية المميِّزة شبكة أمان عند ضعف عمود topic.
    LIMIT يحمي من المسح الواسع على نطاق المليارات.
    """
    where: list[str] = []
    params: dict[str, object] = {}

    if facets.year is not None:
        where.append("year = :year")
        params["year"] = facets.year
    if facets.exercise_number is not None:
        where.append("(exercise_number = :exn OR exercise_number IS NULL)")
        params["exn"] = facets.exercise_number

    if facets.canonical is not None:
        topic_clauses = ["topic ILIKE :canon_like"]
        params["canon_like"] = facets.canonical.db_topic_like
        for i, term in enumerate(facets.canonical.raw_text_terms):
            key = f"rawterm{i}"
            topic_clauses.append(f"raw_text LIKE :{key}")
            params[key] = f"%{term}%"
        where.append("(" + " OR ".join(topic_clauses) + ")")

    where_sql = " AND ".join(where) if where else "TRUE"
    sql = (
        "SELECT id, subject, topic, year, session, exam_ref, exercise_number, raw_text "
        "FROM bac_exercises "
        f"WHERE {where_sql} "
        "LIMIT 25"
    )
    return sql, params


def _row_matches_canonical(row: dict, canonical: CanonicalTopic) -> bool:
    """هل ينتمي صف قاعدة البيانات للموضوع المرجعي؟ (topic إنجليزي أو raw_text عربي مميِّز)."""
    topic = str(row.get("topic") or "").lower()
    if canonical.db_topic_like.strip("%").lower() in topic:
        return True
    raw = str(row.get("raw_text") or "")
    return any(term in raw for term in canonical.raw_text_terms)


def rerank_candidates(rows: list[dict], facets: DBFacets) -> BACDBMatch | None:
    """يعيد ترتيب المرشّحين بمُصنِّف متعدد الإشارات ويُرجِع الأفضل (أو None)."""
    best: BACDBMatch | None = None
    best_key: tuple[int, int] | None = None

    for row in rows:
        score = 0
        if facets.year is not None and row.get("year") == facets.year:
            score += _W_YEAR
        if facets.canonical is not None and _row_matches_canonical(row, facets.canonical):
            score += _W_CANONICAL
        if (
            facets.exercise_number is not None
            and row.get("exercise_number") == facets.exercise_number
        ):
            score += _W_EXERCISE

        if score <= 0:
            continue

        # كسر التعادل حتمياً: درجة أعلى ثم رقم تمرين أعلى (لا يعتمد ترتيب الصفوف)
        key = (score, int(row.get("exercise_number") or 0))
        if best_key is None or key > best_key:
            canonical_id = facets.canonical.canonical_id if facets.canonical else None
            if facets.canonical and not _row_matches_canonical(row, facets.canonical):
                canonical_id = None
            best = BACDBMatch(
                exercise_id=str(row.get("id")),
                canonical_id=canonical_id,
                year=row.get("year"),
                exercise_number=row.get("exercise_number"),
                topic=str(row.get("topic") or ""),
                exam_ref=row.get("exam_ref"),
                session=row.get("session"),
                raw_text=str(row.get("raw_text") or ""),
                score=score,
            )
            best_key = key

    return best


async def search_bac_exercises_db(query: str, *, timeout_s: float = 4.0) -> BACDBMatch | None:
    """
    استرجاع تمرين البكالوريا من Supabase (candidate-generation + rerank).

    يُرجِع أفضل تمرين مطابِق، أو None عند: غياب إشارة كافية / تعذّر الوصول / خطأ / مهلة /
    لا نتيجة — في كل تلك الحالات يلجأ المُستدعي إلى الفهرس النصّي (markdown).
    """
    facets = extract_db_facets(query)
    if not facets.is_anchored:
        return None

    try:
        from sqlalchemy import text  # lazy: لا نُحمِّل DB stack إلا عند الحاجة

        from app.core.database import async_session_factory

        sql, params = build_candidate_query(facets)
        async with async_session_factory() as session:
            result = await asyncio.wait_for(session.execute(text(sql), params), timeout=timeout_s)
            rows = [dict(m) for m in result.mappings().all()]
    except Exception as exc:
        logger.info("bac_db_retriever fallback to markdown index (DB unavailable): %s", exc)
        return None

    if not rows:
        return None
    return rerank_candidates(rows, facets)


async def fetch_exercise_raw_text(
    *,
    year: int | None,
    exercise_number: int | None,
    canonical_id: str | None,
    timeout_s: float = 4.0,
) -> str | None:
    """
    يجلب نص تمرين بعينه من Supabase بهويته (سنة + رقم + موضوع مرجعي).

    يُستخدم للتحميل الهجين للمحتوى: المُسترجِع النصّي يُحدِّد أي تمرين (recognition)، وهذا
    يجلب نصه الرسمي من قاعدة البيانات (single source of truth). None عند أي تعذّر → markdown.
    """
    from app.services.capabilities.arabic_normalize import CANONICAL_BY_ID

    canonical = CANONICAL_BY_ID.get(canonical_id) if canonical_id else None
    facets = DBFacets(year=year, exercise_number=exercise_number, canonical=canonical)
    if not facets.is_anchored:
        return None
    match = await search_bac_exercises_db_from_facets(facets, timeout_s=timeout_s)
    return match.raw_text if match and match.raw_text.strip() else None


async def search_bac_exercises_db_from_facets(
    facets: DBFacets, *, timeout_s: float = 4.0
) -> BACDBMatch | None:
    """نسخة من search_bac_exercises_db تأخذ الإشارات جاهزة (لإعادة الاستخدام الداخلي)."""
    if not facets.is_anchored:
        return None
    try:
        from sqlalchemy import text

        from app.core.database import async_session_factory

        sql, params = build_candidate_query(facets)
        async with async_session_factory() as session:
            result = await asyncio.wait_for(session.execute(text(sql), params), timeout=timeout_s)
            rows = [dict(m) for m in result.mappings().all()]
    except Exception as exc:
        logger.info("bac_db_retriever fallback to markdown index (DB unavailable): %s", exc)
        return None
    if not rows:
        return None
    return rerank_candidates(rows, facets)
