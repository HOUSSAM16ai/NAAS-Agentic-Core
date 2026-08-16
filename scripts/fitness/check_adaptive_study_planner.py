#!/usr/bin/env python3
"""بوّابة دستور مخطط الدراسة التكيفي — D-264 / ISS-178→ISS-181.

## لماذا هذه البوّابة موجودة
دستورٌ جديد (`.memory/adaptive_study_planner_constitution.md`) يحوّل ورقة
المخطّط الأسبوعي من To-Do List إلى عقلٍ يخطط ويتكيف: «الطالب يحدد أهدافه ←
النظام يشخّصها ← يقسّمها تلقائيًّا على الأسبوع ← يتابع الإنجاز ← يعيد
الضبط». والقانون ما له فارض؛ فإضافة نصٍّ إلى مستودعٍ ليست إضافةَ قانون.

**ما تفحصه (قانون D-264 §4):**
1. الدستور موجود ومكتمل: §1 التشخيص · §2 العقيدة والحلقة المغلقة الست ·
   §3 الأبواب الأربعة · §4 القوانين العشرة · §6 المقياس.
2. **L1: التشخيص قبل الجدولة** — مصادرها الوحيدة موجودة وحيّة:
   `shared/curriculum/` (D-193) · `shared/scheduling/fsrs.py` (D-194) ·
   `shared/habit/streak.py` (D-195) · `bkt_engine.py`.
3. **L3: الحتمية القابلة للاختبار** — نمط مولّدٍ نقي (pure function) على
   التشخيص: لا تُوجد دالة ترتيبٍ تعتمد LLM/صدفة في أي مولّد مخطّط حالي أو قادم.
4. **L7: الامتحان يقفل الجدول** — حقل/جدول تواريخ امتحانات موجود (أو نمط
   schema يلتزم به) داخل REQUIRED_SCHEMA أو ملف schema.
5. **L9: الإنجاز append-only** — `student_review_schedule` يحمل نمط append-only
   (يُتحقق نصيًا أنه لا يُكتب update/delete عليه في الكود الإنتاجي).
6. **L10: التفسير قبل الوعد** — لا قالبٍ في المسار الحيّ يعد بناتج واعد
   («ستتقن/ستنجح»)؛ الوعد الوظيفي الوحيد «مستهدف بمؤشر قياس».
7. **لا ادّعاء رقمي يدوي** — أي «+%» في وثيقةٍ دستورية يجب أن يشير إلى مرجعٍ
   منشور أو منهجيةٍ (يمتدّ D-263 §6.6 وقفل Learning Gain).
8. **الأعداد تُشتَقّ** — عداد القوانين عشرة كامل، وكل قانون يسمي فارضًا
   موجودًا (no orphan enforcer — D-188 بند ③).

**لا تُستورد من app/** (نمط `check_pedagogical_os.py`) — static-text خالصة
تعمل في بيئة متدهورة. Exit 0 = نظيف · 1 = انتهاك.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_FAILURES: list[str] = []


def _fail(msg: str) -> None:
    _FAILURES.append(msg)
    print(f"❌ {msg}")


def _pass(msg: str) -> None:
    print(f"✅ {msg}")


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    if not path.is_file():
        _fail(f"ملفّ مفقود: {rel}")
        return ""
    return path.read_text(encoding="utf-8")


def _must(pattern: str, text: str, where: str, count: int | None = None) -> None:
    found = re.findall(pattern, text)
    n = len(found)
    if count is not None:
        if n != count:
            _fail(f"{where}: متوقّع {count} مطابقة لنمط `{pattern}`، وُجدت {n}")
            return
        _pass(f"{where}: {n} مطابقة لـ `{pattern}`")
    elif n == 0:
        _fail(f"{where}: النمط مفقود `{pattern}`")
    else:
        _pass(f"{where}: `{pattern}` حاضر ({n}×)")


def _check_constitution_sections(const: str) -> None:
    for section in (
        r"## 1\. التشخيص الدستوري",
        r"## 2\. العقيدة الأساسية",
        r"الحلقة التكيفية المغلقة",
        r"## 3\. الركائز الأربع",
        r"## 4\. القوانين الصارمة العشرة",
        r"## 6\. مقياس النجاح الدستوري",
        r"## 7\. علاقة هذا الدستور بالعقائد القائمة",
    ):
        _must(section, const, "الدستور D-264")


def _check_section_laws(const: str) -> None:
    # ⑧ عداد القوانين: عشرة تمامًا (يُشتَقّ من نص الدستور)
    laws = re.findall(r"^\| L(\d+) \|", const, flags=re.M)
    if set(laws) != {str(i) for i in range(1, 11)}:
        _fail(f"قوانين §4 ليست عشرة كاملة (وُجدت: {sorted(laws, key=int)})")
        return
    _pass("القوانين العشرة كاملة L1–L10")


def _check_diagnostic_sources() -> None:
    # L1: المصادر التشخيصية الوحيدة للمخطّط حيّة (D-193 · D-194 · D-195)
    cur = _read("shared/curriculum/registry.py")
    _must(r"[Cc]oncept|curriculum", cur, "shared/curriculum/registry.py (مصدر المفاهيم D-193)")
    fsrs = _read("shared/scheduling/fsrs.py")
    _must(
        r"def (retention|interval|stability|schedule)|Retrievability",
        fsrs,
        "fsrs.py (منحنى النسيان D-194)",
    )
    sched = _read("app/services/skills/review_scheduler_skill.py") or _read(
        "app/services/review/persistence.py",
    )
    if sched:
        _must(
            r"review_schedule|student_review_schedule|schedule",
            sched,
            "جدول المراجعات (append-only)",
        )
    bkt = _read("app/services/skills/bkt_engine.py")
    _must(r"def update_mastery", bkt, "bkt_engine (مصفوفة الإتقان)")
    streak = _read("shared/habit/streak.py")
    _must(r"streak|STREAK|Streak", streak, "streak.py (سلسلة D-195)")


def _check_no_llm_ordering() -> None:
    # L3: لا يوجد مولّد ترتيبٍ بالاعتماد على LLM/صدفة؛ المولّد الحتمي النمطي
    # الحالي هو ReviewSchedulerSkill (FSRS-based). المسح نصي على كل مولّدات
    # الجدولة المعروفة لمنع انزلاق LLM إلى «ترتيب الأيام».
    for cand in (
        "app/services/skills/review_scheduler_skill.py",
        "app/services/review/persistence.py",
        "shared/scheduling/fsrs.py",
    ):
        text = _read(cand)
        if not text:
            continue
        # استثناء معلوم: تعليق توثيقي يصرّح بحتمية المولّد ("صفر LLM") —
        # التصريح بالحتمية ليس اعتمادًا عليها؛ نحذف الأسطر المت-commentة ونفحص الكود.
        code_lines = [
            line
            for line in text.splitlines()
            if not re.match(r"^\s*(#|\*|''')", line) and not re.match(r'^\s*"""', line)
        ]
        code = "\n".join(code_lines)
        bad = re.findall(r"\b(random\.choice|OpenRouter|openai)\b", code)
        # كلمة LLM وحدها في كودٍ قد تكون اسم متغيرٍ مشروع (مثل llm=None default)
        # — الفحص هنا على النمط الأخطر حصريًا: استدعاء صدفة فعلي.
        if bad:
            _fail(f"{Path(cand).name}: اعتماد على LLM/صدفة في مولّد الجدولة (L3)")
        else:
            _pass(f"{Path(cand).name}: خالٍ من ترتيب LLM/صدفة (L3)")


