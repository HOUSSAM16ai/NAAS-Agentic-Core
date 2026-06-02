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
- `answer_quality_skill.AnswerQualitySkill` — تقييم جودة الإجابة وتحسينها (D-072).
- `bkt_engine.BKTEngine` — الطبقة المعرفية الأساسية (Bayesian Knowledge Tracing،
  D-074). الأساس الذي تُبنى فوقه كل القدرات التكيّفية المستقبلية. يلتزم بـ
  `BKT_COGNITIVE_DOCTRINE` (الإصدار `BKT_COGNITIVE_DOCTRINE_VERSION`).
- `output_firewall.OutputFirewall` — جدار الحماية المزدوج للقنوات (D-086 — V46.0).
  يرفض/ينظف HTML/JSX من القناة B (صوت المعلم). المعلم لا يُصيِّر — المعلم يشرح.
- `topic_lock.TopicLock` — قفل الموضوع وحماية نقاء السياق (D-086 — V46.0).
  يُسجِّل انتهاكات تسرب المواضيع دون كسر المسار.

**D-069 (2026-05-18)** — Skills Doctrine Module:
الـ `doctrine` module يُصدِّر القواعد الرسمية لكيفية:
- استدعاء المحتوى (RETRIEVAL_DOCTRINE)
- شرح الإجابة النموذجية (EXPLANATION_DOCTRINE — v2.0.0)
- الاعتماد على الإجابة النموذجية أثناء الشرح المفصل (MODEL_ANSWER_RELIANCE_RULES)
- ضوابط الشرح المفصل حسب نوع السؤال (DETAILED_EXPLANATION_RULES)

**D-072 (2026-05-19)** — AnswerQualitySkill:
Skill جديد يُقيِّم جودة إجابة LLM قبل إرسالها للطالب ويُصحِّح المشاكل تلقائياً.

