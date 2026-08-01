"""ترتيب نتائج البحث — حتمي، مُفسَّر، و dep-free (D-200).

لماذا هذا الملفّ موجود
----------------------
`GET /api/content/search` كان يبحث بـ`title LIKE '%q%' OR md_content LIKE '%q%'` ثمّ
`LIMIT 50`. ثلاثة أعطاب في سطرٍ واحد:

1. **لا ترتيب إطلاقاً.** النتائج بترتيب إدراجها في الجدول. أوّل نتيجة ليست الأنسب بل
   الأقدم — وطالبٌ يبحث لا يقرأ خمسين نتيجة، يقرأ الأولى.
2. **`LIKE` يطابق داخل الكلمات.** «شعاع» تُطابق «الإشعاعي»، وهو بالضبط صنف العطب الذي
   حاربه D-193 في تصنيف المفاهيم — هنا يعود من باب البحث.
3. **بلا تطبيع عربي.** «الأعداد المركبة» لا تُطابق «الاعداد المركبه»، والطالب يكتب
   الصيغتين بالتناوب.

القرار: الترتيب يعيش هنا — **حتمي، بلا LLM، وقابل للتفسير**. كلّ نتيجة تحمل درجتها
وسببها، فيستطيع الطالب (والمُصحِّح) أن يرى **لماذا** ظهرت. صندوقٌ أسود في البحث يعني
أنّ نتيجةً سيّئة لا يمكن تشخيصها.

ما هذا الملفّ **ليس**
---------------------
ليس استرجاعاً متّجهياً. عمود `embedding` وفهرس HNSW و`CrossEncoder` موجودة في المستودع
لكنّها لا تُستدعى وقت الطلب (تبقى خلف `ENABLE_RETRIEVAL_RERANK_SKILL`). هذه الطبقة
تُصلح المُرشِّح الأساسي بما يعمل **اليوم** وبلا بنية تحتية جديدة؛ ودمج المتّجهات يضيف
مُرشِّحاً ثانياً فوق نفس واجهة الترتيب.

عقد الموقع
----------
stdlib فقط + `shared/textnorm`. لا استيراد من `app/` ولا من أيّ خدمة (قانون الحدود).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from shared.textnorm import normalize

__all__ = [
    "RankedDocument",
    "RetrievalError",
    "ScoredMatch",
    "rank_documents",
    "score_document",
    "tokenize",
]


class RetrievalError(ValueError):
    """خرق لمجال الاسترجاع — استعلام فارغ أو أوزان غير صالحة."""


#: وزن مطابقة العنوان مقابل المتن. العنوان إشارة نيّة أقوى بكثير من ورودٍ عابر في نصّ طويل.
TITLE_WEIGHT: Final = 3.0
BODY_WEIGHT: Final = 1.0
#: مكافأة تطابق العبارة كاملةً متتاليةً — أقوى دليل صلة متاح بلا متّجهات.
PHRASE_BONUS: Final = 4.0
#: أقصى مساهمة لتكرار كلمة واحدة: بلا سقف يتصدّر مستندٌ يُكرّر كلمةً مئة مرّة.
MAX_TERM_CONTRIBUTION: Final = 3

_TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)

#: كلمات وظيفية عربية/فرنسية شائعة — وجودها لا يدلّ على صلة.
_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "في",
        "من",
        "على",
        "الى",
        "عن",
        "مع",
        "هذا",
        "هذه",
        "ذلك",
        "التي",
        "الذي",
        "ما",
        "هل",
        "كيف",
        "لي",
        "لك",
        "هو",
        "هي",
        "او",
        "و",
        "ثم",
        "قد",
        "كل",
        "le",
        "la",
        "les",
        "de",
        "du",
        "des",
        "un",
        "une",
        "et",
        "ou",
        "pour",
        "the",
        "a",
        "an",
        "of",
        "for",
        "and",
        "or",
        "to",
        "in",
        "on",
    }
)


@dataclass(frozen=True)
class RankedDocument:
    """مستندٌ مُرشَّح كما يصل طبقة الترتيب."""

    doc_id: str
    title: str
    body: str = ""


@dataclass(frozen=True)
class ScoredMatch:
    """نتيجة مُرتَّبة مع **سبب** ظهورها."""

    doc_id: str
    score: float
    #: المصطلحات التي طابقت فعلاً — هذا ما يجعل النتيجة قابلة للتشخيص.
    matched_terms: tuple[str, ...] = field(default_factory=tuple)
    title_hit: bool = False
    phrase_hit: bool = False

    @property
    def confidence(self) -> float:
        """ثقة مُطبَّعة في [0,1] — مشتقّة من الدرجة، تُعرَض للمستخدم."""
        return round(min(1.0, self.score / 12.0), 4)


def _strip_article(token: str) -> str:
    """
    يحذف أداة التعريف «ال» من أوّل الكلمة.

    **نفس صنف العطب الذي عالجه D-193 في التصنيف، عائداً من باب البحث:** طالبٌ يكتب
    «احتمالات» لا يجد مستنداً عنوانه «الاحتمالات». القياس الوحيد المقبول هو الجذر
    المُعرَّف نفسه في الطرفين. حدّ الطول ٤ يحمي ما «ال» جزءٌ أصيل منه (الله · الان).
    """
    return token[2:] if token.startswith("ال") and len(token) > 4 else token


def tokenize(text: str) -> tuple[str, ...]:
    """يُطبِّع النصّ ويقطّعه إلى كلمات ذات دلالة (بلا كلمات وظيفية ولا أحرف مفردة)."""
    normalized = normalize(text)
    return tuple(
        stripped
        for token in _TOKEN_RE.findall(normalized)
        if len(token) > 1 and token not in _STOPWORDS
        for stripped in (_strip_article(token),)
        if stripped not in _STOPWORDS
    )


def _count_whole_word(haystack_tokens: tuple[str, ...], term: str) -> int:
    """
    عدّ على **حدود الكلمات** لا سلاسل فرعية.

    `LIKE '%شعاع%'` تُطابق «الإشعاعي» — نفس صنف العطب الذي حاربه D-193 في التصنيف.
    التقطيع يجعل ذلك غير مُمثَّل بدل أن يكون مُرشَّحاً.
    """
    return sum(1 for token in haystack_tokens if token == term)


def score_document(query: str, document: RankedDocument) -> ScoredMatch:
    """يُسجِّل مستنداً واحداً مقابل استعلام — حتمي تماماً."""
    query_terms = tokenize(query)
    if not query_terms:
        raise RetrievalError("query has no searchable terms")

    title_tokens = tokenize(document.title)
    body_tokens = tokenize(document.body)

    score = 0.0
    matched: list[str] = []
    title_hit = False

    for term in dict.fromkeys(query_terms):  # فريدة مع حفظ الترتيب
        in_title = min(_count_whole_word(title_tokens, term), MAX_TERM_CONTRIBUTION)
        in_body = min(_count_whole_word(body_tokens, term), MAX_TERM_CONTRIBUTION)
        if in_title:
            title_hit = True
        if in_title or in_body:
            matched.append(term)
        score += in_title * TITLE_WEIGHT + in_body * BODY_WEIGHT

    # تطابق العبارة كاملةً متتاليةً — أقوى دليل صلة متاح هنا.
    phrase_hit = False
    if len(query_terms) > 1:
        joined_title = " ".join(title_tokens)
        joined_body = " ".join(body_tokens)
        phrase = " ".join(query_terms)
        if phrase in joined_title or phrase in joined_body:
            phrase_hit = True
            score += PHRASE_BONUS

    return ScoredMatch(
        doc_id=document.doc_id,
        score=round(score, 4),
        matched_terms=tuple(matched),
        title_hit=title_hit,
        phrase_hit=phrase_hit,
    )


def rank_documents(
    query: str, documents: list[RankedDocument], *, limit: int = 20
) -> tuple[ScoredMatch, ...]:
    """
    يُرتِّب المستندات تنازلياً بالدرجة. **يُسقِط ما لم يُطابِق شيئاً.**

    عرض نتيجة بدرجة صفر يعني إخبار الطالب بأنّ هذا «جواب» بينما لم يُطابِق شيئاً —
    والقائمة الفارغة الصادقة أنفع من قائمةٍ مليئة بلا معنى (§0).
    """
    if limit < 1:
        raise RetrievalError("limit must be >= 1")

    scored = [score_document(query, document) for document in documents]
    relevant = [match for match in scored if match.score > 0]
    # الترتيب الثانوي بالمُعرَّف يجعل النتيجة **مستقرّة** بين التشغيلات.
    relevant.sort(key=lambda match: (-match.score, match.doc_id))
    return tuple(relevant[:limit])
