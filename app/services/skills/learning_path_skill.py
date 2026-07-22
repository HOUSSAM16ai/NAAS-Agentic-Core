"""LearningPathSkill — المسار التعلّمي التكيفي (D-111).

«المعيار الأعلى ليس الانبهار اللحظي، بل الاستقلال المعرفي» — فلسفة E-TAALEEM.

القفزة التربوية فوق BKT (D-074): محرّك الإتقان يكتب احتمال إتقان الطالب لكل
مفهوم، لكن لا شيء كان يقترح **الخطوة التالية**. هذا الـ Skill يُغلق الحلقة:
يقرأ إتقان المفهوم الحالي ويقترح — حتمياً — المفهوم التالي في تسلسل منهج
البكالوريا وصعوبةً متكيفة:

- إتقان ≥ 0.7 ⇒ تقدّم للمفهوم التالي + صعوبة hard (الطالب جاهز للتحدّي).
- 0.35 ≤ إتقان < 0.7 ⇒ ابقَ على المفهوم + صعوبة medium (ترسيخ قبل التقدّم).
- إتقان < 0.35 أو مجهول ⇒ ابقَ + صعوبة easy (ثبّت الأساس أولاً).

حتمي بالكامل: لا LLM، لا I/O داخل الـ Skill (الإتقان يُمرَّر من المُستدعي
الذي حسبه عبر BKT) — نفس المدخلات ⇒ نفس التوصية (قابل لـ pytest).
"""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Literal

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill
from app.services.skills.doctrine import LEARNING_PATH_DOCTRINE_VERSION

logger = logging.getLogger("cogniforge.skills.learning_path")

DOCTRINE_VERSION = LEARNING_PATH_DOCTRINE_VERSION

# ── عتبات السياسة (لا تُعدَّل بدون ترقية doctrine — مرآة adaptive_pedagogy) ───────
ADVANCE_THRESHOLD: float = 0.7
CONSOLIDATE_THRESHOLD: float = 0.35

Difficulty = Literal["easy", "medium", "hard"]

# ── تسلسل منهج البكالوريا (الجزائر) — خريطة ثابتة، لا overfitting ────────────────
# المفهوم الحالي → المفهوم التالي المنطقي في المنهج. المفهوم بلا تالٍ = نهاية
# السلسلة (يبقى عليه عند الإتقان — لا يخترع مفهوماً غير موجود).
_CURRICULUM_SEQUENCE: dict[str, str] = {
    "limits": "derivatives",
    "derivatives": "numerical_functions",
    "numerical_functions": "integration",
    "integration": "differential_equations",
    "sequences": "limits",
    "exponential": "logarithm",
    "logarithm": "integration",
    "complex_numbers": "geometry",
    "probability": "conditional_probability",
    "conditional_probability": "statistics",
    "trigonometry": "complex_numbers",
}

# تسميات عربية للمفاهيم (مرآة CONCEPT_LABELS في الواجهة).
_CONCEPT_LABELS: dict[str, str] = {
    "probability": "الاحتمالات",
    "conditional_probability": "الاحتمال الشرطي",
    "statistics": "الإحصاء",
    "complex_numbers": "الأعداد المركبة",
    "numerical_functions": "الدوال العددية",
    "integration": "التكامل",
    "differential_equations": "المعادلات التفاضلية",
    "derivatives": "الاشتقاق",
    "limits": "النهايات",
    "sequences": "المتتاليات",
    "trigonometry": "المثلثات",
    "logarithm": "اللوغاريتم",
    "exponential": "الدالة الأسية",
    "geometry": "الهندسة",
    "general": "عام",
}


def _label(concept_id: str) -> str:
    return _CONCEPT_LABELS.get(concept_id, concept_id or "المفهوم")


# ── العقود (Pydantic) ────────────────────────────────────────────────────────────


class LearningPathInput(RobustBaseModel):
    """مدخلات الاشتقاق — الإتقان يُمرَّر من المُستدعي (BKT)."""

    concept_id: str = Field(..., min_length=1, max_length=120)
    mastery: float | None = Field(None, ge=0.0, le=1.0, description="احتمال إتقان المفهوم الحالي")
    interaction_count: int = Field(0, ge=0, description="عدد التفاعلات السابقة على المفهوم")


class LearningPathOutput(RobustBaseModel):
    """مخرج الاشتقاق — التوصية التالية للطالب."""

    current_concept: str
    next_concept: str
    advanced: bool = Field(..., description="هل تقدّم لمفهوم جديد أم بقي للترسيخ؟")
    target_difficulty: Difficulty
    recommendation_text: str = Field(..., max_length=400)
    rationale: str = Field(..., max_length=400)
    doctrine_version: str = DOCTRINE_VERSION