**D-086 (2026-05-23)** — OutputFirewall + TopicLock (Protocol V46.0):
فصل صارم بين القناة A (JSON هيكلي) والقناة B (صوت المعلم).
جدار الحماية يرفض أو ينظف أي HTML/JSX في القناة B.
قفل الموضوع يُسجِّل انتهاكات تسرب المواضيع.
"""

from app.services.skills.answer_quality_skill import (
    AnswerQualityFailure,
    AnswerQualityInput,
    AnswerQualityOutput,
    AnswerQualitySkill,
    QualityIssue,
    get_answer_quality_skill,
)
from app.services.skills.arabic_stream_guard import (
    arabic_prose_ratio,
    guard_arabic_stream,
    is_probably_non_arabic,
    sanitize_stream_chunk,
)
from app.services.skills.bac_exercise_skill import (
    BACExerciseSkill,
    BACSkillExplanationOutput,
    BACSkillInput,
    BACSkillRetrievalOutput,
    SkillFailure,
    SkillMode,
)
from app.services.skills.bkt_engine import (
    BKTEngine,
    BKTEvaluation,
    BKTEvaluationInput,
    get_bkt_engine,
)
from app.services.skills.doctrine import (
    BKT_COGNITIVE_DOCTRINE,
    BKT_COGNITIVE_DOCTRINE_VERSION,
    CONTENT_INVOCATION_DOCTRINE,
    CONTENT_INVOCATION_DOCTRINE_VERSION,
    DETAILED_EXPLANATION_RULES,
    DETAILED_EXPLANATION_VERSION,
    EXERCISE_EXPLANATION_SYSTEM_PROMPT,
    EXPLANATION_DOCTRINE,
    EXPLANATION_DOCTRINE_VERSION,
    MODEL_ANSWER_EXPLANATION_DOCTRINE,
    MODEL_ANSWER_EXPLANATION_VERSION,
    MODEL_ANSWER_RELIANCE_RULES,
    MODEL_ANSWER_RELIANCE_VERSION,
    PROBABILITY_CALCULATION_DOCTRINE,
    PROBABILITY_CALCULATION_DOCTRINE_VERSION,
    RETRIEVAL_DOCTRINE,
    RETRIEVAL_DOCTRINE_VERSION,
    SKILL_DOCTRINE_MANIFEST,
    SKILL_INVOCATION_PROTOCOL,
    SKILL_INVOCATION_PROTOCOL_VERSION,
    STEP_BY_STEP_EXPLANATION_RULES,
    STEP_BY_STEP_EXPLANATION_VERSION,
    build_exercise_explanation_prompt,
    get_bkt_cognitive_summary,
    get_content_invocation_summary,
    get_detailed_explanation_summary,
    get_explanation_doctrine_summary,
    get_model_answer_explanation_summary,
    get_model_answer_reliance_summary,
    get_probability_calculation_summary,
    get_retrieval_doctrine_summary,
    get_skill_invocation_protocol_summary,
    get_step_by_step_summary,
    list_all_doctrines,
)
from app.services.skills.exercise_alignment_skill import (
    ExerciseAlignmentInput,
    ExerciseAlignmentOutput,
    ExerciseAlignmentSkill,
    get_exercise_alignment_skill,
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
from app.services.skills.output_firewall import (
    ContaminationDetail,
    FirewallInput,
    FirewallOutput,
    OutputFirewall,
    apply_channel_b_firewall,
    get_output_firewall,
)
from app.services.skills.probability_skill import (
    CompositionItem,
    ExerciseStep,
    FullExerciseStoryOutput,
    ProbabilityCalculatorSkill,
    ProbabilityFailure,
    ProbabilityInput,
    ProbabilityModelOutput,
)
from app.services.skills.topic_lock import (
    TopicLock,
    TopicLockInput,
    TopicLockOutput,
    get_topic_lock,
)

__all__ = [
    "BKT_COGNITIVE_DOCTRINE",
    "BKT_COGNITIVE_DOCTRINE_VERSION",
    "CONTENT_INVOCATION_DOCTRINE",
    "CONTENT_INVOCATION_DOCTRINE_VERSION",
    "DETAILED_EXPLANATION_RULES",
    "DETAILED_EXPLANATION_VERSION",
    "EXERCISE_EXPLANATION_SYSTEM_PROMPT",
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "MODEL_ANSWER_EXPLANATION_DOCTRINE",
    "MODEL_ANSWER_EXPLANATION_VERSION",
    "MODEL_ANSWER_RELIANCE_RULES",
    "MODEL_ANSWER_RELIANCE_VERSION",
    "PROBABILITY_CALCULATION_DOCTRINE",
    "PROBABILITY_CALCULATION_DOCTRINE_VERSION",
    "RETRIEVAL_DOCTRINE",
    "RETRIEVAL_DOCTRINE_VERSION",
    "SKILL_DOCTRINE_MANIFEST",
    "SKILL_INVOCATION_PROTOCOL",
    "SKILL_INVOCATION_PROTOCOL_VERSION",
    "STEP_BY_STEP_EXPLANATION_RULES",
    "STEP_BY_STEP_EXPLANATION_VERSION",
    "AnswerQualityFailure",
    "AnswerQualityInput",
    "AnswerQualityOutput",
    "AnswerQualitySkill",
    "BACExerciseSkill",
    "BACSkillExplanationOutput",
    "BACSkillInput",
    "BACSkillRetrievalOutput",
    "BKTEngine",
    "BKTEvaluation",
    "BKTEvaluationInput",
    "CompositionItem",
    "ContaminationDetail",
    "ExerciseAlignmentInput",
    "ExerciseAlignmentOutput",
    "ExerciseAlignmentSkill",
    "ExerciseStep",
    "FirewallInput",
    "FirewallOutput",
    "FullExerciseStoryOutput",
    "GreetingSkill",
    "GreetingSkillFailure",
    "GreetingSkillInput",
    "GreetingSkillOutput",
    "GreetingSkillResult",
    "MathSkill",
    "MathSkillInput",
    "MathSkillOutput",
    "OutputFirewall",
    "ProbabilityCalculatorSkill",
    "ProbabilityFailure",
    "ProbabilityInput",
    "ProbabilityModelOutput",
    "QualityIssue",
    "SkillFailure",
    "SkillMode",
    "TopicLock",
    "TopicLockInput",
    "TopicLockOutput",
    "apply_channel_b_firewall",
    "arabic_prose_ratio",
    "build_exercise_explanation_prompt",
    "get_answer_quality_skill",
    "get_bkt_cognitive_summary",
    "get_bkt_engine",
    "get_content_invocation_summary",
    "get_detailed_explanation_summary",
    "get_exercise_alignment_skill",
    "get_explanation_doctrine_summary",
    "get_model_answer_explanation_summary",
    "get_model_answer_reliance_summary",
    "get_output_firewall",
    "get_probability_calculation_summary",
    "get_retrieval_doctrine_summary",
    "get_skill_invocation_protocol_summary",
    "get_step_by_step_summary",
    "get_topic_lock",
    "guard_arabic_stream",
    "is_probably_non_arabic",
    "list_all_doctrines",
    "sanitize_stream_chunk",
]
