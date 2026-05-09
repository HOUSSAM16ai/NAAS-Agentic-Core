"""
Local LangGraph Chat Engine — CogniForge
-----------------------------------------
رسم بياني مدمج يعمل مباشرة داخل FastAPI بدون microservices.
يستخدم MemorySaver لاستمرارية السياق عبر رسائل نفس المحادثة.

التدفق:
  supervisor (تصنيف النية) → chat_node (توليد الرد) → END

thread_id = conversation_id  →  كل محادثة لها ذاكرة مستقلة.
"""

from __future__ import annotations

import contextvars
import logging
import re
import time
from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

logger = logging.getLogger("cogniforge.local_graph")

# Carries the parent trace context across async LangGraph node calls
_graph_trace_context: contextvars.ContextVar = contextvars.ContextVar(
    "graph_trace_context", default=None
)

# ─── Intent patterns ──────────────────────────────────────────────────────────

_EDUCATIONAL_PATTERNS = [
    r"(تمرين|مسألة|شرح|درس|مادة|كيفية حل|باكالوريا|بكالوريا|bac)",
    r"(فيزياء|رياضيات|كيمياء|تاريخ|جغرافيا|أدب|فلسفة|علوم|إحصاء|جبر)",
    r"(exercise|problem|solve|lesson|physics|math|chemistry|history|geography)",
    r"(حل|شرح لي|وضح لي|علمني|أريد أن أفهم|كيف أحل|ما هو الحل)",
]

_GREETING_PATTERNS = [
    r"^(السلام|مرحبا|أهلا|هلا|hello|hi\b|hey|salam|بونجور)[\s\W]*$",
    r"^(كيف حالك|ما أخبارك|how are you|كيف الأحوال)[\s\W]*$",
    r"^(شكرا|شكراً|merci|thank you|thanks)[\s\W]*$",
    r"^(مع السلامة|وداعاً|bye|goodbye|au revoir)[\s\W]*$",
]

_SYSTEM_PROMPTS = {
    "educational": (
        "أنت مساعد تعليمي متخصص للطلاب الجزائريين. "
        "مهمتك مساعدة الطالب في المواد الدراسية: رياضيات، فيزياء، كيمياء، تاريخ، جغرافيا، لغات. "
        "أجب بالعربية الفصحى الواضحة. استخدم الخطوات المرقمة والشرح التفصيلي. "
        "اعتمد على سياق المحادثة السابقة إذا كان الطالب يسأل سؤالاً متعلقاً بما سبق."
    ),
    "general": (
        "أنت مساعد ذكي واسع المعرفة، متخصص في خدمة الطلاب الجزائريين. "
        "أجب بدقة على سؤال المستخدم مع الاستناد إلى سياق المحادثة السابقة "
        "عند وجود ضمائر أو إشارات مرجعية. "
        "لا تُشر إلى تفاصيل داخلية أو بنية النظام."
    ),
    "chat": ("أنت مساعد ودود للطلاب الجزائريين. رد بشكل طبيعي ومختصر باللغة العربية."),
}


# ─── State ────────────────────────────────────────────────────────────────────


class LocalChatState(TypedDict):
    question: str
    intent: str
    history_messages: list[dict]
    final_response: str


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _classify_intent(question: str) -> str:
    q = question.strip()
    for pattern in _GREETING_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return "chat"
    for pattern in _EDUCATIONAL_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE | re.UNICODE):
            return "educational"
    return "general"


def _format_history(history_messages: list[dict], max_turns: int = 20) -> str:
    lines: list[str] = []
    for msg in history_messages[-max_turns:]:
        role = str(msg.get("role", "")).strip()
        content = str(msg.get("content", "")).replace("\x00", "").strip()
        if not content or role not in {"user", "assistant"}:
            continue
        label = "الطالب" if role == "user" else "المساعد"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


# ─── Nodes ────────────────────────────────────────────────────────────────────


async def _supervisor_node(state: LocalChatState) -> dict:
    t0 = time.perf_counter()
    intent = _classify_intent(state["question"])
    logger.info(
        "local_graph.supervisor intent=%s question=%.60s",
        intent,
        state["question"],
    )

    import contextlib

    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        parent = _graph_trace_context.get()
        ctx = obs.start_trace(
            "langgraph.supervisor",
            parent_context=parent,
            tags={"intent": intent, "node": "supervisor"},
        )
        duration_s = time.perf_counter() - t0
        obs.end_span(
            ctx.span_id,
            status="OK",
            metrics={"duration_ms": duration_s * 1000},
        )
        # ── LangGraph Prometheus metrics (feeds 20-langgraph.json dashboard) ──
        # cogniforge_langgraph_intent_total — intent distribution panel
        obs.increment_counter(
            "langgraph.intent.total",
            labels={"intent": intent, "graph": "local"},
        )
        # cogniforge_langgraph_node_count_total — node throughput panel
        obs.increment_counter(
            "langgraph.node.count.total",
            labels={"node": "supervisor", "graph": "local"},
        )
        # cogniforge_langgraph_node_duration_seconds — p95 latency panel
        obs.record_metric(
            "langgraph.node.duration_seconds",
            value=duration_s,
            labels={"node": "supervisor", "graph": "local"},
        )

    return {"intent": intent}


