"""
منصّة الـ Skills الموحَّدة — Registry + Composition + Observability.

CLAUDE.md §0.5 (النجمة القطبية): «كل قدرة ذكاء اصطناعي يجب أن تكون Skill — وحدة مستقلة
قابلة للقياس والاختبار والاستبدال». هذه الوحدة تُحقِّق الطبقة الموحِّدة فوق الـ Skills الـ 14:
  • **SkillRegistry** — اكتشاف + بيانات وصفية (للرصد عبر `/api/v1/skills`).
  • **compose_text_refinement** — خط تنقية الإجابة (sanitize → quality → firewall → topic_lock)
    كبدائية قابلة لإعادة الاستخدام، تُرجِع نصاً منقَّحاً مع مقاييس لكل خطوة وتدهور رشيق.

> **مبدأ السلامة (لا يكسر الإقلاع أبداً):** كل شيء هنا إضافي. الـ registry بيانات وصفية نقية؛
> الاستيراد الفعلي للـ Skills كسول (lazy) داخل الدوال. أي خطوة تنقية تفشل → تُتجاهَل ويُحتفَظ
> بالنص كما هو (graceful degradation). الأعلام (flags) تُبقي الـ Skills الجديدة مُعطَّلة افتراضياً.

> **ملاحظة معمارية:** هذه الطبقة لا تُعيد توصيل سلسلة `local_graph._chat_node` الحيّة (تبقى
> مرجعاً) — بل تُوفِّر الصياغة الرسمية القابلة لإعادة الاستخدام + الرصد. التركيب عبر الخدمات
> (planning+research+reasoning) يبقى في `microservices/.../skills_pipeline.py:run_skills_pipeline`.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger("cogniforge.skills.registry")

# ─────────────────────────────────────────────────────────────────────────────
# مقاييس Prometheus (registry مستقل، حارس ضد التسجيل المزدوج — نمط bkt_engine)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter, Gauge

    _existing = {m.name for m in REGISTRY.collect()}
    if "cogniforge_skill_compose_invocations" not in _existing:
        _COMPOSE_INVOCATIONS = Counter(
            "cogniforge_skill_compose_invocations_total",
            "Total compose_text_refinement invocations",
            ["mode", "status"],
        )
        _COMPOSE_STEP = Counter(
            "cogniforge_skill_compose_step_total",
            "Per-step refinement outcomes within a composition",
            ["step", "result"],
        )
        _REGISTRY_GAUGE = Gauge(
            "cogniforge_skill_registry_skills",
            "Number of skills registered in the in-process registry",
            ["status"],
        )
    else:  # pragma: no cover - يحدث فقط عند إعادة الاستيراد في نفس العملية (اختبارات)
        _COMPOSE_INVOCATIONS = next(
            m for m in REGISTRY.collect() if m.name == "cogniforge_skill_compose_invocations"
        )  # type: ignore[assignment]
        _COMPOSE_STEP = None  # type: ignore[assignment]
        _REGISTRY_GAUGE = None  # type: ignore[assignment]

    def _record_compose(mode: str, status: str) -> None:
        with contextlib.suppress(Exception):  # pragma: no cover
            _COMPOSE_INVOCATIONS.labels(mode=mode, status=status).inc()

    def _record_step(step: str, result: str) -> None:
        try:
            if _COMPOSE_STEP is not None:
                _COMPOSE_STEP.labels(step=step, result=result).inc()
        except Exception:  # pragma: no cover
            pass

    def _set_registry_gauge(status: str, value: int) -> None:
        try:
            if _REGISTRY_GAUGE is not None:
                _REGISTRY_GAUGE.labels(status=status).set(value)
        except Exception:  # pragma: no cover
            pass

except Exception:  # pragma: no cover - prometheus غير متوفر (sandbox)

    def _record_compose(mode: str, status: str) -> None:
        pass

    def _record_step(step: str, result: str) -> None:
        pass

    def _set_registry_gauge(status: str, value: int) -> None:
        pass


SkillStatus = Literal["ACTIVE", "FLAGGED", "PARTIAL"]


@dataclass(frozen=True)
class SkillDescriptor:
    """بيانات وصفية لـ Skill واحد في السجل (للرصد + الاكتشاف)."""

    name: str
    summary: str
    input_contract: str
    output_contract: str
    primary_method: str
    metrics_prefix: str
    consumed_by: tuple[str, ...]
    status: SkillStatus = "ACTIVE"
    feature_flag: str | None = None
    #: مُحمِّل كسول للـ singleton (لا يُستورَد إلا عند الطلب — يتجنّب pydantic عند الرصد)
    accessor: Callable[[], object] | None = field(default=None, compare=False, repr=False)

    def is_enabled(self) -> bool:
        """ACTIVE دائماً مُفعَّل؛ FLAGGED مُفعَّل فقط عند رفع العلم في البيئة/الإعدادات."""
        if self.status != "FLAGGED" or not self.feature_flag:
            return True
        return _flag_is_on(self.feature_flag)

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "summary": self.summary,
            "input_contract": self.input_contract,
            "output_contract": self.output_contract,
            "primary_method": self.primary_method,
            "metrics_prefix": self.metrics_prefix,
            "consumed_by": list(self.consumed_by),
            "status": self.status,
            "feature_flag": self.feature_flag,
            "enabled": self.is_enabled(),
        }


def _flag_is_on(flag: str) -> bool:
    """يقرأ علم ميزة: env var (override، 12-factor) أولاً ثم الإعدادات. الافتراضي False."""
    import os

    raw = os.getenv(flag)
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    try:
        from app.core.config import get_settings

        value = getattr(get_settings(), flag, None)
        if isinstance(value, bool):
            return value
    except Exception:
        pass
    return False


class SkillRegistry:
    """سجل في-العملية لكل الـ Skills — اكتشاف + بيانات وصفية موحَّدة."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}

    def register(self, descriptor: SkillDescriptor) -> None:
        if descriptor.name in self._skills:
            raise ValueError(f"Skill already registered: {descriptor.name}")
        self._skills[descriptor.name] = descriptor
        self._refresh_gauge()

    def get(self, name: str) -> SkillDescriptor | None:
        return self._skills.get(name)

    def names(self) -> list[str]:
        return sorted(self._skills)

    def list(self) -> list[SkillDescriptor]:
        return [self._skills[n] for n in self.names()]

    def by_status(self, status: SkillStatus) -> list[SkillDescriptor]:
        return [d for d in self.list() if d.status == status]

    def _refresh_gauge(self) -> None:
        for status in ("ACTIVE", "FLAGGED", "PARTIAL"):
            _set_registry_gauge(status, sum(1 for d in self._skills.values() if d.status == status))


