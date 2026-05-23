"""
النواة التعليمية التكيّفية (Adaptive Educational Kernel — AEK).

Protocol V44.0: نظام تشغيل معرفي حتمي يُنظِّم الحِمل الإدراكي،
ويُسلسل الفهم، ويُحوِّل الحيرة إلى بنية تعليمية منظَّمة.

المكوّنات:
    - ``fsm``: آلة الحالة المحدودة الإعلانية (Declarative FSM)
    - ``state``: نموذج الحالة المعرفية (Cognitive State Model)
    - ``intents``: النوايا التربوية (Cognitive Intents)
    - ``kernel``: المحرّك الرئيسي (AEK Runtime)
"""

from app.services.aek.fsm import ALLOWED_TRANSITIONS, CognitiveState, transition
from app.services.aek.intents import CognitiveIntent
from app.services.aek.kernel import AdaptiveEducationalKernel
from app.services.aek.state import AEKRuntimeState, ExerciseScope, LearnerCapability

__all__ = [
    "ALLOWED_TRANSITIONS",
    "AEKRuntimeState",
    "AdaptiveEducationalKernel",
    "CognitiveIntent",
    "CognitiveState",
    "ExerciseScope",
    "LearnerCapability",
    "transition",
]
