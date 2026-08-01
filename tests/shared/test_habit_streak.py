"""اختبارات سلسلة المواظبة — D-195.

الخطر كلّه في المنطقة الزمنية: «يوم» هو يومٌ في تقويم الطالب لا ٢٤ ساعة من UTC. طالبٌ
جزائري يراجع الساعة ٠٠:٣٠ يُسجَّل في UTC عند ٢٣:٣٠ من اليوم **السابق** — فالحساب على UTC
يكسر مواظبة كلّ من يدرس ليلاً، وهو أكثر أوقات مراجعة البكالوريا شيوعاً.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from shared.habit.streak import (
    ALGIERS_TZ,
    GRACE_DAYS,
    HabitError,
    active_days,
    summarize_streak,
)

ALGIERS = ZoneInfo(ALGIERS_TZ)
NOW = datetime(2026, 8, 1, 10, 0, tzinfo=ALGIERS)


def day_before(offset: int, hour: int = 12) -> datetime:
    return (NOW - timedelta(days=offset)).replace(hour=hour)


# ── المنطقة الزمنية: الخطر الأصلي ───────────────────────────────────────────────


def test_a_late_night_session_belongs_to_the_local_day_not_the_utc_one() -> None:
    """
    ٠٠:٣٠ بتوقيت الجزائر = ٢٣:٣٠ من اليوم السابق بتوقيت UTC.

    هذا هو العطب الذي يمنعه التحويل: مراجعةٌ بعد منتصف الليل كانت ستُحتسَب لليوم
    الفائت فتُقطَع سلسلةُ الطالب رغم مواظبته.
    """
    late = datetime(2026, 8, 1, 0, 30, tzinfo=ALGIERS)
    assert active_days([late]) == (date(2026, 8, 1),)
    assert late.astimezone(UTC).date() == date(2026, 7, 31)


def test_naive_timestamps_are_read_as_utc() -> None:
    """SQLite يُعيد أزمنةً عارية؛ رفضُها يجعل المواظبة تعمل على Postgres وحده."""
    assert active_days([datetime(2026, 7, 31, 23, 30)]) == (date(2026, 8, 1),)


def test_multiple_sessions_on_one_day_count_once() -> None:
    same_day = [day_before(0, hour) for hour in (8, 13, 21)]
    assert summarize_streak(same_day, now=NOW).total_active_days == 1


def test_unknown_timezone_raises() -> None:
    with pytest.raises(HabitError, match="unknown timezone"):
        summarize_streak([], now=NOW, timezone_name="Mars/Olympus")


def test_naive_now_is_rejected() -> None:
    with pytest.raises(HabitError, match="timezone-aware"):
        summarize_streak([], now=datetime(2026, 8, 1, 10, 0))


# ── حساب السلسلة ───────────────────────────────────────────────────────────────


def test_consecutive_days_ending_today() -> None:
    summary = summarize_streak([day_before(0), day_before(1), day_before(2)], now=NOW)
    assert summary.current_streak == 3
    assert summary.longest_streak == 3
    assert summary.active_today is True
    assert summary.at_risk is False
    assert summary.last_active_on == date(2026, 8, 1)


def test_a_streak_survives_until_the_end_of_the_grace_day() -> None:
    """
    من واظب ثلاثين يوماً يجب ألّا يرى «٠» كلّ صباحٍ قبل أن يفتح التطبيق —
    وإلّا عاقبنا المواظبة بدل أن نكافئها.
    """
    summary = summarize_streak([day_before(1), day_before(2), day_before(3)], now=NOW)
    assert summary.current_streak == 3
    assert summary.active_today is False
    assert summary.at_risk is True


def test_a_gap_beyond_the_grace_breaks_the_streak_but_keeps_the_record() -> None:
    summary = summarize_streak([day_before(2), day_before(3), day_before(4)], now=NOW)
    assert summary.current_streak == 0
    assert summary.longest_streak == 3
    assert summary.at_risk is False


def test_grace_is_exactly_one_day() -> None:
    assert GRACE_DAYS == 1
    assert summarize_streak([day_before(GRACE_DAYS)], now=NOW).current_streak == 1
    assert summarize_streak([day_before(GRACE_DAYS + 1)], now=NOW).current_streak == 0


def test_longest_streak_survives_a_later_break() -> None:
    days = [day_before(offset) for offset in (10, 9, 8, 7, 6, 1, 0)]
    summary = summarize_streak(days, now=NOW)
    assert summary.longest_streak == 5
    assert summary.current_streak == 2


def test_a_single_day_is_a_streak_of_one() -> None:
    summary = summarize_streak([day_before(0)], now=NOW)
    assert summary.current_streak == 1
    assert summary.longest_streak == 1


def test_no_activity_is_all_zeroes_and_not_at_risk() -> None:
    summary = summarize_streak([], now=NOW)
    assert summary.current_streak == 0
    assert summary.longest_streak == 0
    assert summary.total_active_days == 0
    assert summary.last_active_on is None
    assert summary.at_risk is False


def test_future_timestamps_cannot_manufacture_a_streak() -> None:
    """ساعة خادمٍ منحرفة لا تُنشئ مواظبة لم تحدث."""
    summary = summarize_streak([day_before(-3), day_before(-2), day_before(0)], now=NOW)
    assert summary.current_streak == 1
    assert summary.total_active_days == 1
    assert summary.last_active_on == date(2026, 8, 1)


def test_unordered_input_is_handled() -> None:
    days = [day_before(2), day_before(0), day_before(1)]
    assert summarize_streak(days, now=NOW).current_streak == 3


def test_activity_across_a_month_boundary_is_continuous() -> None:
    """٣١ يوليو ثمّ ١ أغسطس سلسلةٌ من يومين — لا تنقطع بتغيّر الشهر."""
    days = [
        datetime(2026, 7, 31, 20, 0, tzinfo=ALGIERS),
        datetime(2026, 8, 1, 9, 0, tzinfo=ALGIERS),
    ]
    assert summarize_streak(days, now=NOW).current_streak == 2


def test_active_days_returns_sorted_unique_dates() -> None:
    days = active_days([day_before(2), day_before(0), day_before(2), day_before(1)])
    assert days == (date(2026, 7, 30), date(2026, 7, 31), date(2026, 8, 1))
