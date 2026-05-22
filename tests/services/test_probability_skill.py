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
    # D-078: الجذر بلا احتمال (لا p_num) — نتخطّاه ولا نُضمّنه في الفحص.
    if "p_num" in tree:
        acc.append((tree.get("label", ""), tree["p_num"], tree["p_den"]))
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


# ─── D-077 (V17.0) — no garbage fractions, accurate Arabic parsing ───────────────


def _all_nodes(tree: dict, acc: list[tuple[int, int]]) -> None:
    # D-078: الجذر بلا احتمال (لا p_num) — نتخطّاه.
    if "p_num" in tree:
        acc.append((tree["p_num"], tree["p_den"]))
    for child in tree.get("children", []) or []:
        _all_nodes(child, acc)


def test_no_division_by_zero_or_overflow_anywhere() -> None:
    """كل عقدة في كل سيناريو يجب أن تحقّق 1 ≤ p_den و 0 ≤ p_num ≤ p_den."""
    questions = [
        "كيس فيه كرتان: واحدة بيضاء وواحدة حمراء، نسحب كرتين بدون إرجاع، احتمال",
        "كيس فيه كرتان بيضاوان، نسحب 3 كرات بدون إرجاع، احتمال شجرة",
        "نرمي حجر نرد، احتمال رقم زوجي؟",
        "مصنع: الآلة A تنتج 60% والآلة B تنتج 40%. نسبة المعيب من A هي 2% ومن B هي 5%.",
        "علبة بها 8 بطاقات: 3 رقم 1 و5 رقم 2، نسحب بطاقتين مع الإرجاع",
    ]
    for q in questions:
        out = _skill().analyze(q)
        if not isinstance(out, ProbabilityModelOutput):
            continue
        nodes: list[tuple[int, int]] = []
        _all_nodes(out.tree, nodes)
        for pn, pd in nodes:
            assert pd >= 1, f"division by zero (p_den={pd}) in: {q}"
            assert 0 <= pn <= pd, f"invalid fraction {pn}/{pd} in: {q}"


def test_draw_count_not_mistaken_for_total() -> None:
    """«نسحب 3 كرات» = عدد سحبات لا حجم الكيس (regression: كان total=3 خطأً)."""
    out = _skill().analyze("كيس فيه كرتان بيضاوان، نسحب 3 كرات بدون إرجاع، احتمال")
    assert isinstance(out, ProbabilityModelOutput)
    assert out.total == 2, (
        f"total must be the urn size (2), not the draw count (3); got {out.total}"
    )


def test_tiny_urn_no_degenerate_second_level() -> None:
    """كيس من كرتين بدون إرجاع لا يولّد فروعاً منحلّة (0/1، 1/1)."""
    out = _skill().analyze("كيس فيه كرتان: واحدة بيضاء وواحدة حمراء، نسحب كرتين بدون إرجاع، احتمال")
    assert isinstance(out, ProbabilityModelOutput)
    nodes: list[tuple[int, int]] = []
    _all_nodes(out.tree, nodes)
    # لا عقدة فرعية بمقام 1 (التي تُنتج 0/1 أو 1/1)
    assert all(pd >= 2 or (pn, pd) == (1, 1) for pn, pd in nodes), (
        f"degenerate /1 sub-branches present: {nodes}"
    )


# ─── D-078 (V19.0) — Simultaneous vs Sequential router + frustration + no-1/1-root ─


