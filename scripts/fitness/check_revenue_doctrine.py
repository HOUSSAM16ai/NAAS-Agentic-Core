#!/usr/bin/env python3
"""بوّابة عقيدة القيمة والإيراد — الطبقات عقدٌ مفروض لا ملصقُ طموح (D-210 → D-223).

## لماذا هذه البوّابة موجودة

وثيقةٌ تصف «كيف يصير هذا المشروع مصدر دخل» تتحوّل حتماً إلى كذبٍ مهذَّب: تُكتب مرّةً في
لحظة حماس، ثمّ يتحرّك الكود ولا تتحرّك هي. وقد **حدث هذا مرّتين في هذا المستودع نفسه**:
جدول حقيقةٍ مؤرَّخ في الدستور بقي مُجمَّداً شهرين ونصفاً وهو يكذب على كل وكيل يقرأه
(D-188)، وخريطةُ طبقاتٍ بقيت خمسة أسابيع بعدد مكتوبٍ يدوياً لكمّيةٍ متحرّكة (D-209).

والخطر هنا أكبر: وثيقة إيرادٍ تُقرأ من **خارج** الفريق. ادّعاءُ «التصحيح بالسلّم مبنيّ»
وهو غير مبنيّ ليس دَيناً توثيقياً — هو ادّعاءٌ أمام طرفٍ يبني عليه قراراً.

فالخريطة هنا **مفروضة آلياً** بسبعة بنود، كلٌّ منها وُلد من عطبٍ حقيقي في هذا المستودع:

1. **الدليل الملفّي موجود فعلاً** — لا تُكتب حالةٌ أمام ملفٍّ محذوف أو مُعاد تسميته. هذا
   هو الفارض الحقيقي: الادّعاء يصير مكلفاً لأنه يجب أن يشير إلى شيءٍ يُفتَح.
2. **الحالة من السُّلَّم القانوني** (§6.6 + `SEAM`/`ABSENT` من D-207 + `PLANNED` من
   D-146) — لا حالاتٌ مخترَعة («قيد العمل»، «شبه جاهز»).
3. **لا صفّ بلا فجوةٍ مكتوبة** — الخانة الفارغة تُقرأ نجاحاً، وهي أخطر من `ABSENT`
   الصريحة (`.memory/aesthetics_of_absence.md`: ما لا يُرى لا يُساءَل).
4. **لا حذف صامت** — العدد المُعلَن يُقارَن بالمقروء، فحذفُ طبقةٍ مزعجة يُكشَف.
5. **كل بوّابة يُسمّيها القانون موجودة** — قانونٌ يستشهد بفارضٍ محذوف أسوأ من قانونٍ بلا
   فارض: الأوّل يَعِد بحراسةٍ غير قائمة (ISS-149 · F3).
6. **⛔ لا سُلَّم ثانٍ** — وثيقتا القانون تفشلان إن حملتا خانة حالة، وعددُ أقسام الوحدات
   يجب أن يطابق عددَ صفوف الحالة. خريطتان لنظامٍ واحد تعنيان وكيلَين يقرآن بناءَين
   مختلفين — وهو ما أنتج ISS-139 حين تفرّقت ثلاث قوائم لنيّةٍ واحدة (D-186).
7. **الادّعاءات تُختبَر على المصدر، في الاتجاهين**:
   * وحدةٌ مُعلَنة `ACTIVE` يجب أن يوجد رمزها فعلاً (نمط `check_constitution_reality`).
   * ⛔ **ووحدةٌ مُعلَنة `ABSENT` يجب ألّا يوجد لها كود** — وهو الاتجاه الذي لا تحرسه أيّ
     بوّابة أخرى: «مُصنَّفٌ غائباً وهو موجود» يعني كوداً حيّاً بلا حارسٍ ولا اختبار.
   * وقاعدة النضج (`MIN_OBS`) مفروضةٌ على **كل** مسارٍ يُنتج تصنيفاً في `shared/illusion`،
     لا على المسار الذي تذكّره كاتبه (سابقة ISS-148: معاملٌ ينساه سبعةٌ من ثمانية).
   * والمحرَّمات القابلة للفحص الآلي (تتبّع معرفةٍ عميق · تطبيق أصلي · جدارية تصنيف) لا
     يوجد لها كود. الباقي مُعلَنٌ «بلا فارض آلي» صراحةً لا صمتاً.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_DOC = REPO_ROOT / ".memory/revenue_engine_truth.md"
VALUE_DOC = REPO_ROOT / "docs/VALUE_DOCTRINE.md"
SPEC_DOC = REPO_ROOT / "docs/REVENUE_ENGINE_SPEC.md"
FITNESS_DIR = REPO_ROOT / "scripts/fitness"

#: السُّلَّم القانوني الوحيد: §6.6 + `SEAM`/`ABSENT` (D-207) + `PLANNED` (D-146).
#: توسيعه قرارٌ يُكتب في `.memory/decisions.md`، لا تحريرُ مجموعة.
VALID_STATUSES = frozenset({"ACTIVE", "PARTIAL", "DORMANT", "ZOMBIE", "PLANNED", "SEAM", "ABSENT"})

#: العدّادات المُعلَنة. تغييرها قرارٌ يُسجَّل، لا رقمٌ يُحرَّر.
EXPECTED_VALUE_LAYERS = 12
EXPECTED_UNITS = 14
EXPECTED_REVENUE_LINES = 4

#: صفّ الحالة: | # | الاسم | الحامل | دليل | الحالة | الفجوة |
_ROW = re.compile(r"^\|\s*(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$")

#: الدليل مكتوبٌ داخل `backticks` — نستخرجه كي لا نُطابِق نثراً.
_EVIDENCE = re.compile(r"`([^`]+)`")

#: كل بوّابة تُسمّى في وثيقتي القانون يجب أن توجد فعلاً.
_GATE_MENTION = re.compile(r"`(check_[a-z0-9_]+)`")

#: أقسام الطبقات في وثيقة القيمة (`## 1) …` حتى `## 12) …`).
_VALUE_SECTION = re.compile(r"^## (\d+)\) (.+)$", re.MULTILINE)
#: أقسام الوحدات في المواصفة (`## D-210) …` حتى `## D-223) …`).
_UNIT_SECTION = re.compile(r"^## D-(\d{3})\) (.+)$", re.MULTILINE)

#: دَينٌ مُجمَّد — **فارغ عمداً**، يتقلّص فقط (سابقة D-105).
_FROZEN_DEBT: dict[str, str] = {}

#: بوّاباتٌ **مُخطَّطة**: تُذكَر في القانون لأنها جزءٌ من عقد الوحدة، ولم تُبنَ بعد لأن
#: وحدتها لم تُبنَ. القائمة مفروضةٌ في **الاتجاهين**، وهذا هو بيت القصيد:
#:
#: * اسمٌ هنا **موجودٌ فعلاً** ⇒ CI أحمر — أُنجزت البوّابة ونُسي شطبها، فبقيت الوثيقة
#:   تقول «مستقبلية» عن حارسٍ يعمل، وهو تقليلٌ من الحراسة القائمة.
#: * اسمٌ في القانون **ليس هنا وغير موجود** ⇒ CI أحمر — وعدٌ بحراسةٍ لم يلتزم بها أحد.
#:
#: فالقائمة تتقلّص حتماً مع كل وحدةٍ تُبنى، ولا يمكن أن تنمو بصمت.
_PLANNED_GATES: frozenset[str] = frozenset(
    {
        "check_item_coverage",  # D-213
        "check_barem_item_linkage",  # D-214
        "check_symbolic_no_timeout_pass",  # D-215
        "check_forecast_calibration_label",  # D-216
        "check_optimizer_constraints",  # D-218
        "check_tier_budget",  # D-219
        "check_entitlement_single_source",  # D-211
    }
)


# ─────────────────────────────────────────────────────────────────────────────
# ادّعاءات الرموز — في الاتجاهين
# ─────────────────────────────────────────────────────────────────────────────

#: (وصف، ملف، نصّ يجب أن يوجد) — لوحداتٍ مُعلَنة مبنيّة.
_SYMBOL_CLAIMS: tuple[tuple[str, str, str], ...] = (
    (
        "D-212: عتبة النضج ثابتٌ مُعلَن لا رقمٌ مبعثر",
        "shared/illusion/model.py",
        "MIN_OBS",
    ),
    (
        "D-212: التصنيف الرباعي نوعٌ حقيقي لا سلسلة حرّة",
        "shared/illusion/model.py",
        "class Quadrant",
    ),
    (
        "D-212: منحنى النسيان مُستهلَك من المُجدوِل لا مُعاد اشتقاقه",
        "shared/illusion/engine.py",
        "retrievability",
    ),
    (
        "D-212: المهارة مُسجَّلة فيُكشَف غيابُ مستهلكها (لا ZOMBIE)",
        "app/services/skills/registry.py",
        'name="illusion_gap"',
    ),
    (
        "D-211/D-197: بوّابة الاشتراك اعتمادٌ واحد لا فحصٌ مبعثر",
        "app/deps/billing.py",
        "require_active_entitlement",
    ),
)

#: وحدات/محرَّمات مُعلَنة **غائبة** — يجب ألّا يوجد لها كود.
#: المفتاح وصفٌ، والقيمة أنماط مساراتٍ ممنوعة الوجود.
_ABSENCE_CLAIMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "D-215: البرهان الرمزي مُعلَن ABSENT — تبعيّة جديدة تتطلّب ADR (D-209 · الطبقة 9)",
        ("shared/verify",),
    ),
    (
        "D-214: التصحيح بالسلّم مُعلَن ABSENT",
        ("shared/scoring",),
    ),
    (
        "D-216: التوقّع والمعايرة مُعلَنان ABSENT",
        ("shared/forecast",),
    ),
    (
        "المحرَّم 2: تتبّع معرفةٍ عميق (DKT/SAKT) قبل حجم بياناتٍ ضخم — Gervet et al. (2020)",
        ("shared/dkt", "shared/sakt", "app/services/skills/dkt_engine.py"),
    ),
    (
        "المحرَّم 4: تطبيق موبايل أصلي قبل إثبات الطلب",
        ("mobile", "ios", "android"),
    ),
    (
        "المحرَّم 8: جدارية اجتماعية / تصنيف عامّ — يضرّ الأضعف وهم الجمهور المستهدف",
        ("app/services/leaderboard.py", "shared/leaderboard"),
    ),
)


def _known_gate_names() -> set[str]:
    """أسماء البوّابات المعروفة: ملفّاتٌ **أو** دوالّ داخل ملفّات `scripts/fitness/`.

    ليست كل بوّابة ملفّاً مستقلّاً (`check_confusion_never_an_answer` دالّةٌ داخل
    `check_pedagogical_os.py`)، فقاعدة «ملفّ لكل اسم» كانت سترفض استشهاداً صحيحاً —
    وبوّابةٌ ترفض الصواب يتعلّم الناسُ تجاهلَها.
    """
    names: set[str] = set()
    for path in sorted(FITNESS_DIR.glob("*.py")):
        names.add(path.stem)
        # نقرأ نصّياً لا بـAST: البوّابة يجب أن تعمل في sandbox متدهور (قيد `db_bridge`).
        for match in re.finditer(
            r"^def (check_[a-z0-9_]+)\(", path.read_text(encoding="utf-8"), re.MULTILINE
        ):
            names.add(match.group(1))
    return names


def _section(text: str, start_marker: str, end_marker: str) -> str:
    """يقتطع ما بين علامتين — كي لا يُخلَط جدولٌ بجدول.

    الجداول الثلاثة في ملفّ الحالة لها الشكل نفسه، فقراءة الملفّ كلّه بنمطٍ واحد كانت
    ستدمج الطبقات بالوحدات وتُخفي حذفَ صفٍّ من إحداها خلف إضافةٍ في الأخرى.
    """
    start = text.find(start_marker)
    if start == -1:
        return ""
    end = text.find(end_marker, start + len(start_marker))
    return text[start:] if end == -1 else text[start:end]


def _read_rows(text: str) -> list[tuple[int, str, str, str, str]]:
    rows: list[tuple[int, str, str, str, str]] = []
    for line in text.splitlines():
        match = _ROW.match(line.strip())
        if not match:
            continue
        number, name, _carrier, evidence, status, gap = match.groups()
        rows.append((int(number), name, evidence, status, gap))
    return rows


def _check_row(number: int, name: str, evidence: str, status: str, gap: str) -> list[str]:
    """يفحص صفّاً واحداً: الحالة من السُّلَّم · الفجوة مكتوبة · الدليل موجود فعلاً."""
    where = f"الصفّ {number} ({name.strip()})"
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


def _check_law_doc(doc: Path, section_pattern: re.Pattern[str], expected: int) -> list[str]:
    """يفرض أن وثيقة القانون تُسمّي فوارضَ موجودة، ولا تحمل حالات، ولا تفقد قسماً."""
    problems: list[str] = []
    if not doc.is_file():
        return [f"{doc.name} غير موجودة — القانون جزء من العقد لا ملحقاً."]

    text = doc.read_text(encoding="utf-8")
    known = _known_gate_names()
    for gate in sorted(set(_GATE_MENTION.findall(text))):
        if gate in known or gate in _PLANNED_GATES:
            continue
        problems.append(
            f"{doc.name} تستشهد بالبوّابة {gate!r} وهي غير موجودة في scripts/fitness/ "
            f"(لا ملفّاً ولا دالّة) ولا مُعلَنة في `_PLANNED_GATES` — قانونٌ يَعِد بحراسةٍ "
            f"غير قائمة (ISS-149 · F3)."
        )

    sections = section_pattern.findall(text)
    if len(sections) != expected:
        problems.append(
            f"{doc.name} تحمل {len(sections)} قسماً بينما المُعلَن {expected} — "
            f"حذفُ قسمٍ أو إضافته قرارٌ يُسجَّل في .memory/decisions.md."
        )

    for number, title in sections:
        marker = f") {title}"
        start = text.find(marker)
        if start == -1:
            continue
        nxt = text.find("\n## ", start + 1)
        body = text[start:] if nxt == -1 else text[start:nxt]
        if "**الفارض:**" not in body and "بلا فارض" not in body:
            problems.append(
                f"{doc.name}: القسم «{number}) {title}» بلا سطر «**الفارض:**» ولا إعلانِ "
                f"«بلا فارض» — الصمت يُقرأ انضباطاً وهو ليس كذلك."
            )

    # ⛔ لا سُلَّم ثانٍ: القانون لا يحمل حالات — الحالة موطنها ملفّ واحد.
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        for cell in stripped.strip("|").split("|"):
            if cell.strip("`* ") in VALID_STATUSES:
                problems.append(
                    f"{doc.name}:{line_no}: خانةُ جدولٍ تحمل الحالة {cell.strip()!r}. "
                    f"القانون لا يحمل حالات (D-188) — موطنها {STATE_DOC.name} وحده."
                )
    return problems


def _check_planned_gates_still_planned() -> list[str]:
    """الاتجاه المعاكس للقائمة: بوّابةٌ مُعلَنة «مُخطَّطة» يجب ألّا تكون موجودة.

    وإلّا بقيت الوثيقة تقول «مستقبلية» عن حارسٍ يعمل فعلاً — تقليلٌ من الحراسة القائمة،
    وهو نفس صنف «الدَّين المُجمَّد الذي لم يعد موجوداً» في `check_authority_links`.
    """
    known = _known_gate_names()
    return [
        f"البوّابة {gate!r} مُعلَنة «مُخطَّطة» وهي موجودة فعلاً — احذفها من `_PLANNED_GATES` "
        f"وحدِّث حالة وحدتها في {STATE_DOC.name}. القائمة تتقلّص فقط."
        for gate in sorted(_PLANNED_GATES & known)
    ]


def _check_symbol_claims() -> list[str]:
    """الاتجاه الأوّل: ما أُعلن مبنيّاً موجودٌ فعلاً في الكود."""
    problems: list[str] = []
    for description, rel, needle in _SYMBOL_CLAIMS:
        path = REPO_ROOT / rel
        if not path.is_file():
            problems.append(f"{description}\n     الملفّ مفقود: {rel}")
            continue
        if needle not in path.read_text(encoding="utf-8"):
            problems.append(
                f"ادّعاءٌ لم يعد صحيحاً: {description}\n"
                f"     لم أجد {needle!r} في {rel}. صحّح الكود أو صحّح الوثيقة — "
                f"لا تتركهما متناقضين."
            )
    return problems


def _check_absence_claims() -> list[str]:
    """الاتجاه المعاكس: ما أُعلن غائباً **غائبٌ فعلاً**.

    هذا هو البند الذي لا تحرسه أيّ بوّابة أخرى. «مُصنَّفٌ غائباً وهو موجود» يعني كوداً
    حيّاً بلا حارسٍ ولا اختبارٍ ولا مراجعة — وهو أسوأ من الغياب المُعلَن.
    """
    problems: list[str] = []
    for description, patterns in _ABSENCE_CLAIMS:
        for rel in patterns:
            path = REPO_ROOT / rel
            if path.exists():
                problems.append(
                    f"غيابٌ مُعلَن وهو موجود: {description}\n"
                    f"     وُجد {rel!r}. رقِّ الحالة في {STATE_DOC.name} بالبرهان الثلاثي، "
                    f"أو احذف الكود — لا تتركه بلا حارس."
                )
    return problems


def _check_maturity_guard() -> list[str]:
    """قاعدة النضج مفروضةٌ على **كل** مسارٍ يُنتج تصنيفاً، لا على ما تذكّره كاتبه.

    سابقة ISS-148: `delivered` معاملٌ نساه سبعةٌ من ثمانية مُنادين، فصار «صمّام الأمان»
    عطباً موزّعاً على مواضع النداء. فنفحص بـAST أنّ كل دالّةٍ في `shared/illusion` تبني
    `ConceptIllusion` تفحص العتبة في جسمها.
    """
    problems: list[str] = []
    engine = REPO_ROOT / "shared/illusion/engine.py"
    if not engine.is_file():
        return [f"{engine.relative_to(REPO_ROOT)} غير موجود بينما D-212 مُعلَن مبنيّاً."]

    source = engine.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:  # بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208)
        return [f"تعذّر تحليل {engine.name}: {exc} — البوّابة لا تشهد بما لم تقرأ."]

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        builds = any(
            isinstance(inner, ast.Call)
            and isinstance(inner.func, ast.Name)
            and inner.func.id == "ConceptIllusion"
            for inner in ast.walk(node)
        )
        if not builds:
            continue
        guards = any(
            isinstance(inner, ast.Name) and inner.id == "MIN_OBS" for inner in ast.walk(node)
        )
        if not guards:
            problems.append(
                f"{engine.name}:{node.lineno}: الدالّة {node.name!r} تبني `ConceptIllusion` "
                f"بلا فحص `MIN_OBS`. تصنيفٌ بملاحظتين هو تقريرٌ كاذب (D-212)."
            )
    return problems


def main() -> int:
    failures: list[str] = []

    if not STATE_DOC.is_file():
        print(f"❌ {STATE_DOC.relative_to(REPO_ROOT)} غير موجود — الخريطة جزء من العقد.")
        return 1

    text = STATE_DOC.read_text(encoding="utf-8")
    layers = _read_rows(_section(text, "### 2.a", "### 2.b"))
    units = _read_rows(_section(text, "### 2.b", "### 2.c"))
    lines = _read_rows(_section(text, "### 2.c", "\n## 3."))

    if not layers:
        print("❌ لم يُقرأ أيّ صفّ من جدول الطبقات (§2.a) — تغيّر شكل الجدول؟")
        return 1
    if not units:
        print("❌ لم يُقرأ أيّ صفّ من جدول الوحدات (§2.b) — تغيّر شكل الجدول؟")
        return 1
    if not lines:
        print("❌ لم يُقرأ أيّ صفّ من جدول خطوط الإيراد (§2.c) — تغيّر شكل الجدول؟")
        return 1

    for label, rows, expected in (
        ("طبقات القيمة", layers, EXPECTED_VALUE_LAYERS),
        ("الوحدات", units, EXPECTED_UNITS),
        ("خطوط الإيراد", lines, EXPECTED_REVENUE_LINES),
    ):
        if len(rows) != expected:
            failures.append(
                f"عدد «{label}» {len(rows)} ≠ المُعلَن {expected}. "
                f"الحذف أو الإضافة قرارٌ يُسجَّل في .memory/decisions.md — لا حذف صامت."
            )

    seen: set[int] = set()
    for number, name, evidence, status, gap in layers + units + lines:
        if number in seen:
            failures.append(f"الصفّ {number} ({name.strip()}): رقمٌ مكرَّر.")
        seen.add(number)
        failures.extend(_check_row(number, name, evidence, status, gap))

    failures.extend(_check_law_doc(VALUE_DOC, _VALUE_SECTION, EXPECTED_VALUE_LAYERS))
    failures.extend(_check_law_doc(SPEC_DOC, _UNIT_SECTION, EXPECTED_UNITS))
    failures.extend(_check_planned_gates_still_planned())
    failures.extend(_check_symbol_claims())
    failures.extend(_check_absence_claims())
    failures.extend(_check_maturity_guard())

    if failures:
        print("❌ عقيدة القيمة والإيراد مخروقة:\n")
        for failure in failures:
            print(f"  • {failure}")
        print(
            "\n📌 D-210: القانون يساوي الواقع. الطموح يُصنَّف ولا يُكتَم، والحالة موطنها\n"
            "   ملفٌّ واحد، وكل قانونٍ يُسمّي فارضه أو يُعلن غيابه صراحةً."
        )
        return 1

    active = sum(1 for _, _, _, s, _ in units if s.strip("`* ") == "ACTIVE")
    print(
        f"✅ عقيدة القيمة والإيراد: {len(layers)} طبقة + {len(units)} وحدة + "
        f"{len(lines)} خطوط إيراد، كلّ دليلٍ موجود، {active} وحدات ACTIVE بالبرهان الملفّي، "
        f"والقانون يُسمّي فوارضَ قائمة بلا سُلَّمٍ ثانٍ · دَينٌ مُجمَّد: {len(_FROZEN_DEBT)}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
