"""
النواة التعليمية التكيّفية — المحرّك الرئيسي (AEK Runtime).

Protocol V44.0: نظام تشغيل معرفي حتمي.

## المسؤولية الواحدة
تحويل سؤال الطالب + تاريخ المحادثة إلى:
  1. ``AEKRuntimeState`` مُحدَّث (الحالة المعرفية الجديدة)
  2. ``AEKOutput`` (نية تربوية + بيانات القناتين A و B)

## قانون القناتين (§IX)
    CHANNEL_A: حمولة JSON آلية (نية، حالة، بيانات بصرية)
    CHANNEL_B: سرد سقراطي دافئ (Markdown فقط)
    القناتان لا تتلوّثان أبداً.

## قانون العزل الموضوعي (§V)
    عند topic_lock=True: لا مفاهيم خارج current_exercise_scope.

## قانون الحالة المستحيلة المحلية (§VI)
    الحالة المستحيلة تُعزَل جراحياً — لا تُدمِّر الحالة الأم.

## قانون التكيّف (§VIII)
    cognitive_load_index يرتفع → تجريد أقل، بصري أكثر، وتيرة أبطأ.
"""

from __future__ import annotations

import logging
import re
import time

from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.services.aek.fsm import CognitiveState, transition
from app.services.aek.intents import DEFAULT_INTENT_FOR_STATE, CognitiveIntent
from app.services.aek.state import AEKRuntimeState, ExerciseScope, LearnerCapability

logger = logging.getLogger("cogniforge.aek.kernel")

# ─── أنماط كشف الحيرة (Protocol V44.0 §VII) ──────────────────────────────────
_CONFUSION_PATTERNS: tuple[str, ...] = (
    r"(لم\s+أفهم|ما\s+فهمت|مفهمتش|مفهمش)",
    r"(كيفاش|كيف\s+هذا|كيف\s+ذلك|كيف\s+يعني)",
    r"(اشرح\s+لي|وضّح\s+لي|وضح\s+لي|شرح\s+أكثر)",
    r"(مش\s+فاهم|مش\s+واضح|غير\s+واضح|مبيّنش)",
    r"(confused|don't\s+understand|not\s+clear|explain\s+again)",
    r"(je\s+comprends\s+pas|c'est\s+pas\s+clair|expliqu[ée])",
    r"(لماذا|pourquoi|why\s+is|why\s+does)",
    r"(ما\s+معنى|ما\s+المقصود|qu'est.ce\s+que)",
)

# ─── أنماط كشف نطاق الاحتمالات ────────────────────────────────────────────────
_PROBABILITY_SCOPE_PATTERNS: tuple[str, ...] = (
    r"(احتمال|احتمالات|probability|probabilité)",
    r"(كيس|صندوق|urne|sac|urn)",
    r"(كرات|بطاقات|أوراق|boules|cartes)",
    r"(سحب|اختيار|tirage|draw|pick)",
    r"(C\s*\d|\bC_\d|\bC\^\d|تركيبة|combinaison)",
    r"(متغير\s+عشوائي|variable\s+aléatoire|random\s+variable)",
    r"(فضاء\s+عيّنة|espace\s+échantillon|sample\s+space)",
)

_COMPILED_CONFUSION = [re.compile(p, re.IGNORECASE) for p in _CONFUSION_PATTERNS]
_COMPILED_PROBABILITY = [re.compile(p, re.IGNORECASE) for p in _PROBABILITY_SCOPE_PATTERNS]


def _detect_confusion(text: str) -> bool:
    """يكشف إشارات الحيرة في نص الطالب."""
    return any(p.search(text) for p in _COMPILED_CONFUSION)


def _detect_probability_scope(text: str) -> bool:
    """يكشف إذا كان السؤال ينتمي لنطاق الاحتمالات."""
    return any(p.search(text) for p in _COMPILED_PROBABILITY)


