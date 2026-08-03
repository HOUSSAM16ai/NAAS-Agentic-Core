#!/usr/bin/env python3
"""ISS-149 (F1) — بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف.

## لماذا هذه الوحدة موجودة

سبعُ بوّابات كانت تحمل هذا الشكل حرفياً:

```python
try:
    tree = ast.parse(path.read_text(...))
except SyntaxError:
    return []          # ← ملفٌّ تعذّر تحليله = صفر انتهاكات = أخضر صامت
```

فملفٌّ لا يُحلَّل يُبلَّغ عنه بأنه **خالٍ من الانتهاكات**. وهذه ليست حالةً نظرية:
على Python 3.11 (والمشروع يستعمل صيغة PEP 695) قرأتْ `check_no_new_any` صفرَ
`Any` في `app/services/skills/base.py` بينما الدَّين المُجمَّد ١٢ — لا لأن أحداً
نظّف الملفّ بل لأنها **عجزت عن قراءته**. هناك نجا المشروع بالمصادفة وحدها: ذلك
الدَّين ثنائي الاتجاه فصرخ. أمّا البوّابات التي تعدّ الانتهاكات تصاعدياً — ومنها
`check_no_shell_true` (أمنُ الصدفة، دَينه **صفر**) و`check_intent_single_source`
(مصدر النيّة الواحد) و`check_correlated_http` (أثر التتبّع) — فملفٌّ غير مقروء
عندها **أخضر تام**.

وهذا هو **«الثمن الثالث»** في `docs/architecture/ENGINEERING_DOCTRINE.md`: *صمتٌ
يُقرأ نجاحاً*. العقيدة تسمّيه منذ D-207 ولم يكن له مثالٌ حيّ **داخل فوارضها هي**.

## العقد

`parse_source` تُحلّل أو **ترفع**. لا قيمة ثالثة. والبوّابة التي تستعملها تلفّ
`main` بـ`run_gate` فيصير الملفّ غير المقروء **فشلاً صريحاً** لا صمتاً.

الاستثناء المشروع الوحيد أن تُبلِّغ البوّابةُ الخطأ **انتهاكاً** بنفسها — وهو ما
تفعله `check_test_hygiene` بحقّ (تُرجِع `SyntaxError` ضمن قائمة الانتهاكات).
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path


class UnparsableSourceError(Exception):
    """ملفٌّ مصدرٍ تعذّر تحليله — نتيجةٌ مجهولة، لا نتيجةٌ نظيفة."""

    def __init__(self, path: Path, error: SyntaxError) -> None:
        self.path = path
        self.error = error
        super().__init__(
            f"تعذّر تحليل {path}: {error}\n"
            f"   البوّابة **لم تفحص** هذا الملفّ، فلا تستطيع أن تشهد بنظافته.\n"
            f"   (المشروع يتطلّب Python 3.12+ — راجع `target-version` في pyproject.toml.)"
        )


def parse_source(path: Path) -> ast.Module:
    """يُحلّل ملفَّ بايثون أو يرفع `UnparsableSourceError` — الصمت ليس خياراً."""
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="ignore"), filename=str(path))
    except SyntaxError as exc:
        raise UnparsableSourceError(path, exc) from exc


def run_gate(main_fn: Callable[[], int]) -> int:
    """يُشغّل `main` ويحوّل الملفَّ غير المقروء إلى فشلٍ صريح برمز خروج 1."""
    try:
        return main_fn()
    except UnparsableSourceError as exc:
        print(f"❌ {exc}")
        return 1
