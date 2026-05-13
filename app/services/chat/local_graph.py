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

import contextlib
import contextvars
import logging
import re
import time
from collections.abc import AsyncGenerator
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
        "أنت مساعد تعليمي متخصص للطلاب الجزائريين المتقدمين لامتحان البكالوريا.\n\n"
        "## مهمتك الأساسية\n"
        "مساعدة الطالب في المواد الدراسية: رياضيات، فيزياء، كيمياء، تاريخ، جغرافيا، لغات.\n\n"
        "## قواعد الرموز الرياضية (إلزامية)\n"
        "- استخدم LaTeX دائماً للرموز الرياضية:\n"
        "  - للمعادلات المستقلة: $$...$$\n"
        "  - للرموز المضمّنة في النص: \\\\(...\\\\)\n"
        "- مثال صحيح: $$\\\\lim_{x \\\\to +\\\\infty} f(x) = -\\\\infty$$\n"
        "- مثال صحيح: الدالة \\\\(f(x) = -x + (x^2+3x+2)e^{-x}\\\\) معرَّفة على \\\\(\\\\mathbb{R}\\\\)\n\n"
        "## منهجية شرح الإجابة النموذجية\n"
        "عند شرح إجابة نموذجية لتمرين بكالوريا:\n"
        "1. اذكر المبدأ الرياضي المستخدم أولاً\n"
        "2. اشرح كل خطوة بالتفصيل مع الرموز الرياضية\n"
        "3. ضع النتيجة النهائية في صندوق: $$\\\\boxed{...}$$\n"
        "4. أضف التفسير الهندسي إذا طُلب\n\n"
        "## قاعدة 2016 الاستثنائية\n"
        "سنة 2016 هي السنة الوحيدة في تاريخ بكالوريا الجزائر بدورتين (الأولى والثانية).\n"
        "عند ذكر 2016، تحقق دائماً من الدورة المقصودة.\n\n"
        "## أسلوب الإجابة\n"
        "- أجب بالعربية الفصحى الواضحة\n"
        "- استخدم الخطوات المرقمة والشرح التفصيلي\n"
        "- اعتمد على سياق المحادثة السابقة\n"
        "- لا تختصر الشرح — الطالب يحتاج الفهم الكامل"
    ),
    "general": (
        "أنت مساعد ذكي واسع المعرفة، متخصص في خدمة الطلاب الجزائريين. "
        "أجب بدقة على سؤال المستخدم مع الاستناد إلى سياق المحادثة السابقة "
        "عند وجود ضمائر أو إشارات مرجعية. "
        "استخدم LaTeX للرموز الرياضية: $$...$$ للمعادلات و \\\\(...\\\\) للرموز المضمّنة. "
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
                with contextlib.suppress(Exception):
                    obs.end_span(
                        root_span_ctx.span_id,
                        status="OK",
                        metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                    )
            return response
        logger.warning("local_graph.run_empty_response thread_id=%s", thread_id)
        if root_span_ctx:
            with contextlib.suppress(Exception):
                obs.end_span(
                    root_span_ctx.span_id,
                    status="OK",
                    metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                )
    except Exception:
        logger.warning("local_graph.run_failed thread_id=%s", thread_id, exc_info=True)
        if root_span_ctx:
            with contextlib.suppress(Exception):
                obs.end_span(root_span_ctx.span_id, status="ERROR")
    finally:
        if token is not None:
            with contextlib.suppress(Exception):
                _graph_trace_context.reset(token)

    return None


# ─── Streaming variant — D-047 (word-by-word typing effect) ──────────────────


async def run_local_graph_stream(
    question: str,
    conversation_id: int | None,
    history_messages: list[dict] | None = None,
    trace_context=None,
) -> AsyncGenerator[str, None]:
    """
    نسخة انسيابية من ``run_local_graph`` — تُصدِر القطع نصياً عبر AsyncGenerator
    لتمكين الـ assistant_delta كلمة بكلمة على WebSocket.

    لماذا تتجاوز LangGraph عند البث؟
        ``OpenRouterClient`` ليس ``BaseChatModel`` من LangChain، فلا تُولِّد
        ``astream_events`` أحداث ``on_chat_model_stream``. لذلك نُشغِّل
        ``_classify_intent`` يدوياً لاختيار الـ system prompt، ثم نتصل بـ
        ``OpenRouterClient.stream_chat`` مباشرة ونُصدِر كل قطعة محتوى فوراً.
        النتيجة: زمن أول-قطعة ~1s، تجربة typing ناعمة، صفر buffering.

    Yields:
        str: قطعة نص (token/فاصلة كلمات) — يضمها ``mergeAssistantContent`` في الواجهة.

    إذا فشل أي تيار في المسار → AsyncGenerator يفرغ بصمت
    (المسؤول الأعلى يطبّق fallback chain بعده).
    """
    from app.core.ai_gateway import get_ai_client

    sanitized = question.replace("\x00", "").strip()
    if not sanitized:
        return

    intent = _classify_intent(sanitized)
    system_prompt = _SYSTEM_PROMPTS.get(intent, _SYSTEM_PROMPTS["general"])
    history = history_messages or []
    history_text = _format_history(history)
    user_message = (
        f"سياق المحادثة السابقة:\n{history_text}\n\nالسؤال الحالي: {sanitized}"
        if history_text
        else sanitized
    )

    obs = None
    span_ctx = None
    t0 = time.perf_counter()
    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        span_ctx = obs.start_trace(
            "langgraph.run_stream",
            parent_context=trace_context,
            tags={
                "thread_id": str(conversation_id) if conversation_id is not None else "anon",
                "intent": intent,
                "question_len": len(sanitized),
            },
        )
        # نُسجِّل عَدّ النوايا للوحة 20-langgraph.json
        obs.increment_counter(
            "langgraph.intent.total",
            labels={"intent": intent, "graph": "local"},
        )

    ai_client = get_ai_client()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    chunk_count = 0
    total_chars = 0
    try:
        async for raw_chunk in ai_client.stream_chat(messages):
            # raw_chunk: OpenRouter SSE delta — نستخرج فقط محتوى المساعد
            try:
                choices = raw_chunk.get("choices") if isinstance(raw_chunk, dict) else None
                if not choices:
                    continue
                delta = choices[0].get("delta", {}) or {}
                content = delta.get("content")
                if not content or not isinstance(content, str):
                    continue
                clean = content.replace("\x00", "")
                if not clean:
                    continue
                chunk_count += 1
                total_chars += len(clean)
                yield clean
            except Exception:
                # قطعة واحدة سيئة لا تكسر التيار
                continue
    except Exception:
        logger.warning("local_graph.stream_failed intent=%s", intent, exc_info=True)
        if obs is not None and span_ctx is not None:
            with contextlib.suppress(Exception):
                obs.end_span(span_ctx.span_id, status="ERROR")
        return

    duration_s = time.perf_counter() - t0
    logger.info(
        "local_graph.stream_ok intent=%s chunks=%d chars=%d duration_s=%.3f",
        intent,
        chunk_count,
        total_chars,
        duration_s,
    )
    if obs is not None and span_ctx is not None:
        with contextlib.suppress(Exception):
            obs.end_span(
                span_ctx.span_id,
                status="OK",
                metrics={
                    "duration_ms": duration_s * 1000,
                    "chunks": float(chunk_count),
                    "chars": float(total_chars),
                },
            )
            # مقاييس انسيابية للوحة LangGraph
            obs.increment_counter(
                "langgraph.node.count.total",
                labels={"node": "chat_stream", "graph": "local"},
            )
            obs.record_metric(
                "langgraph.node.duration_seconds",
                value=duration_s,
                labels={"node": "chat_stream", "graph": "local"},
            )
            obs.increment_counter(
                "ws.chat.delta.total",
                labels={"path": "local_graph_stream"},
            )


# ─── شرح التمرين مع السياق الكامل — ISS-053 ─────────────────────────────────
#
# المشكلة: "اشرح تمرين الدوال العددية 2016" كان يذهب إلى LangGraph بدون محتوى
# التمرين → LLM يُهلوس تمريناً خاطئاً أو يقول "لا أملك التفاصيل".
#
# الحل: نجلب المحتوى الكامل (نص + إجابة نموذجية) من قاعدة المعرفة ونُمرِّره
# للـ LLM كـ context صريح مع تعليمات شرح الإجابة النموذجية خطوة بخطوة.
# ─────────────────────────────────────────────────────────────────────────────

_EXERCISE_EXPLANATION_SYSTEM_PROMPT = (
    "أنت مساعد تعليمي متخصص للطلاب الجزائريين المتقدمين لامتحان البكالوريا.\n\n"
    "## مهمتك\n"
    "لديك النص الكامل لتمرين بكالوريا مع إجابته النموذجية الرسمية.\n"
    "اشرح الإجابة النموذجية للطالب خطوة بخطوة بأسلوب تعليمي واضح.\n\n"
    "## منهجية الشرح الإلزامية\n"
    "لكل سؤال فرعي:\n"
    "1. **المبدأ الرياضي**: اذكر القانون أو المبدأ المستخدم\n"
    "2. **الخطوات التفصيلية**: اشرح كيف وصلنا إلى الإجابة النموذجية خطوة بخطوة\n"
    "3. **النتيجة النهائية**: ضعها في صندوق $$\\boxed{...}$$\n"
    "4. **التفسير الهندسي**: أضفه عند الطلب أو عند الأهمية\n\n"
    "## قواعد LaTeX الإلزامية\n"
    "- المعادلات المستقلة: $$...$$\n"
    "- الرموز المضمّنة في النص: \\(...\\)\n"
    "- النتائج النهائية: $$\\boxed{...}$$\n\n"
    "## قاعدة 2016 الاستثنائية\n"
    "سنة 2016 هي السنة الوحيدة في تاريخ بكالوريا الجزائر بدورتين (الأولى والثانية).\n"
    "هذا التمرين يخص الدورة الأولى حصراً.\n\n"
    "## أسلوب الإجابة\n"
    "- أجب بالعربية الفصحى الواضحة\n"
    "- استخدم الخطوات المرقمة والشرح التفصيلي\n"
    "- لا تختصر — الطالب يحتاج الفهم الكامل\n"
    "- اعتمد حصراً على الإجابة النموذجية المُقدَّمة، لا تخترع إجابات"
)


_MAX_EXERCISE_CONTEXT_CHARS = 6000
"""
الحد الأقصى لحجم context التمرين المُرسَل للـ LLM.

ISS-STREAM-005: النماذج المجانية على OpenRouter تتجمد مع context > 8000 حرف.
نقطع المحتوى عند 6000 حرف للحفاظ على استجابة سريعة مع الاحتفاظ بالإجابة النموذجية.
"""

_MAX_EXPLANATION_TOKENS = 1200
"""
الحد الأقصى للرموز المُولَّدة في شرح التمرين.

يمنع النماذج المجانية من توليد ردود طويلة جداً تُسبِّب timeout.
1200 token ≈ 900 كلمة عربية — كافٍ لشرح مفصل لسؤال واحد.
"""


async def run_local_graph_with_exercise_context(
    question: str,
    exercise_full_content: str,
    conversation_id: int | None,
    history_messages: list[dict] | None = None,
    trace_context=None,
) -> AsyncGenerator[str, None]:
    """
    يشرح تمرين بكالوريا محدد بالاعتماد على محتواه الكامل (نص + إجابة نموذجية).

    يحل ISS-053: بدلاً من إرسال السؤال للـ LLM بدون سياق (→ هلوسة)، نُمرِّر
    المحتوى الكامل للتمرين كـ context صريح مع تعليمات شرح الإجابة النموذجية.

    ISS-STREAM-005: يُقلِّص context إلى _MAX_EXERCISE_CONTEXT_CHARS حرف
    ويُحدِّد max_tokens لمنع timeout مع النماذج المجانية.

    Args:
        question: سؤال الطالب (مثل "اشرح الجزء الثاني من التمرين")
        exercise_full_content: نص التمرين + الإجابة النموذجية الكاملة
        conversation_id: معرف المحادثة للذاكرة
        history_messages: سياق المحادثة السابقة
        trace_context: سياق التتبع للـ observability

    Yields:
        str: قطع النص التتابعية (streaming)
    """
    from app.core.ai_gateway import get_ai_client

    sanitized_question = question.replace("\x00", "").strip()
    if not sanitized_question or not exercise_full_content:
        return

    history = history_messages or []
    history_text = _format_history(history)

    # ISS-STREAM-005: تقليص context لمنع timeout مع النماذج المجانية
    # نحتفظ بالجزء الأخير (الإجابة النموذجية) لأنه الأهم للشرح
    trimmed_content = exercise_full_content
    if len(exercise_full_content) > _MAX_EXERCISE_CONTEXT_CHARS:
        # نحتفظ بالنصف الأول (نص التمرين) + النصف الثاني (الإجابة النموذجية)
        half = _MAX_EXERCISE_CONTEXT_CHARS // 2
        trimmed_content = (
            exercise_full_content[:half]
            + "\n\n[... محتوى مختصر للأداء ...]\n\n"
            + exercise_full_content[-half:]
        )

    # بناء رسالة المستخدم مع السياق المُقلَّص للتمرين
    context_block = (
        f"## محتوى التمرين (نص + إجابة نموذجية رسمية)\n\n"
        f"{trimmed_content}\n\n"
        f"---\n\n"
    )

    if history_text:
        user_message = (
            f"{context_block}"
            f"## سياق المحادثة السابقة\n{history_text}\n\n"
            f"## طلب الطالب الحالي\n{sanitized_question}"
        )
    else:
        user_message = (
            f"{context_block}"
            f"## طلب الطالب\n{sanitized_question}"
        )

    obs = None
    span_ctx = None
    t0 = time.perf_counter()
    with contextlib.suppress(Exception):
        from app.telemetry.unified_observability import get_unified_observability

        obs = get_unified_observability()
        span_ctx = obs.start_trace(
            "langgraph.exercise_explanation_stream",
            parent_context=trace_context,
            tags={
                "thread_id": str(conversation_id) if conversation_id is not None else "anon",
                "intent": "exercise_explanation",
                "question_len": len(sanitized_question),
                "context_len": len(exercise_full_content),
            },
        )
        obs.increment_counter(
            "langgraph.intent.total",
            labels={"intent": "exercise_explanation", "graph": "local"},
        )

    ai_client = get_ai_client()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _EXERCISE_EXPLANATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    chunk_count = 0
    total_chars = 0
    try:
        # ISS-STREAM-005: max_tokens يمنع timeout مع النماذج المجانية
        async for raw_chunk in ai_client.stream_chat(messages, max_tokens=_MAX_EXPLANATION_TOKENS):
            try:
                choices = raw_chunk.get("choices") if isinstance(raw_chunk, dict) else None
                if not choices:
                    continue
                delta = choices[0].get("delta", {}) or {}
                content = delta.get("content")
                if not content or not isinstance(content, str):
                    continue
                clean = content.replace("\x00", "")
                if not clean:
                    continue
                chunk_count += 1
                total_chars += len(clean)
                yield clean
            except Exception:
                continue
    except Exception:
        logger.warning("local_graph.exercise_explanation_stream_failed", exc_info=True)
        if obs is not None and span_ctx is not None:
            with contextlib.suppress(Exception):
                obs.end_span(span_ctx.span_id, status="ERROR")
        return

    duration_s = time.perf_counter() - t0
    logger.info(
        "local_graph.exercise_explanation_ok chunks=%d chars=%d duration_s=%.3f",
        chunk_count,
        total_chars,
        duration_s,
    )
    if obs is not None and span_ctx is not None:
        with contextlib.suppress(Exception):
            obs.end_span(
                span_ctx.span_id,
                status="OK",
                metrics={
                    "duration_ms": duration_s * 1000,
                    "chunks": float(chunk_count),
                    "chars": float(total_chars),
                },
            )
            obs.increment_counter(
                "langgraph.node.count.total",
                labels={"node": "exercise_explanation_stream", "graph": "local"},
            )
            obs.record_metric(
                "langgraph.node.duration_seconds",
                value=duration_s,
                labels={"node": "exercise_explanation_stream", "graph": "local"},
            )

