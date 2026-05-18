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
- `greeting_skill.GreetingSkill` — ردود التحيات الحتمية (D-067 — يحل ISS-079).
- `bac_exercise_skill.BACExerciseSkill` — استرجاع وشرح تمارين بكالوريا الجزائر.
- `math_skill.MathSkill` — حل وشرح أسئلة الرياضيات بـ Math Pipeline (D-061).

**D-069 (2026-05-18)** — Skills Doctrine Module:
الـ `doctrine` module يُصدِّر القواعد الرسمية لكيفية:
- استدعاء المحتوى (RETRIEVAL_DOCTRINE)
- شرح الإجابة النموذجية (EXPLANATION_DOCTRINE — v2.0.0)
- الاعتماد على الإجابة النموذجية أثناء الشرح المفصل (MODEL_ANSWER_RELIANCE_RULES)
- ضوابط الشرح المفصل حسب نوع السؤال (DETAILED_EXPLANATION_RULES)
"""

from app.services.skills.bac_exercise_skill import (
    BACExerciseSkill,
    BACSkillExplanationOutput,
    BACSkillInput,
    BACSkillRetrievalOutput,
    SkillFailure,
    SkillMode,
)
from app.services.skills.doctrine import (
    DETAILED_EXPLANATION_RULES,
    DETAILED_EXPLANATION_VERSION,
    EXPLANATION_DOCTRINE,
    EXPLANATION_DOCTRINE_VERSION,
    MODEL_ANSWER_RELIANCE_RULES,
    MODEL_ANSWER_RELIANCE_VERSION,
    RETRIEVAL_DOCTRINE,
    RETRIEVAL_DOCTRINE_VERSION,
    SKILL_DOCTRINE_MANIFEST,
    get_detailed_explanation_summary,
    get_explanation_doctrine_summary,
    get_model_answer_reliance_summary,
    get_retrieval_doctrine_summary,
    list_all_doctrines,
)
from app.services.skills.greeting_skill import (
    GreetingSkill,
    GreetingSkillFailure,
    GreetingSkillInput,
    GreetingSkillOutput,
    GreetingSkillResult,
)
from app.services.skills.math_skill import (
    MathSkill,
    MathSkillInput,
    MathSkillOutput,
)

__all__ = [
    # Doctrines (D-069)
    "DETAILED_EXPLANATION_RULES",
    "DETAILED_EXPLANATION_VERSION",
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "MODEL_ANSWER_RELIANCE_RULES",
    "MODEL_ANSWER_RELIANCE_VERSION",
    "RETRIEVAL_DOCTRINE",
    "RETRIEVAL_DOCTRINE_VERSION",
    "SKILL_DOCTRINE_MANIFEST",
    # Skills
    "BACExerciseSkill",
    "BACSkillExplanationOutput",
    "BACSkillInput",
    "BACSkillRetrievalOutput",
    "GreetingSkill",
    "GreetingSkillFailure",
    "GreetingSkillInput",
    "GreetingSkillOutput",
    "GreetingSkillResult",
    "MathSkill",
    "MathSkillInput",
    "MathSkillOutput",
    "SkillFailure",
    "SkillMode",
    "get_detailed_explanation_summary",
    "get_explanation_doctrine_summary",
    "get_model_answer_reliance_summary",
    "get_retrieval_doctrine_summary",
    "list_all_doctrines",
]
