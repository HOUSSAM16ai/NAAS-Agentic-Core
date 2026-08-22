"""الحدّ المعماري لمسار المنتج — D-267 L1/L2/L5 + قفل D-187.

خريطة الاعتماد في `docs/architecture/NAAS_VERIFICATION_LAYER.md §3.1` كانت **نثراً
بلا فارض**. وهذا الملفّ يجعلها عقداً مفروضاً بـAST:

1. `naas_verifier/**` لا يستورد `app` ولا `microservices` — والقلب يضيف
   `shared.curriculum`/`shared.notation`: قلبٌ يعرف مجالاً بعينه ميزةٌ متنكّرة لا منتج.
2. `app/**` · `microservices/**` لا يستوردان `naas_verifier` ولا ذخيرته — جدار الحجب
   (D-113 · D-196): الذخيرة لا تصل مسار الطالب أبداً.
3. **قفل D-187 بنيويّاً**: لا `subprocess` ولا عميل شبكةٍ داخل `naas_verifier` — توليدُ
   رقعةٍ بنموذجٍ ثمّ تنفيذها هو حمولة `M1→M4` لا التفافٌ عليها.

⛔ **البوّابة لا تشهد بما لم تقرأ (D-208):** ملفٌّ يتعذّر تحليله يُبلَّغ **انتهاكاً**،
ولا يُبتلَع بـ`except SyntaxError: return []`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRODUCT_ROOT = REPO_ROOT / "naas_verifier"
CONSUMER_ROOTS = ("app", "microservices")

#: إصدار المشروع (`PYTHON_VERSION` في `.github/workflows/ci.yml`). المستودع يستعمل
#: بناء PEP 695 (`type X = ...`)، فمُفسِّرٌ أقدم يعجز عن تحليل عشرات الملفّات السليمة.
MIN_PYTHON = (3, 12)

#: ممنوعٌ على كامل حزمة المنتج.
FORBIDDEN_EVERYWHERE = ("app", "microservices")
#: ممنوعٌ على القلب وحده — المجال يدخل من `adapters/` بياناتٍ لا استيراداً.
FORBIDDEN_IN_CORE = ("shared.curriculum", "shared.notation", "shared")
#: قفل D-187 — القدرة ≠ الأمان.
FORBIDDEN_CAPABILITY = ("subprocess", "httpx", "requests", "aiohttp", "openai", "socket")

_FAILURES: list[str] = []


def _fail(message: str) -> None:
    _FAILURES.append(message)
    print(f"❌ {message}")


def _imported_modules(path: Path) -> set[str]:
    """أسماء الوحدات المستورَدة — بـAST لا بـgrep."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        # ⛔ لا ابتلاع: بوّابةٌ تعجز عن القراءة تُبلِّغ ولا تُبرّئ.
        _fail(f"{path.relative_to(REPO_ROOT)}: unparseable, cannot certify — {exc}")
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
    return names


def _matches(imported: str, forbidden: str) -> bool:
    return imported == forbidden or imported.startswith(f"{forbidden}.")


def _check_product_tree() -> None:
    files = sorted(PRODUCT_ROOT.rglob("*.py"))
    if not files:
        _fail("naas_verifier/ has no python modules — a gate that reads nothing certifies nothing")
        return
    for path in files:
        rel = path.relative_to(REPO_ROOT)
        in_core = "core" in path.relative_to(PRODUCT_ROOT).parts
        imported = _imported_modules(path)
        for name in sorted(imported):
            for forbidden in FORBIDDEN_EVERYWHERE:
                if _matches(name, forbidden):
                    _fail(f"{rel}: imports `{name}` — the product path is separate by design (L1/L2)")
            for forbidden in FORBIDDEN_CAPABILITY:
                if _matches(name, forbidden):
                    _fail(
                        f"{rel}: imports `{name}` — D-187 lock: no sandbox executor or network "
                        "client inside the verifier before M1→M4"
                    )
            if in_core:
                for forbidden in FORBIDDEN_IN_CORE:
                    if _matches(name, forbidden):
                        _fail(
                            f"{rel}: core imports `{name}` — a core that knows a domain is a "
                            "feature in disguise, not a product (L2)"
                        )
    print(f"✅ product tree clean: {len(files)} module(s) inside the architectural boundary")


def _check_no_reverse_import() -> None:
    """⛔ الاتجاه المعاكس: مسار الطالب لا يرى الذخيرة أبداً (D-113 · L5)."""
    offenders: list[str] = []
    scanned = 0
    for root_name in CONSUMER_ROOTS:
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            scanned += 1
            if any(
                _matches(name, "naas_verifier") for name in _imported_modules(path)
            ):
                offenders.append(str(path.relative_to(REPO_ROOT)))
    for offender in offenders:
        _fail(
            f"{offender}: imports `naas_verifier` — the exploit corpus must never reach "
            "the student path (D-113 · D-196)"
        )
    if not offenders:
        print(f"✅ no reverse import: {scanned} module(s) in app/ and microservices/ stay clear")


def main() -> int:
    if sys.version_info < MIN_PYTHON:
        # ⛔ لا تُبرِّئ ولا تُدين: مُفسِّرٌ أقدم من إصدار المشروع يعجز عن تحليل ملفّاتٍ
        # سليمة، فيُنتج انتهاكاتٍ كاذبة. والصمت هنا أسوأ — فترفض البوّابة الشهادة
        # صراحةً (D-208: بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف).
        running = ".".join(str(part) for part in sys.version_info[:3])
        required = ".".join(str(part) for part in MIN_PYTHON)
        print(
            f"❌ refusing to certify: this gate needs Python >= {required}, running {running}. "
            "The repository uses PEP 695 syntax, so an older interpreter reports valid "
            "modules as unparseable."
        )
        return 1
    _check_product_tree()
    _check_no_reverse_import()
    if _FAILURES:
        print(f"\n❌ naas-verifier-boundary: {len(_FAILURES)} violation(s)")
        return 1
    print("\n✅ naas-verifier-boundary: the dependency map is a contract, not prose.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
