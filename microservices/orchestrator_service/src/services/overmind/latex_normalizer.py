"""
LatexStreamNormalizer — ISS-074 / D-062.

تطبيع LaTeX على دفعات (streaming chunks) قبل إرسالها للمستخدم.

## المشكلة (تجريب حي 2026-05-15)
نماذج OpenRouter المجانية المُتاحة اليوم (`nvidia/nemotron-3-super-120b-a12b:free`،
`nvidia/nemotron-3-nano-30b-a3b:free`، `openai/gpt-oss-20b:free`، `openai/gpt-oss-120b:free`)
تستخدم جميعها `\\[...\\]` و `\begin{equation}...\\end{equation}` بدلاً من `$$...$$`
رغم system prompt الصريح. الـ frontend (D-051) يُحوِّل لكن خلال streaming بعض الأحيان
الـ chunks تصل مُجزَّأة (`\\` ثم `[` في chunks منفصلة) → typewriter يكشف حروفاً
خام قبل أن يستطيع preprocessMath التطبيع.

## الحل
هذا الـ module يعمل على الـ **خادم** (orchestrator) قبل إرسال الـ chunks للعميل:
1. يحتفظ بـ small lookahead buffer (~6 chars + الـ block المفتوح)
2. عند رؤية `\\[`, `\\[`, `\begin{equation`, إلخ → يحبس الـ chunk حتى يجد إغلاقاً
3. يُطبِّع الـ block إلى `$$...$$` ثم يُصدره دفعة واحدة
4. النص الـ regular يمر فوراً (مع 6-char lookahead للأمان فقط)

## الاستخدام (في عقد StateGraph)
```python
from microservices.orchestrator_service.src.services.overmind.latex_normalizer import (
    LatexStreamNormalizer, normalize_latex,
)

normalizer = LatexStreamNormalizer()
parts: list[str] = []
async for chunk in llm_client.stream_chat(messages):
    content = llm_client.extract_stream_content(chunk)
    if not content:
        continue
    for safe in normalizer.feed(content):
        parts.append(safe)
        writer({"chunk_type": "assistant_delta", "content": safe, "node": "synthesizer"})
for tail in normalizer.flush():
    parts.append(tail)
    writer({"chunk_type": "assistant_delta", "content": tail, "node": "synthesizer"})

# للنص الكامل (للـ persistence): "".join(parts) — مُطبَّع بالكامل
```

## الـ contracts (لا تُكسر)
- `feed()` و `flush()` آمنة من الأخطاء — لا ترفع استثناءات
- المخرج الكلي = `normalize_latex(input_total)` بالضبط — لا فقد بايتات
- inline LaTeX `\\(...\\)` يمر بدون تعديل (لا يلمس)
- `$...$` و `$$...$$` تمر بدون تعديل (تنسيق صحيح بالفعل)
"""

from __future__ import annotations

import re

# ── Regex compiled مرة واحدة (performance) ──────────────────────────────────
_RX_DBRACKET = re.compile(r"\\\\\[\s*(.*?)\s*\\\\\]", re.DOTALL)
_RX_BRACKET = re.compile(r"\\\[\s*(.*?)\s*\\\]", re.DOTALL)
_RX_EQUATION = re.compile(r"\\begin\{equation\*?\}\s*(.*?)\s*\\end\{equation\*?\}", re.DOTALL)
_RX_ALIGN = re.compile(r"\\begin\{align\*?\}\s*(.*?)\s*\\end\{align\*?\}", re.DOTALL)
_RX_ALIGNED = re.compile(r"\\begin\{aligned\*?\}\s*(.*?)\s*\\end\{aligned\*?\}", re.DOTALL)
_RX_EMPTY_DOLLARS = re.compile(r"\$\$\s*\$\$")


def normalize_latex(text: str) -> str:
    """
    يُحوِّل جميع صيغ LaTeX display إلى `$$...$$` الموحَّدة.

    التحويلات:
      `\\[ ... \\]`                          → `$$ ... $$`
      `\\[ ... \\]`                            → `$$ ... $$`
      `\begin{equation} ... \\end{equation}`  → `$$ ... $$`
      `\begin{align} ... \\end{align}`        → `$$ ... $$`
      `\begin{aligned} ... \\end{aligned}`    → `$$ ... $$`
      `$$  $$`                               → `` (تنظيف)

    inline `\\(...\\)` و `$...$` لا يُلمسان.
    """
    if not text:
        return text

    def _wrap(m: re.Match[str]) -> str:
        inner = m.group(1).strip()
        return f"\n$$\n{inner}\n$$\n"

    text = _RX_DBRACKET.sub(_wrap, text)
    text = _RX_BRACKET.sub(_wrap, text)
    text = _RX_EQUATION.sub(_wrap, text)
    text = _RX_ALIGN.sub(_wrap, text)
    text = _RX_ALIGNED.sub(_wrap, text)
    return _RX_EMPTY_DOLLARS.sub("", text)


