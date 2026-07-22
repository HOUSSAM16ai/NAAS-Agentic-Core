"""
Skills Doctrine — Single Source of Truth لقواعد كل Skill في المشروع.

CLAUDE.md §0.5: «كل قدرة AI في النظام يجب أن تكون Skill — وحدة مستقلة قابلة
للقياس والاختبار والاستبدال». هذا الملف هو المرجع المركزي لكل قواعد التشغيل
التي يجب أن تحترمها الـ Skills.

**لماذا doctrine module مستقل؟**

قبل (Prompt Spaghetti):
    - قواعد الشرح متناثرة بين system prompts و LLM instructions
    - تغيير قاعدة = تعديل عشرات الـ prompts يدوياً
    - لا يوجد invariant CI gate يضمن أن الـ doctrine لم تنحرف

بعد (Skills Doctrine Module):
    - كل قاعدة تعيش كثابت Python (`tuple[str, ...]` أو `dict[str, str]`)
    - versioning صريح: تغيير قاعدة = bump version + update CI gate
    - اختبارات unit تثبت أن كل caller يحترم الـ doctrine الحية
    - CI gate يحرس على عدم drift بين الـ doctrine في الـ Skill والـ system prompt

**كيف يستخدم Skill قاعدة؟**

```python
from app.services.skills.doctrine import (
    RETRIEVAL_DOCTRINE,
    EXPLANATION_DOCTRINE,
    MODEL_ANSWER_RELIANCE_RULES,
)

# في Skill:
class BACExerciseSkill:
    def _build_explanation_prompt(self, full_content: str) -> str:
        return (
            "أنت أستاذ بكالوريا جزائر. اشرح وفقاً للقواعد التالية:\\n"
            + "\\n".join(f"- {r}" for r in EXPLANATION_DOCTRINE)
            + f"\\n\\nالتمرين + الإجابة النموذجية:\\n{full_content}"
        )
```

**كيف يضمن CI أن الـ doctrine متّسقة؟**

`scripts/fitness/check_skills_doctrine.py` يفحص:
1. كل Skill في `app/services/skills/` يستورد على الأقل قاعدة doctrine واحدة.
2. أي تعديل على قاعدة doctrine يجب أن يرافقه bump في الـ version.
3. الـ system prompts في `local_graph.py` تحتوي تمثيلاً قابلاً للتحقق من
   `EXPLANATION_DOCTRINE` (drift detection).

التاريخ:
    2026-05-18 (ISS-080 / D-068): إنشاء الـ doctrine module — استخراج
    EXPLANATION_DOCTRINE من `bac_exercise_skill.py`.

    2026-05-18 (ISS-CI-GREEN-001 / D-069): إضافة RETRIEVAL_DOCTRINE،
    MODEL_ANSWER_RELIANCE_RULES، CONTENT_INVOCATION_RULES، DETAILED_EXPLANATION_RULES
    كقواعد رسمية مستقلة، تطبيقاً لطلب المستخدم بتطوير منظومة الـ skills.

    2026-05-19 (D-070): تطوير منظومة Skills — إضافة:
    - CONTENT_INVOCATION_DOCTRINE: بروتوكول استدعاء المحتوى التعليمي خطوة بخطوة.
    - MODEL_ANSWER_EXPLANATION_DOCTRINE: كيفية شرح الإجابة النموذجية للطالب.
    - STEP_BY_STEP_EXPLANATION_RULES: قواعد الشرح خطوة بخطوة.
    - SKILL_INVOCATION_PROTOCOL: بروتوكول استدعاء الـ Skills.
"""

from __future__ import annotations

