"""
محرّك التطبيع والتعرّف العربي — الأساس المعمّم لاسترجاع التمارين على نطاق المليارات.

> القاعدة الذهبية: المطابقة يجب أن تكون **صامدة أمام الصرف العربي** — أداة التعريف
> «ال»، تنويع الهمزات (أ/إ/آ/ٱ)، التاء المربوطة (ة)، الألف المقصورة (ى)، التشكيل،
> والتطويل (ـــ). بدون هذا التطبيع، «الأعداد المركبة» لا تطابق «أعداد مركبة» (السبب
> الجذري لـ ISS — استرجاع الاحتمالات بدل الأعداد المركبة).

هذا المحرّك مستقل تماماً عن مصدر البيانات (in-memory index أو Supabase). يجلس كطبقة
تطبيع + تعرّف موضوعي أمام أي backend استرجاع، فيعمل مع 3 تمارين اليوم ومع مليارات غداً.

المبدأ المعماري: **retrieve-then-rerank**.
  1. التطبيع (هنا) يوحّد صيغ الكتابة.
  2. التصنيف الموضوعي (CanonicalTopic) يربط صياغة الطالب بالموضوع المرجعي + قيمته في DB.
  3. الـ backend يولّد المرشحين (candidate generation) بفلاتر مفهرسة.
  4. مُصنِّف متعدد الإشارات يعيد الترتيب (rerank) بدقة عالية.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# ─────────────────────────────────────────────────────────────────────────────
# تطبيع النص العربي (Arabic morphological normalization)
# ─────────────────────────────────────────────────────────────────────────────

# التشكيل (fatha…sukun) + الألف الخنجرية (superscript alef U+0670)
_DIACRITICS_RE = re.compile(r"[ً-ٰٟ]")
_TATWEEL = "ـ"

# توحيد الحروف المتغيّرة إلى صورة قانونية واحدة
_CHAR_FOLD = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ؤ": "و",
        "ئ": "ي",
        "ء": "",
        "ة": "ه",
        "ى": "ي",
        # أرقام عربية-هندية → لاتينية (للسنوات/الأرقام في النص العربي)
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
    }
)

# بادئات أداة التعريف (مرتّبة من الأطول للأقصر — الأطول أولاً)
# وال/فال/بال/كال = حرف عطف/جر + ال ؛ لل = لام الجر + ال (للدالة) ؛ ال = التعريف
_AL_PREFIXES: tuple[str, ...] = ("وال", "فال", "بال", "كال", "لل", "ال")
# الحد الأدنى لطول الجذع بعد حذف البادئة (يمنع تشويه الكلمات القصيرة مثل «والد»)
_MIN_STEM_LEN = 2

_WS_RE = re.compile(r"\s+")
# رمز كلمة عربي/لاتيني/رقمي (للتقطيع إلى وحدات معجمية)
_TOKEN_RE = re.compile(r"[0-9A-Za-zء-ي]+")


def _strip_definite_article(token: str) -> str:
    """يحذف أداة التعريف «ال» (وصيغها) من بداية الرمز مع حماية الكلمات القصيرة."""
    for prefix in _AL_PREFIXES:
        if token.startswith(prefix) and (len(token) - len(prefix)) >= _MIN_STEM_LEN:
            return token[len(prefix) :]
    return token


def normalize_ar(text: str) -> str:
    """
    يُرجِع صورة قانونية موحّدة للنص العربي صالحة للمطابقة الصامدة أمام الصرف.

    الخطوات (بالترتيب):
      1. NFKC unicode normalization.
      2. حذف التطويل (ـ) والتشكيل والألف الخنجرية.
      3. توحيد الهمزات/التاء المربوطة/الألف المقصورة + الأرقام العربية.
      4. تصغير اللاتيني (lower).
      5. حذف أداة التعريف «ال» لكل رمز (مع حماية الجذع القصير).
      6. تطبيع المسافات.

    تُطبَّق على **طرفي المطابقة** (الاستعلام + فهرس المواضيع) لضمان التقاء الصيغ:
    «الأعداد المركبة» و«أعداد مركبة» و«الأعداد المركبه» → كلها «اعداد مركبه».
    """
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", str(text))
    s = s.replace(_TATWEEL, "")
    s = _DIACRITICS_RE.sub("", s)
    s = s.translate(_CHAR_FOLD)
    s = s.lower()
    # حذف «ال» على مستوى الرمز مع الحفاظ على الفواصل
    parts = re.split(r"(\s+)", s)
    parts = [p if p.isspace() else _strip_definite_article(p) for p in parts]
    s = "".join(parts)
    return _WS_RE.sub(" ", s).strip()


def normalize_tokens(text: str) -> frozenset[str]:
    """يُرجِع مجموعة الرموز المطبَّعة (للتداخل المعجمي token-overlap)."""
    norm = normalize_ar(text)
    return frozenset(_TOKEN_RE.findall(norm))


def contains_normalized(haystack: str, needle: str) -> bool:
    """هل يحتوي النص (بعد التطبيع) على العبارة (بعد التطبيع) كسلسلة فرعية؟"""
    n = normalize_ar(needle)
    if not n:
        return False
    return n in normalize_ar(haystack)


# ─────────────────────────────────────────────────────────────────────────────
# تصنيف المواضيع المرجعي (Canonical Topic Taxonomy)
#
# يربط صياغة الطالب (عربي ±ال، فرنسي، إنجليزي، دارجة) بـ:
#   • canonical_id  : معرّف داخلي ثابت (مستقل عن اللغة)
#   • db_topic      : قيمة عمود `bac_exercises.topic` في Supabase (إنجليزية)
#   • db_topic_like : نمط ILIKE مختصر للبحث في DB
#   • raw_text_terms: مصطلحات عربية مميِّزة موجودة في raw_text (للتمييز الحاسم)
#   • aliases       : أسماء بديلة (تُخزَّن **مطبَّعة**) للتعرّف على نية الطالب
#
# هذا الجسر هو ما يجعل نفس طبقة التعرّف تخدم backend الذاكرة وbackend Supabase معاً.
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CanonicalTopic:
    """موضوع رياضي مرجعي يجسر بين صياغة الطالب وقيمة قاعدة البيانات."""

    canonical_id: str
    db_topic: str
    db_topic_like: str
    raw_text_terms: tuple[str, ...]
    aliases: tuple[str, ...] = field(default_factory=tuple)

    def matches_query(self, normalized_query: str) -> bool:
        """هل يذكر الاستعلام المطبَّع أحد الأسماء البديلة لهذا الموضوع؟"""
        return any(alias and alias in normalized_query for alias in self.aliases)


def _topic(
    canonical_id: str,
    db_topic: str,
    db_topic_like: str,
    raw_text_terms: tuple[str, ...],
    raw_aliases: tuple[str, ...],
) -> CanonicalTopic:
    """يبني CanonicalTopic مع تطبيع الأسماء البديلة تلقائياً."""
    normalized_aliases = tuple(dict.fromkeys(normalize_ar(a) for a in raw_aliases if a.strip()))
    return CanonicalTopic(
        canonical_id=canonical_id,
        db_topic=db_topic,
        db_topic_like=db_topic_like,
        raw_text_terms=raw_text_terms,
        aliases=normalized_aliases,
    )


# السجل المرجعي للمواضيع. التوسّع لمليارات التمارين = إضافة مدخلات هنا (Data as Code).
CANONICAL_TOPICS: tuple[CanonicalTopic, ...] = (
    _topic(
        canonical_id="complex_numbers",
        db_topic="Complex Numbers",
        db_topic_like="%complex%",
        raw_text_terms=("الأعداد المركبة", "الأعداد العقدية", "الشكل المثلثي"),
        raw_aliases=(
            "أعداد مركبة",
            "الأعداد المركبة",
            "عدد مركب",
            "أعداد عقدية",
            "الأعداد العقدية",
            "الشكل المثلثي",
            "complex numbers",
            "complex number",
            "nombres complexes",
            "nombre complexe",
        ),
    ),
    _topic(
        canonical_id="probability",
        db_topic="Probability",
        db_topic_like="%probab%",
        raw_text_terms=("الاحتمالات", "الاحتمال", "متغير عشوائي"),
        raw_aliases=(
            "احتمالات",
            "الاحتمالات",
            "احتمال",
            "الاحتمال",
            "متغير عشوائي",
            "المتغير العشوائي",
            "probability",
            "probabilities",
            "probabilités",
            "probabilites",
            "loi de probabilité",
        ),
    ),
    _topic(
        canonical_id="numerical_functions",
        db_topic="Numerical Functions",
        db_topic_like="%function%",
        raw_text_terms=("الدوال العددية", "الدالة", "جدول التغيرات"),
        raw_aliases=(
            "دوال عددية",
            "الدوال العددية",
            "دالة عددية",
            "الدالة العددية",
            "دراسة دالة",
            "جدول التغيرات",
            "نقطة انعطاف",
            "المقارب",
            "numerical functions",
            "numerical function",
            "fonctions numériques",
            "fonctions numeriques",
            "fonction numérique",
            "etude de fonction",
        ),
    ),
)

# فهرس سريع canonical_id → CanonicalTopic
CANONICAL_BY_ID: dict[str, CanonicalTopic] = {t.canonical_id: t for t in CANONICAL_TOPICS}


def resolve_canonical_topics(query: str) -> list[CanonicalTopic]:
    """
    يُرجِع كل المواضيع المرجعية التي يذكرها الاستعلام (مرتّبة بطول الاسم الأطول أولاً).

    يستخدم التطبيع العربي على الطرفين فـ«الأعداد المركبة» تُطابِق «أعداد مركبة».
    قد يُرجِع أكثر من موضوع عند سؤال مركّب — المُستهلِك يختار الأنسب بالإشارات الأخرى.
    """
    normalized = normalize_ar(query)
    if not normalized:
        return []
    matches: list[tuple[int, CanonicalTopic]] = []
    for topic in CANONICAL_TOPICS:
        best_alias_len = 0
        for alias in topic.aliases:
            if alias and alias in normalized:
                best_alias_len = max(best_alias_len, len(alias))
        if best_alias_len:
            matches.append((best_alias_len, topic))
    # الاسم الأطول المطابِق أكثر تحديداً → أولوية أعلى
    matches.sort(key=lambda x: x[0], reverse=True)
    return [t for _, t in matches]


def primary_canonical_topic(query: str) -> CanonicalTopic | None:
    """يُرجِع الموضوع المرجعي الأكثر تحديداً للاستعلام، أو None."""
    topics = resolve_canonical_topics(query)
    return topics[0] if topics else None
