#!/usr/bin/env python3
"""ISS-149 — مؤشّر الفهم برهانٌ على آلية، لا اسمُ المفهوم نفسه.

## لماذا هذه البوّابة موجودة

طالبٌ سأل: «كيف نفرق بين **البسط** و المقام؟». وكان `favorable_cases` يُصرِّح أنّ
مؤشّر فهمه هو الاسم المفرد `"البسط"`. فطابق المؤشّرُ **سؤالَ الطالب نفسه**، وقرّرت
مصفوفةُ التصعيد أنّه أتقن المفهوم، فردّت على «لم أفهم؟» التالية بـ«أحسنت ✅ — يبدو
أنك أمسكت الفكرة»، وكتبت في نموذجه المعرفي `state="understood"` / `evidence="verified"`.

الطالب **سأل** عن المصطلح فحُسِب أنّه **برهنه**. وهذه دائرةٌ مغلقة: من يسأل عن شيء
يذكر اسمه بالضرورة، فاسمُ المفهوم أسوأ مؤشّرٍ ممكن على فهمه.

القاعدة كانت مفهومةً ضمناً ومكتوبةً في عقد المهارة نفسه («آلية، لا «فهمت»»)،
ومُطبَّقةً في **كل** المؤشّرات إلّا اثنين — وبلا فارضٍ آلي. وقانونٌ بلا فارض يُنسى
في أوّل PR عاجل (`ENGINEERING_DOCTRINE.md`، «الثمن الأول»).

## ما تفرضه

1. **كل `evidence_marker` عبارة** (كلمتان فأكثر). اسمٌ مفرد يُطابَق في كل ذكرٍ
   للمصطلح، والذكرُ ليس برهاناً.
2. **لا تقاطع مع علامات النيّة** في `shared/intent`. مؤشّرٌ يساوي علامةَ نيّةٍ يعني
   أنّ **سؤالاً** يُقرأ برهاناً — وهو الجذر بعينه.
3. **مسار القرار يستشير الحارس**: `_has_understanding_evidence` تقرأ رسالة الحاضر
   وتُبطِل البرهان على الحيرة والسؤال. (يفحصها أيضاً `check_pedagogical_os`
   من زاوية «الحيرة ليست إجابة»؛ هنا من زاوية «ما الذي يصلح برهاناً».)

تقرأ بـ**AST** لا بـgrep: قائمةٌ في تعليق ليست عقداً.

الدَّين المُجمَّد **فارغ** ويتقلّص فقط (سابقة D-105/D-187): إدخالٌ جديد يُفشِل،
وإدخالٌ نُظِّف ولم يُحذَف يُفشِل أيضاً — فلا يصير الاستثناء إعفاءً دائماً.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: الملفّات التي تُصرِّح مؤشّرات الفهم (كلاهما يُغذّي قراراً يكتب في الحالة الدائمة).
_SOURCES: tuple[str, ...] = (
    "app/services/skills/semantic_property_skill.py",
    "app/services/skills/understanding_state_skill.py",
)

#: مسار القرار الذي يستهلك المؤشّرات.
_DECISION_SOURCE = "app/services/skills/pedagogical_escalation_skill.py"

#: دَينٌ مُجمَّد — **فارغ عمداً**. المفتاح `"<file>::<marker>"` والقيمة سببٌ منطوق.
#: يتقلّص فقط: أيّ إضافة هنا تحتاج تبريراً في `.memory/decisions.md`.
_FROZEN_DEBT: dict[str, str] = {}

_MIN_WORDS = 2


def _marker_tuples(path: Path) -> list[tuple[str, int]]:
    """كل قيمة نصّية داخل `evidence_markers=(...)` مع رقم سطرها — بـAST."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.keyword) or node.arg != "evidence_markers":
            continue
        if not isinstance(node.value, ast.Tuple):
            continue
        for element in node.value.elts:
            if isinstance(element, ast.Constant) and isinstance(element.value, str):
                found.append((element.value, element.lineno))
    return found


def _intent_markers() -> set[str]:
    """كل علامات النيّة القانونية، مُطبَّعة (المصدر الواحد — D-186)."""
    sys.path.insert(0, str(REPO_ROOT))
    from shared.intent import all_intents, markers_for, normalize

    return {normalize(m) for intent in all_intents() for m in markers_for(intent)}


def main() -> int:
    failures = 0
    seen_debt: set[str] = set()
    sys.path.insert(0, str(REPO_ROOT))
    from shared.intent import normalize

    intent_markers = _intent_markers()

    for rel in _SOURCES:
        path = REPO_ROOT / rel
        if not path.exists():
            print(f"❌ {rel}: الملفّ غير موجود — حدِّث `_SOURCES`.")
            failures += 1
            continue
        for marker, lineno in _marker_tuples(path):
            key = f"{rel}::{marker}"
            if key in _FROZEN_DEBT:
                seen_debt.add(key)
                continue
            if len(marker.split()) < _MIN_WORDS:
                print(
                    f"❌ {rel}:{lineno}: مؤشّر الفهم {marker!r} كلمةٌ واحدة.\n"
                    f"   اسمُ المفهوم يَرِد في **السؤال عنه** بقدر ما يَرِد في برهانه —\n"
                    f"   فالمؤشّر عبارةٌ تصف الآلية («البسط هو عدد الحالات»)، لا الاسم."
                )
                failures += 1
                continue
            if normalize(marker) in intent_markers:
                print(
                    f"❌ {rel}:{lineno}: مؤشّر الفهم {marker!r} هو نفسه علامةُ نيّة في\n"
                    f"   `shared/intent` — أي أنّ **سؤالاً** سيُقرأ برهانَ إتقان (ISS-149)."
                )
                failures += 1

    # ── الدَّين يتقلّص في الاتجاهين (D-189) ──────────────────────────────────
    for key in sorted(set(_FROZEN_DEBT) - seen_debt):
        print(f"❌ دَينٌ مُجمَّد لم يعد موجوداً: {key!r} — احذفه من `_FROZEN_DEBT`.")
        failures += 1

    # ── مسار القرار يستشير الحارس ────────────────────────────────────────────
    decision = (REPO_ROOT / _DECISION_SOURCE).read_text(encoding="utf-8")
    body = decision.split("def _has_understanding_evidence", 1)[-1].split("\n    def ", 1)[0]
    for symbol, why in (
        ("_current_student_text", "البرهان من رسالة الحاضر لا من نافذة الماضي"),
        ("_is_confusion_signal", "الحيرة المُعلَنة تُبطل البرهان"),
        ("_is_question_not_answer", "السؤال عن مصطلح ليس برهان إتقانه"),
    ):
        if symbol not in body:
            print(f"❌ {_DECISION_SOURCE}: `_has_understanding_evidence` بلا {symbol} — {why}.")
            failures += 1

    if failures:
        print(f"\n❌ check_understanding_evidence: {failures} انتهاكاً.")
        return 1
    print("✅ مؤشّرات الفهم عباراتُ آلية، ولا تتقاطع مع علامات النيّة، والحارس مُستشار.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