def _estimate_cognitive_load(
    question: str,
    history: list[dict[str, str]],
    current_load: float,
) -> float:
    """
    يُقدِّر الحِمل الإدراكي الجديد بناءً على إشارات الطالب.

    الإشارات المُرفِعة للحِمل:
        - وجود حيرة صريحة (+0.25)
        - سؤال طويل جداً (+0.10)
        - تكرار نفس السؤال في التاريخ (+0.15)

    الإشارات المُخفِّضة للحِمل:
        - سؤال قصير ومباشر (-0.10)
        - لا حيرة في آخر 3 رسائل (-0.05)
    """
    delta = 0.0

    if _detect_confusion(question):
        delta += 0.25

    if len(question) > 400:
        delta += 0.10

    # كشف تكرار السؤال في التاريخ
    recent = [m.get("content", "") for m in history[-4:] if m.get("role") == "user"]
    if any(_detect_confusion(m) for m in recent):
        delta += 0.15

    if len(question) < 80 and not _detect_confusion(question):
        delta -= 0.10

    if not any(_detect_confusion(m) for m in recent[-3:]):
        delta -= 0.05

    # تسوية تدريجية نحو الوسط (mean reversion)
    new_load = current_load + delta
    return max(0.0, min(1.0, new_load))


class AEKChannelA(RobustBaseModel):
    """
    القناة A — الحمولة الآلية المنظَّمة (JSON).

    تحتوي على النية التربوية وبيانات الحالة المعرفية.
    الواجهة تستهلك هذه القناة لتقرير طريقة العرض.
    """

    cognitive_intent: CognitiveIntent
    cognitive_state: CognitiveState
    exercise_scope: ExerciseScope
    step_index: int
    cognitive_load_index: float
    learner_capability: LearnerCapability
    runtime_mode: str
    topic_lock: bool
    abstraction_level: int = Field(ge=1, le=3)
    terminate_pipeline: bool = Field(
        default=False,
        description="True → الواجهة تُوقف أي LLM stream لاحق (Text-Wall Muzzle).",
    )
    impossible_branch: bool = Field(
        default=False,
        description="True → فرع محلي مستحيل، الحالة الأم سليمة.",
    )


class AEKChannelB(RobustBaseModel):
    """
    القناة B — السرد السقراطي الدافئ (Markdown).

    نص بشري فقط — لا JSON، لا بيانات آلية.
    مُزامَن مع الحالة البصرية النشطة.
    """

    narrative: str = Field(description="نص Markdown سقراطي دافئ.")
    pacing_hint: str = Field(
        default="normal",
        description="normal | slow | fast — تلميح للواجهة حول وتيرة العرض.",
    )


class AEKOutput(RobustBaseModel):
    """
    مخرج النواة التعليمية الكامل.

    يحتوي على القناتين A و B + الحالة المُحدَّثة.
    القناتان لا تتلوّثان — الواجهة تستهلكهما بشكل مستقل.
    """

    channel_a: AEKChannelA
    channel_b: AEKChannelB
    updated_state: AEKRuntimeState
    processing_ms: float = Field(default=0.0)


