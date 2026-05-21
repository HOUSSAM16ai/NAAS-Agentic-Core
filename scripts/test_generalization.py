#!/usr/bin/env python3
"""
Protocol V15.0 — Generalization Stress-Test (Anti-Overfitting).

يُثبت أن ``ProbabilityCalculatorSkill`` ليس مخصّصاً لـ«الكرات في الكيس»، بل
يعمل عبر أنماط معمّمة (Total Universe, Sub-events, Conditional Branches) على
سياقات تربوية عربية مختلفة كلياً: نرد، مصنع (Bayesian)، بطاقات.

التشغيل المباشر (live engine):
    python scripts/test_generalization.py

كلٌّ من الحالات يطبع حمولة JSON الحقيقية (نفس ما يُبثّ كـ ui_component) ويتحقق
من أن الكسور محسوبة ديناميكياً (3/6، 60/100، 2/100، 3/8) لا قيماً وهمية.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.skills.probability_skill import (
    ProbabilityCalculatorSkill,
    ProbabilityModelOutput,
)


def _flatten(tree: dict, acc: list[tuple[str, int, int]]) -> None:
    acc.append((tree.get("label", ""), tree.get("p_num", -1), tree.get("p_den", -1)))
    for child in tree.get("children", []) or []:
        _flatten(child, acc)


def _find(pairs: list[tuple[str, int, int]], substr: str, num: int, den: int) -> bool:
    return any(substr in lbl and pn == num and pd == den for lbl, pn, pd in pairs)


def _run(name: str, question: str) -> ProbabilityModelOutput:
    skill = ProbabilityCalculatorSkill()
    out = skill.analyze(question)
    print(f"\n{'=' * 78}\n{name}\n{'=' * 78}")
    print(f"السؤال: {question}\n")
    if not isinstance(out, ProbabilityModelOutput):
        print(f"❌ FAILURE: {out.reason}")
        raise AssertionError(f"{name}: engine returned failure ({out.reason})")
    print(f"strategy={out.strategy} | total={out.total} | with_replacement={out.with_replacement}")
    print("composition (level-1, dynamically calculated fractions):")
    for c in out.composition:
        print(f"   • {c.label}: P = {c.p_num}/{c.p_den}  ≈ {c.p_decimal}")
    print("\nRAW JSON ui_component payload:")
    payload = {
        "type": "ui_component",
        "payload": {
            "component": "probability_tree",
            "props": {
                "title": out.title,
                "is_illustrative": False,
                "calculated": True,
                "with_replacement": out.with_replacement,
                "total": out.total,
                "strategy": out.strategy,
                "composition": [c.model_dump() for c in out.composition],
                "tree": out.tree,
            },
            "fallback_text": "شجرة احتمالات (نص بديل).",
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return out


def main() -> int:
    failures: list[str] = []

    # ── Test Case 1: The Dice (حجر النرد) ──────────────────────────────────────
    try:
        out = _run(
            "Test Case 1 — حجر النرد (Dice)",
            "نرمي حجر نرد غير مزيف مرقم من 1 إلى 6. ما هو احتمال الحصول على رقم زوجي؟",
        )
        pairs: list[tuple[str, int, int]] = []
        _flatten(out.tree, pairs)
        assert _find(pairs, "زوجي", 3, 6), "expected رقم زوجي = 3/6"
        assert _find(pairs, "فردي", 3, 6), "expected رقم فردي = 3/6"
        print("\n✅ Test Case 1 PASS — رقم زوجي 3/6 و رقم فردي 3/6")
    except AssertionError as e:
        failures.append(f"Dice: {e}")
        print(f"\n❌ Test Case 1 FAIL — {e}")

    # ── Test Case 2: Factory Defects (Bayesian conditional) ─────────────────────
    try:
        out = _run(
            "Test Case 2 — مصنع الهواتف (Conditional / Bayesian)",
            "مصنع ينتج هواتف. الآلة A تنتج 60% من الهواتف، والآلة B تنتج 40%. "
            "نسبة الهواتف المعيبة من الآلة A هي 2%، ومن الآلة B هي 5%. ارسم شجرة الاحتمالات.",
        )
        pairs = []
        _flatten(out.tree, pairs)
        assert _find(pairs, "A", 60, 100), "expected الآلة A = 60/100"
        assert _find(pairs, "B", 40, 100), "expected الآلة B = 40/100"
        assert _find(pairs, "معيب", 2, 100), "expected معيب (A) = 2/100"
        assert _find(pairs, "معيب", 5, 100), "expected معيب (B) = 5/100"
        print("\n✅ Test Case 2 PASS — A 60/100, B 40/100, معيب 2/100 و 5/100")
    except AssertionError as e:
        failures.append(f"Factory: {e}")
        print(f"\n❌ Test Case 2 FAIL — {e}")

    # ── Test Case 3: The Cards (سحب بطاقات) ─────────────────────────────────────
    try:
        out = _run(
            "Test Case 3 — البطاقات (Cards, with replacement)",
            "علبة بها 8 بطاقات: 3 تحمل الرقم 1، و 5 تحمل الرقم 2. "
            "نسحب بطاقتين على التوالي مع الإرجاع.",
        )
        pairs = []
        _flatten(out.tree, pairs)
        assert _find(pairs, "1", 3, 8), "expected بطاقة رقم 1 = 3/8"
        assert _find(pairs, "2", 5, 8), "expected بطاقة رقم 2 = 5/8"
        assert out.with_replacement is True, "expected with_replacement=True"
        # السحب الثاني (مع الإرجاع) يطابق الأول
        second_level = list(out.tree["children"][0].get("children", []))
        assert any(n["p_num"] == 3 and n["p_den"] == 8 for n in second_level), (
            "second draw must match first (3/8)"
        )
        print("\n✅ Test Case 3 PASS — بطاقة 1 = 3/8, بطاقة 2 = 5/8, السحب الثاني مطابق")
    except AssertionError as e:
        failures.append(f"Cards: {e}")
        print(f"\n❌ Test Case 3 FAIL — {e}")

    # ── Regression: V14 urn (4/11) must still work ──────────────────────────────
    try:
        out = _run(
            "Regression — كيس الكرات (V14, P(Red)=4/11)",
            "يحتوي كيس على 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. "
            "نسحب 3 كرات على التوالي وبدون إرجاع، احسب احتمال سحب كرة حمراء",
        )
        assert any(
            c.label == "كرة حمراء" and c.p_num == 4 and c.p_den == 11 for c in out.composition
        )
        print("\n✅ Regression PASS — P(كرة حمراء) = 4/11")
    except AssertionError as e:
        failures.append(f"Urn: {e}")
        print(f"\n❌ Regression FAIL — {e}")

    print(f"\n{'=' * 78}")
    if failures:
        print(f"❌ {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"   - {f}")
        return 1
    print("🎉 ALL GENERALIZATION CASES PASS — engine is universal, not hardcoded.")
    print(f"{'=' * 78}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
