"""شرائح الشروط الحتمية للرسم الموحَّد (D-262).

نمط D-164/D-168/D-261: شرائح نقية بلا حالة تفوَّض إليها القشرة `main.py`
بالاسم نفسه (`route_intent` · `check_results` · `check_quality` + ثوابت
`ROUTING_MAP` و`FAILURE_PHRASES`) — لا أسماء أعيد تعريفها، فيبقى كل
monkeypatch واختبارٍ قديم فعالًا.

DEADLOCK FIX (D-262 · ISS-173): `route_intent` يعيد النية المكلَّمة لا اسم
العقدة — خريطة الحافة الشرطية تحوّلها إلى العقدة. أي نيةٍ مجهولةٍ لا تظهر في
`ROUTING_MAP` تُقفَل حتمًا إلى `"educational"` بدل أن يرمي LangGraph
«unknown branch» (deadlock صامت كان يطال الطالب في أقصى درجات الارتباك).
"""

from __future__ import annotations

import logging

from microservices.orchestrator_service.src.services.overmind.graph.state import (
    AgentState,
)

logger = logging.getLogger("graph")

#: جدول التوجيه التصريحي من النية إلى العقدة الأولى لكل شعبة (D-262).
#: «النية» هي القيمة التي يعيدها `route_intent`، و`check_results` تعود منها
#: مفاتيح الحافة على `reranker`.
ROUTING_MAP: dict[str, str] = {
    "educational": "query_rewriter",
    "admin": "admin_agent",
    "tool": "tool_executor",
    "chat": "chat_fallback",
    "general_knowledge": "general_knowledge",
}

#: عبارات الفشل التي تعيد التحويلة إلى المشرف (D-262 — مطابقة حرفية للأصل).
FAILURE_PHRASES: tuple[str, ...] = ("لم أفهم", "يرجى التوضيح", "لا أستطيع")


def route_intent(state: AgentState) -> str:
    """تعيد النية المكلَّمة (لا اسم العقدة — الحافة الشرطية تحوّلها) — D-262.

    السلوك مطابقٌ حرفيًا للأصل: نية `search` تعاد إلى `educational`،
    والنيات المجهولة تُقفَل إلى `educational` (DEADLOCK FIX · ISS-173).
    """
    intent = state.get("intent", "educational")

    if intent == "search":
        intent = "educational"

    # DEADLOCK FIX: guarantee a valid branch. Returning a raw intent absent
    # from the conditional-edge map raises a LangGraph "unknown branch" error;
    # clamp unexpected intents to a deterministic default exit.
    if intent not in ROUTING_MAP:
        intent = "educational"
    logger.info(f"SUPERVISOR_NODE → routing to → {ROUTING_MAP[intent]}")
    return intent


def check_results(state: AgentState) -> str:
    """شريطة حافة `reranker` — مطابقة حرفية للأصل (D-262)."""
    docs = state.get("reranked_docs", [])
    if len(docs) > 0:
        return "found"
    intent = state.get("intent", "")
    if intent == "educational":
        return "web_fallback"
    return "general_knowledge"


def check_quality(state: AgentState) -> str:
    """شريطة حافة `validator` — مطابقة حرفية للأصل (D-262)."""
    final_response = state.get("final_response")
    if not final_response:
        return "fail"

    if isinstance(final_response, str):
        response_lower = final_response.lower()
        if (
            any(phrase in response_lower for phrase in FAILURE_PHRASES)
            or not response_lower.strip()
        ):
            return "fail"

    return "pass"
