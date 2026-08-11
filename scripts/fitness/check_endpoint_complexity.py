#!/usr/bin/env python3
"""ميزانيات التعقيد لطبقة API في الأوركستريتور — ratchet ثنائي الاتجاه.

## لماذا هذه البوّابة موجودة

قاست CodeScene `chat_with_agent_endpoint` عند **336 سطراً وتعقيدٍ 48 وتردّد تغييرٍ 43**
— أسوأ نقطةٍ ساخنة في المستودع، تحمل أربعة أعراضٍ معاً (شرطٌ مركّب · دالّةٌ مركّبة ·
طريقٌ وعر · تعقيدٌ متداخل عميق). والدالّة وحدها كانت **٢١٪** من `routes.py`.

لكنّ القياس الخارجي ليس فارضاً: CodeScene خدمةٌ خارجية، وتقريرها يصل بعد الدمج، ولا
يُفشِل PR. فالرقم الذي لا تحرسه آلةٌ **في مسار الدمج** يعود بعد أوّل PR عاجل — وهذا
بالضبط ما تقوله العقيدة الهندسية: *البيت المنهار لا يُبنى بقرارٍ واحد سيّئ بل بحاصل
جمع قراراتٍ صغيرة لم يحرسها شيء* (D-207).

## العقد

ثلاث آليات في بوّابةٍ واحدة:

1. **`BUDGETS`** — ميزانيات صريحة لدوالّ مُسمّاة. تُفشِل عند التجاوز. هذه هي التي
   تحرس ألّا تعود النقطة الساخنة.
2. **الدَّين المُجمَّد** (`endpoint_complexity_debt.json`) — أرقام اليوم لكلّ ما هو
   قائم، **تتقلّص فقط** وفي الاتجاهين (نموٌّ ⇒ أحمر، ودَينٌ أُغلق بلا تحديث الرقم
   ⇒ أحمر أيضاً — سابقة D-189). يشمل التوأمين `chat_ws_stategraph` و
   `admin_chat_ws_stategraph`: لا يُفكَّكان الآن (مسار الطالب الحيّ) لكنّهما **لا
   ينموان**.
3. **ميزانية الوافد الجديد** — أيّ دالّة أو ملفّ **غير موجود في الدَّين** يُحاكَم
   بالميزانية الافتراضية فوراً. فاستبدال دالّةٍ إلهية بوحدةٍ إلهية ليس تحسيناً،
   وهذه الآلية تجعله **مقيساً** لا مفترَضاً.

## المقياس (مُصرَّح لا مُصادَف — L12)

- `loc` = `end_lineno - lineno + 1` (المدى الفيزيائي للدالّة، بلا الديكوريتر).
- `cc`  = 1 + عدد عُقَد القرار (`If/For/AsyncFor/While/ExceptHandler/With/AsyncWith/
  Assert/IfExp/comprehension`) + مجموع (`len(BoolOp.values) - 1`).
- `nesting` = أقصى عمق تعشيشٍ للبنى الحاملة للكتل، **وتُحتسَب الدالّة المتداخلة
  مستوىً** — لأن مولّداً يُعرَّف داخل مُعالِج طلبٍ هو بالضبط شكل العطب هنا.

⚠️ الرقم لا يطابق CodeScene بالضرورة (قاست 48 وقِسنا 51 لنفس الدالّة، واتفقت الـ336).
هذا مقصود: **نحرس رقمنا نحن** فلا تختلف البوّابة مع نفسها، ولا نُحسِّن على مقياس
جهةٍ خارجية (قانون Goodhart — نُحسّن الواقع والأرقام تتبع).

المشروع يتطلّب Python 3.12+ (صيغة PEP 695): على 3.11 ترفع `parse_source` بدل أن
تشهد بنظافة ملفٍّ لم تقرأه (D-208 · البند ٦).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ast_util import parse_source, run_gate

REPO_ROOT = Path(__file__).resolve().parents[2]
API_DIR = REPO_ROOT / "microservices/orchestrator_service/src/api"
DEBT_FILE = Path(__file__).with_name("endpoint_complexity_debt.json")

#: ميزانية كلّ وافدٍ جديد — دالّة ليست في الدَّين المُجمَّد.
DEFAULT_FUNCTION_BUDGET = {"loc": 60, "cc": 10, "nesting": 3}

#: ميزانية كلّ ملفٍّ جديد — ملفّ ليس في الدَّين المُجمَّد.
DEFAULT_MODULE_LOC = 300

#: ميزانيات صريحة تتفوّق على الدَّين — لا تُرفَع إلّا بقرارٍ مكتوب (D-209 · الطبقة ٩).
BUDGETS: dict[str, dict[str, int]] = {
    "routes.py::chat_with_agent_endpoint": {"loc": 40, "cc": 6, "nesting": 2},
}

_DECISION = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.ExceptHandler,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.IfExp,
    ast.comprehension,
)

_NESTING = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
)


def _cyclomatic(node: ast.AST) -> int:
    total = 1
    for child in ast.walk(node):
        if isinstance(child, _DECISION):
            total += 1
        elif isinstance(child, ast.BoolOp):
            total += len(child.values) - 1
    return total


def _max_nesting(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        child_depth = depth + 1 if isinstance(child, _NESTING) else depth
        deepest = max(deepest, _max_nesting(child, child_depth))
    return deepest


def _measure(path: Path) -> dict[str, dict[str, int]]:
    """يقيس كلّ دالّة على المستوى الأعلى في الملفّ + الملفّ نفسه."""
    tree = parse_source(path)
    name = path.name
    found: dict[str, dict[str, int]] = {
        name: {"loc": len(path.read_text(encoding="utf-8").splitlines())}
    }
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        found[f"{name}::{node.name}"] = {
            "loc": node.end_lineno - node.lineno + 1,
            "cc": _cyclomatic(node),
            "nesting": _max_nesting(node),
        }
    return found


def _scan() -> dict[str, dict[str, int]]:
    measured: dict[str, dict[str, int]] = {}
    for path in sorted(API_DIR.glob("*.py")):
        measured.update(_measure(path))
    return measured


def _violations(key: str, actual: dict[str, int], budget: dict[str, int], why: str) -> list[str]:
    out: list[str] = []
    for metric, limit in budget.items():
        value = actual.get(metric)
        if value is not None and value > limit:
            out.append(f"❌ {key}: {metric}={value} يتجاوز {limit} ({why}).")
    return out


def main() -> int:
    current = _scan()

    if "--update" in sys.argv:
        DEBT_FILE.write_text(
            json.dumps(dict(sorted(current.items())), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"✅ baseline written: {len(current)} entries → {DEBT_FILE.name}")
        return 0

    if not DEBT_FILE.is_file():
        print(f"❌ ملفّ الدَّين مفقود: {DEBT_FILE.name}. شغّل `--update` مرّة لتثبيت الأساس.")
        return 1
    frozen: dict[str, dict[str, int]] = json.loads(DEBT_FILE.read_text(encoding="utf-8"))

    errors: list[str] = []

    for key, actual in sorted(current.items()):
        # (1) الميزانية الصريحة تتفوّق على كلّ شيء.
        if key in BUDGETS:
            errors += _violations(key, actual, BUDGETS[key], "ميزانية صريحة")
            continue

        # (3) وافدٌ جديد: يُحاكَم بالميزانية الافتراضية فوراً.
        if key not in frozen:
            budget = {"loc": DEFAULT_MODULE_LOC} if "::" not in key else DEFAULT_FUNCTION_BUDGET
            errors += _violations(key, actual, budget, "وافدٌ جديد — الميزانية الافتراضية")
            continue

        # (2) دَينٌ مُجمَّد: يتقلّص فقط.
        for metric, allowed in frozen[key].items():
            value = actual.get(metric)
            if value is None:
                continue
            if value > allowed:
                errors.append(
                    f"❌ {key}: {metric}={value} بينما الدَّين المُجمَّد {allowed} — نموّ ممنوع."
                )
            elif value < allowed:
                errors.append(
                    f"❌ {key}: {metric}={value} بينما الدَّين المُجمَّد {allowed}.\n"
                    f"   حدِّث الرقم (`--update`) — الخريطة تتبع الواقع أو تتقادم بصمت (D-188)."
                )

    # (2ب) إدخالٌ مُجمَّد اختفى: يُحدَّث صراحةً لا بصمت.
    for key in sorted(frozen):
        if key not in current:
            errors.append(
                f"❌ {key}: كان في الدَّين المُجمَّد واختفى.\n"
                f"   إن حُذف أو أُعيدت تسميته فحدِّث الرقم (`--update`) بقرارٍ مكتوب."
            )

    if errors:
        print("\n".join(errors))
        print(
            "\n📌 النقطة الساخنة لا تعود: `chat_with_agent_endpoint` كانت 336 سطراً "
            "وتعقيد 51 وعمق 13. راجع docs/architecture/AGENT_CHAT_RESPONSIBILITY_MAP.md"
        )
        return 1

    functions = sum(1 for key in current if "::" in key)
    print(
        f"✅ api complexity: {functions} دالّة في {len(current) - functions} ملفّاً "
        f"ضمن الميزانية — لا نموّ."
    )
    return 0


if __name__ == "__main__":
    sys.exit(run_gate(main))
