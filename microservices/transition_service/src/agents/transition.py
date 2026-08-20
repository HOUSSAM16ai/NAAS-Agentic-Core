"""وكيل الانتقال المهني — وثيقة المشروع §4 وكيل 4 (مخرجه §8-4).

مخرجه خطة انتقال فردية كاملة:
1. مسارات بديلة مرتبة بمؤشر القرب المهارية + إشارة الطلب (Pomsland et al. 2025).
2. جسر تدريبي: وحدات قصيرة متراكمة تسد الفجوة لكل مسار.
3. احتمال نجاح مُقدَّر حتمياً (1 − مسافة مهارية + 0.15×إشارة الطلب).
4. علم حماية اجتماعية: هل يحتاج العامل وسادة انتقالية (حسب فجوة المسافة وفئة الدخل).

كل أرقام الخطة حتمية؛ الخطة «توصية» فقط — التنفيذ بيد العامل والإنسان
(مستوى قرار معلوماتي/مساند عبر بوابة الحوكمة).
"""

from __future__ import annotations

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import (
    OCCUPATIONS,
    SKILLS,
)
from microservices.transition_service.src.schemas import (
    StandardResponse,
    TransitionRequest,
)

AGENT_NAME = "career_transition"


def _build_path(source, target) -> dict[str, object]:
    distance = engine.transition_distance(source, target)
    feasibility = round(max(0.0, min(1.0, 1.0 - distance + target.demand_signal * 0.15)), 3)
    gap = engine.skills_gap(list(source.current_skills), list(target.current_skills))
    units = engine.training_coverage(source, target)

    needs_transition_support = distance > 0.55 or source.wage_reference < 0.75

    target_skills_detail = [
        {
            "code": s,
            "label_ar": SKILLS[s].label_ar,
            "in_possession": s in set(source.current_skills),
        }
        for s in target.current_skills
        if s in SKILLS
    ]
    return {
        "target_occupation": target.code,
        "label_ar": target.label_ar,
        "label_en": target.label_en,
        "sector": target.sector,
        "skill_distance": distance,
        "feasibility_score": feasibility,
        "demand_signal": target.demand_signal,
        "target_skills": target_skills_detail,
        "missing_skills": gap["missing_skills"],
        "training_bridge": units,
        "total_bridge_weeks": sum(u["duration_weeks"] for u in units),
        "wage_delta_reference": round(target.wage_reference - source.wage_reference, 2),
        "needs_transition_support": needs_transition_support,
    }


async def career_transition(request: TransitionRequest) -> StandardResponse:
    worker = request.worker
    source = engine.occupation(worker.current_occupation)

    if request.target_occupation:
        targets = [engine.occupation(request.target_occupation)]
    else:
        candidates = [OCCUPATIONS[a] for a in source.adjacent_occupations if a in OCCUPATIONS]
        # مسارات النمو الرئيسية كإضافات عالمية (لا تقتصر على الجوار المباشر)
        extra = ["o_care_assistant", "o_green_tech", "o_data_quality"]
        candidates += [
            OCCUPATIONS[e]
            for e in extra
            if e in OCCUPATIONS and e not in source.adjacent_occupations
        ]
        targets = candidates

    paths = [_build_path(source, t) for t in targets]
    paths.sort(key=lambda p: (-p["feasibility_score"], p["skill_distance"]))
    paths = paths[: max(request.max_paths, 1)]

    result: dict[str, object] = {
        "worker_id": worker.worker_id,
        "current_occupation": {
            "code": source.code,
            "label_ar": source.label_ar,
            "demand_signal": source.demand_signal,
        },
        "transition_paths": paths,
        "evidence_base": [
            "Pomsland et al. (2025) NBER — التكيفية ترتبط بقرب المهنة من مصدر الاضطراب",
            "WEF 2025 — الاقتصادات المستقرة: إعادة تأهيل داخلي قبل فصل ثم توظيف جديد",
        ],
        "decision_note": "هذه خطة توصية — تبني المسار والالتحاق بالتدريب قرار العامل بإرادته الحرة",
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
