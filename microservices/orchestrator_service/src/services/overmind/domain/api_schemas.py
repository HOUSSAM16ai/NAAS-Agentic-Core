# app/services/overmind/domain/api_schemas.py
"""
نماذج واجهة برمجة تطبيقات "العقل المدبر" (Overmind API Schemas).
---------------------------------------------------------
تحتوي هذه الوحدة على نماذج البيانات (Pydantic Models) الصارمة التي تحدد عقد التواصل
مع منظومة الوكلاء الخارقين. تلتزم هذه النماذج بمعايير CS50 2025.

المعايير:
- استخدام `pydantic` للتحقق الصارم من البيانات.
- توثيق "Legendary" باللغة العربية.
- عدم الاعتماد على `typing.List` أو `Optional` واستخدام `list` و `| None`.
- الوراثة من `RobustBaseModel` لضمان المرونة في المدخلات (Postel's Law).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import AliasChoices, Field

from app.core.schemas import RobustBaseModel


class MissionStatusEnum(StrEnum):
    """حالات المهمة الممكنة."""

    # Ensure values match app.models.MissionStatus (lowercase)
    PENDING = "pending"
    PLANNING = "planning"
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"  # Not in DB yet? DB has ADAPTING.
    ADAPTING = "adapting"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELED = "canceled"
    # Backwards compatibility if needed, or to handle mixed case
    # Pydantic 2 Enums are strict by default on value


class StepStatusEnum(StrEnum):
    """حالات خطوة التنفيذ."""

    # Aligned with app.models.TaskStatus
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "success"  # DB uses success
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RETRY = "retry"


class MissionStepResponse(RobustBaseModel):
    """
    نموذج استجابة لخطوة واحدة داخل المهمة (Task).
    """

    id: int | None = Field(None, description="معرف الخطوة")
    name: str = Field(
        ..., validation_alias=AliasChoices("task_key", "name"), description="اسم الخطوة أو الإجراء"
    )
    description: str | None = Field(None, description="وصف تفصيلي للخطوة")
    status: StepStatusEnum = Field(StepStatusEnum.PENDING, description="حالة الخطوة الحالية")
    result: str | None = Field(
        None,
        validation_alias=AliasChoices("result_text", "result"),
        description="نتيجة تنفيذ الخطوة",
    )
    tool_used: str | None = Field(
        None,
        validation_alias=AliasChoices("tool_name", "tool_used"),
        description="اسم الأداة المستخدمة إن وجد",
    )
    created_at: datetime = Field(..., description="توقيت إنشاء الخطوة")
    completed_at: datetime | None = Field(
        None,
        validation_alias=AliasChoices("finished_at", "completed_at"),
        description="توقيت اكتمال الخطوة",
    )


class MissionCreate(RobustBaseModel):
    """
    نموذج إنشاء مهمة جديدة.
    يطلب هذا النموذج الهدف الأساسي والسياق الاختياري.
    """

    objective: str = Field(..., min_length=5, max_length=5000, description="الهدف الرئيسي للمهمة")
    context: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, description="سياق إضافي للمهمة (مثل بيئة العمل، قيود)"
    )
    priority: int = Field(1, ge=1, le=5, description="أولوية المهمة (1-5)")


class MissionResponse(RobustBaseModel):
    """
    نموذج الاستجابة الكاملة للمهمة.
    """

    id: int = Field(..., description="معرف المهمة الفريد")
    objective: str = Field(..., description="الهدف الرئيسي")
    status: MissionStatusEnum = Field(..., description="الحالة العامة للمهمة")
    outcome: str | None = Field(None, description="نتيجة المهمة الدلالية (outcome)")
    created_at: datetime = Field(..., description="توقيت الإنشاء")
    updated_at: datetime = Field(..., description="آخر تحديث")
    result: dict[str, str | int | float | bool | None] | None = Field(
        None, description="النتيجة النهائية للمهمة"
    )
    # Using 'tasks' from DB model, mapped to 'steps' in API if we want to keep API consistent,
    # or just rename to 'tasks'. Let's use validation_alias to accept 'tasks' from DB object.
    steps: list[MissionStepResponse] = Field(
        default_factory=list,
        validation_alias=AliasChoices("tasks", "steps"),
        description="قائمة خطوات التنفيذ",
    )


class MissionEventResponse(RobustBaseModel):
    """
    نموذج لحدث واحد في تدفق البث (SSE).
    """

    event_type: str = Field(..., description="نوع الحدث (مثلاً: step_start, log, completion)")
    mission_id: int = Field(..., description="معرف المهمة")
    timestamp: datetime = Field(default_factory=datetime.now, description="توقيت الحدث")
    payload: dict[str, str | int | float | bool | list | dict | None] = Field(
        default_factory=dict, description="بيانات الحدث التفصيلية"
    )


class AgentPlanPriority(StrEnum):
    """مستويات أولوية خطة الوكلاء."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class AgentsPlanRequest(RobustBaseModel):
    """
    طلب إنشاء خطة للوكلاء.

    يحدد الهدف والسياق والقيود التشغيلية لتوليد خطة واضحة.
    """

    objective: str = Field(..., min_length=5, max_length=5000, description="الهدف الرئيسي المطلوب")
    context: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, description="سياق إضافي يساعد الوكلاء على التخطيط"
    )
    constraints: list[str] = Field(default_factory=list, description="قيود تشغيلية أو تقنية")
    priority: AgentPlanPriority = Field(
        default=AgentPlanPriority.MEDIUM, description="أولوية التخطيط"
    )


