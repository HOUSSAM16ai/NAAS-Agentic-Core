"""وكيل فجوة المهارات — وثيقة المشروع §4 وكيل 3 (مخرجه §8-3).

مخرجه: مقارنة المهارات المتوفرة بالمطلوبة على المستوى الفردي (أو القطاعي عبر
تجميع حتمي لمجموعة مهن). أساس المقارنة أطلس المهارات الحتمي — لا LLM يقرر
ما هي «المهارة المطلوبة».
"""

from __future__ import annotations

from microservices.transition_service.src.core import engine
from microservices.transition_service.src.data.occupations import (
    SKILLS,
)
from microservices.transition_service.src.schemas import (
    SkillsGapRequest,
    StandardResponse,
)

AGENT_NAME = "skills_gap"


async def skills_gap(request: SkillsGapRequest) -> StandardResponse:
    worker = request.worker
    occ = engine.occupation(worker.current_occupation)

    target_code = request.target_occupation or occ.code
    target = engine.occupation(target_code)

    # مهارات العامل المعلن + مهارات مهنته الحالية (يُجمَّع الاثنان)
    current_skills = sorted(set(worker.current_skills) | set(occ.current_skills))
    gap = engine.skills_gap(current_skills, target.future_skills)

    result: dict[str, object] = {
        "worker_id": worker.worker_id,
        "current_occupation": occ.code,
        "target_occupation": target_code,
        "skills_gap": gap,
        "missing_skill_details": [
            {
                "code": s,
                "label_ar": SKILLS[s].label_ar,
                "label_en": SKILLS[s].label_en,
                "kind": SKILLS[s].kind,
            }
            for s in gap["missing_skills"]
        ],
        "evidence_base": [
            "WEF 2025 — فجوة المهارات هي العائق رقم 1 للتحوّل (63% من أرباب العمل)",
            "WEF 2025 — 59% من القوى العاملة تحتاج إعادة تأهيل بحلول 2030",
        ],
    }
    return StandardResponse(agent=AGENT_NAME, result=result)
