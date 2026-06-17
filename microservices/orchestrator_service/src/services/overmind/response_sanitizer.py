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

# ── D-113 (ISS-115 — وَهْم الإتقان): حجب الإجابة النهائية ─────────────────────
# port مستقل من `app/services/skills/answer_redaction_skill.py` (المونوليث لا
# يستورد من microservices والعكس — نفس نمط heartbeat/content_integrity).
# الكارثة: مخرج الـ orchestrator (SynthesizerNode) يكشف الحلّ الكامل
# (P(A)=14/165، C(11,3)=165، E(X)=1.73، $$\boxed{}$$) → وهم الطلاقة → انهيار
# يوم الامتحان. الحارس حتمي، نطاق ضيّق (يحفظ C(n,k) التعليمية)، fail-open.
_MATH_MASK = "?"
_PROSE_MASK = "؟"
_NUM = r"[-+]?\d[\d.,]*\s*(?:/\s*\d[\d.,]*)?\s*%?"
# نتيجة احتمال/توافيق/أمل صريحة: P(...)=، E(...)=، C(...)=<عدد ختامي فقط>.
_FINAL_RESULT_RE = re.compile(
    r"(?P<lhs>[PECpec]\s*(?:_?[A-Za-z])?\s*\([^)\n]{0,60}\)\s*=\s*)(?P<rhs>" + _NUM + r")"
)
# خلاصة لفظية تنتهي بعدد: «إذن/ومنه/النتيجة/الجواب ... = <عدد>».
_CONCLUSION_RE = re.compile(
    r"(?P<lhs>(?:إذن|ومنه|النتيجة|الجواب|فإن)[^=\n]{0,90}=\s*)(?P<rhs>" + _NUM + r")"
)
# أسطر العلامات الصريحة للنتيجة النهائية.
_RESULT_MARKER_RE = re.compile(
    r"(?P<lbl>(?:الإجابة|النتيجة|الجواب)\s*(?:النهائية|النهائي)\s*[:：]?\s*)(?P<val>.+)"
)


