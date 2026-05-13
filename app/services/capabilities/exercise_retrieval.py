"""
قدرة استرجاع التمارين التعليمية — نظام موحد ومنظم.

يعتمد هذا النظام على فهرس مركزي (knowledge_index.py) لاستدعاء التمارين
بدقة عالية بدلاً من البحث العشوائي في الملفات.

المبدأ: كل تمرين له هوية فريدة (سنة + دورة + موضوع + رقم التمرين).
الاستدعاء يكون دائماً بمعايير محددة، لا بكلمات مفتاحية عشوائية.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.capabilities.knowledge_index import (
    ExerciseEntry,
    find_best_match,
    search_exercises,
)

# ─────────────────────────────────────────────────────────────────────────────
# أنماط النية السلبية — تشير إلى أن المستخدم يريد شرحاً أو مساعدة وليس جلب محتوى.
# عند وجود أي منها، يُلغى الاسترجاع حتى لو ذُكرت كلمة "تمرين".
# ─────────────────────────────────────────────────────────────────────────────
_EXPLANATION_INTENT_PATTERNS: tuple[str, ...] = (
    # طلب الشرح الصريح
    "اشرح",
    "شرح",
    "وضح",
    "فسر",
    "explain",
    "describe",
    # طلب المساعدة في حل
    "ساعدني",
    "ساعد",
    "help me",
    "help with",
    # الإشارة إلى محتوى مُقدَّم من المستخدم ("هذا التمرين" = المستخدم يملك التمرين)
    "هذا التمرين",
    "هذه المسألة",
    "هذا السؤال",
    "هذا الجزء",
    "الجزء أ",
    "الجزء ب",
    "الجزء ج",
    "الجزء الأول",
    "الجزء الثاني",
    "الجزء الثالث",
    "part a",
    "part b",
    "part c",
    # طلب الفهم المفاهيمي
    "كيف",
    "لماذا",
    "ما هو",
    "ما هي",
    "ما معنى",
    "ما مفهوم",
    "how",
    "why",
    "what is",
    "what are",
    "what does",
)

# ─────────────────────────────────────────────────────────────────────────────
# أنماط النية الإيجابية — تشير إلى طلب جلب محتوى من قاعدة المعرفة.
# يجب أن تكون محددة جداً لتجنب التفعيل الخاطئ.
# ─────────────────────────────────────────────────────────────────────────────
_RETRIEVAL_INTENT_PATTERNS: tuple[str, ...] = (
    # طلب صريح لتمرين بكالوريا
    "تمرين بكالوريا",
    "تمارين بكالوريا",
    "بكالوريا",
    "bac",
    "baccalauréat",
    # طلب تمرين محدد بموضوع
    "تمرين احتمالات",
    "تمارين احتمالات",
    "exercise probability",
    "probability exercise",
    "تمرين دوال",
    "دوال عددية",
    "numerical functions",
    "تمرين أعداد مركبة",
    "أعداد مركبة",
    "complex numbers",
    # طلب موضوع امتحان
    "الموضوع الأول",
    "الموضوع الثاني",
    "الموضوع الثالث",
    "subject 1",
    "subject 2",
    "subject 3",
    # طلب تمرين مُرقَّم بالترتيب
    "التمرين الأول",
    "التمرين الثاني",
    "التمرين الثالث",
    "التمرين الرابع",
    "exercise 1",
    "exercise 2",
    "exercise 3",
    "exercise 4",
    # طلب صريح للجلب
    "أعطني تمرين",
    "أعطني تمارين",
    "أريد تمرين",
    "أريد تمارين",
    "give me exercise",
    "give me exercises",
    "fetch exercise",
    "get exercise",
    "ابحث عن تمرين",
    "جلب تمرين",
    # الدورة الأولى / الثانية (خاص بـ 2016)
    "الدورة الأولى",
    "الدورة الثانية",
    "دورة أولى",
    "دورة ثانية",
    "session 1",
    "session 2",
)

# أنماط استخراج السنة والدورة والموضوع والتمرين
_SESSION_PATTERNS: dict[str, str] = {
    "الدورة الأولى": "الأولى",
    "الدورة الثانية": "الثانية",
    "دورة أولى": "الأولى",
    "دورة ثانية": "الثانية",
    "session 1": "الأولى",
    "session 2": "الثانية",
}

_SUBJECT_PATTERNS: dict[str, int] = {
    "الموضوع الأول": 1,
    "الموضوع الثاني": 2,
    "الموضوع الثالث": 3,
    "subject 1": 1,
    "subject 2": 2,
    "subject 3": 3,
    "subject1": 1,
    "subject2": 2,
    "subject3": 3,
}

_EXERCISE_PATTERNS: dict[str, int] = {
    "التمرين الأول": 1,
    "التمرين الثاني": 2,
    "التمرين الثالث": 3,
    "التمرين الرابع": 4,
    "exercise 1": 1,
    "exercise 2": 2,
    "exercise 3": 3,
    "exercise 4": 4,
}

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "احتمالات": ["الاحتمالات", "probability"],
    "probability": ["الاحتمالات", "probability"],
    "دوال عددية": ["الدوال العددية", "numerical functions"],
    "numerical functions": ["الدوال العددية", "numerical functions"],
    "أعداد مركبة": ["الأعداد المركبة", "complex numbers"],
    "complex numbers": ["الأعداد المركبة", "complex numbers"],
    "تكامل": ["التكامل", "integration"],
    "integration": ["التكامل", "integration"],
    "مشتقة": ["المشتقة", "derivative"],
    "derivative": ["المشتقة", "derivative"],
}

# "تمرين" أو "exercise" متبوعاً برقم مباشرة
_EXERCISE_WITH_NUMBER_RE = re.compile(r"(تمرين|تمارين|exercise)\s*\d+", re.IGNORECASE)

# سنة دراسية (2020–2030)
_YEAR_RE = re.compile(r"\b20[2-3]\d\b")


class ExerciseRetrievalRequest(RobustBaseModel):
    """طلب استرجاع تعليمي منسّق."""

    question: str = Field(..., min_length=1)


class ExerciseRetrievalDecision(RobustBaseModel):
    """قرار التعرف على نية الاسترجاع التعليمي."""

    recognized: bool
    reason: str = ""
    matched_entry: ExerciseEntry | None = None

    model_config = {"arbitrary_types_allowed": True}


class ExerciseRetrievalResult(RobustBaseModel):
    """نتيجة استرجاع التمارين مع semantics واضحة."""

    success: bool
    message: str | None = None
    entry: ExerciseEntry | None = None

    model_config = {"arbitrary_types_allowed": True}


def _has_explanation_intent(normalized: str) -> bool:
    """يكشف عن نية الشرح أو المساعدة — تلغي الاسترجاع عند وجودها."""
    return any(pattern in normalized for pattern in _EXPLANATION_INTENT_PATTERNS)


def _has_retrieval_intent(normalized: str) -> bool:
    """يكشف عن نية جلب محتوى من قاعدة المعرفة بشكل صريح."""
    if any(pattern in normalized for pattern in _RETRIEVAL_INTENT_PATTERNS):
        return True
    if _EXERCISE_WITH_NUMBER_RE.search(normalized):
        return True
    # "تمرين" + سنة = طلب تمرين من سنة محددة
    return bool(("تمرين" in normalized or "exercise" in normalized) and _YEAR_RE.search(normalized))


def _extract_year(normalized: str) -> int | None:
    """يستخرج السنة من النص."""
    match = _YEAR_RE.search(normalized)
    return int(match.group()) if match else None


def _extract_session(normalized: str) -> str | None:
    """يستخرج الدورة من النص."""
    for pattern, session in _SESSION_PATTERNS.items():
        if pattern in normalized:
            return session
    return None


def _extract_subject_number(normalized: str) -> int | None:
    """يستخرج رقم الموضوع من النص."""
    for pattern, number in _SUBJECT_PATTERNS.items():
        if pattern in normalized:
            return number
    return None


def _extract_exercise_number(normalized: str) -> int | None:
    """يستخرج رقم التمرين من النص."""
    for pattern, number in _EXERCISE_PATTERNS.items():
        if pattern in normalized:
            return number
    match = _EXERCISE_WITH_NUMBER_RE.search(normalized)
    if match:
        digits = re.search(r"\d+", match.group())
        if digits:
            return int(digits.group())
    return None


def _extract_topic_keywords(normalized: str) -> list[str]:
    """يستخرج الكلمات المفتاحية للموضوع الرياضي."""
    found: list[str] = []
    for keyword, topics in _TOPIC_KEYWORDS.items():
        if keyword in normalized:
            found.extend(topics)
    return list(set(found))


def _find_matching_entry(normalized: str) -> ExerciseEntry | None:
    """
    يبحث في فهرس قاعدة المعرفة عن أفضل تمرين مطابق للسؤال.

    يستخرج المعايير من النص ثم يستدعي search_exercises.
    """
    year = _extract_year(normalized)
    session = _extract_session(normalized)
    subject_number = _extract_subject_number(normalized)
    exercise_number = _extract_exercise_number(normalized)
    topic_keywords = _extract_topic_keywords(normalized)

    results = search_exercises(
        year=year,
        session=session,
        subject_number=subject_number,
        exercise_number=exercise_number,
        topic_keywords=topic_keywords if topic_keywords else None,
    )

    if results:
        return results[0]

    # بحث بالوسوم إذا لم تُوجد نتائج بالمعايير
    tag_keywords = [w for w in normalized.split() if len(w) > 2]
    return find_best_match(tag_keywords)


def detect_exercise_retrieval(request: ExerciseRetrievalRequest) -> ExerciseRetrievalDecision:
    """
    يتعرف على أسئلة الاسترجاع التعليمي بدقة عالية لتجنب التفعيل الخاطئ.

    المنطق ثلاثي المراحل:
    1. نية الشرح/المساعدة → لا استرجاع (حتى لو ذُكر "تمرين" أو "احتمالات")
    2. نية الجلب الصريحة → استرجاع مع تحديد التمرين من الفهرس
    3. حالة الشك → لا استرجاع (LangGraph يعالج الحالات الغامضة أفضل)

    يحل ISS-038: كلمة "تمرين" في سياق الشرح كانت تُطلق استرجاع تمرين
    الاحتمالات بشكل ثابت بغض النظر عن السياق.
    """
    normalized = request.question.strip().lower()

    # الأولوية الأولى: نية الشرح تلغي الاسترجاع دائماً
    if _has_explanation_intent(normalized):
        return ExerciseRetrievalDecision(
            recognized=False,
            reason="explanation_intent_detected",
        )

    # الأولوية الثانية: نية الجلب الصريحة
    if _has_retrieval_intent(normalized):
        matched_entry = _find_matching_entry(normalized)
        return ExerciseRetrievalDecision(
            recognized=True,
            reason="retrieval_intent_detected",
            matched_entry=matched_entry,
        )

    # الحالة الافتراضية: لا استرجاع — اللجوء إلى LangGraph
    return ExerciseRetrievalDecision(
        recognized=False,
        reason="no_clear_retrieval_intent",
    )


def load_exercise_content(entry: ExerciseEntry) -> str | None:
    """
    يحمِّل محتوى ملف التمرين من قاعدة المعرفة.

    يُرجع المحتوى كنص أو None إذا لم يُوجد الملف.
    """
    project_root = Path(__file__).resolve().parents[3]
    file_path = project_root / entry.file_path

    if not file_path.exists():
        return None

    return file_path.read_text(encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# عرض التمرين بشكل نظيف للطالب (D-048)
#
# قبل ISS-051: الاسترجاع كان يُرجع كامل محتوى الملف (YAML + نص التمرين +
# عناصر الإجابة النموذجية) مما يُسبب فوضى بصرية وكشف الحلول قبل الأوان.
#
# بعد ISS-051: نُخرج فقط بطاقة الامتحان + نص التمرين، ونحذف:
#   1. YAML frontmatter
#   2. كل ما يلي "عناصر الإجابة" أو "الحل" أو "Solution"
#   3. وسوم البحث في نهاية الملف
# ─────────────────────────────────────────────────────────────────────────────

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

# قواطع نهاية نص التمرين — أي قسم يبدأ بأحد هذه العناوين يُحذف وما بعده
_SOLUTION_SECTION_MARKERS: tuple[str, ...] = (
    "## عناصر الإجابة",
    "## الإجابة النموذجية",
    "## الحل",
    "## الإجابة",
    "## شرح الحل",
    "## Solution",
    "## Model Answer",
    "## Answer",
    "## وسوم البحث",
    "## Tags",
    "### الجزء I",  # بداية الشرح المفصَّل
    "### الجزء II",
    "### الجزء III",
)


def _strip_frontmatter(content: str) -> str:
    """يحذف YAML frontmatter من بداية ملف markdown."""
    return _FRONTMATTER_RE.sub("", content, count=1).lstrip()


def _trim_at_solution(content: str) -> str:
    """يقطع المحتوى عند أول قسم يحوي عناصر الإجابة/الحل/الوسوم."""
    cut_index: int | None = None
    for marker in _SOLUTION_SECTION_MARKERS:
        idx = content.find(marker)
        if idx == -1:
            continue
        if cut_index is None or idx < cut_index:
            cut_index = idx
    if cut_index is None:
        return content.rstrip()
    return content[:cut_index].rstrip()


def format_exercise_for_display(entry: ExerciseEntry, raw_content: str) -> str:
    """
    يُهيِّئ محتوى التمرين لعرض نظيف للطالب — فقط نص التمرين، بدون YAML أو حل.

    يحل ISS-051:
      - YAML frontmatter يظهر للطالب
      - عناصر الإجابة النموذجية تُكشف قبل أن يحل الطالب
      - وسوم البحث في الأسفل
      - أكثر من تمرين يظهر في رد واحد (لأن الـ wide-net retrieval كان يقرأ كل
        ملفات .md؛ الآن نقرأ ملفاً واحداً مطابقاً بالضبط)

    Args:
        entry: السجل المطابق من knowledge_index.
        raw_content: محتوى الملف الخام (مع YAML + الحل).

    Returns:
        محتوى نظيف يحوي: عنوان + بطاقة الامتحان + نص التمرين فقط.
    """
    if not raw_content:
        return ""
    no_frontmatter = _strip_frontmatter(raw_content)
    questions_only = _trim_at_solution(no_frontmatter)
    return questions_only.strip()


def make_result(raw_result: str | None, entry: ExerciseEntry | None = None) -> ExerciseRetrievalResult:
    """يحوّل النتيجة الخام إلى عقد موحد دون كسر السلوك التاريخي."""
    if raw_result is None or not raw_result.strip():
        return ExerciseRetrievalResult(success=False)
    return ExerciseRetrievalResult(success=True, message=raw_result, entry=entry)
