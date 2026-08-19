#!/usr/bin/env python3
"""بوّابة عقيدتَي الـHarness والذاكرة — القانون منفصل، والحالة بدليل (D-228/D-229).

## لماذا هذه البوّابة موجودة

بحثان أُضيفا إلى الدستور. وإضافةُ نصٍّ إلى مستودعٍ ليست إضافةَ قانون — القانون ما له
فارض. وقد وُلد هذا الملفّ من ثلاثة أعطالٍ حقيقية سبق أن دفع المستودع ثمنها:

**① خريطتان لنظامٍ واحد.** حين حمل الدستورُ جدولَ حالةٍ مُجمَّداً بجانب القانون، تقادم
الجدول شهرين ونصف وصار **يكذب** على كل وكيلٍ يقرأه (D-188). فالقانون هنا في
`docs/architecture/*_DOCTRINE.md` والحالةُ في `.memory/*_truth.md`، وخلطُهما يُفشِل CI:
رمزُ حالةٍ من سُلَّم §6.6 داخل وثيقة قانونٍ ⇒ أحمر.

**② الخانة الفارغة تُقرأ نجاحاً.** فجوةٌ غير مكتوبة ليست «لا فجوة» بل «لم يُنظَر»
(`.memory/aesthetics_of_absence.md`). فكلّ صفٍّ يحمل فجوةً منطوقة أو يفشل.

**③ بوّابةٌ يُستشهَد بها وهي غير موجودة.** وثيقةٌ تقول «الفارض: `check_X`» بينما `check_X`
غير موجود تمنح طمأنينةً بلا ثمنٍ مدفوع — نفس صنف ISS-148 (فارضٌ بلا مرمى). فكل اسمٍ من
شكل `check_*` يُذكَر في الوثائق الأربع يجب أن يقابله ملفٌّ فعليّ.

⛔ **ولا `except SyntaxError: return []`** (D-208 بند ٦): بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ
أنه نظيف — فشلُ القراءة يُعلَن ويُفشِل.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: سُلَّم الحالة القانوني الوحيد (§6.6). لا سُلَّم ثانٍ.
VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})

#: (وثيقة القانون، وثيقة الحالة، عدد الصفوف المتوقَّع).
#:
#: العدد مُصرَّح كي يصير **حذفُ صفٍّ بصمت** أحمر: من يحذف قدرةً أو تحدّياً يجب أن
#: يُحدِّث الرقم هنا، فيصير الحذف قراراً مرئياً لا تسرّباً.
DOCTRINES: tuple[tuple[str, str, int], ...] = (
    (
        "docs/architecture/HARNESS_ENGINEERING_DOCTRINE.md",
        ".memory/harness_truth.md",
        15,
    ),
    (
        # D-269: 9 → 10. أُضيف صفُّ **الطبقة المحيطة** (طرفٌ ثالث — Honcho) بعد أن
        # دخل مفتاحُها المستودع. أُضيف صفّاً مستقلّاً لا مالكاً ثانياً لطبقةٍ قائمة،
        # لأنّ طبقةً بمالكَين هي بالضبط ما أنتج ٢٦ انفجار كتابةٍ مزدوجة في ٥٢ صفّاً
        # (يونيو 2026) — والرقم مُصرَّح هنا كي يصير حذفُ الصفّ قراراً مرئياً.
        "docs/architecture/MEMORY_ARCHITECTURE_DOCTRINE.md",
        ".memory/memory_architecture_truth.md",
        10,
    ),
)

#: دليلٌ داخل `backticks`. أوّل مسارٍ يبدو كمسار مستودع هو الدليل.
_BACKTICKED = re.compile(r"`([^`]+)`")
_GATE_NAME = re.compile(r"\bcheck_[a-z0-9_]+\b")
_STATUS_TOKEN = re.compile(r"\b(ACTIVE|PARTIAL|DORMANT|ZOMBIE|PLANNED|SEAM|ABSENT)\b")


class DoctrineGateError(RuntimeError):
    """يُرفَع حين يتعذّر قراءة ملفٍّ — الصمت ليس نجاحاً."""


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.is_file():
        raise DoctrineGateError(f"ملفٌّ مفقود: {rel}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - عطل نظام ملفّات
        raise DoctrineGateError(f"تعذّرت قراءة {rel}: {exc}") from exc


def _looks_like_path(candidate: str) -> bool:
    """مسار مستودع: فيه `/` أو ينتهي بلاحقةٍ معروفة."""
    return "/" in candidate or candidate.endswith((".py", ".md", ".json", ".css", ".jsx"))


def _table_rows(text: str) -> list[tuple[int, list[str]]]:
    """كل صفّ جدولٍ يبدأ بعددٍ — بلا افتراضٍ عن عدد الأعمدة.

    الجداول هنا ليست بعرضٍ واحد (بعضها ٥ أعمدة وبعضها ٦)، والقارئ الذي يفترض عرضاً
    ثابتاً يتجاهل الجدول الآخر بصمت — وهو تحديداً ما يجعل بوّابةً تمرّ زوراً.
    """
    rows: list[tuple[int, list[str]]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if len(cells) < 4 or not cells[0].isdigit():
            continue
        rows.append((line_no, cells))
    return rows


def _check_row_status(where: str, cells: list[str]) -> list[str]:
    """الحالة من السُّلَّم القانوني وحده — لا سُلَّم ثانٍ (§6.6)."""
    if any(cell.strip("`* ") in VALID_STATUSES for cell in cells):
        return []
    return [
        f"{where}: بلا حالةٍ من السُّلَّم القانوني "
        f"({' · '.join(sorted(VALID_STATUSES))}) — لا سُلَّم ثانٍ (§6.6)."
    ]


def _check_row_gap(where: str, cells: list[str]) -> list[str]:
    """الفراغ يُقرأ نجاحاً — «لا فجوة معروفة» جوابٌ مشروع، والفراغ ليس كذلك."""
    gap = cells[-1]
    if gap and gap not in {"-", "—", "–"}:
        return []
    return [f"{where}: خانة الفجوة فارغة. الفراغ يُقرأ نجاحاً."]


def _check_row_evidence(where: str, cells: list[str]) -> list[str]:
    """كل المرشَّحين في الصفّ، لا الأوّل وحده.

    خانة «الحامل» تذكر أحياناً مساراً اصطلاحياً (`/metrics`) ليس ملفّاً، والدليل الحقيقي
    في خانةٍ تالية. يكفي أن **يوجد واحد** — وحذفُ الدليل يبقى أحمر لأنّ أحداً لن يوجد.
    """
    candidates = [
        candidate
        for cell in cells
        for candidate in _BACKTICKED.findall(cell)
        if _looks_like_path(candidate)
    ]
    if not candidates:
        return [f"{where}: بلا دليلٍ ملفّي داخل `backticks`."]
    if any((REPO_ROOT / candidate).exists() for candidate in candidates):
        return []
    return [
        f"{where}: لا واحد من الأدلّة المذكورة موجود ({' · '.join(candidates)}).\n"
        f"     حالةٌ أمام دليلٍ محذوف هي ادّعاءٌ لا حقيقة (§6.6)."
    ]


def _check_row_count(rel: str, actual: int, expected: int) -> list[str]:
    if actual == expected:
        return []
    return [
        f"{rel}: عدد الصفوف {actual} والمتوقَّع {expected}.\n"
        f"     إضافةُ صفٍّ أو حذفه قرارٌ يُعلَن: حدِّث DOCTRINES في هذه البوّابة "
        f"ودوِّن السبب في .memory/decisions.md. ⛔ لا حذف صامت."
    ]


def _check_state_doc(rel: str, expected_rows: int) -> list[str]:
    rows = _table_rows(_read(rel))
    problems = _check_row_count(rel, len(rows), expected_rows)

    seen: set[int] = set()
    for line_no, cells in rows:
        number = int(cells[0])
        where = f"{rel}:{line_no} (الصفّ {number})"
        if number in seen:
            problems.append(f"{where}: رقم صفٍّ مكرَّر — الترقيم مُعرِّف لا زينة.")
        seen.add(number)

        problems += _check_row_status(where, cells)
        problems += _check_row_gap(where, cells)
        problems += _check_row_evidence(where, cells)

    return problems


def _check_law_doc(rel: str) -> list[str]:
    """وثيقة القانون لا تحمل حالة — وإلّا صار للنظام سُلَّمان وخريطتان."""
    problems: list[str] = []
    text = _read(rel)
    for line_no, raw in enumerate(text.splitlines(), start=1):
        match = _STATUS_TOKEN.search(raw)
        if match is None:
            continue
        problems.append(
            f"{rel}:{line_no}: رمز حالة {match.group(0)!r} داخل وثيقة قانون.\n"
            f"     الحالة موطنها `.memory/*_truth.md` وحده (D-188/D-209): "
            f"خريطتان لنظامٍ واحد تعنيان وكيلَين يقرآن بناءَين مختلفين."
        )
    return problems


def _check_cited_gates(docs: list[str]) -> list[str]:
    """بوّابةٌ يُستشهَد بها وهي غير موجودة تمنح طمأنينةً بلا ثمن (ISS-148)."""
    problems: list[str] = []
    for rel in docs:
        text = _read(rel)
        for name in sorted(set(_GATE_NAME.findall(text))):
            if not (REPO_ROOT / "scripts" / "fitness" / f"{name}.py").is_file():
                problems.append(
                    f"{rel}: يستشهد بالبوّابة {name!r} وهي غير موجودة في scripts/fitness/.\n"
                    f"     قانونٌ يُسمّي فارضاً غير موجود ليس مفروضاً — إمّا تُبنى أو يُصرَّح «بلا فارض»."
                )
    return problems


def main() -> int:
    failures: list[str] = []
    all_docs: list[str] = []

    try:
        for law, state, expected in DOCTRINES:
            all_docs.extend((law, state))
            failures.extend(_check_law_doc(law))
            failures.extend(_check_state_doc(state, expected))
        failures.extend(_check_cited_gates(all_docs))
    except DoctrineGateError as exc:
        print(f"❌ عقيدتا البحث (D-228/D-229): {exc}")
        print("   بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208).")
        return 1

    if failures:
        print("❌ عقيدتا الـHarness والذاكرة (D-228/D-229) — مخالفات:\n")
        for item in failures:
            print(f"  • {item}")
        print(
            "\n   القاعدة: القانون في docs/architecture/ والحالة في .memory/، "
            "وكل صفٍّ بدليلٍ موجودٍ وفجوةٍ منطوقة، وكل بوّابةٍ مذكورةٍ موجودة."
        )
        return 1

    total = sum(expected for _, _, expected in DOCTRINES)
    print(
        f"✅ عقيدتا الـHarness والذاكرة (D-228/D-229): "
        f"{len(DOCTRINES)} عقيدتان · {total} صفّ حالةٍ بدليلٍ موجودٍ وفجوةٍ منطوقة · "
        f"كل بوّابةٍ مذكورةٍ موجودة."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
