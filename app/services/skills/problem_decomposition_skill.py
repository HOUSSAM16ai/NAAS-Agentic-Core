"""ProblemDecompositionSkill — حل المشكلات (D-181).

CLAUDE.md §0.5. حلّ المشكلة = **تفكيكها** لا تسليم الجواب: مراحل بوليا الأربع
(افهم → خطّط → نفّذ → راجع) + ترتيب تنفيذ حتمي على التبعيّات (فرز طوبولوجي عبر
`app/core/reasoning/decomposition`). يُعطي الطالب الخطوة *التالية* الناقصة فقط.

## القياس (Prometheus)
- `cogniforge_skill_problem_decomposition_total{status}` (counter)
- `cogniforge_skill_problem_decomposition_duration_seconds` (histogram)
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import Field

from app.core.reasoning import decomposition as dec_mod
from app.core.reasoning.errors import ReasoningError
from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from app.services.skills.doctrine import PROBLEM_DECOMPOSITION_DOCTRINE_VERSION

_INVOCATIONS = skill_counter(
    "cogniforge_skill_problem_decomposition_total",
    "ProblemDecompositionSkill invocations",
    ("status",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_problem_decomposition_duration_seconds",
    "ProblemDecompositionSkill duration (seconds)",
)


class SubGoalSpec(RobustBaseModel):
    """خطوة مُدخَلة: معرّف + وصف + مرحلة بوليا + تبعيّات."""

    id: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="", max_length=500)
    phase: str = Field(default="execute", max_length=16)
    depends_on: list[str] = Field(default_factory=list, max_length=32)


class ProblemDecompositionInput(RobustBaseModel):
    """مدخلات التفكيك — نصّ المشكلة + (اختياري) خطوات صريحة بتبعيّاتها."""

    problem: str = Field(..., min_length=1, max_length=2000)
    subgoals: list[SubGoalSpec] = Field(default_factory=list, max_length=64)


class ProblemDecompositionOutput(RobustBaseModel):
    """مخرج التفكيك."""

    problem: str
    ordered_steps: list[str]
    phases: dict[str, list[str]]
    next_step: str | None
    used_scaffold: bool
    error: str | None = None


class ProblemDecompositionSkill(BaseSkill[ProblemDecompositionInput, ProblemDecompositionOutput]):
    """يُفكّك المشكلة إلى خطوات مرتّبة حتمياً (بوليا + فرز طوبولوجي) — D-181."""

    name: ClassVar[str] = "problem_decomposition"
    version: ClassVar[str] = "1.0.0"
    doctrine_version: ClassVar[str] = PROBLEM_DECOMPOSITION_DOCTRINE_VERSION

    def run(self, payload: ProblemDecompositionInput) -> ProblemDecompositionOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`decompose`."""
        return self.decompose(payload)

    def decompose(self, payload: ProblemDecompositionInput) -> ProblemDecompositionOutput:
        """يُفكّك المشكلة — يستخدم الخطوات المُعطاة أو سقالة بوليا الافتراضية."""
        t0 = time.perf_counter()
        try:
            used_scaffold = not payload.subgoals
            if used_scaffold:
                decomposition = dec_mod.polya_scaffold(payload.problem)
            else:
                subgoals = [
                    dec_mod.SubGoal(
                        id=s.id,
                        description=s.description,
                        phase=s.phase,
                        depends_on=tuple(s.depends_on),
                    )
                    for s in payload.subgoals
                ]
                decomposition = dec_mod.decompose(payload.problem, subgoals)

            order = decomposition.execution_order()
            phases = {ph: [s.id for s in subs] for ph, subs in decomposition.by_phase().items()}
            out = ProblemDecompositionOutput(
                problem=payload.problem,
                ordered_steps=order,
                phases=phases,
                next_step=order[0] if order else None,
                used_scaffold=used_scaffold,
            )
            _record("scaffold" if used_scaffold else "ok", time.perf_counter() - t0)
            return out
        except ReasoningError as exc:
            _record("invalid", time.perf_counter() - t0)
            return ProblemDecompositionOutput(
                problem=payload.problem,
                ordered_steps=[],
                phases={},
                next_step=None,
                used_scaffold=False,
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover — fail-safe
            _record("error", time.perf_counter() - t0)
            return ProblemDecompositionOutput(
                problem=payload.problem,
                ordered_steps=[],
                phases={},
                next_step=None,
                used_scaffold=False,
                error=type(exc).__name__,
            )


def _record(status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_problem_decomposition_skill() -> ProblemDecompositionSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return ProblemDecompositionSkill.instance()


__all__ = [
    "ProblemDecompositionInput",
    "ProblemDecompositionOutput",
    "ProblemDecompositionSkill",
    "SubGoalSpec",
    "get_problem_decomposition_skill",
]
