#!/usr/bin/env python3
"""التأجيل يُصرَّح، ولا يُعمَّر بعد بلاغه (ISS-199 · يمدّد D-206 L11 · D-186 · D-189).

**لماذا هذه البوّابة موجودة:**

الدفعة ``3176fe6`` وصلت ``live-e2e`` بـ``required-ci`` **ولم تلمس رأس** ``live-e2e.yml``
الذي يقول «ولماذا **ليس** في ``required-ci``». فصارت بوّابةٌ **حاجبة** مُوجَّهةً إلى
**ISS-150** — وهو 🔴 مفتوحٌ في ``.memory/issues.md`` بقرارٍ مكتوبٍ بتأجيل إصلاحه. وبوّابةٌ
تحجب على عطبٍ قرّر المستودع تأجيله لا تحرس ضدّ انحدار: تمنع كلّ دفعة، بالبناء.

والعلاج ليس إسكات المخالفة بل **تصريحها**: ``scripts/e2e/deferred_findings.py`` هو الموطن
الوحيد لما يُبلَّغ ولا يحجب. وهذه البوّابة تمنع الأخطار الأربعة لذلك السجلّ:

1. **تأجيلٌ يُعمِّر بعد بلاغه** — بلاغٌ أُغلق وبقي مؤجَّلاً يعني مخالفةً حقيقية تمرّ
   صامتةً إلى الأبد. وهو التقادم الصامت الذي يحرّمه D-188، وقد وقع حرفيّاً في هذا
   المستودع بين 2026-05-09 و2026-07-29.
2. **إعفاءٌ بلا سبب منطوق** — الخانة الفارغة تُقرأ نجاحاً (D-206 L11).
3. **قائمةٌ ثانية** — ثلاث قوائم لنيّةٍ واحدة أنتجت ISS-139؛ فكلّ سكربتٍ يُصدِر مخالفةً
   موسومةً ببلاغ **يجب** أن يقرأ هذا السجلّ لا أن يحمل قائمته (D-186).
4. **دَينٌ يكبر بصمت** — العدد مُجمَّد ويتقلّص فقط، **وفي الاتجاهين**: أُغلق بندٌ ولم
   يُحدَّث الرقم ⇒ أحمر أيضاً (نمط ``check_correlated_http`` — D-189).

⛔ **ولا تشهد هذه البوّابة بما لم تقرأ** (D-208 #6): ملفٌّ يتعذّر تحليله يُبلَّغ عنه
انتهاكاً، ولا يُبتلَع بـ``except SyntaxError``.

تُشغَّل ضمن وظيفة ``guardrails``. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_ISSUES = REPO_ROOT / ".memory" / "issues.md"
E2E_DIR = REPO_ROOT / "scripts" / "e2e"
REGISTRY = E2E_DIR / "deferred_findings.py"

#: مسار الاستيراد الذي يجب أن يسلكه كل سكربتٍ يُصدِر مخالفةً موسومةً ببلاغ.
REGISTRY_MODULE = "scripts.e2e.deferred_findings"

#: رمزُ حالةٍ يعني «مفتوح». المُغلَق (🟢) ممنوعٌ في السجلّ، وغيابُ الرمز كلّياً ممنوع
#: كذلك — الحالة تُصرَّح ولا تُستنتَج (D-206 L11).
OPEN_MARKERS = ("🔴", "🟡")
CLOSED_MARKER = "🟢"

#: أدنى طولٍ لسببٍ يُقبَل تصريحاً. «سببٌ» من كلمتين اعتذارٌ لا تصريح.
MIN_REASON_CHARS = 60

_ISSUE_ID = re.compile(r"\bISS-\d{3}\b")

#: الوسمُ كما يُكتب داخل **نصّ المخالفة** نفسها — `… (ISS-150)`. الشكل المُقوَّس هو
#: المُميِّز: التعليقات والوثائق تذكر البلاغات بلا هذا الشكل أو خارج شجرة البناء.
_TAGGED_PROBLEM = re.compile(r"\(ISS-\d{3}")

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _load_registry() -> tuple[dict[str, str], int]:
    """يقرأ السجلّ **بالاستيراد** لا بالتحليل النصّي — القيم هي ما يُنفَّذ فعلاً."""
    sys.path.insert(0, str(REPO_ROOT))
    from scripts.e2e.deferred_findings import (
        DEFERRED_FINDINGS,
        FROZEN_DEFERRED_COUNT,
    )

    return dict(DEFERRED_FINDINGS), int(FROZEN_DEFERRED_COUNT)


def _issue_status_line(issues_text: str, issue_id: str) -> str | None:
    """سطرُ عنوان البلاغ في ``.memory/issues.md`` — أو ``None`` إن لم يوجد أصلاً."""
    for line in issues_text.splitlines():
        if line.startswith(f"## {issue_id} ") or line.startswith(f"## {issue_id}("):
            return line
    return None


def _check_declared_issues_are_open(deferred: dict[str, str], issues_text: str) -> None:
    """كل بلاغٍ مؤجَّل موجودٌ **ومفتوح** — والمُغلَق يُحمِّر لا يُنسى."""
    for issue_id, reason in sorted(deferred.items()):
        line = _issue_status_line(issues_text, issue_id)
        if line is None:
            _fail(f"{issue_id} مؤجَّلٌ في السجلّ ولا عنوان له في `.memory/issues.md` — تأجيلُ عدم.")
            continue
        if CLOSED_MARKER in line:
            _fail(
                f"{issue_id} **مُغلَق** ({CLOSED_MARKER}) وما زال مؤجَّلاً — "
                "احذف سطره من `deferred_findings.py` ليعود حاجباً (D-188)."
            )
            continue
        if not any(marker in line for marker in OPEN_MARKERS):
            _fail(
                f"{issue_id} بلا رمز حالةٍ في عنوانه — الحالة تُصرَّح ولا تُستنتَج "
                f"(D-206 L11). المتوقَّع أحد {OPEN_MARKERS}."
            )
            continue
        if len(reason.strip()) < MIN_REASON_CHARS:
            _fail(f"{issue_id} سببُ تأجيله أقصر من {MIN_REASON_CHARS} حرفاً — تصريحٌ لا يصرّح.")
            continue
        _pass(f"{issue_id} مؤجَّلٌ بسببٍ منطوق، والبلاغ مفتوحٌ فعلاً.")


def _check_frozen_count(deferred: dict[str, str], frozen: int) -> None:
    """العدد يتقلّص فقط، ويُطابق الواقع في الاتجاهين."""
    actual = len(deferred)
    if actual != frozen:
        _fail(
            f"FROZEN_DEFERRED_COUNT={frozen} والسجلّ يحمل {actual} — "
            "الرقم يُحدَّث مع كل تقلّص، وإلّا كان دَيناً مكتوماً (D-189)."
        )
        return
    _pass(f"العدد المُجمَّد يطابق السجلّ: {actual}.")


def _module_imports_registry(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom) and node.module == REGISTRY_MODULE
        for node in ast.walk(tree)
    )


def _docstring_ids(tree: ast.Module) -> set[int]:
    """مُعرَّفات عُقَد الوثائق — تُستثنى لأنّ ذكر البلاغ فيها توثيقٌ لا إصدار مخالفة."""
    ids: set[int] = set()
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            ids.add(id(first.value))
    return ids


def _emits_tagged_problem(tree: ast.Module) -> bool:
    """هل يبني هذا السكربت نصَّ مخالفةٍ موسوماً ببلاغ؟

    الفحص على **الحرفيات النصّية في شجرة البناء** لا على المصدر الخام: التعليق
    ليس عُقدةً، والوثائق مُستثناة صراحةً. وبلا هذه الدقّة تُبلِّغ البوّابة عن ملفٍّ
    يذكر بلاغاً في تعليق — وبوّابةٌ تصيح بلا ذئب تُدرِّب الناس على تجاهلها، وهو
    العطب نفسه الذي وُلدت هذه الدفعة لعلاجه.
    """
    skip = _docstring_ids(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or id(node) in skip:
            continue
        if isinstance(node.value, str) and _TAGGED_PROBLEM.search(node.value):
            return True
    return False


def _check_single_source(deferred: dict[str, str]) -> None:
    """لا قائمةَ ثانية: كل سكربتٍ يُصدِر مخالفةً موسومةً ببلاغ يقرأ هذا السجلّ."""
    scripts = sorted(p for p in E2E_DIR.glob("*.py") if p != REGISTRY)
    checked = 0
    for path in scripts:
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:  # ⛔ لا نشهد بما لم نقرأ (D-208 #6)
            _fail(f"{path.relative_to(REPO_ROOT)} يتعذّر تحليله ({exc}) — لا يُقال إنّه نظيف.")
            continue
        emits_tagged = _emits_tagged_problem(tree)
        if emits_tagged and not _module_imports_registry(tree):
            _fail(
                f"{path.relative_to(REPO_ROOT)} يُصدِر مخالفاتٍ موسومةً ببلاغ ولا يستورد "
                f"`{REGISTRY_MODULE}` — قائمةٌ ثانية للنيّة نفسها (D-186)."
            )
            continue
        if emits_tagged:
            checked += 1
    if checked == 0:
        _fail("لا سكربت e2e واحد يمرّ عبر السجلّ — بوّابةٌ بلا مرمى (ISS-148).")
        return
    _pass(f"{checked} سكربتاً يقرأ السجلّ الواحد، و{len(deferred)} بنداً مُصرَّحاً فيه.")


def main() -> int:
    _FAILURES.clear()  # قابلةٌ للاستدعاء أكثر من مرّة في نفس العملية (اختبارات البوّابة)
    if not REGISTRY.exists():
        _fail(f"السجلّ مفقود: {REGISTRY}")
        return 1
    if not MEMORY_ISSUES.exists():
        _fail("`.memory/issues.md` مفقود — لا مرجع لحالة البلاغات.")
        return 1

    deferred, frozen = _load_registry()
    issues_text = MEMORY_ISSUES.read_text(encoding="utf-8")

    _check_declared_issues_are_open(deferred, issues_text)
    _check_frozen_count(deferred, frozen)
    _check_single_source(deferred)

    if _FAILURES:
        print(f"\n❌ e2e deferred findings: {len(_FAILURES)} انتهاكاً.")
        return 1
    print("\n✅ e2e deferred findings: كل تأجيلٍ مُصرَّحٌ ببلاغٍ مفتوح، والسجلّ واحدٌ ومُجمَّد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
