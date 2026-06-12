#!/usr/bin/env python3
"""بوابة نظافة الاختبارات — D-105 (ISS-113).

تمنع فئة البق التي أسقطت CI في ISS-113: تسميم الحالة العالمية للجلسة من ملفات
الاختبارات. القاعدة الذهبية:

1. **ممنوع** أي كتابة في ``sys.modules`` على مستوى الوحدة (module-level) في أي ملف
   يجمعه pytest — الكتابة تحدث وقت الجمع وتسمّم كل ما يُستورد بعدها في الجلسة
   (هذا بالضبط ما جعل ``mock.Document`` يتسرب إلى ``graph/search.py`` فأسقط
   ``test_d103_injected_context`` على CI).
2. **ممنوع** الكتابة العارية في ``sys.modules`` داخل دوال الاختبار بدون سياج
   (``patch.dict``/``monkeypatch``): ملف يحوي كتابة مباشرة ولا يستخدم أي آلية
   استرجاع يفشل البوابة.
3. **ممنوع** ``os.environ[...] = ...`` أو ``os.environ.setdefault`` على مستوى
   الوحدة في ملفات الاختبار لقيم **متغايرة بين الملفات** — يسمح به فقط في
   conftest الجذري (الخط القانوني الموحَّد) وفي allowlist موثَّقة قيد التصفية.

الاستخدام::

    python scripts/fitness/check_test_hygiene.py            # فحص
    python scripts/fitness/check_test_hygiene.py --verbose  # تفاصيل

Exit codes: 0 = نظيف | 1 = انتهاكات.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# المجالات التي يجمعها pytest (مرآة pytest.ini:testpaths — أي تغيير هناك يُحدَّث هنا)
COLLECTED_ROOTS = ("tests", "scripts/ci", "microservices")

# ملفات يُسمح لها بكتابة os.environ على مستوى الوحدة (ديون موثَّقة قيد التصفية —
# القيم متطابقة فعلياً مع conftest الجذري أو حميدة بـ setdefault؛ لا تُضِف ملفاً
# جديداً هنا: الاتجاه الوحيد المسموح هو التقليص).
_ENV_WRITE_ALLOWLIST = frozenset(
    {
        "tests/conftest.py",  # الخط القانوني الموحَّد (canonical baseline)
        "tests/integration/test_microservices_integration.py",
        "tests/microservices/test_mission_routing_fix.py",
        "tests/microservices/test_orchestrator_service.py",
        "tests/microservices/conversation_service/test_step12_conversation_service.py",
        "tests/microservices/test_microservices.py",
        "tests/microservices/test_health_security_fix.py",
        "tests/microservices/test_api_gateway_routing.py",
        "tests/test_api_first_platform.py",
        "tests/services/test_iss098_keepalive.py",
        "tests/services/test_ws_send_concurrency_lock.py",
        "tests/services/test_iss100_ws_connect_no_db.py",
        "tests/services/test_auth_token_lifetime.py",
        "tests/microservices/test_orchestrator_admin_tool_security.py",
        "tests/test_caching_standalone.py",
        "tests/unit/test_db_factory_guardrails.py",
        "tests/unit/core/test_settings.py",
        "microservices/observability_service/tests/test_observability_api.py",
    }
)


def _iter_collected_test_files() -> list[Path]:
    """يُرجع كل ملفات test_*.py التي يجمعها pytest وفق testpaths."""
    files: list[Path] = []
    for root in COLLECTED_ROOTS:
        base = REPO_ROOT / root
        if base.exists():
            files.extend(sorted(base.rglob("test_*.py")))
            files.extend(sorted(base.rglob("conftest.py")))
    return files


def _is_sys_modules_write(node: ast.AST) -> bool:
    """يكشف ``sys.modules[...] = ...`` أو ``sys.modules.setdefault/update/pop`` ككتابة."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "modules"
                and isinstance(target.value.value, ast.Name)
                and target.value.value.id == "sys"
            ):
                return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        func = node.value.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in ("setdefault", "update")
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "modules"
            and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "sys"
        ):
            return True
    return False


def _is_environ_write(node: ast.AST) -> bool:
    """يكشف ``os.environ[...] = ...`` أو ``os.environ.setdefault(...)``."""
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if (
                isinstance(target, ast.Subscript)
                and isinstance(target.value, ast.Attribute)
                and target.value.attr == "environ"
            ):
                return True
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        func = node.value.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "setdefault"
            and isinstance(func.value, ast.Attribute)
            and func.value.attr == "environ"
        ):
            return True
    return False


