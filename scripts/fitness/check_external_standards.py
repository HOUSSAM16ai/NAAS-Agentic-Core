#!/usr/bin/env python3
"""التبنّي بقرارٍ مكتوب لا بإعجاب (D-271 L12).

**لماذا هذه البوّابة موجودة:**

ISS-193 فُتِحت حرفياً على «تبنّي harness خارجي بلا قرارٍ مكتوب». والنمط يتكرّر بسهولة:
قائمةٌ من عشرة مستودعاتٍ لامعة تصل، فتُقرأ **إعجاباً** بدل **عقد**، فيدخل منها ما يدخل
بلا أحدٍ يعرف ما استُعير ولا ما رُفض ولا من يحرسه.

فكلّ مصدرٍ خارجي هنا صفٌّ يحمل:

* **وجوداً مُتحقَّقاً منه** (``verified_on`` + طريقة التحقّق) — لا نقلاً عن منشور.
  وما لم يُقرأ يُقال إنّه لم يُقرأ: ما لا يُقرأ لا يُشهَد عليه (D-208 §6).
* **ما اُستُعير** و**ما رُفض ولماذا** — ومعرفةُ لماذا رُفض الأحدث تشتري مصداقيةً أكثر
  من استعماله (المحرَّم الثاني · D-226).
* **فارضاً مُسمّى موجوداً**، أو إعلانَ غيابه بسببٍ منطوق (D-206 L11).
* **حالةً من سُلَّم §6.6 وحده** — ⛔ لا سُلَّم ثانٍ (D-209).
* **شرط ترقيةٍ** لكلّ ما ليس ACTIVE — الطموح يُصنَّف ولا يُكتَم.

⛔ **والفحص في الاتجاهين:** صفٌّ مُصنَّف ``ABSENT``/``SEAM`` وله كودٌ على القرص ⇒ CI
أحمر. كودٌ حيّ بلا حارسٍ ولا اختبار أسوأ من الغياب المُعلَن (قاعدة D-210، ونفس بند
D-269 L7).

المصدر القانوني: ``docs/governance/EXTERNAL_STANDARDS_REGISTRY.json``.
تُشغَّل ضمن وظيفة ``guardrails``. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REGISTRY = REPO_ROOT / "docs" / "governance" / "EXTERNAL_STANDARDS_REGISTRY.json"

#: مواطن الفوارض التي يجوز للصفّ أن يسمّيها.
ENFORCER_HOMES = ("scripts/fitness", "tools/ci", ".github/scripts")

#: سُلَّم §6.6 وحده — والتوسعة قرارٌ لا سهو.
STATUSES = ("ACTIVE", "PARTIAL", "SEAM", "PLANNED", "ABSENT")

#: حالاتٌ تعني «لا كود» — ويُفحَص ذلك بنيوياً لا بالثقة.
CODELESS = ("ABSENT", "SEAM")

REQUIRED_FIELDS = (
    "id",
    "repo",
    "verified_on",
    "verification_method",
    "read_ar",
    "adopted_ar",
    "rejected_ar",
    "status",
)

_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _known_enforcers() -> set[str]:
    return {
        path.name
        for home in ENFORCER_HOMES
        if (REPO_ROOT / home).is_dir()
        for path in (REPO_ROOT / home).glob("*.py")
    }


def _check_required_fields(label: str, row: dict) -> None:
    for field in REQUIRED_FIELDS:
        if not str(row.get(field, "")).strip():
            _fail(f"{label}: الحقل `{field}` فارغ أو مفقود")


def _check_row_enforcers(label: str, row: dict, enforcers: set[str]) -> None:
    named = list(row.get("enforcers", []))
    for enforcer in named:
        if enforcer not in enforcers:
            _fail(f"{label}: يسمّي فارضاً غير موجود `{enforcer}` — خريطةٌ تكذب (ISS-149)")
    if not named and not str(row.get("no_enforcer_reason_ar", "")).strip():
        _fail(f"{label}: بلا فارضٍ وبلا `no_enforcer_reason_ar` — الغياب يُعلَن (D-206 L11)")


def _check_row_status(label: str, row: dict, status: str) -> None:
    if status not in STATUSES:
        _fail(f"{label}: حالةٌ خارج سُلَّم §6.6: {status!r} — ⛔ لا سُلَّم ثانٍ (D-209)")
    if status != "ACTIVE" and not str(row.get("upgrade_condition_ar", "")).strip():
        _fail(f"{label}: حالته `{status}` بلا شرط ترقية — الطموح يُصنَّف ولا يُكتَم (D-209)")


def _check_row_code_paths(label: str, row: dict, status: str) -> None:
    """⛔ الفحص في الاتجاهين: مُصنَّفٌ بلا كودٍ وله كود · وACTIVE يشير إلى العدم."""
    paths = list(row.get("code_paths", []))
    if status in CODELESS and (existing := [p for p in paths if (REPO_ROOT / p).exists()]):
        _fail(
            f"{label}: مُصنَّف `{status}` (أي بلا كود) وله كودٌ على القرص: {existing} — "
            "كودٌ حيّ بلا حارسٍ أسوأ من الغياب المُعلَن"
        )
    if status == "ACTIVE" and (missing := [p for p in paths if not (REPO_ROOT / p).exists()]):
        _fail(f"{label}: مُصنَّف ACTIVE ويشير إلى مساراتٍ غير موجودة: {missing}")


def _check_row(row: dict, enforcers: set[str]) -> None:
    label = str(row.get("id", "<بلا مُعرِّف>"))
    status = str(row.get("status", ""))
    _check_required_fields(label, row)
    _check_row_status(label, row, status)
    _check_row_enforcers(label, row, enforcers)
    _check_row_code_paths(label, row, status)


def main() -> int:
    if not REGISTRY.is_file():
        print(f"❌ سجلّ المعايير الخارجية مفقود: {REGISTRY.relative_to(REPO_ROOT)}")
        return 1
    try:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"❌ `EXTERNAL_STANDARDS_REGISTRY.json` ليس JSON صالحاً: {exc}")
        return 1

    sources = registry.get("sources", [])
    if not sources:
        print("❌ `sources` فارغة — سجلٌّ بلا صفوفٍ يُقرأ حمايةً")
        return 1

    identifiers = [str(row.get("id", "")) for row in sources]
    if len(set(identifiers)) != len(identifiers):
        _fail("مُعرِّفات مكرّرة في السجلّ — كل مصدرٍ صفٌّ واحد")

    enforcers = _known_enforcers()
    for row in sources:
        _check_row(row, enforcers)

    if _FAILURES:
        print(f"\n❌ المعايير الخارجية (D-271 L12): {len(_FAILURES)} انتهاكاً")
        return 1
    active = sum(1 for row in sources if row.get("status") == "ACTIVE")
    print(
        f"\n✅ المعايير الخارجية (D-271 L12): {len(sources)} مصدراً مُسجَّلاً "
        f"({active} ACTIVE) — كلٌّ بما اُستُعير وما رُفض وفارضِه أو إعلانِ غيابه."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
