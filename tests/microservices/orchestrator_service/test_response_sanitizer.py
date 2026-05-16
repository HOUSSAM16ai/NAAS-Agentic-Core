"""
اختبارات ResponseSanitizer + Greeting FastPath — ISS-076 / D-064.

يُغطي:
1. تنظيف الكلمات الأجنبية (Russian/Norwegian/Spanish/Chinese/Japanese)
2. تنظيف CJK punctuation (`。 ）（`)
3. حذف chat meta-narration ("Okay, the user...")
4. تجاهل meta-narration للـ educational/general intent (chat-only stripping)
5. Greeting fast-path للتحيات الشائعة
6. المخرج الديترميني للـ fastpath (بدون LLM)
"""

from __future__ import annotations

from microservices.orchestrator_service.src.services.overmind.response_sanitizer import (
    get_greeting_fastpath_response,
    sanitize_response,
)


class TestSanitizeForeignScripts:
    """تنظيف كلمات وscripts أجنبية تتسرَّب من LLM."""

    def test_remove_russian_cyrillic(self):
        text = "السلام будет на вас всех"
        out = sanitize_response(text, intent="chat")
        # الكلمة الرئيسية مُستبدَلة، أي Cyrillic متبقٍ محذوف
        cyrillic_count = sum(1 for c in out if 0x0400 <= ord(c) <= 0x04FF)
        assert cyrillic_count == 0

    def test_remove_norwegian_ogsa(self):
        text = "النص og også المزيد"
        out = sanitize_response(text, intent="chat")
        assert "også" not in out

    def test_remove_spanish_sentido(self):
        text = "النص sentido de المعنى"
        out = sanitize_response(text, intent="chat")
        assert "sentido de" not in out

    def test_remove_mexico_city_catastrophe(self):
        # الكارثة الفعلية من شكوى المستخدم
        text = "تستخدم كتحية Mexico City Amigos."
        out = sanitize_response(text, intent="chat")
        assert "Mexico City" not in out
        assert "Amigos" not in out

    def test_remove_eugene_french_meta(self):
        text = "أُ Eugène的に hello"
        out = sanitize_response(text, intent="chat")
        assert "Eugène" not in out
        # CJK Han 的に also removed
        cjk = sum(1 for c in out if 0x4E00 <= ord(c) <= 0x9FFF)
        assert cjk == 0

    def test_remove_cjk_punctuation(self):
        text = "نص。 و（مثال）"
        out = sanitize_response(text, intent="chat")
        assert "。" not in out
        assert "（" not in out
        assert "）" not in out

    def test_remove_japanese_kana(self):
        text = "النص ひらがな カタカナ المزيد"
        out = sanitize_response(text, intent="chat")
        # ヒラガナ + カタカナ stripped
        kana = sum(1 for c in out if 0x3040 <= ord(c) <= 0x30FF)
        assert kana == 0


class TestChatMetaNarration:
    """حذف meta-narration بالإنجليزية في بداية ردود chat فقط."""

    def test_strip_okay_the_user(self):
        text = "Okay, the user said مرحبا. وعليكم السلام!"
        out = sanitize_response(text, intent="chat")
        assert "Okay, the user" not in out
        assert "وعليكم السلام!" in out

    def test_strip_let_me_respond(self):
        text = "Let me respond carefully. أهلاً بك!"
        out = sanitize_response(text, intent="chat")
        assert "Let me respond" not in out
        assert "أهلاً بك!" in out

    def test_strip_first_i_should(self):
        text = "First, I should answer this. الإجابة هي..."
        out = sanitize_response(text, intent="chat")
        assert "First, I should" not in out

    def test_educational_keeps_meta(self):
        """educational intent يحتفظ بـ meta — ليس chat-only stripping."""
        text = "Let me explain this concept. هذا الشرح..."
        out = sanitize_response(text, intent="educational")
        assert "Let me explain" in out

    def test_general_keeps_meta(self):
        """general intent يحتفظ بـ meta."""
        text = "Let me think about this. هذا الجواب."
        out = sanitize_response(text, intent="general")
        assert "Let me think" in out