# ── القياس ─────────────────────────────────────────────────────────────────────


def _record_metric(status: str, difficulty: str, duration_s: float) -> None:
    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        obs.record_metric(
            "skill.learning_path.invocations.total",
            1.0,
            labels={"status": status, "difficulty": difficulty},
        )
        obs.record_metric("skill.learning_path.duration_seconds", duration_s)


# ── الـ Skill ──────────────────────────────────────────────────────────────────


class LearningPathSkill(BaseSkill):
    """محرّك المسار التعلّمي الحتمي.

    عقد دائم (لا يُكسر بدون ADR):
    1. يُبنى فوق student_mastery_probability — لا يُعيد اختراع تتبّع الإتقان.
    2. حتمي تماماً — لا LLM، لا I/O داخل الـ Skill.
    3. تسلسل المنهج خريطة ثابتة معمّمة — لا overfitting.
    4. fail-open مطلق — توصية محايدة آمنة عند أي تعذّر.
    """

    VERSION = DOCTRINE_VERSION
    SKILL_NAME = "learning_path"
    name = "learning_path"

    def run(self, payload: LearningPathInput) -> LearningPathOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`derive`."""
        return self.derive(payload)

    def derive(self, payload: LearningPathInput) -> LearningPathOutput:
        t0 = time.perf_counter()
        try:
            out = self._derive(payload)
            _record_metric("success", out.target_difficulty, time.perf_counter() - t0)
            return out
        except Exception:  # pragma: no cover - fail-open
            logger.debug("learning_path derive failed (fail-open)", exc_info=True)
            _record_metric("fallback", "easy", time.perf_counter() - t0)
            label = _label(payload.concept_id)
            return LearningPathOutput(
                current_concept=payload.concept_id,
                next_concept=payload.concept_id,
                advanced=False,
                target_difficulty="easy",
                recommendation_text=f"واصل التدرّب على {label} لترسيخ الأساس.",
                rationale="توصية محايدة آمنة (fail-open).",
            )

    @staticmethod
    def _derive(payload: LearningPathInput) -> LearningPathOutput:
        concept = payload.concept_id
        mastery = payload.mastery
        label = _label(concept)
        next_in_curriculum = _CURRICULUM_SEQUENCE.get(concept, concept)

        if mastery is not None and mastery >= ADVANCE_THRESHOLD:
            next_label = _label(next_in_curriculum)
            advanced = next_in_curriculum != concept
            if advanced:
                rec = f"أتقنت {label} ({mastery:.0%}). انتقل الآن إلى {next_label} بتمارين متقدّمة."
                rationale = f"إتقان ≥ {ADVANCE_THRESHOLD:.0%} ⇒ تقدّم في تسلسل المنهج."
            else:
                rec = f"أتقنت {label} ({mastery:.0%}). جرّب تمارين تحدٍّ متقدّمة لإحكام المهارة."
                rationale = "آخر مفهوم في السلسلة — تثبيت بتحدٍّ."
            return LearningPathOutput(
                current_concept=concept,
                next_concept=next_in_curriculum,
                advanced=advanced,
                target_difficulty="hard",
                recommendation_text=rec,
                rationale=rationale,
            )

        if mastery is not None and mastery >= CONSOLIDATE_THRESHOLD:
            return LearningPathOutput(
                current_concept=concept,
                next_concept=concept,
                advanced=False,
                target_difficulty="medium",
                recommendation_text=f"تقدّمك جيد في {label} ({mastery:.0%}). رسّخه بتمارين متوسطة قبل التقدّم.",
                rationale=f"{CONSOLIDATE_THRESHOLD:.0%} ≤ إتقان < {ADVANCE_THRESHOLD:.0%} ⇒ ترسيخ.",
            )

        mastery_txt = f" ({mastery:.0%})" if mastery is not None else ""
        return LearningPathOutput(
            current_concept=concept,
            next_concept=concept,
            advanced=False,
            target_difficulty="easy",
            recommendation_text=f"لنبدأ بأساسيات {label}{mastery_txt} بتمارين بسيطة موجّهة خطوة بخطوة.",
            rationale="إتقان منخفض/مجهول ⇒ تثبيت الأساس بصعوبة easy.",
        )


_SINGLETON: LearningPathSkill | None = None


def get_learning_path_skill() -> LearningPathSkill:
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = LearningPathSkill()
    return _SINGLETON


__all__ = [
    "LearningPathInput",
    "LearningPathOutput",
    "LearningPathSkill",
    "get_learning_path_skill",
]
