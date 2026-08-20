"""وكيل الحماية الاجتماعية — وثيقة المشروع §4 وكيل 7 (مخرجه §8-7).

مخرجه حزمة دعم انتقالي موصى بها للعامل، حتمية البناء:
- وسادة انتقالية (دعم دخل مؤقت) إن كانت المسافة المهارية أو الدخل الحالي يستوجبان.
- تأمين أجر (wage-insurance) لتعويض فرق الأجر بعد الانتقال (أدبيات Autor & Dorn).
- إعادة تأهيل مدفوع، رعاية أثناء التدريب، استشارة نفس-مهنية.
- نقاط اتصال بمؤسسات قائمة (صندوق ضمان، تأمين بطالة، برامج وطنية).

التصنيف لا LLM: عتبة المسافة المهارية والدخل تحسم الحاجة.
"""

from __future__ import annotations

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import OCCUPATIONS
from microservices.transition_service.src.schemas import (
    SocialProtectionRequest,
    StandardResponse,
)

AGENT_NAME = "social_protection"


def _package_for(worker_input) -> dict[str, object]:
    occ = engine.occupation(worker_input.current_occupation)
    # أقرب مهنة نمو كمسار افتراضي
    best_target = None
    best_dist = 1.0
    for a in occ.adjacent_occupations:
        target = OCCUPATIONS.get(a)
        if target:
            d = engine.transition_distance(occ, target)
            if d < best_dist:
                best_dist = d
                best_target = target
    if best_target is None:
        best_target = OCCUPATIONS["o_care_assistant"]
        best_dist = engine.transition_distance(occ, best_target)

    gap = engine.skills_gap(list(occ.current_skills), list(best_target.current_skills))
    needs_bridge = best_dist > 0.5 or occ.wage_reference < 0.75 or worker_input.income_band == "low"

    components = [
        {
            "name": "وسادة دخل انتقالية",
            "provided": needs_bridge,
            "duration_months": 6 if worker_input.income_band != "low" else 9,
            "rationale": "تغطية أساسيات المعيشة أثناء إعادة التأهيل — تمنع القفز القسري لعمل أقل جودة",
        },
        {
            "name": "إعادة تأهيل مدفوعة بالكامل",
            "provided": True,
            "duration_weeks": 10,
            "rationale": "حصة العامل في تكاليف التدريب تُعد أهم عائق — OECD 2025",
        },
        {
            "name": "تأمين أجرة انتقال",
            "provided": worker_input.income_band != "high",
            "rationale": "تعويض حتى 70% من فرق الأجر لمدة 24 شهراً إن كان الأجر الجديد أقل (نموذج wage-insurance)",
        },
        {
            "name": "رعاية أثناء التدريب",
            "provided": needs_bridge,
            "rationale": "بدون رعاية (أطفال/إعاقة) لا يكتمل التدريب — عدالة وصول (WEF 2025)",
        },
        {
            "name": "استشارة نفس-مهنية",
            "provided": best_dist > 0.6,
            "rationale": "الانتقال الكبير يرافقه قلق مهني — الدعم النفسي جزء من نجاح التبني",
        },
    ]

    return {
        "worker_id": worker_input.worker_id,
        "current_occupation": {"code": occ.code, "label_ar": occ.label_ar},
        "suggested_target": {
            "code": best_target.code,
            "label_ar": best_target.label_ar,
            "skill_distance": best_dist,
        },
        "gap_ratio": gap["gap_ratio"],
        "package": components,
        "eligibility_rationale": (
            f"مسافة مهارية {best_dist:.2f}، أجر مرجعي {occ.wage_reference:.2f}، فئة دخل {worker_input.income_band or 'غير محددة'}"
        ),
        "institutional_touchpoints": [
            "صندوق الضمان/التأمينات الاجتماعية — وسادة الدخل",
            "برنامج التأمين ضد التعطل — إن وُجد",
            "مراكز التأهيل المهني الوطنية — إعادة التأهيل",
            "وزارة/هيئة التعليم والتدريب — الشهادات القصيرة",
        ],
        "evidence_base": [
            "Acemoglu & Restrepo — إعادة التمكين يتطلب استثماراً عاماً في إعادة التأهيل لا ترك العامل للسوق وحده",
            "WEF 2025 — دعم الدخل والوصول للتدريب أبرز ما يرفع نجاح التحول",
        ],
        "decision_note": "استحقاق مقترح فقط — التصرف النهائي للمؤسسات الاجتماعية البشرية وفق قوانينها",
    }


async def social_protection(request: SocialProtectionRequest) -> StandardResponse:
    result = _package_for(request.worker)
    result["horizon_months"] = request.transition_horizon_months
    return StandardResponse(agent=AGENT_NAME, result=result)
