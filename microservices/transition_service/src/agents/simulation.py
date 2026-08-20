"""وكيل محاكاة السياسات — وثيقة المشروع §4 وكيل 10 (مخرجه §8-10).

نموذج المهمة (task model) مستنسخ من Acemoglu & Restrepo (2018/2019):
- الاقتصاد مجموعة مهام؛ الأتمتة «تزيح» العمالة من مهام وتُعيد تمكينها في
  «مهام جديدة» (reinstatement effect). صافي التوظيف = أثر الإزاحة + أثر إعادة
  التمكين + أثر الإنتاجية.
- السياسة تُحاكى بثلاثة أرقام حتمية: معدل الإزاحة، معدل إعادة التمكين،
  أفق زمني. السيناريو يُقارن مع خط أساس (لا سياسة).
- المخرجات: توظيف صافٍ لكل قطاع، فجوة مهارات مركّمة، مؤشر «توازن الاستبدال-الاستحداث»
  (displacement-to-creation ratio) — الوثيقة §10: «الإنقاذ الحقيقي ليس الإبقاء
  على وظائف قديمة بل خلق جديدة أعلى جودة».
"""

from __future__ import annotations

from microservices.transition_service.src.data.occupations import (
    GROWTH_SECTORS,
)
from microservices.transition_service.src.schemas import (
    SimulationRequest,
    StandardResponse,
)

AGENT_NAME = "simulation"

# خط أساس: اتجاه الطلب الطبيعي (بدون سياسة) ينمو بمقدار صغير
BASELINE_GROWTH_PER_YEAR: float = 0.01


def _sector_workforce(occ_codes: tuple[str, ...]) -> float:
    """حجم قوة عمل نسبي افتراضي للقطاع (وحدة = 1.0 موزعة على القطاعات)."""
    if not occ_codes:
        return 1.0
    return max(len(occ_codes) * 0.1, 0.1)


async def simulation(request: SimulationRequest) -> StandardResponse:
    codes = request.sector_codes or list(GROWTH_SECTORS.keys())
    sector_results = []
    total_displaced = 0.0
    total_reinstated = 0.0
    total_new = 0.0

    for code in codes:
        sector = GROWTH_SECTORS.get(code)
        if not sector:
            continue
        workforce = _sector_workforce(sector["key_occupations"])
        # أثر السياسة: الإزاحة تضرب المهام الآلية (حصة آلية تقديرية 45%)
        automated_task_share = 0.45
        displaced = workforce * automated_task_share * request.displacement_rate
        # إعادة التمكين: تولد مهام جديدة في القطاع بنمو القطاعات المرافقة
        growth_signal = sector["growth_signal"]
        reinstated = workforce * request.reinstatement_rate * growth_signal * 0.8
        # أثر الإنتاجية الإيجابي (Brynjolfsson: ارتفاع إنتاجية ≈ نمو طلب)
        productivity_effect = workforce * request.reinstatement_rate * 0.1

        baseline_jobs = workforce * (1 + BASELINE_GROWTH_PER_YEAR * request.horizon_years)
        net_jobs = reinstated + productivity_effect - displaced
        policy_jobs = baseline_jobs + net_jobs

        total_displaced += displaced
        total_reinstated += reinstated
        total_new += productivity_effect

        sector_results.append(
            {
                "sector": code,
                "label_ar": sector["label_ar"],
                "baseline_jobs": round(baseline_jobs, 3),
                "jobs_displaced": round(displaced, 3),
                "jobs_reinstated_new_tasks": round(reinstated, 3),
                "productivity_demand_effect": round(productivity_effect, 3),
                "net_policy_effect": round(net_jobs, 3),
                "policy_jobs": round(policy_jobs, 3),
                "replacement_creation_ratio": round(
                    displaced / reinstated if reinstated > 0 else float("inf"), 3
                ),
            }
        )

    net_total = total_reinstated + total_new - total_displaced
    ratio = total_displaced / total_reinstated if total_reinstated > 0 else float("inf")

    # تصنيف السياسة: «توازن صحي» أم «إزاحة صافية»؟ (وثيقة المشروع §10)
    policy_verdict = (
        "balanced_creation"
        if ratio <= 1.0 and net_total >= 0
        else ("net_displacement" if net_total < 0 else "managed_transition")
    )

    result: dict[str, object] = {
        "policy_name": request.policy_name,
        "parameters": {
            "displacement_rate": request.displacement_rate,
            "reinstatement_rate": request.reinstatement_rate,
            "horizon_years": request.horizon_years,
        },
        "sectors": sector_results,
        "aggregate": {
            "jobs_displaced": round(total_displaced, 3),
            "jobs_reinstated": round(total_reinstated, 3),
            "productivity_new_demand": round(total_new, 3),
            "net_employment_effect": round(net_total, 3),
            "replacement_creation_ratio": round(ratio, 3) if ratio != float("inf") else None,
            "verdict": policy_verdict,
        },
        "interpretation_guide": (
            "ratio ≤ 1.0 مع أثر صافٍ ≥ 0 = سياسة توازن صحي (استحداث يتجاوز إزاحة). "
            "ratio > 1.5 = خطر إزاحة صافية — يلزم رفع معدل إعادة التمكين (تأهيل + حوافز مهام جديدة)."
        ),
        "evidence_base": [
            "Acemoglu & Restrepo (2018/2019) — task model: displacement + reinstatement + productivity effects",
            "Autor (2024) PNAS — labor as a system of tasks reshaped by AI",
        ],
        "decision_note": "محاكاة تقديرية — قرار السياسة بيد اللجنة البشرية مع هذه النتائج كمُدخل",
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