def _strip_boxed(text: str) -> str:
    r"""يستبدل محتوى كل `\boxed{...}` بـ `?` (موازنة أقواس). يُبقي الصندوق صالحاً."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        idx = text.find("\\boxed", i)
        if idx == -1:
            out.append(text[i:])
            break
        out.append(text[i:idx])
        j = idx + len("\\boxed")
        while j < n and text[j] in " \t":
            j += 1
        if j < n and text[j] == "{":
            depth = 0
            k = j
            while k < n:
                if text[k] == "{":
                    depth += 1
                elif text[k] == "}":
                    depth -= 1
                    if depth == 0:
                        k += 1
                        break
                k += 1
            out.append("\\boxed{" + _MATH_MASK + "}")
            i = k
        else:
            out.append(text[idx : idx + len("\\boxed")])
            i = idx + len("\\boxed")
    return "".join(out)


# D-114: الفواصل الحارسة للمثال المحلول — نسخة من
# app/services/skills/doctrine.py:WORKED_EXAMPLE_OPEN/CLOSE (حدّ معماري: المونوليث
# لا يستورد من microservices والعكس). يجب أن تبقى القيمتان متطابقتين حرفياً.
_WE_OPEN = "⟦مثال_محلول⟧"
_WE_CLOSE = "⟦/مثال_محلول⟧"


# ── D-115: المُطهّر المُصفّح (Bulletproof) — شبكة أمان ضد كل غارباج مُسرَّب ─────
# الكارثة الحيّة: النماذج المجانية تُسرّب فواصل ⟦⟧ مشوّهة/مقسّمة، تعليمات
# system prompt إنجليزية (WARM-UP...)، وأقواس يتيمة. هذه الدالة تحذفها بـ regex
# قوي مهما تشوّهت — تُطبَّق على deltas + النهائي، حتمية، fail-open.
# أي قوس زاوية رياضي ⟦...⟧ (U+27E6/27E7) مكتمل (حتى لو طويلاً)
_BRACKET_BLOCK_RE = re.compile(r"⟦[^⟧\n]{0,120}⟧")
# عبارة الفاصل بالأندرسكور (شكل العلامة لا العربية الطبيعية «مثال محلول» بمسافة)
_MARKER_PHRASE_RE = re.compile(r"/?\s*مثال_محلول")
# أسطر تعليمات مُسرَّبة (system prompt بالإنجليزية أو علامات توجيه داخلية).
# D-117: «الطالب يرى التعليم لا هندسة التعليم» — أي سطر يصف تفكير النظام نفسه
# (توجيه D-104، قالب D-115 السقراطي، وضع MODE_B، هلوسة «Konzept») يُحذف بالكامل.
_INSTRUCTION_LEAK_RE = re.compile(
    r"(?im)^.*?(?:WARM[\s\-]?UP|the instruction must|coalesced|rendered in a|"
    r"single flowing syntax|semantic nuances|prepares the learner|Konzept|"
    r"التوجيه التربوي|توجيه تربوي|تفعيل الفهم المبكر|مثال_محلول|"
    r"مستوى الدعم|نوع المسألة|سؤال تشخيصي|أصغر خطوة|اطلب من الطالب|"
    r"وضع الشرح العميق|فهمت المطلوب).*$"
)


def strip_garbage_markers(text: str) -> str:
    """D-115: يحذف كل أشكال الفواصل/التعليمات المُسرَّبة (حتمي، fail-open).

    - كتل ⟦...⟧ المكتملة (يحذف العلامة، يُبقي المحتوى الداخلي عبر التقاط منفصل).
    - الأقواس اليتيمة ⟦/⟧ مهما تشوّهت أو انقسمت عبر chunks.
    - عبارة العلامة «مثال_محلول» (بالأندرسكور — ليست عربية طبيعية).
    - أسطر تعليمات system prompt الإنجليزية المُسرَّبة.
    """
    if not text:
        return text or ""
    try:
        out = _BRACKET_BLOCK_RE.sub("", text)
        # أقواس يتيمة/مشوّهة باقية
        out = out.replace("⟦", "").replace("⟧", "")
        # D-116: علامات تجميعية لاتينية دخيلة (U+0300–U+036F) — «لا̅ يمكن̅».
        out = re.sub(r"[̀-ͯ]", "", out)
        out = _MARKER_PHRASE_RE.sub("", out)
        return _INSTRUCTION_LEAK_RE.sub("", out)
    except Exception:  # pragma: no cover — fail-open
        return text


def _redact_core(text: str) -> str:
    """يحجب كل نتيجة نهائية صريحة (بلا وعي بالفواصل)."""
    result = _strip_boxed(text)
    result = _FINAL_RESULT_RE.sub(lambda m: f"{m.group('lhs')}{_PROSE_MASK}", result)
    result = _CONCLUSION_RE.sub(lambda m: f"{m.group('lhs')}{_PROSE_MASK}", result)
    return _RESULT_MARKER_RE.sub(
        lambda m: f"{m.group('lbl')}{_PROSE_MASK} (حاول أن تصل إليها بنفسك)", result
    )


def _strip_sentinels(text: str) -> str:
    """يحذف علامات الفواصل الحارسة من المُخرَج (لا تصل الطالب أبداً)."""
    return text.replace(_WE_OPEN, "").replace(_WE_CLOSE, "")


def _redact_outside_sentinels(text: str) -> str:
    """D-114: يحجب ما *خارج* الفواصل ويمرّر ما *بداخلها* حرفياً (مثال محلول مماثل)."""
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        start = text.find(_WE_OPEN, i)
        if start == -1:
            out.append(_redact_core(text[i:]))
            break
        out.append(_redact_core(text[i:start]))
        end = text.find(_WE_CLOSE, start + len(_WE_OPEN))
        if end == -1:
            # فاصل غير مُغلق ⇒ fail-closed: احجب الباقي
            out.append(_redact_core(text[start + len(_WE_OPEN) :]))
            break
        out.append(text[start + len(_WE_OPEN) : end])  # داخل الفاصل يمرّ حرفياً
        i = end + len(_WE_CLOSE)
    return "".join(out)


def redact_final_answers(text: str, support_level: int | None = None) -> str:
    """يحجب كل نتيجة نهائية صريحة من النص. حتمي، fail-open (أي فشل → النص كما هو).

    D-114: عند ``support_level == 1`` ووجود الفواصل الحارسة، يُعفى ما *بداخلها*
    (المثال المحلول على مسألة مماثلة) ويُحجب ما *خارجها*. غير ذلك ⇒ حجب كامل
    مع إزالة أي علامات فواصل شاردة (fail-closed).
    """
    if not text or not text.strip():
        return text or ""
    try:
        has_sentinels = _WE_OPEN in text and _WE_CLOSE in text
        if support_level == 1 and has_sentinels:
            return _redact_outside_sentinels(text)
        result = _redact_core(text)
        if has_sentinels or _WE_OPEN in result or _WE_CLOSE in result:
            result = _strip_sentinels(result)
        return result
    except Exception:  # pragma: no cover - fail-open مطلق
        return text


def _redact_boxed_chunk(text: str) -> str:
    r"""حجب آمن للبثّ المباشر (per-chunk): `\boxed{...}` فقط (لا يحتاج سياق سطر)."""
    if not text or "\\boxed" not in text:
        return text or ""
    try:
        return _strip_boxed(text)
    except Exception:  # pragma: no cover
        return text


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


def sanitize_response(text: str, intent: str = "general", support_level: int | None = None) -> str:
    """
    ينظِّف رد LLM قبل إرساله للمستخدم.

    Steps:
    1. استبدالات Russian/Spanish/Norwegian/CJK punct → عربي
    2. حذف Cyrillic / CJK Han / Hiragana / Katakana بـ regex
    3. للـ chat فقط: حذف English meta-narration في البداية
    4. حجب الإجابة النهائية (واعٍ بالفواصل عند support_level==1 — D-114)

    Args:
        text: النص الخام من الـ LLM
        intent: chat | educational | general | admin
        support_level: D-114 — 1 يُعفي كتلة المثال المحلول الملفوفة بالفواصل.

    Returns:
        النص النظيف
    """
    if not text:
        return text
    out = text
    # 0. D-115: حذف الغارباج المُسرَّب (فواصل ⟦⟧ مشوّهة + تعليمات إنجليزية)
    out = strip_garbage_markers(out)
    # 1. استبدالات
    for foreign, arabic in _FOREIGN_REPLACEMENTS.items():
        out = out.replace(foreign, arabic)
    # 2. حذف scripts كاملة
    out = re.sub(r"[Ѐ-ӿ]+", "", out)  # Cyrillic
    out = re.sub(r"[一-鿿]+", "", out)  # CJK Han
    out = re.sub(r"[぀-ゟ゠-ヿ]+", "", out)  # Japanese kana
    out = re.sub(r"[가-힣ㄱ-ㅎㅏ-ㅣ]+", "", out)  # Korean Hangul (D-103 live finding)
    # 3. meta-narration للـ chat فقط
    if intent == "chat":
        for _ in range(5):  # multi-pass
            prev = out
            for rx in _CHAT_META_PATTERNS:
                out = rx.sub("", out, count=1)
            out = out.lstrip()
            if out == prev:
                break
    # 4. D-113/D-114: حجب الإجابة النهائية — واعٍ بالفواصل عند support_level==1.
    return redact_final_answers(out, support_level)


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
    # D-115: حذف الغارباج المُسرَّب فوراً على الـ chunk (فواصل ⟦⟧ + تعليمات إنجليزية)
    out = strip_garbage_markers(out)
    # D-114: استبدالات الكلمات الأجنبية الكاملة (روسي/نرويجي/إسباني + علامات CJK)
    # — best-effort على الـ chunk (الكلمات المنقسمة عبر chunks يلتقطها التنظيف
    # النهائي sanitize_response). آمن: استبدال نصّي مباشر بلا false-positive.
    for foreign, replacement in _FOREIGN_REPLACEMENTS.items():
        out = out.replace(foreign, replacement)
    # حذف scripts كاملة (آمن — كل char منفصل)
    out = re.sub(r"[Ѐ-ӿ]+", "", out)  # Cyrillic
    out = re.sub(r"[一-鿿]+", "", out)  # CJK Han
    out = re.sub(r"[぀-ゟ゠-ヿ]+", "", out)  # Japanese kana
    out = re.sub(r"[가-힣ㄱ-ㅎㅏ-ㅣ]+", "", out)  # Korean Hangul (D-103 live finding)
    # D-113: حجب \boxed الحيّ (النتائج اللفظية تُحجب نهائياً في sanitize_response)
    return _redact_boxed_chunk(out)


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
    "redact_final_answers",
    "sanitize_chunk",
    "sanitize_response",
]
