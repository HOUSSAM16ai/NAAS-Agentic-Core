#!/usr/bin/env python3
"""ISS-149 (F1) — لا بوّابةَ تبتلع خطأ التحليل فتشهد بنظافة ملفٍّ لم تقرأه.

## لماذا هذه البوّابة موجودة

سبعُ بوّابات كانت تُرجِع «صفر انتهاكات» عن ملفٍّ عجزت عن تحليله:

```python
except SyntaxError:
    return []          # ← أخضر صامت
```

ومنها `check_no_shell_true` — دَينُها **صفر** وهي حارسُ حقن الصدفة (D-187)،
و`check_intent_single_source` (مصدر النيّة الواحد — D-186)، و`check_correlated_http`
(أثر التتبّع — D-189). أي أنّ أشدّ ما يتّكئ عليه الدستور كان قابلاً لأن يمرّ
أخضرَ على شجرةٍ لم تُقرأ.

والدليل حيّ لا نظري: على Python 3.11 أبلغت `check_no_new_any` أن
`app/services/skills/base.py` صار `0× Any` بينما الدَّين المُجمَّد ١٢ — لا لأن أحداً
نظّفه بل لأنها **لم تستطع قراءته**. نجا المشروع بالمصادفة: ذلك الدَّين ثنائي الاتجاه
فصرخ. والبوّابات التي تعدّ تصاعدياً لا تصرخ أبداً.

هذا **«الثمن الثالث»** في `docs/architecture/ENGINEERING_DOCTRINE.md` — *صمتٌ يُقرأ
نجاحاً* — واقعاً داخل الفوارض نفسها.

## ما تفرضه

أي `except SyntaxError` في `scripts/fitness/` يجب أن يُنتج **فشلاً أو انتهاكاً**،
لا قيمةً فارغة. يُرصَد بـ**AST**: مُعالِجٌ جسمُه `return []` / `return 0` /
`return False` / `continue` / `pass` هو ابتلاعٌ صامت.

الاستثناء المشروع أن تُبلِّغ البوّابةُ الخطأ انتهاكاً بنفسها — وهو ما تفعله
`check_test_hygiene` بحقّ (`return [f"{rel}: SyntaxError: {exc}"]`): قيمةٌ **غير
فارغة** تحمل الخطأ. لذلك لا تحتاج استثناءً مكتوباً؛ الفحص يقبلها بنيوياً.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FITNESS_DIR = REPO_ROOT / "scripts/fitness"

#: دَينٌ مُجمَّد — **فارغ عمداً**، يتقلّص فقط في الاتجاهين (سابقة D-105/D-187/D-189).
_FROZEN_DEBT: dict[str, str] = {}


#: أسماء نداءاتٍ تُسجّل انتهاكاً فعلياً (لا مجرّد طباعة).
_RECORDING_CALLS: frozenset[str] = frozenset({"append", "add", "extend", "_fail", "fail"})


def _records_a_failure(handler: ast.ExceptHandler) -> bool:
    """هل يُسجّل المُعالِجُ فشلاً بحيث يظهر في نتيجة البوّابة؟

    الطباعة وحدها **ليست** تسجيلاً: بوّابةٌ تطبع ثم تُرجِع صفراً تبقى خضراء في CI،
    وهي بالضبط الحالة التي تحرسها هذه البوّابة. المطلوب أثرٌ في القيمة المُرجَعة:
    عدّادٌ يزيد، أو قائمةٌ تُلحَق بها، أو `_fail` تُستدعى.
    """
    for node in ast.walk(handler):
        if isinstance(node, ast.AugAssign):
            return True
        # `ok = False` — إسنادُ الفشل إلى علَمٍ يحكم رمزَ الخروج (نمط قائم).
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and node.value.value is False
        ):
            return True
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name in _RECORDING_CALLS:
                return True
    return False


def _returns_nothing_meaningful(value: ast.expr | None) -> bool:
    """هل القيمة المُرجَعة «لا شيء» (None/0/False/سلسلة أو حاوية فارغة)؟"""
    if value is None:
        return True
    if isinstance(value, ast.Constant):
        return value.value in (0, False, None, "")
    if isinstance(value, (ast.List, ast.Dict, ast.Tuple, ast.Set)):
        return not (getattr(value, "elts", None) or getattr(value, "keys", None))
    return False


def _is_silent_swallow(handler: ast.ExceptHandler) -> bool:
    """هل يبتلع المُعالِجُ الخطأ صمتاً (يُرجِع فراغاً أو يتخطّى بلا تسجيل)؟"""
    for node in handler.body:
        if isinstance(node, ast.Raise):
            return False
        if isinstance(node, (ast.Continue, ast.Pass)):
            return not _records_a_failure(handler)
        if isinstance(node, ast.Return):
            if not _returns_nothing_meaningful(node.value):
                return False
            return not _records_a_failure(handler)
    return False


def _catches_syntax_error(handler: ast.ExceptHandler) -> bool:
    names: list[str] = []
    target = handler.type
    if isinstance(target, ast.Name):
        names = [target.id]
    elif isinstance(target, ast.Tuple):
        names = [e.id for e in target.elts if isinstance(e, ast.Name)]
    elif target is None:  # `except:` العارية تبتلع كل شيء ومنه SyntaxError
        return True
    return any(n in ("SyntaxError", "Exception", "BaseException") for n in names)


def _parses_a_file(block: ast.Try) -> bool:
    """هل يُحلّل جسمُ `try` **ملفَّ مصدرٍ** (لا تعبيراً)؟

    ISS-149 — تضييقٌ ضروري: `ast.literal_eval(node.value)` ترفع `SyntaxError`
    على عقدةٍ غير حرفية، وتخطّيها سلوكٌ صحيح لا ابتلاع. القاعدة تخصّ **الملفّ**
    الذي لم يُقرأ، لا التعبير الذي لم يكن حرفياً. بلا هذا التضييق تُنتج البوّابة
    إيجابيةً كاذبة — وبوّابةٌ تصرخ في غير موضعها تُعلَّم الناسُ تجاهلَها.
    """
    for node in ast.walk(ast.Module(body=block.body, type_ignores=[])):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name in ("parse", "parse_source", "read_text"):
            return True
    return False


def main() -> int:
    failures = 0
    seen_debt: set[str] = set()

    for path in sorted(FITNESS_DIR.glob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            # القاعدة على نفسها: هذه البوّابة لا تبتلع ما تحرّمه.
            print(f"\u274c {rel}: البوّابة نفسها لا تُحلَّل — {exc}")
            failures += 1
            continue

        for block in ast.walk(tree):
            if not isinstance(block, ast.Try) or not _parses_a_file(block):
                continue
            for handler in block.handlers:
                if not _catches_syntax_error(handler) or not _is_silent_swallow(handler):
                    continue
                key = f"{rel}:{handler.lineno}"
                if key in _FROZEN_DEBT:
                    seen_debt.add(key)
                    continue
                print(
                    f"\u274c {rel}:{handler.lineno}: خطأ التحليل يُبتلَع صمتاً — البوّابة\n"
                    f"   تشهد بنظافة ملفٍّ لم تقرأه (ISS-149\u00b7F1). استعمل\n"
                    f"   `scripts/fitness/_ast_util.parse_source` + `run_gate`، أو أبلِغ\n"
                    f"   الخطأ **انتهاكاً** كما تفعل `check_test_hygiene`."
                )
                failures += 1

    for key in sorted(set(_FROZEN_DEBT) - seen_debt):
        print(f"\u274c دَينٌ مُجمَّد لم يعد موجوداً: {key!r} — احذفه من `_FROZEN_DEBT`.")
        failures += 1

    if failures:
        print(f"\n\u274c check_gate_parse_honesty: {failures} انتهاكاً.")
        return 1
    print("\u2705 لا بوّابة تبتلع خطأ التحليل — «لم أقرأه» لا تُقرأ «نظيف».")
    return 0


if __name__ == "__main__":
    sys.exit(main())
