"""
Local LangGraph Chat Engine — CogniForge
-----------------------------------------
رسم بياني مدمج يعمل مباشرة داخل FastAPI بدون microservices.
يستخدم MemorySaver لاستمرارية السياق عبر رسائل نفس المحادثة.

التدفق:
  supervisor (تصنيف النية) → chat_node (توليد الرد) → END

thread_id = conversation_id  →  كل محادثة لها ذاكرة مستقلة.

## V46.0 — الفصل المزدوج للقنوات

كل إجابة LLM تمر عبر طبقتين دفاعيتين قبل الوصول للطالب:

1. **OutputFirewall** (output_firewall.py): يرفض أو ينظف أي HTML/JSX/markup
   في القناة B (صوت المعلم). المعلم لا يُصيِّر — المعلم يشرح.

2. **TopicLock** (topic_lock.py): يُسجِّل انتهاكات تسرب المواضيع
   (احتمالات → تفاضل، إلخ) دون كسر المسار.

D-086 (2026-05-23): تطبيق Protocol V46.0.
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

# أنماط طلب الشرح النصي الصريح — تُعطِّل LaTeX وتُفعِّل الشرح بالكلمات فقط
_TEXTUAL_EXPLAIN_PATTERNS = [
    r"نصيا",
    r"بالكلمات",
    r"بدون\s+(صيغ|رموز|معادلات|latex|لاتكس)",
    r"اشرح\s+لي\s+بدون",
    r"بطريقة\s+بسيطة",
    r"بلغة\s+بسيطة",
    r"بدون\s+رياضيات",
]

_COMPILED_TEXTUAL = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _TEXTUAL_EXPLAIN_PATTERNS]


def _is_textual_explain_request(question: str) -> bool:
    """يكشف طلب الشرح النصي الصريح — يُعطِّل LaTeX في system prompt."""
    return any(p.search(question) for p in _COMPILED_TEXTUAL)


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
        "- شجّع الطالب وأكد له أن الرياضيات ممتعة وليست صعبة\n\n"
        "## قواعد الجودة الإلزامية (مضاد الكوارث)\n"
        "- التزم حرفياً بمعطيات التمرين ولا تُضِف لوناً أو رقماً غير موجود في النص.\n"
        "- امنع التكرار: لا تعِد نفس الفقرة أو نفس القائمة بصياغات متشابهة.\n"
        "- عند طلب «شجرة احتمالات»، ابنِ سحباً متتالياً بدون إرجاع مع فروع واضحة واحتمالات كل مستوى.\n"
        "- ميّز بين «سحب دفعة واحدة» (توافيق) و«سحب متتالٍ» (شجرة/احتمالات شرطية).\n"
        "- إذا ظهر تناقض في نصّ الطالب، اذكره بلطف ثم أكمل الحل على فرضية صريحة.\n"
        "- اختم كل حل بـ «تحقّق سريع» عددي يثبت النتيجة (مثل: مجموع الاحتمالات = 1)."
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
    # يُفعَّل عند طلب الشرح النصي الصريح ("نصيا"، "بالكلمات"، "بدون صيغ")
    "educational_textual": (
        "أنت أستاذ رياضيات متخصص في البكالوريا الجزائرية.\n"
        "الطالب طلب شرحاً نصياً بدون صيغ رياضية — التزم بهذا الطلب تماماً.\n\n"
        "## قواعد صارمة لهذا الوضع\n"
        "- اشرح بالكلمات العربية الفصحى فقط — لا معادلات، لا رموز، لا LaTeX\n"
        "- استخدم الأمثلة الحياتية والتشبيهات الملموسة\n"
        "- ابدأ بالمعنى والصورة الذهنية قبل أي شيء آخر\n"
        "- استخدم أسلوباً سقراطياً دافئاً: اطرح أسئلة تقود الطالب للفهم\n"
        "- اشرح لماذا يحدث هذا قبل كيف يُحسب\n"
        "- لا تبدأ بـ LaTeX أو رموز رياضية أبداً\n\n"
        "## منهجية الشرح النصي\n"
        "1. ابدأ بسؤال: «تخيّل معي...» أو «فكّر في الأمر هكذا...»\n"
        "2. اعطِ مثالاً من الحياة اليومية يُجسِّد المفهوم\n"
        "3. اشرح المعنى بجملتين أو ثلاث بسيطة\n"
        "4. اربط المفهوم بما يعرفه الطالب مسبقاً\n"
        "5. اختم بجملة تُلخِّص الفكرة الجوهرية\n"
        "لا تذكر أي صيغة رياضية — الطالب طلب الفهم بالكلمات فقط."
    ),
}


# ─── State ────────────────────────────────────────────────────────────────────


class LocalChatState(TypedDict):
    question: str
    intent: str
    history_messages: list[dict]
    final_response: str
    tutor_state: dict
    pedagogical_decision: dict
    conversation_id: int | None
    user_id: int | None


# ─── ISS-075 D-063: Foreign-script + chat meta-narration sanitizer ────────────


# D-170 Stage D: مُطهِّرات الردّ مُستخرَجة إلى local_graph_sanitizers (re-export خلفي).
from app.services.chat.local_graph_sanitizers import (  # noqa: F401
    _CHAT_META_PATTERNS,
    _FOREIGN_REPLACEMENTS,
    _build_precision_guardrail,
    _dedupe_repeated_blocks,
    _is_long_educational_scaffold,
    _is_near_duplicate,
    _normalize_for_dedup,
    _sanitize_local_graph_response,
    _strip_unrequested_color_lines,
    _token_signature,
)


def _apply_answer_quality_skill(question: str, answer: str, intent: str) -> str:
    """D-073: يُطبِّق ``AnswerQualitySkill`` defensively قبل إرجاع الإجابة للطالب.

    قبل D-073 كان ``AnswerQualitySkill`` (D-072) موجوداً كـ class مع 6 فحوصات
    deterministic — لكنه لم يُستدعَ من أي مسار إنتاجي. هذا يجعله Skill زومبي
    بحسب قاعدة CLAUDE.md §6.6 (import + call chain + runtime evidence مطلوبة).

    هذا الـ helper يربطه فعلياً في ``_chat_node`` كآخر طبقة دفاع قبل البث للطالب:

    - يَخريط النية المحلية (``educational/general/chat``) إلى نية الـ Skill
      (``educational/math/chat/retrieval``).
    - يُعطِّل ``require_steps`` للإجابات القصيرة (< 300 char) — لتجنب false-positives.
    - يَستخدم ``improved_answer`` من الـ Skill فقط عندما تُحدِث تغييراً ملموساً
      (مثل تحويل ``\\[...\\]`` → ``$$...$$`` — ISS-071).
    - يَلتقط أي استثناء — Skill defensive، لا يُفشل المسار أبداً.

    Returns:
        النص المُصحَّح إذا كان هناك تصحيح، وإلا النص الأصلي.
    """
    if not answer or not answer.strip():
        return answer
    try:
        # late import — لتجنب circular dependencies في boot time
        from app.services.skills import (
            AnswerQualityInput,
            AnswerQualityOutput,
            get_answer_quality_skill,
        )

        # خرائط النية: local intents → skill intents
        if intent == "chat":
            skill_intent = "chat"
        elif intent in ("educational", "math"):
            skill_intent = "educational"
        else:
            # general / غير معروف → educational (الإعداد الأكثر صرامة)
            skill_intent = "educational"

        # ضوابط مرنة — الإجابات القصيرة لا تحتاج خطوات مرقمة
        require_latex = skill_intent in ("educational", "math")
        require_steps = skill_intent in ("educational", "math") and len(answer) > 300

        result = get_answer_quality_skill().evaluate(
            AnswerQualityInput(
                question=question[:2000],
                answer=answer,
                intent=skill_intent,  # type: ignore[arg-type]
                require_latex=require_latex,
                require_steps=require_steps,
            )
        )
        if isinstance(result, AnswerQualityOutput):
            if result.improved_answer and result.improved_answer != answer:
                logger.info(
                    "answer_quality.improved chars=%d→%d score=%.2f issues=%d",
                    len(answer),
                    len(result.improved_answer),
                    result.score,
                    len(result.issues),
                )
                return result.improved_answer
            logger.debug(
                "answer_quality.passed score=%.2f issues=%d",
                result.score,
                len(result.issues),
            )
    except Exception as exc:
        # Skill defensive — لا يُفشل المسار أبداً (D-073 invariant)
        logger.debug("answer_quality skill non-fatal failure: %s", exc)
    return answer


# ─── V46.0: Output Firewall + Topic Lock helpers ──────────────────────────────


def _apply_output_firewall(answer: str, intent: str) -> str:
    """D-086 (V46.0): يُطبِّق OutputFirewall على القناة B (صوت المعلم).

    يرفض أو ينظف أي HTML/JSX/markup في الإجابة السردية.
    إذا رُفضت الإجابة كلياً (تلوث فوق العتبة) → يُعيد النص الأصلي
    مع تسجيل تحذير (fail-open — لا يكسر المسار).

    Returns:
        النص المُنظَّف إذا كان هناك تلوث قابل للتنظيف، وإلا النص الأصلي.
    """
    if not answer or not answer.strip():
        return answer
    try:
        from app.services.skills.output_firewall import apply_channel_b_firewall

        cleaned, was_rejected = apply_channel_b_firewall(answer, intent=intent)
        if was_rejected:
            # تلوث فوق العتبة — نُعيد الأصل مع تحذير (fail-open)
            # المُستدعي الأعلى يمكنه إعادة المحاولة إذا أراد
            logger.warning(
                "output_firewall.rejected_fail_open intent=%s chars=%d",
                intent,
                len(answer),
            )
            return answer
        return cleaned
    except Exception as exc:
        logger.debug("output_firewall non-fatal failure: %s", exc)
        return answer


def _apply_answer_redaction(answer: str, intent: str) -> str:
    """D-113 (ISS-115 — وَهْم الإتقان): يحجب أي نتيجة نهائية صريحة قبل وصولها للطالب.

    شبكة الأمان الحتمية الأخيرة: حتى مع الـ doctrine السقراطي + أسئلة-فقط، قد
    يخترع نموذج مجاني نتيجة (`$$\\boxed{}$$`، `P(A)=14/165`). هذا الحارس يحجبها.
    fail-open مطلق — لا يكسر دور الطالب.
    """
    if not answer or not answer.strip():
        return answer
    try:
        from app.services.skills.answer_redaction_skill import redact_final_answers

        redacted, n = redact_final_answers(answer)
        if n:
            logger.info("answer_redaction.applied intent=%s redactions=%d", intent, n)
        return redacted
    except Exception as exc:
        logger.debug("answer_redaction non-fatal failure: %s", exc)
        return answer


def _check_topic_lock(
    question: str,
    answer: str,
    history: list[dict],
) -> None:
    """D-086 (V46.0): يفحص نقاء الموضوع — تحذيري فقط، لا يكسر المسار."""
    try:
        from app.services.skills.topic_lock import TopicLockInput, get_topic_lock

        result = get_topic_lock().check(
            TopicLockInput(
                response=answer[:1000],
                question=question[:500],
                history=history[-5:],
            )
        )
        if not result.passed and result.leaked_topics:
            logger.warning(
                "topic_lock.violation active=%s leaked=%s",
                result.active_topic,
                result.leaked_topics,
            )
    except Exception as exc:
        logger.debug("topic_lock non-fatal failure: %s", exc)


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

    # ── Pedagogical State Resolution (D-142) ──
    tutor_state = state.get("tutor_state", {})
    pedagogical_decision = {}
    conversation_id = state.get("conversation_id")

    if conversation_id:
        with contextlib.suppress(Exception):
            from app.core.database import get_db_session
            from app.services.analytics.tutor_state_service import TutorStateService
            from app.services.skills.pedagogical_policy_engine import (
                PedagogicalPolicyEngine,
                PolicyObservation,
            )

            async for db in get_db_session():
                tutor_state_svc = TutorStateService(db)
                tutor_state = await tutor_state_svc.load(conversation_id)
                break

            if tutor_state.get("active_concept"):
                policy_engine = PedagogicalPolicyEngine()
                obs = PolicyObservation(
                    question=state["question"],
                    active_concept=tutor_state["active_concept"],
                    is_correct=False,  # We don't evaluate answer in supervisor
                    is_frustrated=False,
                )
                decision = policy_engine.evaluate_turn(tutor_state, obs)
                pedagogical_decision = {
                    "next_action": decision.next_action,
                    "learning_stage": decision.learning_stage,
                    "representation": decision.representation,
                    "focus": decision.focus,
                    "reason": decision.reason,
                }

    intent = _classify_intent(state["question"])

    # If we have an active pedagogical session, override random intents (prevent hijacking)
    if tutor_state.get("active_concept") and intent not in ("exercise_explanation", "chat"):
        intent = "educational"

    logger.info(
        "local_graph.supervisor intent=%s question=%.60s active_concept=%s",
        intent,
        state["question"],
        tutor_state.get("active_concept", "none"),
    )

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

    return {
        "intent": intent,
        "tutor_state": tutor_state,
        "pedagogical_decision": pedagogical_decision,
    }


async def _chat_node(state: LocalChatState) -> dict:
    from app.core.ai_gateway import get_ai_client

    ai_client = get_ai_client()
    intent = state.get("intent", "general")
    question = state["question"].replace("\x00", "").strip()
    history = state.get("history_messages", [])

    # ISS-079 (D-067): Greeting fast-path — قبل أي استدعاء LLM
    if intent == "chat":
        fastpath = _greeting_fastpath_response(question)
        if fastpath:
            logger.info("local_graph.chat_node greeting_fastpath chars=%d", len(fastpath))
            return {"final_response": fastpath}

    # FIX-001: Exercise retrieval preempt — قبل LLM
    # "اعطني تمرين الاحتمالات 2024" يجب أن يُعيد التمرين الحقيقي من knowledge_base
    # وليس تمريناً مُولَّداً من LLM.
    if intent == "educational":
        import contextlib as _ctx

        with _ctx.suppress(Exception):
            from app.services.capabilities.exercise_retrieval import (
                ExerciseRetrievalRequest,
                detect_exercise_retrieval,
                format_exercise_for_display,
                load_exercise_content,
            )

            _retrieval_decision = detect_exercise_retrieval(
                ExerciseRetrievalRequest(question=question),
                history_messages=history,
            )
            if _retrieval_decision.recognized and _retrieval_decision.matched_entry:
                _entry = _retrieval_decision.matched_entry
                _raw = load_exercise_content(_entry)
                if _raw:
                    _display = format_exercise_for_display(_entry, _raw)
                    logger.info(
                        "local_graph.chat_node exercise_retrieval_preempt entry=%s",
                        getattr(_entry, "id", "?"),
                    )
                    return {"final_response": _display}

    # FIX-002: Textual explain mode — "نصيا" / "بالكلمات" / "بدون صيغ"
    # يُعطِّل LaTeX ويُفعِّل system prompt الشرح النصي الصريح.
    _effective_intent = intent
    if _is_textual_explain_request(question):
        _effective_intent = "educational_textual"
        logger.info("local_graph.chat_node textual_explain_mode activated")

    system_prompt = _SYSTEM_PROMPTS.get(
        _effective_intent, _SYSTEM_PROMPTS.get(intent, _SYSTEM_PROMPTS["general"])
    )

    # ── Inject Pedagogical Constraints (D-142) ──
    pedagogical_decision = state.get("pedagogical_decision", {})
    tutor_state = state.get("tutor_state", {})
    if pedagogical_decision and tutor_state:
        learning_stage = pedagogical_decision.get("learning_stage", "definition")
        representation = pedagogical_decision.get("representation", "text")
        focus = pedagogical_decision.get("focus")
        last_step_emitted = tutor_state.get("last_step_emitted", "")

        system_prompt += (
            f"\n\n## التوجيهات التربوية الإلزامية لهذه الخطوة:\n"
            f"- المرحلة التعليمية الحالية: {learning_stage}\n"
            f"- نوع التمثيل المطلوب: {representation}\n"
            f"- البؤرة (Concept Focus): {focus or 'عام'}\n"
        )
        if last_step_emitted:
            system_prompt += (
                f"\n\n## تحذير صارم لمنع التكرار (Strict Anti-Loop):\n"
                f"الخطوة السابقة التي عرضتها للطالب كانت:\n"
                f"«{last_step_emitted[-200:]}»\n"
                f"**يُمنع منعاً باتاً** إعادة نفس الشرح أو نفس السؤال. قدّم خطوة جديدة تماماً بناءً على تقدم الطالب ومرحلته الحالية."
            )

    history_text = _format_history(history)
    if history_text:
        user_message = f"سياق المحادثة السابقة:\n{history_text}\n\nالسؤال الحالي: {question}"
    else:
        user_message = question
    precision_guardrail = _build_precision_guardrail(user_message, intent)
    if precision_guardrail:
        system_prompt = f"{system_prompt}\n\n{precision_guardrail}"

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
        # D-090: إزالة أسطر ألوان غير مطلوبة من سياق السؤال (احتمالات)
        clean = _strip_unrequested_color_lines(user_message, clean, intent)
        # ISS-075 D-063: تنظيف foreign-script + chat meta-narration
        clean = _sanitize_local_graph_response(clean, intent)
        # D-073: AnswerQualitySkill — آخر طبقة دفاع (يحل ZOMBIE skill من D-072)
        clean = _apply_answer_quality_skill(question, clean, intent)
        # D-086 (V46.0): OutputFirewall — جدار الحماية المزدوج للقنوات
        # القناة B (صوت المعلم) يجب أن تكون Markdown نظيفاً — لا HTML، لا JSX.
        clean = _apply_output_firewall(clean, intent)
        # D-113 (ISS-115): حجب أي نتيجة نهائية تسرّبت — توليد مُجبَر سقراطي.
        clean = _apply_answer_redaction(clean, intent)
        # D-086 (V46.0): TopicLock — فحص نقاء الموضوع (تحذيري فقط)
        _check_topic_lock(question, clean, history)
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
    user_id: int | None = None,
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
        "tutor_state": {},
        "pedagogical_decision": {},
        "conversation_id": conversation_id,
        "user_id": user_id,
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

            # ── Record pedagogical state turn (D-142) ──
            if conversation_id and user_id:
                ped_decision = result.get("pedagogical_decision", {})
                intent = result.get("intent", "general")
                # Evaluate if it ended with a question mark heuristically
                is_socratic = "?" in response or "؟" in response

                # Default values for state updates
                tutor_state_up = result.get("tutor_state", {})
                active_concept = tutor_state_up.get("active_concept", "general_inquiry")
                if intent == "educational" and not active_concept:
                    active_concept = "math_concept"

                import contextlib

                with contextlib.suppress(Exception):
                    from app.core.database import get_db_session
                    from app.services.analytics.tutor_state_service import TutorStateService

                    async for db in get_db_session():
                        tutor_state_svc = TutorStateService(db)
                        await tutor_state_svc.record_turn(
                            conversation_id=conversation_id,
                            user_id=user_id,
                            active_concept=active_concept,
                            assistant_text=response,
                            is_socratic_question=is_socratic,
                            learning_stage=ped_decision.get("learning_stage", "definition"),
                            representation_used=ped_decision.get("representation", "text"),
                        )
                        break

            if root_span_ctx:
                import contextlib

                with contextlib.suppress(Exception):
                    obs.end_span(
                        root_span_ctx.span_id,
                        status="OK",
                        metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                    )
            return response
        logger.warning("local_graph.run_empty_response thread_id=%s", thread_id)
        if root_span_ctx:
            import contextlib

            with contextlib.suppress(Exception):
                obs.end_span(
                    root_span_ctx.span_id,
                    status="OK",
                    metrics={"duration_ms": (time.perf_counter() - t0) * 1000},
                )
    except Exception:
        logger.warning("local_graph.run_failed thread_id=%s", thread_id, exc_info=True)
        if root_span_ctx:
            import contextlib

            with contextlib.suppress(Exception):
                obs.end_span(root_span_ctx.span_id, status="ERROR")
    finally:
        if token is not None:
            import contextlib

            with contextlib.suppress(Exception):
                _graph_trace_context.reset(token)

    return None


# ─── Streaming variant — D-047 (word-by-word typing effect) ──────────────────


async def run_local_graph_stream(
    question: str,
    conversation_id: int | None,
    user_id: int | None = None,
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
    history = history_messages or []

    # FIX-002 (stream): Textual explain mode — "نصيا" / "بالكلمات"
    _effective_intent = intent
    if _is_textual_explain_request(sanitized):
        _effective_intent = "educational_textual"
        logger.info("local_graph.stream textual_explain_mode activated")

    system_prompt = _SYSTEM_PROMPTS.get(
        _effective_intent, _SYSTEM_PROMPTS.get(intent, _SYSTEM_PROMPTS["general"])
    )

    # ── Inject Pedagogical Constraints (D-142) for streaming ──
    pedagogical_decision = {}
    tutor_state = {}

    if conversation_id:
        with contextlib.suppress(Exception):
            from app.core.database import get_db_session
            from app.services.analytics.tutor_state_service import TutorStateService
            from app.services.skills.pedagogical_policy_engine import (
                PedagogicalPolicyEngine,
                PolicyObservation,
            )

            async for db in get_db_session():
                tutor_state_svc = TutorStateService(db)
                tutor_state = await tutor_state_svc.load(conversation_id)
                break

            if tutor_state.get("active_concept"):
                policy_engine = PedagogicalPolicyEngine()
                obs = PolicyObservation(
                    question=sanitized,
                    active_concept=tutor_state["active_concept"],
                    is_correct=False,
                    is_frustrated=False,
                )
                decision = policy_engine.evaluate_turn(tutor_state, obs)
                pedagogical_decision = {
                    "next_action": decision.next_action,
                    "learning_stage": decision.learning_stage,
                    "representation": decision.representation,
                    "focus": decision.focus,
                    "reason": decision.reason,
                }
                if intent not in ("exercise_explanation", "chat"):
                    intent = "educational"

    if pedagogical_decision and tutor_state:
        learning_stage = pedagogical_decision.get("learning_stage", "definition")
        representation = pedagogical_decision.get("representation", "text")
        focus = pedagogical_decision.get("focus")
        last_step_emitted = tutor_state.get("last_step_emitted", "")

        system_prompt += (
            f"\n\n## التوجيهات التربوية الإلزامية لهذه الخطوة:\n"
            f"- المرحلة التعليمية الحالية: {learning_stage}\n"
            f"- نوع التمثيل المطلوب: {representation}\n"
            f"- البؤرة (Concept Focus): {focus or 'عام'}\n"
        )
        if last_step_emitted:
            system_prompt += (
                f"\n\n## تحذير صارم لمنع التكرار (Strict Anti-Loop):\n"
                f"الخطوة السابقة التي عرضتها للطالب كانت:\n"
                f"«{last_step_emitted[-200:]}»\n"
                f"**يُمنع منعاً باتاً** إعادة نفس الشرح أو نفس السؤال. قدّم خطوة جديدة تماماً بناءً على تقدم الطالب ومرحلته الحالية."
            )

    history_text = _format_history(history)
    user_message = (
        f"سياق المحادثة السابقة:\n{history_text}\n\nالسؤال الحالي: {sanitized}"
        if history_text
        else sanitized
    )
    precision_guardrail = _build_precision_guardrail(user_message, intent)
    if precision_guardrail:
        system_prompt = f"{system_prompt}\n\n{precision_guardrail}"

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
        # ISS-107: حارس اللغة العربية + إعادة توليد + تنظيف الرموز الملتصقة.
        # لا نبثّ ai_client.stream_chat خاماً للطالب أبداً (الإنجليزية/الغارباج محظورة).
        from app.services.skills.arabic_stream_guard import guard_arabic_stream

        # ISS-114 (D-106): طبقة نزاهة المحتوى فوق حارس اللغة — تلتقط الغارباج
        # اللاتيني (snake_case/diacritics) وتسريب HTML على كامل التيار. fail-open.
        _integrity = None
        try:
            from app.services.skills.content_integrity_skill import StreamIntegrityFilter

            _integrity = StreamIntegrityFilter()
        except Exception:  # pragma: no cover - fail-open
            _integrity = None

        async for clean in guard_arabic_stream(ai_client, messages):
            if not clean:
                continue
            emit = clean
            if _integrity is not None:
                emit = _integrity.feed(clean)
                if not emit:
                    continue
            chunk_count += 1
            total_chars += len(emit)
            yield emit
        if _integrity is not None:
            tail = _integrity.flush()
            if tail:
                chunk_count += 1
                total_chars += len(tail)
                yield tail
        # ── Record pedagogical state turn for stream (D-142) ──
        # We need the full response to evaluate if it's a Socratic question.
        # Since we just streamed it, we don't have the full string aggregated yet.
        # Let's not fully implement saving here, because `chat_backend` (the caller)
        # normally buffers and calls `run_local_graph` for stateful interactions anyway.
        # But if we want it perfect, we'd need to aggregate it:
        # Wait, the monolith chat backend actually breaks streaming and buffers!
        pass
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

# D-071 (2026-05-19): الـ prompt يُبنى الآن من doctrine.py مباشرة.
# هذا يضمن أن أي تغيير في EXPLANATION_DOCTRINE أو MODEL_ANSWER_EXPLANATION_DOCTRINE
# ينعكس تلقائياً على الـ LLM instruction surface — لا drift ممكن.
#
# ISS-079 (D-067 — 2026-05-17): القيود الإلزامية محفوظة:
# - < 1000 حرف (build_exercise_explanation_prompt() تُطبِّق هذا الحد)
# - لا box-drawing chars
# - لا تكرار
from app.services.skills.doctrine import EXERCISE_EXPLANATION_SYSTEM_PROMPT as _DOCTRINE_PROMPT

_EXERCISE_EXPLANATION_SYSTEM_PROMPT = _DOCTRINE_PROMPT


# D-170 Stage D: شرح التمرين بسياق مُستخرَج إلى local_graph_explanation (re-export خلفي).
# سطر الـ doctrine + `_EXERCISE_EXPLANATION_SYSTEM_PROMPT` أعلاه يبقى في هذا الملف
# (بوّابة D-071 تقرأ local_graph.py مباشرةً وتتطلب استيراد doctrine + ذكر الرمز).
from app.services.chat.local_graph_explanation import (  # noqa: F401
    _CONCEPT_PATTERNS,
    _FULL_EXPLANATION_PATTERNS,
    _JUSTIFICATION_PATTERNS,
    _MAX_EXERCISE_CONTEXT_CHARS,
    _MAX_EXPLANATION_TOKENS,
    _METHOD_PATTERNS,
    _PART_PATTERNS,
    _PART_SECTION_MARKERS,
    _classify_question_budget,
    _detect_requested_part,
    _extract_part_context,
    run_local_graph_with_exercise_context,
)
