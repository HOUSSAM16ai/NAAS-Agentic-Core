#!/usr/bin/env python3
"""يفرض أن «التمرين قيد النقاش» له مصدرٌ واحد، وأن الوعد البصري يتبع حمولةً مُسلَّمة.

**لماذا هذه البوّابة موجودة (D-191 · ISS-140 ج/د/د-2):**

طالبٌ كتب تمرينه بنفسه («كيس فيه 12 كرة: 5 حمراء و4 خضراء و3 صفراء») تلقّى شرحاً على
كيسٍ آخر تماماً («4 حمراء، 2 بيضاء، 5 خضراء»). الجذر لم يكن سطراً خاطئاً بل **غياب
مصدرٍ واحد**: الحرفية ``"اعطني تمرين الاحتمالات 2024"`` كانت مكرَّرة في **٧** مواضع عبر
٤ ملفّات، تُغذّي ١٢ موضع استدعاء، و``_load_canonical_combinations`` كانت تستقبل
``question`` و**ترميه**. سبعة مصادر لا تتّفق إلا صدفةً — وقد اتّفقت على الجواب الخطأ.

وفي المسار نفسه كان الوعد البصري («إليك الشرح البصري المفصل… 🪄») يُبَثّ **بلا شرط**
بعد أن يُسقط المُطبِّع الحمولة إلى ``noop`` — فيقرأ الطالب وعداً لا يصل (§0: لا فشل صامت).

**ما تفرضه:**

1. الحرفية القانونية لها **موطن واحد**: ``app/services/skills/exercise_context.py``.
   الدَّين المُجمَّد **فارغ** ويتقلّص فقط (سابقة D-187 ``check_no_shell_true``).
2. مسار الاستخراج الوحيد **لا يقرأ نثر الحلّ النموذجي** (``load_exercise_content``).
3. مرحلة التسليم تربط بثّ النصّ المرافق **بحكم المُطبِّع** — لا ببثّ المكوّن.

القاعدة الثالثة تُؤكَّد على **الثابت** لا على سطرٍ بعينه (D-137): نفحص أن الحكم
مربوط باسمٍ يُقرأ قبل الوعد، لا أن سطراً حرفياً موجود.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]

RESOLVER = "app/services/skills/exercise_context.py"
DELIVERY = "app/infrastructure/clients/orchestrator/turn_preempts_delivery.py"

#: الحرفية القانونية لطلب التمرين المرجعي — موطنها الوحيد هو المُحلّ.
CANONICAL_LITERAL = "اعطني تمرين الاحتمالات 2024"

#: الدَّين المُجمَّد: ملفّات مسموح لها (مؤقتاً) بتكرار الحرفية. **فارغ — ويتقلّص فقط.**
FROZEN_DEBT: frozenset[str] = frozenset()

#: أشجار يُفحَص فيها التكرار. السكربتات والاختبارات مستثناة: الحرفية فيها **مُدخَل
#: مستخدم** (مسبار حيّ يكتب ما يكتبه الطالب) لا مصدرَ حقيقةٍ في مسار التشغيل.
SCANNED_ROOTS = ("app", "microservices", "shared")


def _tracked_python_files() -> list[Path]:
    files: list[Path] = []
    for root in SCANNED_ROOTS:
        base = REPO_ROOT / root
        if base.is_dir():
            files.extend(sorted(base.rglob("*.py")))
    return files


def _has_literal(path: Path) -> bool:
    """هل يحمل الملفّ الحرفية القانونية كـ**سلسلة في الكود**؟

    نستعمل AST لا ``in`` النصّي: التعليق الذي *يذكر* الطلب («… يجب أن يُعيد التمرين
    الحقيقي») ليس مصدراً ثانياً — والبوّابة التي تخلط الشرح بالكود تُعاقب التوثيق.
    وثوابت الـ docstring مستثناة لنفس السبب.
    """
    # ISS-149 (F1): يرفع — «لم أقرأه» ليست «نظيف».
    tree = parse_source(path)
    docstrings = {
        node.body[0].value
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    return any(
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and CANONICAL_LITERAL in node.value
        and node not in docstrings
        for node in ast.walk(tree)
    )


def _check_single_home() -> list[str]:
    """القاعدة 1: الحرفية القانونية لا تظهر كسلسلةِ كودٍ خارج المُحلّ."""
    errors: list[str] = []
    for path in _tracked_python_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == RESOLVER or rel in FROZEN_DEBT:
            continue
        if _has_literal(path):
            errors.append(
                f"❌ {rel}: تكرار الحرفية القانونية {CANONICAL_LITERAL!r}.\n"
                f"   استورد `CANONICAL_EXERCISE_QUERY` من {RESOLVER} بدلها — "
                f"مصدرٌ واحد لا سبعة (D-191 · ISS-140 د)."
            )
    return errors


def _check_stale_debt() -> list[str]:
    """الـratchet ثنائي الاتجاه: مدخل مُجمَّد لم يعد مخروقاً يجب أن يُحذَف."""
    errors: list[str] = []
    for rel in sorted(FROZEN_DEBT):
        path = REPO_ROOT / rel
        if not path.is_file():
            errors.append(f"❌ الدَّين المُجمَّد يذكر ملفاً غير موجود: {rel} — احذف المدخل.")
            continue
        if not _has_literal(path):
            errors.append(f"❌ {rel} نظيف الآن — احذفه من FROZEN_DEBT (الدَّين يتقلّص فقط).")
    return errors


def _check_extraction_never_reads_model_answer() -> list[str]:
    """القاعدة 2: مسار الاستخراج لا يلمس الملف الكامل (نثر الحلّ — ISS-120)."""
    resolver_path = REPO_ROOT / RESOLVER
    if not resolver_path.is_file():
        return [f"❌ {RESOLVER} مفقود — المُحلّ الواحد هو شرط القاعدة كلّها (D-191)."]
    resolver = resolver_path.read_text(encoding="utf-8")
    if "load_exercise_content(" in resolver:
        return [
            f"❌ {RESOLVER}: يقرأ الملف الكامل (نثر الحلّ النموذجي).\n"
            f"   الاستخراج يقرأ كياناتٍ مهيكلة أو أسئلة-فقط حصراً (ISS-120 · D-153)."
        ]
    if "load_exercise_questions_only(" not in resolver:
        return [f"❌ {RESOLVER}: فقدَ قراءة أسئلة-فقط — حارس ISS-120 مفقود."]
    return []


def _check_promise_follows_delivery() -> list[str]:
    """القاعدة 3: النصّ المرافق مشروط بحكم المُطبِّع (ثابتٌ لا سطر — D-137).

    نقرأ ``_stage_calculated_ui`` بـAST: يجب أن يوجد اسمٌ يُسنَد من مقارنةِ نوع الحدث
    المُطبَّع (حكم التسليم)، وأن يُقرأ ذلك الاسم داخل المرحلة. غيابه يعني أن الحكم
    يُرمى مجدداً — وهي بالضبط حالة ISS-140 ج.
    """
    tree = ast.parse((REPO_ROOT / DELIVERY).read_text(encoding="utf-8"))
    stage = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "_stage_calculated_ui"
        ),
        None,
    )
    if stage is None:
        return [f"❌ {DELIVERY}: لم أجد `_stage_calculated_ui` — حُدِّث اسم المرحلة؟"]

    assigned: set[str] = set()
    for node in ast.walk(stage):
        if isinstance(node, ast.Assign) and isinstance(node.value, (ast.Compare, ast.BoolOp)):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned.add(target.id)
    verdict_names = {name for name in assigned if "deliver" in name.lower()}
    if not verdict_names:
        return [
            f"❌ {DELIVERY}: حكم المُطبِّع على `ui_component` غير مربوط باسم.\n"
            f"   القاعدة (D-191 · ISS-140 ج): الكمّامة والنصّ المرافق يبرّرهما المكوّن\n"
            f"   **المُسلَّم**، لا نيّة تسليمه. بلا هذا الربط يعود الوعد بلا حمولة."
        ]
    read_names = {node.id for node in ast.walk(stage) if isinstance(node, ast.Name)}
    if not (verdict_names & read_names):
        return [f"❌ {DELIVERY}: حكم التسليم مُسنَد ولا يُقرأ — الوعد ما زال بلا شرط."]
    return []


def main() -> int:
    errors: list[str] = []
    errors += _check_single_home()
    errors += _check_stale_debt()
    errors += _check_extraction_never_reads_model_answer()
    errors += _check_promise_follows_delivery()

    if errors:
        print("\n".join(errors))
        print(
            "\n📌 D-191 (ISS-140): التمرين قيد النقاش مصدره واحد وأوّلُه نصّ الطالب؛\n"
            "   ولا يُطبَع رقمٌ لم يذكره الطالب بلا تصريح؛ ولا وعدَ بصريّ بلا حمولة."
        )
        return 1
    print(
        "✅ exercise-context single source: الحرفية القانونية في موطنٍ واحد، "
        "والاستخراج لا يرى نثر الحلّ، والوعد يتبع حمولةً مُسلَّمة."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
