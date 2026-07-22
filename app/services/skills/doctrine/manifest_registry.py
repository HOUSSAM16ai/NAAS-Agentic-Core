"""Manifest Registry — sliced verbatim from the former doctrine.py (D-173 Stage 2a).

جزء من حزمة `app.services.skills.doctrine` — المصدر الوحيد للحقيقة لقواعد كل
Skill. لا تُعرَّف doctrines خارج هذه الحزمة (بوّابة skills-doctrine تحرس ذلك).
"""

from __future__ import annotations

from typing import Final

from app.services.skills.doctrine.exercise_core import (
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
    WORKED_EXAMPLE_DOCTRINE,
    WORKED_EXAMPLE_DOCTRINE_VERSION,
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
from app.services.skills.doctrine.pedagogy import (
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
from app.services.skills.doctrine.platform_layer import (
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
)
from app.services.skills.doctrine.probability import (
    IMPOSSIBLE_CASE_DOCTRINE,
    IMPOSSIBLE_CASE_DOCTRINE_VERSION,
    PROBABILITY_CALCULATION_DOCTRINE,
    PROBABILITY_CALCULATION_DOCTRINE_VERSION,
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

# ─────────────────────────────────────────────────────────────────────────────

#: All-in-one manifest يُصدِّره الـ Skill module للـ CI gate لفحص الـ drift.
SKILL_DOCTRINE_MANIFEST: Final[dict[str, dict[str, object]]] = {
    "retrieval": {
        "version": RETRIEVAL_DOCTRINE_VERSION,
        "rules_count": len(RETRIEVAL_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._retrieve",
            "orchestrator_client._stream_local_retrieval_response",
            "exercise_retrieval.detect_exercise_retrieval",
        ),
    },
    "explanation": {
        "version": EXPLANATION_DOCTRINE_VERSION,
        "rules_count": len(EXPLANATION_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._explain",
            "local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT",
            "BACSkillExplanationOutput.methodology_handle",
        ),
    },
    "model_answer_reliance": {
        "version": MODEL_ANSWER_RELIANCE_VERSION,
        "rules_count": len(MODEL_ANSWER_RELIANCE_RULES),
        "consumed_by": (
            "BACExerciseSkill._explain",
            "local_graph.run_local_graph_with_exercise_context",
        ),
    },
    "detailed_explanation": {
        "version": DETAILED_EXPLANATION_VERSION,
        "rules_count": len(DETAILED_EXPLANATION_RULES),
        "consumed_by": ("local_graph._classify_question_budget",),
    },
    "content_invocation": {
        "version": CONTENT_INVOCATION_DOCTRINE_VERSION,
        "rules_count": len(CONTENT_INVOCATION_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._retrieve",
            "local_graph.run_local_graph_with_exercise_context",
            "orchestrator_client._stream_local_retrieval_response",
        ),
    },
    "model_answer_explanation": {
        "version": MODEL_ANSWER_EXPLANATION_VERSION,
        "rules_count": len(MODEL_ANSWER_EXPLANATION_DOCTRINE),
        "consumed_by": (
            "BACExerciseSkill._explain",
            "local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT",
        ),
    },
    "step_by_step_explanation": {
        "version": STEP_BY_STEP_EXPLANATION_VERSION,
        "rules_count": len(STEP_BY_STEP_EXPLANATION_RULES),
        "consumed_by": (
            "local_graph._classify_question_budget",
            "BACExerciseSkill._explain",
        ),
    },
    "skill_invocation_protocol": {
        "version": SKILL_INVOCATION_PROTOCOL_VERSION,
        "rules_count": len(SKILL_INVOCATION_PROTOCOL),
        "consumed_by": (
            "orchestrator_client.chat_with_agent",
            "local_graph.run_local_graph",
        ),
    },
    "answer_quality": {
        "version": "1.0.0",
        "rules_count": 6,
        "consumed_by": (
            "AnswerQualitySkill.evaluate",
            # D-073 (2026-05-19): wired into the live monolith path.
            "local_graph._apply_answer_quality_skill",
        ),
    },
    "answer_redaction": {
        "version": ANSWER_REDACTION_DOCTRINE_VERSION,
        "rules_count": len(ANSWER_REDACTION_DOCTRINE),
        "consumed_by": (
            # D-113 (ISS-115): الحارس الحتمي الأخير ضد كشف الإجابة النهائية.
            "AnswerRedactionSkill.redact",
            "content_integrity.sanitize_final_text",
            "local_graph._apply_answer_redaction",
        ),
    },
    "bkt_cognitive": {
        "version": BKT_COGNITIVE_DOCTRINE_VERSION,
        "rules_count": len(BKT_COGNITIVE_DOCTRINE),
        "consumed_by": (
            # D-074 (Protocol V6.0): الطبقة المعرفية الأساسية — موصولة حيّاً.
            "BKTEngine.evaluate",
            "bkt_persistence.BKTAnalyticsService.evaluate_and_record",
            "customer_chat._evaluate_bkt_cards",
            "orchestrator_client._build_probability_tree_props",
        ),
    },
    "concept_diagnosis": {
        "version": CONCEPT_DIAGNOSIS_DOCTRINE_VERSION,
        "rules_count": len(CONCEPT_DIAGNOSIS_DOCTRINE),
        "consumed_by": (
            # D-127: الطبقتان 1+5 — موصولة حيّاً في مخرج الطوارئ الاحتمالي.
            "ConceptDiagnosisSkill.diagnose",
            "orchestrator_client.chat_with_agent",
        ),
    },
    "semantic_property": {
        "version": SEMANTIC_PROPERTY_DOCTRINE_VERSION,
        "rules_count": len(SEMANTIC_PROPERTY_DOCTRINE),
        "consumed_by": (
            # D-131: الطبقة 2 — الطبقة الدلالية + Misconception Graph.
            "SemanticPropertySkill.interpret",
            "orchestrator_client._build_cognitive_response",
        ),
    },
    "pedagogical_policy": {
        "version": PEDAGOGICAL_POLICY_DOCTRINE_VERSION,
        "rules_count": len(PEDAGOGICAL_POLICY_DOCTRINE),
        "consumed_by": (
            # D-129: الطبقة 4 — موصولة حيّاً في مخرج الطوارئ الاحتمالي.
            "PedagogicalPolicySkill.decide",
            "orchestrator_client.chat_with_agent",
        ),
    },
    "socratic_evaluator": {
        "version": SOCRATIC_EVALUATOR_DOCTRINE_VERSION,
        "rules_count": len(SOCRATIC_EVALUATOR_DOCTRINE),
        "consumed_by": (
            # D-130: الطبقة 1 (الإصغاء النشط) — موصولة حيّاً قبل الاسترجاع المُفهرَس.
            "SocraticEvaluatorSkill.evaluate",
            "orchestrator_client._stream_socratic_evaluation",
        ),
    },
    "adaptive_pedagogy": {
        "version": ADAPTIVE_PEDAGOGY_DOCTRINE_VERSION,
        "rules_count": len(ADAPTIVE_PEDAGOGY_DOCTRINE),
        "consumed_by": (
            "AdaptivePedagogySkill.derive",
            "customer_chat._build_pedagogy_directive",
            "orchestrator_client.chat_with_agent",
        ),
    },
    "probability_calculation": {
        "version": PROBABILITY_CALCULATION_DOCTRINE_VERSION,
        "rules_count": len(PROBABILITY_CALCULATION_DOCTRINE),
        "consumed_by": (
            # D-075 (Protocol V14.0): محرّك الاحتمالات الحتمي — موصول حيّاً.
            "ProbabilityCalculatorSkill.analyze",
            "orchestrator_client._build_probability_tree_props",
            # D-078 (Protocol V19.0): الموجِّه التربوي (آني/تتابعي) — موصول حيّاً.
            "orchestrator_client._build_calculated_ui",
        ),
    },
    "impossible_case": {
        "version": IMPOSSIBLE_CASE_DOCTRINE_VERSION,
        "rules_count": len(IMPOSSIBLE_CASE_DOCTRINE),
        "consumed_by": (
            # D-082: content-retrieval-skill /impossible-case endpoint.
            "content_retrieval_skill.src.impossible_case.analyze_impossible_case",
            # frontend: ImpossibleCaseRenderer (4 مراحل بصرية).
            "frontend.components.ImpossibleCaseRenderer",
        ),
    },
    "realtime_protocol": {
        "version": REALTIME_PROTOCOL_DOCTRINE_VERSION,
        "rules_count": len(REALTIME_PROTOCOL_DOCTRINE),
        "consumed_by": (
            # D-WS-FLAP-002 (2026-05-26): معالج موحَّد لـ ping/pong عبر كل WS endpoints.
            "ws_heartbeat_skill.handle_control_message",
            "customer_chat.chat_stream_ws",
            "admin.admin_chat_stream_ws",
            "conversation_service.main.chat_ws",
            "conversation_service.main.admin_chat_ws",
        ),
    },
    "skills_platform": {
        "version": SKILLS_PLATFORM_DOCTRINE_VERSION,
        "rules_count": len(SKILLS_PLATFORM_DOCTRINE),
        "consumed_by": (
            # D-100: المنصّة الموحَّدة — registry + composition + observability.
            "api.routers.skills.list_skills",
            "api.routers.skills.refine_endpoint",
            "registry.get_skill_registry",
        ),
    },
    "content_integrity": {
        "version": CONTENT_INTEGRITY_DOCTRINE_VERSION,
        "rules_count": len(CONTENT_INTEGRITY_DOCTRINE),
        "consumed_by": (
            # D-106 (ISS-114): حارس نزاهة المحتوى — موصول حيّاً عند مخرج البثّ.
            "ContentIntegritySkill.check",
            "orchestrator_client.chat_with_agent",
            "local_graph.run_local_graph_stream",
            "local_graph.run_local_graph_with_exercise_context",
        ),
    },
    "learning_path": {
        "version": LEARNING_PATH_DOCTRINE_VERSION,
        "rules_count": len(LEARNING_PATH_DOCTRINE),
        "consumed_by": (
            # D-111: المسار التعلّمي التكيفي — موصول حيّاً بعد تقييم BKT.
            "LearningPathSkill.derive",
            "customer_chat._evaluate_bkt_cards",
        ),
    },
    "mandatory_orchestration": {
        "version": MANDATORY_ORCHESTRATION_DOCTRINE_VERSION,
        "rules_count": len(MANDATORY_ORCHESTRATION_DOCTRINE),
        "consumed_by": (
            # D-112: العمود الفقري الإلزامي — hard-fail عند تعذّر الـ orchestrator.
            "orchestrator_client.chat_with_agent",
        ),
    },
    "worked_example": {
        "version": WORKED_EXAMPLE_DOCTRINE_VERSION,
        "rules_count": len(WORKED_EXAMPLE_DOCTRINE),
        "consumed_by": (
            # D-115 (ISS-116): البروتوكول السقراطي المنضبط — التوليد في الـ orchestrator.
            "search.SynthesizerNode",
            "content_integrity.strip_garbage_markers",
            "answer_redaction.redact_final_answers",
        ),
    },
    "student_state": {
        "version": STUDENT_STATE_DOCTRINE_VERSION,
        "rules_count": len(STUDENT_STATE_DOCTRINE),
        "consumed_by": (
            # D-133: قراءة حالة الطالب (نيّة + إحباط) — إشارة قرار موصولة حيّاً.
            "StudentStateSkill.read",
            "orchestrator_client.chat_with_agent",
            "pedagogical_policy.PolicyInput",
        ),
    },
    "dialogue_manager": {
        "version": DIALOGUE_MANAGER_DOCTRINE_VERSION,
        "rules_count": len(DIALOGUE_MANAGER_DOCTRINE),
        "consumed_by": (
            # D-142 Phase 2: سلطة قرار الدور — موصولة حيّاً في المسار السقراطي (خلف العلم).
            "DialogueManagerSkill.decide",
            "orchestrator_client._stream_socratic_evaluation",
            # D-158: طبقة القرار الموحَّدة فوق tutor_state.kc_progress الدائم (خلف COGNITIVE_TURN_ENABLED).
            "orchestrator_client._cognitive_turn",
        ),
    },
    "understanding_state": {
        "version": UNDERSTANDING_STATE_DOCTRINE_VERSION,
        "rules_count": len(UNDERSTANDING_STATE_DOCTRINE),
        "consumed_by": (
            # D-135: محرّك حالة الفهم (Learning State) — موصول حيّاً في مخرج الطوارئ.
            "UnderstandingStateSkill.decide",
            "orchestrator_client.chat_with_agent",
        ),
    },
    "pedagogical_escalation": {
        "version": PEDAGOGICAL_ESCALATION_DOCTRINE_VERSION,
        "rules_count": len(PEDAGOGICAL_ESCALATION_DOCTRINE),
        "consumed_by": (
            # D-138: المصفوفة التصعيدية التكيّفية — موصولة حيّاً في بلوك تعليم المفهوم.
            "PedagogicalEscalationSkill.decide",
            "orchestrator_client.chat_with_agent",
        ),
    },
    "micro_simulation": {
        "version": MICRO_SIMULATION_DOCTRINE_VERSION,
        "rules_count": len(MICRO_SIMULATION_DOCTRINE),
        "consumed_by": (
            # D-138: خادم محتوى L3 الحتمي — موصول حيّاً عبر المصفوفة التصعيدية.
            "MicroSimulationSkill.get_micro_simulation",
            "PedagogicalEscalationSkill.decide",
            "orchestrator_client.chat_with_agent",
        ),
    },
    # ── D-181: النواة المعرفية للتفكير (Cognitive Reasoning Core) ──────────────
    "reasoning_core": {
        "version": REASONING_CORE_DOCTRINE_VERSION,
        "rules_count": len(REASONING_CORE_DOCTRINE),
        "consumed_by": (
            # D-181: القاعدة الجامعة لمهارات التفكير الستّ فوق app/core/reasoning.
            "registry.compose_reasoning",
            "api.routers.skills.reason_endpoint",
        ),
    },
    "logic_reasoning": {
        "version": LOGIC_REASONING_DOCTRINE_VERSION,
        "rules_count": len(LOGIC_REASONING_DOCTRINE),
        "consumed_by": (
            "LogicReasoningSkill.analyze",
            "registry.compose_reasoning",
        ),
    },
    "critical_thinking": {
        "version": CRITICAL_THINKING_DOCTRINE_VERSION,
        "rules_count": len(CRITICAL_THINKING_DOCTRINE),
        "consumed_by": (
            "CriticalThinkingSkill.analyze",
            "registry.compose_reasoning",
        ),
    },
    "problem_decomposition": {
        "version": PROBLEM_DECOMPOSITION_DOCTRINE_VERSION,
        "rules_count": len(PROBLEM_DECOMPOSITION_DOCTRINE),
        "consumed_by": (
            "ProblemDecompositionSkill.decompose",
            "registry.compose_reasoning",
        ),
    },
    "causal_reasoning": {
        "version": CAUSAL_REASONING_DOCTRINE_VERSION,
        "rules_count": len(CAUSAL_REASONING_DOCTRINE),
        "consumed_by": (
            "CausalReasoningSkill.analyze",
            "registry.compose_reasoning",
        ),
    },
    "abstraction": {
        "version": ABSTRACTION_DOCTRINE_VERSION,
        "rules_count": len(ABSTRACTION_DOCTRINE),
        "consumed_by": (
            "AbstractionSkill.generalize",
            "registry.compose_reasoning",
        ),
    },
    "mental_model": {
        "version": MENTAL_MODEL_DOCTRINE_VERSION,
        "rules_count": len(MENTAL_MODEL_DOCTRINE),
        "consumed_by": (
            "MentalModelSkill.build",
            "registry.compose_reasoning",
        ),
    },
}


def get_retrieval_doctrine_summary() -> str:
    """يُرجِع doctrine الاستدعاء كنص قصير (للاستخدام في prompts / logs)."""
    return " | ".join(RETRIEVAL_DOCTRINE)


def get_explanation_doctrine_summary() -> str:
    """يُرجِع doctrine الشرح كنص قصير (للاستخدام في system prompts)."""
    return " | ".join(EXPLANATION_DOCTRINE)


def get_model_answer_reliance_summary() -> str:
    """يُرجِع doctrine الاحتجاج بالإجابة النموذجية (للـ prompts)."""
    return " | ".join(MODEL_ANSWER_RELIANCE_RULES)


def get_detailed_explanation_summary() -> str:
    """يُرجِع doctrine الشرح المفصل (للـ prompts)."""
    return " | ".join(DETAILED_EXPLANATION_RULES)


def get_content_invocation_summary() -> str:
    """يُرجِع بروتوكول استدعاء المحتوى كنص قصير (للـ prompts / logs)."""
    return " | ".join(CONTENT_INVOCATION_DOCTRINE)


def get_model_answer_explanation_summary() -> str:
    """يُرجِع doctrine شرح الإجابة النموذجية (للـ system prompts)."""
    return " | ".join(MODEL_ANSWER_EXPLANATION_DOCTRINE)


def get_step_by_step_summary() -> str:
    """يُرجِع قواعد الشرح خطوة بخطوة (للـ prompts)."""
    return " | ".join(STEP_BY_STEP_EXPLANATION_RULES)


def get_skill_invocation_protocol_summary() -> str:
    """يُرجِع بروتوكول استدعاء الـ Skills (للـ orchestrator / logs)."""
    return " | ".join(SKILL_INVOCATION_PROTOCOL)


def get_bkt_cognitive_summary() -> str:
    """يُرجِع doctrine الطبقة المعرفية BKT كنص قصير (للـ logs / prompts)."""
    return " | ".join(BKT_COGNITIVE_DOCTRINE)


def get_adaptive_pedagogy_summary() -> str:
    """ملخص doctrine البيداغوجيا التكيفية (D-104) — سطر واحد للاستهلاك البرمجي."""
    return " | ".join(ADAPTIVE_PEDAGOGY_DOCTRINE)


def get_probability_calculation_summary() -> str:
    """يُرجِع doctrine حساب الاحتمالات كنص قصير (للـ logs / prompts)."""
    return " | ".join(PROBABILITY_CALCULATION_DOCTRINE)


def get_answer_redaction_summary() -> str:
    """يُرجِع doctrine حجب الإجابة النهائية كنص قصير (للـ logs)."""
    return " | ".join(ANSWER_REDACTION_DOCTRINE)


def get_worked_example_summary() -> str:
    """يُرجِع doctrine المثال المحلول المُتدرّج كنص قصير (للـ prompts / logs)."""
    return " | ".join(WORKED_EXAMPLE_DOCTRINE)


def build_exercise_explanation_prompt() -> str:
    """يبني system prompt شرح التمرين مباشرةً من الـ doctrine.

    D-071 (2026-05-19): هذه الدالة هي **single source of truth** للـ prompt
    المُرسَل للـ LLM عند شرح تمارين البكالوريا. أي تغيير في الـ doctrine
    ينعكس تلقائياً على الـ prompt — لا drift ممكن.

    القيود الإلزامية (D-067):
    - الـ prompt يجب أن يبقى < 1000 حرف (النماذج المجانية تدخل reasoning-mode
      مع prompts > 1500 حرف).
    - لا box-drawing chars (U+2500–U+257F) — تُربك tokenizers النماذج المجانية.
    - لا تكرار — كل قاعدة تُذكر مرة واحدة فقط.

    المُستهلكون:
    - `app.services.chat.local_graph._EXERCISE_EXPLANATION_SYSTEM_PROMPT`
    - `microservices.conversation_service.src.conversation_graph`
    """
    # الجزء الثابت — هوية الأستاذ السقراطي (D-113)
    header = (
        "أنت أستاذ بكالوريا جزائري تُعلّم بالطريقة السقراطية.\n"
        "مهمتك أن تجعل الطالب يفكّر ويصل للحل بنفسه — لا أن تحلّ مكانه.\n\n"
    )

    # نسخة مُوجَزة من المبادئ السقراطية الخمسة (تبقى مشتقّة من EXPLANATION_DOCTRINE،
    # لكن مكثّفة لتبقى < 1000 حرف مع المراسي — D-067). كل سطر يطابق قاعدة في
    # EXPLANATION_DOCTRINE[:5] (القاعدة الذهبية، المنع المطلق، المحاولة، السُلّم، «لم أفهم»).
    # المراسي الإلزامية للـ CI: «الإجابة النموذجية» + «حرفياً» + «LaTeX».
    core_rules = (
        "1. القاعدة الذهبية: لا تكشف أبداً نتيجةً أو خطوةً يستطيع الطالب توليدها — قُد بالأسئلة."
        "\n2. ممنوع منعاً باتاً كشف الإجابة النموذجية أو أي نتيجة نهائية (P(A)=14/165، "
        "C(11,3)=165، $$\\boxed{...}$$) — لا حرفياً ولا بإعادة صياغة."
        "\n3. محاولة قبل الشرح: لا تشرح مسألةً لم يحاولها الطالب — ادعُه للمحاولة ثم وجِّهه."
        "\n4. سُلّم التلميحات: مبدأ ← سؤال موجِّه ← هدف جزئي ← خطوة تالية فقط. لا تقفز للإجابة."
        "\n5. عند «لم أفهم»: شخّص موضع الكسر بسؤال، ثم تلميح أدنى واحد — لا تُعِد الاشتقاق."
        "\n6. استخدم LaTeX لكل رمز رياضي ($...$) — لكن لا تكتب النتيجة النهائية."
        "\n7. التزم بمعطيات هذا التمرين حصراً (لا موضوع خارجي). لا HTML في نصك."
    )

    prompt = header + "قواعد إلزامية:\n" + core_rules

    # ضمان عدم تجاوز 1000 حرف (D-067 invariant)
    if len(prompt) > 1000:
        prompt = prompt[:997] + "..."

    return prompt


#: الـ prompt المُبنى من الـ doctrine — يُستخدم في local_graph و conversation_graph.
#: D-071: هذا الثابت هو المرجع الوحيد — لا تعريف prompt محلي في أي ملف آخر.
EXERCISE_EXPLANATION_SYSTEM_PROMPT: Final[str] = build_exercise_explanation_prompt()


def get_reasoning_core_summary() -> str:
    """يُرجِع القاعدة الجامعة للنواة المعرفية للتفكير كنص قصير (D-181، للـ prompts)."""
    return " | ".join(REASONING_CORE_DOCTRINE)


def list_all_doctrines() -> dict[str, dict[str, object]]:
    """يُرجِع manifest كامل لكل الـ doctrines + versions + consumers (للـ CI)."""
    return SKILL_DOCTRINE_MANIFEST