class LatexStreamNormalizer:
    """
    Stream-aware LaTeX normalizer.

    يستقبل chunks تدفقياً ويُعيد قطعاً قابلة للإرسال للعميل.
    عندما يكتشف بداية `\\[` أو `\\\\[` أو `\\begin{equation` يحبس البafer
    حتى يجد إغلاقاً مطابقاً، ثم يطبِّع ويُصدر الكل دفعة واحدة.

    Edge cases مغطاة:
    - chunk ينتهي بـ `\\` (نصف opener) → يحتفظ بـ 6-char lookahead
    - block ضخم بدون إغلاق (>4096 chars) → forced flush مع تطبيع جزئي
    - inline `\\(...\\)` يمر بدون احتجاز

    Thread-safety: NO. أنشئ instance جديد لكل request.
    """

    _MAX_BUFFER = 8192  # حد أقصى آمن قبل forced flush
    _LOOKAHEAD = 8  # عدد الأحرف المحجوزة دائماً تحسباً لـ opener partial

    # علامات تفتح block — يجب احتجاز الـ stream عندها
    _OPENERS = ("\\[", "\\\\[", "\\begin{")
    # علامات إغلاق المُحتمَلة
    _CLOSERS = (
        "\\]",
        "\\\\]",
        "\\end{equation}",
        "\\end{equation*}",
        "\\end{align}",
        "\\end{align*}",
        "\\end{aligned}",
        "\\end{aligned*}",
    )

    def __init__(self) -> None:
        self._buf: str = ""
        self._in_block: bool = False

    def feed(self, chunk: str) -> list[str]:
        """يستقبل chunk جديد ويُعيد قائمة من القطع الجاهزة للإرسال (قد تكون فارغة)."""
        if not chunk:
            return []
        self._buf += chunk
        out: list[str] = []
        while True:
            if self._in_block:
                close_idx = self._find_earliest(self._buf, self._CLOSERS, with_len=True)
                if close_idx < 0:
                    if len(self._buf) > self._MAX_BUFFER:
                        # forced flush — block غير مغلق طويل جداً
                        out.append(normalize_latex(self._buf))
                        self._buf = ""
                        self._in_block = False
                    return out
                block_text = self._buf[:close_idx]
                self._buf = self._buf[close_idx:]
                self._in_block = False
                out.append(normalize_latex(block_text))
                continue

            open_idx = self._find_earliest(self._buf, self._OPENERS, with_len=False)
            if open_idx < 0:
                # لا opener — flush كل شيء ما عدا lookahead
                if len(self._buf) > self._LOOKAHEAD:
                    safe = self._buf[: -self._LOOKAHEAD]
                    self._buf = self._buf[-self._LOOKAHEAD :]
                    if safe:
                        out.append(safe)
                return out
            # وجدنا opener — emit ما قبله، ثم انتقل لوضع block
            prefix = self._buf[:open_idx]
            self._buf = self._buf[open_idx:]
            if prefix:
                out.append(prefix)
            self._in_block = True

    def flush(self) -> list[str]:
        """يجبر إصدار أي محتوى متبقٍ — يُستدعى عند انتهاء الـ stream."""
        if not self._buf:
            return []
        normalized = normalize_latex(self._buf)
        self._buf = ""
        self._in_block = False
        return [normalized] if normalized else []

    @staticmethod
    def _find_earliest(text: str, markers: tuple[str, ...], with_len: bool) -> int:
        """
        يبحث عن أقدم marker في text.
        - with_len=False: يُعيد موضع البداية (للـ opener)
        - with_len=True : يُعيد موضع النهاية (للـ closer)
        """
        best = -1
        best_end = -1
        for m in markers:
            i = text.find(m)
            if i < 0:
                continue
            end = i + len(m)
            if best < 0 or i < best:
                best = i
                best_end = end
        return best_end if with_len else best


__all__ = ["LatexStreamNormalizer", "normalize_latex"]
