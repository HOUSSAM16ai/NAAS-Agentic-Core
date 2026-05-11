"""
مُصنِّف النوايا لـ content-retrieval-skill — الخطوة 11.

المسؤولية الوحيدة: تحديد نية الطلب بدقة عالية.

Contract:
  Input:  str (سؤال الطالب)
  Output: IntentResult(intent, confidence, reason)

Intents:
  "retrieval"    — طلب جلب محتوى من قاعدة المعرفة (BAC exercises)
  "explanation"  — طلب شرح أو مساعدة (لا استرجاع)
  "unknown"      — غير محدد → يُعالَج بـ LangGraph

Anti-patterns (ISS-038):
  - كلمة "تمرين" وحدها لا تكفي لتفعيل الاسترجاع
  - سياق الشرح يلغي الاسترجاع دائماً
  - الشك → لا استرجاع (LangGraph أفضل للحالات الغامضة)
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IntentResult:
    """نتيجة تصنيف النية — contract ثابت."""

    intent: str  # "retrieval" | "explanation" | "unknown"
    confidence: float  # 0.0 – 1.0
    reason: str  # سبب القرار للتتبع والتشخيص


# ── أنماط نية الشرح (الأولوية الأولى — تلغي الاسترجاع) ──────────────────────
_EXPLANATION_PATTERNS: tuple[str, ...] = (
    # طلب الشرح الصريح
    "اشرح",
    "شرح",
    "وضح",
    "فسر",
    "explain",
    "describe",
    # طلب المساعدة
    "ساعدني",
    "ساعد",
    "help me",
    "help with",
    # إشارة لمحتوى مُقدَّم من المستخدم
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

# ── أنماط نية الاسترجاع الصريحة (الأولوية الثانية) ──────────────────────────
_RETRIEVAL_PATTERNS: tuple[str, ...] = (
    # بكالوريا صريحة
    "تمرين بكالوريا",
    "تمارين بكالوريا",
    "بكالوريا",
    "bac",
    "baccalauréat",
    # موضوع محدد
    "تمرين احتمالات",
    "تمارين احتمالات",
    "exercise probability",
    "probability exercise",
    # موضوع امتحان
    "الموضوع الأول",
    "الموضوع الثاني",
    "الموضوع الثالث",
    "subject 1",
    "subject 2",
    "subject 3",
    # تمرين مُرقَّم
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

# تمرين/exercise + رقم مباشر
_EXERCISE_NUMBER_RE = re.compile(r"(تمرين|تمارين|exercise)\s*\d+", re.IGNORECASE)

# سنة دراسية (2020–2030)
_YEAR_RE = re.compile(r"\b20[2-3]\d\b")


def classify_intent(question: str) -> IntentResult:
    """
    يُصنِّف نية الطلب بمنطق ثلاثي المراحل.

    المرحلة 1: نية الشرح → explanation (تلغي الاسترجاع دائماً)
    المرحلة 2: نية الجلب الصريحة → retrieval
    المرحلة 3: الشك → unknown (LangGraph يعالجه)

    هذا المنطق يحل ISS-038: كلمة "تمرين" في سياق الشرح
    كانت تُطلق استرجاع تمرين الاحتمالات بشكل ثابت.
    """
    normalized = question.strip().lower()

    # ── المرحلة 1: نية الشرح تلغي الاسترجاع ─────────────────────────────────
    for pattern in _EXPLANATION_PATTERNS:
        if pattern in normalized:
            return IntentResult(
                intent="explanation",
                confidence=0.95,
                reason=f"explanation_pattern_matched: '{pattern}'",
            )

    # ── المرحلة 2: نية الجلب الصريحة ─────────────────────────────────────────
    for pattern in _RETRIEVAL_PATTERNS:
        if pattern in normalized:
            return IntentResult(
                intent="retrieval",
                confidence=0.90,
                reason=f"retrieval_pattern_matched: '{pattern}'",
            )

    if _EXERCISE_NUMBER_RE.search(normalized):
        return IntentResult(
            intent="retrieval",
            confidence=0.85,
            reason="exercise_number_pattern_matched",
        )

    if ("تمرين" in normalized or "exercise" in normalized) and _YEAR_RE.search(normalized):
        return IntentResult(
            intent="retrieval",
            confidence=0.80,
            reason="exercise_with_year_matched",
        )

    # ── المرحلة 3: غير محدد ───────────────────────────────────────────────────
    return IntentResult(
        intent="unknown",
        confidence=0.50,
        reason="no_clear_intent_detected",
    )
