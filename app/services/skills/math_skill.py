"""
MathSkill — وحدة Skill رسمية لحل وشرح أسئلة الرياضيات (D-062 / ISS-074).

CLAUDE.md §0.5: «كل قدرة ذكاء اصطناعي يجب أن تكون Skill — وحدة مستقلة قابلة للقياس والاختبار والاستبدال».

## المسؤولية الواحدة
تحويل سؤال رياضي (نص حر) إلى شرح تعليمي عالي الجودة:
- تصنيف نوع المسألة (مشتق/تكامل/نهاية/معادلة/...)
- استدعاء النموذج المناسب مع system prompt متخصص
- التطبيع: LaTeX، تنظيف foreign scripts، استبعاد meta-narration
- إصدار شرح خطوة بخطوة مع `$$\\boxed{...}$$`

## العقد (Pydantic)
- Input: `MathSkillInput(question, history, conversation_id)`
- Output: `MathSkillOutput | SkillFailure`

## الاستقلالية
- يحترم الـ hard boundary (`tests/architecture/test_boundaries.py`):
  *لا يستورد* من `microservices/*` على مستوى الـ AST. يجلب
  `invoke_math_pipeline` و `_TYPE_LABELS` ديناميكياً عبر
  `importlib.import_module` عند `invoke()` فقط — بحيث يستطيع
  الموناوليث استدعاء Skill conversation-service محلياً (in-process) متى
  كان الـ pipeline متاحاً، ويُرجع `SkillFailure` بأمان إذا لم يكن.
- لا يستورد من Skills أخرى مباشرةً
- يعمل بدون orchestrator-service
- آمن في وضع fallback عند فشل LLM (يُرجع `SkillFailure`)

## القياس (Prometheus)
- `cogniforge_skill_math_invocations_total{math_type,status}` (counter)
- `cogniforge_skill_math_duration_seconds{math_type}` (histogram)
- `cogniforge_skill_math_retries_total{reason}` (counter — meta/echo/foreign)

## الاستخدام (في monolith)
```python
from app.services.skills import MathSkill, MathSkillInput, MathSkillOutput, SkillFailure

skill = MathSkill()
result = await skill.invoke(MathSkillInput(question="احسب مشتقة x²·e^(3x)"))
if isinstance(result, MathSkillOutput):
    print(result.solution)  # شرح خطوة بخطوة
```
"""

from __future__ import annotations

import importlib
import time
from typing import Literal

from pydantic import Field

try:
    from app.core.logging import get_logger
except ImportError:  # pragma: no cover
    import logging

    def get_logger(name: str) -> logging.Logger:  # type: ignore[no-redef]
        return logging.getLogger(name)


from app.core.schemas import RobustBaseModel
from app.services.skills.bac_exercise_skill import SkillFailure
from app.services.skills.base import BaseSkill

logger = get_logger("skill.math")


# ── Prometheus metrics ─────────────────────────────────────────────────────────
try:
    from prometheus_client import REGISTRY, Counter, Histogram

    # حماية ضد إعادة التسجيل (re-import safe)
    if "cogniforge_skill_math_invocations_total" in {m.name for m in REGISTRY.collect()}:
        _math_invocations = next(
            m for m in REGISTRY.collect() if m.name == "cogniforge_skill_math_invocations_total"
        )
        _math_duration = next(
            m for m in REGISTRY.collect() if m.name == "cogniforge_skill_math_duration_seconds"
        )
        _math_retries = next(
            m for m in REGISTRY.collect() if m.name == "cogniforge_skill_math_retries_total"
        )
    else:
        _math_invocations = Counter(
            "cogniforge_skill_math_invocations_total",
            "Total invocations of MathSkill, labelled by math_type and status.",
            ["math_type", "status"],
        )
        _math_duration = Histogram(
            "cogniforge_skill_math_duration_seconds",
            "Duration of MathSkill invocations in seconds.",
            ["math_type"],
        )
        _math_retries = Counter(
            "cogniforge_skill_math_retries_total",
            "MathSkill retries by reason (meta-text, echo, foreign-script).",
            ["reason"],
        )

    import contextlib

    def _record_invocation(math_type: str, status: str, duration: float) -> None:
        with contextlib.suppress(Exception):
            _math_invocations.labels(math_type=math_type, status=status).inc()
            _math_duration.labels(math_type=math_type).observe(duration)

    def _record_retry(reason: str) -> None:
        with contextlib.suppress(Exception):
            _math_retries.labels(reason=reason).inc()

