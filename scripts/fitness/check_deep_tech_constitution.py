#!/usr/bin/env python3
"""بوّابة دستور التقنية العميقة والعملة الصعبة (D-273).

تحرس القواعد الدستورية التالية:
- وجود وثيقة القانون [`docs/DEEP_TECH_CONSTITUTION.md`](docs/DEEP_TECH_CONSTITUTION.md).
- وجود وثيقة الحالة [`.memory/deep_tech_constitution_truth.md`](.memory/deep_tech_constitution_truth.md).
- صدق الحالة: لا سطرٌ يعلن خطًّا `ACTIVE` دون دليلٍ مذكورٍ في وثيقة الحالة.
- تسجيل الدستور في [`docs/governance/CONSTITUTION_REGISTRY.json`](docs/governance/CONSTITUTION_REGISTRY.json).

النمط مطابقٌ للفوارض الأخرى في `scripts/fitness/` (D-266: بوّابةٌ بلا تنفيذٍ
تُقرأ حمايةً وهي ليست حماية).
"""

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LAW_DOC = REPO_ROOT / "docs" / "DEEP_TECH_CONSTITUTION.md"
TRUTH_DOC = REPO_ROOT / ".memory" / "deep_tech_constitution_truth.md"
REGISTRY = REPO_ROOT / "docs" / "governance" / "CONSTITUTION_REGISTRY.json"

FAILED = False


def fail(msg: str) -> None:
    global FAILED
    FAILED = True
    print(f"❌ D-273: {msg}", file=sys.stderr)


def check_files_exist() -> None:
    if not LAW_DOC.exists():
        fail(f"وثيقة القانون غائبة: {LAW_DOC.relative_to(REPO_ROOT)}")
    if not TRUTH_DOC.exists():
        fail(f"وثيقة الحالة غائبة: {TRUTH_DOC.relative_to(REPO_ROOT)}")


def check_active_lines_have_evidence() -> None:
    """لا سطر `ACTIVE` في وثيقة الحالة دون دليلٍ في نفس السطر أو الأسطر المجاورة.

    القاعدة: إعلانٌ بلا دليلٍ كذبةٌ منظمة (D-267 · وثيقةُ الحالة صادقةٌ).
    """
    if not TRUTH_DOC.exists():
        return
    text = TRUTH_DOC.read_text(encoding="utf-8")
    active_re = re.compile(r"^\s*\|\s*\d+\s*\|.+\|\s*`ACTIVE`", re.MULTILINE)
    for m in active_re.finditer(text):
        start = m.start()
        # ابحث عن كلمة "دليل" أو مسار ملف أو رابط في السطر نفسه أو ما يليه
        window = text[start : text.find("\n", start) + 300]
        if not re.search(r"دليل|/|`", window):
            fail(
                "سطرٌ يعلن خطًّا ACTIVE دون دليلٍ في وثيقة الحالة: "
                + m.group(0).strip()[:120]
            )


def check_registry_entry() -> None:
    """صف D-273 يجب أن يسجَّل في السجل الدستوري (D-266) وأن تشير مساراته إلى
    ملفاتٍ موجودةٍ فعلاً — خريطةٌ تكذب أسوأ من غياب الخريطة (ISS-149)."""
    if not REGISTRY.exists():
        fail(f"السجل الدستوري غائب: {REGISTRY.relative_to(REPO_ROOT)}")
        return
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    found = [c for c in registry.get("constitutions", []) if c.get("id") == "D-273"]
    if not found:
        fail("صف D-273 غير مسجَّل في CONSTITUTION_REGISTRY.json")
        return
    entry = found[0]
    for doc_path in entry.get("law_docs", []) + entry.get("status_docs", []):
        if not (REPO_ROOT / doc_path).exists():
            fail(f"مسارٌ في السجل الدستوري لا وجود له: {doc_path}")


def main() -> int:
    check_files_exist()
    check_active_lines_have_evidence()
    check_registry_entry()
    if FAILED:
        print("check_deep_tech_constitution: FAIL", file=sys.stderr)
        return 1
    print("check_deep_tech_constitution: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