def test_simultaneous_routes_to_combinations_not_tree() -> None:
    """«دفعة واحدة» = سحب آني → CombinationsModelOutput، ممنوع شجرة تتابعية."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(
        "كيس فيه 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. "
        "نسحب عشوائياً 3 كرات دفعة واحدة. احتمال"
    )
    assert isinstance(out, CombinationsModelOutput)
    assert out.component == "combinations_visualizer"
    assert out.n == 11
    assert out.k == 3
    assert out.total_combinations == 165  # C(11,3)
    fav = {g.label: g.favorable_combinations for g in out.groups}
    assert fav["كرة حمراء"] == 4  # C(4,3)
    assert fav["كرة بيضاء"] == 0  # C(2,3) = 0
    assert fav["كرة خضراء"] == 10  # C(5,3)
    assert out.same_group_favorable == 14  # 4 + 0 + 10  → P(3 same) = 14/165


def test_sequential_stays_a_tree() -> None:
    out = _skill().analyze(
        "كيس فيه 11 كرة: 4 حمراء و7 خضراء. نسحب كرتين على التوالي وبدون إرجاع، احتمال"
    )
    assert isinstance(out, ProbabilityModelOutput)
    assert out.component == "probability_tree"


def test_simultaneous_never_returns_tree_for_bac2024() -> None:
    """Regression V19: السحب الآني لا يُنتج شجرة احتمالات أبداً."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(
        "التمرين الأول: نسحب عشوائيا 3 كرات دفعة واحدة من كيس فيه "
        "4 كرات حمراء و5 كرات خضراء وكرتان بيضاوان"
    )
    assert isinstance(out, CombinationsModelOutput)
    assert not hasattr(out, "tree")


def test_frustration_detector_signals() -> None:
    skill = _skill()
    assert skill.is_confusion("مفهمتش كيفاش حسبنا الاحتمال") is True
    assert skill.is_confusion("لم أفهم شجرة الاحتمالات") is True
    assert skill.is_confusion("كيفاش نحسب") is True
    assert skill.is_confusion("اشرح لي") is True
    assert skill.is_confusion("شكرا جزيلا") is False