class AdaptiveEducationalKernel:
    """
    النواة التعليمية التكيّفية — المحرّك الرئيسي.

    يُحوِّل سؤال الطالب + الحالة الحالية إلى:
        - حالة معرفية جديدة (FSM transition)
        - نية تربوية (cognitive intent)
        - قناتان منفصلتان (A: JSON، B: Markdown)

    الاستخدام:
        kernel = AdaptiveEducationalKernel()
        output = kernel.process(question, history, state)
    """

    def process(
        self,
        question: str,
        history: list[dict[str, str]],
        state: AEKRuntimeState | None = None,
    ) -> AEKOutput:
        """
        يُعالج سؤال الطالب ويُنتج مخرج النواة الكامل.

        Args:
            question: سؤال الطالب (عربي/فرنسي/دارجة).
            history: تاريخ المحادثة [{"role": "user"|"assistant", "content": "..."}].
            state: الحالة المعرفية الحالية. إذا كانت None → تُنشأ حالة افتراضية.

        Returns:
            AEKOutput يحتوي على القناتين والحالة المُحدَّثة.
        """
        t0 = time.perf_counter()

        if state is None:
            state = AEKRuntimeState()

        # ── 1. تحديث الحِمل الإدراكي ──────────────────────────────────────────
        new_load = _estimate_cognitive_load(question, history, state.cognitive_load_index)
        state = state.model_copy(update={"cognitive_load_index": new_load})

        # ── 2. كشف النطاق الموضوعي ────────────────────────────────────────────
        if not state.topic_lock and _detect_probability_scope(question):
            state = state.model_copy(
                update={
                    "current_exercise_scope": ExerciseScope.PROBABILITY,
                    "topic_lock": True,
                }
            )

        # ── 3. انتقال FSM ─────────────────────────────────────────────────────
        prev_state = state.current_cognitive_state
        target = self._decide_target_state(question, state)
        new_cognitive_state = transition(prev_state, target)

        if new_cognitive_state != prev_state:
            state.record_transition(prev_state, new_cognitive_state)

        state = state.model_copy(update={"current_cognitive_state": new_cognitive_state})

        # ── 4. تحديد النية التربوية ───────────────────────────────────────────
        intent = self._resolve_intent(new_cognitive_state, state)
        state = state.model_copy(update={"current_cognitive_intent": intent})

        # ── 5. وضع التشغيل (MODE_A / MODE_B) ─────────────────────────────────
        is_mode_b = _detect_confusion(question)
        runtime_mode = "MODE_B" if is_mode_b else "MODE_A"
        state = state.model_copy(update={"current_runtime_mode": runtime_mode})

        # ── 6. بناء القناة A ──────────────────────────────────────────────────
        abstraction = state.abstraction_level_allowed()
        channel_a = AEKChannelA(
            cognitive_intent=intent,
            cognitive_state=new_cognitive_state,
            exercise_scope=state.current_exercise_scope,
            step_index=state.current_step_index,
            cognitive_load_index=round(state.cognitive_load_index, 3),
            learner_capability=state.learner_capability,
            runtime_mode=runtime_mode,
            topic_lock=state.topic_lock,
            abstraction_level=abstraction,
            terminate_pipeline=(runtime_mode == "MODE_A"),
            impossible_branch=False,
        )

        # ── 7. بناء القناة B ──────────────────────────────────────────────────
        channel_b = self._build_narrative(question, new_cognitive_state, intent, state)

        # ── 8. تقدّم الخطوة ───────────────────────────────────────────────────
        if new_cognitive_state not in (
            CognitiveState.CONFUSION,
            CognitiveState.EMOTIONAL_RECOVERY,
        ):
            state = state.model_copy(
                update={"current_step_index": state.current_step_index + 1}
            )

        elapsed = (time.perf_counter() - t0) * 1000

        logger.info(
            "aek_process: state=%s intent=%s load=%.2f mode=%s scope=%s step=%d ms=%.1f",
            new_cognitive_state.value,
            intent.value,
            state.cognitive_load_index,
            runtime_mode,
            state.current_exercise_scope.value,
            state.current_step_index,
            elapsed,
        )

        return AEKOutput(
            channel_a=channel_a,
            channel_b=channel_b,
            updated_state=state,
            processing_ms=round(elapsed, 2),
        )

    # ─── منطق القرار الداخلي ──────────────────────────────────────────────────

    def _decide_target_state(
        self,
        question: str,
        state: AEKRuntimeState,
    ) -> CognitiveState:
        """
        يُقرِّر الحالة المعرفية الهدف بناءً على السؤال والحالة الحالية.

        الأولوية:
            1. حيرة صريحة → CONFUSION
            2. حِمل مرتفع → EMOTIONAL_RECOVERY (من CONFUSION)
            3. متعلّم متقدّم + سؤال قصير → DIRECT_ANSWER
            4. نطاق احتمالات → VISUAL_INTUITION
            5. افتراضي → STEP_REASONING
        """
        current = state.current_cognitive_state

        if _detect_confusion(question):
            if current == CognitiveState.CONFUSION and state.is_overloaded():
                return CognitiveState.EMOTIONAL_RECOVERY
            return CognitiveState.CONFUSION

        if (
            state.learner_capability == LearnerCapability.ADVANCED
            and len(question) < 120
            and current == CognitiveState.STANDARD
        ):
            return CognitiveState.DIRECT_ANSWER

        if state.current_exercise_scope == ExerciseScope.PROBABILITY:
            if current in (CognitiveState.STANDARD, CognitiveState.EMOTIONAL_RECOVERY):
                return CognitiveState.VISUAL_INTUITION
            if current == CognitiveState.VISUAL_INTUITION:
                return CognitiveState.STEP_REASONING
            if current == CognitiveState.STEP_REASONING:
                return CognitiveState.FORMAL_MATH

        if current == CognitiveState.FORMAL_MATH:
            return CognitiveState.STANDARD

        return CognitiveState.STEP_REASONING

    def _resolve_intent(
        self,
        state: CognitiveState,
        runtime_state: AEKRuntimeState,
    ) -> CognitiveIntent:
        """
        يُحدِّد النية التربوية النهائية.

        المتعلّم المتقدّم مع حِمل منخفض → قد يتجاوز VISUAL_INTUITION مباشرةً
        إلى FORMAL_MATH.
        """
        default = DEFAULT_INTENT_FOR_STATE[state]

        # المتعلّم المتقدّم + حِمل منخفض + حالة STEP_REASONING → FORMAL_MATH مباشرةً
        if (
            runtime_state.learner_capability == LearnerCapability.ADVANCED
            and runtime_state.cognitive_load_index < 0.3
            and state == CognitiveState.STEP_REASONING
        ):
            return CognitiveIntent.FORMAL_MATH

        return default

    def _build_narrative(
        self,
        question: str,
        state: CognitiveState,
        intent: CognitiveIntent,
        runtime_state: AEKRuntimeState,
    ) -> AEKChannelB:
        """
        يبني السرد السقراطي الدافئ للقناة B.

        النص مُزامَن مع الحالة البصرية النشطة.
        لا JSON، لا بيانات آلية — Markdown فقط.
        """
        pacing = "normal"

        if state == CognitiveState.EMOTIONAL_RECOVERY:
            pacing = "slow"
            narrative = (
                "لا بأس — هذا المفهوم يحتاج وقتاً.\n\n"
                "دعنا نبدأ من الصفر بخطوة واحدة بسيطة جداً."
            )

        elif state == CognitiveState.CONFUSION:
            pacing = "slow"
            narrative = (
                "أفهم تماماً — هذه النقطة تُربك كثيراً من الطلاب.\n\n"
                "سنبني الفهم بصرياً أولاً قبل أي رمز رياضي."
            )

        elif intent == CognitiveIntent.VISUAL_INTUITION:
            narrative = (
                "قبل أي معادلة، دعنا نرى الصورة الكاملة.\n\n"
                "تخيّل المسألة كـ..."
            )

        elif intent == CognitiveIntent.STEP_REASONING:
            step = runtime_state.current_step_index + 1
            narrative = f"**الخطوة {step}:** نبني الحل خطوة بخطوة."

        elif intent == CognitiveIntent.FORMAL_MATH:
            pacing = "fast"
            narrative = "الآن نُصيغ الحل رياضياً بدقة:"

        elif intent == CognitiveIntent.DIRECT_ANSWER:
            pacing = "fast"
            narrative = "إجابة مباشرة:"

        else:
            narrative = "نتابع الشرح:"

        return AEKChannelB(narrative=narrative, pacing_hint=pacing)
