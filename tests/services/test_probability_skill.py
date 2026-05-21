"""
ProbabilityCalculatorSkill — unit tests (D-075/D-076 · Protocol V14.0/V15.0).

يغطي:
  • الحساب الحقيقي (P=count/total) لا 0.5 الوهمية.
  • التعميم (Anti-Overfitting): نرد، قطعة نقدية، مصنع شرطي، بطاقات، كرات.
  • السحب بدون/مع إرجاع (احتمالات شرطية دقيقة).
  • حالات الفشل المنظَّم (لا استثناءات).
  • سلامة العقد Pydantic (كسور تربوية + علم calculated).
"""

from __future__ import annotations

import pytest

from app.services.skills.probability_skill import (
    CompositionItem,
    ProbabilityCalculatorSkill,
    ProbabilityFailure,
    ProbabilityInput,
    ProbabilityModelOutput,
)


def _skill() -> ProbabilityCalculatorSkill:
    return ProbabilityCalculatorSkill()


def _flatten(tree: dict, acc: list[tuple[str, int, int]]) -> None:
    acc.append((tree.get("label", ""), tree.get("p_num", -1), tree.get("p_den", -1)))
    for child in tree.get("children", []) or []:
        _flatten(child, acc)


def _pairs(model: ProbabilityModelOutput) -> list[tuple[str, int, int]]:
    acc: list[tuple[str, int, int]] = []
    _flatten(model.tree, acc)
    return acc


# ─── Real calculation (no dumb 0.5) — V14 urn ───────────────────────────────────


def test_urn_real_fraction_4_over_11() -> None:
    out = _skill().analyze(
        "يحتوي كيس على 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. "
        "احسب احتمال سحب كرة حمراء"
    )
    assert isinstance(out, ProbabilityModelOutput)
    assert out.total == 11
    red = next(c for c in out.composition if c.label == "كرة حمراء")
    assert (red.p_num, red.p_den) == (4, 11)
    white = next(c for c in out.composition if c.label == "كرة بيضاء")
    assert (white.p_num, white.p_den) == (2, 11)
    green = next(c for c in out.composition if c.label == "كرة خضراء")
    assert (green.p_num, green.p_den) == (5, 11)


def test_urn_without_replacement_conditional() -> None:
    out = _skill().analyze(
        "كيس فيه 11 كرة: أربع كرات حمراء وسبع كرات خضراء. "
        "نسحب كرتين على التوالي وبدون إرجاع. ما احتمال الحصول على كرة حمراء؟"
    )
    assert isinstance(out, ProbabilityModelOutput)
    assert out.with_replacement is False
    pairs = _pairs(out)
    # المستوى الأول: حمراء 4/11
    assert any("حمراء" in lbl and pn == 4 and pd == 11 for lbl, pn, pd in pairs)
    # المستوى الثاني الشرطي: بعد سحب حمراء يبقى 3 حمراء من 10
    assert any("حمراء" in lbl and pn == 3 and pd == 10 for lbl, pn, pd in pairs)


# ─── Generalization — V15 dice ───────────────────────────────────────────────────


def test_dice_even_odd_3_over_6() -> None:
    out = _skill().analyze("نرمي حجر نرد مرقم من 1 إلى 6. ما احتمال الحصول على رقم زوجي؟")
    assert isinstance(out, ProbabilityModelOutput)
    assert out.strategy == "universe"
    assert out.total == 6
    pairs = _pairs(out)
    assert any("زوجي" in lbl and pn == 3 and pd == 6 for lbl, pn, pd in pairs)
    assert any("فردي" in lbl and pn == 3 and pd == 6 for lbl, pn, pd in pairs)


def test_dice_custom_faces() -> None:
    out = _skill().analyze("نرمي حجر نرد مرقم من 1 إلى 8، احتمال رقم زوجي؟")
    assert isinstance(out, ProbabilityModelOutput)
    assert out.total == 8
    pairs = _pairs(out)
    assert any("زوجي" in lbl and pn == 4 and pd == 8 for lbl, pn, pd in pairs)


def test_coin_half() -> None:
    out = _skill().analyze("نرمي قطعة نقدية. ما احتمال ظهور الوجه؟ احتمال")
    assert isinstance(out, ProbabilityModelOutput)
    assert out.total == 2
    pairs = _pairs(out)
    assert any(pn == 1 and pd == 2 for _l, pn, pd in pairs)


# ─── Generalization — V15 factory (Bayesian conditional) ─────────────────────────


