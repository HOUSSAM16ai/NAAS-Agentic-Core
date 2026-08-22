"""القيد كنوعٍ لا كسلسلة نصّية (D-267 §3) + الأبعاد الخمسة (L3).

⛔ **القانون الحاكم:** «نظامٌ يفحص `final outcome` وحده هو **مُصحِّح**، لا مُتحقِّق.»
لذلك `Dimension` قائمةٌ مغلقة من خمسة، و`ConstraintSet` يرفض أن يُقيَّم وهو يغطّي
أقلّ من الخمسة **إلّا بتصريحٍ منطوق** لكلّ بُعدٍ متروك (D-206 L11: الفراغ يُقرأ نجاحاً).

⛔ مكتبة قياسية فقط.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from naas_verifier.core.trajectory import Trajectory

__all__ = ["Constraint", "ConstraintError", "ConstraintSet", "Dimension", "Outcome"]


class ConstraintError(ValueError):
    """خرقُ مجالٍ في بناء القيد أو المجموعة."""


class Dimension(StrEnum):
    """الأبعاد الخمسة — مجتمعةً أو ليس تحقّقاً (L3)."""

    OBSERVABLE_OUTCOMES = "observable_outcomes"
    INTERMEDIATE_CONSTRAINTS = "intermediate_constraints"
    STATE_TRANSITIONS = "state_transitions"
    TOOL_USE = "tool_use"
    FINAL_OUTCOME = "final_outcome"


class Outcome(StrEnum):
    """⛔ `INCONCLUSIVE` ليست نجاحاً — «لا نعرف» تُعلَن ولا تُبتلَع (D-215)."""

    HOLDS = "holds"
    VIOLATED = "violated"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class Constraint:
    """قيدٌ واحد على بُعدٍ واحد.

    `predicate` تُعيد `Outcome` لا `bool`: القيد الذي لا يستطيع الحكم يجب أن يقول
    ذلك، لا أن يُرجِع `False` فيُقرأ انتهاكاً، ولا `True` فيُقرأ سلامة.
    """

    constraint_id: str
    dimension: Dimension
    description: str
    predicate: Callable[[Trajectory], Outcome]

    def __post_init__(self) -> None:
        if not self.constraint_id.strip():
            raise ConstraintError("constraint_id must not be empty")
        if not self.description.strip():
            raise ConstraintError(f"{self.constraint_id}: description must not be empty")

    def evaluate(self, trajectory: Trajectory) -> Outcome:
        """يُقيَّم القيد؛ وأيّ استثناءٍ غير متوقّع يصير `INCONCLUSIVE` لا `HOLDS`.

        بوّابةٌ تشهد بما لم تقرأ هي بالضبط ما حرّمه D-208 (`except: return []`).
        """
        try:
            result = self.predicate(trajectory)
        except Exception:
            return Outcome.INCONCLUSIVE
        if not isinstance(result, Outcome):
            raise ConstraintError(
                f"{self.constraint_id}: predicate must return Outcome, got {type(result)!r}"
            )
        return result


@dataclass(frozen=True)
class ConstraintSet:
    """مجموعةُ قيودٍ تغطّي الأبعاد الخمسة — أو تُصرِّح لماذا لا تغطّيها."""

    constraints: tuple[Constraint, ...]
    uncovered_reason: Mapping[Dimension, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for item in self.constraints:
            if item.constraint_id in seen:
                raise ConstraintError(f"duplicate constraint_id: {item.constraint_id}")
            seen.add(item.constraint_id)
        missing = set(Dimension) - self.covered - set(self.uncovered_reason)
        if missing:
            raise ConstraintError(
                "uncovered dimensions must be declared with a spoken reason: "
                f"{sorted(dim.value for dim in missing)} — checking the final outcome "
                "alone makes this a grader, not a verifier (L3)"
            )
        for dimension, reason in self.uncovered_reason.items():
            if not str(reason).strip():
                raise ConstraintError(
                    f"uncovered dimension `{dimension.value}` has an empty reason — "
                    "an empty cell reads as success (D-206 L11)"
                )

    @property
    def covered(self) -> set[Dimension]:
        return {item.dimension for item in self.constraints}

    def by_dimension(self, dimension: Dimension) -> tuple[Constraint, ...]:
        return tuple(item for item in self.constraints if item.dimension is dimension)