from app.services.skills.doctrine.exercise_core import (  # noqa: F401
    ANSWER_REDACTION_DOCTRINE,
    ANSWER_REDACTION_DOCTRINE_VERSION,
    DETAILED_EXPLANATION_RULES,
    DETAILED_EXPLANATION_VERSION,
    EXPLANATION_DOCTRINE,
    EXPLANATION_DOCTRINE_VERSION,
    MODEL_ANSWER_RELIANCE_RULES,
    MODEL_ANSWER_RELIANCE_VERSION,
    RETRIEVAL_DOCTRINE,
    RETRIEVAL_DOCTRINE_VERSION,
    WORKED_EXAMPLE_CLOSE,
    WORKED_EXAMPLE_DOCTRINE,
    WORKED_EXAMPLE_DOCTRINE_VERSION,
    WORKED_EXAMPLE_OPEN,
)
from app.services.skills.doctrine.invocation import (
    CONTENT_INVOCATION_DOCTRINE,
    CONTENT_INVOCATION_DOCTRINE_VERSION,
    MODEL_ANSWER_EXPLANATION_DOCTRINE,
    MODEL_ANSWER_EXPLANATION_VERSION,
    SKILL_INVOCATION_PROTOCOL,
    SKILL_INVOCATION_PROTOCOL_VERSION,
    STEP_BY_STEP_EXPLANATION_RULES,
    STEP_BY_STEP_EXPLANATION_VERSION,
)
from app.services.skills.doctrine.manifest_registry import (  # noqa: F401
    EXERCISE_EXPLANATION_SYSTEM_PROMPT,
    SKILL_DOCTRINE_MANIFEST,
    build_exercise_explanation_prompt,
    get_adaptive_pedagogy_summary,
    get_answer_redaction_summary,
    get_bkt_cognitive_summary,
    get_content_invocation_summary,
    get_detailed_explanation_summary,
    get_explanation_doctrine_summary,
    get_model_answer_explanation_summary,
    get_model_answer_reliance_summary,
    get_probability_calculation_summary,
    get_reasoning_core_summary,
    get_retrieval_doctrine_summary,
    get_skill_invocation_protocol_summary,
    get_step_by_step_summary,
    get_worked_example_summary,
    list_all_doctrines,
)
from app.services.skills.doctrine.pedagogy import (  # noqa: F401
    ADAPTIVE_PEDAGOGY_DOCTRINE,
    ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
    BKT_COGNITIVE_DOCTRINE,
    BKT_COGNITIVE_DOCTRINE_VERSION,
    CONCEPT_DIAGNOSIS_DOCTRINE,
    CONCEPT_DIAGNOSIS_DOCTRINE_VERSION,
    PEDAGOGICAL_POLICY_DOCTRINE,
    PEDAGOGICAL_POLICY_DOCTRINE_VERSION,
    SEMANTIC_PROPERTY_DOCTRINE,
    SEMANTIC_PROPERTY_DOCTRINE_VERSION,
    SOCRATIC_EVALUATOR_DOCTRINE,
    SOCRATIC_EVALUATOR_DOCTRINE_VERSION,
)
from app.services.skills.doctrine.platform_layer import (  # noqa: F401
    CONTENT_INTEGRITY_DOCTRINE,
    CONTENT_INTEGRITY_DOCTRINE_VERSION,
    DIALOGUE_MANAGER_DOCTRINE,
    DIALOGUE_MANAGER_DOCTRINE_VERSION,
    LEARNING_PATH_DOCTRINE,
    LEARNING_PATH_DOCTRINE_VERSION,
    MANDATORY_ORCHESTRATION_DOCTRINE,
    MANDATORY_ORCHESTRATION_DOCTRINE_VERSION,
    MICRO_SIMULATION_DOCTRINE,
    MICRO_SIMULATION_DOCTRINE_VERSION,
    PEDAGOGICAL_ESCALATION_DOCTRINE,
    PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION,
    REALTIME_PROTOCOL_DOCTRINE,
    REALTIME_PROTOCOL_DOCTRINE_VERSION,
    SKILLS_PLATFORM_DOCTRINE,
    SKILLS_PLATFORM_DOCTRINE_VERSION,
    STUDENT_STATE_DOCTRINE,
    STUDENT_STATE_DOCTRINE_VERSION,
    UNDERSTANDING_STATE_DOCTRINE,
    UNDERSTANDING_STATE_DOCTRINE_VERSION,
    get_content_integrity_summary,
    get_dialogue_manager_summary,
    get_learning_path_summary,
    get_mandatory_orchestration_summary,
    get_micro_simulation_summary,
    get_pedagogical_escalation_summary,
    get_realtime_protocol_summary,
    get_skills_platform_summary,
    get_student_state_summary,
    get_understanding_state_summary,
)
from app.services.skills.doctrine.probability import (
    IMPOSSIBLE_CASE_DOCTRINE,
    IMPOSSIBLE_CASE_DOCTRINE_VERSION,
    PROBABILITY_CALCULATION_DOCTRINE,
    PROBABILITY_CALCULATION_DOCTRINE_VERSION,
    get_impossible_case_summary,
)
from app.services.skills.doctrine.reasoning import (
    ABSTRACTION_DOCTRINE,
    ABSTRACTION_DOCTRINE_VERSION,
    CAUSAL_REASONING_DOCTRINE,
    CAUSAL_REASONING_DOCTRINE_VERSION,
    CRITICAL_THINKING_DOCTRINE,
    CRITICAL_THINKING_DOCTRINE_VERSION,
    LOGIC_REASONING_DOCTRINE,
    LOGIC_REASONING_DOCTRINE_VERSION,
    MENTAL_MODEL_DOCTRINE,
    MENTAL_MODEL_DOCTRINE_VERSION,
    PROBLEM_DECOMPOSITION_DOCTRINE,
    PROBLEM_DECOMPOSITION_DOCTRINE_VERSION,
    REASONING_CORE_DOCTRINE,
    REASONING_CORE_DOCTRINE_VERSION,
)