def test_factory_conditional_tree() -> None:
    out = _skill().analyze(
        "مصنع ينتج هواتف. الآلة A تنتج 60% من الهواتف، والآلة B تنتج 40%. "
        "نسبة الهواتف المعيبة من الآلة A هي 2%، ومن الآلة B هي 5%. ارسم شجرة الاحتمالات."
    )
    assert isinstance(out, ProbabilityModelOutput)
    assert out.strategy == "conditional"
    assert out.total == 100
    pairs = _pairs(out)
    assert any("A" in lbl and pn == 60 and pd == 100 for lbl, pn, pd in pairs)
    assert any("B" in lbl and pn == 40 and pd == 100 for lbl, pn, pd in pairs)
    # الفروع الشرطية للعيوب
    assert any("معيب" in lbl and pn == 2 and pd == 100 for lbl, pn, pd in pairs)
    assert any("معيب" in lbl and pn == 5 and pd == 100 for lbl, pn, pd in pairs)
    assert any("سليم" in lbl and pn == 98 and pd == 100 for lbl, pn, pd in pairs)


def test_factory_labels_beautified() -> None:
    out = _skill().analyze(
        "مصنع: الآلة A تنتج 70% والآلة B تنتج 30%. نسبة المعيب من الآلة A هي 3% ومن الآلة B هي 6%."
    )
    assert isinstance(out, ProbabilityModelOutput)
    assert any("الآلة" in c.label for c in out.composition)
    assert all("الالة" not in c.label for c in out.composition)


# ─── Generalization — V15 cards (with replacement) ───────────────────────────────


def test_cards_with_replacement() -> None:
    out = _skill().analyze(
        "علبة بها 8 بطاقات: 3 تحمل الرقم 1، و 5 تحمل الرقم 2. نسحب بطاقتين على التوالي مع الإرجاع."
    )
    assert isinstance(out, ProbabilityModelOutput)
    assert out.total == 8
    assert out.with_replacement is True
    pairs = _pairs(out)
    assert any("1" in lbl and pn == 3 and pd == 8 for lbl, pn, pd in pairs)
    assert any("2" in lbl and pn == 5 and pd == 8 for lbl, pn, pd in pairs)
    # السحب الثاني (مع الإرجاع) يطابق الأول
    first_branch = out.tree["children"][0]
    assert any(n["p_num"] == 3 and n["p_den"] == 8 for n in first_branch.get("children", []))


# ─── Failure modes (structured, never raises) ────────────────────────────────────


def test_no_probability_context_fails() -> None:
    out = _skill().analyze("اشرح لي قانون نيوتن الثاني")
    assert isinstance(out, ProbabilityFailure)
    assert out.reason == "no_probability_context"


def test_probability_word_but_no_model_fails() -> None:
    out = _skill().analyze("ما هو تعريف الاحتمال في الرياضيات؟")
    assert isinstance(out, ProbabilityFailure)


def test_string_input_accepted() -> None:
    out = _skill().analyze("كيس فيه 3 كرات حمراء و2 بيضاء، احتمال سحب كرة حمراء")
    assert isinstance(out, ProbabilityModelOutput)
    red = next(c for c in out.composition if c.label == "كرة حمراء")
    assert (red.p_num, red.p_den) == (3, 5)


# ─── History context (follow-up question) ────────────────────────────────────────


def test_composition_extracted_from_history() -> None:
    history = [
        {"role": "user", "content": "كيس فيه 4 كرات حمراء و 7 كرات بيضاء"},
        {"role": "assistant", "content": "حسناً، الكيس يحتوي 11 كرة."},
    ]
    out = _skill().analyze(ProbabilityInput(question="ارسم لي شجرة الاحتمالات", history=history))
    assert isinstance(out, ProbabilityModelOutput)
    assert any(c.label == "كرة حمراء" and c.p_num == 4 for c in out.composition)


# ─── Contract integrity ──────────────────────────────────────────────────────────


def test_output_marks_calculated_real_values() -> None:
    out = _skill().analyze("نرمي نرد، احتمال رقم زوجي؟")
    assert isinstance(out, ProbabilityModelOutput)
    assert out.success is True
    assert out.skill == "probability_calculation"
    # كل عقدة في الشجرة تحمل كسراً صحيحاً (p_num/p_den) لا قيمة عشرية مجرّدة فقط
    for _lbl, pn, pd in _pairs(out):
        assert isinstance(pn, int) and isinstance(pd, int) and pd >= 1


def test_composition_item_validation() -> None:
    item = CompositionItem(label="كرة حمراء", count=4, p_num=4, p_den=11, p_decimal=0.3636)
    assert item.p_num == 4
    with pytest.raises(Exception):  # noqa: B017 — مقام صفر مرفوض
        CompositionItem(label="x", count=1, p_num=1, p_den=0, p_decimal=0.5)
