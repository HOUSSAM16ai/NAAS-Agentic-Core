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

# ISS-075 (D-063): تطبيقات regex الـ greeting يجب أن تسمح بكلمات إضافية
# قبل الإصلاح: `^(السلام)[\s\W]*$` يفشل عند "السلام عليكم" لأن "عليكم"
# ليست في `[\s\W]`. نتيجة: التحية تُصنَّف كـ `general` → الـ LLM يُولد
# شرحاً etymological مع كلمات أجنبية (català/også/wishes/CJK punct).
# الحل: استخدام `\b...\b` مع `.*` لقبول أي امتداد طبيعي.
# هذا الـ regex مكرَّر في `app/telemetry/path_observer.py` — يجب تحديث كليهما (D-013).
_GREETING_PATTERNS = [
    # تحيات إسلامية وعربية شاملة (السلام عليكم + ورحمة الله + إلخ)
    r"^(?:و\s*)?(?:عليكم\s+)?السلام(?:\s+عليكم)?(?:\s+و?رحم[ةى]\s+الله)?(?:\s+و?بركاته)?[\s\W]*$",
    # مرحبا/أهلا/هلا + امتدادات طبيعية ("مرحبا بك", "أهلاً وسهلاً", "هلا والله")
    r"^(مرحبا|أهلاً?|أهلا|هلاً?|هلا)(?:\s+\S+){0,3}[\s\W]*$",
    # تحيات إنجليزية/فرنسية (وحدها أو مع امتداد قصير)
    r"^(hello|hi|hey|salam|بونجور|bonjour|salut|good\s+(morning|afternoon|evening))(?:\s+\S+){0,2}[\s\W]*$",
    # كيف حالك + امتدادات (يا أستاذ، اليوم، إلخ)
    r"^(كيف\s+حالك|ما\s+أخبارك|how\s+are\s+you|كيف\s+الأحوال)(?:\s+\S+){0,4}[\s\W]*$",
    # شكر
    r"^(شكرا|شكراً|merci|thank\s+you|thanks)(?:\s+\S+){0,4}[\s\W]*$",
    # وداع
    r"^(مع\s+السلامة|وداع[اً]?|bye|goodbye|au\s+revoir)(?:\s+\S+){0,3}[\s\W]*$",
    # تحيات قصيرة (صباح الخير، مساء الخير، ليلة سعيدة، صباحك)
    r"^(صباح\s+(الخير|النور)|مساء\s+(الخير|النور)|ليلة\s+سعيدة|صباحك\s+\S+|مساؤك\s+\S+)[\s\W]*$",
]

