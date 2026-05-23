"""
آلة الحالة المحدودة الإعلانية (Declarative Pedagogical FSM).

Protocol V44.0 §III: الموجِّه التربوي يعمل كـ FSM صارم حتمي.
الانتقالات مُعرَّفة كبيانات (data) لا كمنطق if/else — قابلة للاختبار
والفحص والتحقق الآلي.

قانون الانتقال:
    - الانتقالات غير المسموح بها لا تُنفَّذ صامتةً — تُعيد الحالة الحالية
      مع تسجيل تحذير (controlled fallback).
    - كل انتقال يُسجَّل في سجل الانتقالات للتتبع والتشخيص.
"""

from __future__ import annotations

import logging
from enum import StrEnum

logger = logging.getLogger("cogniforge.aek.fsm")


class CognitiveState(StrEnum):
    """
    حالات الآلة المحدودة التربوية.

    كل حالة تمثّل وضعاً معرفياً مختلفاً للمتعلّم — لا وضعاً للواجهة.
    الواجهة تُقرِّر كيف تُصيِّر كل حالة (carousel، accordion، animation...).
    """

    STANDARD = "STANDARD"
    """الوضع الافتراضي — سؤال مباشر، إجابة منظَّمة."""

    CONFUSION = "CONFUSION"
    """الطالب يُعبِّر عن حيرة أو عدم فهم."""

    EMOTIONAL_RECOVERY = "EMOTIONAL_RECOVERY"
    """استعادة الاستقرار المعرفي — تخفيف الحِمل، تبسيط التجريد."""

    VISUAL_INTUITION = "VISUAL_INTUITION"
    """بناء الحدس البصري قبل الصياغة الرياضية."""

    STEP_REASONING = "STEP_REASONING"
    """التفكير خطوة بخطوة — تسلسل منطقي محكوم."""

    FORMAL_MATH = "FORMAL_MATH"
    """الصياغة الرياضية الرسمية — LaTeX، برهان، نتيجة."""

    DIRECT_ANSWER = "DIRECT_ANSWER"
    """إجابة مباشرة مختصرة — للمتعلّم المتقدّم أو السؤال البسيط."""


# ─── مصفوفة الانتقالات الإعلانية ────────────────────────────────────────────
#
# هذه البيانات هي المصدر الوحيد للحقيقة حول الانتقالات المسموح بها.
# أي تعديل على منطق التوجيه يجب أن يمرّ من هنا — لا if/else مبعثرة.

ALLOWED_TRANSITIONS: dict[CognitiveState, list[CognitiveState]] = {
    CognitiveState.STANDARD: [
        CognitiveState.CONFUSION,
        CognitiveState.DIRECT_ANSWER,
        CognitiveState.VISUAL_INTUITION,
        CognitiveState.STEP_REASONING,
    ],
    CognitiveState.CONFUSION: [
        CognitiveState.EMOTIONAL_RECOVERY,
        CognitiveState.VISUAL_INTUITION,
    ],
    CognitiveState.EMOTIONAL_RECOVERY: [
        CognitiveState.VISUAL_INTUITION,
        CognitiveState.STEP_REASONING,
    ],
    CognitiveState.VISUAL_INTUITION: [
        CognitiveState.STEP_REASONING,
        CognitiveState.CONFUSION,
        CognitiveState.FORMAL_MATH,
    ],
    CognitiveState.STEP_REASONING: [
        CognitiveState.FORMAL_MATH,
        CognitiveState.CONFUSION,
        CognitiveState.VISUAL_INTUITION,
    ],
    CognitiveState.FORMAL_MATH: [
        CognitiveState.STANDARD,
        CognitiveState.CONFUSION,
    ],
    CognitiveState.DIRECT_ANSWER: [
        CognitiveState.STANDARD,
        CognitiveState.CONFUSION,
    ],
}


def transition(
    current: CognitiveState,
    target: CognitiveState,
) -> CognitiveState:
    """
    يُنفِّذ انتقالاً معرفياً محكوماً.

    إذا كان الانتقال مسموحاً به → يُعيد الحالة الهدف.
    إذا كان ممنوعاً → يُسجِّل تحذيراً ويُعيد الحالة الحالية (controlled fallback).

    Args:
        current: الحالة المعرفية الحالية.
        target: الحالة المعرفية المطلوبة.

    Returns:
        الحالة الفعلية بعد محاولة الانتقال.
    """
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if target in allowed:
        logger.debug("aek_fsm_transition: %s → %s", current.value, target.value)
        return target

    logger.warning(
        "aek_fsm_invalid_transition: %s → %s (not in %s) — staying at %s",
        current.value,
        target.value,
        [s.value for s in allowed],
        current.value,
    )
    return current


def is_valid_transition(current: CognitiveState, target: CognitiveState) -> bool:
    """يتحقق من صحة الانتقال بدون تنفيذه."""
    return target in ALLOWED_TRANSITIONS.get(current, [])