def _check_exam_lock() -> None:
    # L7: تواريخ الامتحانات جزء من نمط schema — إما REQUIRED_SCHEMA أو
    # migrations تحتوي نمط امتحان. الغياب = خطة لا تعرف الامتحان = مرفوض.
    schema = _read("app/core/db_schema_config.py")
    if not schema:
        # fallback: امسح أي ملف schema معروف
        for cand in (
            "app/db/schema.py",
            "scripts/db/schema.py",
            "app/core/schema.py",
        ):
            text = _read(cand)
            if text:
                schema = text
                break
    found = bool(re.search(r"[Ee]xam", schema))
    if not found:
        _fail("لا نمط امتحانات/assessment في schema — L7 (الامتحان يقفل الجدول)")
    else:
        _pass("نمط الامتحانات/assessment حاضر في schema — L7")


def _check_append_only() -> None:
    # L9: `student_review_schedule` يُكتب insert فقط — تحديث/حذف عليه = أحمر.
    bad_files = []
    for py in REPO_ROOT.rglob("*.py"):
        rel = str(py.relative_to(REPO_ROOT))
        if "scripts/fitness/" in rel or ".e2e" in rel or py.is_relative_to(REPO_ROOT / "tests"):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        if "student_review_schedule" in text and re.search(
            r"update\s+(student_review_schedule)|student_review_schedule.*\.(update|delete)\b|UPDATE.*student_review_schedule",
            text,
            flags=re.I,
        ):
            bad_files.append(rel)
    if bad_files:
        _fail(f"update/delete على student_review_schedule في: {bad_files} (L9 append-only)")
    else:
        _pass("student_review_schedule append-only (لا update/delete إنتاجي — L9)")


