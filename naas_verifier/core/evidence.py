"""الدليل بأصنافٍ مُسمّاة — لا درجةٌ عارية (D-267 §3).

⛔ **القانون:** «أعلى إشارةٍ ممكنة معاملةٌ مُسوّاة، وما دونها انطباع.» وعلى مستوى
المُتحقِّق: رقمٌ بلا مرجعٍ قابلٍ لإعادة الإنتاج ليس دليلاً. لذلك كل دليلٍ هنا يحمل
**صنفاً** و**مرجعاً** و**أمرَ إعادة إنتاج** — والصنف من قائمةٍ مغلقة.

⛔ مكتبة قياسية فقط.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = ["Evidence", "EvidenceError", "EvidenceKind"]


class EvidenceError(ValueError):
    """دليلٌ ناقص الحقول — يُرفَع عند الإنشاء لا عند القراءة."""


class EvidenceKind(StrEnum):
    """أصناف الدليل المقبولة داخل المُتحقِّق.

    مُحاذاةً لـ`docs/governance/evidence_schema.json`: المقبول قابلٌ لإعادة الإنتاج،
    والمرفوض هناك (نجومٌ · اجتماع · خطاب نيّةٍ غير مدفوع) لا يملك تمثيلاً هنا أصلاً —
    **المنع بالنوع لا بمُرشِّح**.
    """

    CONSTRAINT_EVALUATION = "constraint_evaluation"
    EXPLOIT_REPRODUCTION = "exploit_reproduction"
    BASELINE_COMPARISON = "baseline_comparison"
    REPRODUCIBLE_EXPERIMENT = "reproducible_experiment"


@dataclass(frozen=True)
class Evidence:
    """سجلّ دليلٍ واحد — مُلحَق-فقط بطبيعته: لا يُعدَّل بعد إنشائه (`frozen`)."""

    evidence_id: str
    kind: EvidenceKind
    summary: str
    reproduction: str
    source_reference: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("evidence_id", "summary", "reproduction", "source_reference"):
            if not str(getattr(self, name)).strip():
                raise EvidenceError(
                    f"evidence `{self.evidence_id or '?'}`: `{name}` must not be empty — "
                    "a claim without a reproduction is an impression, not evidence"
                )

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind.value,
            "summary": self.summary,
            "reproduction": self.reproduction,
            "source_reference": self.source_reference,
            "payload": dict(self.payload),
        }
