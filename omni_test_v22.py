"""
omni_test_v22.py — اختبار تجريبي حي للبروتوكول V22.0.

يُثبت ثلاثة ضمانات معمارية:

1. كاشف الإحباط (Frustration Detector): «مفهمتش» تُفعِّل التوجيه البصري.
2. الموجِّه التربوي (Pedagogical Router): «دفعة واحدة» → combinations_visualizer،
   ممنوع probability_tree.
3. حارس المستحيل (Impossible Guard): C(2,3) = 0 — لا قسمة على صفر، لا هلوسة.
4. عقد Next.js (JSON Contract): الحمولة تجتاز UIComponentPayload بلا استثناء.

الاستخدام:
    python omni_test_v22.py
"""

from __future__ import annotations

import json
import sys
import time

# ── الاستيراد ──────────────────────────────────────────────────────────────────

try:
    from app.contracts.streaming import UIComponentPayload
    from app.services.skills.probability_skill import (
        CombinationsModelOutput,
        ProbabilityCalculatorSkill,
        ProbabilityFailure,
        ProbabilityInput,
    )
except ImportError as exc:
    print(f"[FATAL] Import failed — run from project root with PYTHONPATH set: {exc}")
    sys.exit(1)

# ── ثوابت الاختبار ─────────────────────────────────────────────────────────────

# سياق BAC 2024: 11 كرة (2 بيضاء، 4 حمراء، 5 خضراء)، سحب 3 دفعة واحدة.
BAC_CONTEXT = (
    "كيس فيه 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. "
    "نسحب عشوائياً 3 كرات دفعة واحدة."
)

# رسالة الطالب المحبَط (Darija).
STUDENT_MESSAGE = "مفهمتش كيفاش حسبنا الكرات البيضاء"

# تاريخ المحادثة — يحمل سياق التمرين.
HISTORY = [
    {"role": "user", "content": "اعطني تمرين الاحتمالات"},
    {"role": "assistant", "content": BAC_CONTEXT},
]

# ── مساعدات ────────────────────────────────────────────────────────────────────

_PASS = "✅ PASS"
_FAIL = "❌ FAIL"
_results: list[tuple[str, bool, str]] = []


def _check(name: str, condition: bool, detail: str = "") -> None:
    status = _PASS if condition else _FAIL
    _results.append((name, condition, detail))
    print(f"  {status}  {name}" + (f" — {detail}" if detail else ""))
    if not condition:
        print(f"         ^ ASSERTION FAILED")


# ── الاختبارات ─────────────────────────────────────────────────────────────────


def test_frustration_detector(skill: ProbabilityCalculatorSkill) -> None:
    """الضمان 1: كاشف الإحباط يُفعَّل بـ «مفهمتش»."""
    print("\n[1] Frustration Detector")
    _check("مفهمتش → is_confusion=True", skill.is_confusion(STUDENT_MESSAGE))
    _check("لم أفهم → is_confusion=True", skill.is_confusion("لم أفهم شجرة الاحتمالات"))
    _check("كيفاش → is_confusion=True", skill.is_confusion("كيفاش نحسب الاحتمال"))
    _check("شكرا → is_confusion=False", not skill.is_confusion("شكرا جزيلا"))


def test_pedagogical_router(
    skill: ProbabilityCalculatorSkill,
) -> CombinationsModelOutput | None:
    """الضمان 2: «دفعة واحدة» → combinations_visualizer، ممنوع probability_tree."""
    print("\n[2] Pedagogical Router — Simultaneous vs Sequential")

    payload = ProbabilityInput(question=STUDENT_MESSAGE, history=HISTORY)
    t0 = time.perf_counter()
    result = skill.analyze(payload)
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    _check(
        "نتيجة CombinationsModelOutput (لا ProbabilityModelOutput)",
        isinstance(result, CombinationsModelOutput),
        f"got {type(result).__name__}",
    )

    if not isinstance(result, CombinationsModelOutput):
        if isinstance(result, ProbabilityFailure):
            print(f"         reason: {result.reason}")
        return None

    _check("component == combinations_visualizer", result.component == "combinations_visualizer")
    _check("draw_mode == simultaneous", result.draw_mode == "simultaneous")
    _check("n == 11 (حجم الكيس)", result.n == 11, f"n={result.n}")
    _check("k == 3 (عدد المسحوبات)", result.k == 3, f"k={result.k}")
    _check(
        "total_combinations == C(11,3) = 165",
        result.total_combinations == 165,
        f"got {result.total_combinations}",
    )
    _check(f"duration_ms ≥ 0 ({elapsed_ms}ms)", result.duration_ms >= 0)
    return result