# ─────────────────────────────────────────────────────────────────────────────
# خط تنقية الإجابة (Composition) — صياغة رسمية لسلسلة ما-بعد-المعالجة
# ─────────────────────────────────────────────────────────────────────────────
#: refiner = دالة تأخذ (نص، سياق) وتُرجِع (نص منقَّح، هل طُبِّق). يجب ألا ترفع استثناءً
#: مُهلِكاً — أي فشل يُعالَج هنا (graceful degradation).
TextRefiner = Callable[[str, dict[str, object]], "RefinerResult"]


@dataclass(frozen=True)
class RefinerResult:
    text: str
    applied: bool = False


@dataclass(frozen=True)
class RefinementResult:
    text: str
    applied_steps: tuple[str, ...]
    failed_steps: tuple[str, ...]


def _refiner_exercise_alignment(text: str, ctx: dict[str, object]) -> RefinerResult:
    from app.services.skills.exercise_alignment_skill import (
        ExerciseAlignmentInput,
        get_exercise_alignment_skill,
    )

    out = get_exercise_alignment_skill().align(
        ExerciseAlignmentInput(
            question=str(ctx.get("question", ""))[:6000] or " ",
            answer=text,
            intent=str(ctx.get("intent", "educational")),  # type: ignore[arg-type]
        )
    )
    return RefinerResult(out.aligned_answer, out.applied)


