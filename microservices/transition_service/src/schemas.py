"""مخططات Pydantic لواجهات خدمة التحول — وثيقة المشروع §8 (المخرجات المطلوبة)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WorkerInput(BaseModel):
    """ملف حالة فرد — الأساس لكل تحليل فردي."""

    worker_id: str = Field(..., description="معرّف مستخدم داخلي — لا بيانات شخصية حساسة")
    current_occupation: str = Field(..., description="كود المهنة الحالية من أطلس المنظومة")
    region: str = Field("", description="المنطقة الجغرافية")
    age_band: str = Field("", description="فئة العمر: young | mid | senior")
    gender_band: str = Field("", description="فئة الجنس لأغراض مراقبة العدالة فقط: f | m | other")
    current_skills: list[str] = Field(default_factory=list, description="أكواد المهارات المتوفرة")
    income_band: str = Field("", description="فئة الدخل: low | mid | high")
    disability_band: str = Field("", description="إعاقة: yes | no | unknown")


class EarlyWarningRequest(BaseModel):
    """وكيل الإنذار المبكر — مخرجه §8-1: خريطة المخاطر الوطنية + قائمة إنذارات."""

    scope: str = Field("national", description="national | sector | individual")
    occupation_codes: list[str] = Field(
        default_factory=list, description="إن لم يُذكر: كل أطلس المهن"
    )
    worker: WorkerInput | None = Field(None, description="لتحليل فردي")


class ExposureRequest(BaseModel):
    """وكيل التعرض المهني — مخرجه §8-2."""

    occupation_code: str
    task_breakdown: list[dict[str, str]] | None = Field(
        None,
        description="مهام مخصصة {label_ar, label_en, category, time_fraction} لتقييم مهنة غير مسجلة",
    )


class SkillsGapRequest(BaseModel):
    """وكيل فجوة المهارات — مخرجه §8-3."""

    worker: WorkerInput
    target_occupation: str | None = Field(
        None, description="إن لم يُحدد: تُستنتج من أفضل مسار انتقال"
    )


class TransitionRequest(BaseModel):
    """وكيل الانتقال المهني — مخرجه §8-4: خطة انتقال فردية كاملة."""

    worker: WorkerInput
    target_occupation: str | None = None
    max_paths: int = Field(3, ge=1, le=10)


class EducationRequest(BaseModel):
    """وكيل التعليم — مخرجه §8-5: تحليل مناهج + وحدات تدريب قصيرة."""

    institution_type: str = Field("general", description="general | vocational | school")
    target_skills: list[str] = Field(default_factory=list, description="المهارات المطلوبة في السوق")
    current_curriculum_skills: list[str] = Field(
        default_factory=list, description="المهارات التي يغطيها المنهج"
    )
    for_occupation: str | None = None


class JobCreationRequest(BaseModel):
    """وكيل خلق الوظائف — مخرجه §8-6."""

    region: str = ""
    sectors: list[str] = Field(
        default_factory=list, description="أكواد القطاعات من GROWTH_SECTORS أو كل القطاعات"
    )


class SocialProtectionRequest(BaseModel):
    """وكيل الحماية الاجتماعية — مخرجه §8-7."""

    worker: WorkerInput
    transition_horizon_months: int = Field(12, ge=1, le=36)


class GovernanceRequest(BaseModel):
    """وكيل الحوكمة والامتثال — مخرجه §8-8."""

    system_type: str = Field(
        ..., description="نوع النظام الخوارزمي: hiring | worker_management | promotion | other"
    )
    decision_description: str = Field(..., description="وصف القرار الذي يتخذه النظام")
    affected_groups: list[str] = Field(
        default_factory=list,
        description="الفئات المتأثرة: young | women | disabled | rural | low_income",
    )


class EquityRequest(BaseModel):
    """وكيل العدالة — مخرجه §8-9."""

    population: list[WorkerInput] = Field(..., description="عينة سكانية للتحليل")


class SimulationRequest(BaseModel):
    """وكيل المحاكاة — مخرجه §8-10: سيناريوهات Acemoglu–Restrepo (استبدال/استحداث)."""

    policy_name: str = Field(..., description="اسم السياسة محل المحاكاة")
    displacement_rate: float = Field(
        ..., ge=0.0, le=1.0, description="معدل إزاحة العمالة في المهام الآلية"
    )
    reinstatement_rate: float = Field(
        ..., ge=0.0, le=1.0, description="معدل إعادة التمكين عبر المهام الجديدة"
    )
    horizon_years: int = Field(5, ge=1, le=20)
    sector_codes: list[str] = Field(default_factory=list)


class DialogueRequest(BaseModel):
    """وكيل الحوار الاجتماعي — مخرجه §8-11."""

    stakeholder: str = Field(
        ..., description="employer | worker | union | government | educator | citizen"
    )
    feedback_text: str = Field(..., description="نص الملاحظات من الأطراف المعنية")


class EvaluationRequest(BaseModel):
    """وكيل التقييم والمساءلة — مخرجه §8-12."""

    kpi_code: str = Field(
        ...,
        description="transition_completion_rate | six_month_placement | wage_change | gender_gap_closure | rural_access",
    )
    measured_value: float
    target_value: float
    period: str = Field("current", description="current | previous")


class RedTeamRequest(BaseModel):
    """وكيل الفريق الأحمر — مخرجه §8-13: اختبارات انحياز وإجهاد للنظام."""

    test_kind: str = Field(
        ...,
        description="bias_gender | bias_region | bias_income | unrealistic_recommendation | fairness_across_age",
    )
    payload: dict[str, object] = Field(
        default_factory=dict, description="بيانات الاختبار — أعمار/مناطق/دخول متطابقة المهارات"
    )


class GovernanceApprovalRequest(BaseModel):
    """طلب اتخاذ إجراء — يدخل عبر بوابة القرار الأربعة المستويات."""

    request_id: str
    agent: str = Field(..., description="اسم الوكيل طالب الإجراء")
    action_key: str
    description: str
    duration_days: int = Field(0, ge=0)
    budget: float = Field(0.0, ge=0.0)


# ── المخرجات ──────────────────────────────────────────────────────────────


class StandardResponse(BaseModel):
    status: str = Field("ok")
    agent: str
    result: dict[str, object]
    governance: dict[str, object] | None = Field(None, description="قرار بوابة الحوكمة إن وُجد")


class EarlyWarningResponse(StandardResponse):
    pass


class ExposureResponse(StandardResponse):
    pass


class SkillsGapResponse(StandardResponse):
    pass


class TransitionResponse(StandardResponse):
    pass


class EducationResponse(StandardResponse):
    pass


class JobCreationResponse(StandardResponse):
    pass


class SocialProtectionResponse(StandardResponse):
    pass


class GovernanceResponse(StandardResponse):
    pass


class EquityResponse(StandardResponse):
    pass


class SimulationResponse(StandardResponse):
    pass


class DialogueResponse(StandardResponse):
    pass


class EvaluationResponse(StandardResponse):
    pass


class RedTeamResponse(StandardResponse):
    pass


class DecisionResponse(BaseModel):
    allowed: bool
    decision_level: str
    reason: str
    human_action_description: str
    decision_log: dict[str, object]