def test_confusion_followup_routes_to_combinations_via_history() -> None:
    """«مفهمتش» بعد تمرين سحب آني → combinations (سياق المحادثة يحفظ التركيبة)."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    bac = "كيس فيه 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. نسحب 3 كرات دفعة واحدة."
    history = [
        {"role": "user", "content": "اعطني تمرين الاحتمالات"},
        {"role": "assistant", "content": bac},
    ]
    out = _skill().analyze(
        ProbabilityInput(question="مفهمتش كيفاش حسبنا الاحتمال", history=history)
    )
    assert isinstance(out, CombinationsModelOutput)
    assert out.k == 3 and out.n == 11


def test_tree_root_has_no_dummy_probability() -> None:
    """D-078: أُلغي جذر 1/1 الوهمي — الجذر بلا p_num/p_den."""
    out = _skill().analyze("كيس فيه 4 حمراء و7 خضراء. نسحب كرتين على التوالي وبدون إرجاع، احتمال")
    assert isinstance(out, ProbabilityModelOutput)
    assert "p_num" not in out.tree
    assert "p_den" not in out.tree
    assert out.tree["label"] == "البداية"


def test_combinations_safe_when_k_exceeds_total() -> None:
    """k > n لا يُنتج استثناءً ولا قيمة غير صالحة."""
    out = _skill().analyze("كيس فيه كرتان حمراوان، نسحب 5 كرات دفعة واحدة، احتمال")
    # k=5 > n=2 → fails cleanly (no tree fallback, no crash)
    assert isinstance(out, ProbabilityFailure)


def test_composition_item_validation() -> None:
    item = CompositionItem(label="كرة حمراء", count=4, p_num=4, p_den=11, p_decimal=0.3636)
    assert item.p_num == 4
    with pytest.raises(Exception):  # noqa: B017 — مقام صفر مرفوض
        CompositionItem(label="x", count=1, p_num=1, p_den=0, p_decimal=0.5)


# ── Protocol V26.2 — الحالة المستحيلة (Visual Pedagogy short-circuit) ──────────────

_BAC_URN = (
    "يحتوي كيس على 11 كرة: كرتان بيضاوان مرقمتان بـ 1 و 3، وأربع كرات حمراء، وخمس كرات خضراء."
)


def test_impossible_draw_short_circuits_to_pedagogical_payload() -> None:
    """V26.2: سحب 3 بيضاء من كيس فيه 2 بيضاء → ImpossibleCaseOutput لا حساب."""
    from app.services.skills.probability_skill import ImpossibleCaseOutput

    out = _skill().analyze(
        ProbabilityInput(
            question="كيفاش نسحب 3 كرات بيضاء في نفس الوقت؟",
            history=[{"role": "user", "content": _BAC_URN}],
        )
    )
    assert isinstance(out, ImpossibleCaseOutput)
    assert out.ui_mode == "impossible_case"
    assert out.component == "impossible_draw_animation"
    assert out.numerical_state.available_items == 2
    assert out.numerical_state.requested_items == 3
    assert out.numerical_state.item_color == "white"
    assert out.visual_directives.fallback_math is None
    assert out.visual_directives.animation_hint == "bag_shake"
    assert out.pedagogical_message


def test_impossible_case_emits_no_degenerate_math() -> None:
    """البنية لا تحوي أي مفاتيح حساب (tree/total_combinations/composition)."""
    from app.services.skills.probability_skill import ImpossibleCaseOutput

    out = _skill().analyze(
        ProbabilityInput(
            question="كيفاش نسحب 3 كرات بيضاء في نفس الوقت؟",
            history=[{"role": "user", "content": _BAC_URN}],
        )
    )
    assert isinstance(out, ImpossibleCaseOutput)
    dumped = out.model_dump()
    for forbidden in ("tree", "total_combinations", "composition", "groups"):
        assert forbidden not in dumped


def test_impossible_takes_priority_over_combinations() -> None:
    """الحالة المستحيلة لها الأولوية على مسار التأليفات (combinations)."""
    from app.services.skills.probability_skill import (
        CombinationsModelOutput,
        ImpossibleCaseOutput,
    )

    out = _skill().analyze(
        ProbabilityInput(
            question="نسحب 3 كرات بيضاء دفعة واحدة",
            history=[{"role": "user", "content": _BAC_URN}],
        )
    )
    assert isinstance(out, ImpossibleCaseOutput)
    assert not isinstance(out, CombinationsModelOutput)


def test_possible_draw_still_computes_not_impossible() -> None:
    """سحب ممكن (3 خضراء من 5 خضراء) لا يُفعّل الحالة المستحيلة."""
    from app.services.skills.probability_skill import ImpossibleCaseOutput

    out = _skill().analyze(
        ProbabilityInput(
            question="نسحب 3 كرات خضراء دفعة واحدة",
            history=[{"role": "user", "content": _BAC_URN}],
        )
    )
    assert not isinstance(out, ImpossibleCaseOutput)


def test_with_replacement_is_not_impossible() -> None:
    """مع الإرجاع: سحب 3 بيضاء من 2 ممكن (لا استحالة) → ليس ImpossibleCaseOutput."""
    from app.services.skills.probability_skill import ImpossibleCaseOutput

    out = _skill().analyze(
        ProbabilityInput(
            question="نسحب 3 كرات بيضاء مع الإرجاع",
            history=[{"role": "user", "content": _BAC_URN}],
        )
    )
    assert not isinstance(out, ImpossibleCaseOutput)


# ─── V30.0: Sub-Group Leak Surgery + Deep Dive Generative UI ─────────────────────

_BAC_URN_SIMUL = (
    "يحتوي كيس على 11 كرة: كرتان بيضاوان، أربع كرات حمراء، خمس كرات خضراء. نسحب 3 كرات دفعة واحدة."
)


def test_subgroup_leak_guardrail_no_c_2_3_equals_zero() -> None:
    """V30.0: المجموعة المستحيلة (بيضاء 2، سحب 3) لا تُخرِج C_2^3=0 مضلِّلاً."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(_BAC_URN_SIMUL)
    assert isinstance(out, CombinationsModelOutput)
    white = next(g for g in out.groups if "بيضاء" in g.label)
    assert white.is_possible is False
    assert white.favorable_combinations == 0
    assert "مستحيل" in white.pedagogical_string
    # حارس صريح: لا صيغة C(...) في رسالة المجموعة المستحيلة
    assert "C(" not in white.pedagogical_string


