#!/usr/bin/env python3
"""ISS-148 — كلّ نداءٍ للتفريغ الرمزي يُمرِّر دفتر ما سُلِّم للطالب.

## لماذا هذه البوّابة موجودة

`_build_symbolic_reveal` يقبل `delivered` — مجموعة الخطوات المعروضة سابقاً — فيحذف ما
سبق تسليمه بدل إعادة تفريغه (D-158). القاعدة سليمة؛ **تطبيقها لم يكن**: من **٧** مواضع
نداء كان **واحد** فقط يُمرِّرها (`turn_engine.py:258`).

والنتيجة فشلٌ باتّجاهين متعاكسين، كلاهما رآه طالبٌ حقيقي في المحادثة 837:

  • بلا `delivered` ⇒ يُعاد تفريغ كل شيء. الرسالتان 4611 و4615 كشفتا `165` مرّتين.
  • بـ`delivered` كاملة ⇒ يُحذَف كلّ بلوك فيبقى العنوان والخاتمة وحدهما. الرسالة
    4613: «لنُكمل معاً خطوة بخطوة حتى النهاية:» ثمّ ولا خطوة — ١٣٦ حرفاً من العدم.

**معاملٌ ينساه ستّةٌ من سبعة ليس صمّام أمان، بل احتمالُ عطبٍ موزَّع على مواضع النداء.**
الدفاع الصحيح أن يكون النسيان **غير مُمثَّل**: `delivered` معامل إلزامي، وهذه البوّابة
تُثبت أن كلّ موضع نداء يُمرِّره.

## الدَّين المُجمَّد

`_FROZEN_DEBT` يبدأ **فارغاً** ويتقلّص فقط (سابقة D-105/D-187). موضعٌ جديد بلا
`delivered` ⇒ CI أحمر.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEARCH_ROOTS = ("app", "microservices", "shared")

#: الدالّة المحروسة والمعامل الإلزامي.
GUARDED_CALL = "_build_symbolic_reveal"
REQUIRED_KWARG = "delivered"

#: الدَّين المُجمَّد — يتقلّص فقط. ممنوع إضافة أي مدخل بلا قرار معماري.
_FROZEN_DEBT: dict[str, str] = {}


def _iter_python_files():
    for root in SEARCH_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        yield from sorted(base.rglob("*.py"))


def _call_name(node: ast.Call) -> str | None:
    """اسم الدالّة المُستدعاة — يغطّي `self.x()` و`cls.x()` و`x()`."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _guarded_calls() -> list[tuple[str, bool]]:
    """كل مواضع نداء الدالّة المحروسة: ``(موضع، هل يُمرِّر الدفتر؟)``."""
    found: list[tuple[str, bool]] = []
    for path in _iter_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — ملفّ غير صالح يلتقطه lint
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) != GUARDED_CALL:
                continue
            passes = any(
                keyword.arg in (REQUIRED_KWARG, None)  # None = **kwargs
                for keyword in node.keywords
            )
            found.append((f"{rel}:{node.lineno}", passes))
    return found


def main() -> int:
    failures: list[str] = []
    calls = _guarded_calls()

    for location, passes_ledger in calls:
        if passes_ledger or location in _FROZEN_DEBT:
            continue
        failures.append(
            f"{location}: نداء {GUARDED_CALL}(…) بلا {REQUIRED_KWARG!r} — "
            f"سيُعاد تفريغ ما سُلِّم أصلاً للطالب (ISS-148)."
        )

    # دَينٌ أُغلِق ولم يُحدَّث الرقم = البوّابة تحرس ماضياً.
    live_locations = {location for location, _ in calls}
    for stale in sorted(set(_FROZEN_DEBT) - live_locations):
        failures.append(
            f"{stale}: مُدرَج في الدَّين المُجمَّد ولا نداء هناك — "
            f"احذف المدخل (الدَّين يتقلّص، ولا يحرس ماضياً)."
        )

    checked = len(calls)
    if failures:
        print("❌ دفتر التفريغ الرمزي مخروق (ISS-148):\n")
        for failure in failures:
            print(f"  • {failure}")
        return 1

    print(
        f"✅ كل مواضع نداء {GUARDED_CALL} ({checked}) تُمرِّر {REQUIRED_KWARG!r}؛ "
        f"الدَّين المُجمَّد {len(_FROZEN_DEBT)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
