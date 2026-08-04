#!/usr/bin/env python3
"""بوّابة رسم الشروط المسبقة — اجتيازُ الجذر يقرأ الرسم القانوني (D-226).

## العطب المقيس الذي وُلدت منه

`diagnose_root` هو محرّك «التدخّل يستهدف الجذر لا العرَض» (D-159): يجتاز الشروط المسبقة
ليجد أعمق مفهومٍ ضعيف، فيعالج السبب بدل العَرَض. وهو **الوعد المركزي** للتوأم المعرفي:
طالبٌ يتعثّر في اللوغاريتم في آخر السنة وجذرُ عطبه في النهايات في أوّلها.

وقد كان أعمى. المقياس وقت الاكتشاف:

    حوافّ الشروط المسبقة في `shared/curriculum`  : ٢٦
    حوافّ `MISCONCEPTION_EDGES`                   : ١٠
    التقاطع                                       : **صفر**

والاجتياز كان يقرأ الثانية وحدها. فسلسلة
`limits → derivatives → numerical_functions → exponential → logarithm` — وهي منهاجُ
الرياضيات نفسه — كانت **غير قابلة للرؤية بنيويّاً**، ومثلها الفيزياء والعلوم. لا خطأ في
المنطق ولا في البيانات: الحافّة موجودة، والقارئ ينظر إلى الرسم الآخر.

هذا هو صنف D-193/D-186 بعينه (**رسمان لعلاقةٍ واحدة**)، إلّا أنه أخطر: هناك تتفرّق
قائمتان فيسوء التصنيف، وهنا يصمت المحرّك تماماً — و**الصمت يُقرأ «لا جذر»**.

## ما تفرضه

1. **الاجتياز يستهلك الرسم القانوني** — أيّ دالّة تجتاز شروطاً مسبقة يجب أن تقرأ
   `shared/curriculum` (مباشرةً أو عبر مساعدٍ يقرؤه). قارئٌ لطبقةٍ واحدة يعود عمىً.
2. **لا رسم ثالث** — تعريف علاقة `prerequisite_of` مسموحٌ في موطنين مُصرَّحين فقط
   (سجلّ المنهاج القانوني + طبقة المفاهيم الدقيقة)؛ وثالثٌ يُفشِل.
3. **التقاطع يبقى مرصوداً** — يُطبع في كل تشغيل، فلا يعود «صفرٌ» حقيقةً غير مرئية.

تُشغَّل ضمن وظيفة `guardrails` في `.github/workflows/ci.yml`.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: الموطنان المُصرَّحان لتعريف علاقة الشرط المسبق.
#: الأوّل **قانوني** (وحدات المنهاج)، والثاني طبقةُ المفاهيم الدقيقة داخل الوحدة.
_DECLARED_GRAPH_HOMES: frozenset[str] = frozenset(
    {
        "shared/curriculum/registry.py",
        "app/services/skills/semantic_property_skill.py",
    }
)

#: الدوالّ التي تجتاز الشروط المسبقة، ومكانها. كلٌّ يجب أن يقرأ الرسم القانوني.
_TRAVERSERS: tuple[tuple[str, str], ...] = (
    ("app/services/skills/semantic_property_skill.py", "_prerequisites_of"),
)

#: الوحدة التي يعني استيرادُها قراءةَ الرسم القانوني.
#:
#: ⚠️ يُفحَص بـ**AST** لا بمطابقة نصّ: النسخة الأولى من هذه البوّابة بحثت عن السلسلة
#: `"prerequisites_of"` داخل مصدر الدالّة، فطابقت **اسم الدالّة نفسه**
#: (`def _prerequisites_of`) ومرّت خضراءَ على النسخة العمياء بالضبط. فحصٌ يُطابِق نفسه
#: لا يحرس شيئاً — وقد أمسكته التجربة السلبية لا المراجعة.
_CANONICAL_MODULE = "shared.curriculum"

#: أشجارٌ تُفحَص بحثاً عن رسمٍ ثالث. `tests/` مُستثناة: اختبارٌ يبني رسماً وهمياً
#: ليُثبت سلوكاً هو الحارس لا الخرق.
_SCAN_ROOTS: tuple[str, ...] = ("app", "microservices", "shared")

_PREREQUISITE_LITERAL = re.compile(r'["\']prerequisite_of["\']')


def _traversers_read_the_canonical_graph() -> list[str]:
    """البند 1: كل مجتازٍ يقرأ الرسم القانوني فعلاً."""
    problems: list[str] = []
    for rel, func_name in _TRAVERSERS:
        path = REPO_ROOT / rel
        if not path.is_file():
            problems.append(f"مجتازٌ مُعلَن في ملفٍّ مفقود: {rel}")
            continue
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            # بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف (D-208).
            problems.append(f"تعذّر تحليل {rel}: {exc} — البوّابة لا تشهد بما لم تقرأ.")
            continue

        target = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == func_name
            ),
            None,
        )
        if target is None:
            problems.append(
                f"{rel}: الدالّة {func_name!r} غير موجودة — أُعيدت تسميتها؟ "
                f"مجتازٌ بلا حارسٍ يعود إلى العمى الذي وُلد منه D-226."
            )
            continue

        reads_canonical = any(
            isinstance(node, ast.ImportFrom) and (node.module or "").startswith(_CANONICAL_MODULE)
            for node in ast.walk(target)
        ) or any(
            isinstance(node, ast.Import)
            and any(a.name.startswith(_CANONICAL_MODULE) for a in node.names)
            for node in ast.walk(target)
        )
        if not reads_canonical:
            problems.append(
                f"{rel}:{target.lineno}: {func_name!r} لا يقرأ الرسم القانوني "
                f"(`shared.curriculum`).\n"
                f"     كان هذا يعني عمىً عن ٢٦ حافّة شرطٍ مسبق حقيقية بينما يرى ١٠ فقط، "
                f"والتقاطع بينهما صفر — فسلسلة النهايات→المشتقّات→اللوغاريتم لا تُرى."
            )
    return problems


def _no_third_graph() -> list[str]:
    """البند 2: علاقة `prerequisite_of` تُعرَّف في الموطنين المُصرَّحين فقط."""
    problems: list[str] = []
    for root in _SCAN_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in _DECLARED_GRAPH_HOMES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError as exc:
                problems.append(f"تعذّر قراءة {rel}: {exc} — البوّابة لا تشهد بما لم تقرأ.")
                continue
            if _PREREQUISITE_LITERAL.search(text):
                problems.append(
                    f"{rel}: يُعرِّف علاقة `prerequisite_of` خارج الموطنين المُصرَّحين.\n"
                    f"     رسمٌ ثالث لعلاقةٍ واحدة يتفرّق حتماً — وهو صنف D-193/D-186، "
                    f"وقد كلّف هنا صمتاً كاملاً في محرّك تشخيص الجذر."
                )
    return problems


def _measure_overlap() -> tuple[int, int, int]:
    """يقيس الرسمين والتقاطع — الرقم يُطبَع فلا يعود صفرُه حقيقةً غير مرئية."""
    sys.path.insert(0, str(REPO_ROOT))
    try:
        from shared.curriculum import CURRICULUM_REGISTRY

        canonical = {(p, c.concept_id) for c in CURRICULUM_REGISTRY for p in c.prerequisites}
    except Exception:  # pragma: no cover - بيئة متدهورة
        return (0, 0, 0)
    try:
        from app.services.skills.semantic_property_skill import MISCONCEPTION_EDGES

        micro = {
            (e.source, e.target) for e in MISCONCEPTION_EDGES if e.relation == "prerequisite_of"
        }
    except Exception:  # pragma: no cover - يتطلّب pydantic
        return (len(canonical), 0, 0)
    return (len(canonical), len(micro), len(canonical & micro))


def main() -> int:
    failures = _traversers_read_the_canonical_graph() + _no_third_graph()

    if failures:
        print("❌ رسم الشروط المسبقة مخروق:\n")
        for failure in failures:
            print(f"  • {failure}")
        print(
            "\n📌 D-226: التدخّل يستهدف الجذر — والجذر لا يُرى إلّا بقراءة الرسم القانوني.\n"
            "   رسمان لعلاقةٍ واحدة يتفرّقان، وهنا كان التفرّق صمتاً كاملاً لا خطأً مرئياً."
        )
        return 1

    canonical, micro, overlap = _measure_overlap()
    print(
        f"✅ رسم الشروط المسبقة: مجتازٌ واحد يقرأ الرسم القانوني، ولا رسم ثالث "
        f"(المنهاج {canonical} حافّة · الدقيقة {micro} · التقاطع {overlap} — "
        f"حبيبتان مختلفتان، والاتّحاد هو المقروء)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
