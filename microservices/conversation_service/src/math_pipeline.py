"""
LangGraph Math Pipeline — CogniForge BAC Tutor.

خط أنابيب رياضي متخصص للبكالوريا الجزائرية.

البنية (4 nodes):
  START
    → problem_analysis_node   (تحليل المسألة وتصنيفها)
    → solution_strategy_node  (اختيار استراتيجية الحل)
    → step_by_step_node       (الحل خطوة بخطوة مع LaTeX)
    → verification_node       (التحقق والتفسير الواقعي)
  → END

مبادئ الشرح الخارق (مستوحاة من أبحاث MIT/Stanford/Berkeley):
  1. Conceptual First — الفهم قبل الحساب
  2. Multiple Representations — جبري + هندسي + فيزيائي
  3. Error Anticipation — توقع أخطاء الطالب الشائعة
  4. Scaffolding — بناء تدريجي من البسيط للمعقد
  5. Metacognition — تعليم الطالب كيف يفكر

قانون الـ Skill:
  - مستقل تماماً — لا يستورد من microservice آخر
  - Fallback mode إلزامي عند غياب LLM
  - Timeout guard على كل node
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

logger = logging.getLogger(__name__)

# ── ثوابت ─────────────────────────────────────────────────────────────────────
_NODE_TIMEOUT = 40.0
_DEFAULT_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
_FALLBACK_MODEL = "openai/gpt-oss-20b:free"

# ── تصنيف أنواع المسائل الرياضية ──────────────────────────────────────────────
_MATH_TYPES: dict[str, list[str]] = {
    # الترتيب مهم — الأكثر تحديداً أولاً لتجنب التعارض
    "differential_eq": ["معادلة تفاضلية", "équation différentielle", "y''", "y' +", "y' ="],
    "derivative": ["مشتق", "اشتقاق", "مشتقة", "f'(", "dérivée", "dériver"],
    "integral": ["تكامل", "∫", "intégrale", "intégrer", "primitive"],
    "limit": ["نهاية الدالة", "نهاية عند", "lim(", "lim ", "limite", "∞", "لانهاية"],
    "matrix": ["مصفوفة", "matrice", "déterminant", "عكسية المصفوفة", "محدد المصفوفة"],
    "sequence": ["متتالية", "suite", "تقاربية", "divergente", "حدود المتتالية"],
    "equation": ["معادلة", "حل المعادلة", "equation", "résoudre", "جذر", "حلول"],
    "probability": ["احتمال", "probabilité", "عشوائي", "حادثة", "variable aléatoire"],
    "complex": ["مركب", "complexe", "module", "argument", "conjugué"],
    "geometry": ["هندسة", "géométrie", "مستقيم", "مستوى", "متجه", "vecteur"],
    "function_study": ["ادرس", "دراسة الدالة", "tableau de variation", "تغيرات الدالة", "إشارة الدالة"],
}


def _classify_math_type(question: str) -> str:
    """يُصنِّف نوع المسألة الرياضية."""
    q_lower = question.lower()
    for math_type, patterns in _MATH_TYPES.items():
        if any(p in q_lower for p in patterns):
            return math_type
    return "general_math"


def _get_math_context(math_type: str) -> str:
    """يُعيد سياقاً تعليمياً مخصصاً لكل نوع مسألة."""
    contexts = {
        "derivative": (
            "مسألة اشتقاق — استخدم قواعد: الضرب (uv)' = u'v + uv'، "
            "السلسلة (f∘g)' = f'(g)·g'، القسمة (u/v)' = (u'v - uv')/v²"
        ),
        "integral": (
            "مسألة تكامل — تقنيات: التكامل المباشر، التعويض، التجزئة ∫u·dv = uv - ∫v·du، "
            "التكامل بالكسور الجزئية، التكامل المثلثي"
        ),
        "limit": (
            "مسألة نهايات — تقنيات: رفع الإبهام، قاعدة لوبيتال، المكافئات المقاربية، "
            "الضرب بالمرافق، التحليل إلى عوامل"
        ),
        "equation": (
            "مسألة معادلات — تقنيات: العزل، التحليل، المعادلة التربيعية، "
            "الجذور، دراسة الإشارة"
        ),
        "function_study": (
            "دراسة دالة — خطوات: المجال، الحدود، المشتق، جدول التغيرات، "
            "النقاط الخاصة، الرسم"
        ),
        "probability": (
            "مسألة احتمالات — مفاهيم: الفضاء الاحتمالي، الاحتمال الشرطي، "
            "الاستقلالية، قانون الاحتمالات الكلية، بايز"
        ),
        "complex": (
            "أعداد مركبة — عمليات: الشكل الجبري a+ib، الشكل المثلثي r(cosθ+isinθ)، "
            "الشكل الأسي re^(iθ)، المعامل، الوسيطة"
        ),
        "matrix": (
            "مصفوفات — عمليات: الجمع، الضرب، المحدد، المصفوفة العكسية، "
            "الأنظمة الخطية، القيم الذاتية"
        ),
        "geometry": (
            "هندسة تحليلية — مفاهيم: المتجهات، المستقيمات، المستويات، "
            "المسافات، الزوايا، الإسقاطات"
        ),
        "sequence": (
            "متتاليات — أنواع: حسابية (un = u0 + nr)، هندسية (un = u0·qⁿ)، "
            "التقارب، المجاميع، الاستقراء"
        ),
        "differential_eq": (
            "معادلات تفاضلية — أنواع: الدرجة الأولى (y' + ay = b)، "
            "الدرجة الثانية، الحل العام والخاص"
        ),
    }
    return contexts.get(math_type, "مسألة رياضية عامة")


# ── State ──────────────────────────────────────────────────────────────────────


class MathPipelineState(TypedDict):
    """حالة خط أنابيب الرياضيات — تمر عبر 4 nodes."""

    question: str
    math_type: str           # نوع المسألة (derivative/integral/...)
    math_context: str        # سياق تعليمي مخصص للنوع
    analysis: str            # تحليل المسألة (node 1)
    strategy: str            # استراتيجية الحل (node 2)
    solution: str            # الحل خطوة بخطوة (node 3)
    final_response: str      # الإجابة النهائية مع التحقق (node 4)
    history: list[dict[str, str]]
    thread_id: str
    error: str | None


# ── LLM Helper ────────────────────────────────────────────────────────────────


async def _call_openrouter(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 800,
    model: str | None = None,
) -> str:
    """
    يستدعي OpenRouter مع fallback تلقائي.

    ISS-069: يتحقق من content != None قبل الإعادة.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        return ""

    chosen_model = model or os.environ.get("MATH_PIPELINE_MODEL", _DEFAULT_MODEL)
    models_to_try = [chosen_model, _FALLBACK_MODEL]

    try:
        import httpx

        for attempt_model in models_to_try:
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
                            "model": attempt_model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                            "max_tokens": max_tokens,
                            "temperature": 0.6,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        msg = choices[0].get("message", {})
                        # ISS-069: بعض نماذج reasoning تضع الإجابة في reasoning لا content
                        content = msg.get("content") or msg.get("reasoning") or ""
                        if content and content.strip():
                            return content.strip()
                    logger.warning("math_pipeline: empty content from %s", attempt_model)
            except Exception as e:
                logger.warning("math_pipeline: model %s failed: %s", attempt_model, e)
                continue
    except ImportError:
        logger.error("math_pipeline: httpx not available")

    return ""


