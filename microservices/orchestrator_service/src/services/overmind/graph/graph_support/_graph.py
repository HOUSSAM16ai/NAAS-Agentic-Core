"""شريحة بناء الرسم الموحَّد (D-262).

نمط D-164/D-168/D-261: شريحة نقية تسجّل العقد والأسلاك الحتمية وسلسلة
الـcompile/checkpointer — السلوك مطابقٌ حرفيًا لـ`create_unified_graph`
الأصلي: 12 عقدة + 3 حافات شرطية + DEADLOCK FIX على `general_knowledge`
(D-262 · ISS-173)، ولا منطق تنفيذي في القشرة.
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from microservices.orchestrator_service.src.services.overmind.graph.graph_support._conditions import (
    check_quality,
    check_results,
    route_intent,
)
from microservices.orchestrator_service.src.services.overmind.graph.graph_support._search_shards import (
    load_search_nodes,
)
from microservices.orchestrator_service.src.services.overmind.graph.nodes import (
    ChatFallbackNode,
    QueryRewriterNode,
    SupervisorNode,
    ToolExecutorNode,
    ValidatorNode,
    _configure_dspy,
)
from microservices.orchestrator_service.src.services.overmind.graph.state import (
    AgentState,
)

logger = logging.getLogger(__name__)


def _register_nodes(graph: StateGraph, admin_app=None) -> StateGraph:
    """تسجيل العقد الاثنتي عشرة — مطابقة حرفية للأصل (D-262)."""
    (
        query_analyzer_node,
        internal_retriever_node,
        reranker_node,
        web_search_fallback_node,
        synthesizer_node,
    ) = load_search_nodes()

    from microservices.orchestrator_service.src.services.overmind.graph.admin import (
        AdminAgentNode,
    )
    from microservices.orchestrator_service.src.services.overmind.graph.general_knowledge import (
        GeneralKnowledgeNode,
    )

    graph.add_node("supervisor", SupervisorNode())
    graph.add_node("query_rewriter", QueryRewriterNode())
    graph.add_node("query_analyzer", query_analyzer_node())
    graph.add_node("retriever", internal_retriever_node())
    graph.add_node("reranker", reranker_node())
    graph.add_node("web_fallback", web_search_fallback_node())
    graph.add_node("admin_agent", AdminAgentNode(admin_app=admin_app))
    graph.add_node("tool_executor", ToolExecutorNode())
    graph.add_node("chat_fallback", ChatFallbackNode())
    graph.add_node("general_knowledge", GeneralKnowledgeNode())
    graph.add_node("synthesizer", synthesizer_node())
    graph.add_node("validator", ValidatorNode())
    return graph


def _wire_edges(graph: StateGraph) -> StateGraph:
    """الأسلاك الحتمية + الحافات الشرطية الثلاث — مطابقة حرفية للأصل (D-262)."""
    graph.add_conditional_edges(
        "supervisor",
        route_intent,
        {
            "educational": "query_rewriter",
            "admin": "admin_agent",
            "tool": "tool_executor",
            "chat": "chat_fallback",
            "general_knowledge": "general_knowledge",
        },
    )

    graph.add_edge("query_rewriter", "query_analyzer")
    graph.add_edge("query_analyzer", "retriever")
    graph.add_edge("retriever", "reranker")
    graph.add_conditional_edges(
        "reranker",
        check_results,
        {
            "found": "synthesizer",
            "web_fallback": "web_fallback",
            "general_knowledge": "general_knowledge",
        },
    )

    graph.add_edge("web_fallback", "synthesizer")
    graph.add_edge("admin_agent", "validator")
    graph.add_edge(
        "tool_executor", "validator"
    )  # tool_executor -> validator directly, bypassing synthesizer to not break admin outputs
    graph.add_edge("chat_fallback", "validator")
    graph.add_edge("synthesizer", "validator")
    # DEADLOCK FIX: general_knowledge had no outgoing edge — a silent dead-end
    # bypassing the quality gate. Wire it into the validator so every leaf
    # exits through the single termination path.
    graph.add_edge("general_knowledge", "validator")

    graph.add_conditional_edges("validator", check_quality, {"pass": END, "fail": "supervisor"})

    graph.set_entry_point("supervisor")
    return graph


def _get_checkpointer():
    """يجيب عن checkpointer الـPostgres العام عند توفره — مطابقة للأصل (D-262)."""
    from microservices.orchestrator_service.src.core.database import get_checkpointer

    return get_checkpointer()


def build_graph(admin_app=None) -> StateGraph:
    """تسجيل العقد والأسلاك على رسمٍ جديد — بدون compile (D-262)."""
    _configure_dspy()
    graph = StateGraph(AgentState)
    _register_nodes(graph, admin_app=admin_app)
    _wire_edges(graph)
    return graph


def compile_graph(graph: StateGraph):
    """تجميع بلا checkpointer صريح — سلسلة الإقلاع الافتراضية نفسها (D-262)."""
    db_checkpointer = _get_checkpointer()
    if db_checkpointer:
        logger.info("[CHECKPOINTER] LangGraph compiled with Postgres checkpointer.")
        return graph.compile(checkpointer=db_checkpointer)

    logger.warning(
        "[CHECKPOINTER] LangGraph compiled without checkpointer; state continuity relies on injected history."
    )
    return graph.compile()


def compile_with_checkpointer(graph: StateGraph, checkpointer):
    """تجميع بـcheckpointerٍ صريحٍ (السلوك الأصلي: checkpointer مقدَّم) — D-262."""
    logger.info("[CHECKPOINTER] LangGraph compiled with provided checkpointer.")
    return graph.compile(checkpointer=checkpointer)
