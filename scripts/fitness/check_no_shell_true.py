"""بوّابة «لا صدفة في كود التطبيق» — تنفيذ الأوامر بـ`argv` حصراً (M0).

## لماذا هذه البوّابة موجودة

`app/services/agent_tools/` كان ينفّذ أوامر بـ`subprocess.run(..., shell=True)` في ثلاثة
مواضع، وحارسُه **قائمة منع** نصّية بينما `ALLOWED_COMMANDS` مُعرَّفة ولا تُستخدَم. أثبت
التشغيل الحيّ أن الثمانية تمرّ (`;` · `|` · `$( )` · `` ` `` · سطر جديد · أمر خارج القائمة ·
هروب مسار · خروج شبكة) — و`echo $(id -u)` أعاد `0`.

قائمة المنع خاطئة **بنيويّاً**: لا يمكن تعداد كل صياغة خطرة، والقائمة ناقصة دائماً بحكم
طبيعتها. الصواب أن يكون الحقن **غير مُمثَّل** أصلاً: `argv` + `shell=False`.

هذه البوّابة تمنع عودة الصنف. تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.

**قاعدة الدَّين:** خريطة `_FROZEN_DEBT` **تتقلّص فقط** (سابقة D-105 · D-186): مدخل جديد
يُفشِل CI، ومدخلٌ صار نظيفاً يُفشِل CI أيضاً حتى يُحذَف — فلا تتراكم استثناءات ميتة تُخفي
عودة العطب تحت غطاء «مُجمَّد سابقاً».
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: الأشجار المفحوصة — كود التطبيق الذي قد يبلغه مُدخَل غير موثوق.
SCANNED_ROOTS: tuple[str, ...] = ("app", "microservices", "shared")

#: أدلّة ليست مصدر المشروع.
_SKIP_DIRS = frozenset(
    {"node_modules", ".git", "migrations_archive", "site-packages", ".next", "archive"}
)

#: استدعاءات تُنشئ صدفة — ممنوعة في كود التطبيق.
#: `os.system` و`os.popen` صدفة دائماً؛ و`subprocess.*` صدفةٌ متى كان `shell=True`.
_ALWAYS_SHELL = frozenset({"system", "popen"})
_SUBPROCESS_CALLS = frozenset({"run", "call", "check_call", "check_output", "Popen"})
_ASYNCIO_SHELL = frozenset({"create_subprocess_shell"})

#: **دَين مُجمَّد — يتقلّص فقط.** لكل مدخل سببه المكتوب.
_FROZEN_DEBT: dict[str, str] = {}


def _attr_chain(node: ast.AST) -> str:
    """يبني `a.b.c` من شجرة السمات — لتمييز `os.system` عن `system` المحلّية."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _shell_kwarg_is_true(call: ast.Call) -> bool:
    """هل مُرِّر `shell=True` حرفيّاً؟ (`shell=False` أو غيابه سليم)."""
    for keyword in call.keywords:
        if keyword.arg == "shell":
            return isinstance(keyword.value, ast.Constant) and keyword.value.value is True
    return False


def _scan(path: Path) -> list[tuple[int, str]]:
    """يُرجع (السطر، الوصف) لكل استدعاء يُنشئ صدفة في الملف."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []

    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        chain = _attr_chain(node.func)
        tail = chain.rsplit(".", 1)[-1]

        if chain in {"os.system", "os.popen"} or (
            tail in _ALWAYS_SHELL and chain.startswith("os.")
        ):
            findings.append((node.lineno, f"{chain}() always spawns a shell"))
        elif tail in _ASYNCIO_SHELL:
            findings.append((node.lineno, f"{chain}() spawns a shell"))
        elif tail in _SUBPROCESS_CALLS and _shell_kwarg_is_true(node):
            findings.append((node.lineno, f"{chain}(..., shell=True)"))
    return findings


def main() -> int:
    """يُرجع 0 حين لا صدفة خارج الدَّين المُجمَّد، و1 عند أي خرق أو مدخل بائد."""
    failures = 0
    seen_debt: set[str] = set()

    for root_name in SCANNED_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if any(part.startswith(".venv") or part in _SKIP_DIRS for part in path.parts):
                continue
            rel = str(path.relative_to(REPO_ROOT))
            findings = _scan(path)
            if rel in _FROZEN_DEBT:
                if findings:
                    seen_debt.add(rel)
                continue
            for lineno, what in findings:
                failures += 1
                print(f"❌ Shell execution in application code: {rel}:{lineno} — {what}")
                print("   Fix: build an argv list and call")
                print("        app.services.agent_tools.sandbox.run_sandboxed(argv, cwd=...)")

    # الدَّين يتقلّص فقط: مدخل لم يعد فيه خرق يجب أن يُحذَف من الخريطة.
    for rel, reason in sorted(_FROZEN_DEBT.items()):
        if not (REPO_ROOT / rel).is_file():
            failures += 1
            print(f"❌ Stale frozen-debt entry (file gone): {rel} — {reason}")
        elif rel not in seen_debt:
            failures += 1
            print(f"❌ Stale frozen-debt entry (already clean): {rel}")
            print("   Fix: delete this line from _FROZEN_DEBT — the debt shrank, record it.")

    if failures:
        print(f"\n❌ check_no_shell_true: {failures} violation(s).")
        return 1
    print("✅ check_no_shell_true: application code executes argv only, never a shell.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
