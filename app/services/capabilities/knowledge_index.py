"""
فهرس قاعدة المعرفة — سجل مركزي لجميع التمارين المتاحة.

يُعرِّف هذا الملف بنية بيانات تصريحية (declarative) لكل تمرين في قاعدة المعرفة،
مما يُتيح استدعاءً دقيقاً ومنظماً بدلاً من البحث العشوائي في الملفات.

المبدأ: Data as Code — الإعداد كبيانات، لا كمنطق مُرمَّز.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.capabilities.arabic_normalize import (
    CANONICAL_TOPICS,
    normalize_ar,
)


@dataclass(frozen=True)
class ExerciseEntry:
    """
    سجل تمرين واحد في قاعدة المعرفة.

    كل حقل يُمثِّل بُعداً من أبعاد البحث الدقيق.
    """

    file_path: str
    """المسار النسبي للملف من جذر المشروع."""

    year: int
    """سنة الامتحان."""

    session: str
    """الدورة: 'الأولى' | 'الثانية' | 'عادية'."""

    subject_number: int
    """رقم الموضوع: 1 | 2 | 3."""

    exercise_number: int
    """رقم التمرين: 1 | 2 | 3 | 4."""

    branch: str
    """الشعبة: 'علوم تجريبية' | 'رياضيات' | ..."""

    topics: list[str]
    """المواضيع الرياضية المغطاة."""

    tags: list[str]
    """وسوم البحث العربية والإنجليزية."""

    has_model_answer: bool = True
    """هل يحتوي الملف على إجابة نموذجية مفصلة؟"""

    historical_note: str = ""
    """ملاحظة تاريخية خاصة بهذا الامتحان."""


# ─────────────────────────────────────────────────────────────────────────────
# السجل المركزي لجميع التمارين المتاحة في قاعدة المعرفة
# ─────────────────────────────────────────────────────────────────────────────
KNOWLEDGE_INDEX: list[ExerciseEntry] = [
    # ─── بكالوريا 2024 — الموضوع الأول ───────────────────────────────────────
    ExerciseEntry(
        file_path="knowledge_base/bac2024_math_experimental_subject1_ex1_ex2.md",
        year=2024,
        session="عادية",
        subject_number=1,
        exercise_number=1,
        branch="علوم تجريبية",
        topics=["الاحتمالات", "probability", "متغير عشوائي", "random variable"],
        tags=[
            "bac2024",
            "subject1",
            "exercise1",
            "احتمالات",
            "2024",
            "موضوع أول",
            "تمرين أول",
            "علوم تجريبية",
        ],
        has_model_answer=False,
        historical_note="",
    ),
    ExerciseEntry(
        file_path="knowledge_base/bac2024_math_experimental_subject1_ex1_ex2.md",
        year=2024,
        session="عادية",
        subject_number=1,
        exercise_number=2,
        branch="علوم تجريبية",
        topics=["الأعداد المركبة", "complex numbers", "الشكل المثلثي"],
        tags=[
            "bac2024",
            "subject1",
            "exercise2",
            "أعداد مركبة",
            "2024",
            "موضوع أول",
            "تمرين ثاني",
            "علوم تجريبية",
        ],
        has_model_answer=False,
        historical_note="",
    ),
    # ─── بكالوريا 2016 — الدورة الأولى — الموضوع الثاني ─────────────────────
    ExerciseEntry(
        file_path="knowledge_base/bac2016_s1_math_exp_subject2_ex4_numerical_functions.md",
        year=2016,
        session="الأولى",
        subject_number=2,
        exercise_number=4,
        branch="علوم تجريبية",
        topics=[
            "الدوال العددية",
            "numerical functions",
            "المشتقة",
            "derivative",
            "المقارب",
            "asymptote",
            "نقطة الانعطاف",
            "inflection point",
            "التكامل",
            "integration",
            "جدول التغيرات",
            "variation table",
        ],
        tags=[
            "bac2016",
            "2016",
            "دورة أولى",
            "session1",
            "الدورة الأولى",
            "subject2",
            "موضوع ثاني",
            "الموضوع الثاني",
            "exercise4",
            "تمرين رابع",
            "التمرين الرابع",
            "دوال عددية",
            "numerical functions",
            "علوم تجريبية",
            "experimental sciences",
            "g(x)",
            "f(x)",
            "h(x)",
            "H(x)",
            "2016_دورة_أولى",
            "استثنائية",
        ],
        has_model_answer=True,
        historical_note=(
            "2016 هي السنة الوحيدة في تاريخ بكالوريا الجزائر التي شهدت دورتين "
            "امتحانيتين (الأولى والثانية). هذا التمرين يخص الدورة الأولى حصراً."
        ),
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# جسر المواضيع المرجعية (Canonical Topic Bridge)
#
# لكل ExerciseEntry نحسب مجموعة canonical_id التي تنتمي إليها، بمطابقة مواضيعه
# (entry.topics) مع أسماء CanonicalTopic البديلة بعد التطبيع. يُحسب مرة واحدة
# ويُخزَّن (cache) لأن KNOWLEDGE_INDEX ثابت. هذه هي الإشارة الأقوى للتمييز.
# ─────────────────────────────────────────────────────────────────────────────
_ENTRY_CANONICAL_CACHE: dict[int, frozenset[str]] = {}


def entry_canonical_ids(entry: ExerciseEntry) -> frozenset[str]:
    """يُرجِع معرّفات المواضيع المرجعية التي ينتمي إليها التمرين (مطبَّعة، مخزَّنة)."""
    key = id(entry)
    cached = _ENTRY_CANONICAL_CACHE.get(key)
    if cached is not None:
        return cached
    normalized_topics = " ".join(normalize_ar(t) for t in entry.topics)
    ids = {
        topic.canonical_id
        for topic in CANONICAL_TOPICS
        if any(alias and alias in normalized_topics for alias in topic.aliases)
    }
    result = frozenset(ids)
    _ENTRY_CANONICAL_CACHE[key] = result
    return result


# أوزان الإشارات (Signal Weights). الموضوع المرجعي يجب أن يهيمن على تعادل السنة وحدها.
_W_YEAR = 10
_W_SESSION = 5
_W_SUBJECT = 8
_W_EXERCISE = 8
_W_BRANCH = 3
_W_CANONICAL_TOPIC = 16  # > _W_YEAR — يكسر «تعادل تمرينَي 2024 على السنة»
_W_TOPIC_KW = 2
_W_TAG_KW = 1


def search_exercises(
    *,
    year: int | None = None,
    session: str | None = None,
    subject_number: int | None = None,
    exercise_number: int | None = None,
    branch: str | None = None,
    topic_keywords: list[str] | None = None,
    tag_keywords: list[str] | None = None,
    canonical_topic_id: str | None = None,
) -> list[ExerciseEntry]:
    """
    يبحث في فهرس قاعدة المعرفة بمعايير متعددة مع تسجيل متعدد الإشارات.

    يُرجع قائمة التمارين المطابقة مرتبة حسب دقة التطابق.
    المعايير غير المحددة (None) لا تُطبَّق في الفلترة.

    إصلاح ISS (أداة التعريف «ال»): مطابقة المواضيع تتم على الصورة **المطبَّعة**
    عربياً (`normalize_ar`) فـ«الأعداد المركبة» تطابق «أعداد مركبة». كما أُضيفت
    إشارة `canonical_topic_id` بوزن أعلى من السنة لتكسر تعادل تمرينَي 2024.

    الترتيب حتمي: (score, الانتماء للموضوع المرجعي, -exercise_number) فلا يعتمد
    النتيجة على ترتيب القائمة عند التعادل.
    """
    results: list[tuple[int, int, int, ExerciseEntry]] = []

    for entry in KNOWLEDGE_INDEX:
        score = 0

        if year is not None and entry.year == year:
            score += _W_YEAR
        elif year is not None:
            continue  # السنة إلزامية إذا حُددت

        if session is not None:
            session_norm = session.strip().lower()
            entry_session_norm = entry.session.strip().lower()
            if session_norm in entry_session_norm or entry_session_norm in session_norm:
                score += _W_SESSION

        if subject_number is not None and entry.subject_number == subject_number:
            score += _W_SUBJECT

        if exercise_number is not None and entry.exercise_number == exercise_number:
            score += _W_EXERCISE

        if branch is not None:
            branch_norm = branch.strip().lower()
            entry_branch_norm = entry.branch.strip().lower()
            if branch_norm in entry_branch_norm or entry_branch_norm in branch_norm:
                score += _W_BRANCH

        # الإشارة الأقوى: تطابق الموضوع المرجعي (يكسر تعادل السنة)
        entry_canon = entry_canonical_ids(entry)
        canonical_hit = 1 if (canonical_topic_id and canonical_topic_id in entry_canon) else 0
        if canonical_hit:
            score += _W_CANONICAL_TOPIC

        if topic_keywords:
            for kw in topic_keywords:
                kw_norm = normalize_ar(kw)
                if kw_norm and any(kw_norm in normalize_ar(topic) for topic in entry.topics):
                    score += _W_TOPIC_KW

        if tag_keywords:
            for kw in tag_keywords:
                kw_norm = normalize_ar(kw)
                if kw_norm and any(kw_norm in normalize_ar(tag) for tag in entry.tags):
                    score += _W_TAG_KW

        if score > 0:
            # مفاتيح ترتيب حتمية: score ثم تطابق الموضوع ثم exercise_number تصاعدياً
            results.append((score, canonical_hit, -entry.exercise_number, entry))

    results.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [entry for *_, entry in results]


def find_best_match(query_tags: list[str]) -> ExerciseEntry | None:
    """
    يجد أفضل تمرين مطابق لقائمة وسوم البحث.

    يُستخدم عند الاستدعاء السريع بدون معايير محددة.
    """
    if not query_tags:
        return None

    best_score = 0
    best_secondary = 0
    best_entry: ExerciseEntry | None = None

    for entry in KNOWLEDGE_INDEX:
        score = 0
        all_entry_tags = [normalize_ar(t) for t in entry.tags + entry.topics]

        for tag in query_tags:
            tag_norm = normalize_ar(tag)
            if not tag_norm:
                continue
            for entry_tag in all_entry_tags:
                if tag_norm in entry_tag or entry_tag in tag_norm:
                    score += 1
                    break

        # كسر التعادل: التمرين ذو الرقم الأعلى ثانوياً (حتمي، لا يعتمد ترتيب القائمة)
        secondary = entry.exercise_number
        if score > best_score or (score == best_score and score > 0 and secondary > best_secondary):
            best_score = score
            best_secondary = secondary
            best_entry = entry

    return best_entry if best_score > 0 else None
