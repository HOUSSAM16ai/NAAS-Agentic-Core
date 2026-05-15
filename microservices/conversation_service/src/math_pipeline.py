"""
LangGraph Math Pipeline — CogniForge BAC Tutor.

البنية (2 nodes — مُبسَّطة لمنع meta-text):
  START → classify_node (deterministic) → solve_node (LLM واحد) → END

درس مُكتسَب (ISS-070 live 2026-05-15):
  3 nodes × LLM = meta-text كارثي.
  الحل: node واحد للـ LLM مع prompt مباشر بدون هيكل معقد.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

_NODE_TIMEOUT = 40.0
_DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
_FALLBACK_MODEL = "openai/gpt-oss-20b:free"

_MATH_TYPES: dict[str, list[str]] = {
    "differential_eq": ["معادلة تفاضلية", "équation différentielle", "y''", "y' +", "y' ="],
    "derivative":      ["مشتق", "اشتقاق", "مشتقة", "f'(", "dérivée", "dériver"],
    "integral":        ["تكامل", "∫", "intégrale", "intégrer", "primitive"],
    "limit":           ["نهاية الدالة", "نهاية عند", "lim(", "lim ", "limite", "∞", "لانهاية"],
    "matrix":          ["مصفوفة", "matrice", "déterminant", "عكسية المصفوفة", "محدد المصفوفة"],
    "sequence":        ["متتالية", "suite", "تقاربية", "divergente", "حدود المتتالية"],
    "equation":        ["معادلة", "حل المعادلة", "equation", "résoudre", "جذر", "حلول"],
    "probability":     ["احتمال", "probabilité", "عشوائي", "حادثة", "variable aléatoire"],
    "complex":         ["مركب", "complexe", "module", "argument", "conjugué"],
    "geometry":        ["هندسة", "géométrie", "مستقيم", "مستوى", "متجه", "vecteur"],
    "function_study":  ["ادرس", "دراسة الدالة", "tableau de variation", "تغيرات الدالة", "إشارة الدالة"],
}

_TYPE_LABELS: dict[str, str] = {
    "derivative":      "📐 مسألة اشتقاق",
    "integral":        "∫ مسألة تكامل",
    "limit":           "∞ مسألة نهايات",
    "equation":        "⚖️ مسألة معادلات",
    "function_study":  "📊 دراسة دالة",
    "probability":     "🎲 مسألة احتمالات",
    "complex":         "🔢 أعداد مركبة",
    "matrix":          "🔲 مصفوفات",
    "geometry":        "📐 هندسة تحليلية",
    "sequence":        "🔢 متتاليات",
    "differential_eq": "📈 معادلة تفاضلية",
}

_MATH_HINTS: dict[str, str] = {
    "derivative":      "استخدم قاعدة الضرب (uv)' = u'v + uv' وقاعدة السلسلة",
    "integral":        "فكِّر في التكامل بالتجزئة أو التعويض",
    "limit":           "جرِّب التحليل أو قاعدة لوبيتال أو المكافئات المقاربية",
    "equation":        "عزِّل المجهول أو حلِّل إلى عوامل",
    "function_study":  "ابدأ بالمجال ثم المشتق ثم جدول التغيرات",
    "probability":     "حدِّد الفضاء الاحتمالي ثم طبِّق القانون المناسب",
    "complex":         "حوِّل بين الشكل الجبري والمثلثي والأسي",
    "matrix":          "احسب المحدد أولاً",
    "geometry":        "استخدم المتجهات والمعادلات الديكارتية",
    "sequence":        "حدِّد نوع المتتالية ثم طبِّق القانون",
    "differential_eq": "ابحث عن الحل المتجانس أولاً ثم الحل الخاص",
    "general_math":    "",
}

# System prompt — قصير + مباشر = لا meta-text
_MATH_SYSTEM = (
    "أنت أستاذ رياضيات للبكالوريا الجزائرية. "
    "اكتب بالعربية فقط. "
    "استخدم LaTeX: $$...$$ للمعادلات، \\(...\\) للرموز المضمّنة. "
    "ضع النتيجة النهائية في $$\\boxed{...}$$. "
    "ابدأ بشرح لماذا نستخدم هذه الطريقة، ثم اشرح كل خطوة بتفصيل."
)

_META_MARKERS = [
    "We need to", "Must output", "produce analysis", "I need to",
    "Let me", "I will", "I'll", "I should", "I must",
]


def _classify_math_type(question: str) -> str:
    q_lower = question.lower()
    for math_type, patterns in _MATH_TYPES.items():
        if any(p in q_lower for p in patterns):
            return math_type
    return "general_math"


def _get_math_context(math_type: str) -> str:
    return _MATH_HINTS.get(math_type, "")


class MathPipelineState(TypedDict):
    question:       str
    math_type:      str
    math_hint:      str
    solution:       str
    final_response: str
    history:        list[dict[str, str]]
    thread_id:      str
    error:          str | None


async def _call_openrouter(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1500,
    model: str | None = None,
) -> str:
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return ""

    chosen = model or os.environ.get("MATH_PIPELINE_MODEL", _DEFAULT_MODEL)
    models_to_try = [chosen, _FALLBACK_MODEL]

    try:
        import httpx
        for m in models_to_try:
            try:
                async with httpx.AsyncClient(timeout=35.0) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://cogniforge.dz",
                            "X-Title": "CogniForge Math Pipeline",
                        },
                        json={
                            "model": m,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user",   "content": user_prompt},
                            ],
                            "max_tokens": max_tokens,
                            "temperature": 0.3,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        # ISS-069: reasoning models put answer in "reasoning" not "content"
                        content = msg.get("content") or msg.get("reasoning") or ""
                        if content and content.strip():
                            return content.strip()
                    logger.warning("math_pipeline: empty content from %s", m)
            except Exception as e:
                logger.warning("math_pipeline: model %s failed: %s", m, e)
                continue
    except ImportError:
        logger.error("math_pipeline: httpx not available")
    return ""


async def classify_node(state: MathPipelineState) -> MathPipelineState:
    """Node 1 — Deterministic. لا LLM → لا meta-text ممكن."""
    math_type = _classify_math_type(state["question"])
    math_hint = _get_math_context(math_type)
    return {**state, "math_type": math_type, "math_hint": math_hint}


async def solve_node(state: MathPipelineState) -> MathPipelineState:
    """Node 2 — LLM واحد، prompt مباشر، الحل الكامل."""
    t0 = time.perf_counter()
    question  = state["question"]
    math_type = state["math_type"]
    math_hint = state["math_hint"]
    label     = _TYPE_LABELS.get(math_type, "📚 رياضيات")

    # سياق المحادثة السابقة
    history_ctx = ""
    if state.get("history"):
        recent = [h for h in state["history"][-4:] if h.get("content")]
        if recent:
            lines = "\n".join(f"{h['role']}: {h['content']}" for h in recent)
            history_ctx = f"\n\nسياق المحادثة:\n{lines}"

    hint_line = f"\nتلميح: {math_hint}" if math_hint else ""
    user_prompt = f"{question}{hint_line}{history_ctx}"

    try:
        solution = await asyncio.wait_for(
            _call_openrouter(_MATH_SYSTEM, user_prompt, max_tokens=1500),
            timeout=_NODE_TIMEOUT,
        )

        if not solution or len(solution.strip()) < 20:
            solution = _build_fallback_solution(question, math_type)
        elif any(m in solution for m in _META_MARKERS):
            # meta-text مكتشف — أعد المحاولة بـ prompt أبسط
            logger.warning("math_pipeline: meta-text detected, retrying")
            retry = await asyncio.wait_for(
                _call_openrouter(
                    "أنت أستاذ رياضيات. اكتب بالعربية. LaTeX: $$...$$. النتيجة: $$\\boxed{...}$$",
                    question,
                    max_tokens=1200,
                ),
                timeout=_NODE_TIMEOUT,
            )
            if retry and len(retry.strip()) > 20 and not any(m in retry for m in _META_MARKERS):
                solution = retry
            else:
                solution = _build_fallback_solution(question, math_type)

        elapsed = time.perf_counter() - t0
        logger.info("math_pipeline.solve: type=%s chars=%d time=%.2fs", math_type, len(solution), elapsed)
        final = f"## {label}\n\n{solution}"
        return {**state, "solution": solution, "final_response": final}

    except TimeoutError:
        logger.warning("math_pipeline.solve: timeout")
        fb = _build_fallback_solution(question, math_type)
        return {**state, "solution": fb, "final_response": f"## {label}\n\n{fb}", "error": "timeout"}
    except Exception as exc:
        logger.error("math_pipeline.solve error: %s", exc)
        fb = _build_fallback_solution(question, math_type)
        return {**state, "solution": fb, "final_response": f"## {label}\n\n{fb}", "error": str(exc)}


def _build_fallback_solution(question: str, math_type: str) -> str:
    hint = _get_math_context(math_type)
    hint_line = f"\n\n**تلميح:** {hint}" if hint else ""
    return (
        f"**المسألة:** {question}"
        f"{hint_line}\n\n"
        "⚠️ خدمة الذكاء الاصطناعي غير متاحة حالياً. يُرجى المحاولة مرة أخرى."
    )


def build_math_pipeline() -> object:
    """
    يبني LangGraph Math Pipeline.
    Topology: START → classify_node → solve_node → END
    """
    builder = StateGraph(MathPipelineState)
    builder.add_node("classify", classify_node)
    builder.add_node("solve",    solve_node)
    builder.add_edge(START,      "classify")
    builder.add_edge("classify", "solve")
    builder.add_edge("solve",    END)
    return builder.compile()


# Singleton: initialised once at startup, reused across requests
_math_pipeline: object | None = None


def get_math_pipeline() -> object:
    global _math_pipeline  # noqa: PLW0603
    if _math_pipeline is None:
        _math_pipeline = build_math_pipeline()
    return _math_pipeline


async def invoke_math_pipeline(
    question: str,
    thread_id: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """يستدعي Math Pipeline ويُعيد: final_response, math_type, solution, error."""
    pipeline = get_math_pipeline()
    initial_state: MathPipelineState = {
        "question":       question,
        "math_type":      "general_math",
        "math_hint":      "",
        "solution":       "",
        "final_response": "",
        "history":        history or [],
        "thread_id":      thread_id,
        "error":          None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = await pipeline.ainvoke(initial_state, config=config)
    return {
        "final_response": result.get("final_response", ""),
        "math_type":      result.get("math_type", "general_math"),
        "solution":       result.get("solution", ""),
        "error":          result.get("error"),
    }
