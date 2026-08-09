#!/usr/bin/env python3
"""بوّابة تسميم الذاكرة — لا نصَّ نظامٍ بدور الطالب (D-229 · ISS-146).

## العطل الحيّ الذي وُلدت منه

في نافذة يونيو 2026 كُتب النصّ الداخلي «[توجيه تربوي] الطالب ما زال يبني هذا المفهوم…»
في جدول رسائل الإنتاج **٢٨ مرّة بدور `user`**. أي أنّ المنصّة زرعت تعليماتِ نظامها داخل
ذاكرتها الحلقية موسومةً بأنها **كلام الطالب** — وهو صنف MINJA بعينه (نجاح موثَّق > 95٪،
وأثرٌ **مؤجَّل**: يُزرع اليوم ويُقرأ بعد أسابيع).

والضرر مزدوج: كاشفُ النيّة يقرأ كلامَ النظام كنيّةٍ للطالب (خرق D-102)، وهندسةُ التعليم
تعود إلى عيني الطالب (خرق D-117).

## ما تفرضه هذه البوّابة

**① مصدرٌ واحد للعلامات.** `SYSTEM_AUTHORED_MARKERS` تُعرَّف في
`shared/memory/authorship.py` وحدها. علامةٌ تُعرَّف في موضعين تتفرّق النسختان، فيصير
مسارٌ يمنع ومسارٌ **يسمح** — وهو نمط ISS-139 نفسه.

**② الحارس موصولٌ عند كل كتابة.** كل تعريفٍ لـ`save_message` يستطيع كتابة دور المستخدم
يجب أن يستدعي `assert_student_authored`. قانونٌ في وحدةٍ لا يناديها أحد ليس مفروضاً —
نفس درس ISS-148 (فارضٌ بلا مرمى).

⛔ **الدَّين المُجمَّد فارغ** ويتقلّص في الاتجاهين (D-189): موضعٌ جديد بلا حارس ⇒ أحمر،
ومدخلُ دَينٍ أُغلق وبقي في الخريطة ⇒ أحمر أيضاً.

⛔ **ولا `except SyntaxError: return []`** (D-208 بند ٦): ملفٌّ يتعذّر تحليله يُبلَّغ
ويُفشِل — بوّابةٌ لا تقرأ ملفاً لا تشهد بنظافته.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: الموطن القانوني الوحيد لقائمة العلامات.
MARKERS_HOME = "shared/memory/authorship.py"
MARKERS_NAME = "SYSTEM_AUTHORED_MARKERS"
GUARD_NAME = "assert_student_authored"

#: الشجرات التي تُفحَص بحثاً عن تعريفٍ مُنافس للقائمة.
_SEARCH_ROOTS: tuple[str, ...] = ("app", "shared", "microservices")

#: تعريفات الكتابة التي يجب أن تحمل الحارس.
_PERSIST_FUNCTIONS: frozenset[str] = frozenset({"save_message"})

#: ملفّات تُعرِّف `save_message` بلا قدرةٍ على كتابة دور المستخدم (تفويضٌ محض).
#:
#: كلٌّ يُصرَّح بسببه (L11) — الاستثناء المنطوق ليس إعفاءً (D-208 بند ٧).
_DELEGATING_ONLY: dict[str, str] = {
    "app/services/boundaries/admin_chat_boundary_service.py": (
        "تفويضٌ محض إلى persistence.save_message المحروسة"
    ),
    "app/services/boundaries/customer_chat_boundary_service.py": (
        "تفويضٌ محض إلى persistence.save_message المحروسة"
    ),
}

#: ⛔ يبقى فارغاً. أيّ إدخالٍ هنا يتطلّب سبباً منطوقاً وقراراً في .memory/decisions.md.
_FROZEN_DEBT: dict[str, str] = {}


class GateReadError(RuntimeError):
    """تعذّرت قراءة/تحليل ملفّ — يُعلَن ولا يُبتلَع."""


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for root in _SEARCH_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        files.extend(sorted(base.rglob("*.py")))
    return files


def _parse(path: Path) -> ast.Module:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError, OSError) as exc:
        raise GateReadError(
            f"{path.relative_to(REPO_ROOT)}: تعذّر التحليل — {type(exc).__name__}: {exc}"
        ) from exc


def _assignment_targets(node: ast.AST) -> list[ast.expr]:
    """أهداف الإسناد لعقدةٍ واحدة (`x = …` أو `x: T = …`)، وإلّا فارغة."""
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    return []


def _assigns_markers(tree: ast.Module) -> bool:
    return any(
        isinstance(target, ast.Name) and target.id == MARKERS_NAME
        for node in ast.walk(tree)
        for target in _assignment_targets(node)
    )


def _called_name(node: ast.Call) -> str | None:
    """اسم المُستدعَى: `f(...)` أو `obj.f(...)`."""
    callee = node.func
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def _calls_guard(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _called_name(node) == GUARD_NAME for node in ast.walk(func) if isinstance(node, ast.Call)
    )


def _marker_definers(files: list[Path]) -> list[str]:
    """كل ملفٍّ يُسنِد إلى `SYSTEM_AUTHORED_MARKERS`، بمسارٍ نسبيّ."""
    return [str(path.relative_to(REPO_ROOT)) for path in files if _assigns_markers(_parse(path))]


def _missing_home(definers: list[str]) -> list[str]:
    if MARKERS_HOME in definers:
        return []
    return [
        f"{MARKERS_NAME} غير مُعرَّفة في موطنها {MARKERS_HOME}.\n"
        f"     المصدر الواحد شرطُ ألّا تتفرّق النسختان (D-013/D-193)."
    ]


def _rival_definitions(definers: list[str]) -> list[str]:
    return [
        f"{rel}: تعريفٌ مُنافس لـ{MARKERS_NAME}.\n"
        f"     الموطن الوحيد {MARKERS_HOME} — نسختان تعنيان مساراً يمنع "
        f"ومساراً يسمح، والطالب لا يعرف أيّهما خزّن كلامه."
        for rel in definers
        if rel != MARKERS_HOME
    ]


def _check_single_source(files: list[Path]) -> list[str]:
    """① العلامات بموطنٍ واحد: موجودةٌ فيه، وغائبةٌ عن كل ما عداه."""
    definers = _marker_definers(files)
    return _missing_home(definers) + _rival_definitions(definers)


def _unguarded_writers(path: Path) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """تعريفات الكتابة في ملفٍّ واحد التي لا تنادي الحارس."""
    return [
        node
        for node in ast.walk(_parse(path))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and node.name in _PERSIST_FUNCTIONS
        and not _calls_guard(node)
    ]


def _stale_debt_entries(seen_debt: set[str]) -> list[str]:
    """الدَّين يتقلّص في الاتجاهين: مدخلٌ لم يعد مخالفاً يجب أن يُحذف."""
    return [
        f"{rel}: مُدرَجٌ في _FROZEN_DEBT ولم يعد مخالفاً.\n"
        f"     احذف السطر — دَينٌ أُغلق وبقي مكتوباً كذبٌ صامت (D-189)."
        for rel in sorted(_FROZEN_DEBT)
        if rel not in seen_debt
    ]


def _guard_message(rel: str, node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    return (
        f"{rel}:{node.lineno}: {node.name}() تكتب رسالةً بلا نداء {GUARD_NAME}().\n"
        f"     كل كتابةٍ بدور المستخدم تمرّ بالحارس — وإلّا عاد ISS-146 صامتاً "
        f"(٢٨ صفّاً من نصّ النظام مُخزَّنةً كأنها كلام الطالب)."
    )


def _check_guard_wired(files: list[Path]) -> list[str]:
    """② كل كاتبِ رسالةٍ ينادي الحارس — والمُصرَّح تفويضاً محضاً وحده يُستثنى."""
    offenders = [
        (str(path.relative_to(REPO_ROOT)), node)
        for path in files
        if str(path.relative_to(REPO_ROOT)) not in _DELEGATING_ONLY
        for node in _unguarded_writers(path)
    ]
    seen_debt = {rel for rel, _ in offenders if rel in _FROZEN_DEBT}
    live = [_guard_message(rel, node) for rel, node in offenders if rel not in _FROZEN_DEBT]
    return live + _stale_debt_entries(seen_debt)


def main() -> int:
    try:
        files = _iter_python_files()
        failures = _check_single_source(files) + _check_guard_wired(files)
    except GateReadError as exc:
        print(f"❌ تسميم الذاكرة (D-229): {exc}")
        print("   بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208 بند ٦).")
        return 1

    if failures:
        print("❌ لا نصَّ نظامٍ بدور الطالب (D-229 · ISS-146) — مخالفات:\n")
        for item in failures:
            print(f"  • {item}")
        return 1

    print(
        f"✅ تسميم الذاكرة (D-229): {MARKERS_NAME} بموطنٍ واحد · "
        f"كل كتابةِ رسالةٍ تمرّ بـ{GUARD_NAME}() · الدَّين المُجمَّد فارغ."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
