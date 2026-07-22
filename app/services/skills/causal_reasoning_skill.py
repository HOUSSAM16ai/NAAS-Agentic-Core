"""CausalReasoningSkill — فهم العلاقات السببية (D-181).

CLAUDE.md §0.5. الارتباط ليس سببية: تُميّز حتمياً السبب المباشر من التلازم المُربِك
(سبب مشترك خفيّ)، وتُجيب الأسئلة المضادّة للواقع بتدخّل حتمي (حذف العقدة) — كلّه فوق
`app/core/reasoning/causal`. تكشف القصّة السببية الدائرية وترفضها.

## القياس (Prometheus)
- `cogniforge_skill_causal_reasoning_total{status}` (counter)
- `cogniforge_skill_causal_reasoning_duration_seconds` (histogram)
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import Field

from app.core.reasoning import causal as causal_mod
from app.core.reasoning.errors import ReasoningError
from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from app.services.skills.doctrine import CAUSAL_REASONING_DOCTRINE_VERSION

_INVOCATIONS = skill_counter(
    "cogniforge_skill_causal_reasoning_total",
    "CausalReasoningSkill invocations",
    ("status",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_causal_reasoning_duration_seconds",
    "CausalReasoningSkill duration (seconds)",
)

_RELATION_LABELS: dict[str, str] = {
    "causal": "علاقة سببية مباشرة (A يُسبِّب B).",
    "reverse_causal": "علاقة سببية معكوسة (B يُسبِّب A).",
    "confounded": "تلازم لا سببية: سبب مشترك خفيّ يجعلهما يترافقان دون أن يُسبّب أحدهما الآخر.",
    "independent": "لا علاقة سببية معروفة بينهما.",
}


class CausalReasoningInput(RobustBaseModel):
    """مدخلات السببية — أضلاع (سبب، أثر) + استعلام تصنيف/مضادّ للواقع اختياري."""

    edges: list[list[str]] = Field(default_factory=list, max_length=128)
    classify_pair: list[str] | None = Field(default=None)
    counterfactual_node: str | None = Field(default=None)


class CausalReasoningOutput(RobustBaseModel):
    """مخرج التحليل السببي."""

    nodes: list[str]
    has_cycle: bool
    relationship: str | None = None
    relationship_label: str | None = None
    counterfactual_lost_effects: list[str] | None = None
    explanation: str
    error: str | None = None


class CausalReasoningSkill(BaseSkill[CausalReasoningInput, CausalReasoningOutput]):
    """يُميّز السببية من الارتباط ويُجيب المضادّ للواقع — رمزي حتمي (D-181)."""

    name: ClassVar[str] = "causal_reasoning"
    version: ClassVar[str] = "1.0.0"
    doctrine_version: ClassVar[str] = CAUSAL_REASONING_DOCTRINE_VERSION

    def run(self, payload: CausalReasoningInput) -> CausalReasoningOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`analyze`."""
        return self.analyze(payload)

    def analyze(self, payload: CausalReasoningInput) -> CausalReasoningOutput:
        """يبني الرسم السببي ويُجيب الاستعلامات — لا يرفع استثناءً (fail-open)."""
        t0 = time.perf_counter()
        try:
            graph = causal_mod.CausalGraph()
            for edge in payload.edges:
                if len(edge) != 2:
                    raise ReasoningError(f"each edge must be [cause, effect], got {edge!r}")
                graph.add_edge(edge[0], edge[1])

            has_cycle = graph.has_cycle()
            relationship = None
            relationship_label = None
            if payload.classify_pair and len(payload.classify_pair) == 2:
                a, b = payload.classify_pair
                relationship = graph.classify_relationship(a, b)
                relationship_label = _RELATION_LABELS.get(relationship)

            lost: list[str] | None = None
            if payload.counterfactual_node is not None:
                lost = sorted(str(n) for n in graph.counterfactual(payload.counterfactual_node))

            out = CausalReasoningOutput(
                nodes=sorted(str(n) for n in graph.nodes),
                has_cycle=has_cycle,
                relationship=relationship,
                relationship_label=relationship_label,
                counterfactual_lost_effects=lost,
                explanation=_explain(
                    has_cycle, relationship_label, payload.counterfactual_node, lost
                ),
            )
            _record("ok", time.perf_counter() - t0)
            return out
        except ReasoningError as exc:
            _record("invalid", time.perf_counter() - t0)
            return CausalReasoningOutput(
                nodes=[],
                has_cycle=False,
                explanation="تعذّر بناء الرسم السببي — تحقّق من الأضلاع.",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover — fail-safe
            _record("error", time.perf_counter() - t0)
            return CausalReasoningOutput(
                nodes=[],
                has_cycle=False,
                explanation="خطأ داخلي أثناء التحليل السببي.",
                error=type(exc).__name__,
            )


def _explain(
    has_cycle: bool,
    relationship_label: str | None,
    cf_node: str | None,
    lost: list[str] | None,
) -> str:
    parts: list[str] = []
    if has_cycle:
        parts.append("تنبيه: الرسم السببي يحوي دورة — قصّة سببية غير سليمة (لا يُقبَل دور).")
    if relationship_label:
        parts.append(relationship_label)
    if cf_node is not None:
        if lost:
            parts.append(f"لو لم يحدث «{cf_node}» لَما وقعت الآثار: {'، '.join(lost)}.")
        else:
            parts.append(
                f"لو لم يحدث «{cf_node}» لبقيت الآثار قائمة (لها مسارات سببية بديلة أو لا آثار له)."
            )
    if not parts:
        parts.append("تمّ بناء الرسم السببي؛ حدّد زوجاً للتصنيف أو عقدة للسؤال المضادّ للواقع.")
    return " ".join(parts)


def _record(status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_causal_reasoning_skill() -> CausalReasoningSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return CausalReasoningSkill.instance()


__all__ = [
    "CausalReasoningInput",
    "CausalReasoningOutput",
    "CausalReasoningSkill",
    "get_causal_reasoning_skill",
]
