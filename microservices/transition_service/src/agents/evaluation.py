"""وكيل التقييم والمساءلة — وثيقة المشروع §4 وكيل 12 (مخرجه §8-12).

يقيس KPIs التحول حتمياً: نسبة إتمام الانتقال، التوظيف خلال 6 أشهر،
تغيّر الأجر، إغلاق فجوة النوع، وصول المناطق الريفية — ويعرض البعد عن الهدف
والتوجه (تحسن/تراجع) دون أي LLM في الحساب.
"""

from __future__ import annotations

from microservices.transition_service.src.schemas import (
    EvaluationRequest,
    StandardResponse,
)

AGENT_NAME = "evaluation"

KPI_META: dict[str, dict[str, object]] = {
    "transition_completion_rate": {
        "label_ar": "نسبة إتمام الانتقال المهني",
        "unit": "%",
        "good_direction": "up",
        "target_note": "المقياس الذهبي — وثيقة المشروع §11: هل وصل المتحولون فعلاً لوظيفة جديدة؟",
    },
    "six_month_placement": {
        "label_ar": "التوظيف خلال 6 أشهر من إتمام التدريب",
        "unit": "%",
        "good_direction": "up",
        "target_note": "يكشف فجوة بين «شهادة» و«فرصة عمل حقيقية»",
    },
    "wage_change": {
        "label_ar": "تغيّر الأجر بعد 12 شهراً",
        "unit": "%",
        "good_direction": "up",
        "target_note": "جودة الانتقال لا كمّه فقط — وثيقة المشروع §10",
    },
    "gender_gap_closure": {
        "label_ar": "إغلاق فجوة النوع في برامج التحول",
        "unit": "نقطة",
        "good_direction": "up",
        "target_note": "Anthropic 2026: الربعية الأعلى تعرضاً أعلاه احتمالاً أنثى — يجب قياس التغطية",
    },
    "rural_access": {
        "label_ar": "وصول المناطق الريفية لبرامج التحول",
        "unit": "%",
        "good_direction": "up",
        "target_note": "عدالة الوصول شرط نجاح وطني (وثيقة المشروع §7)",
    },
}


async def evaluation(request: EvaluationRequest) -> StandardResponse:
    meta = KPI_META.get(
        request.kpi_code,
        {
            "label_ar": request.kpi_code,
            "unit": "index",
            "good_direction": "up",
            "target_note": "مؤشر مخصص",
        },
    )

    measured = request.measured_value
    target = request.target_value
    achievement = (
        min(measured / target, 1.5) if target > 0 else (measured if measured >= 0 else 0.0)
    )

    gap = target - measured
    status = (
        "on_track"
        if measured >= target * 0.9
        else ("at_risk" if measured >= target * 0.7 else "off_track")
    )

    result: dict[str, object] = {
        "kpi": {
            "code": request.kpi_code,
            "label_ar": meta["label_ar"],
            "unit": meta["unit"],
            "good_direction": meta["good_direction"],
            "note": meta["target_note"],
        },
        "measured": measured,
        "target": target,
        "achievement_ratio": round(achievement, 3),
        "gap_to_target": round(gap, 3),
        "status": status,
        "recommended_actions": {
            "on_track": "استمرار الرصد — توثيق العوامل الناجحة لإعادة تعميمها",
            "at_risk": "مراجعة الفجوة ربع سنوية مع اللجنة المختصة",
            "off_track": "تدخل تصحيحي فوري + تدقيق أسباب الانحراف في سجل الحوكمة",
        }[status],
        "accountability_note": "المؤشر مدوّن في سجل الحوكمة — المساءلة علنية ودورية (وثيقة المشروع §11)",
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