_SYSTEM_PROMPTS = {
    "educational": (
        "أنت أستاذ رياضيات وعلوم عبقري متخصص في البكالوريا الجزائرية.\n"
        "مهمتك المقدسة: أن يفهم الطالب فهماً عميقاً حقيقياً — إدراكاً لا حفظاً.\n\n"
        "## قواعد اللغة — صارمة لا تُخرق أبداً\n"
        "- اكتب بالعربية الفصحى الواضحة فقط\n"
        "- لا تخلط مع الروسية أو الإنجليزية أو الفرنسية إلا للمصطلحات التقنية\n"
        "- المصطلحات التقنية: اكتبها بالعربية أولاً ثم الأجنبية بين قوسين\n"
        "- مثال صحيح: «قاعدة الضرب (Product Rule)» لا «Product Rule»\n\n"
        "## قواعد LaTeX — إلزامية في كل إجابة رياضية\n"
        "- المعادلات المستقلة: $$...$$\n"
        "- الرموز المضمّنة في النص: \\(...\\)\n"
        "- النتائج النهائية: $$\\boxed{...}$$\n"
        "- أمثلة صحيحة:\n"
        "  $$\\int_0^1 x^2\\,dx = \\frac{1}{3}$$\n"
        "  الدالة \\(f(x) = x^2 e^{-x}\\) معرَّفة على \\(\\mathbb{R}\\)\n"
        "  $$\\lim_{x\\to+\\infty} \\frac{x^2+1}{e^x} = 0$$\n"
        "  $$f'(x) = 2x \\cdot e^{3x} + 3x^2 \\cdot e^{3x} = x e^{3x}(2 + 3x)$$\n\n"
        "## منهجية الشرح العبقري (6 مراحل إلزامية)\n"
        "1. **لماذا؟** — ابدأ بالسؤال: لماذا نحتاج هذه الطريقة؟ ما المشكلة التي تحلها؟\n"
        "2. **الفكرة الجوهرية** — اشرح المبدأ الرياضي بكلمات بسيطة قبل الرموز\n"
        "3. **الخطوات المرقمة** — كل خطوة في سطر منفصل مع تبرير رياضي واضح\n"
        "4. **الحسابات التفصيلية** — لا تتخطى خطوة واحدة — الطالب يحتاج كل التفاصيل\n"
        "5. **النتيجة في صندوق** — $$\\boxed{\\text{النتيجة النهائية}}$$\n"
        "6. **التفسير الواقعي** — ماذا تعني النتيجة في الفيزياء أو الهندسة أو الحياة؟\n\n"
        "## مواد البكالوريا الجزائرية\n"
        "**رياضيات:** التحليل (الدوال، التكامل، المعادلات التفاضلية)، الجبر (الأعداد المركبة، "
        "المصفوفات)، الإحصاء والاحتمالات، الهندسة التحليلية\n"
        "**فيزياء:** الميكانيك (قوانين نيوتن، الطاقة)، الكهرباء، الموجات، الفيزياء الحديثة\n"
        "**كيمياء:** الكيمياء العضوية وغير العضوية، التوازنات الكيميائية\n\n"
        "## قاعدة 2016\n"
        "سنة 2016 هي السنة الوحيدة في تاريخ بكالوريا الجزائر بدورتين (الأولى والثانية). "
        "تحقق دائماً من الدورة المقصودة عند ذكر 2016.\n\n"
        "## أسلوب الشرح الخارق\n"
        "- ابدأ بـ «لماذا نستخدم هذه الطريقة؟» قبل الحساب\n"
        "- اربط المفاهيم بالحياة الواقعية والفيزياء والهندسة\n"
        "- استخدم التشبيهات والأمثلة الملموسة لتثبيت المفهوم\n"
        "- إذا كان السؤال غامضاً، اطرح توضيحاً قبل الإجابة\n"
        "- لا تختصر — الطالب يحتاج الفهم الكامل\n"
        "- شجّع الطالب وأكد له أن الرياضيات ممتعة وليست صعبة"
    ),
    "general": (
        "أنت مساعد ذكي متخصص في خدمة الطلاب الجزائريين.\n"
        "أجب بالعربية الفصحى الواضحة فقط — لا تخلط اللغات.\n"
        "أجب بدقة علمية مع الاستناد إلى سياق المحادثة السابقة.\n"
        "استخدم LaTeX للرموز الرياضية: $$...$$ للمعادلات و \\(...\\) للرموز المضمّنة.\n"
        "قدّم إجابات منظمة بعناوين وخطوات واضحة.\n"
        "لا تُشر إلى تفاصيل داخلية أو بنية النظام."
    ),
    "chat": (
        "أنت مساعد ودود وذكي للطلاب الجزائريين.\n"
        "رد بشكل طبيعي ومختصر باللغة العربية الفصحى.\n"
        "إذا كان السؤال تعليمياً، شجّع الطالب على طرح السؤال بشكل كامل.\n"
        "كن إيجابياً ومحفزاً."
    ),
}


# ─── State ────────────────────────────────────────────────────────────────────


class LocalChatState(TypedDict):
    question: str
    intent: str
    history_messages: list[dict]
    final_response: str


