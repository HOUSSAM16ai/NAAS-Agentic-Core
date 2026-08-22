"""قلب المُتحقِّق — **مستقلّ عن المجال تماماً** (D-267 L1/L2).

⛔ لا يستورد `app/**` ولا `microservices/**` ولا `shared.curriculum` ولا
`shared.notation`. قلبٌ يعرف «الاحتمالات» ميزةٌ متنكّرة لا منتج.
"""

from __future__ import annotations

from naas_verifier.core.constraint import (
    Constraint,
    ConstraintError,
    ConstraintSet,
    Dimension,
    Outcome,
)
from naas_verifier.core.evidence import Evidence, EvidenceError, EvidenceKind
from naas_verifier.core.trajectory import Step, Trajectory, TrajectoryError
from naas_verifier.core.verdict import DimensionResult, Verdict, verify

__all__ = [
    "Constraint",
    "ConstraintError",
    "ConstraintSet",
    "Dimension",
    "DimensionResult",
    "Evidence",
    "EvidenceError",
    "EvidenceKind",
    "Outcome",
    "Step",
    "Trajectory",
    "TrajectoryError",
    "Verdict",
    "verify",
]
