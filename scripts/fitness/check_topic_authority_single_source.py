#!/usr/bin/env python3
"""بوّابة سلطة الموضوع الواحدة — D-266 / ISS-159 (وتُغلق فارض D-193 الغائب).

## الكارثتان اللتان وُلدت منهما

**١. الموضوع يُختطَف (ISS-159).** بلاغ المالك: «النظام يتعامل مع كل سؤال كأنه تمرين
احتمالات». والجذر بنيوي: الصيغة نفسها مكرَّرة في **ستّة** مواضع —

```python
if _canonical is not None and _canonical.canonical_id != "probability":
```

وسجلّ الاسترجاع (`CANONICAL_TOPICS`) يعرف **ثلاثة مواضيع رياضية لا غير**، فسؤال
الفيزياء يُرجِع `None` ويسقط الشرط عند ساقه الأولى — **فلا يعمل الحارس أصلاً**.
كلّ إصلاحٍ سابق كان يضيف الموضوع الناقص إلى القائمة التي أخطأت، فيُشفى العَرَض ويبقى
الصنف. هذه البوّابة تقتل الصنف: نسخةٌ سابعة **مستحيلة** لا مكروهة (سابقة D-186).

**٢. فارضُ D-193 لم يُكتب قطّ.** `shared/curriculum/registry.py` يقول نصّاً في
مقدّمته: «تفرضه بوّابة `scripts/fitness/check_curriculum_single_source`» — وهي
**غير موجودة على القرص**. أي أنّ قانون «تعريف المفهوم واحد» كان بلا فارضٍ طوال الوقت،
وهو **بالضبط** لماذا أمكن لثلاثة تصنيفات للموضوع أن تتفرّق حتى وقعت ISS-159. هذه
البوّابة ترث ذلك الفرض، وتُصحَّح الإحالة في المصدر لتسمّيها.

## ما تفحصه

1. **صيغة الحارس المكسور محظورة**: أيّ مقارنةٍ بحرفية `"probability"` على
   `canonical_id` خارج `topic_authority.py` ⇒ أحمر. الدَّين المُجمَّد **فارغ**.
2. **حاسمٌ واحد**: `is_foreign_to_probability` مُعرَّفة في موضعٍ واحد فقط.
3. **لا سجلّ مواضيع ثانٍ**: مُعرَّفات مفاهيم الاحتمالات في `topic_authority` كلّها
   موجودة فعلاً في `shared/curriculum` — انتقاءٌ من السجلّ لا تعريفٌ ثانٍ له (D-193).
4. **مفردات المادة موطنها `shared/curriculum`**: `SUBJECT_MARKERS` مُعرَّفة هناك وحدها.
5. **لا أرقام تمرينٍ عارية كمفاتيح موضوع**: `"165"`/`"14"` لا تُستعمل مؤشّراً على
   سياق الاحتمالات — كانت مكتوبةً `r"\\b165\\b"` داخل `m in t` (مطابقة **سلسلة** لا
   تعبير نمطي)، فلم تكن تطابق شيئاً بينما يَعِد التعليق بحدود كلمات.

**لا تُستورد من `app/`** — AST + نصّ خالص. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: الموطن الوحيد المسموح له بحمل قرار «هل هذا احتمالات؟».
AUTHORITY = "app/services/capabilities/topic_authority.py"

#: الموطن الوحيد لمفردات المادة (D-193 — تعريف المفهوم والمادة واحد).
CURRICULUM = "shared/curriculum/registry.py"

SCAN_ROOTS = ("app", "shared", "microservices")

#: دَينٌ مُجمَّد يتقلّص فقط. **فارغ** — الصيغة المكسورة أُزيلت من المواضع الستّة كلّها.
_FROZEN_DEBT: dict[str, int] = {}

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCAN_ROOTS:
        directory = REPO_ROOT / root
        if directory.is_dir():
            files.extend(sorted(directory.rglob("*.py")))
    return files


def _parse(path: Path) -> ast.Module | None:
    """يُرجِع الشجرة أو `None` — و`None` **تُبلَّغ** ولا تُقرأ نظافةً (D-208 §6)."""
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError) as exc:
        _fail(
            f"{path.relative_to(REPO_ROOT)}: تعذّرت القراءة ({exc.__class__.__name__}) — لا تُقرأ نظافةً"
        )
        return None


def _check_broken_guard(files: list[Path]) -> None:
    """أيّ مقارنة `... != "probability"` أو `== "probability"` خارج الحاسم الواحد."""
    offenders: dict[str, int] = {}
    for path in files:
        rel = str(path.relative_to(REPO_ROOT))
        if rel == AUTHORITY:
            continue
        tree = _parse(path)
        if tree is None:
            continue
        hits = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            has_literal = any(
                isinstance(op, ast.Constant) and op.value == "probability" for op in operands
            )
            if not has_literal:
                continue
            # نستهدف مقارنة على سمة `canonical_id`/`concept_id` — لا كل ورودٍ للحرفية.
            touches_topic = any(
                isinstance(op, ast.Attribute) and op.attr in ("canonical_id", "concept_id")
                for op in operands
            )
            if touches_topic:
                hits += 1
        if hits:
            offenders[rel] = hits

    new = {rel: n for rel, n in offenders.items() if _FROZEN_DEBT.get(rel, 0) < n}
    if new:
        _fail(
            'صيغة الحارس المكسور (`canonical_id != "probability"`) خارج الحاسم الواحد: '
            f"{new} — استعمل `is_foreign_to_probability` (D-266 · ISS-159)"
        )
    closed = {rel: n for rel, n in _FROZEN_DEBT.items() if offenders.get(rel, 0) < n}
    if closed:
        _fail(f"دَينٌ أُغلق بلا تحديث `_FROZEN_DEBT`: {closed} — الدَّين يتقلّص في الاتجاهين")
    if not new and not closed:
        _pass(f"صفر نسخة من الحارس المكسور (دَينٌ مُجمَّد: {len(_FROZEN_DEBT)})")


def _check_single_predicate(files: list[Path]) -> None:
    definitions: list[str] = []
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "is_foreign_to_probability":
                definitions.append(str(path.relative_to(REPO_ROOT)))
    if definitions != [AUTHORITY]:
        _fail(
            f"`is_foreign_to_probability` يجب أن تُعرَّف في {AUTHORITY} وحده — وُجدت في {definitions}"
        )
    else:
        _pass("حاسمٌ واحد: `is_foreign_to_probability` بموطنٍ واحد")


def _check_concept_ids_are_real() -> None:
    """مُعرَّفات `PROBABILITY_CONCEPT_IDS` انتقاءٌ من السجلّ القانوني لا تعريفٌ ثانٍ (D-193)."""
    authority = (REPO_ROOT / AUTHORITY).read_text(encoding="utf-8")
    curriculum = (REPO_ROOT / CURRICULUM).read_text(encoding="utf-8")
    block = re.search(
        r"PROBABILITY_CONCEPT_IDS[^=]*=\s*frozenset\(\s*\{(.*?)\}\s*\)", authority, flags=re.S
    )
    if block is None:
        _fail(f"{AUTHORITY}: `PROBABILITY_CONCEPT_IDS` غير موجودة أو تغيّر شكلها")
        return
    ids = re.findall(r'"([a-z0-9_]+)"', block.group(1))
    if not ids:
        _fail(f"{AUTHORITY}: `PROBABILITY_CONCEPT_IDS` فارغة")
        return
    missing = [cid for cid in ids if f'concept_id="{cid}"' not in curriculum]
    if missing:
        _fail(f"مُعرَّفات ليست في السجلّ القانوني {CURRICULUM}: {missing} (D-193)")
    else:
        _pass(f"كل مُعرَّفات الاحتمالات الـ{len(ids)} مُنتقاة من السجلّ القانوني (D-193)")


def _check_subject_markers_single_home(files: list[Path]) -> None:
    homes: list[str] = []
    for path in files:
        rel = str(path.relative_to(REPO_ROOT))
        tree = _parse(path)
        if tree is None:
            continue
        for node in ast.walk(tree):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else ([node.target] if isinstance(node, ast.AnnAssign) else [])
            )
            for target in targets:
                if isinstance(target, ast.Name) and target.id == "SUBJECT_MARKERS":
                    homes.append(rel)
    if homes != [CURRICULUM]:
        _fail(f"`SUBJECT_MARKERS` يجب أن تُعرَّف في {CURRICULUM} وحده — وُجدت في {homes}")
    else:
        _pass(f"مفردات المادة بموطنٍ واحد: {CURRICULUM} (D-193)")


#: النمط المحظور **كقيمة**: حدودُ كلمةٍ حول رقم تمرينٍ بعينه. الفحص على AST لا على
#: النصّ، فالشرحُ الذي يقتبس النمط ليس استعمالاً له — وإلّا صار توثيق العطب انتهاكاً.
_BARE_NUMBER_LITERAL = re.compile(r"\\b(?:165|14|56)\\b")


def _docstring_nodes(tree: ast.Module) -> set[int]:
    """مُعرَّفات عُقد النصوص التي هي docstrings — تُستثنى من فحص القيم."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def _check_no_bare_exercise_numbers(files: list[Path]) -> None:
    """أرقام تمرينٍ بعينه ليست تعريفاً لمادة — و`r"\\b165\\b"` داخل `in` لا تطابق شيئاً."""
    offenders: list[str] = []
    for path in files:
        tree = _parse(path)
        if tree is None:
            continue
        skip = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in skip
                and _BARE_NUMBER_LITERAL.search(node.value)
            ):
                offenders.append(str(path.relative_to(REPO_ROOT)))
                break
    if offenders:
        _fail(
            f"أرقام تمرينٍ عارية كمفاتيح موضوع في: {sorted(set(offenders))} — "
            "نمطٌ خام داخل `in` مطابقةُ سلسلة لا تعبيرٌ نمطي (ISS-159)"
        )
    else:
        _pass("صفر رقم تمرينٍ عارٍ كمفتاح موضوع")


def main() -> int:
    files = _python_files()
    if not files:
        print("❌ لم يُعثر على ملفّات بايثون — جذور المسح خاطئة")
        return 1
    _check_broken_guard(files)
    _check_single_predicate(files)
    _check_concept_ids_are_real()
    _check_subject_markers_single_home(files)
    _check_no_bare_exercise_numbers(files)

    if _FAILURES:
        print(f"\n❌ {len(_FAILURES)} انتهاك — سلطة الموضوع ليست واحدة:")
        for failure in _FAILURES:
            print(f"   - {failure}")
        return 1
    print("\n✅ topic-authority: حاسمٌ واحد للموضوع، وسجلٌّ واحد للمفاهيم، وصفر حارسٍ مكسور.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
