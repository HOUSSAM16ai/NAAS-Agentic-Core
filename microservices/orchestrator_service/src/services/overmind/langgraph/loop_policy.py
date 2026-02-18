from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoopPolicy:
    """
    سياسة التحكم في الحلقات التكرارية داخل LangGraph.
    """

    max_iterations: int = 2
    approval_score: float = 0.75


def should_continue_loop(
    *,
    audit: dict[str, object] | None,
    iteration: int,
    policy: LoopPolicy,
) -> bool:
    """
    تحديد ما إذا كانت الدورة تحتاج إلى إعادة تشغيل.
    """
    if iteration >= policy.max_iterations:
        return False

    if not audit:
        return False

    approved = bool(audit.get("approved"))
    score_value = audit.get("score", 0.0)
    try:
        score = float(score_value)
    except (TypeError, ValueError):
        score = 0.0

    return not (approved and score >= policy.approval_score)
