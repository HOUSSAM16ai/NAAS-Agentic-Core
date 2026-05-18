"""
BACExerciseSkill — Skill رسمي لاسترجاع وشرح تمارين بكالوريا الجزائر.

ISS-058 (D-052): الـ Skill المعماري الذي يستبدل "Prompt Spaghetti" بـ contract
محدد ومستقل وقابل للقياس. (راجع CLAUDE.md §0.5 — Skills Doctrine).

**المسؤولية الواحدة**: تحويل سؤال طالب (نص حر) إلى محتوى تعليمي رسمي من
`knowledge_base/` — إما:
  - **استرجاع** (retrieval): جلب نص التمرين النظيف
  - **شرح** (explanation): شرح كيف نصل للإجابة النموذجية، باستخدام التمرين
    المُحدد من السياق (إما صراحةً أو من تاريخ المحادثة).

**العقد** (Pydantic):
  - Input: `BACSkillInput(question, history_messages, conversation_id)`
  - Output: `BACSkillRetrievalOutput` | `BACSkillExplanationOutput` | `SkillFailure`

**الاستقلالية**:
- يستورد من `app.services.capabilities.*` (طبقة قدرات منخفضة) ولكنه
  لا يستورد من Skill آخر.
- يعمل بدون orchestrator-service، بدون LLM (إلا في وضع EXPLAIN).
- آمن في وضع fallback عند فشل LLM.

**القياس**:
- `cogniforge_skill_bac_invocations_total{mode,status}` (counter)
- `cogniforge_skill_bac_duration_seconds{mode}` (histogram)

**ISS-080 (D-068, 2026-05-18)** — Skill Doctrine موحَّد:
كل استدعاء يَخرج من `BACExerciseSkill` يحمل معه `methodology_handle` —
مرجع ثابت إلى الـ doctrine المُعتمد لكيفية شرح الإجابة النموذجية. هذا يفصل
*"كيف يفكر الـ Skill"* عن *"كيف يُعبَّأ الـ system prompt"*، فإذا تغيَّرت
الـ doctrine لاحقاً (مثلاً تعزيز قاعدة الاحتجاج بالإجابة النموذجية) — مكان
واحد فقط يتغيَّر، وكل callers يحصلون على الترقية تلقائياً.
"""

from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from contextlib import suppress
from enum import Enum
from typing import ClassVar, Literal

from pydantic import Field

try:
    from app.core.logging import get_logger
except ImportError:  # pragma: no cover — sandbox/test env without project logger
    import logging

    def get_logger(name: str) -> logging.Logger:  # type: ignore[no-redef]
        return logging.getLogger(name)


from app.core.schemas import RobustBaseModel
from app.services.capabilities.exercise_retrieval import (
    ExerciseEntry,
    ExerciseRetrievalRequest,
    detect_exercise_retrieval,
    detect_explanation_with_context,
    format_exercise_for_display,
    load_exercise_content,
)

# ─────────────────────────────────────────────────────────────────────────────
# D-069 (2026-05-18): Single Source of Truth = `app.services.skills.doctrine`
#
# الـ Skill يستورد الـ doctrines من `doctrine.py` بدلاً من تعريفها محلياً.
# هذا يضمن أن:
#   - تغيير قاعدة doctrine = تعديل ملف واحد فقط (`doctrine.py`).
#   - الـ version pin يتزامن تلقائياً عبر كل callers (Skill + system prompts).
#   - الـ CI gate `check_skills_doctrine.py` يفحص مكاناً واحداً.
#
# Backward-compat: re-export `EXPLANATION_DOCTRINE` و
# `get_explanation_doctrine_summary` و `EXPLANATION_DOCTRINE_VERSION` تحت
# هذا الـ namespace حتى لا يكسر أي caller قديم.
# الأسماء مُعرَّفة في `__all__` أدناه لمنع ruff من حذفها كـ unused imports.
# ─────────────────────────────────────────────────────────────────────────────
from app.services.skills.doctrine import (
    EXPLANATION_DOCTRINE,
    EXPLANATION_DOCTRINE_VERSION,
    get_explanation_doctrine_summary,
)

logger = get_logger("skill.bac_exercise")

# Backward-compat re-exports — لا تحذف هذه الأسماء بدون ADR (CI gate يحرسها).
__all__ = [
    "EXPLANATION_DOCTRINE",
    "EXPLANATION_DOCTRINE_VERSION",
    "BACExerciseSkill",
    "BACSkillExplanationOutput",
    "BACSkillInput",
    "BACSkillRetrievalOutput",
    "SkillFailure",
    "SkillMode",
    "get_explanation_doctrine_summary",
]


class SkillMode(str, Enum):  # noqa: UP042  # subclassing keeps str semantics on older runtimes
    """أنماط تشغيل الـ Skill — اختيار صريح يُجبر استدلال واضحاً."""

    RETRIEVE = "retrieve"  # جلب نص تمرين رسمي
    EXPLAIN = "explain"  # شرح كيف نصل للإجابة النموذجية
    AUTO = "auto"  # تخمين النية تلقائياً