__all__ = [
    "ABSTRACTION_DOCTRINE",
    "ABSTRACTION_DOCTRINE_VERSION",
    "BKT_COGNITIVE_DOCTRINE",
    "BKT_COGNITIVE_DOCTRINE_VERSION",
    "CAUSAL_REASONING_DOCTRINE",
    "CAUSAL_REASONING_DOCTRINE_VERSION",
    "CONCEPT_DIAGNOSIS_DOCTRINE",
    "CONCEPT_DIAGNOSIS_DOCTRINE_VERSION",
    "CONTENT_INTEGRITY_DOCTRINE",
    "CONTENT_INTEGRITY_DOCTRINE_VERSION",
    "CONTENT_INVOCATION_DOCTRINE",
    "CONTENT_INVOCATION_DOCTRINE_VERSION",
    "CRITICAL_THINKING_DOCTRINE",
    "CRITICAL_THINKING_DOCTRINE_VERSION",
    "DETAILED_EXPLANATION_RULES",
    "DETAILED_EXPLANATION_VERSION",
    "EXERCISE_EXPLANATION_SYSTEM_PROMPT",
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "IMPOSSIBLE_CASE_DOCTRINE",
    "IMPOSSIBLE_CASE_DOCTRINE_VERSION",
    "LEARNING_PATH_DOCTRINE",
    "LEARNING_PATH_DOCTRINE_VERSION",
    "LOGIC_REASONING_DOCTRINE",
    "LOGIC_REASONING_DOCTRINE_VERSION",
    "MANDATORY_ORCHESTRATION_DOCTRINE",
    "MANDATORY_ORCHESTRATION_DOCTRINE_VERSION",
    "MENTAL_MODEL_DOCTRINE",
    "MENTAL_MODEL_DOCTRINE_VERSION",
    "MICRO_SIMULATION_DOCTRINE",
    "MICRO_SIMULATION_DOCTRINE_VERSION",
    "MODEL_ANSWER_EXPLANATION_DOCTRINE",
    "MODEL_ANSWER_EXPLANATION_VERSION",
    "MODEL_ANSWER_RELIANCE_RULES",
    "MODEL_ANSWER_RELIANCE_VERSION",
    "PEDAGOGICAL_ESCALATION_DOCTRINE",
    "PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION",
    "PEDAGOGICAL_POLICY_DOCTRINE",
    "PEDAGOGICAL_POLICY_DOCTRINE_VERSION",
    "PROBABILITY_CALCULATION_DOCTRINE",
    "PROBABILITY_CALCULATION_DOCTRINE_VERSION",
    "PROBLEM_DECOMPOSITION_DOCTRINE",
    "PROBLEM_DECOMPOSITION_DOCTRINE_VERSION",
    "REALTIME_PROTOCOL_DOCTRINE",
    "REALTIME_PROTOCOL_DOCTRINE_VERSION",
    "REASONING_CORE_DOCTRINE",
    "REASONING_CORE_DOCTRINE_VERSION",
    "RETRIEVAL_DOCTRINE",
    "RETRIEVAL_DOCTRINE_VERSION",
    "SEMANTIC_PROPERTY_DOCTRINE",
    "SEMANTIC_PROPERTY_DOCTRINE_VERSION",
    "SKILLS_PLATFORM_DOCTRINE",
    "SKILLS_PLATFORM_DOCTRINE_VERSION",
    "SKILL_DOCTRINE_MANIFEST",
    "SKILL_INVOCATION_PROTOCOL",
    "SKILL_INVOCATION_PROTOCOL_VERSION",
    "SOCRATIC_EVALUATOR_DOCTRINE",
    "SOCRATIC_EVALUATOR_DOCTRINE_VERSION",
    "STEP_BY_STEP_EXPLANATION_RULES",
    "STEP_BY_STEP_EXPLANATION_VERSION",
    "WORKED_EXAMPLE_CLOSE",
    "WORKED_EXAMPLE_DOCTRINE",
    "WORKED_EXAMPLE_DOCTRINE_VERSION",
    "WORKED_EXAMPLE_OPEN",
    "build_exercise_explanation_prompt",
    "get_bkt_cognitive_summary",
    "get_content_invocation_summary",
    "get_detailed_explanation_summary",
    "get_explanation_doctrine_summary",
    "get_impossible_case_summary",
    "get_micro_simulation_summary",
    "get_model_answer_explanation_summary",
    "get_model_answer_reliance_summary",
    "get_pedagogical_escalation_summary",
    "get_probability_calculation_summary",
    "get_realtime_protocol_summary",
    "get_reasoning_core_summary",
    "get_retrieval_doctrine_summary",
    "get_skill_invocation_protocol_summary",
    "get_skills_platform_summary",
    "get_step_by_step_summary",
    "get_worked_example_summary",
    "list_all_doctrines",
]
