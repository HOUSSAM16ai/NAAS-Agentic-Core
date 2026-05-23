"""
نموذج الحالة المعرفية للنواة التعليمية التكيّفية (AEK Runtime State).

Protocol V44.0 §II: قبل توليد أي مخرج، يجب تأسيس كائن حالة واحد موثوق.
هذا الكائن هو المصدر الوحيد للحقيقة — لا متغيرات عالمية، لا سياق ضمني.

قانون النقاء:
    - لا انتقالات مخفية.
    - لا قفزات سياق ضمنية.
    - لا نزيف ذاكرة غير محكوم.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, field_validator

from app.core.schemas import RobustBaseModel
from app.services.aek.fsm import CognitiveState
from app.services.aek.intents import CognitiveIntent


class ExerciseScope(StrEnum):
    """
    نطاق التمرين الحالي — يُطبِّق عزل الموضوع (Topic Isolation §V).

    عند تحديد النطاق، تُمنع كل المفاهيم خارجه منعاً باتاً.
    """

    PROBABILITY = "PROBABILITY"
    """احتمالات: تركيبات، فضاء عيّنة، أحداث، احتمال شرطي، متغيرات عشوائية."""

    CALCULUS = "CALCULUS"
    """تفاضل وتكامل: مشتقات، تكاملات، دراسة دوال."""

    ALGEBRA = "ALGEBRA"
    """جبر: معادلات، متتاليات، مصفوفات."""

    STATISTICS = "STATISTICS"
    """إحصاء: توزيعات، مقاييس نزعة مركزية، تشتت."""

    GEOMETRY = "GEOMETRY"
    """هندسة: فضاء، متجهات، تحويلات."""

    PHYSICS = "PHYSICS"
    """فيزياء: ميكانيك، كهرباء، بصريات."""

    GENERAL = "GENERAL"
    """عام — لا قيود موضوعية."""


class LearnerCapability(StrEnum):
    """
    تقدير قدرة المتعلّم الحالية — يُحدِّد مستوى التجريد المسموح به.

    Protocol V44.0 §VIII: المتعلّمون المتقدّمون قد يتجاوزون الطبقات الوسيطة.
    """

    NOVICE = "NOVICE"
    """مبتدئ — يحتاج تجريداً منخفضاً، تصويراً بصرياً، وتسلسلاً بطيئاً."""

    INTERMEDIATE = "INTERMEDIATE"
    """متوسط — يتحمّل تجريداً معتدلاً مع دعم بصري."""

    ADVANCED = "ADVANCED"
    """متقدّم — يتحمّل الصياغة الرسمية مباشرةً."""


class AEKRuntimeState(RobustBaseModel):
    """
    كائن الحالة المعرفية الكامل للنواة التعليمية.

    هذا الكائن هو المصدر الوحيد للحقيقة في كل دورة معالجة.
    يُمرَّر صراحةً — لا يُخزَّن في متغيرات عالمية.

    Protocol V44.0 §II: الحقول المطلوبة:
        - current_cognitive_state
        - current_exercise_scope
        - current_step_index
        - current_cognitive_intent
        - cognitive_load_index
        - learner_capability
        - topic_lock
        - current_runtime_mode
    """

    # ─── الحالة المعرفية ──────────────────────────────────────────────────────
    current_cognitive_state: CognitiveState = Field(
        default=CognitiveState.STANDARD,
        description="الحالة المعرفية الحالية في الـ FSM.",
    )
    current_cognitive_intent: CognitiveIntent = Field(
        default=CognitiveIntent.STEP_REASONING,
        description="النية التربوية المُصدَرة للواجهة.",
    )

    # ─── نطاق التمرين ─────────────────────────────────────────────────────────
    current_exercise_scope: ExerciseScope = Field(
        default=ExerciseScope.GENERAL,
        description="الموضوع المُقفَل — يمنع التلوّث المفاهيمي.",
    )
    topic_lock: bool = Field(
        default=False,
        description="عند True: لا يُسمح بأي مفهوم خارج current_exercise_scope.",
    )

    # ─── تقدّم الخطوات ────────────────────────────────────────────────────────
    current_step_index: int = Field(
        default=0,
        ge=0,
        description="مؤشر الخطوة الحالية في التسلسل التعليمي.",
    )

    # ─── الحِمل الإدراكي والقدرة ──────────────────────────────────────────────
    cognitive_load_index: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="مؤشر الحِمل الإدراكي [0,1]. كلما ارتفع → خفِّض التجريد.",
    )
    learner_capability: LearnerCapability = Field(
        default=LearnerCapability.INTERMEDIATE,
        description="تقدير قدرة المتعلّم — يُحدِّد مستوى التجريد المسموح به.",
    )

    # ─── وضع التشغيل ──────────────────────────────────────────────────────────
    current_runtime_mode: str = Field(
        default="MODE_A",
        description="MODE_A (مباشر) أو MODE_B (بيداغوجيا عميقة — حيرة).",
    )

    # ─── سجل الانتقالات ───────────────────────────────────────────────────────
    transition_log: list[str] = Field(
        default_factory=list,
        description="سجل الانتقالات المعرفية لهذه الجلسة — للتشخيص.",
    )

    @field_validator("cognitive_load_index")
    @classmethod
    def _clamp_load(cls, v: float) -> float:
        """يضمن بقاء المؤشر في النطاق [0, 1]."""
        return max(0.0, min(1.0, v))

    def record_transition(self, from_state: CognitiveState, to_state: CognitiveState) -> None:
        """يُسجِّل انتقالاً في سجل الجلسة."""
        self.transition_log.append(f"{from_state.value}→{to_state.value}")

    def is_overloaded(self) -> bool:
        """يُعيد True إذا تجاوز الحِمل الإدراكي عتبة التدخل (0.7)."""
        return self.cognitive_load_index >= 0.7

    def abstraction_level_allowed(self) -> int:
        """
        يُحسب مستوى التجريد المسموح به [1-3].

        1 = بصري فقط، 2 = خطوات + بصري، 3 = رسمي كامل.
        يأخذ في الاعتبار كلاً من cognitive_load_index وlearner_capability.
        """
        if self.is_overloaded():
            return 1
        if self.learner_capability == LearnerCapability.ADVANCED:
            return 3
        if self.learner_capability == LearnerCapability.NOVICE:
            return 1
        # INTERMEDIATE: يعتمد على الحِمل
        if self.cognitive_load_index < 0.4:
            return 3
        if self.cognitive_load_index < 0.65:
            return 2
        return 1