def test_subgroup_possible_groups_carry_formula_string() -> None:
    """V30.0: المجموعات الممكنة تحمل is_possible=True + صيغة C(count,k)."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(_BAC_URN_SIMUL)
    assert isinstance(out, CombinationsModelOutput)
    red = next(g for g in out.groups if "حمراء" in g.label)
    green = next(g for g in out.groups if "خضراء" in g.label)
    assert red.is_possible is True and red.favorable_combinations == 4
    assert red.pedagogical_string == "C(4,3) = 4"
    assert green.is_possible is True and green.favorable_combinations == 10
    assert green.pedagogical_string == "C(5,3) = 10"
    # same_group: 4 + 10 = 14 (المستحيلة لا تُضاف)
    assert out.same_group_favorable == 14


def test_deep_dive_activated_by_confusion() -> None:
    """V30.0: حيرة الطالب («لم أفهم أي شيء») تُفعّل deep_dive + القصة البصرية."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(
        ProbabilityInput(
            question="اريد شرح خارق لاني لم افهم اي شي",
            history=[{"role": "user", "content": _BAC_URN_SIMUL}],
        )
    )
    assert isinstance(out, CombinationsModelOutput)
    assert out.deep_dive is True
    # حالة الكيس وتحليل الأحداث مملوءان للقصة البصرية
    assert len(out.urn_state) == len(out.groups)
    assert len(out.event_analysis) == len(out.groups)
    assert all("color" in u for u in out.urn_state)
    impossible = [e for e in out.event_analysis if e["is_possible"] is False]
    assert impossible and all(e["value"] == 0 for e in impossible)


def test_deep_dive_off_without_confusion() -> None:
    """V30.0: بلا حيرة → deep_dive=False (لا قصة بصرية مفروضة)."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(_BAC_URN_SIMUL)
    assert isinstance(out, CombinationsModelOutput)
    assert out.deep_dive is False


def test_combination_group_color_tokens() -> None:
    """V30.0: المجموعات الملوّنة تحمل رمز CSS صحيح (red/white/green)."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(_BAC_URN_SIMUL)
    assert isinstance(out, CombinationsModelOutput)
    colors = {g.label: g.color for g in out.groups}
    assert colors["كرة حمراء"] == "red"
    assert colors["كرة بيضاء"] == "white"
    assert colors["كرة خضراء"] == "green"


# ─── ISS-083 (D-081): Ball-numbering must NOT create garbage "رقم N" entities ────
# الكارثة الحية: «مرقمة بـ 0، 1، 1، 3» كان يُلتقَط كـ «كرة رقم 0»/«كرة رقم 1»
# (السلسلة الفرعية «رقم» داخل «مرقمة») فيتضخّم المجموع (17 بدل 11) وتظهر كسور
# خاطئة (4/17 بدل 4/11) وتسميات غارباج في شجرة الواجهة — تماماً صورة المستخدم.

_BAC2024_FULL = (
    "يحتوي كيس على 11 كرة متماثلة لا تُفرّق باللمس موزعة كما يلي: "
    "كرتان بيضاوان مرقمتان بـ 1، 3 "
    "أربع كرات حمراء مرقمة بـ 0، 1، 1، 3 "
    "خمس كرات خضراء مرقمة بـ 0، 1، 1، 3، 4 "
    "نسحب عشوائيًا 3 كرات دفعة واحدة من الكيس."
)
# صيغة upstream قد تُزيل «بـ» فتلتصق الأرقام بـ«مرقمة» (أسوأ حالة للالتباس).
_BAC2024_STRIPPED = (
    "كرتان بيضاوان مرقمتان 1 3 أربع كرات حمراء مرقمة 0 1 1 3 خمس كرات خضراء مرقمة 0 1 1 3 4"
)


