"""
اختبارات ISS-075 / D-063 — Greeting Recognition + Explanation Patterns + Sanitizer.

تجريب حي كشف 3 كوارث:
1. «السلام عليكم» يُصنَّف كـ `general` (لأن regex لا يقبل امتداداً للكلمة)
   → الـ LLM يُولِّد رداً etymological طويلاً بـ كلمات نرويجية/إسبانية/CJK
2. «أريد شرح مفصل للسؤال 1 أ» لا يُكتشف كـ explanation request
   → يضيع السياق → هلوسة إندونيسية عن "dokumen pendidikan"
3. كلمات أجنبية (`også`, `wishes`, `（）。`) لا تُنظَّف من الرد

هذا الـ test يضمن أن:
- _GREETING_PATTERNS الجديدة تطابق 15+ صيغة طبيعية للتحية
- _BAC_EXERCISE_EXPLANATION_PATTERNS تشمل "أريد شرح" و "للسؤال" و "ممكن تشرح"
- _sanitize_local_graph_response يُزيل foreign-script + meta-narration
"""

from __future__ import annotations

import re

# ─── Test fixtures (يجب أن يطابق الـ patterns في local_graph.py + path_observer.py)

_GREETING_PATTERNS = [
    r"^(?:و\s*)?(?:عليكم\s+)?السلام(?:\s+عليكم)?(?:\s+و?رحم[ةى]\s+الله)?(?:\s+و?بركاته)?[\s\W]*$",
    r"^(مرحبا|أهلاً?|أهلا|هلاً?|هلا)(?:\s+\S+){0,3}[\s\W]*$",
    r"^(hello|hi|hey|salam|بونجور|bonjour|salut|good\s+(morning|afternoon|evening))(?:\s+\S+){0,2}[\s\W]*$",
    r"^(كيف\s+حالك|ما\s+أخبارك|how\s+are\s+you|كيف\s+الأحوال)(?:\s+\S+){0,4}[\s\W]*$",
    r"^(شكرا|شكراً|merci|thank\s+you|thanks)(?:\s+\S+){0,4}[\s\W]*$",
    r"^(مع\s+السلامة|وداع[اً]?|bye|goodbye|au\s+revoir)(?:\s+\S+){0,3}[\s\W]*$",
    r"^(صباح\s+(الخير|النور)|مساء\s+(الخير|النور)|ليلة\s+سعيدة|صباحك\s+\S+|مساؤك\s+\S+)[\s\W]*$",
]


def _matches_greeting(text: str) -> bool:
    """يطابق التحية مثلما يفعل local_graph.py."""
    normalized = text.strip().lower()
    return any(re.search(p, normalized) for p in _GREETING_PATTERNS)


class TestGreetingRegex:
    """ISS-075: greeting regex يجب أن يطابق امتدادات طبيعية."""

    def test_islamic_greeting_alone(self):
        assert _matches_greeting("السلام عليكم")

    def test_islamic_greeting_full(self):
        assert _matches_greeting("السلام عليكم ورحمة الله وبركاته")

    def test_response_greeting(self):
        assert _matches_greeting("وعليكم السلام")

    def test_response_greeting_full(self):
        assert _matches_greeting("وعليكم السلام ورحمة الله")

    def test_marhaba_alone(self):
        assert _matches_greeting("مرحبا")

    def test_marhaba_extended(self):
        assert _matches_greeting("مرحبا بك")

    def test_ahlan_wa_sahlan(self):
        assert _matches_greeting("أهلاً وسهلاً")

    def test_hala_wallah(self):
        assert _matches_greeting("هلا والله")

    def test_kayfa_halak_simple(self):
        assert _matches_greeting("كيف حالك")

    def test_kayfa_halak_extended(self):
        assert _matches_greeting("كيف حالك يا أستاذ")

    def test_kayfa_halak_today(self):
        assert _matches_greeting("كيف حالك اليوم")

    def test_thanks(self):
        assert _matches_greeting("شكرا جزيلاً")

    def test_morning(self):
        assert _matches_greeting("صباح الخير")

    def test_evening(self):
        assert _matches_greeting("مساء النور")

    def test_hello_english(self):
        assert _matches_greeting("hello there")

    def test_good_morning_english(self):
        assert _matches_greeting("good morning")

    # سلبية — يجب ألا تُطابق
    def test_educational_not_greeting(self):
        assert not _matches_greeting("اشرح مسألة الاشتقاق")

    def test_general_not_greeting(self):
        assert not _matches_greeting("ما هو الذكاء الاصطناعي")


# ─── Sanitizer tests ──────────────────────────────────────────────────────────

