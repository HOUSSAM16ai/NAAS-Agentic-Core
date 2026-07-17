"""D-170: سياق الدور المشترك بين مراحل preempt في `chat_with_agent`.

`chat_with_agent` كان دالة async-generator واحدة (~1,030 سطراً) بكتل preempt تتشارك
حالة محلية. التفكيك (D-170) حوّل كل كتلة إلى مرحلة sub-generator تقرأ/تكتب هذا
السياق: المرحلة تبثّ أحداثها، وتضبط ``turn_complete = True`` **صراحةً** عند اكتمال
الدور (لا الاعتماد على «بثّ أي شيء» — MODE_B يبثّ ويُكمل). المُنسِّق في
`chat_turn.py` يمشي المراحل بالترتيب — **الترتيب هو العقد** (ISS-110/D-124/D-101).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnContext:
    """حالة دور الدردشة المشتركة بين مراحل الـ preempt (D-170)."""

    question: str
    user_id: int
    conversation_id: int | None
    history_messages: list[dict[str, str]] | None
    context: dict[str, object] | None
    # رصد الدور (telemetry) — يُنشأ مرة واحدة في المُنسِّق.
    obs: Any = None
    t0: float = 0.0
    root_ctx: Any = None
    # قناة الـ handoff الدائمة (D-142/D-158) — تُستخرَج في مرحلة بوابة السياسة.
    tutor_state: dict[str, object] = field(default_factory=dict)
    # V38.0: قرار التوجيه من مرحلة الواجهة المحسوبة — يقرأه سلك HTTP والـ fallback.
    is_mode_b: bool = False
    # D-052/D-103: قرار الشرح بسياق + حقن محتوى التمرين نحو الـ orchestrator.
    explanation_decision: Any = None
    exercise_injection: dict[str, str] = field(default_factory=dict)
    # MODE_B: السؤال الفعّال (بتعليمة الشرح العميق) — يستهلكه سلك HTTP والـ fallback.
    effective_question: str = ""
    # العقد المركزي: المرحلة التي تُكمل الدور تضبطه True فيتوقف المُنسِّق فوراً.
    turn_complete: bool = False
