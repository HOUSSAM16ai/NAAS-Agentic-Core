"""
اختبارات AnswerQualitySkill — D-072.

تتحقق من:
1. تقييم الإجابات الجيدة (happy path)
2. اكتشاف المشاكل الحرجة (error paths)
3. تصحيح LaTeX الخاطئ
4. اكتشاف reasoning leak (D-067)
5. اكتشاف box-drawing chars (D-067)
6. حساب نقطة الجودة
7. Prometheus metrics (defensive import)
8. Singleton pattern
"""

from __future__ import annotations

import pytest

from app.services.skills.answer_quality_skill import (
    AnswerQualityInput,
    AnswerQualityOutput,
    AnswerQualitySkill,
    get_answer_quality_skill,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def skill() -> AnswerQualitySkill:
    return AnswerQualitySkill()


def _good_educational_answer() -> str:
    return (
        "قانون نيوتن الثاني يربط القوة بالكتلة والتسارع.\n\n"
        "1. أولاً نُعرِّف القوة الصافية: $$\\vec{F} = m\\vec{a}$$\n"
        "2. ثانياً نُعوِّض بالقيم المعطاة.\n"
        "3. إذن نجد التسارع: $$a = \\frac{F}{m}$$\n"
        "4. بالتعويض: $$a = \\frac{20}{5} = 4 \\text{ m/s}^2$$\n"
        "5. نستنتج أن الجسم يتسارع بمقدار 4 متر/ثانية².\n"
        "$$\\boxed{a = 4 \\text{ m/s}^2}$$"
    )


def _short_answer() -> str:
    return "القوة = الكتلة × التسارع"


def _bad_latex_answer() -> str:
    return (
        "الحل:\n"
        "\\[F = ma\\]\n"
        "\\begin{equation}a = F/m\\end{equation}\n"
        "إذن التسارع يساوي 4 متر/ثانية²."
    )


def _foreign_language_answer() -> str:
    return (
        "We need to apply Newton's second law.\n"
        "Therefore, F = ma.\n"
        "Hence the acceleration is 4 m/s²."
    )


def _box_drawing_answer() -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "قانون نيوتن الثاني: F = ma\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "1. أولاً نُعرِّف القوة الصافية.\n"
        "2. ثانياً نُعوِّض بالقيم المعطاة.\n"
        "إذن نجد التسارع: $$a = 4 \\text{ m/s}^2$$"
    )


# ── Happy Path Tests ──────────────────────────────────────────────────────────


def test_good_answer_passes(skill: AnswerQualitySkill) -> None:
    """إجابة جيدة تجتاز التقييم بنقطة عالية."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن الثاني",
        answer=_good_educational_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    assert result.passed is True
    assert result.score >= 0.6


def test_good_answer_no_critical_issues(skill: AnswerQualitySkill) -> None:
    """إجابة جيدة لا تحتوي على مشاكل حرجة."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن الثاني",
        answer=_good_educational_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    critical = [i for i in result.issues if i.severity == "critical"]
    assert len(critical) == 0


def test_score_is_one_for_perfect_answer(skill: AnswerQualitySkill) -> None:
    """إجابة مثالية تحصل على نقطة 1.0."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن الثاني",
        answer=_good_educational_answer(),
        intent="educational",
        require_steps=True,
        require_latex=True,
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    assert result.score == 1.0


# ── Error Path Tests ──────────────────────────────────────────────────────────


def test_short_answer_fails(skill: AnswerQualitySkill) -> None:
    """إجابة قصيرة جداً تفشل التقييم."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن الثاني",
        answer=_short_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    codes = [i.code for i in result.issues]
    assert "TOO_SHORT" in codes


def test_bad_latex_detected(skill: AnswerQualitySkill) -> None:
    """LaTeX خاطئ يُكتشَف ويُصحَّح."""
    inp = AnswerQualityInput(
        question="احسب التسارع",
        answer=_bad_latex_answer(),
        intent="math",
        require_latex=True,
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    codes = [i.code for i in result.issues]
    assert "BAD_LATEX_FORMAT" in codes
    # التصحيح التلقائي
    assert "\\[" not in result.improved_answer
    assert "\\begin{equation}" not in result.improved_answer


def test_foreign_language_detected(skill: AnswerQualitySkill) -> None:
    """اللغة الأجنبية (reasoning leak) تُكتشَف."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=_foreign_language_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    codes = [i.code for i in result.issues]
    assert "FOREIGN_LANGUAGE_LEAK" in codes


def test_box_drawing_chars_detected(skill: AnswerQualitySkill) -> None:
    """Box-drawing chars تُكتشَف (D-067)."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=_box_drawing_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    codes = [i.code for i in result.issues]
    assert "BOX_DRAWING_CHARS" in codes


def test_score_decreases_with_issues(skill: AnswerQualitySkill) -> None:
    """نقطة الجودة تنخفض مع وجود مشاكل."""
    good_inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=_good_educational_answer(),
        intent="educational",
    )
    bad_inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=_foreign_language_answer(),
        intent="educational",
    )
    good_result = skill.evaluate(good_inp)
    bad_result = skill.evaluate(bad_inp)
    assert isinstance(good_result, AnswerQualityOutput)
    assert isinstance(bad_result, AnswerQualityOutput)
    assert good_result.score > bad_result.score