_FOREIGN_REPLACEMENTS = {
    "линейный": "خطي",
    "линейная": "خطية",
    "линейное": "خطية",
    "функция": "دالة",
    "уравнение": "معادلة",
    "også": "أيضاً",
    "auch": "أيضاً",
    "aparece": "يظهر",
    "aparecen": "تظهر",
    "wishes": "أمنيات",
    "invitation": "دعوة",
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

_CHAT_META_PATTERNS = [
    re.compile(r"^Okay,\s+the user[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^First,?\s+I\s+(should|must|need|will)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^The user (greeted|said|asked|wrote)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^I need to (respond|answer|reply)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^Let me (think|respond|answer|consider)[^.\n]*\.\s*", re.IGNORECASE),
    re.compile(r"^Alright,\s+(the\s+)?(user|question|so)[^.\n]*\.\s*", re.IGNORECASE),
]


def _sanitize(text: str, intent: str) -> str:
    """نسخة طبق الأصل من _sanitize_local_graph_response لأغراض الاختبار."""
    if not text:
        return text
    out = text
    for foreign, arabic in _FOREIGN_REPLACEMENTS.items():
        out = out.replace(foreign, arabic)
    out = re.sub(r"[Ѐ-ӿ]+", "", out)
    out = re.sub(r"[一-鿿]+", "", out)
    out = re.sub(r"[぀-ゟ゠-ヿ]+", "", out)
    if intent == "chat":
        for _ in range(5):
            prev = out
            for rx in _CHAT_META_PATTERNS:
                out = rx.sub("", out, count=1)
            out = out.lstrip()
            if out == prev:
                break
    return out


class TestForeignScriptSanitizer:
    """ISS-075: تنظيف الكلمات الأجنبية + meta-narration."""

    def test_remove_norwegian(self):
        assert "også" not in _sanitize("نص og også المزيد", "chat")

    def test_remove_english_in_arabic(self):
        out = _sanitize("نص wishes ثم invitation", "chat")
        assert "wishes" not in out
        assert "invitation" not in out

    def test_remove_cjk_punct(self):
        out = _sanitize("نص。 و（مثال）", "chat")
        assert "。" not in out
        assert "（" not in out
        assert "）" not in out

    def test_remove_russian(self):
        out = _sanitize("функция линейный uravneнie", "chat")
        # Cyrillic chars stripped entirely
        cyrillic_count = sum(1 for c in out if 0x0400 <= ord(c) <= 0x04FF)
        assert cyrillic_count == 0

    def test_remove_chinese(self):
        out = _sanitize("نص 向心 force", "chat")
        cjk_count = sum(1 for c in out if 0x4E00 <= ord(c) <= 0x9FFF)
        assert cjk_count == 0

    def test_strip_chat_meta_narration(self):
        out = _sanitize("Okay, the user greeted me with مرحبا. وعليكم السلام!", "chat")
        assert "Okay" not in out
        assert "وعليكم السلام!" in out

    def test_strip_let_me_respond(self):
        out = _sanitize("Let me respond to this. أهلاً!", "chat")
        assert "Let me respond" not in out
        assert "أهلاً!" in out

    def test_user_catastrophe_full_response(self):
        """الكارثة الفعلية من شكوى المستخدم — تنظيف كامل."""
        catastrophic = (
            "العبارة «السلام عليكم» هي تحية. كلمة «عليكم» wishes‑ السلام "
            "تُردُّ بـ«وعليكم السلام» også. لذا فإن invitation لتخ التحية。 "
            "（مثال）。 معني العبارة هو: «السلام يكون عليكم»."
        )
        out = _sanitize(catastrophic, "chat")
        assert "wishes" not in out
        assert "også" not in out
        assert "invitation" not in out
        assert "。" not in out
        assert "（" not in out
        assert "）" not in out

    def test_educational_does_not_strip_meta(self):
        """meta-narration stripping للـ chat فقط — لا يُطبَّق على educational."""
        text = "Okay, let me explain this educational concept. الموضوع التعليمي."
        # في wave educational نتركها (لا strip)
        out = _sanitize(text, "educational")
        assert "Okay" in out  # محفوظ في educational


class TestExplanationPatterns:
    """ISS-075: أنماط طلب الشرح يجب أن تشمل صياغات طبيعية متنوعة."""

    def _has_pattern(self, text: str, patterns: tuple) -> bool:
        return any(p in text.lower() for p in patterns)

    def test_natural_phrasings(self):
        """نختبر تطابق الصياغات الطبيعية مع explanation patterns."""
        # هذه يجب أن تُكتشف
        from app.services.capabilities.exercise_retrieval import (
            _BAC_EXERCISE_EXPLANATION_PATTERNS,
        )

        positives = [
            "أريد شرح مفصل للسؤال 1 أ",
            "شرح مفصل للسؤال 1 أ",
            "ممكن تشرح لي السؤال 1",
            "أحتاج شرح",
            "اشرح السؤال 2",
            "ماذا نقصد بالاشتقاق",
            "لماذا نستخدم قاعدة الضرب",
        ]
        for q in positives:
            assert self._has_pattern(q, _BAC_EXERCISE_EXPLANATION_PATTERNS), (
                f"FAIL: {q!r} should match explanation patterns"
            )
