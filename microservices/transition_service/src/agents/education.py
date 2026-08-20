"""وكيل التعليم والمناهج — وثيقة المشروع §4 وكيل 5 (مخرجه §8-5).

مخرجه:
1. تحليل فجوة المنهج مقابل متطلبات السوق (حتمي عبر أطلس المهارات).
2. وحدات تدريب قصيرة مقترحة متوافقة مع DigComp 3.0 (محو الأمية الذكية أولاً —
   OECD AILit / EU DigComp 3.0) ووثيقة المشروع §9.4 (تأهيل المعلم أولاً).
3. توصية تسلسل: معلم ← أداة ← منهج (وثيقة المشروع §9.5).
"""

from __future__ import annotations

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import (
    OCCUPATIONS,
    SKILLS,
    TrainingUnit,
)
from microservices.transition_service.src.schemas import (
    EducationRequest,
    StandardResponse,
)

AGENT_NAME = "education"


async def education(request: EducationRequest) -> StandardResponse:
    target_skills = {s for s in request.target_skills if s in SKILLS}
    curriculum_skills = {s for s in request.current_curriculum_skills if s in SKILLS}
    gap = engine.skills_gap(list(curriculum_skills), sorted(target_skills))

    # وحدات مناسبة لسد الفجوة
    recommended_units = []
    for unit in TrainingUnit.all().values():
        covers = [s for s in unit.skills if s in set(gap["missing_skills"])]
        if covers:
            recommended_units.append(
                {
                    "code": unit.code,
                    "label_ar": unit.label_ar,
                    "duration_weeks": unit.duration_weeks,
                    "skills_covered": sorted(covers),
                    "level": unit.level,
                }
            )
    recommended_units.sort(key=lambda u: (u["level"] != "foundational", -len(u["skills_covered"])))

    # مهنة مستهدفة (إن وُجدت)
    occupation_analysis: dict[str, object] = {}
    if request.for_occupation and request.for_occupation in OCCUPATIONS:
        occ = OCCUPATIONS[request.for_occupation]
        occupation_analysis = {
            "code": occ.code,
            "label_ar": occ.label_ar,
            "future_skills_demand": list(occ.future_skills),
            "recommended_first_unit": next(
                (u.code for u in TrainingUnit.all().values() if occ.code in u.target_occupations),
                None,
            ),
        }

    # تسلسل التأهيل حسب وثيقة المشروع §9.5: معلم ← أدوات ← منهج
    sequencing = "teacher_first" if request.institution_type == "school" else "skills_first"

    result: dict[str, object] = {
        "institution_type": request.institution_type,
        "curriculum_gap": gap,
        "recommended_units": recommended_units,
        "occupation_focus": occupation_analysis,
        "sequencing_principle": sequencing,
        "evidence_base": [
            "EU DigComp 3.0 (2025) — أطر كفاية الذكاء الاصطناعي",
            "OECD AILit (2025) — إطار محو الأمية الذكية للقياس والمقارنة",
            "WEF 2025 — المهارات الأسرع نمواً: الذكاء الاصطناعي والبيانات الضخمة والأمن السيبراني",
        ],
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