class TestGreetingFastPath:
    """Greeting fast-path returns deterministic responses without LLM."""

    def test_salam_alaykum(self):
        r = get_greeting_fastpath_response("السلام عليكم")
        assert r is not None
        assert "وعليكم السلام" in r

    def test_full_islamic_greeting(self):
        r = get_greeting_fastpath_response("السلام عليكم ورحمة الله وبركاته")
        assert r is not None
        assert "وعليكم السلام" in r

    def test_marhaba(self):
        r = get_greeting_fastpath_response("مرحبا")
        assert r is not None

    def test_kayfa_halak(self):
        r = get_greeting_fastpath_response("كيف حالك")
        assert r is not None
        assert "بخير" in r

    def test_sabah_alkhayr(self):
        r = get_greeting_fastpath_response("صباح الخير")
        assert r is not None
        assert "صباح" in r

    def test_hello_english(self):
        r = get_greeting_fastpath_response("hello")
        assert r is not None

    def test_thanks_arabic(self):
        r = get_greeting_fastpath_response("شكرا")
        assert r is not None
        assert "العفو" in r

    def test_educational_question_not_greeting(self):
        r = get_greeting_fastpath_response("اشرح مسألة الاشتقاق")
        assert r is None

    def test_general_question_not_greeting(self):
        r = get_greeting_fastpath_response("ما هو الذكاء الاصطناعي")
        assert r is None

    def test_empty_returns_none(self):
        assert get_greeting_fastpath_response("") is None
        assert get_greeting_fastpath_response("   ") is None

    # ── ISS-077 D-065: blocker tests — fastpath must NOT match questions ──

    def test_greeting_plus_question_blocked(self):
        """'السلام عليكم اشرح لي قانون نيوتن' → الـ blocker يرفض fastpath.

        كان bug في D-064: prefix-match بـ 30char margin يلتقط أسئلة كاملة.
        الـ user كان يحصل على رد greeting بدلاً من إجابة السؤال.
        """
        r = get_greeting_fastpath_response("السلام عليكم اشرح لي قانون نيوتن")
        assert r is None, f"FAIL: greeting+question must reject fastpath, got {r!r}"

    def test_greeting_plus_exercise_request_blocked(self):
        r = get_greeting_fastpath_response("مرحبا اعطني تمرين")
        assert r is None

    def test_kayfa_question_blocked(self):
        """'كيف' interrogative blocked, but 'كيف حالك' allowed."""
        # blocker: كيف بمعنى آخر
        assert get_greeting_fastpath_response("كيف أحل هذه المسألة") is None
        # exception: كيف حالك تحية مسموحة
        assert get_greeting_fastpath_response("كيف حالك") is not None
        assert get_greeting_fastpath_response("كيف الحال") is not None

    def test_what_is_blocked(self):
        """'ما هو/ما هي' interrogative blocked."""
        assert get_greeting_fastpath_response("ما هو التكامل") is None
        assert get_greeting_fastpath_response("ما هي الدالة") is None

    def test_why_when_where_blocked(self):
        assert get_greeting_fastpath_response("لماذا نستخدم لوبيتال") is None
        assert get_greeting_fastpath_response("متى نستخدم القاعدة") is None
        assert get_greeting_fastpath_response("أين نضع الإشارة") is None

    def test_solve_calculate_find_blocked(self):
        assert get_greeting_fastpath_response("احسب التكامل") is None
        assert get_greeting_fastpath_response("أوجد المشتقة") is None
        assert get_greeting_fastpath_response("حل المعادلة") is None

    def test_full_islamic_greeting_with_extension_allowed(self):
        """tail words like 'وبركاته' / 'ورحمة الله' allowed in fastpath."""
        assert get_greeting_fastpath_response("السلام عليكم ورحمة الله") is not None
        assert get_greeting_fastpath_response("السلام عليكم ورحمة الله وبركاته") is not None
        assert get_greeting_fastpath_response("وعليكم السلام ورحمة الله") is not None


class TestEdgeCases:
    """حالات حافة."""

    def test_none_safe(self):
        assert sanitize_response(None, intent="chat") is None
        assert sanitize_response("", intent="chat") == ""

    def test_pure_arabic_unchanged(self):
        text = "هذا نص عربي نظيف بدون أي شوائب."
        out = sanitize_response(text, intent="chat")
        assert out == text

    def test_arabic_with_latin_math_preserved(self):
        # المصطلحات التقنية اللاتينية مسموحة (sin, cos, dx, …)
        text = "الدالة sin(x) ثم cos(y) dx"
        out = sanitize_response(text, intent="educational")
        assert "sin(x)" in out
        assert "cos(y)" in out
        assert "dx" in out