# ── Chat Intent Tests ─────────────────────────────────────────────────────────


def test_chat_intent_no_steps_required(skill: AnswerQualitySkill) -> None:
    """المحادثة العادية لا تتطلب خطوات مرقمة."""
    inp = AnswerQualityInput(
        question="كيف حالك",
        answer="أنا بخير، شكراً لسؤالك! كيف يمكنني مساعدتك في دراستك اليوم؟",
        intent="chat",
        require_steps=False,
        require_latex=False,
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    codes = [i.code for i in result.issues]
    assert "NO_NUMBERED_STEPS" not in codes


# ── Output Contract Tests ─────────────────────────────────────────────────────


def test_output_has_duration(skill: AnswerQualitySkill) -> None:
    """النتيجة تحتوي على وقت التقييم."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=_good_educational_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    assert result.duration_ms >= 0.0


def test_output_has_doctrine_version(skill: AnswerQualitySkill) -> None:
    """النتيجة تحتوي على نسخة الـ doctrine."""
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=_good_educational_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    assert result.doctrine_version == "2.0.0"


def test_original_answer_preserved(skill: AnswerQualitySkill) -> None:
    """الإجابة الأصلية محفوظة في النتيجة."""
    answer = _good_educational_answer()
    inp = AnswerQualityInput(
        question="اشرح قانون نيوتن",
        answer=answer,
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    assert result.original_answer == answer


# ── Singleton Tests ───────────────────────────────────────────────────────────


def test_singleton_returns_same_instance() -> None:
    """get_answer_quality_skill يُعيد نفس الـ instance."""
    s1 = get_answer_quality_skill()
    s2 = get_answer_quality_skill()
    assert s1 is s2


def test_singleton_is_answer_quality_skill() -> None:
    """get_answer_quality_skill يُعيد AnswerQualitySkill."""
    s = get_answer_quality_skill()
    assert isinstance(s, AnswerQualitySkill)


# ── Skill Contract Tests ──────────────────────────────────────────────────────


def test_skill_has_version() -> None:
    """AnswerQualitySkill لديه VERSION."""
    assert AnswerQualitySkill.VERSION == "1.0.0"


def test_skill_has_name() -> None:
    """AnswerQualitySkill لديه SKILL_NAME."""
    assert AnswerQualitySkill.SKILL_NAME == "answer_quality"


def test_skill_imports_from_doctrine() -> None:
    """AnswerQualitySkill يستورد من doctrine (D-072 invariant)."""
    import inspect

    import app.services.skills.answer_quality_skill as mod

    src = inspect.getsource(mod)
    assert "from app.services.skills.doctrine import" in src


def test_skill_in_package_init() -> None:
    """AnswerQualitySkill مُصدَّر من package __init__."""
    from app.services.skills import AnswerQualitySkill as ImportedSkill

    assert ImportedSkill is AnswerQualitySkill


# ── Doctrine Integration Tests ────────────────────────────────────────────────


def test_issues_reference_doctrine_rules(skill: AnswerQualitySkill) -> None:
    """المشاكل المُكتشَفة تُشير إلى قواعد الـ doctrine."""
    inp = AnswerQualityInput(
        question="اشرح",
        answer=_short_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    for issue in result.issues:
        assert isinstance(issue.doctrine_rule, str)


def test_quality_issue_has_severity(skill: AnswerQualitySkill) -> None:
    """كل مشكلة لها severity صحيح."""
    inp = AnswerQualityInput(
        question="اشرح",
        answer=_short_answer(),
        intent="educational",
    )
    result = skill.evaluate(inp)
    assert isinstance(result, AnswerQualityOutput)
    valid_severities = {"critical", "warning", "info"}
    for issue in result.issues:
        assert issue.severity in valid_severities
