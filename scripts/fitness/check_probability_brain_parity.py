"""بوّابة تكافؤ العقلين — منطقُ مصيرِ دور الطالب لا يعيش نسختين (D-206 · L5).

## لماذا هذه البوّابة موجودة

المونوليث (`probability_brain/cognitive_verification.py`) والخدمة
(`overmind/probability_tutor.py`) كانا يحملان **نفس** علامات خطوات التدريس منسوخةً
حرفياً. وبها يُقرَّر: هل بدأ الحوار التدريسي؟ وأيّ سؤالٍ معلَّق يُقاس عليه جوابُ الطالب؟

فانحرافُ علامةٍ واحدة = **عقلٌ يعترف بإجابة الطالب وعقلٌ يتجاهلها**، والطالب لا يعرف
أيّهما أجابه. وهذا ليس افتراضاً: عند إنشاء هذه البوّابة كانت النسختان **منحرفتَين
فعلاً** — نسخة الخدمة وحدها تعرف ``"لنبدأ من فهمك أنت"`` كخطوة تدريس، فالمونوليث لا
يتعرّف على probe بثّه هو ويجوز أن يُعيده.

على سابقة `check_notation_parity` (D-185) و`check_redaction_parity` (D-203):
تكافؤٌ محروسٌ آلياً بدل «حرّر النسختين يدوياً».

## ماذا تفحص

**تكافؤ القيم لا النصّ** — بـAST لا بـgrep:

1. المونوليث **يستورد** من `shared/pedagogy` ولا يُعرّف العلامات حرفياً.
2. الخدمة تحمل **مرآةً** لأن ملفّها مستقلّ بذاته عمداً (يُحمَّل بلا حزمة في اختبارات
   المنفذ، فلا يستورد شيئاً — نفس عقد `response_sanitizer.py`). فتُقارَن **قيمُ** كل
   اسمٍ محروس بقيمته في المصدر: أيّ فرقٍ في عنصرٍ واحد يُفشِل CI في الاتجاهين.

هذا هو الفرق بين تكافؤ الشكل وتكافؤ المعنى: التوريد بايتاً ببايت كان سيكسر عقدَ
الاستقلال الذاتي للملفّ، ومقارنةُ القيم تحفظ العقدين معاً.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

CANONICAL = REPO_ROOT / "shared/pedagogy/probability_steps.py"
MONOLITH_BRAIN = REPO_ROOT / "app/services/skills/probability_brain/cognitive_verification.py"
SERVICE_MIRROR = (
    REPO_ROOT / "microservices/orchestrator_service/src/services/overmind/probability_tutor.py"
)

#: الأسماء التي يجب أن تتطابق قيمتها بين المصدر والمرآة.
_GUARDED_NAMES: tuple[str, ...] = (
    "STEP_QUESTION_MARKERS",
    "TUTORING_STEP_MARKERS",
    "FIRST_HELP_MARKERS",
)


def _literal_values(path: Path) -> dict[str, object]:
    """قيم الأسماء المحروسة المُعرَّفة **حرفياً** على مستوى الوحدة."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return {}

    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = [t.id for t in targets if isinstance(t, ast.Name)]
        if not names or node.value is None:
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        for name in names:
            if name.lstrip("_") in _GUARDED_NAMES:
                values[name.lstrip("_")] = value
    return values


def _defines_literal_markers(path: Path) -> list[tuple[str, int]]:
    """أسماء محروسة مُعرَّفة بقيمة حرفية — يُستعمل على المونوليث حيث الاستيراد واجب."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, FileNotFoundError):
        return []

    offenders: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        if not isinstance(node.value, ast.Tuple | ast.List):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            name = getattr(target, "id", None) or getattr(target, "attr", None)
            if name and name.lstrip("_") in _GUARDED_NAMES:
                offenders.append((name, node.lineno))
    return offenders


def main() -> int:
    """يفشل عند انحراف قيمةٍ واحدة بين المصدر والمرآة، أو نسخةٍ محلّية في المونوليث."""
    violations = 0

    canonical = _literal_values(CANONICAL)
    missing = [n for n in _GUARDED_NAMES if n not in canonical]
    if missing:
        print(f"❌ المصدر القانوني لا يُعرّف: {', '.join(missing)}")
        return 1

    mirror = _literal_values(SERVICE_MIRROR)
    for name in _GUARDED_NAMES:
        if name not in mirror:
            violations += 1
            print(f"❌ المرآة لا تُعرّف {name} — {SERVICE_MIRROR.relative_to(REPO_ROOT)}")
            continue
        if mirror[name] != canonical[name]:
            violations += 1
            only_src = [x for x in canonical[name] if x not in mirror[name]]
            only_mir = [x for x in mirror[name] if x not in canonical[name]]
            print(f"❌ انحراف قيمة {name} بين العقلين:")
            if only_src:
                print(f"   في المصدر وحده: {only_src}")
            if only_mir:
                print(f"   في المرآة وحدها: {only_mir}")
            print("   الإصلاح: طابِق القيمتين — علامةٌ يعرفها عقلٌ واحد تصير للعقلين.")

    for name, lineno in _defines_literal_markers(MONOLITH_BRAIN):
        violations += 1
        rel = MONOLITH_BRAIN.relative_to(REPO_ROOT).as_posix()
        print(f"❌ علامات مُعرَّفة حرفياً في المونوليث: {rel}:{lineno} — {name}")
        print("   الإصلاح: استورد من `shared.pedagogy` (المونوليث يملك حقّ الاستيراد).")

    if violations:
        print(f"\n❌ check_probability_brain_parity: {violations} مخالفة.")
        return 1

    print("✅ check_probability_brain_parity: العقلان متكافئان قيمةً على مصدرٍ واحد.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
