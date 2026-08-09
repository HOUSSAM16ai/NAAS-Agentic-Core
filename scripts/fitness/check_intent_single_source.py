"""بوّابة «مصدر النيّة الواحد» — القائمة السادسة مستحيلة لا غير مرغوبة (D-186).

## لماذا هذه البوّابة موجودة

ثلاث كوارث متتالية على طالب حقيقي كان جذرها **واحداً**: قوائم علامات متعدّدة لنفس نيّة
الطالب تتفرّق بمرور الوقت (ISS-128 · ISS-138 · ISS-139). في ISS-139 كانت **ثلاث** قوائم
للنيّة التعريفية (23 و13 و27 علامة) لا تتّفق أيّ اثنتين منها، فسؤال «ماذا يقصد بالحرف C»
عرفته واحدة وجهلته اثنتان ⇒ سقطت المرحلة التعريفية وأُجيب الطالب بمثالٍ عارٍ.

كل مرّة كان العلاج «أضِف الكلمة الناقصة» — فيُصلَح العَرَض ويبقى الصنف. هذه البوّابة
تُنهي الصنف: أي وحدة تُعرّف علامات نيّة **خارج** `shared/intent` تُفشِل CI.

على سابقة `check_notation_parity.py` (D-185) و`check_model_chain_parity.py` (D-174):
«تكافؤ محروس آلياً بدل حرّر النسخ يدوياً».

## ماذا تفحص بالضبط

تمسح مصدر المشروع بـAST بحثاً عن أي تعيين على مستوى الوحدة/الصنف قيمته `tuple`/`list`
من السلاسل، تحتوي **عبارتَين أو أكثر** من عبارات النيّة القانونية. وجودها خارج المصدر
الواحد = نسخة جديدة = فشل.

العتبة «عبارتان» مقصودة: سلسلة واحدة قد ترد في قائمة لغرض آخر مشروع (رسالة، قالب)،
أمّا اجتماع عبارتين من عبارات النيّة نفسها فهو قائمة نيّة بالتعريف.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]

CANONICAL = REPO_ROOT / "shared/intent/registry.py"

#: أدلّة لا تُمسَح (تبعيات/بناء/أرشيف — ليست مصدر المشروع).
#:
#: **`tests` مُستثنى عمداً:** اختبارٌ يُعدِّد صيغ الطالب («كل هذه تُصنَّف definition»)
#: ليس نسخةً مخفيّة بل هو **الحارس** نفسه. إلزامه بالاستيراد من المصدر يجعله
#: تحصيلاً حاصلاً (يختبر المصدر بالمصدر) فيفقد كل قيمته.
_SKIP_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "migrations_archive",
        "site-packages",
        ".next",
        "archive",
        "docs",
        "tests",
    }
)

#: ملفّات مُستثناة صراحةً ولكلٍّ سببها — الاستثناء يُوثَّق ولا يُمنَح ضمناً.
_ALLOWLIST: dict[str, str] = {
    "shared/intent/registry.py": "المصدر القانوني نفسه.",
    "shared/notation/registry.py": (
        "نسخة مُوَرَّدة مقصودة: يجب أن تبقى صالحة للتوريد إلى `notation-service` بلا "
        "استيراد من `shared/` (دستور الخدمات المصغّرة، القاعدتان 97/98). محروسة "
        "بـ`check_notation_parity.py` + فحص الاحتواء أدناه."
    ),
    "microservices/notation_service/src/notation/registry.py": (
        "النسخة المُوَرَّدة الفعلية — مطابقة بايتاً ببايت للأعلى."
    ),
    "scripts/fitness/check_intent_single_source.py": (
        "هذا الملف نفسه يحمل العبارات كسلاسل حرفية للبحث."
    ),
    "scripts/e2e/live_student_journey.py": (
        "ترانسكريبت طالبٍ حقيقي (المحادثة 763 في الإنتاج) يُعاد تمثيله حرفياً — "
        "**ما كتبه الطالب فعلاً**، لا تعريفٌ ثانٍ لنيّة. نفس منطق استثناء `tests/`: "
        "تعدادُ الصيغ هنا حارسٌ لا نسخة، وتغييرُه إلى استيرادٍ من `shared/intent` "
        "يجعل الاختبار يسأل النظامَ عمّا يعرفه بدل أن يسأله عمّا قاله طالب."
    ),
}

#: **دَين مُجمَّد — يتقلّص فقط** (سابقة D-105: «قوائم deselect تتقلّص فقط»).
#:
#: مسحُ D-186 كشف أن الازدواج أوسع من القوائم الخمس التي وُلدت منها ISS-139. هُوجرت
#: قوائم الحيرة/التعريف في المسار التعليمي الحيّ؛ وما بقي مُجمَّد هنا **بسببه المكتوب**.
#: القاعدة: هذه الخريطة **لا تكبر أبداً**. أي قائمة جديدة تُفشِل CI، وكل هجرة تحذف
#: سطراً. فالدَّين مرئي ومحصور بدل أن يكون خفيّاً ومتكاثراً.

#: ISS-149 — بوّابات التكافؤ المقبولة كفارضٍ لإعفاء «توريد مقصود».
_PARITY_GATES: frozenset[str] = frozenset(
    {
        "check_probability_brain_parity",
        "check_notation_parity",
        "check_redaction_parity",
        "check_model_chain_parity",
    }
)

#: صيغة الاعتراف الصريح بغياب الحراسة — العقيدة تقبلها، وترفض الصمت.
_NO_GATE_DECLARATION = "بلا بوّابة تكافؤ"

_FROZEN_DEBT: dict[str, str] = {
    "app/services/chat/local_graph_explanation.py": "أنماط شرح للمسار المحلّي — نطاق آخر.",
    # نصوص doctrine (توثيق مُقتبَس) لا كاشفات — تُطابَق نصّياً لا وظيفياً.
    "app/services/skills/doctrine/exercise_core.py": "نصّ doctrine مُقتبَس لا كاشف.",
    "app/services/skills/doctrine/pedagogy.py": "نصّ doctrine مُقتبَس لا كاشف.",
    "app/services/skills/doctrine/platform_layer.py": "نصّ doctrine مُقتبَس لا كاشف.",
    # بوّابة الفعل الكلامي (سؤال مقابل إجابة) — نحوٌ لا نيّة (D-162).
    "app/services/skills/probability_brain/cognitive_verification.py": (
        "بوّابة الفعل الكلامي (D-162) — تمييز السؤال من الإجابة، لا تصنيف نيّة."
    ),
    "app/services/skills/probability_brain/escape_hatch.py": (
        "كاشف السؤال المفاهيمي المحلّي — مرشَّح للهجرة في موجة تالية."
    ),
    "app/services/skills/bkt_engine.py": "إشارة evidence لينة (BKT) — مرشَّح للهجرة.",
    "app/services/skills/concept_diagnosis_skill.py": "علامات حوادث التمرين لا نيّة الطالب.",
    "app/services/skills/probability_vocab.py": "كاشف الإحباط (D-078) — مرشَّح للهجرة.",
    # خدمات مصغّرة: دستورها يمنع مكتبة منطق مشتركة (القاعدتان 97/98) ⇒ التوريد مقصود.
    # ISS-149: ليست مرآةً لقائمةٍ قانونية بل **مُصنِّف محلّي** لنيّة الاسترجاع
    # مقابل الشرح، بنطاقٍ خاصّ بالخدمة. لا نظير له في `shared/intent` يُقارَن به،
    # فلا بوّابة تكافؤ ممكنة اليوم — والاعتراف بذلك أنفع من ادّعاء حراسة.
    # الفجوة مُسجَّلة في `.memory/issues.md` تحت ISS-149.
    "microservices/content_retrieval_skill/src/intent_classifier.py": (
        "خدمة مصغّرة — توريد مقصود، بلا بوّابة تكافؤ: مُصنِّف محلّي لا مرآة لقائمة قانونية."
    ),
    # ISS-149: صار التوريد محروساً — `_CONFUSION` تُقارَن قيمةً بـ`shared/intent`.
    "microservices/orchestrator_service/src/services/overmind/probability_tutor.py": (
        "خدمة مصغّرة — توريد مقصود (port العقل الحتمي)، يحرسه check_probability_brain_parity."
    ),
    "scripts/verify_d139_live.py": "سكربت تحقّق حيّ — ليس مسار تشغيل.",
}

#: عبارات مميِّزة لكل نيّة — وجود اثنتين منها في قائمة واحدة = قائمة نيّة.
#: مُنتقاة لتكون **طويلة ومميِّزة** فلا تلتقط قوائم لغرض آخر.
_SIGNATURES: tuple[str, ...] = (
    "ماذا نقصد",
    "ماذا يقصد",
    "شنو يقصد",
    "ما المقصود",
    "ما معنى",
    "ماذا يعني",
    "لم افهم",
    "لم أفهم",
    "مفهمتش",
    "ما فهمت",
    "مش فاهم",
    "اعطني مثال",
    "أعطني مثال",
    "هات مثال",
    "كيف نحسب",
    "كيفاش نحسب",
    "خطوات الحل",
    "اعطني تلميح",
    "ساعدني",
)

#: الحدّ الأدنى لاعتبار القائمة «قائمة نيّة».
_MIN_HITS: int = 2


def _string_items(node: ast.AST) -> list[str]:
    """سلاسل عناصر `tuple`/`list` حرفية — وإلا قائمة فارغة."""
    if not isinstance(node, ast.Tuple | ast.List):
        return []
    return [e.value for e in node.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]


def _scan(path: Path) -> list[tuple[str, int, list[str]]]:
    """يُرجع (اسم المتغيّر، السطر، العبارات المُلتقَطة) لكل قائمة نيّة في الملف."""
    # ISS-149 (F1): يرفع — قائمةٌ فارغة عن ملفٍّ لم يُحلَّل تعني «لا نيّات مكرّرة» زوراً.
    tree = parse_source(path)

    findings: list[tuple[str, int, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
            names = [t.id for t in targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            names = [node.target.id] if isinstance(node.target, ast.Name) else []
            value = node.value
        else:
            continue
        if not names:
            continue
        items = _string_items(value)
        if not items:
            continue
        hits = sorted({sig for sig in _SIGNATURES if any(sig in item for item in items)})
        if len(hits) >= _MIN_HITS:
            findings.append((names[0], node.lineno, hits))
    return findings


def _mirror_is_contained() -> list[str]:
    """يتحقّق أن علامات النسخة المُوَرَّدة (notation) ⊆ المصدر القانوني.

    التوريد مسموح (استقلال الخدمات)، أمّا **الانجراف** فلا: علامة في النسخة المُوَرَّدة
    لا يعرفها المصدر تُعيد إنتاج الصنف نفسه من باب آخر.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from shared.intent.registry import markers_for, normalize
    from shared.notation.registry import _COMPUTE_INTENT, _DEFINITIONAL_INTENT

    canonical = {normalize(m) for m in markers_for("definition")} | {
        normalize(m) for m in markers_for("computation")
    }
    mirrored = {normalize(m) for m in (*_DEFINITIONAL_INTENT, *_COMPUTE_INTENT)}
    return sorted(mirrored - canonical)


