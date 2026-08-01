"""
منصّة الـ Skills الموحَّدة — Registry + Composition + Observability.

CLAUDE.md §0.5 (النجمة القطبية): «كل قدرة ذكاء اصطناعي يجب أن تكون Skill — وحدة مستقلة
قابلة للقياس والاختبار والاستبدال». هذه الوحدة تُحقِّق الطبقة الموحِّدة فوق كل الـ Skills
المسجَّلة (العدد الحقيقي = عدد الـ descriptors في `_build_registry` أدناه — لا رقم مُصلَّب هنا):
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
# النواة المعرفية للتفكير — Composition (D-181)
# ─────────────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ReasoningComposition:
    """أثر تفكير مُركَّب — مسار تفكيك دائم + نتائج مهارات التفكير المُفعَّلة."""

    question: str
    modes: tuple[str, ...]
    results: dict[str, dict[str, object]]
    narrative: str


def compose_reasoning(
    question: str, context: dict[str, object] | None = None
) -> ReasoningComposition:
    """يُركِّب النواة المعرفية للتفكير على سؤال حرّ (D-181) — الموحِّد الثوري.

    حتمي 100% ولا يكسر المسار أبداً (كل مهارة معزولة بـ try/except، تدهور رشيق):
      • **دائماً** يُفكّك السؤال بسقالة بوليا (ProblemDecomposition) — مسار تفكير لأي سؤال
        مهما كان، فيخدم «يجيب على كل سؤال» ببنية بدل نصّ فارغ.
      • **دائماً** يفحص التفكير النقدي (CriticalThinking) على نصّ السؤال (كشف مغالطات + أسئلة).
      • يُفعِّل المهارة المتخصّصة عند توفّر مدخلها المُهيكَل في `context`:
        premises+conclusion → LogicReasoning | edges → CausalReasoning |
        instances/sequence/source+target → Abstraction | relations/dynamics → MentalModel.

    يُرجِع `ReasoningComposition` (أثر مُهيكَل + سرد حتمي مختصر) مع مقاييس لكل استدعاء.
    """
    ctx = context or {}
    q = (question or "").strip()
    results: dict[str, dict[str, object]] = {}
    modes: list[str] = []

    def _run(mode: str, fn: Callable[[], dict[str, object]]) -> None:
        try:
            results[mode] = fn()
            modes.append(mode)
            _record_step(f"reasoning_{mode}", "applied")
        except Exception as exc:  # graceful degradation — لا يكسر المسار
            _record_step(f"reasoning_{mode}", "error")
            logger.debug("compose_reasoning %s non-fatal failure: %s", mode, exc)

    # 1) تفكيك دائم — مسار تفكير لأي سؤال.
    def _decompose() -> dict[str, object]:
        from app.services.skills.problem_decomposition_skill import (
            ProblemDecompositionInput,
            get_problem_decomposition_skill,
        )

        out = get_problem_decomposition_skill().decompose(
            ProblemDecompositionInput(problem=q or "سؤال")
        )
        return out.model_dump()

    _run("decomposition", _decompose)

    # 2) تفكير نقدي دائم على نصّ السؤال.
    def _critical() -> dict[str, object]:
        from app.services.skills.critical_thinking_skill import (
            CriticalThinkingInput,
            get_critical_thinking_skill,
        )

        out = get_critical_thinking_skill().analyze(CriticalThinkingInput(text=q))
        return out.model_dump()

    _run("critical_thinking", _critical)

    # 3) المنطق — عند توفّر مقدّمات + نتيجة.
    if ctx.get("premises") and ctx.get("conclusion"):

        def _logic() -> dict[str, object]:
            from app.services.skills.logic_reasoning_skill import (
                LogicReasoningInput,
                get_logic_reasoning_skill,
            )

            out = get_logic_reasoning_skill().analyze(
                LogicReasoningInput(
                    premises=list(ctx.get("premises", [])),  # type: ignore[arg-type]
                    conclusion=str(ctx.get("conclusion", "")),
                )
            )
            return out.model_dump()

        _run("logic", _logic)

    # 4) السببية — عند توفّر أضلاع.
    if ctx.get("edges"):

        def _causal() -> dict[str, object]:
            from app.services.skills.causal_reasoning_skill import (
                CausalReasoningInput,
                get_causal_reasoning_skill,
            )

            out = get_causal_reasoning_skill().analyze(
                CausalReasoningInput(
                    edges=list(ctx.get("edges", [])),  # type: ignore[arg-type]
                    classify_pair=ctx.get("classify_pair"),  # type: ignore[arg-type]
                    counterfactual_node=ctx.get("counterfactual_node"),  # type: ignore[arg-type]
                )
            )
            return out.model_dump()

        _run("causal", _causal)

    # 5) التجريد — عند توفّر أمثلة/متتالية/زوج تماثل.
    if ctx.get("instances") or ctx.get("sequence") or (ctx.get("source") and ctx.get("target")):

        def _abstraction() -> dict[str, object]:
            from app.services.skills.abstraction_skill import (
                AbstractionInput,
                get_abstraction_skill,
            )

            out = get_abstraction_skill().generalize(
                AbstractionInput(
                    instances=list(ctx.get("instances", [])),  # type: ignore[arg-type]
                    sequence=list(ctx.get("sequence", [])),  # type: ignore[arg-type]
                    source=ctx.get("source"),  # type: ignore[arg-type]
                    target=ctx.get("target"),  # type: ignore[arg-type]
                )
            )
            return out.model_dump()

        _run("abstraction", _abstraction)

    # 6) النموذج الذهني — عند توفّر علاقات/ديناميات.
    if ctx.get("relations") or ctx.get("dynamics"):

        def _mental() -> dict[str, object]:
            from app.services.skills.mental_model_skill import (
                MentalModelInput,
                get_mental_model_skill,
            )

            out = get_mental_model_skill().build(
                MentalModelInput(
                    name=str(ctx.get("model_name", q or "نموذج")),
                    relations=list(ctx.get("relations", [])),  # type: ignore[arg-type]
                    dynamics=list(ctx.get("dynamics", [])),  # type: ignore[arg-type]
                )
            )
            return out.model_dump()

        _run("mental_model", _mental)

    # 7) الأسس الحاسوبية — عند توفّر طلب حساب حتمي مُهيكَل (D-183).
    #    context["compute"] = {"domain": ..., "operation": ..., "args": {...}}
    compute_req = ctx.get("compute")
    if isinstance(compute_req, dict) and compute_req.get("domain"):

        def _foundations() -> dict[str, object]:
            from app.services.skills.foundations_compute_skill import (
                FoundationsComputeInput,
                get_foundations_compute_skill,
            )

            out = get_foundations_compute_skill().compute(
                FoundationsComputeInput(
                    domain=str(compute_req.get("domain", "")),
                    operation=str(compute_req.get("operation", "")),
                    args=dict(compute_req.get("args", {})),  # type: ignore[arg-type]
                )
            )
            return out.model_dump()

        _run("foundations_compute", _foundations)

    # 8) الرموز الرياضية — «ما معنى C؟» جزء من التفكير لا استثناء منه (D-185).
    #    حتمي بالكامل، ويُضاف للمسار فقط حين يكون السؤال فعلاً عن رمز.
    def _notation() -> dict[str, object] | None:
        from app.services.skills.notation_skill import get_notation_skill

        entry = get_notation_skill().resolve(q)
        if entry is None:
            return None
        return {
            "symbol": entry.symbol,
            "title": entry.title,
            "definition": entry.definition,
            "example": entry.example,
            "concept_id": entry.concept_id,
        }

    if _notation() is not None:
        _run("notation", _notation)

    _record_compose("reasoning", "ok" if modes else "empty")
    narrative = "مسار تفكير مُهيكَل عبر: " + ("، ".join(modes) if modes else "لا مهارة")
    return ReasoningComposition(
        question=q, modes=tuple(modes), results=results, narrative=narrative
    )


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap — تسجيل كل الـ Skills (المصدر الوحيد للعدد/الحالة = قائمة descriptors أدناه)
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
            name="pedagogical_escalation",
            summary="المصفوفة التصعيدية التكيّفية — Understanding-Signal + Misconception-Check + ability (D-138).",
            input_contract="EscalationInput",
            output_contract="EscalationDecision",
            primary_method="decide",
            metrics_prefix="cogniforge_tutor_escalation",
            consumed_by=("orchestrator_client.chat_with_agent",),
        ),
        SkillDescriptor(
            name="micro_simulation",
            summary="خادم المحاكيات المصغّرة الحتمي (L3) — مثال عددي isomorphic ≤320 حرف صفر-LLM (D-138).",
            input_contract="concept_id",
            output_contract="str | None",
            primary_method="get_micro_simulation",
            metrics_prefix="cogniforge_tutor_micro_simulation",
            consumed_by=(
                "pedagogical_escalation_skill.decide",
                "orchestrator_client.chat_with_agent",
            ),
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
        # ── D-191: «أيّ تمرين نُدرّس الآن؟» بمصدرٍ واحد (ISS-140 د/د-2) ──────────
        SkillDescriptor(
            name="exercise_context",
            summary=(
                "يحسم التمرين قيد النقاش — نصّ الطالب أوّلاً، ثمّ تاريخه، ثمّ "
                "التمرين المرجعي بتصريح منطوق (D-191)."
            ),
            input_contract="str + history",
            output_contract="ResolvedExercise",
            primary_method="resolve",
            metrics_prefix="cogniforge_exercise_context",
            consumed_by=(
                "probability_brain.cognitive_verification._load_canonical_combinations",
                "probability_brain.escape_hatch._build_probability_direct_explanation",
                "orchestrator_client._build_calculated_ui",
            ),
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
        SkillDescriptor(
            name="review_scheduler",
            summary=(
                "التكرار المتباعد (FSRS) فوق BKT — يحوّل إشارات الإتقان الدائم ومستوى "
                "الدعم إلى موعد المراجعة التالي. إجابةٌ مدعومة لا تُكافَأ بفاصلٍ طويل (D-194)."
            ),
            input_contract="ReviewSchedulerInput",
            output_contract="ReviewDecision",
            primary_method="decide",
            metrics_prefix="cogniforge_skill_review_scheduler",
            consumed_by=(
                "customer_chat._evaluate_bkt_cards",
                "api.routers.review.due_reviews",
            ),
        ),
        # ── FLAGGED (مُعطَّلة افتراضياً — تفعيل اختياري عبر علم) ──
        SkillDescriptor(
            name="dialogue_manager",
            summary="سلطة قرار الدور التعليمي الموحَّدة: evidence×ability×difficulty (D-142 Phase 2).",
            input_contract="DialogueInput",
            output_contract="DialogueDecision",
            primary_method="decide",
            metrics_prefix="cogniforge_skill_dialogue_manager",
            consumed_by=("orchestrator_client._stream_socratic_evaluation",),
            status="ACTIVE",
            feature_flag="SEMANTIC_TUTOR_ENABLED",
        ),
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
        # ── D-181: النواة المعرفية للتفكير (Cognitive Reasoning Core) ──────────
        SkillDescriptor(
            name="logic_reasoning",
            summary="المنطق والاستدلال — صحّة الحجّة + كشف المغالطة الشكلية + مثال مضادّ (D-181).",
            input_contract="LogicReasoningInput",
            output_contract="LogicReasoningOutput",
            primary_method="analyze",
            metrics_prefix="cogniforge_skill_logic_reasoning",
            consumed_by=("registry.compose_reasoning", "api.routers.skills.reason_endpoint"),
        ),
        SkillDescriptor(
            name="critical_thinking",
            summary="التفكير النقدي — تفكيك الحجّة + كشف المغالطات غير الشكلية + أسئلة سقراطية (D-181).",
            input_contract="CriticalThinkingInput",
            output_contract="CriticalThinkingOutput",
            primary_method="analyze",
            metrics_prefix="cogniforge_skill_critical_thinking",
            consumed_by=("registry.compose_reasoning", "api.routers.skills.reason_endpoint"),
        ),
        SkillDescriptor(
            name="problem_decomposition",
            summary="حل المشكلات — تفكيك بوليا + ترتيب تنفيذ حتمي على التبعيّات (D-181).",
            input_contract="ProblemDecompositionInput",
            output_contract="ProblemDecompositionOutput",
            primary_method="decompose",
            metrics_prefix="cogniforge_skill_problem_decomposition",
            consumed_by=("registry.compose_reasoning", "api.routers.skills.reason_endpoint"),
        ),
        SkillDescriptor(
            name="causal_reasoning",
            summary="الاستدلال السببي — سببية مقابل ارتباط + مضادّ للواقع + كشف الدورة (D-181).",
            input_contract="CausalReasoningInput",
            output_contract="CausalReasoningOutput",
            primary_method="analyze",
            metrics_prefix="cogniforge_skill_causal_reasoning",
            consumed_by=("registry.compose_reasoning", "api.routers.skills.reason_endpoint"),
        ),
        SkillDescriptor(
            name="abstraction",
            summary="التجريد والتماثل — استخراج النمط + قاعدة المتتالية + مطابقة بنيوية (D-181).",
            input_contract="AbstractionInput",
            output_contract="AbstractionOutput",
            primary_method="generalize",
            metrics_prefix="cogniforge_skill_abstraction",
            consumed_by=("registry.compose_reasoning", "api.routers.skills.reason_endpoint"),
        ),
        SkillDescriptor(
            name="mental_model",
            summary="بناء النماذج الذهنية — كيانات/علاقات/ديناميات + فحص التماسك (D-181).",
            input_contract="MentalModelInput",
            output_contract="MentalModelOutput",
            primary_method="build",
            metrics_prefix="cogniforge_skill_mental_model",
            consumed_by=("registry.compose_reasoning", "api.routers.skills.reason_endpoint"),
        ),
        SkillDescriptor(
            name="reasoning_compose",
            summary="النواة المعرفية للتفكير المُركَّبة — مسار تفكير مُهيكَل لأي سؤال (D-181).",
            input_contract="question+context",
            output_contract="ReasoningComposition",
            primary_method="compose_reasoning",
            metrics_prefix="cogniforge_skill_compose",
            consumed_by=("api.routers.skills.reason_endpoint",),
        ),
        # ── D-183: النواة الحاسوبية للأسس (First-Roots Compute) ────────────────
        SkillDescriptor(
            name="foundations_compute",
            summary="النواة الحاسوبية للأسس — جبر خطّي/تفاضل/إحصاء/تحسين/رسوم/لغات صورية/تعقيد حتمي (D-183).",
            input_contract="FoundationsComputeInput",
            output_contract="FoundationsComputeOutput",
            primary_method="compute",
            metrics_prefix="cogniforge_skill_foundations_compute",
            consumed_by=("api.routers.skills.compute_endpoint", "registry.compose_reasoning"),
        ),
        # ── D-185: طبقة الرموز — «النظام يعرّف كل رمز يطبعه» (ISS-138) ──────────
        SkillDescriptor(
            name="notation",
            summary="تعريف الرموز الرياضية (C, n!, P_A(B), E(X), Ω…) — حتمي، بعقد، بتدهور رشيق (D-185).",
            input_contract="str",
            output_contract="NotationEntry",
            primary_method="resolve",
            metrics_prefix="cogniforge_skill_notation",
            consumed_by=(
                "semantic_property_skill.interpret",
                "probability_brain.cognitive_response",
                "api.routers.skills.notation_endpoint",
                "registry.compose_reasoning",
            ),
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
