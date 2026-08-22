"""الحكم + مرجع الدليل — لا درجةٌ عارية (D-267 §3).

**قاعدة الحسم:** انتهاكٌ واحد في أيّ بُعدٍ يجعل الحكم `VIOLATED`. وإن لم يقع انتهاكٌ
لكن بقي بُعدٌ **غير حاسم**، فالحكم `INCONCLUSIVE` — ⛔ لا يُرقّى إلى نجاحٍ أبداً
(D-215: انتهاء المهلة ليس نجاحاً، و«لا نعرف» تُعلَن).

⛔ مكتبة قياسية فقط.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from naas_verifier.core.constraint import Constraint, ConstraintSet, Dimension, Outcome
from naas_verifier.core.evidence import Evidence, EvidenceKind
from naas_verifier.core.trajectory import Trajectory

__all__ = ["DimensionResult", "Verdict", "verify"]


@dataclass(frozen=True)
class DimensionResult:
    """نتيجةُ بُعدٍ واحد: حكمُه، وقيوده المنتهَكة، وسببُ تركه إن تُرك."""

    dimension: Dimension
    outcome: Outcome
    violated: tuple[str, ...] = ()
    inconclusive: tuple[str, ...] = ()
    uncovered_reason: str | None = None


@dataclass(frozen=True)
class Verdict:
    """حكمٌ مربوطٌ بدليل — ⛔ ولا يحمل درجةً عارية بلا مرجع."""

    trajectory_id: str
    outcome: Outcome
    dimensions: tuple[DimensionResult, ...]
    evidence: tuple[Evidence, ...]

    @property
    def violated_dimensions(self) -> tuple[Dimension, ...]:
        return tuple(row.dimension for row in self.dimensions if row.outcome is Outcome.VIOLATED)

    def as_dict(self) -> dict[str, object]:
        return {
            "trajectory_id": self.trajectory_id,
            "outcome": self.outcome.value,
            "dimensions": [
                {
                    "dimension": row.dimension.value,
                    "outcome": row.outcome.value,
                    "violated": list(row.violated),
                    "inconclusive": list(row.inconclusive),
                    "uncovered_reason": row.uncovered_reason,
                }
                for row in self.dimensions
            ],
            "evidence": [item.as_dict() for item in self.evidence],
        }


def _evaluate_dimension(
    dimension: Dimension,
    constraints: Sequence[Constraint],
    trajectory: Trajectory,
    uncovered_reason: Mapping[Dimension, str],
) -> DimensionResult:
    if not constraints:
        # بُعدٌ متروك بتصريحٍ منطوق: يُسجَّل `INCONCLUSIVE` لا `HOLDS`. تركُ بُعدٍ
        # قرارٌ مُعلَن، ولا يجوز أن يُحسَب في صالح الوكيل تحت الاختبار.
        return DimensionResult(
            dimension=dimension,
            outcome=Outcome.INCONCLUSIVE,
            uncovered_reason=uncovered_reason.get(dimension),
        )
    violated: list[str] = []
    inconclusive: list[str] = []
    for constraint in constraints:
        result = constraint.evaluate(trajectory)
        if result is Outcome.VIOLATED:
            violated.append(constraint.constraint_id)
        elif result is Outcome.INCONCLUSIVE:
            inconclusive.append(constraint.constraint_id)
    if violated:
        outcome = Outcome.VIOLATED
    elif inconclusive:
        outcome = Outcome.INCONCLUSIVE
    else:
        outcome = Outcome.HOLDS
    return DimensionResult(
        dimension=dimension,
        outcome=outcome,
        violated=tuple(violated),
        inconclusive=tuple(inconclusive),
    )


def verify(
    trajectory: Trajectory,
    constraint_set: ConstraintSet,
    evidence: Sequence[Evidence] = (),
) -> Verdict:
    """يُقيّم الأبعاد الخمسة **كلّها** ويُصدر حكماً مربوطاً بدليل.

    الأبعاد تُقيَّم دائماً بترتيب `Dimension` — لا «أوّل يفوز»: كل بُعدٍ يُسجَّل حتى لو
    سبقه انتهاك، وإلّا فقد المشتري نصفَ التقرير الذي يدفع ثمنه.
    """
    results = tuple(
        _evaluate_dimension(
            dimension,
            constraint_set.by_dimension(dimension),
            trajectory,
            constraint_set.uncovered_reason,
        )
        for dimension in Dimension
    )
    if any(row.outcome is Outcome.VIOLATED for row in results):
        outcome = Outcome.VIOLATED
    elif any(row.outcome is Outcome.INCONCLUSIVE for row in results):
        outcome = Outcome.INCONCLUSIVE
    else:
        outcome = Outcome.HOLDS

    trace = Evidence(
        evidence_id=f"{trajectory.trajectory_id}::constraint-evaluation",
        kind=EvidenceKind.CONSTRAINT_EVALUATION,
        summary=(
            f"{len(constraint_set.constraints)} constraint(s) over "
            f"{len(results)} dimension(s); outcome={outcome.value}"
        ),
        reproduction="python -m naas_verifier.cli run --corpus ar_fr",
        source_reference="docs/architecture/NAAS_VERIFICATION_LAYER.md#2",
        payload={"language": trajectory.language, "steps": len(trajectory.steps)},
    )
    return Verdict(
        trajectory_id=trajectory.trajectory_id,
        outcome=outcome,
        dimensions=results,
        evidence=(*evidence, trace),
    )