#: ISS-149 — «توريد مقصود» يحتاج فارضاً مُسمّى، وإلّا صار إعفاءً دائماً.
#:
#: كانت `probability_tutor.py` مُعفاةً بسبب «خدمة مصغّرة — توريد مقصود». والتوريد
#: نفسه مشروع (دستور الخدمات 97/98 يمنع مكتبة منطق مشتركة)، لكنّ الدستور يشترط
#: اقترانه **ببوّابة تكافؤ**: `check_notation_parity` (D-185) ·
#: `check_redaction_parity` (D-203) · `check_model_chain_parity` (D-174) ·
#: `check_probability_brain_parity` (D-206·L5). وهذه وحدها كانت بلا بوّابة، فانحرفت
#: علاماتُ الحيرة إلى **٧ مقابل ٢٧** بلا أن يلاحظ أحد — أي طالبٌ حائر يُسلَّم إلى
#: الـLLM بدل التشخيص، في أربع صيغ من كل خمس.
def _check_vendoring_has_an_enforcer() -> int:
    """كل إدخالٍ يذكر «توريد» يُسمّي بوّابته الموجودة، أو يُصرّح بغيابها."""
    failures = 0
    for rel, reason in sorted(_FROZEN_DEBT.items()):
        if "توريد" not in reason:
            continue
        named = [g for g in _PARITY_GATES if g in reason]
        if not named:
            # العقيدة تقبل «بلا فارض» **منطوقاً** (ENGINEERING_DOCTRINE، قاعدة
            # الإغلاق): الاعتراف بغياب الحراسة أنفع من ادّعائها. ما ترفضه هو
            # الصمت — إعفاءٌ يبدو محروساً وليس كذلك.
            if _NO_GATE_DECLARATION in reason:
                continue
            failures += 1
            print(
                f"\u274c إعفاء «توريد» بلا فارضٍ مُسمّى: {rel}\n"
                f"   السبب المكتوب: {reason!r}\n"
                f"   التوريد مشروع، لكنّ نسختين بلا بوّابة تكافؤ تنحرفان — سمِّ البوّابة\n"
                f"   في نصّ السبب (مثل: {sorted(_PARITY_GATES)[0]})، أو صرّح\n"
                f"   {_NO_GATE_DECLARATION!r} مع سببٍ منطوق."
            )
            continue
        for gate in named:
            if not (REPO_ROOT / "scripts/fitness" / f"{gate}.py").is_file():
                failures += 1
                print(f"\u274c {rel}: يستشهد بـ{gate} وهي غير موجودة — فارضٌ وهمي.")
    return failures


