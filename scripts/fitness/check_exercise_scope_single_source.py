"""بوّابة «مصدر النطاق الواحد» — القائمة الثامنة مستحيلة لا غير مرغوبة (D-206 · L6).

## لماذا هذه البوّابة موجودة

طالب حقيقي طلب «السؤال الأول فقط» ثلاث مرّات فلم يحصل عليه (ISS-144). أحد الأعطاب
الأربعة: مفردات النطاق (ترتيبيّات · «فقط» · أفعال الطلب · «الجزء») كانت مبعثرة في
**سبع** قوائم عبر ستّ ملفّات، ولا واحدة منها تعرف «**اول** سؤال» نكرةً — بينما تعرفها
كلّها بصيغة «**ال**أول» المُعرَّفة.

هذا هو صنف D-186 حرفياً بمفتاحٍ جديد: كاشفاتٌ متعدّدة لنيّةٍ واحدة تتفرّق بمرور الوقت،
وكلّ إصلاحٍ يضيف الكلمة الناقصة إلى القائمة التي أخطأت — فيُشفى العَرَض ويبقى الصنف.
البوّابة تُنهي الصنف: أيّ قائمة مفردات نطاق **خارج** `shared/exercise_scope` تُفشِل CI.

على سابقة `check_intent_single_source` (D-186) و`check_notation_parity` (D-185).

## ماذا تفحص بالضبط

تمسح مصدر المشروع بـAST بحثاً عن أيّ تعيينٍ على مستوى الوحدة/الصنف قيمته `tuple`/`list`
من السلاسل تحتوي **عبارتَين أو أكثر** من مفردات النطاق القانونية. العتبة «عبارتان»
مقصودة: سلسلةٌ واحدة قد ترد لغرضٍ آخر مشروع (رسالة، قالب)، أمّا اجتماعُ اثنتين فهو
قائمةُ نطاقٍ بالتعريف.

⚠️ **تُقاس على الصور المُطبَّعة**: تبحث عن «الأول» و«اول» معاً، وإلّا أفلتت منها القائمة
التي سبّبت الكارثة أصلاً — وهي مفارقةٌ وقعتُ فيها أوّل مرّة.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL = REPO_ROOT / "shared/exercise_scope/registry.py"

_SKIP_DIRS = frozenset(
    {
        ".git",
        ".next",
        "archive",
        "docs",
        "migrations_archive",
        "node_modules",
        "site-packages",
        # `tests` مُستثنى عمداً — اختبارٌ يُعدِّد صيغ الطالب هو **الحارس** لا نسخة
        # مخفيّة؛ إلزامُه بالاستيراد من المصدر يجعله يختبر المصدر بالمصدر (سابقة D-186).
        "tests",
    }
)

_ALLOWLIST: dict[str, str] = {
    "shared/exercise_scope/registry.py": "المصدر القانوني نفسه.",
    "scripts/fitness/check_exercise_scope_single_source.py": (
        "هذا الملفّ نفسه يحمل العبارات كسلاسل حرفية للبحث."
    ),
}

#: **دَين مُجمَّد — يتقلّص فقط** (سابقة D-105). أيّ قائمة جديدة تُفشِل CI، وكلّ هجرة
#: تحذف سطراً. الخريطة **لا تكبر أبداً**؛ فالدَّين مرئيّ ومحصور بدل أن يتكاثر خفيةً.
_FROZEN_DEBT: dict[str, str] = {
    # الترتيبيّ هنا جزءٌ من **هويّة تمرين** («التمرين الثاني» = أيّ تمرين) لا من
    # **نطاقٍ داخله** («السؤال الثاني» = أيّ بند). مفهومان متمايزان يتشابه لفظهما.
    "app/services/capabilities/exercise_retrieval.py": (
        "هويّة التمرين (_EXERCISE_PATTERNS · _BAC_SPECIFICITY_PATTERNS) لا نطاقٌ داخله."
    ),
    # خرائط الأخطاء الإملائية للبحث («الثانى» بالياء) — تصحيحُ كتابةٍ لا كشفُ نطاق.
    "app/core/helpers/search.py": "خريطة أخطاء إملائية للبحث — نطاقٌ آخر.",
    "microservices/research_agent/src/search_engine/fallback_expander.py": (
        "خريطة أخطاء إملائية للبحث — نطاقٌ آخر (ونسخة خدمة مصغّرة)."
    ),
    # «الحل الكامل» نيّةُ تشخيصٍ لا نيّةُ نطاق. مرشَّحٌ للمراجعة: بعد أن صارت
    # `part_selection` تستبق، قد لا يصحّ بقاء «السؤال الأول» علامةَ حلٍّ كامل أصلاً
    # (D-190 وثّق أنّ `full_solution` كانت تخطف المواضيع). يُقاس أثره في جولة مستقلّة.
    "app/services/skills/concept_diagnosis_skill.py": (
        "علامات «الحل الكامل» — نيّة تشخيص؛ مرشَّحة للمراجعة بعد أسبقيّة part_selection."
    ),
    # الخدمات المصغّرة **لا تستورد `shared/`** إطلاقاً (صفر استيراد في الشجرة كلّها)،
    # فالتوريد مقصود على نمط `notation` (D-185) لا إهمال.
    "microservices/orchestrator_service/src/services/overmind/utils/context_composer.py": (
        "خدمة مصغّرة — لا تستورد shared؛ نسخة مُوَرَّدة مقصودة (نمط D-185)."
    ),
}

#: عبارات مميِّزة لمفردات النطاق — مُنتقاة لتكون **مميِّزة** فلا تلتقط قوائم لغرضٍ آخر.
#: تشمل الصورتين المُعرَّفة والنكرة معاً: إغفالُ النكرة هو العطب الذي وُلدت منه ISS-144.
_SIGNATURES: tuple[str, ...] = (
    "الأول",
    "الاول",
    "اول",
    "الثاني",
    "الثانى",
    "ثاني",
    "الثالث",
    "ثالث",
    "الجزء الأول",
    "الجزء الاول",
    "السؤال الأول",
    "السؤال الاول",
    "بدون حل",
    "نص السؤال",
    "question only",
    "part i",
    "part 1",
    "premiere",
    "deuxieme",
)

_MIN_HITS = 2


def _string_items(node: ast.AST) -> list[str]:
    """سلاسل عناصر `tuple`/`list` حرفية — وإلا قائمة فارغة."""
    if not isinstance(node, ast.Tuple | ast.List):
        return []
    return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def _dict_keys(node: ast.AST) -> list[str]:
    """مفاتيح `dict` الحرفية — قوائم النطاق تُكتب أحياناً خرائطَ («الجزء الأول» → I)."""
    if not isinstance(node, ast.Dict):
        return []
    return [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]


def _scan(path: Path) -> list[tuple[str, int, list[str]]]:
    """(اسم المتغيّر، السطر، العبارات المُلتقَطة) لكل قائمة نطاق في الملفّ."""
    # ISS-149 (F1): يرفع — قائمةٌ فارغة عن ملفٍّ لم يُحلَّل تعني «لا قائمة نطاق» زوراً.
    tree = parse_source(path)

    findings: list[tuple[str, int, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign | ast.AnnAssign):
            continue
        value = node.value
        if value is None:
            continue
        items = _string_items(value) or _dict_keys(value)
        # عناصر tuple المتداخلة (("اول", 1), …) — شكلُ جدولِ الترتيبيّات.
        if not items and isinstance(value, ast.Tuple | ast.List):
            for element in value.elts:
                items.extend(_string_items(element))
        if not items:
            continue
        hits = sorted({s for s in _SIGNATURES if any(s == item for item in items)})
        if len(hits) < _MIN_HITS:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        name = next(
            (t.id for t in targets if isinstance(t, ast.Name)),
            "<expr>",
        )
        findings.append((name, node.lineno, hits))
    return findings


def main() -> int:
    """يفشل إذا عُرِّفت مفردات نطاقٍ خارج المصدر القانوني."""
    if not CANONICAL.exists():
        print(f"❌ المصدر القانوني مفقود: {CANONICAL.relative_to(REPO_ROOT)}")
        return 1

    violations = 0
    for path in sorted(REPO_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if rel in _ALLOWLIST or rel in _FROZEN_DEBT:
            continue
        for name, lineno, hits in _scan(path):
            violations += 1
            print(f"❌ قائمة مفردات نطاق مكرَّرة: {rel}:{lineno} — {name}")
            print(f"   العبارات المُلتقَطة: {', '.join(hits)}")
            print("   الإصلاح: استهلك المصدر القانوني —")
            print("        from shared.exercise_scope import resolve_scope, ORDINAL_FORMS")

    # الدَّين ثنائي الاتجاه: مدخلٌ أُغلق ولم يُحذَف من الخريطة يُفشِل أيضاً (درس D-189).
    for rel, reason in sorted(_FROZEN_DEBT.items()):
        path = REPO_ROOT / rel
        if not path.exists():
            violations += 1
            print(f"❌ دَين مُجمَّد يشير إلى ملفّ غير موجود: {rel} — احذف المدخل.")
            continue
        if not _scan(path):
            violations += 1
            print(f"❌ دَين مُجمَّد لم يعد مخروقاً: {rel} ({reason})")
            print("   الإصلاح: احذف المدخل من `_FROZEN_DEBT` — الخريطة تتقلّص فقط.")

    if violations:
        print(f"\n❌ check_exercise_scope_single_source: {violations} مخالفة.")
        return 1

    print("✅ check_exercise_scope_single_source: مصدر نطاقٍ واحد، والدَّين محصور.")
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
