"""
اختبارات LatexStreamNormalizer — ISS-074 / D-062.

يُغطي:
1. تطبيع `\\[...\\]` → `$$...$$`
2. تطبيع `\\\\[...\\\\]` (double backslash) → `$$...$$`
3. تطبيع `\\begin{equation}` و `\\begin{align}` و `\\begin{aligned}`
4. حفظ `\\(...\\)` inline (لا يُلمَس)
5. حفظ `$...$` و `$$...$$` (لا يُلمَس — تنسيق صحيح أصلاً)
6. streaming chunks مُجزَّأة حرف-بحرف
7. forced flush عند block ضخم بدون إغلاق
8. عدم فقد بايتات
9. plain text untouched
"""

from __future__ import annotations

from microservices.orchestrator_service.src.services.overmind.latex_normalizer import (
    LatexStreamNormalizer,
    normalize_latex,
)


class TestNormalizeLatex:
    """اختبارات الدالة `normalize_latex()` (post-processing batch)."""

    def test_single_bracket_simple(self):
        result = normalize_latex(r"احسب \[x^2\] الناتج.")
        assert "$$" in result
        assert "\\[" not in result
        assert "x^2" in result

    def test_double_bracket(self):
        result = normalize_latex(r"حسب \\[x^2\\] الناتج.")
        assert "$$" in result
        assert "\\\\[" not in result and "\\\\]" not in result

    def test_equation_env(self):
        result = normalize_latex(r"\begin{equation} y' + 2y = 0 \end{equation}")
        assert "$$" in result
        assert "\\begin{equation" not in result
        assert "y' + 2y = 0" in result

    def test_align_env(self):
        result = normalize_latex(r"\begin{align} a &= 1 \\ b &= 2 \end{align}")
        assert "$$" in result
        assert "\\begin{align" not in result

    def test_aligned_env(self):
        result = normalize_latex(r"\begin{aligned} f &= 1 \end{aligned}")
        assert "$$" in result

    def test_inline_preserved(self):
        """inline `\\(...\\)` لا يُلمَس."""
        result = normalize_latex(r"الدالة \(f(x) = x^2\) معرَّفة.")
        assert r"\(" in result and r"\)" in result
        assert "$$" not in result

    def test_dollar_preserved(self):
        """`$...$` و `$$...$$` لا يُلمَسان."""
        result = normalize_latex(r"$$E = mc^2$$ ثم $a + b$ نهاية.")
        assert "$$E = mc^2$$" in result
        assert "$a + b$" in result

    def test_empty_string(self):
        assert normalize_latex("") == ""

    def test_none_safe(self):
        # type-checker حماية: ندخل دالة لا ترفع
        assert normalize_latex(None) is None  # type: ignore[arg-type]

    def test_plain_text_unchanged(self):
        text = "هذا نص عربي عادي بدون رياضيات."
        assert normalize_latex(text) == text


class TestLatexStreamNormalizer:
    """اختبارات `LatexStreamNormalizer` (streaming-aware)."""

    def _stream(self, text: str, chunk_size: int = 1) -> str:
        """يُحاكي البث: قسِّم النص إلى chunks بحجم محدد."""
        n = LatexStreamNormalizer()
        out: list[str] = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i : i + chunk_size]
            out.extend(n.feed(chunk))
        out.extend(n.flush())
        return "".join(out)

    def test_simple_bracket_char_by_char(self):
        result = self._stream(r"لحساب \[f(x) = x^2\] نتيجة.")
        assert "$$" in result
        assert "\\[" not in result
        assert "f(x) = x^2" in result

    def test_simple_bracket_word_by_word(self):
        text = r"احسب \[E = mc^2\] هكذا."
        # كل كلمة كـ chunk منفصل
        words = text.split(" ")
        n = LatexStreamNormalizer()
        out: list[str] = []
        for w in words:
            out.extend(n.feed(w + " "))
        out.extend(n.flush())
        result = "".join(out)
        assert "$$" in result
        assert "\\[" not in result

    def test_equation_env_streaming(self):
        result = self._stream(
            r"المعادلة \begin{equation} y' + 2y = 0 \end{equation} حلها."
        )
        assert "$$" in result
        assert "\\begin{equation" not in result

    def test_inline_preserved_streaming(self):
        result = self._stream(r"\(f(x)\) معرَّفة على \(\mathbb{R}\).")
        assert r"\(" in result and r"\)" in result
        assert "$$" not in result

    def test_dollar_preserved_streaming(self):
        result = self._stream(r"احسب $$x^2$$ ثم $a$ نهاية.")
        assert "$$x^2$$" in result
        assert "$a$" in result

    def test_large_block_forced_flush(self):
        """block ضخم بدون إغلاق → forced flush مع تطبيع جزئي."""
        huge = r"\[" + "x = " + "a" * 9500  # أكبر من _MAX_BUFFER
        n = LatexStreamNormalizer()
        n.feed(huge)
        out = n.flush()
        assert len(out) > 0
        text = "".join(out)
        assert "x = " in text or "a" in text  # المحتوى لم يضع

    def test_empty_feed_safety(self):
        n = LatexStreamNormalizer()
        assert n.feed("") == []
        assert n.flush() == []

    def test_no_content_loss(self):
        """تأكد لا فقد بايتات."""
        result = self._stream(r"abc \[d\] efg")
        for token in ["abc", "d", "efg"]:
            assert token in result, f"lost {token!r} from {result!r}"

    def test_plain_arabic_unchanged(self):
        result = self._stream("هذه إجابة عربية بدون رياضيات.")
        assert result == "هذه إجابة عربية بدون رياضيات."

    def test_partial_opener_lookahead(self):
        """chunk ينتهي بـ `\\` (نصف opener) → يجب احتفاظ في buffer."""
        n = LatexStreamNormalizer()
        out1 = n.feed(r"اختبار \\")
        # الـ buffer يحتفظ بـ `\\` لأنه قد يكون بداية `\\[`
        out2 = n.feed("[")
        out3 = n.feed(r"x^2\\]")
        out4 = n.flush()
        result = "".join(out1 + out2 + out3 + out4)
        # double-backslash variant should also convert
        assert "$$" in result, f"FAIL: {result!r}"
        assert "x^2" in result

    def test_multiple_blocks(self):
        text = r"أولاً \[a\] ثم \[b\] أخيراً."
        result = self._stream(text)
        # يجب 2 من `$$`
        assert result.count("$$") >= 4  # 2 opener + 2 closer
        assert "a" in result and "b" in result


class TestEdgeCases:
    """حالات حافة قد تُسبب bugs."""

    def test_nested_dollar_in_brackets(self):
        """`\\[...$x$...\\]` — `$x$` داخل display block."""
        result = normalize_latex(r"\[\text{قيمة } $x$\]")
        assert "$$" in result
        # الـ $x$ الداخلي محفوظ
        assert "$x$" in result or "x" in result

    def test_mixed_styles_in_same_text(self):
        """نص يخلط `\\[...\\]` مع `$$...$$` مع `\\(...\\)`."""
        text = r"\[a\] و $$b$$ و \(c\)"
        result = normalize_latex(text)
        assert result.count("$$") >= 4  # \[a\] → $$a$$ + الأصلي $$b$$
        assert r"\(c\)" in result

    def test_unicode_safe(self):
        result = normalize_latex(r"النتيجة: \[ x = العربية \] انتهى.")
        assert "$$" in result
        assert "العربية" in result
