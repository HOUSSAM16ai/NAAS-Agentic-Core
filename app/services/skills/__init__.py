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

from app.services.skills.adaptive_pedagogy_skill import (
    AdaptivePedagogySkill,
    PedagogyDirective,
    PedagogyInput,
    get_adaptive_pedagogy_skill,
)
from app.services.skills.answer_quality_skill import (
    AnswerQualityFailure,
    AnswerQualityInput,
    AnswerQualityOutput,
    AnswerQualitySkill,
    QualityIssue,
    get_answer_quality_skill,
)
from app.services.skills.answer_redaction_skill import (
    AnswerRedactionInput,
    AnswerRedactionOutput,
    AnswerRedactionSkill,
    get_answer_redaction_skill,
    redact_chunk,
    redact_final_answers,
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
from app.services.skills.concept_diagnosis_skill import (
    ConceptDiagnosisInput,
    ConceptDiagnosisOutput,
    ConceptDiagnosisSkill,
    get_concept_diagnosis_skill,
)
from app.services.skills.doctrine import (
    ANSWER_REDACTION_DOCTRINE,
    ANSWER_REDACTION_DOCTRINE_VERSION,
    BKT_COGNITIVE_DOCTRINE,
    BKT_COGNITIVE_DOCTRINE_VERSION,
    CONCEPT_DIAGNOSIS_DOCTRINE,
    CONCEPT_DIAGNOSIS_DOCTRINE_VERSION,
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
    PEDAGOGICAL_POLICY_DOCTRINE,
    PEDAGOGICAL_POLICY_DOCTRINE_VERSION,
    PROBABILITY_CALCULATION_DOCTRINE,
    PROBABILITY_CALCULATION_DOCTRINE_VERSION,
    RETRIEVAL_DOCTRINE,
    RETRIEVAL_DOCTRINE_VERSION,
    SEMANTIC_PROPERTY_DOCTRINE,
    SEMANTIC_PROPERTY_DOCTRINE_VERSION,
    SKILL_DOCTRINE_MANIFEST,
    SKILL_INVOCATION_PROTOCOL,
    SKILL_INVOCATION_PROTOCOL_VERSION,
    SOCRATIC_EVALUATOR_DOCTRINE,
    SOCRATIC_EVALUATOR_DOCTRINE_VERSION,
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
from app.services.skills.mcp_tool_skill import (
    MCPToolInput,
    MCPToolOutput,
    MCPToolSkill,
    get_mcp_tool_skill,
)
from app.services.skills.output_firewall import (
    ContaminationDetail,
    FirewallInput,
    FirewallOutput,
    OutputFirewall,
    apply_channel_b_firewall,
    get_output_firewall,
)
from app.services.skills.pedagogical_policy_skill import (
    PedagogicalPolicySkill,
    PolicyInput,
    PolicyOutput,
    get_pedagogical_policy_skill,
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
from app.services.skills.registry import (
    DEFAULT_REFINEMENT_STEPS,
    RefinementResult,
    RefinerResult,
    SkillDescriptor,
    SkillRegistry,
    compose_text_refinement,
    get_skill_registry,
)
from app.services.skills.retrieval_rerank_skill import (
    RetrievalRerankInput,
    RetrievalRerankOutput,
    RetrievalRerankSkill,
    get_retrieval_rerank_skill,
)
from app.services.skills.semantic_property_skill import (
    MISCONCEPTION_GRAPH,
    PROPERTY_REGISTRY,
    MisconceptionNode,
    MisconceptionOutput,
    SemanticPropertyInput,
    SemanticPropertyOutput,
    SemanticPropertySkill,
    get_semantic_property_skill,
)
from app.services.skills.socratic_evaluator_skill import (
    SocraticEvaluatorInput,
    SocraticEvaluatorOutput,
    SocraticEvaluatorSkill,
    get_socratic_evaluator_skill,
)
from app.services.skills.student_state_skill import (
    StudentState,
    StudentStateInput,
    StudentStateSkill,
    get_student_state_skill,
)
from app.services.skills.topic_lock import (
    TopicLock,
    TopicLockInput,
    TopicLockOutput,
    get_topic_lock,
)
from app.services.skills.understanding_state_skill import (
    KnowledgeComponent,
    UnderstandingDecision,
    UnderstandingStateSkill,
    get_understanding_state_skill,
)

__all__ = [
    "ANSWER_REDACTION_DOCTRINE",
    "ANSWER_REDACTION_DOCTRINE_VERSION",
    "BKT_COGNITIVE_DOCTRINE",
    "BKT_COGNITIVE_DOCTRINE_VERSION",
    "CONCEPT_DIAGNOSIS_DOCTRINE",
    "CONCEPT_DIAGNOSIS_DOCTRINE_VERSION",
    "CONTENT_INVOCATION_DOCTRINE",
    "CONTENT_INVOCATION_DOCTRINE_VERSION",
    "DEFAULT_REFINEMENT_STEPS",
    "DETAILED_EXPLANATION_RULES",
    "DETAILED_EXPLANATION_VERSION",
    "EXERCISE_EXPLANATION_SYSTEM_PROMPT",
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "MISCONCEPTION_GRAPH",
    "MODEL_ANSWER_EXPLANATION_DOCTRINE",
    "MODEL_ANSWER_EXPLANATION_VERSION",
    "MODEL_ANSWER_RELIANCE_RULES",
    "MODEL_ANSWER_RELIANCE_VERSION",
    "PEDAGOGICAL_POLICY_DOCTRINE",
    "PEDAGOGICAL_POLICY_DOCTRINE_VERSION",
    "PROBABILITY_CALCULATION_DOCTRINE",
    "PROBABILITY_CALCULATION_DOCTRINE_VERSION",
    "PROPERTY_REGISTRY",
    "RETRIEVAL_DOCTRINE",
    "RETRIEVAL_DOCTRINE_VERSION",
    "SEMANTIC_PROPERTY_DOCTRINE",
    "SEMANTIC_PROPERTY_DOCTRINE_VERSION",
    "SKILL_DOCTRINE_MANIFEST",
    "SKILL_INVOCATION_PROTOCOL",
    "SKILL_INVOCATION_PROTOCOL_VERSION",
    "SOCRATIC_EVALUATOR_DOCTRINE",
    "SOCRATIC_EVALUATOR_DOCTRINE_VERSION",
    "STEP_BY_STEP_EXPLANATION_RULES",
    "STEP_BY_STEP_EXPLANATION_VERSION",
    "AdaptivePedagogySkill",
    "AnswerQualityFailure",
    "AnswerQualityInput",
    "AnswerQualityOutput",
    "AnswerQualitySkill",
    "AnswerRedactionInput",
    "AnswerRedactionOutput",
    "AnswerRedactionSkill",
    "BACExerciseSkill",
    "BACSkillExplanationOutput",
    "BACSkillInput",
    "BACSkillRetrievalOutput",
    "BKTEngine",
    "BKTEvaluation",
    "BKTEvaluationInput",
    "CompositionItem",
    "ConceptDiagnosisInput",
    "ConceptDiagnosisOutput",
    "ConceptDiagnosisSkill",
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
    "KnowledgeComponent",
    "MCPToolInput",
    "MCPToolOutput",
    "MCPToolSkill",
    "MathSkill",
    "MathSkillInput",
    "MathSkillOutput",
    "MisconceptionNode",
    "MisconceptionOutput",
    "OutputFirewall",
    "PedagogicalPolicySkill",
    "PedagogyDirective",
    "PedagogyInput",
    "PolicyInput",
    "PolicyOutput",
    "ProbabilityCalculatorSkill",
    "ProbabilityFailure",
    "ProbabilityInput",
    "ProbabilityModelOutput",
    "QualityIssue",
    "RefinementResult",
    "RefinerResult",
    "RetrievalRerankInput",
    "RetrievalRerankOutput",
    "RetrievalRerankSkill",
    "SemanticPropertyInput",
    "SemanticPropertyOutput",
    "SemanticPropertySkill",
    "SkillDescriptor",
    "SkillFailure",
    "SkillMode",
    "SkillRegistry",
    "SocraticEvaluatorInput",
    "SocraticEvaluatorOutput",
    "SocraticEvaluatorSkill",
    "StudentState",
    "StudentStateInput",
    "StudentStateSkill",
    "TopicLock",
    "TopicLockInput",
    "TopicLockOutput",
    "UnderstandingDecision",
    "UnderstandingStateSkill",
    "apply_channel_b_firewall",
    "arabic_prose_ratio",
    "build_exercise_explanation_prompt",
    "compose_text_refinement",
    "get_adaptive_pedagogy_skill",
    "get_answer_quality_skill",
    "get_answer_redaction_skill",
    "get_bkt_cognitive_summary",
    "get_bkt_engine",
    "get_concept_diagnosis_skill",
    "get_content_invocation_summary",
    "get_detailed_explanation_summary",
    "get_exercise_alignment_skill",
    "get_explanation_doctrine_summary",
    "get_mcp_tool_skill",
    "get_model_answer_explanation_summary",
    "get_model_answer_reliance_summary",
    "get_output_firewall",
    "get_pedagogical_policy_skill",
    "get_probability_calculation_summary",
    "get_retrieval_doctrine_summary",
    "get_retrieval_rerank_skill",
    "get_semantic_property_skill",
    "get_skill_invocation_protocol_summary",
    "get_skill_registry",
    "get_socratic_evaluator_skill",
    "get_step_by_step_summary",
    "get_student_state_skill",
    "get_topic_lock",
    "get_understanding_state_skill",
    "guard_arabic_stream",
    "is_probably_non_arabic",
    "list_all_doctrines",
    "redact_chunk",
    "redact_final_answers",
    "sanitize_stream_chunk",
]
