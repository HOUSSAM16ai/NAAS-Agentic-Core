"""
ResponseSanitizer — ISS-076 / D-064.

تنظيف ردود الـ orchestrator's leaf nodes قبل إرسالها للمستخدم:

1. **Foreign-script removal** — Cyrillic / CJK Han / Hiragana / Katakana / CJK punctuation
2. **Foreign-word replacement** — `også` (نرويجي), `wishes` (إنجليزي meta), `sentido de` (إسباني)
3. **Chat meta-narration stripping** — `"Okay, the user..."`, `"Let me respond..."`
4. **Greeting fast-path** — للتحيات الشائعة، رد deterministic مباشر بدون LLM

## السبب
نماذج OpenRouter المجانية (`nemotron-3-super-120b`, `nemotron-3-nano-30b`, إلخ)
عند سؤال "السلام عليكم" تُولِّد رداً etymological طويلاً بكلمات أجنبية متناثرة
(روسي/إسباني/إنجليزي meta) — كارثة مرئية للطالب.

## الحل
الـ `local_graph.py` (monolith fallback) فيه `_sanitize_local_graph_response` (D-063).
لكن المسار الإنتاجي يستخدم `orchestrator-service` الذي ليس فيه نفس التنظيف.
هذا الـ module يوحِّد التنظيف لكل nodes الـ orchestrator.

## الاستخدام
```python
from microservices.orchestrator_service.src.services.overmind.response_sanitizer import (
    sanitize_response, get_greeting_fastpath_response,
)

# قبل الإرسال للمستخدم
clean = sanitize_response(raw_text, intent="chat")

# عند تحية معروفة، استخدم الرد السريع
fastpath = get_greeting_fastpath_response(query)
if fastpath:
    return fastpath  # تجنَّب LLM
```
"""

from __future__ import annotations

import re

# ── Foreign-word replacements (Russian/Norwegian/Spanish → عربي) ──────────────
_FOREIGN_REPLACEMENTS: dict[str, str] = {
    # روسي
    "линейный": "خطي",
    "линейная": "خطية",
    "линейное": "خطية",
    "функция": "دالة",
    "уравнение": "معادلة",
    "будет на вас": "يكون عليكم",
    "на вас": "عليكم",
    # نرويجي/دانماركي
    "også": "أيضاً",
    "auch": "أيضاً",
    # إسباني
    "aparece": "يظهر",
    "aparecen": "تظهر",
    "sentido de": "بمعنى",
    "Mexico City": "",
    "Amigos": "",
    # فرنسي meta
    "Eugène": "",
    # إنجليزي meta (متناثر في رد عربي)
    "wishes": "أمنيات",
    "invitation": "دعوة",
    "complete": "كامل",
    # CJK punctuation → علامات عربية/لاتينية
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


# ── Chat meta-narration patterns (English/Arabic mix) ────────────────────────
_CHAT_META_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^Okay,\s+the user[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^First,?\s+I\s+(should|must|need|will)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^The user (greeted|said|asked|wrote|sent)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^I need to (respond|answer|reply)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^Let me (think|respond|answer|consider)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^Alright,\s+(the\s+)?(user|question|so)[^.\n]*\.\s*", re.IGNORECASE),
]


# ── Greeting fast-path: deterministic responses (no LLM) ──────────────────────
# Key = normalized greeting prefix, Value = response
_GREETING_FASTPATH: dict[str, str] = {
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


def sanitize_response(text: str, intent: str = "general") -> str:
    """
    ينظِّف رد LLM قبل إرساله للمستخدم.

    Steps:
    1. استبدالات Russian/Spanish/Norwegian/CJK punct → عربي
    2. حذف Cyrillic / CJK Han / Hiragana / Katakana بـ regex
    3. للـ chat فقط: حذف English meta-narration في البداية

    Args:
        text: النص الخام من الـ LLM
        intent: chat | educational | general | admin

    Returns:
        النص النظيف
    """
    if not text:
        return text
    out = text
    # 1. استبدالات
    for foreign, arabic in _FOREIGN_REPLACEMENTS.items():
        out = out.replace(foreign, arabic)
    # 2. حذف scripts كاملة
    out = re.sub(r"[Ѐ-ӿ]+", "", out)  # Cyrillic
    out = re.sub(r"[一-鿿]+", "", out)  # CJK Han
    out = re.sub(r"[぀-ゟ゠-ヿ]+", "", out)  # Japanese kana
    # 3. meta-narration للـ chat فقط
    if intent == "chat":
        for _ in range(5):  # multi-pass
            prev = out
            for rx in _CHAT_META_PATTERNS:
                out = rx.sub("", out, count=1)
            out = out.lstrip()
            if out == prev:
                break
    return out


def get_greeting_fastpath_response(query: str) -> str | None:
    """
    إذا كان السؤال تحية معروفة، يُعيد رداً deterministic بدون LLM.

    يحل كارثة "السلام عليكم → etymology بكلمات أجنبية":
    - الـ LLM المجاني يُولِّد شرحاً لغوياً معقداً لأنه يفسّر التحية كسؤال علمي
    - الـ fast-path يتجنَّب الـ LLM للحالات الشائعة → 0ms response + 100% نظيف

    Returns:
        رد عربي قصير إذا تطابق، None خلاف ذلك
    """
    if not query:
        return None
    normalized = query.strip().lower()
    # احذف punctuation للمطابقة الأفضل
    cleaned = re.sub(r"[^\w\s؀-ۿ]", "", normalized).strip()
    if not cleaned:
        return None
    # طابق exact أو starts_with
    for greeting, response in _GREETING_FASTPATH.items():
        g_lower = greeting.lower()
        if cleaned == g_lower:
            return response
        # السلام عليكم ورحمة الله وبركاته → match prefix
        if cleaned.startswith(g_lower) and len(cleaned) - len(g_lower) <= 30:
            return response
    return None


__all__ = [
    "get_greeting_fastpath_response",
    "sanitize_response",
]
