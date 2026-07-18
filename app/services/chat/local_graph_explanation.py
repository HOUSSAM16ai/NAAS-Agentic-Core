"""شرح تمرين بكالوريا بسياق (D-170 Stage D — مُستخرَج حرفياً من local_graph).

ميزانيات الأسئلة الواعية (ISS-059/D-053) + تقطيع الأجزاء (ISS-055) +
`run_local_graph_with_exercise_context` (ISS-053). مُستخرَج حرفياً؛ `local_graph`
يعيد تصديره — المستهلكون الخارجيون (local_fallback / bac_exercise_skill) بلا تغيير.
`_format_history` يُستورَد lazy داخل الدالة (قاعدة late-binding D-168 — يتجنّب
دائرية الاستيراد مع local_graph الذي يعيد تصدير هذه الوحدة).
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections.abc import AsyncGenerator

from app.services.skills.doctrine import (
    EXERCISE_EXPLANATION_SYSTEM_PROMPT as _EXERCISE_EXPLANATION_SYSTEM_PROMPT,
)

logger = logging.getLogger("cogniforge.local_graph")


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

    # D-170: late-binding (قاعدة D-168) — يتجنّب دائرية الاستيراد مع local_graph
    # الذي يعيد تصدير هذه الوحدة. `_format_history` يبقى مُعرَّفاً في local_graph.
    from app.services.chat.local_graph import _format_history

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
        # ISS-107: حارس اللغة العربية على شرح التمرين أيضاً (لا إنجليزية/غارباج).
        from app.services.skills.arabic_stream_guard import guard_arabic_stream

        # ISS-114 (D-106): طبقة نزاهة المحتوى فوق حارس اللغة. fail-open.
        _integrity = None
        try:
            from app.services.skills.content_integrity_skill import StreamIntegrityFilter

            _integrity = StreamIntegrityFilter()
        except Exception:  # pragma: no cover - fail-open
            _integrity = None

        # D-113 (ISS-115): حجب per-chunk للـ \boxed المباشر (النتائج اللفظية
        # تُحجب نهائياً عبر sanitize_final_text على الإطار النهائي).
        try:
            from app.services.skills.answer_redaction_skill import redact_chunk
        except Exception:  # pragma: no cover - fail-open

            def redact_chunk(text: str) -> str:
                return text

        async for clean in guard_arabic_stream(ai_client, messages, max_tokens=token_budget):
            if not clean:
                continue
            emit = clean
            if _integrity is not None:
                emit = _integrity.feed(clean)
                if not emit:
                    continue
            emit = redact_chunk(emit)
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
