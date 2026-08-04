#!/usr/bin/env python3
"""ISS-149 (F3) — خريطة السلطة لا تشير إلى ملفٍّ غير موجود.

## لماذا هذه البوّابة موجودة

`docs/DOCUMENTATION_INDEX.md` يُعرِّف نفسه بأنه «خريطة السلطة الكاملة»، و`.memory/README.md`
هو «الفهرس الموحَّد» للذاكرة المؤسسية. وكلاهما يُحيل الوكلاءَ والبشرَ إلى مصادر الحقيقة.

وقد كان الفهرس يُحيل إلى **ثلاثة مسارات لا وجود لها**، منها ADR-006 نفسه:

    architecture/adr/006_polyglot_language_adoption.md   ← لا مجلّد ولا ملفّ
    adr/ADR-006-polyglot-language-adoption.md            ← الموجود فعلاً

اكتشفه سؤالُ المالك عن اللغات، لا بوّابة: ذهبتُ أقرأ القرار من مساره المُعلَن فلم أجده.
و`doc-integrity` كان يفحص **وجود** `CLAUDE.md` و`.memory/*` ولا يفحص أن روابطهما تصل.

هذا نفس صنف `check_cs_knowledge_map` (D-207: «دليلٌ يجب أن يوجد»، وبوّابةٌ يُستشهَد بها
وهي غير موجودة ⇒ CI أحمر) مطبَّقاً على **الوثائق** لا على البوّابات. وخريطةٌ تكذب أسوأ
من غياب خريطة: تُقرأ بدقّة من الناس الذين يحاولون أن يكونوا دقيقين.

## ما تفرضه

كل رابط محلّي (غير `http`) في الملفّات المُصرَّحة أدناه يجب أن يُشير إلى مسارٍ موجود.
الروابط الخارجية والمراسي (`#…`) خارج النطاق.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: ملفّات السلطة — من يقرأها يبني عليها قراراً.
#: ⚠️ `README.md` و`README.ar.md` أُضيفا بعد أن تبيّن أن الواجهة الأولى للمستودع كانت
#: تُحيل إلى **ثلاثة مسارات لا وجود لها** (`docs/EVALUATION_PROTOCOL.md` ·
#: `docs/IMPACT_MEASUREMENT_PLAN.md` · `toolkit/START_HERE.md`) وتعرض في خريطتها
#: مجلّداً غير موجود — أي نفس صنف ISS-149 بالضبط، في **أوّل ملفّ يفتحه كل قادمٍ من
#: خارج المستودع**. البوّابة كانت تحرس ما يقرأه المطوّرون وتترك ما يقرأه العالَم.
_AUTHORITY_DOCS: tuple[str, ...] = (
    "docs/DOCUMENTATION_INDEX.md",
    ".memory/README.md",
    "CLAUDE.md",
    "README.md",
    "README.ar.md",
)

_LINK = re.compile(r"\]\((?!https?:|mailto:)([^)\s#]+)")

#: دَينٌ مُجمَّد — **فارغ عمداً**، يتقلّص فقط.
_FROZEN_DEBT: dict[str, str] = {}


def main() -> int:
    failures = 0
    seen_debt: set[str] = set()

    for rel_doc in _AUTHORITY_DOCS:
        doc = REPO_ROOT / rel_doc
        if not doc.exists():
            print(f"❌ ملفّ سلطةٍ مفقود: {rel_doc}")
            failures += 1
            continue
        base = doc.parent
        for target in sorted(set(_LINK.findall(doc.read_text(encoding="utf-8")))):
            key = f"{rel_doc}::{target}"
            if key in _FROZEN_DEBT:
                seen_debt.add(key)
                continue
            if not (base / target).exists():
                print(
                    f"❌ {rel_doc}: الرابط {target!r} لا يُشير إلى شيء.\n"
                    f"   خريطة السلطة تُقرأ بدقّة ممّن يحاول أن يكون دقيقاً — "
                    f"وخريطةٌ تكذب أسوأ من غيابها."
                )
                failures += 1

    for key in sorted(set(_FROZEN_DEBT) - seen_debt):
        print(f"❌ دَينٌ مُجمَّد لم يعد موجوداً: {key!r} — احذفه من `_FROZEN_DEBT`.")
        failures += 1

    if failures:
        print(f"\n❌ check_authority_links: {failures} انتهاكاً.")
        return 1
    print(f"✅ كل روابط ملفّات السلطة الـ{len(_AUTHORITY_DOCS)} تصل إلى مسارات موجودة.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
