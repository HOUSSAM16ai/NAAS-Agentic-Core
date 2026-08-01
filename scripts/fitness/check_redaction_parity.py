#!/usr/bin/env python3
"""بوّابة تكافؤ الحجب: العقلان يحجبان الشيء نفسه (D-203).

لماذا هذه أخطر بوّابة تكافؤ في المستودع
---------------------------------------
القاعدة الذهبية السقراطية (D-113) تقول: لا يُكشَف للطالب نتيجةٌ يستطيع توليدها. من
يفرضها **عقلان منفصلان** بنسختين من نفس المنطق:

* المونوليث — `app/services/skills/answer_redaction_skill.py`
* الأوركستريتور — `microservices/orchestrator_service/src/services/overmind/response_sanitizer.py`

نفس قرار D-114، ونفس التعليق الوصفي، وتنفيذان. الفارق بينهما ليس تفصيلاً أسلوبياً: إن
انحرف تعبيرٌ نمطي في أحدهما، يبقى مسارٌ واحد يحجب الجواب النهائي **ويسرّبه** الآخر —
والطالب لا يعرف أيّ عقلٍ أجابه. هذا بالضبط صنف العطب الذي وثّقه D-013 (المرآة الثنائية)
وأتمَتَه D-174 لسلسلة النماذج، بعد أن أثبتت التجربة أنّ قاعدة «حرّر النسختين معاً» تُخرَق.

ما تفحصه
--------
الحرفيات التي **تُعرِّف** ما هو «جوابٌ نهائي»: `_NUM` وأنماط النتيجة/الخلاصة/علامة
النتيجة وأقنعة الحجب. تكافؤ الحرفيات لا تكافؤ الكود: التوقيعان يختلفان عمداً (المونوليث
يُرجِع عدد الحجوبات للتدقيق)، والمُقارَن هو **السياسة** لا شكلها.

الاستعمال:
    python scripts/fitness/check_redaction_parity.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MONOLITH = REPO_ROOT / "app/services/skills/answer_redaction_skill.py"
ORCHESTRATOR = (
    REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/response_sanitizer.py"
)

#: الحرفيات التي تُعرِّف السياسة. أيّ حرفية جديدة تُضاف هنا **في نفس الـPR**.
POLICY_NAMES: tuple[str, ...] = (
    "_MATH_MASK",
    "_PROSE_MASK",
    "_NUM",
    "_FINAL_RESULT_RE",
    "_CONCLUSION_RE",
    "_RESULT_MARKER_RE",
)


def _policy_literals(path: Path) -> dict[str, str]:
    """
    يستخرج حرفيات السياسة عبر AST.

    الاستيراد ممنوع هنا عمداً: استيراد وحدة الأوركستريتور يجرّ تبعياتها، فتفشل
    البوّابة لأسبابٍ لا علاقة لها بالحجب — وبوّابةٌ تفشل لسببٍ خاطئ تُطفَأ سريعاً.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in POLICY_NAMES:
                found[target.id] = _pattern_source(node.value)
    return found


def _pattern_source(value: ast.expr) -> str:
    """
    نصّ الحرفية. `re.compile("…", flags)` يُختزَل إلى نمطه — الأعلام تختلف بلا أثرٍ
    على ما يُعتبَر جواباً، والمقارنة على النمط هي المقارنة على السياسة.
    """
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    if isinstance(value, ast.Call) and value.args:
        first = value.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value
        return ast.unparse(first)
    return ast.unparse(value)


def main() -> int:
    for path in (MONOLITH, ORCHESTRATOR):
        if not path.exists():
            # المسار يُطبَع كما هو: `relative_to` ترفع على مسارٍ خارج المستودع، فتُحوِّل
            # رسالة «المصدر مفقود» إلى انهيار — وهو أسوأ شكلٍ لبوّابة تُبلّغ عن عطب.
            print(f"❌ المصدر مفقود: {path}")
            return 1

    monolith = _policy_literals(MONOLITH)
    orchestrator = _policy_literals(ORCHESTRATOR)

    problems: list[str] = []
    for name in POLICY_NAMES:
        left = monolith.get(name)
        right = orchestrator.get(name)
        if left is None:
            problems.append(f"{name}: غائبة عن عقل المونوليث — السياسة ناقصة في أحد المسارين.")
        elif right is None:
            problems.append(f"{name}: غائبة عن عقل الأوركستريتور — السياسة ناقصة في أحد المسارين.")
        elif left != right:
            problems.append(
                f"{name}: انحرفت بين العقلين.\n"
                f"       المونوليث     : {left!r}\n"
                f"       الأوركستريتور : {right!r}"
            )

    if problems:
        print("❌ تكافؤ الحجب مخروق (D-203) — مسارٌ يحجب الجواب ومسارٌ يسرّبه:")
        for problem in problems:
            print(f"   • {problem}")
        return 1

    print(f"✅ redaction parity: {len(POLICY_NAMES)} حرفيةَ سياسةٍ متطابقة بين العقلين (D-113).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