def _refiner_answer_quality(text: str, ctx: dict[str, object]) -> RefinerResult:
    from app.services.skills.answer_quality_skill import (
        AnswerQualityInput,
        AnswerQualityOutput,
        get_answer_quality_skill,
    )

    intent = str(ctx.get("intent", "educational"))
    skill_intent = "chat" if intent == "chat" else "educational"
    result = get_answer_quality_skill().evaluate(
        AnswerQualityInput(
            question=str(ctx.get("question", ""))[:2000] or " ",
            answer=text,
            intent=skill_intent,  # type: ignore[arg-type]
            require_latex=skill_intent == "educational",
            require_steps=skill_intent == "educational" and len(text) > 300,
        )
    )
    if (
        isinstance(result, AnswerQualityOutput)
        and result.improved_answer
        and result.improved_answer != text
    ):
        return RefinerResult(result.improved_answer, True)
    return RefinerResult(text, False)


def _refiner_output_firewall(text: str, ctx: dict[str, object]) -> RefinerResult:
    from app.services.skills.output_firewall import apply_channel_b_firewall

    cleaned, rejected = apply_channel_b_firewall(text, intent=str(ctx.get("intent", "educational")))
    return RefinerResult(cleaned, rejected or cleaned != text)


def _refiner_topic_lock(text: str, ctx: dict[str, object]) -> RefinerResult:
    # تحذيري فقط — لا يُغيِّر النص (D-086)
    from app.services.skills.topic_lock import TopicLockInput, get_topic_lock

    get_topic_lock().check(
        TopicLockInput(
            question=str(ctx.get("question", "")),
            answer=text,
            history=list(ctx.get("history", []) or []),  # type: ignore[arg-type]
        )
    )
    return RefinerResult(text, False)


#: ترتيب خط التنقية القانوني (مرآة local_graph._chat_node lines 800-811، دون foreign-script
#: cleanup المحلي الخاص بـ local_graph). يُستخدم في compose_text_refinement الافتراضي.
DEFAULT_REFINEMENT_STEPS: tuple[tuple[str, TextRefiner], ...] = (
    ("exercise_alignment", _refiner_exercise_alignment),
    ("answer_quality", _refiner_answer_quality),
    ("output_firewall", _refiner_output_firewall),
    ("topic_lock", _refiner_topic_lock),
)