class BACSkillInput(RobustBaseModel):
    """مدخلات الـ Skill — typed contract موحَّد."""

    question: str = Field(..., min_length=1, max_length=4000)
    mode: SkillMode = SkillMode.AUTO
    history_messages: list[dict[str, str]] | None = None
    conversation_id: int | None = None


class BACSkillRetrievalOutput(RobustBaseModel):
    """مخرج الـ Skill في وضع RETRIEVE."""

    skill: Literal["bac_exercise"] = "bac_exercise"
    mode: Literal["retrieve"] = "retrieve"
    matched_entry: ExerciseEntry
    display_content: str  # نص نظيف للعرض (بدون YAML، بدون حل)
    is_streamable: bool = True

    model_config: ClassVar[dict[str, object]] = {"arbitrary_types_allowed": True}


class BACSkillExplanationOutput(RobustBaseModel):
    """مخرج الـ Skill في وضع EXPLAIN.

    يحتوي على:
    - `matched_entry`: التمرين المُحدد (من السؤال أو من السياق)
    - `display_content`: نص التمرين فقط (لعرض مبدئي إن أراد المستخدم)
    - `full_content`: نص التمرين + الإجابة النموذجية (للـ LLM فقط)
    - `requested_part`: الجزء المُحدد (I / II / III) إن وُجد
    - `match_source`: "question" | "history" — من أين أتى الـ matched_entry
    - `methodology_handle` (ISS-080 / D-068): مرجع doctrine الشرح المُعتمد —
      كل caller يُفترض أن يحترم هذا. تغيير الـ doctrine = تغيير الرقم هنا.
    """

    skill: Literal["bac_exercise"] = "bac_exercise"
    mode: Literal["explain"] = "explain"
    matched_entry: ExerciseEntry
    display_content: str
    full_content: str  # لا يُرسل للمستخدم — للـ LLM فقط
    requested_part: str | None = None
    match_source: Literal["question", "history"] = "question"
    methodology_handle: str = Field(
        default_factory=lambda: f"explanation_doctrine_v{EXPLANATION_DOCTRINE_VERSION}",
        description=(
            "معرّف ثابت لـ doctrine الشرح. يضمن أن الـ caller يستخدم الإصدار "
            "المعروف من قواعد شرح الإجابة النموذجية."
        ),
    )

    model_config: ClassVar[dict[str, object]] = {"arbitrary_types_allowed": True}


class SkillFailure(RobustBaseModel):
    """مخرج الـ Skill عند عدم التطابق — يسمح للـ caller بالتقدم لـ Skill آخر."""

    skill: Literal["bac_exercise"] = "bac_exercise"
    success: Literal[False] = False
    reason: str
    suggested_next: str | None = None


SkillOutput = BACSkillRetrievalOutput | BACSkillExplanationOutput | SkillFailure


def _record_metric(mode: str, status: str, duration_s: float) -> None:
    """يبث مقاييس Prometheus عبر طبقة الـ telemetry الموحَّدة.

    يحترم §0 doctrine: «Instrumentation before visualization».
    لا يكسر الـ skill إذا التيليمتري فشل (always-suppress).
    """
    try:
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        obs.record_metric(
            "skill.bac.invocations.total",
            1.0,
            labels={"mode": mode, "status": status},
        )
        obs.record_metric(
            "skill.bac.duration_seconds",
            duration_s,
            labels={"mode": mode},
        )
    except Exception:  # pragma: no cover — observability never blocks logic
        pass