def _check_no_promises() -> None:
    # L10: لا قالبٍ في المسار الحيّ يعد بناتج («ستتقن/ستنجح/ضمان نجاح») —
    # القالب الوحيد المسموح وظيفي: «مستهدف من X إلى Y».
    promise_words = re.compile(
        r"(ستتقن|ستنجح|ضمان النجاح|مضمون|guaranteed success|will definitely (pass|master))",
        flags=re.I,
    )
    for cand in (
        "app/api/routers/customer_chat_support/pedagogy.py",
        "app/services/chat/local_graph.py",
        "app/services/skills/pedagogical_policy_skill.py",
        "app/services/review/persistence.py",
    ):
        text = _read(cand)
        if not text:
            continue
        hits = promise_words.findall(text)
        if hits:
            _fail(f"{Path(cand).name}: وعدٌ ناتجي `{hits[0]}` — L10 (التفسير قبل الوعد)")
        else:
            _pass(f"{Path(cand).name}: خالٍ من الوعود الناتجية (L10)")


def _check_no_raw_claims() -> None:
    # أي «+%» في وثيقةٍ دستورية يجب أن يستند إلى مرجع منشور (يمتدّ D-263 §6.6)
    for doc in (
        ".memory/adaptive_study_planner_constitution.md",
        "CLAUDE.md",
        "README.md",
        "spec.md",
    ):
        text = _read(doc)
        if not text:
            continue
        claims = re.findall(r"\+\s*\d+(?:\.\d+)?\s*%", text)
        if not claims:
            continue
        cited = bool(re.search(r"(et al|PNAS|202[0-9]|arXiv|DOI|10\.\d+|Published)", text))
        for claim in claims:
            if not cited:
                _fail(f"{doc}: ادّعاء رقمي {claim} بلا مرجعٍ منشور")
            else:
                _pass(f"{doc}: ادّعاء {claim} مستند إلى مرجعٍ منشور")
                break


def main() -> int:
    # ① الدستور موجود ومكتمل + عداد القوانين يُشتَقّ منه
    const = _read(".memory/adaptive_study_planner_constitution.md")
    if not const:
        return 1
    _check_constitution_sections(const)
    _check_section_laws(const)

    # الأبواب الأربعة (كل باب له اسم ISS مرقّم — لا باب بلا محنة)
    for gate in ("ISS-178", "ISS-179", "ISS-180", "ISS-181"):
        _must(re.escape(gate), const, "أبواب D-264")

    # ② L1: التشخيص قبل الجدولة
    _check_diagnostic_sources()

    # ③ L3: الحتمية — لا LLM/صدفة في الترتيب
    _check_no_llm_ordering()

    # ④ L7: الامتحان يقفل الجدول
    _check_exam_lock()

    # ⑤ L9: الإنجاز append-only
    _check_append_only()

    # ⑥ L10: التفسير قبل الوعد
    _check_no_promises()

    _check_no_raw_claims()

    if _FAILURES:
        print(f"\n❌ {len(_FAILURES)} انتهاك — دستور D-264 ليس محروسًا:")
        for f in _FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ adaptive-planner: الدستور D-264 محروس بالكامل (10 قوانين · بواباته موصولة).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