def main() -> int:
    """يُرجع 0 عند وجود مصدر واحد فقط، و1 عند أي نسخة أو انجراف."""
    if not CANONICAL.is_file():
        print(f"❌ Missing canonical intent registry: {CANONICAL.relative_to(REPO_ROOT)}")
        return 1

    failures = 0
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if any(part.startswith(".venv") or part in _SKIP_DIRS for part in path.parts):
            continue
        rel = str(path.relative_to(REPO_ROOT))
        if rel in _ALLOWLIST or rel in _FROZEN_DEBT:
            continue
        for name, lineno, hits in _scan(path):
            failures += 1
            print(f"❌ Duplicate intent marker list: {rel}:{lineno} — {name}")
            print(f"   matched canonical phrases: {', '.join(hits)}")
            print("   Fix: import from shared.intent instead —")
            print(
                f"        from shared.intent import markers_for\n"
                f'        {name} = markers_for("<intent>")'
            )

    failures += _check_vendoring_has_an_enforcer()

    # الدَّين يتقلّص فقط: مدخلٌ لم يعد فيه ازدواج **يجب** أن يُحذف من الخريطة، وإلّا
    # تراكمت استثناءات ميتة تُخفي عودة الازدواج لاحقاً تحت غطاء «مُجمَّد سابقاً».
    for rel, reason in sorted(_FROZEN_DEBT.items()):
        path = REPO_ROOT / rel
        if not path.is_file():
            failures += 1
            print(f"❌ Stale frozen-debt entry (file gone): {rel} — {reason}")
        elif not _scan(path):
            failures += 1
            print(f"❌ Stale frozen-debt entry (already clean): {rel}")
            print("   Fix: delete this line from _FROZEN_DEBT — the debt shrank, record it.")

    drift = _mirror_is_contained()
    if drift:
        failures += 1
        print("❌ Vendored notation intent markers drifted from shared/intent:")
        for marker in drift:
            print(f"   {marker!r} is in shared/notation but not in shared/intent")
        print("   Fix: add the marker to shared/intent/registry.py (single source).")

    if failures:
        print(f"\n❌ check_intent_single_source: {failures} violation(s).")
        return 1
    print("✅ check_intent_single_source: one canonical intent source, mirror contained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_gate(main))
