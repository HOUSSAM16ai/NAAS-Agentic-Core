#!/usr/bin/env python3
"""بوّابة خريطة علوم الحاسوب — الخريطة عقدٌ مفروض لا ملصقُ طموح (ISS-148).

## لماذا هذه البوّابة موجودة

أيّ وثيقة «أين نحن من علوم الحاسوب؟» تتحوّل حتماً إلى كذبٍ مهذَّب: تُكتب مرّةً في لحظة
حماس، ثمّ يتحرّك الكود ولا تتحرّك هي. وقد حدث هذا في هذا المستودع نفسه أكثر من مرّة —
جدول حالةٍ مؤرَّخ في الدستور بقي مُجمَّداً شهرين ونصفاً وهو يكذب على كل وكيل يقرأه
(D-188)، وأعدادٌ مكتوبة يدوياً تناقض بعضها في قسمين من الملفّ نفسه (D-192).

فالخريطة هنا **مفروضة آلياً**:

1. **الدليل الملفّي موجود فعلاً** — لا يُكتب `ACTIVE` أمام ملفٍّ محذوف أو مُعاد تسميته.
   هذا هو الفارض الحقيقي: الادّعاء يصير مكلفاً لأنه يجب أن يشير إلى شيءٍ يُفتَح.
2. **الحالة من السُّلَّم القانوني** (§6.6) — لا سُلَّم ثانٍ ولا حالاتٌ مخترَعة
   («جزئياً»، «قيد العمل»)، فالسُّلَّم الموازي يُفرِّغ الأوّل من معناه.
3. **لا مجال بلا حالة ولا فجوة** — الخانة الفارغة تُقرأ نجاحاً، وهي أخطر من `ABSENT`
   الصريحة (`.memory/aesthetics_of_absence.md`: ما لا يُرى لا يُساءَل).
4. **المجالات لا تُحذف بصمت** — العدد المُعلَن يُقارَن بالمقروء، فحذفُ صفٍّ مزعج يُكشَف.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAP_DOC = REPO_ROOT / "docs/architecture/CS_KNOWLEDGE_MAP.md"
DOCTRINE_DOC = REPO_ROOT / "docs/architecture/ENGINEERING_DOCTRINE.md"

#: سُلَّم الحالة القانوني — نفس §6.6 زائد `SEAM`/`ABSENT` للصدق عن الغياب.
VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "SEAM", "ABSENT"})

#: عدد المجالات المُعلَن. تغييره قرارٌ يُكتب في `.memory/decisions.md`، لا تحريرُ رقم.
EXPECTED_DOMAINS = 20

#: صفّ الخريطة: | # | مجال | حامل | دليل | حالة | فجوة |
_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|\s*$")

#: الدليل مكتوبٌ داخل `backticks` — نستخرجه كي لا نُطابِق نثراً.
_EVIDENCE = re.compile(r"`([^`]+)`")


#: كل بوّابة تُسمّى في عقيدة الهندسة يجب أن توجد فعلاً في `scripts/fitness/`.
#: قانونٌ يستشهد ببوّابة محذوفة أسوأ من قانونٍ بلا فارض: الأوّل يَعِد بحراسةٍ غير قائمة.
_GATE_MENTION = re.compile(r"`(check_[a-z0-9_]+)`")


def _check_doctrine() -> list[str]:
    """يفرض أن عقيدة الهندسة تُسمّي فوارضَ **موجودة**، وأنها تغطّي المجالات."""
    problems: list[str] = []
    if not DOCTRINE_DOC.is_file():
        return [f"{DOCTRINE_DOC.name} غير موجودة — القانون جزء من العقد لا ملحقاً."]

    text = DOCTRINE_DOC.read_text(encoding="utf-8")
    fitness_dir = REPO_ROOT / "scripts/fitness"
    for gate in sorted(set(_GATE_MENTION.findall(text))):
        if not (fitness_dir / f"{gate}.py").is_file():
            problems.append(
                f"عقيدة الهندسة تستشهد بالبوّابة {gate!r} وهي غير موجودة في "
                f"scripts/fitness/ — قانونٌ يَعِد بحراسةٍ غير قائمة."
            )

    # كل مجالٍ في الوثيقة يجب أن يُسمّي فارضاً أو يُعلن غيابه صراحةً (L11).
    sections = re.split(r"^## \d+\) ", text, flags=re.MULTILINE)[1:]
    for section in sections:
        title = section.splitlines()[0].strip()
        if "**الفارض:**" not in section and "بلا فارض" not in section:
            problems.append(
                f"المجال «{title}» بلا سطر «**الفارض:**» ولا إعلانِ «بلا فارض» — "
                f"الصمت يُقرأ انضباطاً وهو ليس كذلك."
            )
    return problems


def _check_row(number: int, domain: str, evidence: str, status: str, gap: str) -> list[str]:
    """يفحص صفّاً واحداً: الحالة من السُّلَّم · الفجوة مكتوبة · الدليل موجود فعلاً."""
    where = f"المجال {number} ({domain})"
    problems: list[str] = []

    clean_status = status.strip("` ")
    if clean_status not in VALID_STATUSES:
        problems.append(
            f"{where}: الحالة {clean_status!r} خارج السُّلَّم القانوني "
            f"({', '.join(sorted(VALID_STATUSES))}) — لا سُلَّم ثانٍ (§6.6)."
        )

    if not gap or gap in ("-", "—"):
        problems.append(
            f"{where}: خانة الفجوة فارغة. الفراغ يُقرأ نجاحاً — اكتب الفجوة أو «لا فجوة معروفة»."
        )

    evidence_match = _EVIDENCE.search(evidence)
    if not evidence_match:
        problems.append(f"{where}: بلا دليل ملفّي داخل `backticks`.")
        return problems

    evidence_path = evidence_match.group(1).strip()
    if not (REPO_ROOT / evidence_path).exists():
        problems.append(
            f"{where}: الدليل {evidence_path!r} غير موجود في المستودع. "
            f"حالةٌ أمام ملفٍّ غير موجود ادّعاءٌ لا برهان."
        )
    return problems


def main() -> int:
    failures: list[str] = []

    if not MAP_DOC.is_file():
        print(f"❌ {MAP_DOC.relative_to(REPO_ROOT)} غير موجودة — الخريطة جزء من العقد.")
        return 1

    rows: list[tuple[int, str, str, str, str]] = []
    for line in MAP_DOC.read_text(encoding="utf-8").splitlines():
        match = _ROW.match(line.strip())
        if not match:
            continue
        number, domain, _carrier, evidence, status, gap = match.groups()
        rows.append((int(number), domain.strip(), evidence.strip(), status.strip(), gap.strip()))

    if not rows:
        print("❌ لم يُقرأ أيّ صفّ من الخريطة — تغيّر شكل الجدول؟")
        return 1

    if len(rows) != EXPECTED_DOMAINS:
        failures.append(
            f"عدد المجالات {len(rows)} ≠ المُعلَن {EXPECTED_DOMAINS}. "
            f"حذفُ مجالٍ أو إضافته قرارٌ يُسجَّل في .memory/decisions.md."
        )

    seen_numbers: set[int] = set()
    for number, domain, evidence, status, gap in rows:
        if number in seen_numbers:
            failures.append(f"المجال {number} ({domain}): رقمٌ مكرَّر.")
        seen_numbers.add(number)
        failures.extend(_check_row(number, domain, evidence, status, gap))

    failures.extend(_check_doctrine())

    if failures:
        print("❌ خريطة علوم الحاسوب / عقيدة الهندسة مخروقة:\n")
        for failure in failures:
            print(f"  • {failure}")
        return 1

    active = sum(1 for _, _, _, s, _ in rows if s.strip("` ") == "ACTIVE")
    print(
        f"✅ خريطة علوم الحاسوب: {len(rows)} مجالاً، كلّ دليلٍ موجود، "
        f"{active} منها ACTIVE بالبرهان الملفّي."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