# ── System Prompts ─────────────────────────────────────────────────────────────

_BASE_RULES = (
    "## قواعد اللغة — صارمة لا تُخرق\n"
    "- اكتب بالعربية الفصحى الواضحة فقط\n"
    "- لا تخلط مع الروسية أو الإنجليزية أو الفرنسية إلا للمصطلحات التقنية\n\n"
    "## قواعد LaTeX — إلزامية\n"
    "- المعادلات المستقلة: $$...$$\n"
    "- الرموز المضمّنة: \\(...\\)\n"
    "- النتائج النهائية: $$\\boxed{...}$$\n"
)

_ANALYSIS_SYSTEM = (
    "أنت محلل رياضي خبير للبكالوريا الجزائرية.\n"
    "مهمتك: تحليل المسألة وتحديد:\n"
    "1. نوع المسألة الدقيق\n"
    "2. المفاهيم الرياضية المطلوبة\n"
    "3. الأخطاء الشائعة التي يقع فيها الطلاب\n"
    "4. مستوى الصعوبة (سهل/متوسط/صعب)\n\n"
    + _BASE_RULES
    + "أجب بشكل موجز ومنظم."
)

_STRATEGY_SYSTEM = (
    "أنت مخطط استراتيجي للحلول الرياضية.\n"
    "مهمتك: اختيار أفضل استراتيجية للحل وشرح لماذا هي الأنسب.\n"
    "اذكر:\n"
    "1. الاستراتيجية المختارة واسمها\n"
    "2. لماذا هي الأنسب لهذه المسألة\n"
    "3. الخطوات الكبرى للحل (بدون تفاصيل)\n"
    "4. تحذير من الأخطاء الشائعة\n\n"
    + _BASE_RULES
)