async def _chat_node(state: LocalChatState) -> dict:
    from app.core.ai_gateway import get_ai_client

    ai_client = get_ai_client()
    intent = state.get("intent", "general")
    question = state["question"].replace("\x00", "").strip()
    history = state.get("history_messages", [])

    system_prompt = _SYSTEM_PROMPTS.get(intent, _SYSTEM_PROMPTS["general"])

    history_text = _format_history(history)
    if history_text:
        user_message = f"سياق المحادثة السابقة:\n{history_text}\n\nالسؤال الحالي: {question}"
    else:
        user_message = question

    import contextlib

    t0 = time.perf_counter()
    obs = None
    span_ctx = None
    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        parent = _graph_trace_context.get()
        span_ctx = obs.start_trace(
            "langgraph.chat_node",
            parent_context=parent,
            tags={"intent": intent, "node": "chat", "history_turns": len(history)},
        )

    try:
        response = await ai_client.send_message(system_prompt, user_message)
        clean = response.replace("\x00", "").strip()
        logger.info(
            "local_graph.chat_node OK intent=%s chars=%d",
            intent,
            len(clean),
        )
        duration_s = time.perf_counter() - t0
        if obs is not None and span_ctx is not None:
            with contextlib.suppress(Exception):
                obs.end_span(
                    span_ctx.span_id,
                    status="OK",
                    metrics={
                        "duration_ms": duration_s * 1000,
                        "response_chars": float(len(clean)),
                    },
                )
                # ── LangGraph Prometheus metrics (feeds 20-langgraph.json) ──
                obs.increment_counter(
                    "langgraph.node.count.total",
                    labels={"node": "chat", "graph": "local"},
                )
                obs.record_metric(
                    "langgraph.node.duration_seconds",
                    value=duration_s,
                    labels={"node": "chat", "graph": "local"},
                )
        return {"final_response": clean}
    except Exception:
        logger.warning("local_graph.chat_node_failed", exc_info=True)
        if obs is not None and span_ctx is not None:
            with contextlib.suppress(Exception):
                obs.end_span(
                    span_ctx.span_id,
                    status="ERROR",
                    metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                )
                obs.increment_counter(
                    "langgraph.node.count.total",
                    labels={"node": "chat", "graph": "local", "status": "error"},
                )
        return {"final_response": ""}


# ─── Graph singleton ──────────────────────────────────────────────────────────

_memory_saver: MemorySaver = MemorySaver()
_compiled_graph = None


def _build_graph():
    workflow: StateGraph = StateGraph(LocalChatState)
    workflow.add_node("supervisor", _supervisor_node)
    workflow.add_node("chat", _chat_node)
    workflow.set_entry_point("supervisor")
    workflow.add_edge("supervisor", "chat")
    workflow.add_edge("chat", END)
    compiled = workflow.compile(checkpointer=_memory_saver)
    logger.info("local_langgraph_compiled_with_memory_saver")
    return compiled


def get_local_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ─── Public interface ─────────────────────────────────────────────────────────


async def run_local_graph(
    question: str,
    conversation_id: int | None,
    history_messages: list[dict] | None = None,
    trace_context=None,
) -> str | None:
    """
    تشغيل الرسم البياني المحلي وإعادة الرد النهائي كنص، أو None عند الفشل.
    thread_id = conversation_id → ذاكرة مستقلة لكل محادثة عبر MemorySaver.
    """
    graph = get_local_graph()
    thread_id = str(conversation_id) if conversation_id is not None else "anon"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: LocalChatState = {
        "question": question,
        "intent": "general",
        "history_messages": history_messages or [],
        "final_response": "",
    }

    # Create root span and expose it to child nodes via ContextVar
    root_span_ctx = None
    token = None
    t0 = time.perf_counter()
    try:
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        root_span_ctx = obs.start_trace(
            "langgraph.run",
            parent_context=trace_context,
            tags={"thread_id": thread_id, "question_len": len(question)},
        )
        token = _graph_trace_context.set(root_span_ctx)
    except Exception:
        pass

    try:
        result = await graph.ainvoke(initial_state, config=config)
        response = (result.get("final_response") or "").strip()
        if response:
            logger.info(
                "local_graph.run_success thread_id=%s chars=%d",
                thread_id,
                len(response),
            )
            if root_span_ctx:
                try:
                    obs.end_span(
                        root_span_ctx.span_id,
                        status="OK",
                        metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                    )
                except Exception:
                    pass
            return response
        logger.warning("local_graph.run_empty_response thread_id=%s", thread_id)
        if root_span_ctx:
            try:
                obs.end_span(
                    root_span_ctx.span_id,
                    status="OK",
                    metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                )
            except Exception:
                pass
    except Exception:
        logger.warning("local_graph.run_failed thread_id=%s", thread_id, exc_info=True)
        if root_span_ctx:
            try:
                obs.end_span(root_span_ctx.span_id, status="ERROR")
            except Exception:
                pass
    finally:
        if token is not None:
            try:
                _graph_trace_context.reset(token)
            except Exception:
                pass

    return None
