"""موجّه البيداغوجيا البصرية (Protocol V26.2).

نقطة دخول HTTP حتمية تُرجِع حمولة الواجهة التوليدية لمسائل الاحتمالات عبر
``ProbabilityCalculatorSkill`` — بلا قاعدة بيانات وبلا LLM. الغرض الأساسي:
إثبات عقد «الحالة المستحيلة» (impossible_case) حياً عبر POST بسيط، وتغذية
الواجهة (Next.js) بمكوّن توليدي جاهز للتصيير.

عند طلب سحب مستحيل (k > المتاح، بلا إرجاع) يُقصِّر المحرّك الدائرة ويُرجِع
البنية المُفكَّكة الصارمة (visual_directives / numerical_state /
pedagogical_message) بدل أي حساب تأليفي منحلّ.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.skills.probability_skill import (
    ImpossibleCaseOutput,
    ProbabilityCalculatorSkill,
    ProbabilityInput,
)

router = APIRouter(prefix="/api/v1/visual-pedagogy", tags=["visual-pedagogy"])


class VisualPedagogyRequest(BaseModel):
    """طلب تحليل مسألة احتمالات لإنتاج مكوّن واجهة توليدي."""

    question: str = Field(..., min_length=1, max_length=8000)
    history: list[dict[str, str]] | None = None


@router.post("/probability")
async def analyze_probability(payload: VisualPedagogyRequest) -> dict[str, object]:
    """يحلّل المسألة ويُرجِع مخرَج المحرّك الحتمي مباشرةً (model_dump).

    عند الحالة المستحيلة يكون ``ui_mode == "impossible_case"`` والبنية مُفكَّكة
    تماماً — لا تدخل أي عقدة حساب/شجرة/synthesizer.

    V28.0: يُضاف ``companion_text`` (≤ 120 حرف) و``terminate_pipeline=True``
    للحالة المستحيلة — يُعلم الواجهة بكبح أي نص LLM لاحق.
    """
    skill = ProbabilityCalculatorSkill()
    result = skill.analyze(ProbabilityInput(question=payload.question, history=payload.history))
    body = result.model_dump()
    is_impossible = isinstance(result, ImpossibleCaseOutput)
    body["is_impossible_case"] = is_impossible
    body["terminate_pipeline"] = is_impossible
    return body
