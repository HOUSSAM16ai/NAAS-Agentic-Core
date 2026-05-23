"""
موجِّه النواة التعليمية التكيّفية (AEK Router) — Protocol V44.0.

نقطة دخول HTTP للنواة المعرفية. تُعيد القناتين A و B منفصلتين.

نقاط النهاية:
    POST /api/v1/aek/process  — معالجة سؤال وإرجاع الحالة المعرفية + القناتين
    POST /api/v1/aek/reset    — إعادة تعيين الحالة المعرفية لجلسة جديدة
    GET  /api/v1/aek/states   — قائمة الحالات والانتقالات المسموح بها (للتشخيص)
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.aek.fsm import ALLOWED_TRANSITIONS, CognitiveState
from app.services.aek.intents import CognitiveIntent
from app.services.aek.kernel import AdaptiveEducationalKernel, AEKOutput
from app.services.aek.state import AEKRuntimeState, ExerciseScope, LearnerCapability

router = APIRouter(prefix="/api/v1/aek", tags=["adaptive-educational-kernel"])

# Singleton: مُهيَّأ مرة واحدة — لا حالة داخلية، آمن للاستخدام المتزامن.
_kernel = AdaptiveEducationalKernel()


class AEKProcessRequest(RobustBaseModel):
    """طلب معالجة سؤال عبر النواة التعليمية التكيّفية."""

    question: str = Field(..., min_length=1, max_length=10000)
    history: list[dict[str, str]] = Field(
        default_factory=list,
        description="تاريخ المحادثة: [{role: user|assistant, content: ...}]",
    )
    state: AEKRuntimeState | None = Field(
        default=None,
        description="الحالة المعرفية الحالية. None → تُنشأ حالة افتراضية.",
    )
    learner_capability: LearnerCapability = Field(
        default=LearnerCapability.INTERMEDIATE,
        description="تقدير قدرة المتعلّم — يُحدِّد مستوى التجريد.",
    )


class AEKProcessResponse(RobustBaseModel):
    """مخرج النواة التعليمية — القناتان A و B + الحالة المُحدَّثة."""

    channel_a: dict[str, object] = Field(
        description="القناة A: حمولة JSON آلية (نية، حالة، بيانات بصرية).",
    )
    channel_b: dict[str, object] = Field(
        description="القناة B: سرد سقراطي دافئ (Markdown فقط).",
    )
    updated_state: dict[str, object] = Field(
        description="الحالة المعرفية المُحدَّثة — أرسِلها في الطلب التالي.",
    )
    processing_ms: float


class AEKStatesResponse(RobustBaseModel):
    """خريطة الانتقالات المسموح بها — للتشخيص والتوثيق."""

    states: list[str]
    transitions: dict[str, list[str]]
    intents: list[str]
    scopes: list[str]


@router.post(
    "/process",
    response_model=AEKProcessResponse,
    summary="معالجة سؤال عبر النواة التعليمية التكيّفية",
    description=(
        "يُحوِّل سؤال الطالب إلى حالة معرفية + نية تربوية + قناتين منفصلتين.\n\n"
        "**القناة A**: JSON آلي للواجهة (نية، حالة، مستوى تجريد).\n"
        "**القناة B**: سرد Markdown سقراطي دافئ.\n\n"
        "أرسِل `updated_state` من الاستجابة في الطلب التالي للحفاظ على السياق."
    ),
)
async def process_question(payload: AEKProcessRequest) -> AEKProcessResponse:
    """
    يُعالج سؤال الطالب عبر النواة المعرفية ويُرجع القناتين.

    الحالة المعرفية تتطوّر عبر الجلسة — أرسِل updated_state في كل طلب.
    """
    # تطبيق learner_capability من الطلب على الحالة
    state = payload.state
    if state is not None and payload.learner_capability != state.learner_capability:
        state = state.model_copy(update={"learner_capability": payload.learner_capability})
    elif state is None:
        state = AEKRuntimeState(learner_capability=payload.learner_capability)

    output: AEKOutput = _kernel.process(
        question=payload.question,
        history=payload.history,
        state=state,
    )

    return AEKProcessResponse(
        channel_a=output.channel_a.model_dump(),
        channel_b=output.channel_b.model_dump(),
        updated_state=output.updated_state.model_dump(),
        processing_ms=output.processing_ms,
    )


@router.post(
    "/reset",
    response_model=AEKRuntimeState,
    summary="إعادة تعيين الحالة المعرفية",
    description="يُنشئ حالة معرفية نظيفة لجلسة تعليمية جديدة.",
)
async def reset_state(
    learner_capability: LearnerCapability = LearnerCapability.INTERMEDIATE,
    exercise_scope: ExerciseScope = ExerciseScope.GENERAL,
) -> AEKRuntimeState:
    """يُعيد حالة معرفية افتراضية نظيفة."""
    return AEKRuntimeState(
        learner_capability=learner_capability,
        current_exercise_scope=exercise_scope,
    )


@router.get(
    "/states",
    response_model=AEKStatesResponse,
    summary="خريطة الانتقالات المسموح بها",
    description="يُرجع جميع الحالات والانتقالات والنوايا للتشخيص والتوثيق.",
)
async def get_states() -> AEKStatesResponse:
    """يُرجع خريطة الـ FSM الكاملة — مفيد للتشخيص وتوثيق الواجهة."""
    return AEKStatesResponse(
        states=[s.value for s in CognitiveState],
        transitions={k.value: [v.value for v in vs] for k, vs in ALLOWED_TRANSITIONS.items()},
        intents=[i.value for i in CognitiveIntent],
        scopes=[s.value for s in ExerciseScope],
    )
