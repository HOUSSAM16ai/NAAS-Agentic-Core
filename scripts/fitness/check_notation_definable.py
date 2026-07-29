"""بوّابة «لا رمز يتيم» — النظام يعرّف كل رمز يطبعه (D-185).

## القانون الذي تفرضه
طالب حقيقي سأل «ماذا نقصد بحرف C» عن رمزٍ **طبعه المعلّم نفسه**، فلم يجد النظام له تعريفاً
فأعاد عليه الاشتقاق (ISS-138). الدرس: أي رمز يبثّه العقل على الطالب ولا يستطيع تعريفه هو
**دَين معرفي** سيتحوّل إلى كارثة عند أول طالب يسأل عنه.

فتمنع هذه البوّابة الصنف كلّه: تمسح **المصدر المُركَّب** لعقل الاحتمالات (عبر مانيفست
`BRAIN_SOURCE_FILES` — لا قائمة ملفات مُصلَّبة، احتراماً لقاعدة D-163→D-172)، وتستخرج كل
رمز رياضي يظهر فيه، وتُلزِم أن يكون لكلٍّ إدخالٌ في `shared/notation/registry.py`.

## ما تفحصه أيضاً
سلامة السجلّ نفسه: كل إدخال له عنوان وتعريف ومثال، و**المثال محايد** — ممنوع أن يحوي أرقام
تمرين البكالوريا الجاري (14 · 165 · 56)، وإلّا صار «التعريف» باباً خلفيّاً لتسريب الحل
ونقض العقد السقراطي (D-113 → D-155).

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from shared.notation import NOTATION_REGISTRY, define

#: نمط اكتشاف الرمز في المصدر → الرمز القانوني الذي يجب أن يكون مُعرَّفاً.
#: أي بنية ترميز جديدة يبثّها العقل تُضاف هنا **وفي السجلّ** معاً.
_SYMBOL_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"C_\{?\w+\}?\^\{?\w+\}?", "C(n,k)"),
    (r"\bC\(\d+\s*,\s*\d+\)", "C(n,k)"),
    (r"A_\{?\w+\}?\^\{?\w+\}?", "A(n,k)"),
    (r"P_\{?[A-Z]\}?\s*\(", "P_A(B)"),
    (r"\bP\([A-Z]\)", "P(A)"),
    (r"\bE\(X\)", "E(X)"),
    (r"\\Omega|Ω", "Ω"),
    (r"\\cap|∩", "∩"),
    (r"\\cup|∪", "∪"),
    (r"\\bar\{[A-Z]\}|Ā", "Ā"),
    (r"\b\d+!|\bn!", "n!"),
)

#: أرقام تمرين BAC 2024 التي يجب ألّا تظهر أبداً في أمثلة السجلّ (حارس التسريب).
_LEAK_NUMBERS: tuple[str, ...] = ("14", "165", "56")


def _composed_brain_source() -> str:
    """يقرأ المصدر المُركَّب لعقل الاحتمالات عبر المانيفست (لا قائمة ملفات مُصلَّبة)."""
    from app.services.skills.probability_brain.brain_sources import BRAIN_SOURCE_FILES

    parts: list[str] = []
    for relative in BRAIN_SOURCE_FILES:
        path = REPO_ROOT / relative
        if path.is_file():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _check_emitted_symbols() -> list[str]:
    """كل رمز يظهر في مصدر العقل يجب أن يكون قابلاً للتعريف."""
    source = _composed_brain_source()
    failures: list[str] = []
    for pattern, symbol in _SYMBOL_PATTERNS:
        if not re.search(pattern, source):
            continue
        if define(symbol) is None:
            failures.append(
                f"❌ Orphan notation: the brain emits {symbol!r} (pattern {pattern!r}) "
                "but shared/notation/registry.py cannot define it."
            )
    return failures


def _check_registry_health() -> list[str]:
    """سلامة السجلّ: حقول مكتملة + أمثلة محايدة (لا تسريب لأرقام التمرين)."""
    failures: list[str] = []
    for entry in NOTATION_REGISTRY:
        for field in ("title", "definition", "example"):
            if not getattr(entry, field, "").strip():
                failures.append(f"❌ Notation entry {entry.symbol!r} has an empty {field!r}.")
        if not entry.markers:
            failures.append(f"❌ Notation entry {entry.symbol!r} has no markers — unreachable.")
        leaked = [n for n in _LEAK_NUMBERS if n in entry.example]
        if leaked:
            failures.append(
                f"❌ Notation example for {entry.symbol!r} leaks exercise numbers {leaked} — "
                "examples must be neutral (D-113: a definition is not an answer)."
            )
    return failures


def main() -> int:
    """يُرجع 0 حين يكون كل رمز مبثوث قابلاً للتعريف والسجلّ سليماً."""
    failures = _check_emitted_symbols() + _check_registry_health()
    if failures:
        for line in failures:
            print(line)
        print(
            "\n   Fix: add the missing symbol to shared/notation/registry.py, then run\n"
            "   cp shared/notation/registry.py "
            "microservices/notation_service/src/notation/registry.py"
        )
        return 1
    print(
        f"✅ No orphan notation: {len(NOTATION_REGISTRY)} symbols defined, "
        "every symbol the brain emits is definable, all examples neutral."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