_SOLUTION_SYSTEM = (
    "أنت أستاذ رياضيات عبقري للبكالوريا الجزائرية.\n"
    "مهمتك: تقديم الحل الكامل خطوة بخطوة مع التحقق والتفسير الواقعي.\n\n"
    + _BASE_RULES
    + "\n## منهجية الحل الإلزامية (6 أقسام)\n"
    "### القسم 1: لماذا هذه الطريقة؟\n"
    "اشرح سبب اختيار الطريقة وما المشكلة التي تحلها.\n\n"
    "### القسم 2: الخطوات المرقمة\n"
    "كل خطوة في سطر منفصل مع تبرير رياضي واضح.\n\n"
    "### القسم 3: الحسابات التفصيلية\n"
    "لا تتخطى خطوة واحدة — الطالب يحتاج كل التفاصيل.\n\n"
    "### القسم 4: النتيجة النهائية\n"
    "$$\\boxed{النتيجة}$$\n\n"
    "### القسم 5: التحقق\n"
    "تحقق من النتيجة بتعويض قيمة بسيطة أو بطريقة مختلفة.\n\n"
    "### القسم 6: التفسير الواقعي\n"
    "ماذا تعني النتيجة في الفيزياء أو الهندسة أو الحياة؟\n"
    "أين نجد هذا المفهوم في الطبيعة؟\n\n"
    "لا تختصر — الطالب يحتاج الفهم الكامل."
)

_VERIFICATION_SYSTEM = (
    "أنت مُدقِّق رياضي وشارح للمعنى الواقعي للبكالوريا الجزائرية.\n\n"
    + _BASE_RULES
    + "\n## مهمتك — أجب مباشرة بالعربية\n"
    "اكتب فقط هذه الأقسام بالترتيب:\n\n"
    "**✅ التحقق من النتيجة:**\n"
    "[تحقق بتعويض قيمة بسيطة أو بطريقة مختلفة]\n\n"
    "**🔭 التفسير الهندسي/الفيزيائي:**\n"
    "[ماذا تعني النتيجة في الواقع؟]\n\n"
    "**🌍 الربط بالحياة:**\n"
    "[أين نجد هذا المفهوم في الطبيعة أو الهندسة؟]\n\n"
    "**💡 نصيحة للطالب:**\n"
    "[كيف تتذكر هذه الطريقة؟]\n\n"
    "لا تكتب أي شيء آخر. لا تشرح ما ستفعله. افعل فقط."
)


# ── Graph Nodes ────────────────────────────────────────────────────────────────


