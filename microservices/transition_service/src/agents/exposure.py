"""وكيل التعرض المهني — وثيقة المشروع §4 وكيل 2 (مخرجه §8-2).

يحلل أي مهنة من أطلس المنظومة (أو مهام مخصصة لأخرى) إلى:
- تفكيك المهام مع تصنيف كل مهمة (أتمتة كاملة / أدوات / تعزيز / إنسانية) —
  تصنيف β من Eloundou et al. (2023), Science.
- مؤشر التعرض النظري، مؤشر التعرض المرصود (Anthropic Economic Index)،
  مؤشر التعزيز، مؤشر النواة الإنسانية.
- المهن المجاورة الأكثر قابلية للانتقال إليها.
"""

from __future__ import annotations

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import OCCUPATIONS
from microservices.transition_service.src.schemas import (
    ExposureRequest,
    StandardResponse,
)

AGENT_NAME = "occupation_exposure"


async def occupation_exposure(request: ExposureRequest) -> StandardResponse:
    occ = engine.occupation(request.occupation_code)
    tasks_breakdown = [
        {
            "task": t.label_ar,
            "category": t.category,
            "theoretical_beta": engine._theoretical_beta(t.category),
            "time_fraction": t.time_fraction,
            "observed_weight": {
                "auto_full": 1.0,
                "auto_tools": 0.75,
                "augment": 0.5,
                "human_only": 0.0,
            }[t.category],
        }
        for t in occ.tasks
    ]

    adjacent = [
        {
            "code": a,
            "label_ar": OCCUPATIONS[a].label_ar,
            "skill_distance": engine.transition_distance(occ, OCCUPATIONS[a]),
            "demand_signal": OCCUPATIONS[a].demand_signal,
        }
        for a in occ.adjacent_occupations
        if a in OCCUPATIONS
    ]
    adjacent.sort(key=lambda x: x["skill_distance"])

    result: dict[str, object] = {
        "occupation": occ.code,
        "label_ar": occ.label_ar,
        "label_en": occ.label_en,
        "sector": occ.sector,
        "task_breakdown": tasks_breakdown,
        "indices": {
            "theoretical_exposure": engine.theoretical_exposure(occ),
            "observed_exposure": engine.observed_exposure(occ),
            "augmentation_index": engine.augmentation_index(occ),
            "human_core_index": engine.human_core_index(occ),
            "gap_theoretical_vs_observed": round(
                engine.theoretical_exposure(occ) - engine.observed_exposure(occ), 3
            ),
        },
        "future_skills_demand": list(occ.future_skills),
        "adjacent_occupations": adjacent,
        "evidence_base": [
            "Eloundou et al. (2023) — β task-based exposure, Science",
            "Anthropic (2026) — Observed exposure = theoretical × usage",
        ],
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
