"""وكيل خلق الوظائف — وثيقة المشروع §4 وكيل 6 (مخرجه §8-6).

مخرجه خريطة القطاعات النموذجية وفرص العمل الجديدة فيها، مع:
- فرص لكل قطاع مرتبطة بأدواره (من GROWTH_SECTORS الحتمي).
- مبادرات دعم موصى بها (OECD GenAI & SME 2025: دعم الرقمنة يولّد وظائف مساندة؛
  وثيقة المشروع §7: حوافز منشآت صغيرة، اقتصاد رعاية، أخضر، رقمي).
- عدالة الوصول: الفئات الأقل حظاً لكل قطاع.
"""

from __future__ import annotations

from microservices.transition_service.src.data.occupations import (
    GROWTH_SECTORS,
    OCCUPATIONS,
)
from microservices.transition_service.src.schemas import (
    JobCreationRequest,
    StandardResponse,
)

AGENT_NAME = "job_creation"


async def job_creation(request: JobCreationRequest) -> StandardResponse:
    codes = request.sectors or list(GROWTH_SECTORS.keys())
    sectors_result = []
    for code in codes:
        if code not in GROWTH_SECTORS:
            continue
        sector = GROWTH_SECTORS[code]
        roles = []
        for occ_code in sector["key_occupations"]:
            occ = OCCUPATIONS.get(occ_code)
            if not occ:
                continue
            roles.append(
                {
                    "occupation": occ.code,
                    "label_ar": occ.label_ar,
                    "demand_signal": occ.demand_signal,
                    "wage_reference": occ.wage_reference,
                    "entry_barrier": (
                        "low"
                        if occ.wage_reference < 0.9
                        else ("medium" if occ.wage_reference < 1.3 else "high")
                    ),
                }
            )
        sectors_result.append(
            {
                "sector": code,
                "label_ar": sector["label_ar"],
                "growth_signal": sector["growth_signal"],
                "roles": roles,
                "notes": sector["notes"],
                "access_strategy": {
                    "low_income": "مبادرات تدريب مدفوعة + شهادات قصيرة دون اشتراط خبرة سابقة",
                    "rural": "تدريب عن بُعد + ترحيل لوجستي لبرامج الميدان",
                    "young": "تمارين مهنية مبكرة + عقود تدريب-توظيف مضمونة",
                    "women": "مرونة زمنية + رعاية مساندة أثناء التدريب (وثيقة المشروع §7)",
                },
            }
        )
    sectors_result.sort(key=lambda s: -s["growth_signal"])

    result: dict[str, object] = {
        "scope": {"region": request.region, "sectors_analyzed": len(sectors_result)},
        "growth_map": sectors_result,
        "policy_recommended_actions": [
            "حوافز رقمنة للمنشآت الصغيرة (OECD 2025: كل منشأة مرَقمنة تولّد وظائف مساندة جديدة)",
            "توسيع اقتصاد الرعاية — أكبر مصدر وظائف جديدة (WEF 2025)",
            "الانتقال الأخضر: تقنيات متجددة + صيانة ميدانية غير قابلة للأتمتة",
            "منصة عمل حر منظم لاستيعاب القطاع غير الرسمي (وثيقة المشروع §7.4)",
        ],
        "evidence_base": [
            "WEF 2025 — 14% من التوظيف ستأتي من مهن جديدة كلياً (~170 مليون فرصة)",
            "WEF 2025 — أوسع وصول رقمي = +19 مليون وظيفة صافية",
            "OECD (2025) — GenAI والأعمال الصغيرة: دعم الرقمنة يولّد نمواً توظيفياً مسانداً",
        ],
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
