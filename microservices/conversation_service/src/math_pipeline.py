"""
LangGraph Math Pipeline — CogniForge BAC Tutor.

البنية (3 nodes — مُحسَّنة 2026-05-15 ISS-071):
  START → classify_node (deterministic) → solve_node (LLM) → normalize_node (deterministic) → END

دروس مُكتسَبة:
  ISS-070: 3 nodes × LLM = meta-text كارثي → الحل: node واحد للـ LLM.
  ISS-071 (2026-05-15): النموذج يستخدم \\[...\\] بدلاً من $$...$$ رغم التعليمات.
    الحل: normalize_node يُحوِّل كل صيغ LaTeX إلى $$...$$ بعد الـ LLM.
  ISS-072 (2026-05-15): temperature=0.7 يُسبب تشتتاً في الإجابات الرياضية.
    الحل: temperature=0.2 للرياضيات.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re as _re
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

_NODE_TIMEOUT = 40.0
_DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
# ISS-074 (2026-05-15): fallback chain مُحدَّث بعد بنشمارك حي
# - google/gemma-4-26b-a4b-it:free → rate-limited 429 (مُزال)
# - qwen/qwen3-coder:free          → rate-limited 429 (مُزال)
# - الترتيب: الأسرع → الأقوى → الأكبر
_FALLBACK_MODELS = [
    "openai/gpt-oss-20b:free",  # 28s، عربية ممتازة، LaTeX سليم
    "nvidia/nemotron-3-super-120b-a12b:free",  # 14s، 120B params، شرح عبقري
    "openai/gpt-oss-120b:free",  # 21s، احتياطي أخير
    "z-ai/glm-4.5-air:free",  # reasoning mode — ISS-069 fix
]

# ISS-074: ترتيب الأنواع حسب التخصيص (أكثر تحديداً → أقل تحديداً)
# function_study و differential_eq قبل derivative لتجنب false positives
_MATH_TYPES: dict[str, list[str]] = {
    "function_study": [
        # ISS-074: bare "ادرس" was overmatching genuine sequence questions like
        # "ادرس تقاربية المتتالية". Require an explicit function/study marker.
        "ادرس الدالة",
        "ادرس دالة",
        "ادرس f",
        "ادرس g",
        "ادرس h",
        "دراسة الدالة",
        "tableau de variation",
        "تغيرات الدالة",
        "إشارة الدالة",
        "جدول التغيرات",
        "ادرس تغيرات",
    ],
    "differential_eq": [
        "معادلة تفاضلية",
        "équation différentielle",
        "y''",
        "y' +",
        "y' =",
        "ED:",
        "EDO",
    ],
    "derivative": ["مشتق", "اشتقاق", "مشتقة", "f'(", "dérivée", "dériver"],
    "integral": ["تكامل", "∫", "intégrale", "intégrer", "primitive", "احسب التكامل"],
    "limit": [
        "نهاية الدالة",
        "نهاية عند",
        "lim(",
        "lim ",
        "limite",
        "∞",
        "لانهاية",
        "lim_",
        "limit",
    ],
    "matrix": ["مصفوفة", "matrice", "déterminant", "عكسية المصفوفة", "محدد المصفوفة"],
    "sequence": ["متتالية", "suite", "تقاربية", "divergente", "حدود المتتالية"],
    "equation": ["معادلة", "حل المعادلة", "equation", "résoudre", "جذر", "حلول"],
    "probability": ["احتمال", "probabilité", "عشوائي", "حادثة", "variable aléatoire"],
    "complex": ["مركب", "complexe", "module", "argument", "conjugué", "i² = -1"],
    "geometry": ["هندسة", "géométrie", "مستقيم", "مستوى", "متجه", "vecteur"],
}

_TYPE_LABELS: dict[str, str] = {
    "derivative": "📐 مسألة اشتقاق",
    "integral": "∫ مسألة تكامل",
    "limit": "∞ مسألة نهايات",
    "equation": "⚖️ مسألة معادلات",
    "function_study": "📊 دراسة دالة",
    "probability": "🎲 مسألة احتمالات",
    "complex": "🔢 أعداد مركبة",
    "matrix": "🔲 مصفوفات",
    "geometry": "📐 هندسة تحليلية",
    "sequence": "🔢 متتاليات",
    "differential_eq": "📈 معادلة تفاضلية",
}

_MATH_HINTS: dict[str, str] = {
    "derivative": "استخدم قاعدة الضرب (uv)' = u'v + uv' وقاعدة السلسلة",
    "integral": "فكِّر في التكامل بالتجزئة أو التعويض",
    "limit": "جرِّب التحليل أو قاعدة لوبيتال أو المكافئات المقاربية",
    "equation": "عزِّل المجهول أو حلِّل إلى عوامل",
    "function_study": "ابدأ بالمجال ثم المشتق ثم جدول التغيرات",
    "probability": "حدِّد الفضاء الاحتمالي ثم طبِّق القانون المناسب",
    "complex": "حوِّل بين الشكل الجبري والمثلثي والأسي",
    "matrix": "احسب المحدد أولاً",
    "geometry": "استخدم المتجهات والمعادلات الديكارتية",
    "sequence": "حدِّد نوع المتتالية ثم طبِّق القانون",
    "differential_eq": "ابحث عن الحل المتجانس أولاً ثم الحل الخاص",
    "general_math": "",
}

# System prompt — ISS-074 (2026-05-15) — concise + positive instructions
# الدرس: قائمة طويلة من الممنوعات تجعل النموذج يُكرِّرها كنص.
# الحل: تعليمات إيجابية مختصرة + مثال مباشر للأسلوب المطلوب.
_MATH_SYSTEM = (
    "أنت أستاذ رياضيات للبكالوريا الجزائرية. اشرح بالعربية الفصحى لطالب مبتدئ.\n\n"
    "قواعد LaTeX:\n"
    "- استخدم $$...$$ للمعادلات المستقلة\n"
    "- استخدم \\(...\\) للرموز داخل النص\n"
    "- اكتب النتيجة النهائية في $$\\boxed{...}$$\n\n"
    "منهجية الشرح:\n"
    "1. اشرح لماذا نستخدم هذه الطريقة في سطر\n"
    "2. اكتب الخطوات مرقمة مع كل عملية حسابية\n"
    "3. ضع النتيجة النهائية في صندوق\n"
    "4. أضف تفسيراً قصيراً لمعنى النتيجة\n\n"
    "ابدأ مباشرة بالحل — بدون تمهيد أو تفكير صوتي."
)

# ISS-074 (2026-05-15): _META_MARKERS مُحدَّث — قائمة أكثر دقة.
# - فقط عبارات meta-narration حقيقية (تفكير صوتي قبل البدء)
# - لا تطابق طبيعي مع "Let me work" داخل شرح علمي
# - نقحص فقط أول 150 char من الإجابة (حيث meta-text حقيقي يظهر)
_META_MARKERS = [
    "We need to",
    "Must output",
    "produce analysis",
    "I need to provide",
    "Let me think",
    "Let me start by",
    "I'll think",
    "I'll work through",
    "I should think",
    "I must analyze",
    "First, let me",
    "Okay, so",
    "Alright, let",
]

# ISS-074: علامات echo للـ system prompt (يحدث في نماذج صغيرة على أسئلة معقدة)
_SYSTEM_PROMPT_ECHO_MARKERS = [
    "$$...$$ for equations",
    "$$ for equations",
    "$$ for independent equations",
    "$$ for display equations",
    "$$ for display",
    "$$ for inline",
    "$$ for final",
    "$$...$$ for inline",
    "$$...$$ for display",
    "Provide methodology",
    "Must use $$",
    "Must not use",
    "Must follow methodology",
    "for inline? Actually",
    "for inline symbols",
    "for inline display",
    "for equations, ",
    "methodology: explain",
    "steps numbered, final",
    "for boxed",
    "in boxed",
]
_META_CHECK_PREFIX_LEN = 200  # نتحقق فقط من بداية الإجابة

# ── دالة تطبيع LaTeX (ISS-071) ────────────────────────────────────────────────
# `_re` is imported at the top of the file (E402 compliance).


def _normalize_latex(text: str) -> str:
    """
    يُحوِّل جميع صيغ LaTeX إلى $$...$$ الموحَّدة.

    المشكلة (ISS-071): النموذج يستخدم \\[...\\] و \\begin{equation}...\\end{equation}
    بدلاً من $$...$$ رغم التعليمات الصريحة في system prompt.
    الحل: post-processing deterministic بعد كل استجابة LLM.

    التحويلات:
      \\[ ... \\]                    → $$ ... $$
      \\begin{equation} ... \\end{equation} → $$ ... $$
      \\begin{align} ... \\end{align}       → $$ ... $$
      \\begin{aligned} ... \\end{aligned}   → $$ ... $$
    """
    if not text:
        return text

    # \\[ ... \\] → $$ ... $$  (multiline)
    text = _re.sub(
        r"\\\[\s*(.*?)\s*\\\]",
        lambda m: f"$$\n{m.group(1).strip()}\n$$",
        text,
        flags=_re.DOTALL,
    )

    # \\begin{equation} ... \\end{equation} → $$ ... $$
    text = _re.sub(
        r"\\begin\{equation\*?\}\s*(.*?)\s*\\end\{equation\*?\}",
        lambda m: f"$$\n{m.group(1).strip()}\n$$",
        text,
        flags=_re.DOTALL,
    )

    # \\begin{align} ... \\end{align} → $$ ... $$
    text = _re.sub(
        r"\\begin\{align\*?\}\s*(.*?)\s*\\end\{align\*?\}",
        lambda m: f"$$\n{m.group(1).strip()}\n$$",
        text,
        flags=_re.DOTALL,
    )

    # \\begin{aligned} ... \\end{aligned} → $$ ... $$
    text = _re.sub(
        r"\\begin\{aligned\*?\}\s*(.*?)\s*\\end\{aligned\*?\}",
        lambda m: f"$$\n{m.group(1).strip()}\n$$",
        text,
        flags=_re.DOTALL,
    )

    # تنظيف: $$ $$ متعددة متتالية → $$ واحدة
    return _re.sub(r"\$\$\s*\$\$", "", text)


def _clean_foreign_scripts(text: str) -> str:
    """
    ISS-074 (D-062): ينظف خلط لغات شاذ في المخرَج.

    الـ Whitelist:
    - عربي + لاتيني (للأسماء التقنية sin/cos/lim/dx) → مسموح
    - علامات LaTeX → مسموح

    الـ Blacklist (يُحذَف):
    - Cyrillic (روسي): `линейный`, `функция`, …
    - Chinese/Japanese: 向心, 函数, …
    - Spanish فقط: `aparece`, …
    """
    if not text:
        return text
    # 1) استبدالات Russian شائعة بمقابلها العربي
    replacements = {
        "линейный": "خطي",
        "линейная": "خطية",
        "линейное": "خطية",
        "функция": "دالة",
        "уравнение": "معادلة",
        "aparece": "يظهر",
        "aparecen": "تظهر",
        "Force向心": "قوة جذب مركزية",
        "قوة向心": "قوة جذب مركزية",
        "向心": "جذب مركزي",
        "向力": "قوة الجذب",
    }
    for foreign, arabic in replacements.items():
        text = text.replace(foreign, arabic)
    # 2) أي Cyrillic متبقٍ → احذف
    text = _re.sub(r"[Ѐ-ӿ]+", "", text)
    # 3) Chinese/CJK Han → احذف (أبجدية كاملة منفصلة، ليست تقنية)
    text = _re.sub(r"[一-鿿]+", "", text)
    # 4) Hiragana / Katakana → احذف
    return _re.sub(r"[぀-ゟ゠-ヿ]+", "", text)


def _strip_meta_prefix(text: str) -> str:
    """
    ISS-074: يحذف meta-narration من بداية الإجابة، يحتفظ بالمحتوى الجوهري.

    استراتيجية:
    1. ابحث عن أول معادلة LaTeX ($$ أو \\() أو ##/**عنوان قسم
    2. إذا وُجد قبله meta-marker → اقطع من بداية المحتوى الفعلي
    3. وإلا → أعد النص كما هو
    """
    if not text:
        return text
    # ابحث عن أول علامة على بدء المحتوى الفعلي
    candidates = []
    for marker in (
        "$$",
        "\\(",
        "##",
        "**الخطوة",
        "**المعادلة",
        "**الحل",
        "**1.",
        "1.",
        "**القاعدة",
        "**لماذا",
    ):
        i = text.find(marker)
        if i >= 0:
            candidates.append(i)
    if not candidates:
        return text
    start = min(candidates)
    # إذا كان start في أول 30 char، لا meta — أعد كما هو
    if start <= 30:
        return text
    # تأكد أن ما قبل start فيه meta-text (وليس بداية شرعية)
    prefix = text[:start]
    if not any(m in prefix for m in _META_MARKERS):
        return text
    # احذف meta-prefix
    return text[start:].strip()


def _classify_math_type(question: str) -> str:
    q_lower = question.lower()
    for math_type, patterns in _MATH_TYPES.items():
        if any(p in q_lower for p in patterns):
            return math_type
    return "general_math"


def _get_math_context(math_type: str) -> str:
    return _MATH_HINTS.get(math_type, "")


class MathPipelineState(TypedDict):
    question: str
    math_type: str
    math_hint: str
    solution: str
    final_response: str
    history: list[dict[str, str]]
    thread_id: str
    error: str | None


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
    models_to_try = [chosen, *_FALLBACK_MODELS]

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
                                {"role": "user", "content": user_prompt},
                            ],
                            "max_tokens": max_tokens,
                            "temperature": 0.2,  # ISS-072: 0.2 للرياضيات — أقل تشتتاً
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
    question = state["question"]
    math_type = state["math_type"]
    math_hint = state["math_hint"]
    label = _TYPE_LABELS.get(math_type, "📚 رياضيات")

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
        else:
            # ISS-074: meta-text + system-prompt-echo detection — فحص prefix
            prefix = solution[:_META_CHECK_PREFIX_LEN]
            meta_hit = next((m for m in _META_MARKERS if m in prefix), None)
            echo_hit = next((m for m in _SYSTEM_PROMPT_ECHO_MARKERS if m in prefix), None)
            if echo_hit and not meta_hit:
                meta_hit = echo_hit  # treat echo as meta-text for the retry path
            if meta_hit:
                # حاول strip-and-keep أولاً (احتفظ بالمحتوى الجيد)
                stripped = _strip_meta_prefix(solution)
                if stripped and len(stripped.strip()) > 100:
                    logger.info(
                        "math_pipeline: stripped meta-prefix (%r) — kept %d chars",
                        meta_hit,
                        len(stripped),
                    )
                    solution = stripped
                else:
                    # ISS-074: retry على نموذج أقوى (nemotron-super-120B) عند echo/meta
                    # يتجنب nemotron-nano-30B الذي يميل لإعادة echo system prompt
                    logger.warning(
                        "math_pipeline: meta-text/echo detected (%r), retrying on super-120B",
                        meta_hit,
                    )
                    retry = await asyncio.wait_for(
                        _call_openrouter(
                            (
                                "أستاذ رياضيات. اشرح بالعربية الفصحى فقط.\n"
                                "LaTeX: $$...$$ للمعادلات، \\(...\\) للرموز. النتيجة في $$\\boxed{...}$$.\n"
                                "ابدأ مباشرة بـ: 'لحساب ...' أو 'نطبق قاعدة ...' بدون تمهيد."
                            ),
                            question,
                            max_tokens=1500,
                            model="nvidia/nemotron-3-super-120b-a12b:free",
                        ),
                        timeout=_NODE_TIMEOUT,
                    )
                    if retry and len(retry.strip()) > 100:
                        retry_prefix = retry[:_META_CHECK_PREFIX_LEN]
                        if not any(m in retry_prefix for m in _META_MARKERS):
                            solution = retry
                        else:
                            # حتى الـ retry فيه meta — احتفظ بالمحتوى الأطول والأنظف
                            solution = _strip_meta_prefix(retry) or retry

        elapsed = time.perf_counter() - t0
        logger.info(
            "math_pipeline.solve: type=%s chars=%d time=%.2fs", math_type, len(solution), elapsed
        )
        final = f"## {label}\n\n{solution}"
        return {**state, "solution": solution, "final_response": final}

    except TimeoutError:
        logger.warning("math_pipeline.solve: timeout")
        fb = _build_fallback_solution(question, math_type)
        return {
            **state,
            "solution": fb,
            "final_response": f"## {label}\n\n{fb}",
            "error": "timeout",
        }
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


async def normalize_node(state: MathPipelineState) -> MathPipelineState:
    """
    Node 3 — Deterministic post-processing. لا LLM → ضمان أمان.

    يُصحِّح:
    - ISS-071: \\[...\\] → $$...$$ و \\begin{equation}...\\end{equation} → $$...$$
    - ISS-074: كلمات Cyrillic/Greek في نص عربي
    """
    solution = state.get("solution", "")
    if solution:
        normalized = _normalize_latex(solution)
        normalized = _clean_foreign_scripts(normalized)
        label = _TYPE_LABELS.get(state["math_type"], "📚 رياضيات")
        final = f"## {label}\n\n{normalized}"
        return {**state, "solution": normalized, "final_response": final}
    return state


def build_math_pipeline() -> object:
    """
    يبني LangGraph Math Pipeline.
    Topology: START → classify_node → solve_node → normalize_node → END

    ISS-071: normalize_node مُضاف لتحويل \\[...\\] → $$...$$ بعد الـ LLM.
    """
    builder = StateGraph(MathPipelineState)
    builder.add_node("classify", classify_node)
    builder.add_node("solve", solve_node)
    builder.add_node("normalize", normalize_node)
    builder.add_edge(START, "classify")
    builder.add_edge("classify", "solve")
    builder.add_edge("solve", "normalize")
    builder.add_edge("normalize", END)
    return builder.compile()


# Singleton: initialised once at startup, reused across requests
_math_pipeline: object | None = None


def get_math_pipeline() -> object:
    global _math_pipeline
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
        "question": question,
        "math_type": "general_math",
        "math_hint": "",
        "solution": "",
        "final_response": "",
        "history": history or [],
        "thread_id": thread_id,
        "error": None,
    }
    config = {"configurable": {"thread_id": thread_id}}
    result = await pipeline.ainvoke(initial_state, config=config)
    return {
        "final_response": result.get("final_response", ""),
        "math_type": result.get("math_type", "general_math"),
        "solution": result.get("solution", ""),
        "error": result.get("error"),
    }
