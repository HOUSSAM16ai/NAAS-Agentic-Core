import logging

from langgraph.graph import END, StateGraph

from .dspy_compat import dspy  # noqa: F401 — re-export (graph.main.dspy patchable)
from .nodes import (  # noqa: F401 — D-173 Stage 2c re-export (D-168 late-binding)
    ChatFallbackNode,
    ChatFallbackSignature,
    IntentClassifier,
    QueryRewriterNode,
    QueryRewriterSignature,
    SupervisorNode,
    ToolExecutorNode,
    ValidatorNode,
    _configure_dspy,
)
from .state import (  # noqa: F401 — D-173 Stage 2c re-export
    ADMIN_METRIC_TRIGGERS,
    ADMIN_PATTERNS,
    ARABIC_ANAPHORA,
    ARABIC_PRONOUN_SUFFIXES,
    CHAT_INTENT_TRIGGERS,
    ELLIPTICAL_STARTERS,
    ELLIPTICAL_TERMS,
    ENGLISH_ANAPHORA,
    SHORT_QUERY_THRESHOLD,
    AgentState,
    _contains_anaphora_indicator,
    _contains_compound_indicator,
    _extract_recent_entity_anchor,
    _looks_elliptical_followup,
    _resolve_query_from_history,
    _rewrite_with_entity_anchor,
    _tokenize_query,
    build_conversation_context,
    emergency_intent_guard,
    format_conversation_history,
    get_message_content,
    get_message_role,
)

logger = logging.getLogger(__name__)


def _load_search_nodes() -> tuple[type, type, type, type, type]:
    """يحمّل عقد البحث عند توفر التبعيات ويعيد بدائل آمنة عند غيابها."""
    try:
        from .search import (
            InternalRetrieverNode,
            QueryAnalyzerNode,
            RerankerNode,
            SynthesizerNode,
            WebSearchFallbackNode,
        )

        return (
            QueryAnalyzerNode,
            InternalRetrieverNode,
            RerankerNode,
            WebSearchFallbackNode,
            SynthesizerNode,
        )
    except Exception:

        class _PassthroughNode:
            def __call__(self, state: dict) -> dict:
                return state

        return (
            _PassthroughNode,
            _PassthroughNode,
            _PassthroughNode,
            _PassthroughNode,
            _PassthroughNode,
        )


def route_intent(state: AgentState) -> str:
    import logging

    logger = logging.getLogger("graph")
    intent = state.get("intent", "educational")

    if intent == "search":
        intent = "educational"

    routing_map = {
        "educational": "query_rewriter",
        "admin": "admin_agent",
        "tool": "tool_executor",
        "chat": "chat_fallback",
        "general_knowledge": "general_knowledge",
    }
    # DEADLOCK FIX: guarantee a valid branch. Returning a raw intent absent
    # from the conditional-edge map raises a LangGraph "unknown branch" error;
    # clamp unexpected intents to a deterministic default exit.
    if intent not in routing_map:
        intent = "educational"
    logger.info(f"SUPERVISOR_NODE → routing to → {routing_map[intent]}")
    return intent


def check_results(state: AgentState) -> str:
    docs = state.get("reranked_docs", [])
    if len(docs) > 0:
        return "found"
    intent = state.get("intent", "")
    if intent == "educational":
        return "web_fallback"
    return "general_knowledge"


def check_quality(state: AgentState) -> str:
    final_response = state.get("final_response")
    if not final_response:
        return "fail"

    if isinstance(final_response, str):
        response_lower = final_response.lower()
        failure_phrases = ["لم أفهم", "يرجى التوضيح", "لا أستطيع"]
        if (
            any(phrase in response_lower for phrase in failure_phrases)
            or not response_lower.strip()
        ):
            return "fail"

    return "pass"


def create_unified_graph(admin_app=None, checkpointer=None):
    _configure_dspy()
    graph = StateGraph(AgentState)

    (
        query_analyzer_node,
        internal_retriever_node,
        reranker_node,
        web_search_fallback_node,
        synthesizer_node,
    ) = _load_search_nodes()

    from .admin import AdminAgentNode
    from .general_knowledge import GeneralKnowledgeNode

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

    if checkpointer:
        logger.info("[CHECKPOINTER] LangGraph compiled with provided checkpointer.")
        return graph.compile(checkpointer=checkpointer)

    # Use global postgres checkpointer if available, otherwise compile without it
    from microservices.orchestrator_service.src.core.database import get_checkpointer

    db_checkpointer = get_checkpointer()
    if db_checkpointer:
        logger.info("[CHECKPOINTER] LangGraph compiled with Postgres checkpointer.")
        return graph.compile(checkpointer=db_checkpointer)

    logger.warning(
        "[CHECKPOINTER] LangGraph compiled without checkpointer; state continuity relies on injected history."
    )
    return graph.compile()
