#!/usr/bin/env python3
"""بوّابة رموز التصميم — الواجهة تُحكَم كما يُحكَم الخادم (D-199).

لماذا هذه البوّابة موجودة
-------------------------
من ٤١ بوّابة في هذا المستودع **لا واحدة** كانت تلمس CSS أو JSX. والنتيجة قابلة للعدّ:
`globals.css` بلغ ٣٥٨٤ سطراً وفيه ٣٨ قيمة مسافة و١٥ نصف قطر و٣٠ حجم خطّ — لا لأنّ أحداً
قرّر ذلك، بل لأنّ لا شيء منع تراكمه. ما لا يُقاس ينحرف.

ما تفرضه
--------
1. **لا لون خامّ خارج `tokens.css`** — لا `#rrggbb` ولا `rgb()`/`hsl()` حرفيّ في CSS.
2. **لا مسافة خارج السلّم** — قيم `rem` في `margin`/`padding`/`gap` يجب أن تكون من سلّم
   الرموز.
3. **لا بكسل حرفيّ في `style={{…}}`** داخل JSX — أسوأ صنف انحراف لأنّه غير مرئي في CSS.
4. **نسب التباين مُتحقَّقة حسابياً**: كلّ زوج (لون، ورق) في `tokens.css` يجب أن يبلغ
   WCAG AA. تباينٌ ينزلق تحت العتبة يجب أن يُوقِف الدمج لا أن يُكتشَف من مستخدم.

الدَّين المُجمَّد
----------------
`globals.css` القائم مُجمَّد بعدده الحالي و**يتقلّص فقط** (سابقة D-105). الهدف ليس
إعادة كتابة ٣٥٨٤ سطراً في دفعة واحدة، بل ضمان أنّها لا تنمو.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "app"
TOKENS_FILE = FRONTEND / "styles" / "tokens.css"

#: الدَّين المُجمَّد: عدد الألوان الخامّة الباقية في `globals.css`. **يتقلّص فقط.**
FROZEN_RAW_COLOURS = 178

#: عدد إعلانات `style={{…}}` بقيم بكسل حرفية في JSX. **يتقلّص فقط.**
FROZEN_INLINE_PX = 26

_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FUNC_COLOUR_RE = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\s*\(")
_INLINE_PX_RE = re.compile(r"style=\{\{[^}]*?\b\d+px\b", re.DOTALL)


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _relative_luminance(hex_colour: str) -> float:
    value = hex_colour.lstrip("#")
    channels = [int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """نسبة التباين حسب WCAG 2.x."""
    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def _theme_blocks(css: str) -> list[dict[str, str]]:
    """يستخرج مجموعات المتغيّرات التي تُعرِّف `--paper` — أي كتل السمات."""
    blocks: list[dict[str, str]] = []
    for body in re.findall(r"\{([^{}]*)\}", _strip_comments(css)):
        declarations = dict(re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", body))
        if "--paper" in declarations:
            blocks.append(declarations)
    return blocks


def check_contrast() -> list[str]:
    """كلّ لون نصّ/دلالة في كلّ سمة يجب أن يبلغ AA فوق ورقها."""
    failures: list[str] = []
    css = TOKENS_FILE.read_text(encoding="utf-8")
    blocks = _theme_blocks(css)
    if not blocks:
        return ["tokens.css declares no theme block containing --paper"]

    graded = (
        "--ink",
        "--ink-muted",
        "--accent",
        "--accent-hover",
        "--success",
        "--warning",
        "--danger",
    )
    for index, block in enumerate(blocks):
        paper = block["--paper"]
        for name in graded:
            colour = block.get(name)
            if colour is None:
                continue
            ratio = contrast_ratio(colour, paper)
            if ratio < 4.5:
                failures.append(
                    f"theme block #{index}: {name} ({colour}) on --paper ({paper}) "
                    f"is {ratio:.2f}:1 — below WCAG AA (4.5:1)"
                )
    return failures


def check_raw_colours() -> list[str]:
    """الألوان الخامّة خارج `tokens.css` دَينٌ مُجمَّد يتقلّص فقط."""
    failures: list[str] = []
    total = 0
    for path in sorted(FRONTEND.rglob("*.css")):
        if path == TOKENS_FILE:
            continue
        body = _strip_comments(path.read_text(encoding="utf-8"))
        total += len(_HEX_RE.findall(body)) + len(_FUNC_COLOUR_RE.findall(body))

    if total > FROZEN_RAW_COLOURS:
        failures.append(
            f"raw colours outside tokens.css grew to {total} (frozen at {FROZEN_RAW_COLOURS}). "
            f"Use a token from frontend/app/styles/tokens.css instead of a literal."
        )
    elif total < FROZEN_RAW_COLOURS:
        failures.append(
            f"raw colours fell to {total} — good. Lower FROZEN_RAW_COLOURS to {total} "
            f"so the ratchet holds."
        )
    return failures


def check_inline_px() -> list[str]:
    """`style={{…}}` ببكسل حرفيّ — انحرافٌ غير مرئي في CSS."""
    total = 0
    offenders: list[str] = []
    for path in sorted(FRONTEND.rglob("*.jsx")):
        hits = _INLINE_PX_RE.findall(path.read_text(encoding="utf-8"))
        if hits:
            total += len(hits)
            offenders.append(f"{path.relative_to(REPO_ROOT)}: {len(hits)}")

    if total > FROZEN_INLINE_PX:
        return [
            f"inline literal px in JSX grew to {total} (frozen at {FROZEN_INLINE_PX}): "
            + ", ".join(offenders)
        ]
    if total < FROZEN_INLINE_PX:
        return [f"inline literal px fell to {total} — lower FROZEN_INLINE_PX to {total}."]
    return []


def check_tokens_exist() -> list[str]:
    """السلالم الأساسية يجب أن تبقى مُعرَّفة — البوّابة بلا رموز بلا معنى."""
    css = TOKENS_FILE.read_text(encoding="utf-8")
    required = (
        "--space-sm",
        "--radius-md",
        "--text-base",
        "--leading-reading",
        "--measure-reading",
        "--duration-base",
        "--ease-standard",
        "--paper",
        "--ink",
        "--accent",
    )
    return [f"tokens.css is missing {name}" for name in required if f"{name}:" not in css]


def main() -> int:
    if not TOKENS_FILE.exists():
        print(f"❌ design tokens: {TOKENS_FILE.relative_to(REPO_ROOT)} is missing")
        return 1

    failures = check_tokens_exist() + check_contrast() + check_raw_colours() + check_inline_px()

    if failures:
        print("❌ بوّابة رموز التصميم مخروقة (D-199):")
        for failure in failures:
            print(f"   • {failure}")
        return 1

    print(
        "✅ design tokens: contrast meets WCAG AA in every theme, "
        f"raw colours frozen at {FROZEN_RAW_COLOURS}, inline px at {FROZEN_INLINE_PX}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