class BACExerciseSkill:
    """Skill رسمي يستبدل Prompt Spaghetti بـ contract محدَّد ومستقل.

    Usage:
        skill = BACExerciseSkill()
        result = skill.invoke(BACSkillInput(question="...", history_messages=[...]))

        if isinstance(result, BACSkillRetrievalOutput):
            # بث display_content للمستخدم
            ...
        elif isinstance(result, BACSkillExplanationOutput):
            # مرِّر full_content للـ LLM ضمن system prompt الشرح
            ...
        else:
            # SkillFailure → اذهب لـ Skill التالي
            ...

    لاحظ: هذا الـ Skill **متزامن** في الطبقة الأساسية (no LLM call).
    البث الفعلي يتم في طبقة `orchestrator_client._stream_local_retrieval_response`
    أو `_stream_exercise_explanation_response` التي تستهلك المخرج.
    """

    name: str = "bac_exercise"
    version: str = "1.0.0"

    # ─────────────────────────────────────────────────────────────────────
    # واجهة الاستدعاء المتزامنة
    # ─────────────────────────────────────────────────────────────────────
    def invoke(self, payload: BACSkillInput) -> SkillOutput:
        """نقطة الدخول الموحَّدة — يختار وضع RETRIEVE أو EXPLAIN حسب النية."""
        t0 = time.perf_counter()
        try:
            if payload.mode == SkillMode.RETRIEVE:
                result = self._retrieve(payload)
            elif payload.mode == SkillMode.EXPLAIN:
                result = self._explain(payload)
            else:
                # AUTO: حاوِل EXPLAIN أولاً (أدق)، ثم RETRIEVE
                result = self._explain(payload)
                if isinstance(result, SkillFailure):
                    result = self._retrieve(payload)
            duration = time.perf_counter() - t0
            status = "success" if not isinstance(result, SkillFailure) else "no_match"
            mode_label = result.mode if not isinstance(result, SkillFailure) else payload.mode.value
            _record_metric(mode_label, status, duration)
            return result
        except Exception:
            duration = time.perf_counter() - t0
            _record_metric(payload.mode.value, "error", duration)
            logger.warning("bac_exercise_skill_failed", exc_info=True)
            return SkillFailure(reason="internal_error")

    # ─────────────────────────────────────────────────────────────────────
    # وضع RETRIEVE
    # ─────────────────────────────────────────────────────────────────────
    def _retrieve(self, payload: BACSkillInput) -> BACSkillRetrievalOutput | SkillFailure:
        decision = detect_exercise_retrieval(ExerciseRetrievalRequest(question=payload.question))
        if not decision.recognized or decision.matched_entry is None:
            return SkillFailure(
                reason=decision.reason or "no_retrieval_match",
                suggested_next="explain_or_general_chat",
            )

        raw = load_exercise_content(decision.matched_entry)
        if not raw:
            return SkillFailure(reason="content_file_not_found")

        display = format_exercise_for_display(decision.matched_entry, raw)
        if not display:
            return SkillFailure(reason="empty_display_content")

        return BACSkillRetrievalOutput(
            matched_entry=decision.matched_entry,
            display_content=display,
        )

    # ─────────────────────────────────────────────────────────────────────
    # وضع EXPLAIN
    # ─────────────────────────────────────────────────────────────────────
    def _explain(self, payload: BACSkillInput) -> BACSkillExplanationOutput | SkillFailure:
        decision = detect_explanation_with_context(
            ExerciseRetrievalRequest(question=payload.question),
            history_messages=payload.history_messages,
        )
        if (
            not decision.recognized
            or decision.matched_entry is None
            or not decision.full_content
            or not decision.display_content
        ):
            return SkillFailure(
                reason=decision.reason or "no_explanation_context",
                suggested_next="retrieve_or_general_chat",
            )

        match_source: Literal["question", "history"] = (
            "history"
            if decision.reason == "bac_explanation_with_conversation_context"
            else "question"
        )

        return BACSkillExplanationOutput(
            matched_entry=decision.matched_entry,
            display_content=decision.display_content,
            full_content=decision.full_content,
            requested_part=decision.requested_part,
            match_source=match_source,
        )

    # ─────────────────────────────────────────────────────────────────────
    # واجهة بث (للاستهلاك من orchestrator_client)
    # ─────────────────────────────────────────────────────────────────────
    async def stream_retrieval(
        self,
        payload: BACSkillInput,
    ) -> AsyncGenerator[str, None]:
        """بث محتوى الاسترجاع كلمة-بكلمة (يستدعي مولِّد البث الأقدم)."""
        result = self.invoke(
            BACSkillInput(
                question=payload.question,
                mode=SkillMode.RETRIEVE,
                history_messages=payload.history_messages,
                conversation_id=payload.conversation_id,
            )
        )
        if not isinstance(result, BACSkillRetrievalOutput):
            return

        # نُمرِّر النص إلى المولِّد القائم في orchestrator_client
        from app.infrastructure.clients.orchestrator_client import OrchestratorClient

        with suppress(Exception):
            client = OrchestratorClient(base_url="http://noop")  # base_url غير مُستخدم هنا
            async for chunk in client._stream_local_retrieval_response(payload.question):
                if chunk:
                    yield chunk

    async def stream_explanation(
        self,
        payload: BACSkillInput,
    ) -> AsyncGenerator[str, None]:
        """بث الشرح المُولَّد من LLM (يستدعي local_graph context-aware)."""
        result = self.invoke(
            BACSkillInput(
                question=payload.question,
                mode=SkillMode.EXPLAIN,
                history_messages=payload.history_messages,
                conversation_id=payload.conversation_id,
            )
        )
        if not isinstance(result, BACSkillExplanationOutput):
            return

        from app.services.chat.local_graph import run_local_graph_with_exercise_context

        async for chunk in run_local_graph_with_exercise_context(
            question=payload.question,
            exercise_full_content=result.full_content,
            conversation_id=payload.conversation_id,
            history_messages=payload.history_messages,
        ):
            if chunk:
                yield chunk