def _module_level_statements(tree: ast.Module):
    """يمشي العبارات على مستوى الوحدة فقط، مع علم «conditional» لما داخل if/try.

    العبارة المشروطة (داخل ``if``/``except``) قد تكون polyfill مشروعاً؛ العبارة
    غير المشروطة على مستوى الوحدة تسميم مؤكد.
    """
    stack: list[tuple[ast.AST, bool]] = [(node, False) for node in tree.body]
    while stack:
        node, conditional = stack.pop()
        yield node, conditional
        if isinstance(node, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
            inner_conditional = conditional or isinstance(node, (ast.If, ast.Try))
            for attr in ("body", "orelse", "finalbody", "handlers"):
                for child in getattr(node, attr, []) or []:
                    if isinstance(child, ast.ExceptHandler):
                        stack.extend((grand, True) for grand in child.body)
                    else:
                        stack.append((child, inner_conditional))


def _mentions_mock(src: str, node: ast.AST) -> bool:
    """هل العبارة تُسنِد قيمة Mock؟ (Mock يُظلِّل موديولات حقيقية = فئة ISS-113)."""
    segment = ast.get_source_segment(src, node) or ""
    return "Mock" in segment


def check_file(path: Path) -> list[str]:
    """يفحص ملفاً واحداً ويُرجع قائمة الانتهاكات.

    العقد:
    - كتابة sys.modules بقيمة Mock ⇒ انتهاك دائماً (تُظلِّل موديولات حقيقية).
    - كتابة sys.modules غير مشروطة على مستوى الوحدة ⇒ انتهاك (تسميم وقت الجمع).
    - كتابة مشروطة بقيمة ``types.ModuleType`` (polyfill لغياب التبعية) ⇒ مسموحة.
    - كتابة داخل دالة بلا patch.dict/monkeypatch في الملف وبقيمة Mock ⇒ انتهاك.
    - كتابة os.environ على مستوى الوحدة خارج allowlist ⇒ انتهاك.
    """
    rel = str(path.relative_to(REPO_ROOT))
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as exc:  # pragma: no cover — ملف مكسور يفشل في مكان آخر
        return [f"{rel}: SyntaxError: {exc}"]

    violations: list[str] = []
    has_patch_dict = "patch.dict" in src or "monkeypatch" in src

    # 1+3) كتابات مستوى الوحدة
    for node, conditional in _module_level_statements(tree):
        if _is_sys_modules_write(node):
            if _mentions_mock(src, node):
                violations.append(
                    f"{rel}:{node.lineno}: module-level sys.modules write بقيمة Mock — "
                    "يُظلِّل موديولاً حقيقياً ويسمّم الجلسة (فئة ISS-113). "
                    "استخدم patch.dict داخل fixture/اختبار."
                )
            elif not conditional:
                violations.append(
                    f"{rel}:{node.lineno}: module-level sys.modules write غير مشروط — "
                    "يسمّم جلسة pytest وقت الجمع (فئة ISS-113). polyfill مشروع يكون "
                    "داخل if/except لغياب التبعية وبقيمة ModuleType."
                )
        if _is_environ_write(node) and rel not in _ENV_WRITE_ALLOWLIST:
            violations.append(
                f"{rel}:{node.lineno}: module-level os.environ write خارج الـ allowlist — "
                "يكسر عزل الجلسة. استخدم monkeypatch أو conftest الجذري."
            )

    # 2) كتابات sys.modules داخل الدوال: Mock بلا آلية استرجاع ⇒ تسريب مضمون
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for stmt in ast.walk(node):
                if _is_sys_modules_write(stmt) and _mentions_mock(src, stmt) and not has_patch_dict:
                    violations.append(
                        f"{rel}:{stmt.lineno}: bare sys.modules write بقيمة Mock داخل "
                        f"{node.name}() بلا patch.dict/monkeypatch في الملف — تسريب مضمون."
                    )
    return violations


def main() -> int:
    verbose = "--verbose" in sys.argv
    files = _iter_collected_test_files()
    all_violations: list[str] = []
    for path in files:
        all_violations.extend(check_file(path))

    print(f"=== Test Hygiene Gate (D-105 / ISS-113) — فحص {len(files)} ملفاً ===")
    if all_violations:
        print(f"\n❌ {len(all_violations)} انتهاكاً:\n")
        for v in all_violations:
            print(f"  {v}")
        return 1
    if verbose:
        for path in files:
            print(f"  ✓ {path.relative_to(REPO_ROOT)}")
    print("✅ نظيف — لا تسميم sys.modules ولا كتابات بيئة خارج العقد.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
