"""ArabicStreamGuard — حارس اللغة العربية على البثّ الحي (ISS-107).

المشكلة (تجريب حي 2026-06-02):
    سلسلة النماذج الاحتياطية تنحدر عند ضغط gpt-oss إلى نماذج تُخرِج إنجليزية
    في حقل ``content`` (مثل ``nemotron-3-super-120b`` → "We need to respond in
    Arabic...") أو فراغاً (reasoning-only مثل ``glm-4.5-air``). مسار البثّ الحي
    في ``local_graph.run_local_graph_stream`` و ``run_local_graph_with_exercise_context``
    كان يبثّ هذه القطع الخام **بلا أي فحص لغة** → الطالب يرى الإنجليزية/الغارباج.

الحل (هذا الـ Skill — يحترم §0.5 و D-047):
    1. نخزّن **نافذة أولى صغيرة فقط** (~200 حرف) دون إصدار.
    2. نفحص اللغة على **النثر** (بعد إزالة LaTeX/الرياضيات — لأن LaTeX يضخّم اللاتينية
       فيُسيء تصنيف العربية الصحيحة؛ gpt-oss-20b الصحيح كان نسبته الخام 0.57).
    3. عربية → أصدِر النافذة ثم تابع البثّ، مع تنظيف كل قطعة (حذف الرموز الملتصقة
       «أستاذochemistry» → «أستاذ» + Cyrillic/CJK).
    4. إنجليزي/غارباج → **لا تُصدِر النافذة**؛ أعِد التوليد مرّة بـ system prompt
       عربي صارم (سلسلة النماذج كاملة من جديد). إن فشل ثانيةً → أصدِر رسالة عربية
       نظيفة بدل الغارباج (لا silent failure، لا إنجليزية تصل للطالب).

القاعدة الدائمة (ISS-107): أي مسار بثّ يُولِّد إجابة للطالب يجب أن يمرّ عبر
``guard_arabic_stream``. لا تبثّ ``ai_client.stream_chat`` خاماً للطالب أبداً.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger("cogniforge.skills.arabic_stream_guard")

# ─── مقاييس Prometheus — استيراد دفاعي (registry مستقل لكل skill — §6 doctrine) ──
# نمط الكود: لا يجوز أن يفشل استيراد الـ skill بسبب غياب prometheus_client
# (بوّابات CI minimal-deps تستورد الحزمة عبر __init__ بدون prometheus).
try:
    from prometheus_client import CollectorRegistry, Counter

    _REGISTRY = CollectorRegistry()
    _GUARD_CHECKS = Counter(
        "cogniforge_skill_lang_guard_checks_total",
        "عدد فحوصات نافذة اللغة على البثّ الحي",
        ["result"],  # arabic | rejected
        registry=_REGISTRY,
    )
    _GUARD_REGEN = Counter(
        "cogniforge_skill_lang_guard_regenerations_total",
        "عدد إعادات التوليد بعد رفض النافذة الأولى",
        registry=_REGISTRY,
    )
    _GUARD_FALLBACK = Counter(
        "cogniforge_skill_lang_guard_fallback_total",
        "عدد مرّات إصدار الرسالة العربية النظيفة بعد فشل إعادة التوليد",
        registry=_REGISTRY,
    )
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False


def _record_check(result: str) -> None:
    """يُسجِّل نتيجة فحص نافذة اللغة (arabic | rejected)."""
    if _METRICS_AVAILABLE:
        _GUARD_CHECKS.labels(result=result).inc()


def _record_regen() -> None:
    """يُسجِّل إعادة توليد بعد رفض النافذة الأولى."""
    if _METRICS_AVAILABLE:
        _GUARD_REGEN.inc()


def _record_fallback() -> None:
    """يُسجِّل إصدار الرسالة العربية النظيفة بعد فشل كل المحاولات."""
    if _METRICS_AVAILABLE:
        _GUARD_FALLBACK.inc()


# ─── ثوابت ────────────────────────────────────────────────────────────────────
_WINDOW_CHARS = 200
"""حجم النافذة الأولى المُخزَّنة قبل قرار اللغة (~< 1s زمن أول-قطعة)."""

_ARABIC_RANGE = ("؀", "ۿ")  # كتلة العربية الأساسية

# system prompt عربي صارم لإعادة التوليد (< 1000 حرف — D-067، بلا box-drawing)
_STRICT_ARABIC_PROMPT = (
    "أنت أستاذ بكالوريا جزائري. أجب بالعربية الفصحى فقط.\n"
    "ممنوع منعاً باتاً: أي كلمة إنجليزية أو تفكير بصوت عالٍ (مثل We need / The user / Okay).\n"
    "ابدأ الإجابة مباشرة بالعربية ضمن سياق سؤال الطالب الحالي. لا تُغيّر الموضوع.\n"
    "استخدم LaTeX للرياضيات فقط: $$...$$ للمعادلات و \\(...\\) للرموز."
)

# رسالة عربية نظيفة عند فشل كل المحاولات (بدل الغارباج)
_ARABIC_FALLBACK_MESSAGE = (
    "عذراً، تعذّر توليد إجابة سليمة بالعربية في هذه اللحظة. "
    "يرجى إعادة صياغة سؤالك أو المحاولة مرة أخرى."
)

# كلمات إنجليزية شائعة في تسريب التفكير/الهلوسة (إشارة قوية على الإنجليزية)
_ENGLISH_SIGNAL_WORDS = frozenset(
    {
        "the",
        "we",
        "need",
        "to",
        "is",
        "of",
        "and",
        "a",
        "in",
        "this",
        "that",
        "user",
        "respond",
        "explain",
        "explaining",
        "something",
        "says",
        "want",
        "function",
        "integral",
        "sum",
        "area",
        "let",
        "us",
        "so",
        "therefore",
        "first",
        "okay",
        "alright",
        "should",
        "must",
        "will",
        "here",
        "what",
        "covalent",
        "chemistry",
        "bond",
        "bonds",
        "riemann",
        "limit",
    }
)

# ─── أنماط تنظيف ──────────────────────────────────────────────────────────────
# LaTeX/رياضيات تُزال قبل حساب نسبة اللغة (LaTeX يضخّم اللاتينية)
_LATEX_BLOCK = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
_LATEX_CMD = re.compile(r"\\[a-zA-Z]+")
_MATH_NOISE = re.compile(r"[{}^_\\=+\-*/<>|~`\[\]()]|[0-9]+")
# كتل غير لاتينية/عربية تُحذف من القطع المبثوثة
_FOREIGN_BLOCKS = re.compile(r"[Ѐ-ӿ一-鿿぀-ヿㇰ-ㇿ]+")
# لاتيني ملتصق مباشرةً بحرف عربي (الرمز المشوّه «أستاذochemistry» → «أستاذ»)
_GLUED_LATIN = re.compile(r"(?<=[؀-ۿ])[A-Za-z]{2,}")
_ENGLISH_WORD = re.compile(r"[A-Za-z]{2,}")
# ISS-114 (D-106): رموز snake_case لاتينية («experiences_random») غارباج صريح —
# لا تظهر أبداً في محتوى تعليمي مشروع. تقوية stateless إضافية (المرشّح ذو الحالة
# في content_integrity_skill يغطّي الحالات المقسومة عبر الـ chunks).
_SNAKE_LATIN = re.compile(r"\b[A-Za-zÀ-ɏ]+_[A-Za-zÀ-ɏ_]+\b")


def _strip_math(text: str) -> str:
    """يزيل LaTeX والرياضيات لعزل النثر اللغوي فقط."""
    t = _LATEX_BLOCK.sub(" ", text)
    t = _LATEX_CMD.sub(" ", t)
    return _MATH_NOISE.sub(" ", t)


def arabic_prose_ratio(text: str) -> float:
    """نسبة الأحرف العربية إلى (العربية + اللاتينية) في النثر بعد إزالة الرياضيات.

    يُعيد 1.0 عند غياب أحرف أبجدية (نص رياضي بحت) — يُعامَل كعربي-آمن.
    """
    prose = _strip_math(text)
    ar = sum(1 for c in prose if _ARABIC_RANGE[0] <= c <= _ARABIC_RANGE[1])
    la = sum(1 for c in prose if ("a" <= c <= "z") or ("A" <= c <= "Z"))
    total = ar + la
    return (ar / total) if total else 1.0


def is_probably_non_arabic(window: str) -> bool:
    """يقرّر إن كانت النافذة الأولى إنجليزية/غارباج (يجب رفضها وإعادة التوليد).

    منطق مزدوج (يتجنّب إساءة تصنيف العربية المثقلة بـ LaTeX — gpt-oss الصحيح ar≈0.57 خام):
      - بعد إزالة LaTeX: نسبة العربية < 0.35 → إنجليزي.
      - أو: ≥ 3 كلمات إنجليزية إشاريّة (We/need/user/...) ونسبة العربية < 0.7 → تسريب تفكير.
    """
    if not window or not window.strip():
        return False
    ratio = arabic_prose_ratio(window)
    if ratio < 0.35:
        return True
    prose = _strip_math(window)
    english_hits = sum(
        1 for w in _ENGLISH_WORD.findall(prose) if w.lower() in _ENGLISH_SIGNAL_WORDS
    )
    return english_hits >= 3 and ratio < 0.7


def sanitize_stream_chunk(text: str) -> str:
    """ينظّف قطعة مبثوثة: يحذف الكتل الأجنبية والرموز الملتصقة بالعربية.

    «أستاذochemistry» → «أستاذ» | روسي/صيني/ياباني → محذوف.
    لا يلمس LaTeX («f(x)» المسبوقة بمسافة تبقى) ولا العربية النقية.
    """
    if not text:
        return text
    out = _FOREIGN_BLOCKS.sub("", text)
    out = _SNAKE_LATIN.sub("", out)  # ISS-114: snake_case غارباج صريح
    return _GLUED_LATIN.sub("", out)


def _extract_delta_content(raw_chunk: Any) -> str:
    """يستخرج ``delta.content`` من قطعة OpenRouter SSE (يتجاهل reasoning)."""
    if not isinstance(raw_chunk, dict):
        return ""
    choices = raw_chunk.get("choices")
    if not choices:
        return ""
    delta = choices[0].get("delta", {}) or {}
    content = delta.get("content")
    if not content or not isinstance(content, str):
        return ""
    return content.replace("\x00", "")


async def _guarded_attempt(
    ai_client: Any,
    messages: list[dict[str, str]],
    max_tokens: int | None,
) -> AsyncGenerator[tuple[str, str], None]:
    """محاولة واحدة: يخزّن النافذة، يقرّر، ثم يبثّ (chunk) أو يرفض (reject).

    Yields:
        ("chunk", نص نظيف) أو ("reject", "") — الرفض يعني لم يُبثّ شيء بعد.
    """
    buf: list[str] = []
    buf_len = 0
    decided = False
    async for raw in ai_client.stream_chat(messages, max_tokens=max_tokens):
        content = _extract_delta_content(raw)
        if not content:
            continue
        if not decided:
            buf.append(content)
            buf_len += len(content)
            if buf_len >= _WINDOW_CHARS:
                window = "".join(buf)
                if is_probably_non_arabic(window):
                    _record_check("rejected")
                    yield ("reject", "")
                    return
                _record_check("arabic")
                decided = True
                cleaned = sanitize_stream_chunk(window)
                if cleaned:
                    yield ("chunk", cleaned)
                buf = []
            continue
        cleaned = sanitize_stream_chunk(content)
        if cleaned:
            yield ("chunk", cleaned)
    # انتهى التيار قبل امتلاء النافذة
    if not decided and buf:
        window = "".join(buf)
        if is_probably_non_arabic(window):
            _record_check("rejected")
            yield ("reject", "")
            return
        _record_check("arabic")
        cleaned = sanitize_stream_chunk(window)
        if cleaned:
            yield ("chunk", cleaned)


async def guard_arabic_stream(
    ai_client: Any,
    messages: list[dict[str, str]],
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """يلفّ ``ai_client.stream_chat`` بحارس لغة عربية + إعادة توليد عند الفشل.

    Args:
        ai_client: عميل الـ gateway (``OpenRouterClient``) — يملك ``stream_chat``.
        messages: [{"role":"system",...},{"role":"user",...}] كما يبنيها local_graph.
        max_tokens: حدّ الرموز (يُمرَّر كما هو).

    Yields:
        str: قطع نص عربية نظيفة جاهزة للبثّ للطالب.
    """
    emitted = False
    async for kind, payload in _guarded_attempt(ai_client, messages, max_tokens):
        if kind == "chunk":
            emitted = True
            yield payload
        elif kind == "reject":
            break
    if emitted:
        return

    # المحاولة الأولى رُفضت (نافذة إنجليزية/غارباج) — أعِد التوليد بـ prompt عربي صارم
    _record_regen()
    logger.warning("arabic_stream_guard: first attempt non-Arabic — regenerating (strict)")
    non_system = [m for m in messages if m.get("role") != "system"]
    strict_messages = [{"role": "system", "content": _STRICT_ARABIC_PROMPT}, *non_system]
    async for kind, payload in _guarded_attempt(ai_client, strict_messages, max_tokens):
        if kind == "chunk":
            emitted = True
            yield payload
        elif kind == "reject":
            break
    if emitted:
        return

    # فشل كل شيء → رسالة عربية نظيفة بدل الغارباج (لا silent failure)
    _record_fallback()
    logger.error("arabic_stream_guard: regeneration also non-Arabic — emitting clean fallback")
    yield _ARABIC_FALLBACK_MESSAGE