# ─── ISS-075 D-063: Foreign-script + chat meta-narration sanitizer ────────────

import re as _re_sanitize

# الكلمات المختلطة (Russian/Norwegian/Spanish/etc) → استبدالها بالعربية المتوقَّعة
_FOREIGN_REPLACEMENTS = {
    # روسي
    "линейный": "خطي",
    "линейная": "خطية",
    "линейное": "خطية",
    "функция": "دالة",
    "уравнение": "معادلة",
    # نرويجي/دانماركي
    "også": "أيضاً",
    "auch": "أيضاً",
    # إسباني
    "aparece": "يظهر",
    "aparecen": "تظهر",
    # إنجليزي meta في رد عربي
    "wishes": "أمنيات",
    "invitation": "دعوة",
    # CJK punctuation → علامات عربية
    "。": ".",
    "（": "(",
    "）": ")",
    "「": '"',
    "」": '"',
    "『": '"',
    "』": '"',
    "、": "،",
    "〜": "~",
}

# meta-narration بالإنجليزية في بداية ردود chat
_CHAT_META_PATTERNS = [
    _re_sanitize.compile(r"^Okay,\s+the user[^.\n]*\.\s*", _re_sanitize.IGNORECASE),
    _re_sanitize.compile(
        r"^First,?\s+I\s+(should|must|need|will)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
    _re_sanitize.compile(
        r"^The user (greeted|said|asked|wrote)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
    _re_sanitize.compile(r"^I need to (respond|answer|reply)[^.\n]*\.\s*", _re_sanitize.IGNORECASE),
    _re_sanitize.compile(
        r"^Let me (think|respond|answer|consider)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
    _re_sanitize.compile(
        r"^Alright,\s+(the\s+)?(user|question|so)[^.\n]*\.\s*", _re_sanitize.IGNORECASE
    ),
]


def _sanitize_local_graph_response(text: str, intent: str) -> str:
    """ISS-075 (D-063): ينظف foreign-script + chat meta-narration من ردود local_graph.

    يعالج كارثة التحية التي شاهدها المستخدم: «السلام عليكم» يُولِّد رداً
    etymological مع كلمات نرويجية (`også`) وإنجليزية (`wishes`) ونقاط CJK (`。`).

    الـ greeting الآن يُصنَّف كـ chat (بعد regex fix) فيُمر هنا للتنظيف الأخير.
    """
    if not text:
        return text
    out = text
    # 1. استبدالات foreign → عربي
    for foreign, arabic in _FOREIGN_REPLACEMENTS.items():
        out = out.replace(foreign, arabic)
    # 2. حذف Cyrillic كامل (روسي/أوكراني)
    out = _re_sanitize.sub(r"[Ѐ-ӿ]+", "", out)
    # 3. حذف Chinese CJK Han
    out = _re_sanitize.sub(r"[一-鿿]+", "", out)
    # 4. حذف Hiragana/Katakana (ياباني)
    out = _re_sanitize.sub(r"[぀-ゟ゠-ヿ]+", "", out)
    # 5. للـ chat فقط — احذف meta-narration بالإنجليزية في البداية
    if intent == "chat":
        for _ in range(5):  # multi-pass
            prev = out
            for rx in _CHAT_META_PATTERNS:
                out = rx.sub("", out, count=1)
            out = out.lstrip()
            if out == prev:
                break
    return out


# ─── Helpers ──────────────────────────────────────────────────────────────────


# ISS-079 (D-067 — 2026-05-17): Greeting fastpath في المونوليث
# قبل D-067 كانت greeting fastpath موجودة فقط في orchestrator-service.
# عندما orchestrator-service غير متاح أو يفشل، الطلب يصل إلى local_graph.py
# والذي كان يُمرِّر التحية للـ LLM مع system prompt عام → etymology / hallucination.
# الحل: نفس fastpath dict من orchestrator + نفس blockers (D-065)
# يُستدعى في `_chat_node` قبل الذهاب للـ LLM.
_GREETING_FASTPATH_RESPONSES: dict[str, str] = {
    "السلام عليكم": "وعليكم السلام ورحمة الله وبركاته! 🌿 كيف يمكنني مساعدتك في دراستك اليوم؟",
    "السلام": "وعليكم السلام! كيف يمكنني مساعدتك اليوم؟",
    "وعليكم السلام": "أهلاً وسهلاً بك! كيف يمكنني مساعدتك في دراستك؟",
    "مرحبا": "أهلاً وسهلاً! كيف يمكنني مساعدتك اليوم؟",
    "مرحبًا": "أهلاً وسهلاً! كيف يمكنني مساعدتك اليوم؟",
    "أهلا": "أهلاً وسهلاً بك! كيف يمكنني مساعدتك؟",
    "أهلاً": "أهلاً وسهلاً بك! كيف يمكنني مساعدتك؟",
    "هلا": "أهلاً بك! كيف يمكنني مساعدتك؟",
    "هلاً": "أهلاً بك! كيف يمكنني مساعدتك؟",
    "كيف حالك": "بخير والحمد لله! شكراً لسؤالك. كيف يمكنني مساعدتك في دراستك؟",
    "كيف الحال": "بخير والحمد لله! كيف يمكنني مساعدتك اليوم؟",
    "صباح الخير": "صباح النور! كيف يمكنني مساعدتك في دراستك اليوم؟",
    "صباح النور": "صباح الخير! كيف يمكنني مساعدتك؟",
    "مساء الخير": "مساء النور! كيف يمكنني مساعدتك في دراستك؟",
    "مساء النور": "مساء الخير! كيف يمكنني مساعدتك؟",
    "شكرا": "العفو! 😊 إذا احتجت أي مساعدة أخرى، أنا هنا.",
    "شكراً": "العفو! 😊 سعيدٌ بمساعدتك.",
    "شكرا جزيلا": "العفو، لا شكر على واجب! 😊",
    "hello": "Hi! How can I help you with your studies today?",
    "hi": "Hello! How can I help you today?",
    "hey": "Hey there! How can I help?",
    "good morning": "Good morning! How can I help you today?",
    "good evening": "Good evening! How can I help you?",
}

# D-065: blockers — لا fastpath لو يحوي السؤال فعل علمي/تعليمي
_FASTPATH_BLOCKERS: tuple[str, ...] = (
    "اشرح",
    "احسب",
    "اوجد",
    "أوجد",
    "حل ",
    "اعطني",
    "أعطني",
    "هات",
    "تمرين",
    "مسألة",
    "مادة",
    "درس",
    "قانون",
    "نظرية",
    "بكالوريا",
    "explain",
    "solve",
    "calculate",
    "find",
    "give me",
    "help with",
    "ما هو",
    "ما هي",
    "لماذا",
    "متى",
    "أين",
)
_KAYFA_GREETINGS: tuple[str, ...] = (
    "كيف حالك",
    "كيف الحال",
    "كيف الأحوال",
    "كيف صحتك",
)
_GREETING_TAIL_ALLOWED: frozenset[str] = frozenset(
    {
        "وعليكم",
        "السلام",
        "ورحمة",
        "ورحمت",
        "رحمة",
        "الله",
        "وبركاته",
        "بركاته",
        "وسهلاً",
        "وسهلا",
        "بكم",
        "بك",
        "والله",
        "اليوم",
        "يا",
        "أستاذ",
        "أستاذي",
        "والاكرام",
        "في",
    }
)


def _greeting_fastpath_response(query: str) -> str | None:
    """يُعيد رد تحية محدد مسبقاً بدون LLM (D-067 — يحل ISS-079 catastrophe #1).

    يكرر منطق orchestrator's get_greeting_fastpath_response لضمان عمل
    التحيات حتى عندما orchestrator-service غير متاح.
    """
    if not query:
        return None
    normalized = query.strip().lower()
    cleaned = re.sub(r"[^\w\s؀-ۿ]", "", normalized).strip()
    if not cleaned:
        return None

    # blocker: كيف interrogative (إلا تحيات كيف حالك)
    if "كيف" in normalized and not any(g in normalized for g in _KAYFA_GREETINGS):
        return None
    # blockers علمية
    for blocker in _FASTPATH_BLOCKERS:
        if blocker in normalized:
            return None

    for greeting, response in _GREETING_FASTPATH_RESPONSES.items():
        g_lower = greeting.lower()
        if cleaned == g_lower:
            return response
        # امتدادات بهامش ≤ 25 char (السلام عليكم ورحمة الله...)
        if cleaned.startswith(g_lower) and len(cleaned) - len(g_lower) <= 25:
            tail_words = cleaned[len(g_lower) :].strip().split()
            if all(w in _GREETING_TAIL_ALLOWED or len(w) <= 2 for w in tail_words):
                return response
    return None


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

    # ISS-079 (D-067): Greeting fast-path — قبل أي استدعاء LLM
    # يحل كارثة "السلام عليكم → etymology بكلمات أجنبية" التي شاهدها المستخدم.
    # نماذج OpenRouter المجانية تُولِّد etymology طويلة كاستجابة "بدقة علمية"
    # عند سؤال "السلام عليكم" → نستخدم رد deterministic مباشر.
    if intent == "chat":
        fastpath = _greeting_fastpath_response(question)
        if fastpath:
            logger.info("local_graph.chat_node greeting_fastpath chars=%d", len(fastpath))
            return {"final_response": fastpath}

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
        # ISS-075 D-063: تنظيف foreign-script + chat meta-narration
        clean = _sanitize_local_graph_response(clean, intent)
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

# ISS-079 (D-067 — 2026-05-17): إصلاح كارثي
# الـ prompt السابق كان يحوي 78×`━` (box-drawing chars) متكرر 6 مرات + 1690 char
# تجريب حي على nvidia/nemotron-nano-30b-a3b:free كشف أن هذا الـ prompt يُسبب:
# - content_chunks=0 (الكل في reasoning بالإنجليزية)
# - "pepepe aaaa" / etymology / English thinking leak إلى المستخدم
# الحل: prompt مُختصر بدون chars نادرة (~ 500 chars بدل 1690).
_EXERCISE_EXPLANATION_SYSTEM_PROMPT = (
    "أنت أستاذ رياضيات للبكالوريا الجزائرية.\n"
    "اشرح للطالب كيف يفكر، لا تكتفِ بالحساب.\n\n"
    "قواعد إلزامية:\n"
    "1. اكتب بالعربية الفصحى فقط — لا إنجليزية، لا روسية، لا تفكير صوتي.\n"
    "2. لا تنسخ الإجابة النموذجية حرفياً — اشرح المنطق وراءها.\n"
    "3. لا تخترع نتائج، لا تذكر تمارين أخرى، لا تجيب عن أجزاء غير مطلوبة.\n"
    "4. LaTeX إلزامي: $$...$$ للمعادلات، \\(...\\) للرموز داخل النص.\n"
    "5. النتائج الرئيسية: $$\\boxed{...}$$.\n\n"
    "منهجية الشرح (5 خطوات):\n"
    "1. المبدأ: ما القاعدة المستخدمة؟ لماذا اخترناها؟\n"
    "2. الجسر الفكري: «لأن ... إذن ...»\n"
    "3. الحساب التفصيلي: كل خطوة مع تبريرها.\n"
    "4. التحقق: كيف نتأكد من صحة النتيجة؟\n"
    "5. التفسير: ماذا تعني هندسياً أو فيزيائياً؟"
)


_MAX_EXERCISE_CONTEXT_CHARS = 3000
"""
الحد الأقصى لحجم context التمرين المُرسَل للـ LLM.

ISS-055: خُفِّض من 6000 إلى 3000 حرف — النماذج المجانية تتجمد مع context > 4000 حرف.
يُستخدم فقط كـ fallback عند فشل التقطيع الذكي.
"""

_MAX_EXPLANATION_TOKENS = 900
"""
الحد الأقصى للرموز المُولَّدة في شرح التمرين الكامل.

ISS-055: خُفِّض من 1200 إلى 900 — يُقلِّص وقت التوليد مع الحفاظ على جودة الشرح.
900 token ≈ 650 كلمة عربية — كافٍ لشرح مفصل لجزء واحد.

ISS-059: الآن يُستخدم فقط للأسئلة الشاملة. الأسئلة المركَّزة تُولِّد نسبة أصغر
عبر `_classify_question_budget()`.
"""


# ─────────────────────────────────────────────────────────────────────────────
# ISS-059 (D-053 — Question-Aware Latency Budgets):
# تأخُّر الإجابة عند طلب «تفصيل معين» كان كارثياً (~15-18s) لأن كل سؤال
# يطلب 900 token مهما كان حجمه. الآن نُصنِّف السؤال إلى 4 أنواع ونعطي
# كل نوع budget مناسب — TTFT لا يتغيَّر لكن **زمن الانتهاء** ينخفض كثيراً:
#
#   - CONCEPT (ماذا نقصد/ما هو) → context=1200, tokens=350, TTFB+stream ≈ 6s
#   - JUSTIFICATION (لماذا/علِّل) → context=1500, tokens=450, ≈ 7s
#   - METHOD (كيف نُثبت/كيف نحسب) → context=2000, tokens=600, ≈ 10s
#   - FULL (اشرح التمرين/الجزء كاملاً) → context=3000, tokens=900, ≈ 15s
# ─────────────────────────────────────────────────────────────────────────────

# مفاتيح تصنيف نوع السؤال — استدلال خفيف بدون LLM
_CONCEPT_PATTERNS: tuple[str, ...] = (
    "ماذا نقصد",
    "ماذا يقصد",
    "ماذا تعني",
    "ماذا يعني",
    "ما المقصود",
    "ما معنى",
    "ما مفهوم",
    "ما هو معنى",
    "ما هي",
    "ما هو",
    "what is",
    "what does",
    "what means",
)

_JUSTIFICATION_PATTERNS: tuple[str, ...] = (
    "لماذا",
    "علِّل",
    "علل",
    "برِّر",
    "برر",
    "why is",
    "why does",
    "justify",
)

_METHOD_PATTERNS: tuple[str, ...] = (
    "كيف نُثبت",
    "كيف نثبت",
    "كيف نحسب",
    "كيف نُبيِّن",
    "كيف نبين",
    "كيف نستنتج",
    "كيف نجد",
    "كيف نُوجد",
    "كيف يصبح",
    "كيف نصل",
    "كيف وصلنا",
    "how to prove",
    "how to compute",
    "how to derive",
)

_FULL_EXPLANATION_PATTERNS: tuple[str, ...] = (
    "اشرح التمرين",
    "شرح التمرين كامل",
    "اشرح الجزء الكامل",
    "اشرح كل",
    "اشرح بالتفصيل",
    "explain everything",
    "explain in detail",
    "detailed explanation",
)


def _classify_question_budget(question: str) -> tuple[int, int, str]:
    """يحدد budget السؤال (context_chars, max_tokens, label).

    ISS-059: تجنُّب تأخُّر «تفصيل معين» — نسأل: ما حجم الإجابة المتوقَّع؟
    سؤال «ماذا نقصد بـ X» لا يستحق 900 token — 350 token كافية ويوفر ~12s.

    Returns:
        (context_chars, max_tokens, classification_label)
    """
    normalized = question.strip().lower()

    if any(p in normalized for p in _FULL_EXPLANATION_PATTERNS):
        return _MAX_EXERCISE_CONTEXT_CHARS, _MAX_EXPLANATION_TOKENS, "full"
    if any(p in normalized for p in _METHOD_PATTERNS):
        return 2000, 600, "method"
    if any(p in normalized for p in _JUSTIFICATION_PATTERNS):
        return 1500, 450, "justification"
    if any(p in normalized for p in _CONCEPT_PATTERNS):
        return 1200, 350, "concept"
    # افتراضي: متوسط (شرح جزء)
    return 2500, 700, "default"


# أنماط تحديد الجزء المطلوب من التمرين
_PART_PATTERNS: dict[str, tuple[str, ...]] = {
    "I": (
        "الجزء الأول",
        "الجزء i",
        "part i",
        "part 1",
        "الجزء 1",
        "g(x)",
        "الدالة g",
        "دالة g",
        "السؤال الأول",
    ),
    "II": (
        "الجزء الثاني",
        "الجزء ii",
        "part ii",
        "part 2",
        "الجزء 2",
        "f(x)",
        "الدالة f",
        "دالة f",
        "السؤال الثاني",
    ),
    "III": (
        "الجزء الثالث",
        "الجزء iii",
        "part iii",
        "part 3",
        "الجزء 3",
        "h(x)",
        "الدالة h",
        "دالة h",
        "التكامل",
        "الدالة الأصلية",
        "السؤال الثالث",
    ),
}

# حدود الأجزاء في الإجابة النموذجية
_PART_SECTION_MARKERS: dict[str, str] = {
    "I": "### الجزء I",
    "II": "### الجزء II",
    "III": "### الجزء III",
}


def _detect_requested_part(question: str) -> str | None:
    """
    يكشف عن الجزء المطلوب من التمرين (I / II / III).

    يُستخدم لتقطيع السياق ذكياً — بدلاً من إرسال 9670 حرف كاملة،
    نُرسل فقط الجزء المطلوب (~1500-2500 حرف).

    Returns:
        "I" | "II" | "III" | None (إذا لم يُحدَّد جزء معين)
    """
    normalized = question.strip().lower()
    for part, patterns in _PART_PATTERNS.items():
        if any(p in normalized for p in patterns):
            return part
    return None


def _extract_part_context(full_content: str, part: str) -> str:
    """
    يستخرج سياق جزء محدد من المحتوى الكامل.

    يُرجع: نص التمرين للجزء المطلوب + الإجابة النموذجية لنفس الجزء فقط.
    """
    marker = _PART_SECTION_MARKERS.get(part)
    if not marker:
        return full_content[:_MAX_EXERCISE_CONTEXT_CHARS]

    # استخراج الجزء من الإجابة النموذجية
    start_idx = full_content.find(marker)
    if start_idx == -1:
        return full_content[:_MAX_EXERCISE_CONTEXT_CHARS]

    # إيجاد نهاية الجزء (بداية الجزء التالي أو نهاية الملف)
    parts_order = ["I", "II", "III"]
    current_idx = parts_order.index(part) if part in parts_order else -1
    end_idx = len(full_content)
    if current_idx >= 0 and current_idx + 1 < len(parts_order):
        next_marker = _PART_SECTION_MARKERS.get(parts_order[current_idx + 1], "")
        next_idx = full_content.find(next_marker, start_idx + 1)
        if next_idx != -1:
            end_idx = next_idx

    part_solution = full_content[start_idx:end_idx].strip()

    # استخراج نص التمرين للجزء نفسه (من نص التمرين الأصلي)
    # نبحث عن "**I.**" أو "**II.**" أو "**III.**" في نص التمرين
    roman_map = {"I": "**I.**", "II": "**II.**", "III": "**III.**"}
    roman_next = {"I": "**II.**", "II": "**III.**", "III": None}
    q_marker = roman_map.get(part, "")
    q_start = full_content.find(q_marker)
    q_end = len(full_content)
    next_q = roman_next.get(part)
    if next_q:
        nq_idx = full_content.find(next_q, q_start + 1) if q_start != -1 else -1
        if nq_idx != -1:
            q_end = nq_idx

    question_text = full_content[q_start:q_end].strip() if q_start != -1 else ""

    # دمج نص التمرين + الإجابة النموذجية للجزء فقط
    combined = ""
    if question_text:
        combined += f"## نص الجزء {part}\n\n{question_text}\n\n---\n\n"
    combined += f"## الإجابة النموذجية — الجزء {part}\n\n{part_solution}"

    # تأكد من عدم تجاوز الحد الأقصى
    if len(combined) > _MAX_EXERCISE_CONTEXT_CHARS * 2:
        combined = combined[: _MAX_EXERCISE_CONTEXT_CHARS * 2]

    return combined


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

    # ISS-059 (D-053): تصنيف السؤال لتحديد budget مناسب — يحل كارثة التأخير
    # عند طلبات «تفصيل معين». سؤال «ماذا نقصد» يحصل على 350 token (≈ 6s إجمالي)
    # بدل 900 token (≈ 15s)، مع context أصغر يُسرِّع TTFB أيضاً.
    context_budget, token_budget, q_class = _classify_question_budget(sanitized_question)

    # ISS-055: تقطيع ذكي للسياق — نُرسل فقط الجزء المطلوب بدلاً من 9670 حرف كاملة
    requested_part = _detect_requested_part(sanitized_question)
    if requested_part:
        trimmed_content = _extract_part_context(exercise_full_content, requested_part)
        # ISS-059: قصّ إضافي للسياق حسب budget السؤال
        if len(trimmed_content) > context_budget:
            trimmed_content = trimmed_content[:context_budget]
        context_label = f"الجزء {requested_part} ({q_class})"
    elif len(exercise_full_content) > context_budget:
        # طلب عام بدون تحديد جزء — نُرسل الجزء الأول كنقطة بداية
        trimmed_content = _extract_part_context(exercise_full_content, "I")
        if len(trimmed_content) > context_budget:
            trimmed_content = trimmed_content[:context_budget]
        context_label = f"الجزء I ({q_class})"
    else:
        trimmed_content = exercise_full_content
        context_label = f"كامل ({q_class})"

    # بناء رسالة المستخدم مع السياق المُقلَّص للتمرين
    context_block = f"## محتوى التمرين ({context_label})\n\n{trimmed_content}\n\n---\n\n"

    if history_text:
        user_message = (
            f"{context_block}"
            f"## سياق المحادثة السابقة\n{history_text}\n\n"
            f"## طلب الطالب الحالي\n{sanitized_question}"
        )
    else:
        user_message = f"{context_block}## طلب الطالب\n{sanitized_question}"

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
                "context_budget": context_budget,  # ISS-059
                "token_budget": token_budget,  # ISS-059
                "q_class": q_class,  # ISS-059
            },
        )
        obs.increment_counter(
            "langgraph.intent.total",
            labels={"intent": "exercise_explanation", "graph": "local"},
        )
        # ISS-059: تتبُّع budget classification في Grafana
        obs.increment_counter(
            "langgraph.q_class.total",
            labels={"q_class": q_class, "graph": "local"},
        )

    ai_client = get_ai_client()
    messages: list[dict[str, str]] = [
        {"role": "system", "content": _EXERCISE_EXPLANATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    chunk_count = 0
    total_chars = 0
    try:
        # ISS-059 (D-053): max_tokens ديناميكي حسب نوع السؤال
        # CONCEPT=350 | JUSTIFICATION=450 | METHOD=600 | DEFAULT=700 | FULL=900
        async for raw_chunk in ai_client.stream_chat(messages, max_tokens=token_budget):
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