def compose_text_refinement(
    text: str,
    context: dict[str, object] | None = None,
    *,
    steps: Iterable[tuple[str, TextRefiner]] | None = None,
    mode: str = "sequential",
) -> RefinementResult:
    """يُطبِّق خط تنقية الإجابة (Skills متسلسلة) ويُرجِع نصاً منقَّحاً.

    كل خطوة معزولة بـ try/except → فشلها يُتجاهَل ويُحتفَظ بالنص (graceful degradation).
    يُسجِّل مقاييس لكل خطوة + استدعاء التركيب. لا يكسر المسار أبداً.
    """
    ctx = context or {}
    current = text if isinstance(text, str) else str(text or "")
    applied: list[str] = []
    failed: list[str] = []
    pipeline = tuple(steps) if steps is not None else DEFAULT_REFINEMENT_STEPS

    for name, refiner in pipeline:
        try:
            result = refiner(current, ctx)
            if not isinstance(result, RefinerResult):
                raise TypeError(f"refiner {name} returned {type(result)!r}")
            current = result.text if isinstance(result.text, str) and result.text else current
            if result.applied:
                applied.append(name)
                _record_step(name, "applied")
            else:
                _record_step(name, "noop")
        except Exception as exc:  # graceful degradation — لا يكسر المسار
            failed.append(name)
            _record_step(name, "error")
            logger.debug("compose refiner %s non-fatal failure: %s", name, exc)

    _record_compose(mode, "ok" if not failed else "partial")
    return RefinementResult(text=current, applied_steps=tuple(applied), failed_steps=tuple(failed))


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap — تسجيل كل الـ Skills (12 ACTIVE + 2 FLAGGED)
# ─────────────────────────────────────────────────────────────────────────────
def _build_registry() -> SkillRegistry:
    reg = SkillRegistry()
    descriptors = [
        SkillDescriptor(
            name="greeting",
            summary="ردود التحيات الحتمية (D-067 — يحل ISS-079).",
            input_contract="GreetingSkillInput",
            output_contract="GreetingSkillOutput",
            primary_method="respond",
            metrics_prefix="cogniforge_skill_greeting",
            consumed_by=(
                "local_graph._greeting_fastpath_response",
                "orchestrator_client.chat_with_agent",
            ),
        ),
        SkillDescriptor(
            name="bac_exercise",
            summary="استرجاع وشرح تمارين بكالوريا الجزائر.",
            input_contract="BACSkillInput",
            output_contract="BACSkillRetrievalOutput|BACSkillExplanationOutput",
            primary_method="invoke",
            metrics_prefix="cogniforge_skill_bac",
            consumed_by=("orchestrator_client._stream_local_retrieval_response",),
        ),
        SkillDescriptor(
            name="math",
            summary="حل وشرح أسئلة الرياضيات عبر Math Pipeline (D-061).",
            input_contract="MathSkillInput",
            output_contract="MathSkillOutput",
            primary_method="solve",
            metrics_prefix="cogniforge_skill_math",
            consumed_by=("conversation_service.math_pipeline.invoke_math_pipeline",),
        ),
        SkillDescriptor(
            name="answer_quality",
            summary="تقييم جودة الإجابة وتحسينها (D-072/D-073).",
            input_contract="AnswerQualityInput",
            output_contract="AnswerQualityOutput",
            primary_method="evaluate",
            metrics_prefix="cogniforge_skill_answer_quality",
            consumed_by=(
                "local_graph._apply_answer_quality_skill",
                "registry.compose_text_refinement",
            ),
        ),
        SkillDescriptor(
            name="answer_redaction",
            summary="الحارس الحتمي الأخير ضد كشف الإجابة النهائية — توليد مُجبَر سقراطي (D-113).",
            input_contract="AnswerRedactionInput",
            output_contract="AnswerRedactionOutput",
            primary_method="redact",
            metrics_prefix="cogniforge_skill_answer_redaction",
            consumed_by=(
                "content_integrity.sanitize_final_text",
                "local_graph._apply_answer_redaction",
            ),
        ),
        SkillDescriptor(
            name="bkt_engine",
            summary="الطبقة المعرفية الأساسية Bayesian Knowledge Tracing (D-074).",
            input_contract="BKTEvaluationInput",
            output_contract="BKTEvaluation",
            primary_method="evaluate",
            metrics_prefix="cogniforge_skill_bkt",
            consumed_by=("customer_chat._evaluate_bkt_cards",),
        ),
        SkillDescriptor(
            name="concept_diagnosis",
            summary="الطبقتان 1+5 العصبي-الرمزي — تشخيص المفهوم + المفهوم الخاطئ (D-127).",
            input_contract="ConceptDiagnosisInput",
            output_contract="ConceptDiagnosisOutput",
            primary_method="diagnose",
            metrics_prefix="cogniforge_skill_concept_diagnosis",
            consumed_by=("orchestrator_client.chat_with_agent",),
        ),
        SkillDescriptor(
            name="pedagogical_policy",
            summary="الطبقة 4 — محرّك السياسة التربوية: تعريف→سؤال محدود→اعتراف→حلّ رمزي (D-129/D-130).",
            input_contract="PolicyInput",
            output_contract="PolicyOutput",
            primary_method="decide",
            metrics_prefix="cogniforge_skill_pedagogical_policy",
            consumed_by=("orchestrator_client.chat_with_agent",),
        ),
        SkillDescriptor(
            name="student_state",
            summary="قراءة حالة الطالب كإشارة قرار — النيّة (متعدّد-إشارات) + الإحباط اللحظي (D-133).",
            input_contract="StudentStateInput",
            output_contract="StudentState",
            primary_method="read",
            metrics_prefix="cogniforge_skill_student_state",
            consumed_by=("orchestrator_client.chat_with_agent",),
        ),
        SkillDescriptor(
            name="understanding_state",
            summary="محرّك حالة الفهم (Learning State) — ماذا فهم الطالب فعلاً؟ KC-aware + تمثيل استباقي (D-135).",
            input_contract="combo + history",
            output_contract="UnderstandingDecision",
            primary_method="decide",
            metrics_prefix="cogniforge_skill_understanding_state",
            consumed_by=("orchestrator_client.chat_with_agent",),
        ),
        SkillDescriptor(
            name="semantic_property",
            summary="الطبقة 2 — الطبقة الدلالية + Misconception Graph (شخّص ثم تدخّل، D-131).",
            input_contract="SemanticPropertyInput",
            output_contract="SemanticPropertyOutput",
            primary_method="interpret",
            metrics_prefix="cogniforge_skill_semantic_property",
            consumed_by=("orchestrator_client._build_cognitive_response",),
        ),
        SkillDescriptor(
            name="socratic_evaluator",
            summary="الطبقة 1 — مُقيّم الإجابات السقراطي (الإصغاء النشط): يُقيّم رد الطالب الحرّ (D-130).",
            input_contract="SocraticEvaluatorInput",
            output_contract="SocraticEvaluatorOutput",
            primary_method="evaluate",
            metrics_prefix="cogniforge_skill_socratic_evaluator",
            consumed_by=("orchestrator_client._stream_socratic_evaluation",),
        ),
        SkillDescriptor(
            name="adaptive_pedagogy",
            summary="طبقة البيداغوجيا التكيفية — قراءة إتقان BKT تقود عمق التدريس (D-104).",
            input_contract="PedagogyInput",
            output_contract="PedagogyDirective",
            primary_method="derive",
            metrics_prefix="cogniforge_skill_pedagogy",
            consumed_by=("customer_chat._build_pedagogy_directive",),
        ),
        SkillDescriptor(
            name="probability",
            summary="محرّك الاحتمالات الحتمي + الموجِّه التربوي (D-075/D-078).",
            input_contract="ProbabilityInput",
            output_contract="ProbabilityModelOutput|FullExerciseStoryOutput",
            primary_method="analyze",
            metrics_prefix="cogniforge_skill_probability",
            consumed_by=("orchestrator_client._build_calculated_ui",),
        ),
        SkillDescriptor(
            name="exercise_alignment",
            summary="محاذاة الإجابة مع معطيات تمرين الاحتمالات (D-090/D-092).",
            input_contract="ExerciseAlignmentInput",
            output_contract="ExerciseAlignmentOutput",
            primary_method="align",
            metrics_prefix="cogniforge_skill_alignment",
            consumed_by=(
                "local_graph._strip_unrequested_color_lines",
                "registry.compose_text_refinement",
            ),
        ),
        SkillDescriptor(
            name="output_firewall",
            summary="جدار الحماية المزدوج للقنوات — يرفض/ينظف HTML/JSX (D-086).",
            input_contract="FirewallInput",
            output_contract="FirewallOutput",
            primary_method="apply",
            metrics_prefix="cogniforge_output_firewall",
            consumed_by=("local_graph._apply_output_firewall", "registry.compose_text_refinement"),
        ),
        SkillDescriptor(
            name="topic_lock",
            summary="قفل الموضوع وحماية نقاء السياق — تحذيري (D-086).",
            input_contract="TopicLockInput",
            output_contract="TopicLockOutput",
            primary_method="check",
            metrics_prefix="cogniforge_topic_lock",
            consumed_by=("local_graph._check_topic_lock", "registry.compose_text_refinement"),
        ),
        SkillDescriptor(
            name="arabic_stream_guard",
            summary="حارس البثّ العربي — يكشف/يعيد توليد المخرَج غير العربي (D-LANG-GUARD-001).",
            input_contract="str-stream",
            output_contract="str-stream",
            primary_method="guard_arabic_stream",
            metrics_prefix="cogniforge_skill_lang_guard",
            consumed_by=("local_graph.run_local_graph_stream",),
        ),
        SkillDescriptor(
            name="ws_heartbeat",
            summary="معالج ping/pong موحَّد عبر كل WS endpoints (D-WS-FLAP-002).",
            input_contract="dict-control-message",
            output_contract="bool",
            primary_method="handle_control_message",
            metrics_prefix="cogniforge_skill_ws_heartbeat",
            consumed_by=("customer_chat.chat_stream_ws", "admin.admin_chat_stream_ws"),
        ),
        SkillDescriptor(
            name="text_refinement_compose",
            summary="خط تنقية الإجابة المُركَّب (sanitize→quality→firewall→topic_lock).",
            input_contract="str+context",
            output_contract="RefinementResult",
            primary_method="compose_text_refinement",
            metrics_prefix="cogniforge_skill_compose",
            consumed_by=("api.routers.skills.refine_endpoint",),
        ),
        SkillDescriptor(
            name="content_integrity",
            summary="حارس نزاهة المحتوى — يلتقط الغارباج اللاتيني وتسريب HTML على كامل البثّ (D-106).",
            input_contract="ContentIntegrityInput",
            output_contract="ContentIntegrityOutput",
            primary_method="check",
            metrics_prefix="cogniforge_skill_content_integrity",
            consumed_by=(
                "orchestrator_client.chat_with_agent",
                "local_graph.run_local_graph_stream",
            ),
        ),
        SkillDescriptor(
            name="learning_path",
            summary="المسار التعلّمي التكيفي — يقترح المفهوم التالي وصعوبة متكيفة فوق BKT (D-111).",
            input_contract="LearningPathInput",
            output_contract="LearningPathOutput",
            primary_method="derive",
            metrics_prefix="cogniforge_skill_learning_path",
            consumed_by=("customer_chat._evaluate_bkt_cards",),
        ),
        # ── FLAGGED (مُعطَّلة افتراضياً — تفعيل اختياري عبر علم) ──
        SkillDescriptor(
            name="retrieval_rerank",
            summary="استرجاع دلالي (LlamaIndex) + إعادة ترتيب (Reranker/CrossEncoder).",
            input_contract="RetrievalRerankInput",
            output_contract="RetrievalRerankOutput",
            primary_method="retrieve",
            metrics_prefix="cogniforge_skill_retrieval",
            consumed_by=("api.routers.skills.retrieve_endpoint",),
            status="FLAGGED",
            feature_flag="ENABLE_RETRIEVAL_RERANK_SKILL",
        ),
        SkillDescriptor(
            name="mcp_tool",
            summary="جسر أدوات MCP (8 أدوات) — list + call عبر MCPServer.",
            input_contract="MCPToolInput",
            output_contract="MCPToolOutput",
            primary_method="call",
            metrics_prefix="cogniforge_skill_mcp",
            consumed_by=("api.routers.skills.mcp_endpoint",),
            status="FLAGGED",
            feature_flag="ENABLE_MCP_TOOL_SKILL",
        ),
    ]
    for d in descriptors:
        reg.register(d)
    return reg


_REGISTRY_SINGLETON: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """يُعيد Singleton لسجل الـ Skills (يُبنى مرة واحدة)."""
    global _REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is None:
        _REGISTRY_SINGLETON = _build_registry()
    return _REGISTRY_SINGLETON