class AgentPlanStepResponse(RobustBaseModel):
    """
    نموذج خطوة واحدة ضمن خطة الوكلاء.
    """

    step_id: str = Field(..., description="معرف الخطوة")
    title: str = Field(..., description="عنوان مختصر للخطوة")
    description: str = Field(..., description="وصف تفصيلي للخطوة")
    dependencies: list[str] = Field(default_factory=list, description="اعتمادات الخطوة")
    estimated_effort: str | None = Field(default=None, description="تقدير الجهد المتوقع")


class AgentPlanData(RobustBaseModel):
    """
    بيانات خطة الوكلاء.
    """

    plan_id: str = Field(..., description="معرف الخطة")
    objective: str = Field(..., description="الهدف الرئيسي للخطة")
    steps: list[AgentPlanStepResponse] = Field(default_factory=list, description="قائمة الخطوات")
    created_at: datetime = Field(..., description="توقيت إنشاء الخطة")


class AgentsPlanResponse(RobustBaseModel):
    """
    استجابة إنشاء خطة الوكلاء.
    """

    status: str = Field("success", description="حالة الاستجابة")
    data: AgentPlanData = Field(..., description="بيانات الخطة")


class LangGraphRunRequest(RobustBaseModel):
    """
    طلب تشغيل LangGraph للوكلاء المتعددين.
    """

    objective: str = Field(..., min_length=5, max_length=5000, description="الهدف الرئيسي المطلوب")
    context: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, description="سياق إضافي لدعم الوكلاء"
    )
    constraints: list[str] = Field(default_factory=list, description="قيود تشغيلية أو تقنية")
    priority: AgentPlanPriority = Field(
        default=AgentPlanPriority.MEDIUM, description="أولوية التشغيل"
    )


class LangGraphTimelineEvent(RobustBaseModel):
    """
    سجل زمني لحدث داخل دورة LangGraph.
    """

    agent: str = Field(..., description="اسم الوكيل المساهم")
    payload: dict[str, object] = Field(default_factory=dict, description="تفاصيل الحدث")


class LangGraphRunData(RobustBaseModel):
    """
    بيانات تشغيل LangGraph كاملة.
    """

    run_id: str = Field(..., description="معرف تشغيل LangGraph")
    objective: str = Field(..., description="الهدف الرئيسي")
    plan: dict[str, object] | None = Field(None, description="خطة الاستراتيجي")
    design: dict[str, object] | None = Field(None, description="تصميم المعماري")
    execution: dict[str, object] | None = Field(None, description="نتائج المنفذ")
    audit: dict[str, object] | None = Field(None, description="نتائج التدقيق")
    timeline: list[LangGraphTimelineEvent] = Field(
        default_factory=list, description="السجل الزمني للقرارات"
    )


class LangGraphRunResponse(RobustBaseModel):
    """
    استجابة تشغيل LangGraph.
    """

    status: str = Field("success", description="حالة الاستجابة")
    data: LangGraphRunData = Field(..., description="نتائج التشغيل")
