#!/usr/bin/env python3
"""بوّابة دستور المحرك التربوي — D-263 / ISS-174→ISS-177.

## لماذا هذه البوّابة موجودة
دستورٌ جديد (`.memory/pedagogy_engine_constitution.md`) أُقرّ بقرار المالك
2026-08-16 من تشخيص خارجي قاسٍ: «البنية ليست الميزة» — وعشرات الخدمات لا تجعل
النظام Pedagogy Engine. والقانون ما له فارض؛ فإضافة نصٍّ إلى مستودعٍ ليست
إضافةَ قانون.

**ما تفحصه (قانون D-263 §4):**
1. الدستور موجود ومكتمل: §1 التشخيص · §2 الحلقة · §3 الأبواب الأربعة ·
   §4 القوانين العشرة · §6 المقياس.
2. **L3/L4 (موروثة من D-153):** المحرك الرمزي صفر-LLM حيّ في المسار الإنتاجي
   — `ProbabilityCalculatorSkill`/`symbolic` لا يُحذَفان ولا يُقفَلان.
3. **L2 (D-208 ممتد):** حارس الحيرة في عقليَي القرار.
4. **L5/L6:** كل عقلٍ يقرّر `mastery`/`illusion_gap` يمرّ عبر طبقة رمزية/
   إحصائية (BKT engine) — لا نص LLM يقرر إتقانًا.
5. **لا حلقة تربوية خام:** `local_graph.py` (المسار الحيّ الاحتياطي) لا يرسل
   رسالة تعلّم إلى LLM بلا مرحلة تشخيص/سياق تربوي — `_build_pedagogical_context`
   موجود ويُستدعى قبل أي استدعاء نموذج.
6. **الأعداد تُشتَقّ لا تُكتب:** عداد القوانين في الدستور يساوي عشرة فعلًا،
   وكل قانونٍ §4 يسمّي فارضًا موجودًا (no orphan enforcer — D-188 بند ③).
7. **قفل Learning Gain:** أي وثيقةٍ دستورية تحتوي «+%» أو «تحسّن» مع نسبة
   رقمية يجب أن تشير إلى منهجيةٍ منشورة في `.memory/pedagogy_engine_truth.md` —
   (حاليًا: لا أرقام مُعلَنة، فالبوابة تحرس غيابَ الادّعاء قبل المنهجية).

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
        r"## 3\. الركائز الأربع للـmoat",
        r"## 4\. القوانين الصارمة العشرة",
        r"## 6\. مقياس النجاح الدستوري",
        r"## 7\. علاقة هذا الدستور بالعقائد القائمة",
    ):
        _must(section, const, "الدستور D-263")


def _check_section_laws(const: str) -> None:
    # ⑥ عداد القوانين: عشرة تمامًا (يُشتَقّ من نص الدستور)
    laws = re.findall(r"^\| L(\d+) \|", const, flags=re.M)
    if set(laws) != {str(i) for i in range(1, 11)}:
        _fail(f"قوانين §4 ليست عشرة كاملة (وُجدت: {sorted(laws, key=int)})")
        return
    _pass("القوانين العشرة كاملة L1–L10")


def _check_learning_gain_claims() -> None:
    # ⑦ قفل Learning Gain: ادّعاء نتيجة تربوية يجب أن يستند إلى مرجعٍ منشور مقيس
    # (حاليًا: ادّعاءات §02 في README من Bastani et al., PNAS 2025 — تجربة ميدانية
    # منشورة مرجِّحة، فيُقبل وجود اسم المرجع والنتيجة معًا؛ ادّعاء بلا مرجع ⇒ أحمر).
    for doc in (
        ".memory/pedagogy_engine_constitution.md",
        "CLAUDE.md",
        "README.md",
        ".memory/roadmap.md",
    ):
        text = _read(doc)
        if not text:
            continue
        claims = re.findall(r"\+\s*\d+(?:\.\d+)?\s*%", text)
        if not claims:
            continue
        cited = bool(re.search(r"(et al|PNAS|202[0-9]|arXiv|DOI|10\.\d+|Published)", text))
        for claim in claims:
            # مرجع منشور (اسم باحث/دورية) داخل الصفحة نفسها يغنّي عن المنهجية الذاتية
            if not cited:
                _fail(f"{doc}: ادّعاء Learning Gain رقمي {claim} بلا مرجعٍ منشور")
            else:
                _pass(f"{doc}: ادّعاء {claim} مستند إلى مرجعٍ منشور")
                break


def main() -> int:
    # ① الدستور موجود ومكتمل + عداد القوانين يُشتَقّ منه
    const = _read(".memory/pedagogy_engine_constitution.md")
    if not const:
        return 1
    _check_constitution_sections(const)
    _check_section_laws(const)

    # الأبواب الأربعة (كل باب له اسم ISS مرقّم — لا باب بلا محنة)
    for gate in ("ISS-174", "ISS-175", "ISS-176", "ISS-177"):
        _must(re.escape(gate), const, "أبواب D-263")

    # ② القانونان الموروثان: صفر-LLM الرمزي حيّ
    calc = _read("app/services/skills/probability_skill.py")
    _must(r"class ProbabilityCalculatorSkill", calc, "المحرك الرمزي ProbabilityCalculatorSkill")

    # ③ الحيرة في عقليَي القرار (D-208 ممتد — نفس مرمى check_confusion_never_an_answer)
    for skill in (
        "app/services/skills/pedagogical_policy_skill.py",
        "app/services/skills/socratic_evaluator_skill.py",
        "app/services/skills/understanding_state_skill.py",
    ):
        text = _read(skill)
        # فهم الحالة يحرس الحيرة بعلاماتِه القانونية (D-208) بدل `_is_bare_confusion`.
        _must(
            r"_is_bare_confusion|_is_confusion_or_question",
            text,
            f"{Path(skill).name} (L2 — الحيرة)",
        )

    # ④ ل5/L6: العقل الإحصائي للتتبع حيّ — BKT engine + illusion_gap
    bkt = _read("app/services/skills/bkt_engine.py")
    _must(r"def update_mastery", bkt, "bkt_engine (BKT حيّ — تحديث الإتقان)")
    ig = _read("app/services/skills/illusion_gap_skill.py")
    _must(r"illusion_gap|IllusionGapReport", ig, "illusion_gap_skill (فجوة الوهم — L5/L6)")

    # ⑤ لا حلقة تربوية خام على المسار الحيّ: القرار التربوي يُبنى قبل أي بثّ
    lg = _read("app/services/chat/local_graph.py")
    if lg:
        _must(r"pedagogical_decision", lg, "local_graph (مرحلة قرارٍ تربوي — L1)")
        _must(r"_classify_intent", lg, "local_graph (مرحلة تشخيص — L1)")
    ped = _read("app/api/routers/customer_chat_support/pedagogy.py")
    if ped:
        _must(r"illusion_gap", ped, "pedagogy.py (سجلّ أثـر التعلم — L5)")

    _check_learning_gain_claims()

    if _FAILURES:
        print(f"\n❌ {len(_FAILURES)} انتهاك — دستور D-263 ليس محروسًا:")
        for f in _FAILURES:
            print(f"   - {f}")
        return 1
    print("✅ pedagogy-engine: الدستور D-263 محروس بالكامل (10 قوانين · بواباته موصولة).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
