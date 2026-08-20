"""وكيل الإنذار المبكر لسوق العمل — وثيقة المشروع §4 وكلاء 1–3.

المخرجات:
- خريطة المخاطر المهنية الوطنية/القطاعية (مؤشر مركب = 0.35×تعرض نظري +
  0.35×تعرض مرصود − 0.3×إشارة الطلب) — فصل «القدرة النظرية/الاستخدام المرصود»
  من Anthropic 2026 هو قلب التصميم: التغطية النظرية وحدها مضللة (درس التعهيد).
- قائمة إنذارات مرتبة وفق نطاقات المخاطرة (critical/elevated/watch/stable).
- إشارات إنذار مبكر على التوظيف المبكر (بطء توظيف صغار السن في المهن عالية
  التغطية — Anthropic 2026) عند توفر بيانات طلبات التوظيف.
"""

from __future__ import annotations

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import (
    OCCUPATIONS,
    TRAINING_UNITS,
)
from microservices.transition_service.src.schemas import (
    EarlyWarningRequest,
    StandardResponse,
)

AGENT_NAME = "early_warning"


def _analyze_occupation(occ_code: str) -> dict[str, object]:
    occ = engine.occupation(occ_code)
    warning = engine.early_warning_score(occ)
    # الإشارة المبكرة: توظيف صغار السن في مهن عالية التغطية المتعرضة
    early_hiring_cooling = occ.demand_signal < -0.4 and warning["observed_exposure"] > 0.35
    return {
        **warning,
        "label_ar": occ.label_ar,
        "label_en": occ.label_en,
        "sector": occ.sector,
        "human_core_index": round(engine.human_core_index(occ), 3),
        "augmentation_index": round(engine.augmentation_index(occ), 3),
        "early_hiring_cooling_signal": early_hiring_cooling,
        "recommended_first_training": next(
            (u["code"] for u in TRAINING_UNITS.values() if occ_code in u["target_occupations"]),
            None,
        ),
    }


async def early_warning(request: EarlyWarningRequest) -> StandardResponse:
    codes = request.occupation_codes or list(OCCUPATIONS.keys())
    results = [_analyze_occupation(code) for code in codes if code in OCCUPATIONS]
    results.sort(key=lambda r: -r["composite_risk"])

    critical = [r for r in results if r["risk_band"] == "critical"]
    elevated = [r for r in results if r["risk_band"] == "elevated"]
    cooling_signals = [r for r in results if r.get("early_hiring_cooling_signal")]

    # على المستوى الفردي: تشخيص حالة العامل ضمن الخريطة
    individual: dict[str, object] = {}
    if request.worker:
        occ = engine.occupation(request.worker.current_occupation)
        individual = {
            "worker_id": request.worker.worker_id,
            "current_occupation_analysis": _analyze_occupation(occ.code),
            "watchlist": request.worker.current_occupation
            in [r["occupation"] for r in results if r["risk_band"] in ("critical", "elevated")],
        }

    result: dict[str, object] = {
        "scope": request.scope,
        "analyzed_occupations": len(results),
        "risk_map": results,
        "alerts": {
            "critical_count": len(critical),
            "elevated_count": len(elevated),
            "critical_occupations": [r["occupation"] for r in critical],
            "early_hiring_cooling_count": len(cooling_signals),
        },
        "individual": individual,
        "evidence_base": [
            "Anthropic 2026 — النظرية≠المرصود: 94% نظرياً مقابل 33% مرصوداً في الحاسوب والرياضيات",
            "WEF 2025 — 22% من الأدوار تتلاشى أو تتغير كلياً بحلول 2030",
            "Anthropic 2026 — مؤشر مبكر: تباطؤ توظيف صغار السن في المهن عالية التغطية",
        ],
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
