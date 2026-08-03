#!/usr/bin/env python3
"""بوّابة عقيدة تنسيق الوكلاء — الطبقات عقدٌ مفروض لا ملصقُ طموح (D-209).

## لماذا هذه البوّابة موجودة

وثيقةٌ تصف «أين نحن من الذكاء الاصطناعي الوكيل؟» تتحوّل حتماً إلى كذبٍ مهذَّب: تُكتب مرّةً
في لحظة حماس، ثمّ يتحرّك الكود ولا تتحرّك هي. وهذا **حدث فعلاً** في الملفّ الذي تحرسه هذه
البوّابة: `.memory/agentic_runtime_doctrine.md` بقي على تحقّق **2026-06-29** بينما تحرّك
النظام خمسة أسابيع، وكان يكتب «27 registered descriptors» يدوياً لكمّيةٍ متحرّكة — وهو
بالحرف صنفُ العطب الذي وُلد من أجله D-192.

والأخطر أنّ الوثيقة كانت **الخريطة الوحيدة** لطبقات النظام، فوكيلٌ يقرؤها يبني عليها قراراً
معمارياً. خريطةٌ تكذب أسوأ من غياب خريطة: تُقرأ بدقّة من الناس الذين يحاولون أن يكونوا
دقيقين (نفس حجّة `check_cs_knowledge_map` في D-207).

فالخريطة هنا **مفروضة آلياً** بستّة بنود، كلٌّ منها وُلد من عطبٍ حقيقي في هذا المستودع:

1. **الدليل الملفّي موجود فعلاً** — لا تُكتب حالةٌ أمام ملفٍّ محذوف أو مُعاد تسميته. هذا هو
   الفارض الحقيقي: الادّعاء يصير مكلفاً لأنه يجب أن يشير إلى شيءٍ يُفتَح.
2. **الحالة من السُّلَّم القانوني** (§6.6 + `SEAM`/`ABSENT` من D-207 + `PLANNED` التي يستعملها
   هذا الملفّ منذ D-146) — لا حالاتٌ مخترَعة («قيد العمل»، «شبه جاهز»).
3. **لا طبقة بلا فجوة مكتوبة** — الخانة الفارغة تُقرأ نجاحاً، وهي أخطر من `ABSENT` الصريحة
   (`.memory/aesthetics_of_absence.md`: ما لا يُرى لا يُساءَل).
4. **الطبقات لا تُحذف بصمت** — العدد المُعلَن يُقارَن بالمقروء، فحذفُ صفٍّ مزعج يُكشَف.
5. **كل بوّابة يُسمّيها القانون موجودة** — قانونٌ يستشهد بفارضٍ محذوف أسوأ من قانونٍ بلا
   فارض: الأوّل يَعِد بحراسةٍ غير قائمة (ISS-149 F3).
6. **⛔ لا سُلَّم ثانٍ** — وثيقة القانون تفشل إن حملت عمود حالة، وعددُ طبقاتها يجب أن يطابق
   عددَ صفوف الحالة. قائمتان لنفس البناء تعنيان وكيلَين يقرآن خريطتين مختلفتين للنظام
   نفسه — وهو ما أنتج ISS-139 حين تفرّقت ثلاث قوائم لنيّةٍ واحدة (D-186).

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DOC = REPO_ROOT / ".memory/agentic_runtime_doctrine.md"
LAW_DOC = REPO_ROOT / "docs/architecture/AGENTIC_ORCHESTRATION_DOCTRINE.md"
FITNESS_DIR = REPO_ROOT / "scripts/fitness"

#: السُّلَّم القانوني الوحيد: §6.6 + `SEAM`/`ABSENT` (D-207) + `PLANNED` (D-146).
#: توسيعه قرارٌ يُكتب في `.memory/decisions.md`، لا تحريرُ مجموعة.
VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})

#: عدد طبقات التنسيق المُعلَن (§2.a) وعدد الآفاق (§2.b).
#: تغييرهما قرارٌ يُسجَّل، لا رقمٌ يُحرَّر.
EXPECTED_LAYERS = 9
EXPECTED_HORIZONS = 3

#: صفّ الحالة: | # | الطبقة | الحامل | دليل | الحالة | الفجوة |
_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")

#: الدليل مكتوبٌ داخل `backticks` — نستخرجه كي لا نُطابِق نثراً.
_EVIDENCE = re.compile(r"`([^`]+)`")

#: كل بوّابة تُسمّى في وثيقة القانون يجب أن توجد فعلاً.
_GATE_MENTION = re.compile(r"`(check_[a-z0-9_]+)`")

#: أقسام الطبقات في وثيقة القانون: `## 1) …` حتى `## 9) …`.
_LAW_SECTION = re.compile(r"^## (\d+)\) (.+)$", re.MULTILINE)


def _section(text: str, start_marker: str, end_marker: str) -> str:
    """يقتطع ما بين علامتين. نُقيّد القراءة بالقسم كي لا نخلط جدولاً بجدول.

    §2.c يحمل جدولاً بستّة أعمدة أيضاً لكن **بترتيب مختلف** (الحالة قبل الدليل)، فقراءة
    الملفّ كلّه بنمطٍ واحد كانت ستقرأ عمود الدليل مكانَ الحالة وتمرّ زوراً.
    """
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    return text[start:] if end == -1 else text[start:end]


def _known_gate_names() -> set[str]:
    """أسماء البوّابات المعروفة: ملفّاتٌ **أو** دوالّ داخل ملفّات `scripts/fitness/`.

    ليست كل بوّابة ملفّاً مستقلّاً: `check_confusion_never_an_answer` دالّةٌ داخل
    `check_pedagogical_os.py`. فقاعدة «ملفّ لكل اسم» كانت سترفض استشهاداً صحيحاً — وبوّابةٌ
    ترفض الصواب تُعلَّم الناسُ تجاهلَها.
    """
    names: set[str] = set()
    for path in sorted(FITNESS_DIR.glob("*.py")):
        names.add(path.stem)
        # نقرأ نصّياً لا بـAST: البوّابة يجب أن تعمل في sandbox متدهور (نفس قيد db_bridge).
        for match in re.finditer(
            r"^def (check_[a-z0-9_]+)\(", path.read_text(encoding="utf-8"), re.MULTILINE
        ):
            names.add(match.group(1))
    return names


def _check_row(number: int, layer: str, evidence: str, status: str, gap: str) -> list[str]:
    """يفحص صفّاً واحداً: الحالة من السُّلَّم · الفجوة مكتوبة · الدليل موجود فعلاً."""
    where = f"الطبقة {number} ({layer.strip()})"
    problems: list[str] = []

    clean_status = status.strip("`* ")
    if clean_status not in VALID_STATUSES:
        problems.append(
            f"{where}: الحالة {clean_status!r} خارج السُّلَّم القانوني "
            f"({', '.join(sorted(VALID_STATUSES))}) — لا سُلَّم ثانٍ (§6.6)."
        )

    clean_gap = gap.strip()
    if not clean_gap or clean_gap in ("-", "—"):
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


def _read_rows(text: str) -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    for line in text.splitlines():
        match = _ROW.match(line.strip())
        if not match:
            continue
        number, layer, _carrier, evidence, status, gap = match.groups()
        rows.append((int(number), layer, evidence, status, gap))
    return rows


def _check_law(state_layer_count: int) -> list[str]:
    """يفرض أن وثيقة القانون تُسمّي فوارضَ **موجودة**، وأنها لا تحمل حالات."""
    problems: list[str] = []
    if not LAW_DOC.is_file():
        return [f"{LAW_DOC.relative_to(REPO_ROOT)} غير موجودة — القانون جزء من العقد لا ملحقاً."]

    text = LAW_DOC.read_text(encoding="utf-8")
    known = _known_gate_names()
    for gate in sorted(set(_GATE_MENTION.findall(text))):
        if gate not in known:
            problems.append(
                f"عقيدة التنسيق تستشهد بالبوّابة {gate!r} وهي غير موجودة في "
                f"scripts/fitness/ (لا ملفّاً ولا دالّة) — قانونٌ يَعِد بحراسةٍ غير قائمة."
            )

    sections = _LAW_SECTION.findall(text)
    if len(sections) != state_layer_count:
        problems.append(
            f"وثيقة القانون تحمل {len(sections)} طبقة بينما جدول الحالة يحمل "
            f"{state_layer_count} — طبقةٌ بقانونٍ بلا حالة (أو العكس) تعني خريطتين."
        )

    body = text
    for number, title in sections:
        start = body.find(f"## {number}) {title}")
        nxt = body.find("\n## ", start + 1)
        section_text = body[start:] if nxt == -1 else body[start:nxt]
        if "**الفارض:**" not in section_text and "بلا فارض" not in section_text:
            problems.append(
                f"الطبقة «{title}» بلا سطر «**الفارض:**» ولا إعلانِ «بلا فارض» — "
                f"الصمت يُقرأ انضباطاً وهو ليس كذلك."
            )

    # ⛔ لا سُلَّم ثانٍ: القانون لا يحمل حالات — الحالة موطنها ملفّ واحد.
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        for cell in stripped.strip("|").split("|"):
            if cell.strip("`* ") in VALID_STATUSES:
                problems.append(
                    f"{LAW_DOC.name}:{line_no}: خانةُ جدولٍ تحمل الحالة "
                    f"{cell.strip()!r}. القانون لا يحمل حالات (D-188) — "
                    f"موطنها {STATE_DOC.name} وحده."
                )
    return problems


def main() -> int:
    failures: list[str] = []

    if not STATE_DOC.is_file():
        print(f"❌ {STATE_DOC.relative_to(REPO_ROOT)} غير موجودة — الخريطة جزء من العقد.")
        return 1

    text = STATE_DOC.read_text(encoding="utf-8")
    layers = _read_rows(_section(text, "### 2.a", "### 2.b"))
    horizons = _read_rows(_section(text, "### 2.b", "### 2.c"))

    if not layers:
        print("❌ لم يُقرأ أيّ صفّ من جدول الطبقات (§2.a) — تغيّر شكل الجدول؟")
        return 1
    if not horizons:
        print("❌ لم يُقرأ أيّ صفّ من جدول الآفاق (§2.b) — تغيّر شكل الجدول؟")
        return 1

    if len(layers) != EXPECTED_LAYERS:
        failures.append(
            f"عدد طبقات التنسيق {len(layers)} ≠ المُعلَن {EXPECTED_LAYERS}. "
            f"حذفُ طبقةٍ أو إضافتها قرارٌ يُسجَّل في .memory/decisions.md."
        )
    if len(horizons) != EXPECTED_HORIZONS:
        failures.append(
            f"عدد الآفاق {len(horizons)} ≠ المُعلَن {EXPECTED_HORIZONS}. "
            f"الطموح لا يُحذف بصمت — يُصنَّف أو يُسجَّل قرارُ إسقاطه."
        )

    seen: set[int] = set()
    for number, layer, evidence, status, gap in layers + horizons:
        if number in seen:
            failures.append(f"الطبقة {number} ({layer.strip()}): رقمٌ مكرَّر.")
        seen.add(number)
        failures.extend(_check_row(number, layer, evidence, status, gap))

    failures.extend(_check_law(len(layers)))

    if failures:
        print("❌ عقيدة تنسيق الوكلاء مخروقة:\n")
        for failure in failures:
            print(f"  • {failure}")
        return 1

    active = sum(1 for _, _, _, s, _ in layers if s.strip("`* ") == "ACTIVE")
    print(
        f"✅ عقيدة التنسيق: {len(layers)} طبقة + {len(horizons)} آفاق، "
        f"كلّ دليلٍ موجود، {active} طبقات ACTIVE بالبرهان الملفّي، "
        f"والقانون يُسمّي فوارضَ قائمة بلا سُلَّمٍ ثانٍ."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
