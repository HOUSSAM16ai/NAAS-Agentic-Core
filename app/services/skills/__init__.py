"""
Skills Architecture — العمود الفقري المعماري لـ CogniForge.

CLAUDE.md §0.5: «قانون لا يُخرق: كل قدرة ذكاء اصطناعي في هذا النظام يجب أن تكون
Skill — وحدة مستقلة قابلة للقياس والاختبار والاستبدال. لا يوجد Prompt Spaghetti.»

كل Skill هنا يحترم العقد:
1. مسؤولية واحدة (single responsibility)
2. مدخلات/مخرجات Pydantic موحَّدة (typed contract)
3. مقاييس Prometheus (`cogniforge_skill_*_total` + `_duration_seconds`)
4. اختبارات (tests/skills/)
5. استقلالية (لا يستورد من Skill آخر مباشرة)

الـ Skills المتوفرة حالياً:
- `bac_exercise_skill.BACExerciseSkill` — استرجاع وشرح تمارين بكالوريا الجزائر.
- `math_skill.MathSkill` — حل وشرح أسئلة الرياضيات بـ Math Pipeline (D-061).
"""

from app.services.skills.bac_exercise_skill import (
    BACExerciseSkill,
    BACSkillExplanationOutput,
    BACSkillInput,
    BACSkillRetrievalOutput,
    SkillFailure,
    SkillMode,
)
from app.services.skills.math_skill import (
    MathSkill,
    MathSkillInput,
    MathSkillOutput,
)

__all__ = [
    "BACExerciseSkill",
    "BACSkillExplanationOutput",
    "BACSkillInput",
    "BACSkillRetrievalOutput",
    "MathSkill",
    "MathSkillInput",
    "MathSkillOutput",
    "SkillFailure",
    "SkillMode",
]
