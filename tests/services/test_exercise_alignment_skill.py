"""اختبارات ExerciseAlignmentSkill لمحاذاة إجابات الاحتمالات مع معطيات السؤال."""

from app.services.skills.exercise_alignment_skill import (
    ExerciseAlignmentInput,
    get_exercise_alignment_skill,
)


def test_alignment_removes_unrequested_colors() -> None:
    skill = get_exercise_alignment_skill()
    payload = ExerciseAlignmentInput(
        question="تمرين احتمالات: لدينا كرات بيضاء وحمراء فقط.",
        answer="كرات بيضاء وحمراء.\nتوجد كرات زرقاء أيضاً.",
        intent="educational",
    )
    result = skill.align(payload)
    assert result.applied is True
    assert result.removed_lines == 1
    assert "زرقاء" not in result.aligned_answer


def test_alignment_skips_non_probability_question() -> None:
    skill = get_exercise_alignment_skill()
    payload = ExerciseAlignmentInput(
        question="اشرح الاشتقاق.",
        answer="ألوان: زرقاء وحمراء.",
        intent="educational",
    )
    result = skill.align(payload)
    assert result.applied is False
    assert result.aligned_answer == payload.answer


def test_alignment_keeps_line_and_removes_only_forbidden_color_word() -> None:
    skill = get_exercise_alignment_skill()
    payload = ExerciseAlignmentInput(
        question="تمرين احتمالات: كرات بيضاء وحمراء.",
        answer="في السطر نفسه: بيضاء وحمراء وزرقاء.",
        intent="educational",
    )
    result = skill.align(payload)
    assert result.applied is True
    assert "زرقاء" not in result.aligned_answer
    assert "بيضاء" in result.aligned_answer
    assert "حمراء" in result.aligned_answer


def test_alignment_supports_masculine_color_forms() -> None:
    skill = get_exercise_alignment_skill()
    payload = ExerciseAlignmentInput(
        question="تمرين احتمالات: لون أحمر فقط.",
        answer="لون أحمر صحيح، لكن يوجد لون أزرق غير صحيح.",
        intent="educational",
    )
    result = skill.align(payload)
    assert result.applied is True
    assert "أحمر" in result.aligned_answer
    assert "أزرق" not in result.aligned_answer