async def problem_analysis_node(state: MathPipelineState) -> MathPipelineState:
    """
    Node 1: تحليل المسألة وتصنيفها.

    يُحدِّد نوع المسألة والمفاهيم المطلوبة والأخطاء الشائعة.
    """
    t0 = time.perf_counter()
    try:
        math_type = _classify_math_type(state["question"])
        math_context = _get_math_context(math_type)

        analysis = await asyncio.wait_for(
            _call_openrouter(
                system_prompt=_ANALYSIS_SYSTEM,
                user_prompt=(
                    f"حلِّل هذه المسألة:\n{state['question']}\n\n"
                    f"السياق: {math_context}"
                ),
                max_tokens=400,
            ),
            timeout=_NODE_TIMEOUT,
        )

        if not analysis:
            analysis = f"مسألة من نوع: {math_type} — {math_context}"

        logger.info("math_pipeline.analysis: type=%s duration=%.2fs", math_type, time.perf_counter() - t0)
        return {**state, "math_type": math_type, "math_context": math_context, "analysis": analysis}

    except TimeoutError:
        logger.warning("math_pipeline.analysis: timeout")
        math_type = _classify_math_type(state["question"])
        return {
            **state,
            "math_type": math_type,
            "math_context": _get_math_context(math_type),
            "analysis": f"تحليل سريع: مسألة {math_type}",
            "error": "analysis_timeout",
        }
    except Exception as exc:
        logger.error("math_pipeline.analysis error: %s", exc)
        return {**state, "math_type": "general_math", "math_context": "", "analysis": "", "error": str(exc)}


async def solution_strategy_node(state: MathPipelineState) -> MathPipelineState:
    """
    Node 2: اختيار استراتيجية الحل وشرح لماذا هي الأنسب.
    """
    t0 = time.perf_counter()
    try:
        strategy = await asyncio.wait_for(
            _call_openrouter(
                system_prompt=_STRATEGY_SYSTEM,
                user_prompt=(
                    f"المسألة: {state['question']}\n"
                    f"نوع المسألة: {state['math_type']}\n"
                    f"التحليل: {state['analysis']}\n\n"
                    "اختر أفضل استراتيجية للحل وبرِّر اختيارك."
                ),
                max_tokens=350,
            ),
            timeout=_NODE_TIMEOUT,
        )

        if not strategy:
            strategy = f"استراتيجية: {state['math_context']}"

        logger.info("math_pipeline.strategy: duration=%.2fs", time.perf_counter() - t0)
        return {**state, "strategy": strategy}

    except TimeoutError:
        logger.warning("math_pipeline.strategy: timeout")
        return {**state, "strategy": state["math_context"], "error": "strategy_timeout"}
    except Exception as exc:
        logger.error("math_pipeline.strategy error: %s", exc)
        return {**state, "strategy": "", "error": str(exc)}


async def step_by_step_node(state: MathPipelineState) -> MathPipelineState:
    """
    Node 3: الحل الكامل خطوة بخطوة مع LaTeX.

    هذا هو القلب — الشرح العبقري الخارق.
    """
    t0 = time.perf_counter()
    try:
        # بناء سياق المحادثة السابقة
        history_text = ""
        if state.get("history"):
            recent = state["history"][-4:]
            history_text = "\n".join(
                f"{h['role']}: {h['content']}" for h in recent if h.get("content")
            )

        solution = await asyncio.wait_for(
            _call_openrouter(
                system_prompt=_SOLUTION_SYSTEM,
                user_prompt=(
                    f"المسألة: {state['question']}\n"
                    f"نوع المسألة: {state['math_type']}\n"
                    f"الاستراتيجية المختارة: {state['strategy']}\n"
                    + (f"\nسياق المحادثة:\n{history_text}\n" if history_text else "")
                    + "\n\nقدِّم الحل الكامل خطوة بخطوة بالعربية مع LaTeX.\n"
                    "يجب أن تنتهي بـ: $$\\boxed{النتيجة النهائية}$$"
                ),
                max_tokens=1500,
            ),
            timeout=_NODE_TIMEOUT,
        )

        if not solution:
            solution = _build_fallback_solution(state["question"], state["math_type"])

        logger.info("math_pipeline.solution: chars=%d duration=%.2fs", len(solution), time.perf_counter() - t0)
        return {**state, "solution": solution}

    except TimeoutError:
        logger.warning("math_pipeline.solution: timeout")
        return {
            **state,
            "solution": _build_fallback_solution(state["question"], state["math_type"]),
            "error": "solution_timeout",
        }
    except Exception as exc:
        logger.error("math_pipeline.solution error: %s", exc)
        return {**state, "solution": _build_fallback_solution(state["question"], state["math_type"]), "error": str(exc)}


