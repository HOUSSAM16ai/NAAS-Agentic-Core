"""LogicReasoningSkill — المنطق والاستدلال (D-181).

CLAUDE.md §0.5: «كل قدرة AI يجب أن تكون Skill». هذه المهارة تُقرِّر **صحّة الحجّة**
منطقياً وتكشف **المغالطات الشكلية** — الحقيقة من المحرّك الرمزي المُتحقَّق
(`app/core/reasoning/arguments` فوق `foundations.logic`)، لا من الـ LLM.

## المسؤولية الواحدة
تحليل حجّة منطقية (مقدّمات → نتيجة) وإرجاع: صالحة؟ ما شكلها؟ مغالطة؟ + مثال مضادّ
يُبيّن *لماذا* لا تلزم النتيجة (سقراطي). حتمية 100% وقابلة للاختبار بـ pytest.

## القياس (Prometheus)
- `cogniforge_skill_logic_reasoning_total{status}` (counter)
- `cogniforge_skill_logic_reasoning_duration_seconds` (histogram)
"""

from __future__ import annotations

import time
from typing import ClassVar

from pydantic import Field

from app.core.reasoning import arguments as arg_mod
from app.core.reasoning.errors import ReasoningError
from app.core.schemas import RobustBaseModel
from app.services.skills.base import BaseSkill, skill_counter, skill_histogram
from app.services.skills.doctrine import LOGIC_REASONING_DOCTRINE_VERSION

_INVOCATIONS = skill_counter(
    "cogniforge_skill_logic_reasoning_total",
    "LogicReasoningSkill invocations",
    ("status",),
)
_DURATION = skill_histogram(
    "cogniforge_skill_logic_reasoning_duration_seconds",
    "LogicReasoningSkill duration (seconds)",
)


class LogicReasoningInput(RobustBaseModel):
    """مدخلات تحليل الحجّة — مقدّمات ونتيجة كصيغ منطقية نصّية (`p -> q`, `~p`, ...)."""

    premises: list[str] = Field(default_factory=list, max_length=32)
    conclusion: str = Field(..., min_length=1, max_length=500)


class LogicReasoningOutput(RobustBaseModel):
    """مخرج تحليل الحجّة."""

    valid: bool
    form: str
    is_fallacy: bool
    variables: list[str]
    counterexample: dict[str, bool] | None = None
    explanation: str
    error: str | None = None


class LogicReasoningSkill(BaseSkill[LogicReasoningInput, LogicReasoningOutput]):
    """يُقرِّر صحّة الحجّة ويكشف المغالطة الشكلية — رمزي حتمي (D-181)."""

    name: ClassVar[str] = "logic_reasoning"
    version: ClassVar[str] = "1.0.0"
    doctrine_version: ClassVar[str] = LOGIC_REASONING_DOCTRINE_VERSION

    def run(self, payload: LogicReasoningInput) -> LogicReasoningOutput:
        """Polymorphic entry point (BaseSkill) — delegates to :meth:`analyze`."""
        return self.analyze(payload)

    def analyze(self, payload: LogicReasoningInput) -> LogicReasoningOutput:
        """يحلّل الحجّة حتمياً — لا يرفع استثناءً (خطأ الصياغة يُبلَّغ في `error`)."""
        t0 = time.perf_counter()
        try:
            premises = [arg_mod.parse(p) for p in payload.premises if p and p.strip()]
            conclusion = arg_mod.parse(payload.conclusion)
            argument = arg_mod.make_argument(premises, conclusion) if premises else None
            if argument is None:
                out = LogicReasoningOutput(
                    valid=False,
                    form="no_premises",
                    is_fallacy=False,
                    variables=sorted(conclusion.atoms()),
                    explanation="لا مقدّمات: لا يمكن الحكم على لزوم النتيجة دون مقدّمة واحدة على الأقل.",
                )
                _record("no_premises", time.perf_counter() - t0)
                return out

            form = arg_mod.classify_argument_form(argument)
            valid = argument.is_valid()
            counter = None if valid else argument.counterexample()
            out = LogicReasoningOutput(
                valid=valid,
                form=form,
                is_fallacy=arg_mod.is_fallacy(form),
                variables=argument.variables(),
                counterexample=counter,
                explanation=_explain(form, valid, counter),
            )
            _record("ok", time.perf_counter() - t0)
            return out
        except ReasoningError as exc:
            _record("parse_error", time.perf_counter() - t0)
            return LogicReasoningOutput(
                valid=False,
                form="unparseable",
                is_fallacy=False,
                variables=[],
                explanation="تعذّر تحليل الصياغة المنطقية — تحقّق من الرموز (-> & | ~).",
                error=str(exc),
            )
        except Exception as exc:  # pragma: no cover — fail-safe
            _record("error", time.perf_counter() - t0)
            return LogicReasoningOutput(
                valid=False,
                form="error",
                is_fallacy=False,
                variables=[],
                explanation="خطأ داخلي أثناء التحليل المنطقي.",
                error=type(exc).__name__,
            )


_FORM_LABELS: dict[str, str] = {
    "modus_ponens": "قياس استثنائي متصل (Modus Ponens)",
    "modus_tollens": "قياس استثنائي رافع (Modus Tollens)",
    "hypothetical_syllogism": "قياس شرطي متصل (Hypothetical Syllogism)",
    "disjunctive_syllogism": "قياس استثنائي منفصل (Disjunctive Syllogism)",
    "affirming_the_consequent": "مغالطة إثبات التالي",
    "denying_the_antecedent": "مغالطة نفي المقدّم",
    "circular_reasoning": "مصادرة على المطلوب (دور)",
}


def _explain(form: str, valid: bool, counter: dict[str, bool] | None) -> str:
    label = _FORM_LABELS.get(form, "شكل غير قياسي")
    if valid and not arg_mod.is_fallacy(form):
        return f"الحجّة صحيحة منطقياً ({label}): كلّ حالة تُصدِّق المقدّمات تُصدِّق النتيجة."
    tail = ""
    if counter:
        assign = "، ".join(f"{k}={'صحيح' if v else 'خطأ'}" for k, v in counter.items())
        tail = f" مثال مضادّ يكسرها: عند ({assign}) تصدُق المقدّمات وتكذب النتيجة."
    return f"الحجّة غير صحيحة منطقياً ({label}): النتيجة لا تلزم عن المقدّمات.{tail}"


def _record(status: str, duration: float) -> None:
    try:
        _INVOCATIONS.labels(status=status).inc()
        _DURATION.observe(duration)
    except Exception:  # pragma: no cover
        pass


def get_logic_reasoning_skill() -> LogicReasoningSkill:
    """يُرجع نسخة مفردة (BaseSkill.instance)."""
    return LogicReasoningSkill.instance()


__all__ = [
    "LogicReasoningInput",
    "LogicReasoningOutput",
    "LogicReasoningSkill",
    "get_logic_reasoning_skill",
]
