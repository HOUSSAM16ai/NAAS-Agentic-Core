"""قدرة استرجاع التمارين التعليمية بعقد صريح وتدهور عادل متوافق مع الواجهات."""

from __future__ import annotations

import re

from pydantic import Field

from app.core.schemas import RobustBaseModel

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
)

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


class ExerciseRetrievalResult(RobustBaseModel):
    """نتيجة استرجاع التمارين مع semantics واضحة."""

    success: bool
    message: str | None = None


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


def detect_exercise_retrieval(request: ExerciseRetrievalRequest) -> ExerciseRetrievalDecision:
    """
    يتعرف على أسئلة الاسترجاع التعليمي بدقة عالية لتجنب التفعيل الخاطئ.

    المنطق ثلاثي المراحل:
    1. نية الشرح/المساعدة → لا استرجاع (حتى لو ذُكر "تمرين" أو "احتمالات")
    2. نية الجلب الصريحة → استرجاع
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
        return ExerciseRetrievalDecision(
            recognized=True,
            reason="retrieval_intent_detected",
        )

    # الحالة الافتراضية: لا استرجاع — اللجوء إلى LangGraph
    return ExerciseRetrievalDecision(
        recognized=False,
        reason="no_clear_retrieval_intent",
    )


def make_result(raw_result: str | None) -> ExerciseRetrievalResult:
    """يحوّل النتيجة الخام إلى عقد موحد دون كسر السلوك التاريخي."""
    if raw_result is None or not raw_result.strip():
        return ExerciseRetrievalResult(success=False)
    return ExerciseRetrievalResult(success=True, message=raw_result)
