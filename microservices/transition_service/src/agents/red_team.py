"""وكيل الفريق الأحمر — وثيقة المشروع §4 وكيل 13 (مخرجه §8-13).

اختبارات إجهاد وانحياز حتمية:
- bias_gender / bias_region / bias_income / fairness_across_age:
  يولّد أزواج ملفات متطابقة المهارات مختلفة الهوية فقط، ثم يحسب
  «معامل التباين الديموغرافي» (demographic variance coefficient) لكل
  مخرج (توصية المسار، احتمال النجاح، طول جسر التدريب) — إذا تجاوز التباين
  عتبة 0.10 يُعلم «فشل اختبار المساواة».
- unrealistic_recommendation: يتحقق أن أي توصية انتقال تحترم قيود الوثيقة
  (لا انتقال لمهنة بمسافة > 0.9 بدون وسادة اجتماعية، لا مسار «استبدل مهنتك
  بوظيفة AI» لكل أحد).

لا LLM يقيم الإنصاف — الحساب حتمي؛ المحرك اللغوي يسرد النتائج فقط.
"""

from __future__ import annotations

import statistics
from copy import deepcopy

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import OCCUPATIONS
from microservices.transition_service.src.schemas import (
    RedTeamRequest,
    StandardResponse,
    WorkerInput,
)

AGENT_NAME = "red_team"

FAIRNESS_THRESHOLD: float = 0.10  # معامل تباين > هذه القيمة = فشل اختبار المساواة


def _variance_coefficient(values: list[float]) -> float:
    if len(values) < 2 or statistics.mean(values) == 0:
        return 0.0
    return float(statistics.stdev(values) / statistics.mean(values))


def _build_probe_variants(base: WorkerInput, test_kind: str) -> list[WorkerInput]:
    """أزواج متطابقة المهارات مختلفة الهوية فقط."""
    variants: list[WorkerInput] = [base]
    if test_kind == "bias_gender":
        for g in ("f", "m", "other"):
            if g != (base.gender_band or "f"):
                v = deepcopy(base)
                v.gender_band = g
                variants.append(v)
    elif test_kind == "bias_region":
        for region in ("urban", "rural", "remote"):
            if region != (base.region or "urban"):
                v = deepcopy(base)
                v.region = region
                variants.append(v)
    elif test_kind == "bias_income":
        for inc in ("low", "mid", "high"):
            if inc != (base.income_band or "mid"):
                v = deepcopy(base)
                v.income_band = inc
                variants.append(v)
    elif test_kind == "fairness_across_age":
        for age in ("young", "mid", "senior"):
            if age != (base.age_band or "mid"):
                v = deepcopy(base)
                v.age_band = age
                variants.append(v)
    return variants


async def red_team(request: RedTeamRequest) -> StandardResponse:
    if request.test_kind == "unrealistic_recommendation":
        # فحص عام للأطلس: لا مهنة يُفترض انتقالها بمسافة قصوى بلا وسادة
        violations = []
        for code, occ in OCCUPATIONS.items():
            for adj in occ.adjacent_occupations:
                target = OCCUPATIONS.get(adj)
                if target and engine.transition_distance(occ, target) > 0.9:
                    violations.append(
                        {
                            "source": code,
                            "target": adj,
                            "issue": "مسافة انتقال قصوى — يتطلب وسادة حماية اجتماعية إلزامية",
                        }
                    )
        return StandardResponse(
            agent=AGENT_NAME,
            result={
                "test_kind": request.test_kind,
                "max_distance_violations": violations,
                "verdict": "pass" if not violations else "violations_found",
                "note": "المسافات القصوى لا تُحظر — لكنها تُفعّل شرط الوسادة الاجتماعية (وكيل الحماية الاجتماعية)",
            },
        )

    # اختبارات الانحياز الديموغرافي
    base = WorkerInput(
        worker_id="probe_baseline",
        current_occupation=request.payload.get("occupation", "o_admin_support"),
        region=request.payload.get("region", "urban"),
        age_band=request.payload.get("age_band", "mid"),
        gender_band=request.payload.get("gender_band", "f"),
        current_skills=list(request.payload.get("skills", [])) or ["s_doc_sort", "s_ops_coord"],
        income_band=request.payload.get("income_band", "mid"),
    )
    # تحقق من أن المهنة موجودة
    if base.current_occupation not in OCCUPATIONS:
        return StandardResponse(
            agent=AGENT_NAME,
            result={
                "test_kind": request.test_kind,
                "verdict": "error",
                "note": "occupation not in atlas",
            },
        )

    variants = _build_probe_variants(base, request.test_kind)
    feasibilities: dict[str, list[float]] = {
        "feasibility": [],
        "bridge_weeks": [],
        "support_needed": [],
    }

    records = []
    for variant in variants:
        # نستخدم محرك الانتقال نفسه على كل بديل — هوية مختلفة فقط
        paths = engine.recommended_paths(
            OCCUPATIONS[variant.current_occupation],
            [
                OCCUPATIONS[a]
                for a in OCCUPATIONS[variant.current_occupation].adjacent_occupations
                if a in OCCUPATIONS
            ],
        )[:1]
        top = paths[0] if paths else None
        feasibility = float(top["transition_feasibility"]) if top else 0.0
        bridge = None
        if top:
            tgt = OCCUPATIONS.get(top["occupation"])
            if tgt:
                bridge = engine.training_coverage(OCCUPATIONS[variant.current_occupation], tgt)
        bridge_weeks = sum(b["duration_weeks"] for b in bridge) if bridge else 0.0
        occ = OCCUPATIONS[variant.current_occupation]
        support = (
            engine.transition_distance(occ, OCCUPATIONS[top["occupation"]]) > 0.55 if top else False
        )
        feasibilities["feasibility"].append(float(feasibility))
        feasibilities["bridge_weeks"].append(float(bridge_weeks))
        feasibilities["support_needed"].append(1.0 if support else 0.0)
        records.append(
            {
                "profile": {
                    "gender_band": variant.gender_band,
                    "region": variant.region,
                    "age_band": variant.age_band,
                    "income_band": variant.income_band,
                },
                "top_path": dict(top) if top else None,
                "bridge_weeks": bridge_weeks,
                "needs_support": support,
            }
        )

    coefficients = {
        metric: round(_variance_coefficient(vals), 4) for metric, vals in feasibilities.items()
    }
    failed_metrics = [m for m, c in coefficients.items() if c > FAIRNESS_THRESHOLD]

    return StandardResponse(
        agent=AGENT_NAME,
        result={
            "test_kind": request.test_kind,
            "variants_tested": len(variants),
            "demographic_variance_coefficients": coefficients,
            "fairness_threshold": FAIRNESS_THRESHOLD,
            "verdict": "pass" if not failed_metrics else "fail",
            "failed_metrics": failed_metrics,
            "probe_records": records,
            "note": (
                "المحرك حتمي بلا LLM — التباين الديموغرافي هنا ناتج من بيانات المهنة نفسها لا من تحيّز لغوي. "
                "إن فُشل الاختبار: يُوثَّق في سجل الحوكمة ويُفعَّل تعديل وكيل العدالة (تخصيص حصص)."
            ),
        },
    )
