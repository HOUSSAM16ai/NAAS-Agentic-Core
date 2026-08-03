#!/usr/bin/env python3
"""يمنع نموّ `typing.Any` — ratchet ثنائي الاتجاه (D-192 · roadmap §6.5.د D1).

**لماذا هذه البوّابة موجودة:**

الدستور يعلن كتابةً صارمة، والواقع كان **193** استعمالاً لـ`Any` في `app/` — منها
**22** على **حدود التكامل** (`app/integration/`)، وهي آخر مكان يُقبل فيه فقدان أمان
العقد لأنها حيث تدخل بيانات خدمةٍ أخرى إلى النواة. والمفارقة أن الطبقة تحتها كانت
أدقّ: `research_client` يُرجِع `dict[str, object]` بينما البوّابة تُوسّعها إلى
`dict[str, Any]` — أي أن الحدّ كان يُلغي ضيقاً موجوداً.

سُدَّت حدود التكامل في هذه الجولة (22 → **0**). لكن «أصلحناها مرّة» لا يمنع عودتها،
وحملة تحويلٍ شاملة لـ171 الباقية تُخاطر بالمسار الحيّ. الحلّ هو نمط D-105/D-187/D-189
نفسه: **رقمٌ مُجمَّد لكل ملفّ يتقلّص فقط**.

**ثنائي الاتجاه عمداً:** `Any` جديدة تُفشِل البوّابة، **ودَينٌ أُغلق ولم يُحدَّث رقمه
يُفشِلها أيضاً** — وإلا تقادمت الخريطة بصمت (وهو بالضبط عطب D-188 في التوثيق).

استعمالُ `Any` المشروع نادر (توقيعات polymorphic في `BaseSkill.run`)، وهو مُجمَّد
برقمه لا مُستثنى بالاسم: الاستثناء المفتوح يصير باباً.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
DEBT_FILE = Path(__file__).with_name("no_new_any_debt.json")

#: الأشجار المحروسة. `shared/` مشمولة لأنها **نظيفة أصلاً** (صفر `Any`) — فالحراسة
#: هنا تمنع أول تلوّث لا تُقلّص دَيناً.
SCANNED_ROOTS = ("app", "shared")

#: حدّ صفري صارم: لا `Any` إطلاقاً في هذه الأشجار الفرعية — حدود التكامل سُدَّت.
ZERO_TOLERANCE_PREFIXES = ("app/integration/",)


def _count_any(path: Path) -> int:
    """يعدّ استعمالات `Any` **كنوع** — بـAST لا نصّاً.

    العدّ النصّي يحسب كلمة `Any` في تعليقٍ عربي أو docstring يشرح القاعدة نفسها،
    فتُعاقَب الوثيقة التي تحرس القاعدة. الأنواع وحدها تُعَدّ.
    """
    # ISS-149 (F1): يرفع. هنا وقع الدليل الحيّ: على 3.11 أُبلِغ أن `base.py` صار
    # `0× Any` بينما الدَّين 12 — لأن الملفّ لم يُحلَّل أصلاً، لا لأنه نُظِّف.
    tree = parse_source(path)
    return sum(
        1
        for node in ast.walk(tree)
        if (isinstance(node, ast.Name) and node.id == "Any")
        or (isinstance(node, ast.Attribute) and node.attr == "Any")
    )


def _scan() -> dict[str, int]:
    counts: dict[str, int] = {}
    for root in SCANNED_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            found = _count_any(path)
            if found:
                counts[path.relative_to(REPO_ROOT).as_posix()] = found
    return counts


def main() -> int:
    current = _scan()

    if "--update" in sys.argv:
        DEBT_FILE.write_text(
            json.dumps(dict(sorted(current.items())), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"✅ baseline written: {len(current)} files, {sum(current.values())} Any")
        return 0

    if not DEBT_FILE.is_file():
        print(f"❌ ملفّ الدَّين مفقود: {DEBT_FILE.name}. شغّل `--update` مرّة لتثبيت الأساس.")
        return 1
    frozen: dict[str, int] = json.loads(DEBT_FILE.read_text(encoding="utf-8"))

    errors: list[str] = []

    for rel, found in sorted(current.items()):
        if any(rel.startswith(prefix) for prefix in ZERO_TOLERANCE_PREFIXES):
            errors.append(
                f"❌ {rel}: {found}× `Any` على **حدّ تكامل** — الحدّ صفريّ هنا (D-192 · D1).\n"
                f"   استعمل نموذجاً من `app/integration/models.py` أو `object`."
            )
            continue
        allowed = frozen.get(rel, 0)
        if found > allowed:
            errors.append(
                f"❌ {rel}: {found}× `Any` بينما المسموح {allowed}. الدَّين **يتقلّص فقط**.\n"
                f"   صنِّف النوع (نموذج Pydantic · Protocol · `object`) بدل توسيعه."
            )

    for rel, allowed in sorted(frozen.items()):
        found = current.get(rel, 0)
        if found < allowed:
            errors.append(
                f"❌ {rel}: صار {found}× `Any` بينما الدَّين المُجمَّد {allowed}.\n"
                f"   حدِّث الرقم (`--update`) — خريطةٌ لا تتبع الواقع تتقادم بصمت (D-188)."
            )

    if errors:
        print("\n".join(errors))
        print("\n📌 D-192 (roadmap D1): حدود التكامل بلا `Any`، والباقي يتقلّص ولا ينمو.")
        return 1

    total = sum(current.values())
    print(f"✅ no new Any: حدود التكامل صفريّة · الدَّين المُجمَّد {total} في {len(current)} ملفّاً.")
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
