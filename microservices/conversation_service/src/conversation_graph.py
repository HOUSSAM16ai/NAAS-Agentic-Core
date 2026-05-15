"""
LangGraph StateGraph لـ conversation-service — الخطوة 12.

البنية:
  START → intent_node → response_node → END

الحالة (ConversationState):
  - question: سؤال الطالب
  - intent: educational | general | chat
  - history: سجل المحادثة
  - response: الإجابة النهائية
  - thread_id: معرف الجلسة (للـ checkpointing)
  - correlation_id: للتتبع الموزع

قانون الـ Skill:
  - هذا الـ graph مستقل تماماً — لا يستورد من microservice آخر
  - كل node يُسجِّل مقاييسه في Prometheus
  - Fallback mode إلزامي عند غياب LLM
  - Timeout guard على كل ainvoke()
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from microservices.conversation_service.prom_metrics import (
    record_graph_error,
    record_graph_invocation,
)

logger = logging.getLogger(__name__)

# ── ثوابت ─────────────────────────────────────────────────────────────────────
_NODE_TIMEOUT_SECONDS = 30.0
_INTENT_PATTERNS: dict[str, list[str]] = {
    "educational": [
        "اشرح",
        "حل",
        "تمرين",
        "مسألة",
        "قانون",
        "نظرية",
        "درس",
        "رياضيات",
        "فيزياء",
        "كيمياء",
        "بكالوريا",
        "باك",
        "expliquer",
        "exercice",
        "problème",
        "loi",
        "théorème",
    ],
    "chat": [
        "مرحبا",
        "أهلا",
        "كيف حالك",
        "شكرا",
        "وداعا",
        "bonjour",
        "merci",
        "salut",
        "hello",
        "hi",
    ],
}


# ── State TypedDict ────────────────────────────────────────────────────────────


class ConversationState(TypedDict):
    """حالة المحادثة — تمر عبر جميع nodes."""

    question: str
    intent: str  # educational | general | chat
    history: list[dict[str, str]]  # [{role, content}, ...]
    response: str
    thread_id: str
    correlation_id: str
    error: str | None


# ── دوال مساعدة ───────────────────────────────────────────────────────────────


def _classify_intent(question: str) -> str:
    """يُصنِّف نية السؤال بدون LLM — deterministic."""
    q_lower = question.lower()
    for intent, patterns in _INTENT_PATTERNS.items():
        if any(p in q_lower for p in patterns):
            return intent
    return "general"


def _build_fallback_response(question: str, intent: str) -> str:
    """يبني إجابة fallback عند غياب LLM."""
    if intent == "educational":
        return f"سؤالك التعليمي: «{question}» — سيتم معالجته عبر Skills Pipeline عند توفر الاتصال."
    if intent == "chat":
        return "مرحباً! كيف يمكنني مساعدتك اليوم؟"
    return f"تم استلام سؤالك: «{question}»"


async def _call_llm_if_available(question: str, intent: str, history: list[dict[str, str]]) -> str:
    """يستدعي LLM عبر OpenRouter إذا كان المفتاح متاحاً، وإلا يُعيد fallback."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return _build_fallback_response(question, intent)

    try:
        import httpx

        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "أنت مساعد تعليمي ذكي لطلاب البكالوريا الجزائريين. "
                    "تتحدث العربية والفرنسية والدارجة. "
                    "أجب بشكل مختصر ومفيد."
                ),
            }
        ]
        for h in history[-6:]:  # آخر 6 رسائل فقط
            messages.append(h)
        messages.append({"role": "user", "content": question})

        async with httpx.AsyncClient(timeout=25.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    # ISS-068: nemotron-reasoning — أسرع نموذج مجاني مع reasoning tokens
                    "model": os.environ.get("CONVERSATION_LLM_MODEL", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
                    "messages": messages,
                    "max_tokens": 512,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return str(data["choices"][0]["message"]["content"])
    except Exception as exc:
        logger.warning("LLM call failed: %s — using fallback", exc)
        return _build_fallback_response(question, intent)


# ── Graph Nodes ────────────────────────────────────────────────────────────────


async def intent_node(state: ConversationState) -> ConversationState:
    """
    يُصنِّف نية السؤال.

    Input:  state.question
    Output: state.intent
    Metrics: cogniforge_conversation_graph_invocations_total{node="intent"}
    """
    t0 = time.perf_counter()
    try:
        intent = _classify_intent(state["question"])
        duration = time.perf_counter() - t0
        record_graph_invocation("intent", "success", duration)
        return {**state, "intent": intent}
    except Exception as exc:
        duration = time.perf_counter() - t0
        record_graph_invocation("intent", "error", duration)
        record_graph_error("state_error")
        logger.error("intent_node error: %s", exc)
        return {**state, "intent": "general", "error": str(exc)}


async def response_node(state: ConversationState) -> ConversationState:
    """
    يُولِّد الإجابة — LLM حقيقي أو fallback.

    Input:  state.question, state.intent, state.history
    Output: state.response
    Metrics: cogniforge_conversation_graph_invocations_total{node="response"}
    """
    t0 = time.perf_counter()
    try:
        response = await asyncio.wait_for(
            _call_llm_if_available(
                state["question"],
                state["intent"],
                state.get("history", []),
            ),
            timeout=_NODE_TIMEOUT_SECONDS,
        )
        duration = time.perf_counter() - t0
        record_graph_invocation("response", "success", duration)
        return {**state, "response": response}
    except TimeoutError:
        duration = time.perf_counter() - t0
        record_graph_invocation("response", "timeout", duration)
        record_graph_error("timeout")
        fallback = _build_fallback_response(state["question"], state.get("intent", "general"))
        return {**state, "response": fallback, "error": "timeout"}
    except Exception as exc:
        duration = time.perf_counter() - t0
        record_graph_invocation("response", "error", duration)
        record_graph_error("llm_error")
        logger.error("response_node error: %s", exc)
        fallback = _build_fallback_response(state["question"], state.get("intent", "general"))
        return {**state, "response": fallback, "error": str(exc)}


# ── Graph Builder ──────────────────────────────────────────────────────────────


def build_conversation_graph() -> StateGraph:
    """
    يبني StateGraph للمحادثة.

    Topology: START → intent_node → response_node → END
    """
    builder = StateGraph(ConversationState)
    builder.add_node("intent_node", intent_node)
    builder.add_node("response_node", response_node)
    builder.add_edge(START, "intent_node")
    builder.add_edge("intent_node", "response_node")
    builder.add_edge("response_node", END)
    return builder.compile()


# ── Singleton ──────────────────────────────────────────────────────────────────

# Singleton: مُهيَّأ مرة واحدة عند الإقلاع، مُحقَن عبر get_conversation_graph()
_conversation_graph: object | None = None


def get_conversation_graph() -> object:
    """يُعيد الـ graph المُهيَّأ — lazy singleton."""
    global _conversation_graph
    if _conversation_graph is None:
        _conversation_graph = build_conversation_graph()
    return _conversation_graph


async def invoke_graph(
    question: str,
    thread_id: str,
    correlation_id: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """
    يستدعي الـ graph ويُعيد النتيجة.

    يُستخدم من main.py فقط — abstraction barrier.
    """
    graph = get_conversation_graph()
    initial_state: ConversationState = {
        "question": question,
        "intent": "general",
        "history": history or [],
        "response": "",
        "thread_id": thread_id,
        "correlation_id": correlation_id,
        "error": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = await graph.ainvoke(initial_state, config=config)
    return {
        "response": result.get("response", ""),
        "intent": result.get("intent", "general"),
        "error": result.get("error"),
    }