def test_iss083_ball_numbering_creates_no_garbage_entities() -> None:
    """«مرقمة 0 1 1 3» لا يُنتج «كرة رقم 0»/«كرة رقم 1» — ألوان فقط."""
    entities = _skill()._extract_count_entities(_BAC2024_STRIPPED)
    labels = {e[0] for e in entities}
    assert labels == {"كرة حمراء", "كرة بيضاء", "كرة خضراء"}
    assert all("رقم" not in lbl for lbl in labels)
    counts = {e[0]: e[2] for e in entities}
    assert counts == {"كرة حمراء": 4, "كرة بيضاء": 2, "كرة خضراء": 5}


def test_iss083_simultaneous_draw_correct_combinations() -> None:
    """السحب الآني → تأليفات صحيحة: n=11, k=3, C=165, P(A)=14/165."""
    from app.services.skills.probability_skill import CombinationsModelOutput

    out = _skill().analyze(_BAC2024_FULL)
    assert isinstance(out, CombinationsModelOutput)
    assert out.n == 11 and out.k == 3 and out.total_combinations == 165
    assert out.same_group_favorable == 14  # P(A) = 14/165 (الإجابة الرسمية)
    assert all("رقم" not in g.label for g in out.groups)


def test_iss083_sequential_draw_correct_fractions_over_eleven() -> None:
    """السحب التتابعي → شجرة بكسور /11 صحيحة وتسميات لون ملموسة (لا «رقم 0»)."""
    out = _skill().analyze(
        ProbabilityInput(
            question="اعطني شجرة الاحتمالات",
            history=[
                {
                    "role": "assistant",
                    "content": _BAC2024_STRIPPED + " نسحب 3 كرات على التوالي وبدون إرجاع.",
                }
            ],
        )
    )
    assert isinstance(out, ProbabilityModelOutput)
    first_level = {c["label"]: (c["p_num"], c["p_den"]) for c in out.tree["children"]}
    assert first_level == {
        "كرة حمراء": (4, 11),
        "كرة بيضاء": (2, 11),
        "كرة خضراء": (5, 11),
    }
    assert all("رقم" not in lbl for lbl in first_level)


def test_iss083_explicit_numbered_cards_still_work() -> None:
    """حارس الانحدار: «تحمل الرقم 1» و«رقم 2» الصريحة تبقى كيانات سليمة."""
    skill = _skill()
    e1 = {
        x[0]: x[2]
        for x in skill._extract_count_entities("8 بطاقات: 3 تحمل الرقم 1، و5 تحمل الرقم 2")
    }
    assert e1 == {"بطاقة رقم 1": 3, "بطاقة رقم 2": 5}
    e2 = {x[0]: x[2] for x in skill._extract_count_entities("علبة بها 8 بطاقات: 3 رقم 1 و5 رقم 2")}
    assert e2 == {"بطاقة رقم 1": 3, "بطاقة رقم 2": 5}


def test_iss083_doctrine_rule_present_and_versioned() -> None:
    """قاعدة ISS-083 مُسجَّلة في PROBABILITY_CALCULATION_DOCTRINE + الإصدار ≥ 1.2.0."""
    from app.services.skills.doctrine import (
        PROBABILITY_CALCULATION_DOCTRINE,
        PROBABILITY_CALCULATION_DOCTRINE_VERSION,
    )

    assert PROBABILITY_CALCULATION_DOCTRINE_VERSION >= "1.2.0"
    joined = " ".join(PROBABILITY_CALCULATION_DOCTRINE)
    assert "ISS-083" in joined
    assert "مرقمة" in joined  # القاعدة تذكر الصفة المرفوضة صراحةً