async def verification_node(state: MathPipelineState) -> MathPipelineState:
    """
    Node 4: تجميع الإجابة النهائية.

    الحل الكامل من step_by_step_node يتضمن التحقق والتفسير بالفعل.
    هذا الـ node يُنظِّف الإجابة ويُضيف header مناسب.
    """
    solution = state.get("solution", "")
    math_type = state.get("math_type", "general_math")

    if not solution or len(solution) < 30:
        final = _build_fallback_solution(state["question"], math_type)
    else:
        # إضافة header يُوضِّح نوع المسألة
        type_labels = {
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
        label = type_labels.get(math_type, "📚 رياضيات")
        final = f"## {label}\n\n{solution}"

    return {**state, "final_response": final}


# ── Fallback ───────────────────────────────────────────────────────────────────


def _build_fallback_solution(question: str, math_type: str) -> str:
    """يبني إجابة fallback عند فشل LLM."""
    context = _get_math_context(math_type)
    return (
        f"**المسألة:** {question}\n\n"
        f"**النوع:** {math_type}\n\n"
        f"**السياق:** {context}\n\n"
        "⚠️ خدمة الذكاء الاصطناعي غير متاحة حالياً. يُرجى المحاولة مرة أخرى."
    )


# ── Graph Builder ──────────────────────────────────────────────────────────────


def build_math_pipeline() -> object:
    """
    يبني LangGraph Math Pipeline.

    Topology:
      START → problem_analysis_node → solution_strategy_node
            → step_by_step_node → verification_node → END

    كل node مُحمي بـ timeout guard ويُعيد fallback عند الفشل.
    """
    builder = StateGraph(MathPipelineState)
    builder.add_node("problem_analysis", problem_analysis_node)
    builder.add_node("solution_strategy", solution_strategy_node)
    builder.add_node("step_by_step", step_by_step_node)
    builder.add_node("verification", verification_node)

    builder.add_edge(START, "problem_analysis")
    builder.add_edge("problem_analysis", "solution_strategy")
    builder.add_edge("solution_strategy", "step_by_step")
    builder.add_edge("step_by_step", "verification")
    builder.add_edge("verification", END)

    return builder.compile()


# ── Singleton ──────────────────────────────────────────────────────────────────

# Singleton: مُهيَّأ مرة واحدة عند الإقلاع
_math_pipeline: object | None = None


def get_math_pipeline() -> object:
    """يُعيد الـ pipeline المُهيَّأ — lazy singleton."""
    global _math_pipeline
    if _math_pipeline is None:
        _math_pipeline = build_math_pipeline()
    return _math_pipeline


async def invoke_math_pipeline(
    question: str,
    thread_id: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    """
    يستدعي Math Pipeline ويُعيد الإجابة الكاملة.

    يُستخدم من main.py عند اكتشاف سؤال رياضي.
    يُعيد: final_response, math_type, solution, error
    """
    pipeline = get_math_pipeline()
    initial_state: MathPipelineState = {
        "question": question,
        "math_type": "general_math",
        "math_context": "",
        "analysis": "",
        "strategy": "",
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
