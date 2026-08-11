"""اختبارات بوّابة ميزانيات التعقيد — «حارسٌ لا يُثبَت أنه يصرخ ليس حارساً».

البوّابة وُلدت من نقطةٍ ساخنة حقيقية (`chat_with_agent_endpoint`: 336 سطراً · تعقيد 51
· عمق 13)، ووظيفتها منع عودتها. لكنّ فارضاً لا يُختبَر سلبياً يمرّ أخضرَ إلى الأبد —
و«الثمن الثالث» في العقيدة الهندسية هو بالضبط **صمتٌ يُقرأ نجاحاً** (D-207).

فلكلّ آلية من آلياتها الثلاث تجربةٌ سلبية مُثبَتة هنا:

1. **الميزانية الصريحة** — دالّةٌ مُسمّاة تتجاوز حدّها ⇒ أحمر.
2. **الدَّين المُجمَّد ثنائي الاتجاه** — النموّ أحمر، **والتقلّص بلا تحديث الرقم أحمر
   أيضاً** (سابقة D-189: خريطةٌ تتبع الواقع أو تتقادم بصمت).
3. **ميزانية الوافد الجديد** — دالّة/ملفّ خارج الدَّين يُحاكَم فوراً، فاستبدال دالّةٍ
   إلهية بوحدةٍ إلهية يُقاس ولا يُفترَض.

وبندٌ رابع: **البوّابة لا تشهد بنظافة ملفٍّ لم تقرأه** (D-208 · البند ٦).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "fitness"))

import check_endpoint_complexity as gate
from _ast_util import UnparsableSourceError, parse_source

# ── المقياس نفسه ────────────────────────────────────────────────────────────────


def _measure_src(tmp_path: Path, source: str) -> dict[str, dict[str, int]]:
    path = tmp_path / "sample.py"
    path.write_text(source, encoding="utf-8")
    return gate._measure(path)


def test_cyclomatic_counts_branches_and_boolean_operands(tmp_path: Path) -> None:
    """المقياس مُصرَّح لا مُصادَف (L12): كلّ عقدة قرار +1، وكلّ معامل منطقي إضافي +1."""
    measured = _measure_src(
        tmp_path,
        "def f(a, b, c):\n"
        "    if a and b and c:\n"  # +1 (If) +2 (BoolOp: 3 values - 1)
        "        return 1\n"
        "    for _ in range(3):\n"  # +1
        "        pass\n"
        "    return 0\n",
    )
    assert measured["sample.py::f"]["cc"] == 5  # 1 base + 1 + 2 + 1


def test_nested_function_counts_as_a_nesting_level(tmp_path: Path) -> None:
    """مولّدٌ يُعرَّف داخل مُعالِج طلبٍ هو شكل العطب هنا — فيُحتسَب مستوىً.

    الدالّة المقيسة نفسها عند العمق 0؛ فـ`inner` مستوىً 1 و`if` داخلها مستوىً 2.
    وهذا ما جعل المُعالِج الأصلي يقيس 13: مُغلَقتان + شرطٌ عميق داخلهما.
    """
    measured = _measure_src(
        tmp_path,
        "def outer():\n    def inner():\n        if True:\n            pass\n",
    )
    assert measured["sample.py::outer"]["nesting"] == 2

    flat = _measure_src(tmp_path, "def outer():\n    if True:\n        pass\n")
    assert flat["sample.py::outer"]["nesting"] == 1, "المُغلَقة تُضيف مستوىً حقيقياً"


def test_module_line_count_is_recorded_alongside_functions(tmp_path: Path) -> None:
    """الملفّ نفسه مُقاس — وإلّا نمت الوحدة بلا حارس."""
    measured = _measure_src(tmp_path, "x = 1\ny = 2\n")
    assert measured["sample.py"] == {"loc": 2}


# ── التجارب السلبية: البوّابة تصرخ فعلاً ────────────────────────────────────────


def _run(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *, debt: str, budgets: dict) -> int:
    debt_file = tmp_path / "debt.json"
    debt_file.write_text(debt, encoding="utf-8")
    monkeypatch.setattr(gate, "DEBT_FILE", debt_file)
    monkeypatch.setattr(gate, "BUDGETS", budgets)
    monkeypatch.setattr(sys, "argv", ["check_endpoint_complexity.py"])
    return gate.main()


def _api_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, source: str) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (api / "sample.py").write_text(source, encoding="utf-8")
    monkeypatch.setattr(gate, "API_DIR", api)


FAT = "def fat():\n" + "".join(f"    x{i} = {i}\n" for i in range(80))


SMALL = "def small():\n    pass\n"

#: (اسم الحالة، المصدر، الدَّين، الميزانيات، الرمز المتوقَّع، شظية الرسالة)
#:
#: مُجدوَلة لا مكرَّرة: ستّ حالاتٍ كانت ستّ دوالّ متطابقة البنية تختلف في أربع قيم —
#: وهو ما رصدته CodeScene بـ«Code Duplication» على هذا الملفّ. الجدول يُبقي كل حالةٍ
#: مقروءةً بسطرٍ واحد ويجعل إضافة السابعة سطراً لا دالّة.
GATE_CASES = [
    pytest.param(
        FAT,
        '{"sample.py": {"loc": 81}, "sample.py::fat": {"loc": 81, "cc": 1, "nesting": 0}}',
        {"sample.py::fat": {"loc": 40}},
        1,
        "يتجاوز 40",
        id="explicit-budget-overrun",
    ),
    pytest.param(
        FAT,
        '{"sample.py": {"loc": 81}, "sample.py::fat": {"loc": 10, "cc": 1, "nesting": 0}}',
        {},
        1,
        "نموّ ممنوع",
        id="growth-beyond-frozen-debt",
    ),
    pytest.param(
        SMALL,
        '{"sample.py": {"loc": 2}, "sample.py::small": {"loc": 99, "cc": 1, "nesting": 0}}',
        {},
        1,
        "حدِّث الرقم",
        id="shrink-without-updating-the-number",
    ),
    pytest.param(
        FAT,
        '{"sample.py": {"loc": 81}}',
        {},
        1,
        "وافدٌ جديد",
        id="new-oversized-function",
    ),
    pytest.param(
        SMALL,
        '{"sample.py": {"loc": 2}, "sample.py::gone": {"loc": 5, "cc": 1, "nesting": 0}}',
        {},
        1,
        "واختفى",
        id="vanished-debt-entry",
    ),
    pytest.param(
        SMALL,
        '{"sample.py": {"loc": 2}, "sample.py::small": {"loc": 2, "cc": 1, "nesting": 0}}',
        {},
        0,
        "✅",
        id="clean-tree-passes",
    ),
]


@pytest.mark.parametrize(("source", "debt", "budgets", "expected_rc", "expected_text"), GATE_CASES)
def test_each_gate_mechanism_behaves_as_declared(
    monkeypatch, tmp_path, capsys, source, debt, budgets, expected_rc, expected_text
) -> None:
    """كل آليةٍ مُثبَتة: ثلاث تفشل بالنموّ/التجاوز/الوافد، واثنتان بالصمت، وواحدة تنجح.

    الحالة الأخيرة ليست زينة: بوّابةٌ تفشل دائماً تُطفَأ بعد أوّل أسبوع.
    """
    _api_dir(monkeypatch, tmp_path, source)
    assert _run(monkeypatch, tmp_path, debt=debt, budgets=budgets) == expected_rc
    assert expected_text in capsys.readouterr().out


def test_an_unparsable_file_raises_instead_of_reporting_clean(tmp_path: Path) -> None:
    """D-208 · البند ٦: بوّابةٌ لا تقرأ ملفاً لا تُبلِّغ أنه نظيف."""
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n", encoding="utf-8")
    with pytest.raises(UnparsableSourceError):
        parse_source(bad)


# ── العقد الحيّ ─────────────────────────────────────────────────────────────────


def test_the_real_endpoint_is_inside_its_budget() -> None:
    """النقطة الساخنة نفسها: 336/51/13 ⇒ ضمن 40/6/2. هذا هو معيار القبول."""
    measured = gate._scan()["routes.py::chat_with_agent_endpoint"]
    budget = gate.BUDGETS["routes.py::chat_with_agent_endpoint"]
    assert measured["loc"] <= budget["loc"], measured
    assert measured["cc"] <= budget["cc"], measured
    assert measured["nesting"] <= budget["nesting"], measured


def test_the_endpoint_no_longer_declares_a_nested_generator() -> None:
    """الجذر البنيوي للعمق 13 كان مولّدَين مُعرَّفَين داخل مُعالِج الطلب."""
    tree = parse_source(gate.API_DIR / "routes.py")
    endpoint = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "chat_with_agent_endpoint"
    )
    nested = [
        node.name
        for node in ast.walk(endpoint)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node is not endpoint
    ]
    assert nested == [], f"عادت المُغلَقات إلى المُعالِج: {nested}"