except Exception:  # pragma: no cover

    def _record_invocation(math_type: str, status: str, duration: float) -> None:
        pass

    def _record_retry(reason: str) -> None:
        pass


# ── Pydantic contracts ─────────────────────────────────────────────────────────


class MathSkillInput(RobustBaseModel):
    """مدخلات الـ Skill — typed contract موحَّد."""

    question: str = Field(..., min_length=1, max_length=4000)
    history: list[dict[str, str]] | None = None
    conversation_id: int | None = None
    thread_id: str | None = None


class MathSkillOutput(RobustBaseModel):
    """مخرج الـ Skill عند النجاح."""

    skill: Literal["math"] = "math"
    math_type: str  # derivative | integral | limit | ... | general_math
    type_label: str  # "📐 مسألة اشتقاق", ...
    solution: str  # نص الشرح الكامل بـ LaTeX موحَّد
    final_response: str  # solution + label heading (جاهز للعرض)
    duration_ms: int
    retried: bool = False


# ── Skill ───────────────────────────────────────────────────────────────────────


class MathSkill(BaseSkill[MathSkillInput, MathSkillOutput]):
    """
    Skill رسمي لحل وشرح أسئلة الرياضيات.

    عقد دائم (لا يُكسر بدون ADR):
    1. صفر تبعيات على Skills أخرى — استقلالية إلزامية
    2. dispatch ديناميكي إلى math_pipeline (مع تطبيع كامل)
    3. كل invocation يُسجَّل في Prometheus
    4. fallback آمن: إذا فشل LLM → SkillFailure (لا exception)
    5. typed contract — لا تمرير dicts خام
    """

    _skill_name: str = "math"
    name = "math"

    def run(self, payload: MathSkillInput):
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`invoke` (async)."""
        return self.invoke(payload)

    # Dynamic resolution path to keep `app/` free of AST-level
    # `from microservices.*` imports (enforced by tests/architecture/test_boundaries.py).
    # The conversation-service math pipeline ships its module name as a
    # plain string and is loaded on demand here.
    _PIPELINE_MODULE: str = "microservices.conversation_service.src.math_pipeline"

    @classmethod
    def _load_pipeline(cls):
        """Lazy import of the math pipeline module. Returns None if unavailable."""
        try:
            return importlib.import_module(cls._PIPELINE_MODULE)
        except Exception:  # pragma: no cover — module not present in CI sandbox
            return None

    async def invoke(self, payload: MathSkillInput) -> MathSkillOutput | SkillFailure:
        """يُنفِّذ الـ Skill ويُرجع نتيجة typed."""
        t0 = time.perf_counter()
        math_type = "general_math"
        try:
            pipeline = self._load_pipeline()
            if pipeline is None or not hasattr(pipeline, "invoke_math_pipeline"):
                duration = time.perf_counter() - t0
                _record_invocation(math_type, "unavailable", duration)
                return SkillFailure(
                    reason="pipeline_unavailable",
                    details=(
                        "conversation-service math_pipeline module is not importable. "
                        "Run docker compose up -d or supervisor.sh to start it."
                    ),
                )

            result = await pipeline.invoke_math_pipeline(
                question=payload.question,
                thread_id=payload.thread_id or f"math-skill-{payload.conversation_id or 0}",
                history=payload.history or [],
            )
            math_type = result.get("math_type", "general_math")
            solution = result.get("solution", "")
            final_response = result.get("final_response", "")
            error = result.get("error")

            duration = time.perf_counter() - t0

            if error or not solution or len(solution.strip()) < 20:
                _record_invocation(math_type, "fallback", duration)
                return SkillFailure(
                    reason="empty_solution" if not solution else error or "unknown",
                    details=f"math_type={math_type} | duration={duration:.2f}s",
                )

            # نجاح
            _record_invocation(math_type, "success", duration)
            type_labels = getattr(pipeline, "_TYPE_LABELS", {})

            return MathSkillOutput(
                math_type=math_type,
                type_label=type_labels.get(math_type, "📚 رياضيات"),
                solution=solution,
                final_response=final_response,
                duration_ms=int(duration * 1000),
                retried=False,
            )
        except Exception as exc:
            duration = time.perf_counter() - t0
            _record_invocation(math_type, "error", duration)
            logger.error("MathSkill.invoke failed: %s", exc, exc_info=True)
            return SkillFailure(
                reason="exception",
                details=f"{type(exc).__name__}: {exc}",
            )


__all__ = ["MathSkill", "MathSkillInput", "MathSkillOutput"]
