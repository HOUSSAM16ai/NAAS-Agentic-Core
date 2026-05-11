"""
محرك الاسترجاع لـ content-retrieval-skill — الخطوة 11.

المسؤولية الوحيدة: جلب المحتوى من knowledge_base/ بناءً على النية.

Contract:
  Input:  RetrievalQuery(question, intent, filters)
  Output: RetrievalResult(items, total, kb_path, duration_ms)

قواعد:
  - يقرأ من knowledge_base/ فقط (لا DB، لا HTTP)
  - كل ملف .md = وحدة محتوى مستقلة مع metadata YAML front-matter
  - الفلترة بـ subject/year/tags من front-matter
  - Fallback: إذا لم تُوجَد نتائج → قائمة فارغة (لا خطأ)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ContentItem:
    """وحدة محتوى واحدة من knowledge_base/."""

    id: str
    title: str
    subject: str
    year: str
    tags: list[str]
    content_preview: str  # أول 500 حرف
    file_path: str


@dataclass
class RetrievalQuery:
    """طلب الاسترجاع مع فلاتر اختيارية."""

    question: str
    intent: str
    subject: str | None = None
    year: str | None = None
    tags: list[str] = field(default_factory=list)
    max_results: int = 5


@dataclass
class RetrievalResult:
    """نتيجة الاسترجاع — contract ثابت."""

    items: list[ContentItem]
    total: int
    kb_path: str
    duration_ms: float
    query_subject: str | None = None
    query_year: str | None = None


# ── تعبيرات منتظمة للـ front-matter ──────────────────────────────────────────
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_YEAR_IN_QUESTION_RE = re.compile(r"\b(20[2-3]\d)\b")
_SUBJECT_KEYWORDS: dict[str, list[str]] = {
    "math": ["رياضيات", "math", "mathematics", "احتمالات", "probability", "جبر", "هندسة"],
    "physics": ["فيزياء", "physics", "ميكانيك", "كهرباء"],
    "chemistry": ["كيمياء", "chemistry"],
}


def _parse_frontmatter(content: str) -> dict[str, object]:
    """يستخرج YAML front-matter من ملف Markdown بدون مكتبة خارجية."""
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    result: dict[str, object] = {}
    for raw_line in match.group(1).splitlines():
        stripped = raw_line.strip()
        if ":" not in stripped or stripped.startswith("-"):
            continue
        key, _, val = stripped.partition(":")
        result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def _extract_year_from_question(question: str) -> str | None:
    """يستخرج سنة دراسية من السؤال إذا وُجدت."""
    match = _YEAR_IN_QUESTION_RE.search(question)
    return match.group(1) if match else None


def _extract_subject_from_question(question: str) -> str | None:
    """يستخرج المادة من السؤال بناءً على الكلمات المفتاحية."""
    q_lower = question.lower()
    for subject, keywords in _SUBJECT_KEYWORDS.items():
        if any(kw in q_lower for kw in keywords):
            return subject
    return None


def _score_item(item: ContentItem, query: RetrievalQuery) -> float:
    """
    يحسب درجة ملاءمة ContentItem للـ query.

    الدرجة الأعلى = أكثر ملاءمة.
    """
    score = 0.0
    q_lower = query.question.lower()

    # تطابق السنة
    if query.year and query.year in item.year:
        score += 3.0
    elif query.year and query.year in item.file_path:
        score += 2.0

    # تطابق المادة
    if query.subject and query.subject in item.subject.lower():
        score += 2.0

    # تطابق الـ tags
    for tag in item.tags:
        if tag.lower() in q_lower:
            score += 1.0

    # تطابق العنوان
    for word in q_lower.split():
        if len(word) > 3 and word in item.title.lower():
            score += 0.5

    return score


def retrieve(query: RetrievalQuery, kb_root: Path) -> RetrievalResult:
    """
    يسترجع المحتوى من knowledge_base/ بناءً على الـ query.

    الخوارزمية:
      1. اكتشاف السنة والمادة من السؤال إذا لم تُعطَ
      2. قراءة جميع ملفات .md في kb_root
      3. تحليل front-matter لكل ملف
      4. تسجيل درجة الملاءمة
      5. إعادة أعلى max_results نتيجة

    لا يرفع استثناءات — يُعيد قائمة فارغة عند الفشل.
    """
    import time

    start = time.monotonic()

    # اكتشاف تلقائي للسنة والمادة
    effective_year = query.year or _extract_year_from_question(query.question)
    effective_subject = query.subject or _extract_subject_from_question(query.question)

    items: list[tuple[float, ContentItem]] = []

    try:
        md_files = list(kb_root.glob("**/*.md"))
        for md_file in md_files:
            if md_file.name == "README.md":
                continue
            try:
                raw = md_file.read_text(encoding="utf-8")
                meta = _parse_frontmatter(raw)

                # استخراج metadata
                title = str(meta.get("title", md_file.stem))
                subject = str(meta.get("subject", ""))
                year = str(meta.get("year", ""))
                tags_raw = meta.get("tags", "")
                tags: list[str] = []
                if isinstance(tags_raw, str):
                    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

                # معاينة المحتوى (بعد front-matter)
                body = _FRONTMATTER_RE.sub("", raw).strip()
                preview = body[:500]

                item = ContentItem(
                    id=md_file.stem,
                    title=title,
                    subject=subject,
                    year=year,
                    tags=tags,
                    content_preview=preview,
                    file_path=str(md_file.relative_to(kb_root)),
                )

                effective_query = RetrievalQuery(
                    question=query.question,
                    intent=query.intent,
                    subject=effective_subject,
                    year=effective_year,
                    tags=query.tags,
                    max_results=query.max_results,
                )
                score = _score_item(item, effective_query)
                items.append((score, item))

            except Exception:
                continue

    except Exception:
        pass

    # ترتيب تنازلي بالدرجة
    items.sort(key=lambda x: x[0], reverse=True)
    top_items = [item for _, item in items[: query.max_results]]

    duration_ms = (time.monotonic() - start) * 1000

    return RetrievalResult(
        items=top_items,
        total=len(top_items),
        kb_path=str(kb_root),
        duration_ms=duration_ms,
        query_subject=effective_subject,
        query_year=effective_year,
    )
