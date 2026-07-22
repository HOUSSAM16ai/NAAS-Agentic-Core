"""AbstractionSkill — التجريد والتماثل (D-181).

CLAUDE.md §0.5. استخراج الثابت المشترك بين الأمثلة (النمط)، قاعدة المتتالية والحدّ
التالي (بأرقام كسرية مضبوطة)، والتماثل البنيوي بين مجالين — كلّه حتمي فوق
`app/core/reasoning/abstraction`.

## القياس (Prometheus)
- `cogniforge_skill_abstraction_total{status}` (counter)
- `cogniforge_skill_abstraction_duration_seconds` (histogram)
"""

from __future__ import annotations

import time
from typing import Any, ClassVar

from pydantic import Field

from app.core.reasoning import abstraction as abs_mod
from app.core.reasoning.errors import ReasoningError
from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from app.services.skills.doctrine import ABSTRACTION_DOCTRINE_VERSION

_INVOCATIONS = skill_counter(
    "cogniforge_skill_abstraction_total",
    "AbstractionSkill invocations",
    ("status",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_abstraction_duration_seconds",
    "AbstractionSkill duration (seconds)",
)


class AbstractionInput(RobustBaseModel):
    """مدخلات التجريد — أمثلة (لاستخراج النمط) أو متتالية أو زوج (مصدر/هدف) للتماثل."""

    instances: list[dict[str, Any]] = Field(default_factory=list, max_length=64)
    sequence: list[float] = Field(default_factory=list, max_length=64)
    source: dict[str, Any] | None = Field(default=None)
    target: dict[str, Any] | None = Field(default=None)


class AbstractionOutput(RobustBaseModel):
    """مخرج التجريد."""

    invariants: dict[str, Any] | None = None
    parameters: list[str] | None = None
    sequence_kind: str | None = None
    sequence_next: str | None = None
    analogy_confidence: float | None = None
    analogy_mapping: dict[str, list[Any]] | None = None
    explanation: str
    error: str | None = None


class AbstractionSkill(BaseSkill[AbstractionInput, AbstractionOutput]):
    """يُجرِّد النمط المشترك ويبني التماثل البنيوي — حتمي (D-181)."""

    name: ClassVar[str] = "abstraction"
    version: ClassVar[str] = "1.0.0"
    doctrine_version: ClassVar[str] = ABSTRACTION_DOCTRINE_VERSION

    def run(self, payload: AbstractionInput) -> AbstractionOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`generalize`."""
        return self.generalize(payload)

    def generalize(self, payload: AbstractionInput) -> AbstractionOutput:
        """يستخرج النمط/القاعدة/التماثل حسب المدخل — لا يرفع استثناءً (fail-open)."""
        t0 = time.perf_counter()
        try:
            out = AbstractionOutput(explanation="")
            parts: list[str] = []

            if payload.instances:
                pattern = abs_mod.generalize(payload.instances)
                out.invariants = pattern.invariants
                out.parameters = list(pattern.parameters)
                parts.append(
                    f"الثابت المشترك: {pattern.invariants or 'لا شيء'}؛ "
                    f"المتغيّر (البارامترات): {list(pattern.parameters) or 'لا شيء'}."
                )

            if payload.sequence:
                rule = abs_mod.generalize_sequence(payload.sequence)
                out.sequence_kind = rule.kind
                out.sequence_next = None if rule.next_term is None else str(rule.next_term)
                if rule.next_term is not None:
                    parts.append(f"المتتالية {rule.kind}؛ الحدّ التالي = {rule.next_term}.")
                else:
                    parts.append("المتتالية لا تتبع قاعدة بسيطة (ثابتة/حسابية/هندسية).")

            if payload.source and payload.target:
                an = abs_mod.analogy(payload.source, payload.target)
                out.analogy_confidence = round(an.confidence, 4)
                out.analogy_mapping = {k: [v[0], v[1]] for k, v in an.mapping.items()}
                parts.append(
                    f"التماثل البنيوي بثقة {an.confidence:.0%} عبر {len(an.mapping)} علاقة مشتركة."
                )

            if not parts:
                raise ReasoningError("no input: provide instances, a sequence, or source+target")

            out.explanation = " ".join(parts)
            _record("ok", time.perf_counter() - t0)
            return out
        except ReasoningError as exc:
            _record("invalid", time.perf_counter() - t0)
            return AbstractionOutput(
                explanation="لا مدخل صالح للتجريد — قدّم أمثلة أو متتالية أو زوج مصدر/هدف.",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover — fail-safe
            _record("error", time.perf_counter() - t0)
            return AbstractionOutput(
                explanation="خطأ داخلي أثناء التجريد.",
                error=type(exc).__name__,
            )


def _record(status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_abstraction_skill() -> AbstractionSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return AbstractionSkill.instance()


__all__ = [
    "AbstractionInput",
    "AbstractionOutput",
    "AbstractionSkill",
    "get_abstraction_skill",
]
