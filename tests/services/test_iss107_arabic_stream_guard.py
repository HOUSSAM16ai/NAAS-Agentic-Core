"""ISS-107 — اختبارات حارس اللغة العربية على البثّ الحي.

يثبت أن الحارس:
- يكشف الإنجليزية/تسريب التفكير (nemotron-super) ويرفضها.
- يمرّر العربية الصحيحة المثقلة بـ LaTeX (gpt-oss ar≈0.57 خام — لا false positive).
- يُنظّف الرموز الملتصقة («أستاذochemistry» → «أستاذ») والكتل الأجنبية.
- يعيد التوليد عند رفض النافذة، ويُصدِر رسالة عربية نظيفة عند فشل كل المحاولات.
"""

import pytest

from app.services.skills.arabic_stream_guard import (
    _ARABIC_FALLBACK_MESSAGE,
    arabic_prose_ratio,
    guard_arabic_stream,
    is_probably_non_arabic,
    sanitize_stream_chunk,
)


class TestDetection:
    def test_english_thinking_leak_rejected(self):
        # عيّنة حية من nemotron-3-super-120b (2026-06-02)
        t = 'We need to respond in Arabic, explaining something. The user says: "اشرح بالعربية".'
        assert is_probably_non_arabic(t) is True

    def test_english_riemann_rejected(self):
        t = "The integral is defined as the limit of the Riemann sums when the mesh tends to zero."
        assert is_probably_non_arabic(t) is True

    def test_arabic_with_heavy_latex_passes(self):
        # عيّنة حية من gpt-oss-20b — عربية صحيحة لكن نسبتها الخام 0.57 بسبب LaTeX
        t = (
            "## لماذا نحتاج إلى التكامل؟\n\nعند دراسة الدوال العددية نريد معرفة المساحة "
            "تحت المنحنى $$\\int_0^\\lambda h(x)\\,dx$$ حيث \\(h(x)=x+f(x)\\)"
        )
        assert arabic_prose_ratio(t) >= 0.9  # بعد إزالة LaTeX
        assert is_probably_non_arabic(t) is False

    def test_pure_math_no_prose_passes(self):
        assert is_probably_non_arabic("$$f'(x) = 2x e^{3x} + 3x^2 e^{3x}$$") is False

    def test_pure_arabic_passes(self):
        assert is_probably_non_arabic("مرحباً، سأشرح لك الفكرة بالعربية خطوة بخطوة.") is False

    def test_empty_not_flagged(self):
        assert is_probably_non_arabic("") is False
        assert is_probably_non_arabic("   ") is False


class TestSanitize:
    def test_glued_latin_stripped(self):
        assert sanitize_stream_chunk("أستاذochemistry في") == "أستاذ في"

    def test_spaced_latin_preserved(self):
        # f(x) مسبوقة بمسافة = ليست ملتصقة → تبقى
        assert "f(x)" in sanitize_stream_chunk("الدالة f(x) معرفة")

    def test_cyrillic_stripped(self):
        assert "будет" not in sanitize_stream_chunk("نص будет عربي")


# ─── مولّد وهمي يحاكي ai_client.stream_chat ──────────────────────────────────
class _FakeAI:
    def __init__(self, scripts):
        # scripts: list of list[str] — قطع كل محاولة بالترتيب
        self._scripts = list(scripts)
        self.calls = 0

    async def stream_chat(self, messages, max_tokens=None):
        idx = min(self.calls, len(self._scripts) - 1)
        self.calls += 1
        for piece in self._scripts[idx]:
            yield {"choices": [{"delta": {"content": piece}}]}


async def _collect(gen):
    return "".join([c async for c in gen])


class TestGuardFlow:
    @pytest.mark.asyncio
    async def test_arabic_first_attempt_streams(self):
        ai = _FakeAI(
            [["مرحباً يا طالب، ", "سنشرح التكامل ", "خطوة بخطوة بالعربية الفصحى لكي تفهم."]]
        )
        out = await _collect(guard_arabic_stream(ai, [{"role": "user", "content": "اشرح"}]))
        assert "التكامل" in out
        assert ai.calls == 1  # لا إعادة توليد

    @pytest.mark.asyncio
    async def test_english_triggers_regeneration_to_arabic(self):
        # المحاولة 1: إنجليزية (يجب رفضها) — المحاولة 2: عربية
        english = ["We need to respond in Arabic. The user wants explanation of the integral. " * 3]
        arabic = [
            "حسناً، ",
            "التكامل هو مساحة تحت المنحنى، وسأشرحه بالعربية الفصحى بالتفصيل الكامل.",
        ]
        ai = _FakeAI([english, arabic])
        out = await _collect(
            guard_arabic_stream(
                ai, [{"role": "system", "content": "long sys"}, {"role": "user", "content": "اشرح"}]
            )
        )
        assert ai.calls == 2  # أعاد التوليد
        assert "We need" not in out
        assert "التكامل" in out

    @pytest.mark.asyncio
    async def test_all_english_emits_clean_arabic_fallback(self):
        english = [
            "We need to respond. The user asked. Let us explain the function and the integral. " * 3
        ]
        ai = _FakeAI([english, english])  # كلا المحاولتين إنجليزية
        out = await _collect(
            guard_arabic_stream(
                ai, [{"role": "system", "content": "s"}, {"role": "user", "content": "q"}]
            )
        )
        assert out == _ARABIC_FALLBACK_MESSAGE
        assert "We need" not in out