def test_impossible_guard(result: CombinationsModelOutput) -> None:
    """الضمان 3: C(2,3) = 0 — الكرات البيضاء مستحيلة، لا هلوسة."""
    print("\n[3] Impossible Guard — C(2,3) = 0")

    groups = {g.label: g for g in result.groups}

    white = groups.get("كرة بيضاء")
    _check("مجموعة 'كرة بيضاء' موجودة", white is not None)
    if white:
        _check(
            f"C({white.count},3) = 0 (مستحيل — لا هلوسة)",
            white.favorable_combinations == 0,
            f"got {white.favorable_combinations}",
        )
        _check("count == 2 (عدد الكرات البيضاء)", white.count == 2, f"count={white.count}")

    red = groups.get("كرة حمراء")
    if red:
        _check(
            f"C({red.count},3) = 4 (حمراء صحيح)",
            red.favorable_combinations == 4,
            f"got {red.favorable_combinations}",
        )

    green = groups.get("كرة خضراء")
    if green:
        _check(
            f"C({green.count},3) = 10 (خضراء صحيح)",
            green.favorable_combinations == 10,
            f"got {green.favorable_combinations}",
        )

    _check(
        "same_group_favorable == 14 (4+0+10)",
        result.same_group_favorable == 14,
        f"got {result.same_group_favorable}",
    )


def test_nextjs_contract(result: CombinationsModelOutput) -> None:
    """الضمان 4: الحمولة تجتاز UIComponentPayload — لا 500 Error في Next.js."""
    print("\n[4] Next.js JSON Contract — UIComponentPayload")

    try:
        ui_payload = UIComponentPayload(
            component="combinations_visualizer",
            props=result.model_dump(),
            fallback_text=f"تأليفات السحب الآني: اختيار {result.k} من {result.n} كرة",
        )
        _check("UIComponentPayload صالح (لا ValidationError)", True)
        _check(
            "component في KNOWN_UI_COMPONENTS",
            ui_payload.component == "combinations_visualizer",
        )

        # تسلسل JSON كامل — يُثبت عدم وجود قيم غير قابلة للتسلسل.
        raw_json = ui_payload.model_dump_json()
        parsed = json.loads(raw_json)
        _check("JSON قابل للتسلسل والتحليل", True)
        _check("props.success == true", parsed["props"]["success"] is True)
        _check("props.draw_mode == simultaneous", parsed["props"]["draw_mode"] == "simultaneous")
        _check("props.groups قائمة غير فارغة", len(parsed["props"]["groups"]) > 0)

        # لا مفاتيح مجردة (Abstraction Ban — D-074).
        labels = [g["label"] for g in parsed["props"]["groups"]]
        abstract_symbols = {"A", "B", "Ā", "B̄", "B|A"}
        _check(
            "لا رموز مجردة في labels (D-074)",
            not any(lbl in abstract_symbols for lbl in labels),
            f"labels={labels}",
        )

        print("\n  --- حمولة JSON الكاملة ---")
        print(json.dumps(parsed, ensure_ascii=False, indent=2))

    except Exception as exc:
        _check(f"UIComponentPayload فشل: {exc}", False)


def test_sequential_stays_tree(skill: ProbabilityCalculatorSkill) -> None:
    """تحقق إضافي: «على التوالي» لا يزال يُنتج شجرة (لا انحدار)."""
    print("\n[5] Regression — Sequential stays a tree")
    from app.services.skills.probability_skill import ProbabilityModelOutput

    out = skill.analyze(
        "كيس فيه 11 كرة: 4 حمراء و7 خضراء. نسحب كرتين على التوالي وبدون إرجاع، احتمال"
    )
    _check(
        "على التوالي → ProbabilityModelOutput (شجرة)",
        isinstance(out, ProbabilityModelOutput),
        f"got {type(out).__name__}",
    )
    if isinstance(out, ProbabilityModelOutput):
        _check("component == probability_tree", out.component == "probability_tree")


def test_k_exceeds_n_guard(skill: ProbabilityCalculatorSkill) -> None:
    """حارس k > n: لا استثناء، لا قيمة غير صالحة."""
    print("\n[6] Impossible Guard — k > n (e.g. draw 5 from 2 white balls)")
    out = skill.analyze("كيس فيه كرتان بيضاوان فقط، نسحب 5 كرات دفعة واحدة، احتمال")
    _check(
        "k > n → ProbabilityFailure (لا crash، لا 1/0)",
        isinstance(out, ProbabilityFailure),
        f"got {type(out).__name__}",
    )


# ── نقطة الدخول ────────────────────────────────────────────────────────────────


def main() -> int:
    print("=" * 60)
    print("  omni_test_v22.py — CogniForge Protocol V22.0")
    print("  BAC 2024: 11 كرة (2 بيضاء، 4 حمراء، 5 خضراء) — سحب 3 دفعة واحدة")
    print("=" * 60)

    skill = ProbabilityCalculatorSkill()

    test_frustration_detector(skill)
    result = test_pedagogical_router(skill)

    if result is None:
        print("\n[ABORT] الموجِّه التربوي فشل — لا يمكن متابعة الاختبارات التالية.")
        return 1

    test_impossible_guard(result)
    test_nextjs_contract(result)
    test_sequential_stays_tree(skill)
    test_k_exceeds_n_guard(skill)

    # ── ملخص ──────────────────────────────────────────────────────────────────
    total = len(_results)
    passed = sum(1 for _, ok, _ in _results if ok)
    failed = total - passed

    print("\n" + "=" * 60)
    print(f"  النتيجة: {passed}/{total} اجتازت")
    if failed:
        print(f"  فشل: {failed} اختبار")
        for name, ok, detail in _results:
            if not ok:
                print(f"    ❌ {name}" + (f" — {detail}" if detail else ""))
    else:
        print("  ✅ جميع الاختبارات اجتازت — البروتوكول V22.0 مُثبَت")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
