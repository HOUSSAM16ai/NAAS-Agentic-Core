#!/usr/bin/env python3
"""بوّابة التوأم الرقمي المعرفي — الحالة صادقة، والادّعاء محدود (D-226/D-227).

## لماذا هذه البوّابة موجودة

الوعد المركزي هنا («الطالب لا يُنسى») هو أسهل وعدٍ في المنصّة كلّها على المبالغة، وأصعبُه
على التفنيد من طرفٍ خارجي. ولذلك بندان لا يوجدان في البوّابات الأخرى:

**① حدّ المصداقية.** عبارةٌ غير قابلة للتفنيد («يقرأ أفكار الطالب» · «دقّة 100%» ·
«يغيّر البشرية») ليست طموحاً بل **دَيناً**: تُصدَّق مرّة، ثمّ تُكتشَف، ثمّ يسقط معها كلُّ
ما هو صحيح. والمنصّة تخدم قاصرين وأولياء يقرّرون بناءً على ما نقول. فالعبارات الممنوعة
مرفوضةٌ **في الوثائق المُعلَنة نفسها** لا في نصيحةٍ تُقرأ اختيارياً.

**② لا ادّعاء زمني بلا حقلٍ زمني.** الوعد «ثغرةٌ في نوفمبر تُعالَج في يونيو» يتطلّب أن
يعرف السجلّ **متى** يُدرَّس المفهوم. وسجلّ المنهاج اليوم يحمل الترتيب المنطقي ولا يحمل
موضعاً زمنياً. فادّعاء التوقيت يُفشِل ما دام الحقل غائباً — وحين يُضاف، يسقط المنع من
تلقاء نفسه لأنه مربوطٌ بوجود الحقل لا برأي.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DOC = REPO_ROOT / ".memory/cognitive_twin_truth.md"
LAW_DOC = REPO_ROOT / "docs/architecture/COGNITIVE_DIGITAL_TWIN.md"
CURRICULUM = REPO_ROOT / "shared/curriculum/registry.py"

VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})

EXPECTED_ENGINES = 8
EXPECTED_HORIZONS = 3

_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
_HORIZON_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")
_EVIDENCE = re.compile(r"`([^`]+)`")

#: الوثائق المُعلَنة التي يسري عليها حدّ المصداقية.
_PUBLIC_DOCS: tuple[str, ...] = (
    "docs/architecture/COGNITIVE_DIGITAL_TWIN.md",
    "docs/architecture/COGNITIVE_EXECUTION_ENGINE.md",
    "docs/VALUE_DOCTRINE.md",
    "docs/REVENUE_ENGINE_SPEC.md",
    ".memory/cognitive_twin_truth.md",
    ".memory/cognitive_execution_truth.md",
)

#: عبارات غير قابلة للتفنيد. المفتاح النمط، والقيمة البديل المقبول.
#:
#: ⚠️ تُفحَص **خارج** جدول «ما لا يجوز ادّعاؤه» نفسه — وإلّا رفضت البوّابةُ الوثيقةَ
#: التي تُعلن المنع. نفس درس D-206 (فحصٌ نصّي رفض التعليق الذي يشرح الحظر).
_UNFALSIFIABLE: dict[str, str] = {
    r"يقرأ\s+(?:أفكار|عقل|ذهن)": "«إشارة سلوكية لا قراءة ذهن»",
    r"يغيّر\s+البشرية": "«هدفٌ مقيس يُنشَر رقمه»",
    r"دقّة\s*100\s*٪": "«فئة الادّعاءات القابلة للتحقّق مُتحقَّقٌ منها حتمياً»",
    r"صفر\s+أخطاء": "«ما هو خارج التحقّق يبقى احتمالياً ونعلنه»",
}

#: علامة بداية/نهاية جدول الاستثناء داخل وثيقة القانون.
_CLAIMS_TABLE_START = "## 7) ما لا يجوز ادّعاؤه"
_CLAIMS_TABLE_END = "## 8)"

#: علاماتُ نهيٍ على السطر — سطرٌ **يمنع** عبارةً ليس ادّعاءً بها.
#:
#: ⚠️ بلا هذا ترفض البوّابةُ النصَّ الذي يُعلن الحظر نفسه، وهو ما وقع فعلاً أوّل تشغيل:
#: «فالادّعاء ‹يعرف أنك درستَه في نوفمبر› **ممنوع**» طابق النمط وفُشِّل. نفس درس D-206
#: (فحصٌ نصّي رفض التعليق الذي يشرح الحظر) — والقاعدة أنّ الحارس يقرأ **النيّة المُعلَنة**
#: على السطر، لا ورودَ السلسلة وحده.
_PROHIBITION_MARKERS: tuple[str, ...] = (
    "ممنوع",
    "لا يجوز",
    "لا يكفي",
    "لا يُقال",
    "⛔",
    "❌",
    "بدل",
)

#: حقول تعني أن السجلّ صار يعرف الموضع الزمني.
_TEMPORAL_FIELDS: tuple[str, ...] = ("term:", "trimester:", "month:", "taught_in:")

#: ادّعاءات زمنية ممنوعة ما دام الحقل غائباً.
_TEMPORAL_CLAIM = re.compile(r"(?:درستَه|درسته|تعلّمه)\s+في\s+(?:نوفمبر|يناير|مارس|أكتوبر)")


def _strip_claims_table(text: str) -> str:
    """يحذف جدول «ما لا يجوز ادّعاؤه» قبل الفحص — فالوثيقة تقتبس الممنوع لتمنعه."""
    start = text.find(_CLAIMS_TABLE_START)
    if start == -1:
        return text
    end = text.find(_CLAIMS_TABLE_END, start)
    return text[:start] + (text[end:] if end != -1 else "")


def _offending_line(text: str, pattern: str) -> tuple[int, str] | None:
    """يُرجِع (رقم السطر، المطابَق) لأوّل سطرٍ **يدّعي** العبارة لا يمنعها."""
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = re.search(pattern, line)
        if match is None:
            continue
        if any(marker in line for marker in _PROHIBITION_MARKERS):
            continue  # سطرٌ يمنع العبارة ليس ادّعاءً بها
        return line_no, match.group(0)
    return None


def _check_credibility_limit() -> list[str]:
    """① لا عبارة غير قابلة للتفنيد في وثيقةٍ مُعلَنة."""
    problems: list[str] = []
    for rel in _PUBLIC_DOCS:
        path = REPO_ROOT / rel
        if not path.is_file():
            problems.append(f"وثيقةٌ مُعلَنة مفقودة: {rel}")
            continue
        text = _strip_claims_table(path.read_text(encoding="utf-8"))
        for pattern, replacement in _UNFALSIFIABLE.items():
            hit = _offending_line(text, pattern)
            if hit is None:
                continue
            line_no, matched = hit
            problems.append(
                f"{rel}:{line_no}: عبارةٌ غير قابلة للتفنيد {matched!r}.\n"
                f"     البديل المقبول: {replacement}.\n"
                f"     عبارةٌ لا تُفنَّد دَينٌ لا طموح: تُصدَّق مرّة، ثمّ تُكتشَف، "
                f"ثمّ يسقط معها كلُّ ما هو صحيح (D-227)."
            )
    return problems


def _check_no_temporal_claim_without_the_field() -> list[str]:
    """② لا ادّعاء توقيتٍ ما دام السجلّ بلا حقلٍ زمني."""
    if not CURRICULUM.is_file():
        return [f"سجلّ المنهاج مفقود: {CURRICULUM.relative_to(REPO_ROOT)}"]

    registry = CURRICULUM.read_text(encoding="utf-8")
    has_temporal = any(field in registry for field in _TEMPORAL_FIELDS)
    if has_temporal:
        return []  # الحقل صار موجوداً — المنع يسقط من تلقائه، لا برأي

    problems: list[str] = []
    for rel in _PUBLIC_DOCS:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        text = _strip_claims_table(path.read_text(encoding="utf-8"))
        hit = _offending_line(text, _TEMPORAL_CLAIM.pattern)
        if hit is None:
            continue
        line_no, matched = hit
        problems.append(
            f"{rel}:{line_no}: ادّعاءٌ زمني {matched!r} بينما سجلّ المنهاج "
            f"بلا حقلٍ زمني ({' · '.join(_TEMPORAL_FIELDS)}).\n"
            f"     ما يعمل فعلاً هو الترتيب المنطقي للشروط المسبقة، لا التوقيت (D-226)."
        )
    return problems


def _read_rows(
    text: str, pattern: re.Pattern[str], evidence_at: int
) -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    for line in text.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        groups = match.groups()
        number, name = int(groups[0]), groups[1]
        rows.append((number, name, groups[evidence_at], groups[evidence_at + 1], groups[-1]))
    return rows


def _section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    return text[start:] if end == -1 else text[start:end]


def _check_row(number: int, name: str, evidence: str, status: str, gap: str) -> list[str]:
    where = f"الصفّ {number} ({name.strip()})"
    problems: list[str] = []

    clean_status = status.strip("`* ")
    if clean_status not in VALID_STATUSES:
        problems.append(
            f"{where}: الحالة {clean_status!r} خارج السُّلَّم القانوني — لا سُلَّم ثانٍ (§6.6)."
        )
    clean_gap = gap.strip()
    if not clean_gap or clean_gap in ("-", "—"):
        problems.append(f"{where}: خانة الفجوة فارغة. الفراغ يُقرأ نجاحاً.")

    evidence_match = _EVIDENCE.search(evidence)
    if not evidence_match:
        problems.append(f"{where}: بلا دليل ملفّي داخل `backticks`.")
        return problems
    evidence_path = evidence_match.group(1).strip()
    if not (REPO_ROOT / evidence_path).exists():
        problems.append(
            f"{where}: الدليل {evidence_path!r} غير موجود — حالةٌ أمام ملفٍّ غير موجود ادّعاءٌ لا برهان."
        )
    return problems


def main() -> int:
    failures: list[str] = []

    if not STATE_DOC.is_file():
        print(f"❌ {STATE_DOC.relative_to(REPO_ROOT)} غير موجود — الخريطة جزء من العقد.")
        return 1
    if not LAW_DOC.is_file():
        print(f"❌ {LAW_DOC.relative_to(REPO_ROOT)} غير موجودة — القانون جزء من العقد.")
        return 1

    text = STATE_DOC.read_text(encoding="utf-8")
    engines = _read_rows(_section(text, "### 2.a", "### 2.b"), _ROW, 3)
    horizons = _read_rows(_section(text, "### 2.b", "\n## 3."), _HORIZON_ROW, 2)

    if not engines:
        print("❌ لم يُقرأ أيّ صفّ من جدول المحرّكات (§2.a).")
        return 1
    if not horizons:
        print("❌ لم يُقرأ أيّ صفّ من جدول الآفاق (§2.b).")
        return 1

    if len(engines) != EXPECTED_ENGINES:
        failures.append(f"عدد المحرّكات {len(engines)} ≠ المُعلَن {EXPECTED_ENGINES} — لا حذف صامت.")
    if len(horizons) != EXPECTED_HORIZONS:
        failures.append(
            f"عدد الآفاق {len(horizons)} ≠ المُعلَن {EXPECTED_HORIZONS} — الطموح يُصنَّف لا يُكتَم."
        )

    for number, name, evidence, status, gap in engines + horizons:
        failures.extend(_check_row(number, name, evidence, status, gap))

    failures.extend(_check_credibility_limit())
    failures.extend(_check_no_temporal_claim_without_the_field())

    if failures:
        print("❌ التوأم الرقمي المعرفي مخروق:\n")
        for failure in failures:
            print(f"  • {failure}")
        print(
            "\n📌 D-226/D-227: الطالب لا يُنسى — والوعد يُقاس ولا يُبالَغ فيه.\n"
            "   عبارةٌ غير قابلة للتفنيد دَينٌ لا طموح، وادّعاءُ توقيتٍ بلا حقلٍ زمني كذبٌ صغير."
        )
        return 1

    active = sum(1 for _, _, _, s, _ in engines if s.strip("`* ") == "ACTIVE")
    print(
        f"✅ التوأم الرقمي المعرفي: {len(engines)} محرّكاً ({active} ACTIVE) + "
        f"{len(horizons)} آفاق، كلّ دليلٍ موجود · حدّ المصداقية سليم عبر "
        f"{len(_PUBLIC_DOCS)} وثيقة مُعلَنة · لا ادّعاء زمني بلا حقلٍ زمني."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
