"""
النوايا التربوية (Cognitive Intents) — Protocol V44.0 §IV.

الخلفية تُصدِر نوايا معرفية فقط — لا تُملي تنفيذ الواجهة.
الواجهة وحدها تُقرِّر: carousel، accordion، animation، timeline...

قانون الفصل:
    الخلفية تحكم المعنى (meaning).
    الواجهة تحكم التجلّي (manifestation).
"""

from __future__ import annotations

from enum import StrEnum


class CognitiveIntent(StrEnum):
    """
    النوايا التربوية الصادرة من النواة التعليمية.

    كل نية تصف *ماذا يحتاج المتعلّم معرفياً* — لا *كيف تُعرَض*.
    """

    VISUAL_INTUITION = "VISUAL_INTUITION"
    """بناء الحدس البصري — صور ذهنية، استعارات، تمثيلات مرئية."""

    STEP_REASONING = "STEP_REASONING"
    """تفكير خطوة بخطوة — تسلسل منطقي محكوم مع تبرير كل خطوة."""

    FORMAL_MATH = "FORMAL_MATH"
    """صياغة رياضية رسمية — LaTeX، برهان، نتيجة نهائية."""

    IMPOSSIBLE_CASE = "IMPOSSIBLE_CASE"
    """حالة مستحيلة محلية — تُعزَل جراحياً دون تدمير الحالة الأم."""

    EMOTIONAL_RECOVERY = "EMOTIONAL_RECOVERY"
    """استعادة الاستقرار المعرفي — تخفيف الحِمل، تبسيط التجريد."""

    INTERACTIVE_SIMULATION = "INTERACTIVE_SIMULATION"
    """محاكاة تفاعلية — الطالب يُجرِّب ويكتشف بنفسه."""

    DIRECT_ANSWER = "DIRECT_ANSWER"
    """إجابة مباشرة مختصرة — للمتعلّم المتقدّم أو السؤال الواضح."""


# ─── خريطة الحالة → النية الافتراضية ─────────────────────────────────────────
#
# عند دخول حالة معرفية جديدة، هذه هي النية الافتراضية المُصدَرة.
# يمكن للـ kernel تجاوزها بناءً على cognitive_load_index وlearner_capability.

from app.services.aek.fsm import CognitiveState

DEFAULT_INTENT_FOR_STATE: dict[CognitiveState, CognitiveIntent] = {
    CognitiveState.STANDARD: CognitiveIntent.STEP_REASONING,
    CognitiveState.CONFUSION: CognitiveIntent.VISUAL_INTUITION,
    CognitiveState.EMOTIONAL_RECOVERY: CognitiveIntent.EMOTIONAL_RECOVERY,
    CognitiveState.VISUAL_INTUITION: CognitiveIntent.VISUAL_INTUITION,
    CognitiveState.STEP_REASONING: CognitiveIntent.STEP_REASONING,
    CognitiveState.FORMAL_MATH: CognitiveIntent.FORMAL_MATH,
    CognitiveState.DIRECT_ANSWER: CognitiveIntent.DIRECT_ANSWER,
}
