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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

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
    # ISS-149 (F1): يرفع — قاموسٌ فارغ عن ملفٍّ لم يُقرأ يجعل تكافؤ العقلين
    # «مُتحقَّقاً» على لا شيء، وهو أخطر ما يمكن أن تكذب فيه بوّابة تكافؤ.
    tree = parse_source(path)

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
    # ISS-149 (F1): يرفع — «صفر مخالفين» عن ملفٍّ لم يُحلَّل شهادةٌ بلا فحص.
    tree = parse_source(path)

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


def _check_confusion_mirror(mirror: dict[str, object]) -> int:
    """ISS-149 — علامات الحيرة في الخدمة مرآةٌ لـ`shared/intent`، لا قائمةٌ ثانية.

    **الكارثة التي يُغلقها هذا الفحص:** كانت `_CONFUSION` في الخدمة **٧** علامات
    مقابل **٢٧** قانونية، وهي تحكم `_is_tutoring_turn` — أي هل يدخل الدور المسارَ
    التربوي الحتمي أصلاً أم يسقط إلى الـLLM. مسبارٌ تفاضلي على العقلين بخمس صيغ
    حيرة واقعية أعطى **٤ انحرافات من ٥**: «لم استوعب» · «محتار» · «ماعرفتش» ·
    «je ne comprends pas» — كلّها حيرةٌ عند المونوليث وسقوطٌ إلى الـLLM عند الخدمة.

    التوريد نفسه مشروع (دستور الخدمات 97/98)، لكنّ الدستور يشترط اقترانه ببوّابة
    تكافؤ (D-206·L5: «لا عقلان بلا تكافؤ محروس»)، على سابقة `check_notation_parity`
    (D-185) و`check_redaction_parity` (D-203) و`check_model_chain_parity` (D-174).
    وهذه القائمة وحدها كانت **بلا بوّابة**، فبقي الانحراف حيّاً بلا أن يلاحظه شيء.

    المقارنة على النصّ **المُطبَّع** بالمُطبِّع القانوني: الشكل قد يختلف، والمعنى لا.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from shared.intent import markers_for, normalize

    canonical = {normalize(m) for m in markers_for("confusion")}
    # يُقرأ مباشرةً لا عبر `_GUARDED_NAMES`: مصدرُ هذه القائمة `shared/intent`
    # لا `shared/pedagogy`، فلا مكان لها في مرآة الخطوات.
    raw: tuple | None = None
    tree = parse_source(SERVICE_MIRROR)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Tuple):
            continue
        if any(isinstance(t, ast.Name) and t.id == "_CONFUSION" for t in node.targets):
            raw = ast.literal_eval(node.value)
    if raw is None:
        print(
            f"❌ المرآة لا تُعرّف `_CONFUSION` — {SERVICE_MIRROR.relative_to(REPO_ROOT)} (ISS-149)."
        )
        return 1
    vendored = {normalize(m) for m in raw}  # type: ignore[union-attr]
    if vendored == canonical:
        return 0
    print("❌ انحراف علامات الحيرة بين `shared/intent` والخدمة المصغّرة (ISS-149):")
    if canonical - vendored:
        print(f"   يعرفها المونوليث وتجهلها الخدمة: {sorted(canonical - vendored)}")
    if vendored - canonical:
        print(f"   في الخدمة وليست قانونية: {sorted(vendored - canonical)}")
    print("   وهي تحكم دخولَ الدور المسارَ التربوي — فانحرافها يعني طالباً حائراً")
    print("   يُسلَّم إلى الـLLM بدل التشخيص. المصدر: `shared/intent/registry.py`.")
    return 1


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

    violations += _check_confusion_mirror(mirror)

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
    sys.exit(run_gate(main))
