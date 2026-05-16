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


# ── ISS-078 D-066: Streaming-aware sanitization ──────────────────────────────
# المشكلة (مكتشَفة بالتجريب الحي):
# - LLM يبث chunks مباشرة للعميل (writer({"chunk_type": "assistant_delta", ...}))
# - sanitize_response يُطبَّق على المخرج النهائي فقط (بعد انتهاء streaming)
# - النتيجة: chunks تحوي صينية/روسية تصل للمستخدم لحظياً قبل التنظيف
# - المستخدم يرى الكلمات الأجنبية تومض ثم تختفي → كارثة بصرية
#
# الحل: sanitize_chunk() خفيف يُطبَّق على كل chunk قبل إرساله للعميل
# - يحذف Cyrillic/CJK Han/Hiragana/Katakana فوراً (آمن على chunks مفردة)
# - يستبدل CJK punctuation فوراً
# - يتجاهل multi-word replacements (تحتاج سياق كامل — في sanitize_response النهائي)
# - يتجاهل meta-narration stripping (يحتاج بداية النص)


def sanitize_chunk(chunk: str) -> str:
    """
    ينظِّف chunk جزئي خلال streaming قبل إرساله للعميل.

    يحذف:
    - Cyrillic (روسي/أوكراني)
    - CJK Han (صيني)
    - Hiragana/Katakana (ياباني)
    - CJK punctuation → علامات عربية/لاتينية

    لا يُطبِّق:
    - multi-word foreign replacements (تحتاج سياق كامل)
    - meta-narration stripping (يحتاج بداية النص)

    هذه الدوال تُطبَّق في sanitize_response النهائي بعد انتهاء الـ stream.

    Args:
        chunk: قطعة نص جزئية من stream

    Returns:
        chunk مُنظَّف (آمن للعرض الفوري)
    """
    if not chunk:
        return chunk
    out = chunk
    # CJK punctuation single-char replacements (آمنة على chunks)
    for foreign, replacement in (
        ("。", "."),
        ("（", "("),
        ("）", ")"),
        ("「", '"'),
        ("」", '"'),
        ("『", '"'),
        ("』", '"'),
        ("、", "،"),
        ("〜", "~"),
    ):
        out = out.replace(foreign, replacement)
    # حذف scripts كاملة (آمن — كل char منفصل)
    out = re.sub(r"[Ѐ-ӿ]+", "", out)  # Cyrillic
    out = re.sub(r"[一-鿿]+", "", out)  # CJK Han
    return re.sub(r"[぀-ゟ゠-ヿ]+", "", out)  # Japanese kana


def get_greeting_fastpath_response(query: str) -> str | None:
    """
    إذا كان السؤال تحية معروفة، يُعيد رداً deterministic بدون LLM.

    يحل كارثة "السلام عليكم → etymology بكلمات أجنبية":
    - الـ LLM المجاني يُولِّد شرحاً لغوياً معقداً لأنه يفسّر التحية كسؤال علمي
    - الـ fast-path يتجنَّب الـ LLM للحالات الشائعة → 0ms response + 100% نظيف

    ⚠️ ISS-077 (D-065): القاعدة الذهبية — fastpath لا يُطابق إلا تحية صرفة.
    إذا كان النص يحوي فعل سؤال (اشرح/احسب/اعطني/تمرين/مسألة)، رفض fastpath
    وأرجع None ليذهب الطلب للـ LLM. يحل "النظام أصبح أغبى" — السؤال
    "السلام عليكم اشرح لي قانون نيوتن" كان يُجاب بتحية فقط، يُفقد السؤال.

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

    # ⛔ ISS-077 D-065: الـ blocker — لا fastpath لو يحوي فعل سؤال/طلب
    # تحدد لـ fastpath فقط الـ pure greetings بدون أي طلب علمي/تعليمي.
    # ملاحظة: "كيف حالك" تحية مسموحة — نتأكد لاحقاً أنها ليست blocker.
    educational_blockers = (
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
        "أين",  # سؤال interrogative
        # "كيف" مُستثنى لأن "كيف حالك" تحية شائعة
    )
    # كيف interrogative — blocker إلا إذا كان في "كيف حالك" / "كيف الحال" / "كيف الأحوال"
    _kayfa_greetings = ("كيف حالك", "كيف الحال", "كيف الأحوال", "كيف صحتك")
    if "كيف" in normalized and not any(g in normalized for g in _kayfa_greetings):
        return None  # كيف بمعنى آخر (مثل كيف أحل) → LLM
    for blocker in educational_blockers:
        if blocker in normalized:
            return None  # سؤال علمي → اترك LLM يجيب

    # طابق exact أو starts_with بهامش ضيق (≤ 5 chars) للـ punctuation فقط
    for greeting, response in _GREETING_FASTPATH.items():
        g_lower = greeting.lower()
        if cleaned == g_lower:
            return response
        # السلام عليكم ورحمة الله وبركاته يطابق بـ prefix لأنه نفسه تحية صرفة
        # نسمح بـ 25 char margin فقط للامتدادات المُسمَّاة (وبركاته/وسهلاً)
        if cleaned.startswith(g_lower) and len(cleaned) - len(g_lower) <= 25:
            # ⚠️ تأكد إضافي: الجزء التالي بعد التحية يجب أن يكون أيضاً تحية
            # (وعليكم/ورحمة/وبركاته/وسهلاً/الله)
            tail = cleaned[len(g_lower) :].strip()
            tail_words = tail.split()
            allowed_tail_words = {
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
                # مسموح للـ prefix tail الفارغ تماماً (السلام عليكم.)
            }
            # كل كلمة في الـ tail يجب أن تكون من allowed_tail_words
            if all(w in allowed_tail_words or len(w) <= 2 for w in tail_words):
                return response
    return None


__all__ = [
    "get_greeting_fastpath_response",
    "sanitize_chunk",
    "sanitize_response",
]
