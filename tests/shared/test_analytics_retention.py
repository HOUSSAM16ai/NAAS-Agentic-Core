"""اختبارات حساب الاحتفاظ والقُمع — D-197.

التعريف يعيش في مكانٍ واحد ويُختبَر **بلا قاعدة بيانات أصلاً**: منطق الاحتفاظ يجب أن
يُعطي نفس الرقم على SQLite وPostgres، ودوالّ التاريخ تختلف بين المحرّكين — فنسختان من
التعريف تعنيان رقمين مختلفين لنفس السؤال، وهذا أسوأ من ألّا يكون هناك رقم.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from shared.analytics import (
    AnalyticsError,
    EventName,
    cohort_retention,
    funnel,
    is_canonical,
    retention_report,
    validate_event_name,
)

BASE = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)


def day(offset: int) -> datetime:
    return BASE + timedelta(days=offset)


# ── أسماء الأحداث ───────────────────────────────────────────────────────────────


def test_canonical_names_are_accepted() -> None:
    for member in EventName:
        assert is_canonical(member.value)
        assert validate_event_name(member.value) == member.value


def test_an_unregistered_name_is_rejected_at_write_time() -> None:
    """
    الرفض عند الكتابة لا بعد شهر.

    `chat_start` و`chat_started` تعيشان معاً في أيّ نظامٍ بأسماء حرّة، فيصير كلّ رقمٍ
    في لوحة المستثمر مبنيّاً على تجميعٍ ناقص.
    """
    assert not is_canonical("chat_start")
    with pytest.raises(AnalyticsError, match="unknown event name"):
        validate_event_name("chat_start")


def test_event_names_are_past_tense_and_snake_case() -> None:
    """الحدث شيءٌ **وقع** — الصيغة تمنع الخلط بين الحدث والنيّة."""
    for member in EventName:
        assert member.value.islower()
        assert " " not in member.value
        assert member.value.split("_")[-1].endswith(("ed", "up", "in"))


# ── الاحتفاظ ───────────────────────────────────────────────────────────────────


def test_day_one_retention_counts_activity_on_the_next_day_exactly() -> None:
    signups = {1: BASE, 2: BASE}
    activity = {1: [BASE, day(1)], 2: [BASE]}
    cohorts = cohort_retention(signups=signups, activity=activity, today=date(2026, 8, 1))
    assert len(cohorts) == 1
    assert cohorts[0].size == 2
    assert cohorts[0].retained[1] == pytest.approx(0.5)


def test_retention_is_bounded_not_unbounded() -> None:
    """
    نشاطٌ في اليوم الثالث **لا** يُحتسَب لاحتفاظ اليوم الأوّل.

    التعريف «المحدود» هو المُعتمَد؛ خلطُه بـ«غير المحدود» بين لوحتين يجعل المقارنة كذباً
    لأنّ الثاني يُعطي أرقاماً أعلى دائماً.
    """
    cohorts = cohort_retention(
        signups={1: BASE}, activity={1: [BASE, day(3)]}, today=date(2026, 8, 1)
    )
    assert cohorts[0].retained[1] == 0.0


def test_an_immature_cohort_returns_none_not_zero() -> None:
    """
    من سجّل أمس لا يُقاس احتفاظ اليوم السابع لديه.

    صفرٌ هنا يقرأ «فقدناهم» بينما الحقيقة «لم يحن الوقت» (§0).
    """
    cohorts = cohort_retention(
        signups={1: BASE}, activity={1: [BASE, day(1)]}, today=BASE.date() + timedelta(days=1)
    )
    assert cohorts[0].retained[1] == pytest.approx(1.0)
    assert cohorts[0].retained[7] is None
    assert cohorts[0].retained[30] is None


def test_overall_is_weighted_by_cohort_size_over_mature_cohorts_only() -> None:
    signups = {1: BASE, 2: BASE, 3: day(1)}
    activity = {1: [day(1)], 2: [], 3: [day(2)]}
    report = retention_report(signups=signups, activity=activity, today=date(2026, 8, 1))
    # الفوج الأول: 1/2 · الفوج الثاني: 1/1 ⇒ المرجّح = (0.5*2 + 1.0*1)/3
    assert report.overall[1] == pytest.approx(2 / 3)


def test_overall_is_none_when_no_cohort_is_mature() -> None:
    report = retention_report(signups={1: BASE}, activity={1: [BASE]}, today=BASE.date())
    assert report.overall[1] is None
    assert report.overall[7] is None


def test_cohorts_are_grouped_by_local_day_not_utc() -> None:
    """
    نفس قاعدة D-195: الفوج يوم تسجيلٍ بتقويم الطالب.

    ٢٣:٣٠ UTC هو ٠٠:٣٠ من اليوم التالي في الجزائر — فالمسجَّلان ينتميان لفوجين.
    """
    late_utc = datetime(2026, 7, 1, 23, 30, tzinfo=UTC)
    early_utc = datetime(2026, 7, 1, 10, 0, tzinfo=UTC)
    cohorts = cohort_retention(
        signups={1: early_utc, 2: late_utc}, activity={}, today=date(2026, 8, 1)
    )
    assert [c.cohort_date for c in cohorts] == [date(2026, 7, 1), date(2026, 7, 2)]


def test_naive_timestamps_are_read_as_utc() -> None:
    cohorts = cohort_retention(
        signups={1: datetime(2026, 7, 1, 10, 0)}, activity={}, today=date(2026, 8, 1)
    )
    assert cohorts[0].cohort_date == date(2026, 7, 1)


def test_no_signups_yields_no_cohorts() -> None:
    report = retention_report(signups={}, activity={}, today=date(2026, 8, 1))
    assert report.cohorts == ()
    assert all(value is None for value in report.overall.values())


def test_horizons_must_be_positive() -> None:
    with pytest.raises(ValueError, match="horizons"):
        cohort_retention(signups={}, activity={}, today=date(2026, 8, 1), horizons=[0])


def test_unknown_timezone_raises() -> None:
    with pytest.raises(ValueError, match="unknown timezone"):
        cohort_retention(
            signups={}, activity={}, today=date(2026, 8, 1), timezone_name="Mars/Olympus"
        )


def test_report_reports_its_horizons_sorted() -> None:
    report = retention_report(
        signups={1: BASE}, activity={}, today=date(2026, 8, 1), horizons=[30, 1, 7]
    )
    assert report.horizons == (1, 7, 30)


# ── القُمع ──────────────────────────────────────────────────────────────────────


def test_funnel_intersects_so_conversion_can_never_exceed_one() -> None:
    """
    كلّ خطوة تُحسَب على من أتمّ الخطوات السابقة.

    بلا التقاطع يستطيع القُمع أن يُظهِر تحويلاً يفوق ١٠٠٪ (مستخدمٌ راجع دون أن يسجّل
    في النافذة مثلاً) — وهو ما يجعل اللوحة بلا معنى.
    """
    steps = funnel(
        steps=["a", "b"],
        users_by_event={"a": [1, 2], "b": [1, 2, 3, 4, 5]},
    )
    assert steps[1].users == 2
    assert steps[1].conversion_from_start == pytest.approx(1.0)


def test_funnel_reports_both_conversion_rates() -> None:
    steps = funnel(
        steps=["a", "b", "c"],
        users_by_event={"a": [1, 2, 3, 4], "b": [1, 2], "c": [1]},
    )
    assert [s.users for s in steps] == [4, 2, 1]
    assert steps[2].conversion_from_start == pytest.approx(0.25)
    assert steps[2].conversion_from_previous == pytest.approx(0.5)


def test_an_empty_funnel_is_empty() -> None:
    assert funnel(steps=[], users_by_event={}) == ()


def test_a_funnel_with_no_users_does_not_divide_by_zero() -> None:
    steps = funnel(steps=["a", "b"], users_by_event={})
    assert [s.users for s in steps] == [0, 0]
    assert steps[1].conversion_from_start == 0.0
    assert steps[1].conversion_from_previous == 0.0
