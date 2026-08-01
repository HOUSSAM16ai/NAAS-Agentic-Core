"""اختبارات مُجدوِل التكرار المتباعد FSRS — D-194.

الاختبارات هنا تُثبِّت **الخصائص الرياضية** لا مجرّد قيماً محفوظة: الاستقرار مُعرَّف بأنّه
المدّة التي ينزل بعدها التذكّر إلى الهدف، والانتكاسة لا تُطيل الفاصل أبداً، والصعوبة
محبوسة، وكلّ خرقٍ للمجال يرفع بدل أن يُرجِع رقماً مضلِّلاً.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from shared.scheduling import fsrs
from shared.scheduling.fsrs import (
    DEFAULT_PARAMETERS,
    MAX_DIFFICULTY,
    MAXIMUM_INTERVAL_DAYS,
    MIN_DIFFICULTY,
    MINIMUM_INTERVAL_DAYS,
    REQUEST_RETENTION,
    Rating,
    ReviewState,
    SchedulingError,
    initial_state,
    interval_days,
    is_due,
    retrievability,
    review,
)

NOW = datetime(2026, 8, 1, 12, 0, tzinfo=UTC)


# ── منحنى النسيان: الخصائص المُعرِّفة ────────────────────────────────────────────


def test_retrievability_is_one_at_zero_elapsed() -> None:
    assert retrievability(0.0, 5.0) == pytest.approx(1.0)


def test_retrievability_equals_target_after_exactly_one_stability() -> None:
    """**تعريف الاستقرار**: بعد `S` يوماً يكون احتمال التذكّر ٠٫٩ بالضبط."""
    for stability in (0.5, 1.0, 5.0, 42.0, 365.0):
        assert retrievability(stability, stability) == pytest.approx(REQUEST_RETENTION, abs=1e-9)


def test_retrievability_decreases_monotonically() -> None:
    previous = 1.1
    for day in range(0, 60):
        current = retrievability(float(day), 10.0)
        assert current < previous
        previous = current


def test_interval_of_stability_is_stability_at_default_retention() -> None:
    """عكس المنحنى — الفاصل عند الهدف الافتراضي يساوي الاستقرار."""
    for stability in (2.0, 10.0, 100.0):
        assert interval_days(stability) == pytest.approx(stability, rel=1e-9)


def test_higher_requested_retention_shortens_the_interval() -> None:
    """طلب تذكّر أعلى ⇒ مراجعة أبكر. علاقة يجب ألّا تنعكس."""
    assert interval_days(50.0, 0.95) < interval_days(50.0, 0.90) < interval_days(50.0, 0.80)


def test_interval_is_clamped_to_the_configured_bounds() -> None:
    assert interval_days(0.0001) == MINIMUM_INTERVAL_DAYS
    assert interval_days(10_000.0) == MAXIMUM_INTERVAL_DAYS
    assert interval_days(10_000.0, maximum_interval=30.0) == 30.0


# ── عقد الأخطاء: لا صفر مضلِّل ───────────────────────────────────────────────────


@pytest.mark.parametrize("stability", [0.0, -1.0, float("nan"), float("inf")])
def test_retrievability_rejects_invalid_stability(stability: float) -> None:
    with pytest.raises(SchedulingError, match="stability"):
        retrievability(1.0, stability)


def test_retrievability_rejects_negative_elapsed() -> None:
    with pytest.raises(SchedulingError, match="elapsed_days"):
        retrievability(-1.0, 5.0)


@pytest.mark.parametrize("stability", [0.0, -3.0, float("inf")])
def test_interval_rejects_invalid_stability(stability: float) -> None:
    with pytest.raises(SchedulingError, match="stability"):
        interval_days(stability)


@pytest.mark.parametrize("retention", [0.0, 1.0, -0.2, 1.5])
def test_interval_rejects_retention_outside_the_open_unit_interval(retention: float) -> None:
    with pytest.raises(SchedulingError, match="request_retention"):
        interval_days(10.0, retention)


def test_interval_rejects_a_maximum_below_the_minimum() -> None:
    with pytest.raises(SchedulingError, match="maximum_interval"):
        interval_days(10.0, maximum_interval=0.5)


def test_parameters_must_have_the_exact_fsrs5_arity() -> None:
    with pytest.raises(SchedulingError, match="19 parameters"):
        initial_state(Rating.GOOD, NOW, parameters=(0.4, 1.2))


def test_parameters_must_be_finite() -> None:
    broken = (float("nan"), *DEFAULT_PARAMETERS[1:])
    with pytest.raises(SchedulingError, match="finite"):
        initial_state(Rating.GOOD, NOW, parameters=broken)


@pytest.mark.parametrize("rating", [0, 5, -1, 99])
def test_unknown_rating_is_rejected(rating: int) -> None:
    with pytest.raises(SchedulingError, match="rating must be one of"):
        initial_state(rating, NOW)


def test_naive_datetimes_are_rejected_everywhere() -> None:
    """
    زمنٌ بلا منطقة زمنية هو أصلُ أخطاء الجدولة الصامتة عبر خوادم بمناطق مختلفة.
    """
    naive = datetime(2026, 8, 1, 12, 0)
    with pytest.raises(SchedulingError, match="timezone-aware"):
        initial_state(Rating.GOOD, naive)
    state = initial_state(Rating.GOOD, NOW)
    with pytest.raises(SchedulingError, match="timezone-aware"):
        review(state, Rating.GOOD, naive)
    with pytest.raises(SchedulingError, match="timezone-aware"):
        is_due(state, naive)


def test_a_review_cannot_precede_the_previous_one() -> None:
    state = initial_state(Rating.GOOD, NOW)
    with pytest.raises(SchedulingError, match="cannot happen before"):
        review(state, Rating.GOOD, NOW - timedelta(days=1))


# ── الحالة الابتدائية ───────────────────────────────────────────────────────────


def test_initial_stability_grows_with_the_rating() -> None:
    stabilities = [initial_state(rating, NOW).stability for rating in Rating]
    assert stabilities == sorted(stabilities)


def test_initial_difficulty_falls_as_the_rating_improves() -> None:
    difficulties = [initial_state(rating, NOW).difficulty for rating in Rating]
    assert difficulties == sorted(difficulties, reverse=True)


def test_again_on_first_contact_counts_a_lapse_and_enters_relearning() -> None:
    state = initial_state(Rating.AGAIN, NOW)
    assert state.lapses == 1
    assert state.state == "relearning"


def test_good_on_first_contact_enters_review_with_no_lapse() -> None:
    state = initial_state(Rating.GOOD, NOW)
    assert state.lapses == 0
    assert state.state == "review"
    assert state.reps == 1


def test_initial_due_date_matches_the_derived_interval() -> None:
    state = initial_state(Rating.GOOD, NOW)
    expected = interval_days(state.stability)
    assert (state.due_at - NOW).total_seconds() / 86400.0 == pytest.approx(expected)


# ── المراجعة المتتالية ──────────────────────────────────────────────────────────


def test_successful_reviews_lengthen_the_interval_monotonically() -> None:
    """الغرض كلّه: نجاحٌ متكرّر ⇒ تباعدٌ متزايد."""
    state = initial_state(Rating.GOOD, NOW)
    previous = 0.0
    for _ in range(6):
        moment = state.due_at
        state = review(state, Rating.GOOD, moment)
        gap = (state.due_at - moment).total_seconds() / 86400.0
        assert gap > previous
        previous = gap


def test_a_lapse_never_lengthens_stability() -> None:
    """
    قيد FSRS-5 الحاسم: لو زاد الاستقرارُ بعد فشل، لكوفئ الطالب على النسيان.
    """
    state = initial_state(Rating.GOOD, NOW)
    for _ in range(5):
        state = review(state, Rating.GOOD, state.due_at)
    lapsed = review(state, Rating.AGAIN, state.due_at)
    assert lapsed.stability <= state.stability
    assert lapsed.lapses == state.lapses + 1
    assert lapsed.state == "relearning"


def test_easy_outpaces_good_which_outpaces_hard() -> None:
    base = initial_state(Rating.GOOD, NOW)
    moment = base.due_at
    outcomes = {
        rating: review(base, rating, moment).stability
        for rating in (Rating.HARD, Rating.GOOD, Rating.EASY)
    }
    assert outcomes[Rating.HARD] < outcomes[Rating.GOOD] < outcomes[Rating.EASY]


def test_difficulty_stays_inside_its_bounds_under_adversarial_streaks() -> None:
    """صعوبةٌ منفلتة تُفسد كلّ المعادلات اللاحقة — الحبس يجب أن يصمد للطرفين."""
    for streak in (Rating.AGAIN, Rating.EASY):
        state = initial_state(Rating.GOOD, NOW)
        for _ in range(40):
            state = review(state, streak, state.due_at)
            assert MIN_DIFFICULTY <= state.difficulty <= MAX_DIFFICULTY
            assert state.stability > 0.0


def test_reps_increment_on_every_review() -> None:
    state = initial_state(Rating.GOOD, NOW)
    for expected in range(2, 6):
        state = review(state, Rating.GOOD, state.due_at)
        assert state.reps == expected


def test_reviewing_early_yields_less_stability_than_reviewing_on_time() -> None:
    """
    المراجعة المبكّرة تُفيد أقلّ — لأنّ التذكّر ما زال عالياً فالاسترجاع لم يُجهِد الذاكرة.
    هذا «أثر التباعد» وهو سبب وجود الخوارزمية أصلاً.
    """
    state = initial_state(Rating.GOOD, NOW)
    early = review(state, Rating.GOOD, NOW + timedelta(days=1))
    on_time = review(state, Rating.GOOD, state.due_at)
    assert early.stability < on_time.stability


def test_review_does_not_mutate_the_input_state() -> None:
    state = initial_state(Rating.GOOD, NOW)
    snapshot = (state.stability, state.difficulty, state.due_at, state.reps)
    review(state, Rating.AGAIN, state.due_at)
    assert (state.stability, state.difficulty, state.due_at, state.reps) == snapshot


# ── الاستحقاق ───────────────────────────────────────────────────────────────────


def test_is_due_flips_exactly_at_the_due_moment() -> None:
    state = initial_state(Rating.GOOD, NOW)
    assert not is_due(state, state.due_at - timedelta(seconds=1))
    assert is_due(state, state.due_at)
    assert is_due(state, state.due_at + timedelta(days=3))


# ── عقد بناء الحالة ─────────────────────────────────────────────────────────────


def _state(**overrides: object) -> ReviewState:
    base: dict[str, object] = {
        "stability": 5.0,
        "difficulty": 5.0,
        "due_at": NOW + timedelta(days=5),
        "last_reviewed_at": NOW,
    }
    base.update(overrides)
    return ReviewState(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"stability": 0.0}, "stability"),
        ({"stability": -1.0}, "stability"),
        ({"stability": math.nan}, "stability"),
        ({"difficulty": 0.5}, "difficulty"),
        ({"difficulty": 11.0}, "difficulty"),
        ({"reps": -1}, "negative"),
        ({"lapses": -2}, "negative"),
        ({"state": "graduated"}, "unknown state"),
    ],
)
def test_invalid_review_states_are_rejected(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(SchedulingError, match=message):
        _state(**overrides)


def test_naive_timestamps_on_the_state_are_rejected() -> None:
    with pytest.raises(SchedulingError, match="timezone-aware"):
        _state(due_at=datetime(2026, 8, 6, 12, 0))
    with pytest.raises(SchedulingError, match="timezone-aware"):
        _state(last_reviewed_at=datetime(2026, 8, 1, 12, 0))


def test_default_parameters_are_the_published_fsrs5_arity() -> None:
    assert len(DEFAULT_PARAMETERS) == 19
    assert all(math.isfinite(value) for value in DEFAULT_PARAMETERS)


def test_custom_parameters_change_the_schedule() -> None:
    """المعاملات مُمرَّرة لا مُثبَّتة — وهذا شرط إعادة تدريبها على بيانات المنصّة."""
    slower = (0.1, *DEFAULT_PARAMETERS[1:])
    assert (
        initial_state(Rating.AGAIN, NOW, parameters=slower).stability
        < initial_state(Rating.AGAIN, NOW).stability
    )


def test_utcnow_helper_is_timezone_aware() -> None:
    assert fsrs._utcnow().tzinfo is not None
