"""MentalModelSkill — بناء النماذج الذهنية (D-181).

CLAUDE.md §0.5. بناء تمثيل مُهيكَل للمفهوم (كيانات + علاقات ساكنة + ديناميات سببية)
وفحص تماسكه حتمياً (تناقض، دورة سببية، كيان معزول) فوق `app/core/reasoning/mental_model`.

## القياس (Prometheus)
- `cogniforge_skill_mental_model_total{status}` (counter)
- `cogniforge_skill_mental_model_duration_seconds` (histogram)
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import Field

from app.core.reasoning import mental_model as mm_mod
from app.core.reasoning.errors import ReasoningError
from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from app.services.skills.doctrine import MENTAL_MODEL_DOCTRINE_VERSION

_INVOCATIONS = skill_counter(
    "cogniforge_skill_mental_model_total",
    "MentalModelSkill invocations",
    ("status",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_mental_model_duration_seconds",
    "MentalModelSkill duration (seconds)",
)


class MentalModelInput(RobustBaseModel):
    """مدخلات النموذج الذهني — اسم + علاقات (فاعل، فعل، مفعول) + ديناميات (سبب، أثر)."""

    name: str = Field(..., min_length=1, max_length=200)
    relations: list[list[str]] = Field(default_factory=list, max_length=128)
    dynamics: list[list[str]] = Field(default_factory=list, max_length=128)


class MentalModelOutput(RobustBaseModel):
    """مخرج بناء النموذج الذهني."""

    name: str
    summary: dict[str, int]
    consistent: bool
    contradictions: list[list[str]]
    has_causal_cycle: bool
    isolated_entities: list[str]
    explanation: str
    error: str | None = None


class MentalModelSkill(BaseSkill[MentalModelInput, MentalModelOutput]):
    """يبني النموذج الذهني ويفحص تماسكه — حتمي (D-181)."""

    name: ClassVar[str] = "mental_model"
    version: ClassVar[str] = "1.0.0"
    doctrine_version: ClassVar[str] = MENTAL_MODEL_DOCTRINE_VERSION

    def run(self, payload: MentalModelInput) -> MentalModelOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`build`."""
        return self.build(payload)

    def build(self, payload: MentalModelInput) -> MentalModelOutput:
        """يبني النموذج ويفحص التماسك — لا يرفع استثناءً (fail-open)."""
        t0 = time.perf_counter()
        try:
            model = mm_mod.MentalModel(name=payload.name)
            for rel in payload.relations:
                if len(rel) != 3:
                    raise ReasoningError(
                        f"each relation must be [subject, verb, object], got {rel!r}"
                    )
                model.add_relation(rel[0], rel[1], rel[2])
            for dyn in payload.dynamics:
                if len(dyn) != 2:
                    raise ReasoningError(f"each dynamic must be [cause, effect], got {dyn!r}")
                model.add_dynamic(dyn[0], dyn[1])

            report = model.check_consistency()
            out = MentalModelOutput(
                name=payload.name,
                summary=model.summary(),
                consistent=report.consistent,
                contradictions=[
                    [a.subject, a.verb, b.verb, a.object] for a, b in report.contradictions
                ],
                has_causal_cycle=report.has_causal_cycle,
                isolated_entities=list(report.isolated_entities),
                explanation=_explain(report),
            )
            _record("ok", time.perf_counter() - t0)
            return out
        except ReasoningError as exc:
            _record("invalid", time.perf_counter() - t0)
            return MentalModelOutput(
                name=payload.name,
                summary={"entities": 0, "relations": 0, "dynamics": 0},
                consistent=False,
                contradictions=[],
                has_causal_cycle=False,
                isolated_entities=[],
                explanation="تعذّر بناء النموذج — تحقّق من صيغة العلاقات/الديناميات.",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover — fail-safe
            _record("error", time.perf_counter() - t0)
            return MentalModelOutput(
                name=payload.name,
                summary={"entities": 0, "relations": 0, "dynamics": 0},
                consistent=False,
                contradictions=[],
                has_causal_cycle=False,
                isolated_entities=[],
                explanation="خطأ داخلي أثناء بناء النموذج الذهني.",
                error=type(exc).__name__,
            )


def _explain(report: mm_mod.ConsistencyReport) -> str:
    if report.consistent and not report.isolated_entities:
        return "النموذج الذهني متماسك: لا تناقض، لا دورة سببية، لا كيان معزول."
    parts: list[str] = []
    if report.contradictions:
        parts.append(f"تناقضات في العلاقات: {len(report.contradictions)}.")
    if report.has_causal_cycle:
        parts.append("دورة سببية في الديناميات (النموذج يعود على نفسه).")
    if report.isolated_entities:
        parts.append(f"كيانات معزولة (بلا رابط): {'، '.join(report.isolated_entities)}.")
    parts.append("طوّر النموذج بالأسئلة السقراطية لسدّ الفجوة.")
    return " ".join(parts)


def _record(status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_mental_model_skill() -> MentalModelSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return MentalModelSkill.instance()


__all__ = [
    "MentalModelInput",
    "MentalModelOutput",
    "MentalModelSkill",
    "get_mental_model_skill",
]
