"""CriticalThinkingSkill — التفكير النقدي (D-181).

CLAUDE.md §0.5. تفكيك الحجّة إلى بنيتها (مقدّمات/نتيجة/افتراضات/دليل) وكشف
**المغالطات غير الشكلية** (bandwagon، ad hominem، تعميم متسرّع، معضلة زائفة، منحدر
زلق، احتكام للسلطة) عبر تصنيف حتمي، ثم توليد **أسئلة سقراطية** تُدرّب عضلة النقد.

## المسؤولية الواحدة
لا يُصدِر رأياً؛ يُظهِر البنية والافتراض الخفي والقفزة غير المبرَّرة، ويسأل. حتمي
100% + قابل للاختبار. الصحّة الشكلية (حين تُرمَّز الحجّة) تُفوَّض لـ LogicReasoningSkill.

## القياس (Prometheus)
- `cogniforge_skill_critical_thinking_total{status}` (counter)
- `cogniforge_skill_critical_thinking_duration_seconds` (histogram)
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from app.services.skills.doctrine import CRITICAL_THINKING_DOCTRINE_VERSION

_INVOCATIONS = skill_counter(
    "cogniforge_skill_critical_thinking_total",
    "CriticalThinkingSkill invocations",
    ("status",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_critical_thinking_duration_seconds",
    "CriticalThinkingSkill duration (seconds)",
)

#: تصنيف حتمي للمغالطات غير الشكلية عبر علامات لغوية (عربي + إنجليزي).
_FALLACY_MARKERS: dict[str, tuple[str, ...]] = {
    "bandwagon": ("الجميع يعرف", "كل الناس", "الكل يقول", "everyone knows", "everybody"),
    "ad_hominem": ("أنت جاهل", "غبي", "لا تفهم", "stupid", "idiot", "you people"),
    "appeal_to_authority": ("قال الخبير", "لأن العالم قال", "expert says", "authority says"),
    "false_dichotomy": ("إما أو فقط", "لا خيار ثالث", "either you", "only two"),
    "slippery_slope": ("سيؤدي حتماً إلى", "ثم الكارثة", "will inevitably lead", "slippery"),
    "hasty_generalization": ("دائماً", "أبداً", "كل مرة", "always", "never", "all of them"),
    "appeal_to_emotion": ("فكّر في الأطفال", "من أجل الله", "think of the children"),
    "circular": ("لأنه كذلك", "بما أنه صحيح لأنه", "because it is true"),
}

#: أسئلة سقراطية حتمية تُدرّب النقد (لا تُعطي رأياً).
_SOCRATIC_PROBES: tuple[str, ...] = (
    "ما الدليل الذي يسند هذا الادّعاء؟",
    "ما الافتراض الخفي الذي تعتمد عليه الحجّة؟",
    "هل هناك تفسير أو بديل آخر ممكن؟",
    "هل الدليل كافٍ للانتقال إلى هذه النتيجة؟",
    "من قد يختلف مع هذا، وبأي حجّة؟",
)


class CriticalThinkingInput(RobustBaseModel):
    """مدخلات النقد — نصّ الحجّة + (اختياري) ادّعاءات وأدلّة مُفصَّلة."""

    text: str = Field(default="", max_length=4000)
    claims: list[str] = Field(default_factory=list, max_length=32)
    evidence: list[str] = Field(default_factory=list, max_length=64)


class CriticalThinkingOutput(RobustBaseModel):
    """مخرج تحليل التفكير النقدي."""

    fallacies: list[str]
    unsupported_claims: list[str]
    assumptions_probe: list[str]
    socratic_questions: list[str]
    summary: str


class CriticalThinkingSkill(BaseSkill[CriticalThinkingInput, CriticalThinkingOutput]):
    """يُفكّك الحجّة ويكشف المغالطات غير الشكلية ويسأل سقراطياً — حتمي (D-181)."""

    name: ClassVar[str] = "critical_thinking"
    version: ClassVar[str] = "1.0.0"
    doctrine_version: ClassVar[str] = CRITICAL_THINKING_DOCTRINE_VERSION

    def run(self, payload: CriticalThinkingInput) -> CriticalThinkingOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`analyze`."""
        return self.analyze(payload)

    def analyze(self, payload: CriticalThinkingInput) -> CriticalThinkingOutput:
        """يحلّل الحجّة حتمياً — لا يرفع استثناءً (fail-open)."""
        t0 = time.perf_counter()
        try:
            text_low = (payload.text or "").lower()
            fallacies = [
                name
                for name, markers in _FALLACY_MARKERS.items()
                if any(m.lower() in text_low for m in markers)
            ]
            unsupported = self._unsupported_claims(payload)
            n_probes = min(len(_SOCRATIC_PROBES), 3 + len(fallacies))
            out = CriticalThinkingOutput(
                fallacies=fallacies,
                unsupported_claims=unsupported,
                assumptions_probe=list(_SOCRATIC_PROBES[1:3]),
                socratic_questions=list(_SOCRATIC_PROBES[:n_probes]),
                summary=self._summary(fallacies, unsupported),
            )
            _record("ok", time.perf_counter() - t0)
            return out
        except Exception as exc:  # pragma: no cover — fail-safe
            _record("error", time.perf_counter() - t0)
            return CriticalThinkingOutput(
                fallacies=[],
                unsupported_claims=[],
                assumptions_probe=list(_SOCRATIC_PROBES[1:3]),
                socratic_questions=list(_SOCRATIC_PROBES[:3]),
                summary=f"تعذّر التحليل الكامل ({type(exc).__name__}) — إليك أسئلة نقدية للبدء.",
            )

    @staticmethod
    def _unsupported_claims(payload: CriticalThinkingInput) -> list[str]:
        """ادّعاءات بلا دليل: كل ادّعاء لا تُشير إليه أيّ قطعة دليل (تطابق كلمة مشتركة)."""
        if not payload.claims:
            return []
        evidence_blob = " ".join(payload.evidence).lower()
        unsupported: list[str] = []
        for claim in payload.claims:
            words = {w for w in claim.lower().split() if len(w) > 3}
            if not words or not any(w in evidence_blob for w in words):
                unsupported.append(claim)
        return unsupported

    @staticmethod
    def _summary(fallacies: list[str], unsupported: list[str]) -> str:
        parts: list[str] = []
        if fallacies:
            parts.append(f"رُصدت مؤشّرات مغالطة: {'، '.join(fallacies)}.")
        if unsupported:
            parts.append(f"ادّعاءات تحتاج دليلاً: {len(unsupported)}.")
        if not parts:
            parts.append("لم تُرصد مغالطة صريحة — استخدم الأسئلة السقراطية لفحص البنية والافتراضات.")
        return " ".join(parts)


def _record(status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_critical_thinking_skill() -> CriticalThinkingSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return CriticalThinkingSkill.instance()


__all__ = [
    "CriticalThinkingInput",
    "CriticalThinkingOutput",
    "CriticalThinkingSkill",
    "get_critical_thinking_skill",
]
