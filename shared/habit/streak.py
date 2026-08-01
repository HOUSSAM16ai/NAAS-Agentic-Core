"""سلسلة المواظبة — حتمية، dep-free، وواعية بالمنطقة الزمنية (D-195).

لماذا المنطقة الزمنية هي كلّ الصعوبة
------------------------------------
«يوم» ليس ٢٤ ساعة من UTC — هو يومٌ في تقويم **الطالب**. طالبٌ في الجزائر (UTC+1) يدرس
الساعة ١١:٣٠ ليلاً يُسجَّل نشاطه في UTC عند ٢٢:٣٠ من **اليوم نفسه**، لكنّ من يدرس
الساعة ٠٠:٣٠ صباحاً يُسجَّل عند ٢٣:٣٠ من **اليوم السابق** بتوقيت UTC. حسابُ السلسلة على
UTC يكسر مواظبة كلّ طالبٍ يدرس ليلاً — وهو أكثر أوقات مراجعة البكالوريا شيوعاً. لذلك
كلّ طابع زمني يُحوَّل إلى تاريخٍ **محلّي** قبل أيّ عدّ.

الجزائر على UTC+1 ثابتاً بلا توقيت صيفي، لكنّنا نستعمل `zoneinfo` لا إزاحةً ثابتة:
الإزاحة الثابتة قرارٌ سياسي قد يتغيّر، وقاعدة بيانات المناطق هي المصدر الصحيح.

قاعدة المهلة (grace)
--------------------
السلسلة تبقى حيّة إن كان آخر نشاطٍ **اليوم أو أمس**. بلا ذلك يرى طالبٌ واظب ثلاثين
يوماً «٠» كلّ صباحٍ قبل أن يفتح التطبيق — وهذا يُعاقِب على المواظبة بدل أن يكافئها.
المهلة يومٌ واحد فقط: يومان يجعلان «السلسلة» بلا معنى.

عقد الموقع
----------
stdlib فقط (`zoneinfo` جزءٌ من المكتبة القياسية منذ 3.9). لا استيراد من `app/` ولا من
أيّ خدمة (قانون الحدود §6.7.و).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "ALGIERS_TZ",
    "GRACE_DAYS",
    "HabitError",
    "StreakSummary",
    "active_days",
    "summarize_streak",
]

#: المنطقة الزمنية القانونية لطلاب المنصّة.
ALGIERS_TZ: Final = "Africa/Algiers"

#: كم يوماً تبقى السلسلة حيّة بعد آخر نشاط. ١ = «أمس ما زال يحتسب».
GRACE_DAYS: Final = 1


class HabitError(ValueError):
    """خرقٌ لمجال المواظبة — منطقة زمنية مجهولة أو طابع زمني عارٍ."""


@dataclass(frozen=True)
class StreakSummary:
    """خلاصة مواظبة طالبٍ واحد عند لحظةٍ بعينها."""

    current_streak: int
    longest_streak: int
    total_active_days: int
    active_today: bool
    last_active_on: date | None
    #: `True` حين تكون السلسلة حيّة لكنّ اليوم لم يُسجَّل بعد — إشارة التذكير.
    at_risk: bool


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise HabitError(f"unknown timezone: {timezone_name!r}") from None


def active_days(
    timestamps: Iterable[datetime], *, timezone_name: str = ALGIERS_TZ
) -> tuple[date, ...]:
    """
    يحوّل طوابع النشاط إلى تواريخ محلّية فريدة مرتّبة تصاعدياً.

    الطوابع العارية من المنطقة الزمنية تُفسَّر UTC: هذا ما يُرجِعه SQLite، ورفضُها
    كان سيجعل المواظبة تعمل على Postgres وتنهار على SQLite.
    """
    zone = _zone(timezone_name)
    days = {
        (moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC))
        .astimezone(zone)
        .date()
        for moment in timestamps
    }
    return tuple(sorted(days))


def _longest_run(days: tuple[date, ...]) -> int:
    longest = 0
    run = 0
    previous: date | None = None
    for day in days:
        run = run + 1 if previous is not None and day - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = day
    return longest


def _current_run(days: tuple[date, ...], today: date) -> int:
    """يعدّ الأيام المتتالية المنتهية اليوم أو أمس؛ وإلّا فالسلسلة منقطعة.

    شرطٌ مسبق: `days` غير فارغة ومرتّبة تصاعدياً (يضمنه `summarize_streak`).
    """
    last = days[-1]
    if (today - last).days > GRACE_DAYS:
        return 0
    run = 1
    for earlier, later in zip(reversed(days[:-1]), reversed(days[1:]), strict=False):
        if later - earlier != timedelta(days=1):
            break
        run += 1
    return run


def summarize_streak(
    timestamps: Iterable[datetime],
    *,
    now: datetime,
    timezone_name: str = ALGIERS_TZ,
) -> StreakSummary:
    """يحسب خلاصة المواظبة — حتمي تماماً، صفر عشوائية وصفر LLM."""
    if now.tzinfo is None:
        raise HabitError("now must be timezone-aware")
    zone = _zone(timezone_name)
    today = now.astimezone(zone).date()

    days = active_days(timestamps, timezone_name=timezone_name)
    # نشاطٌ في المستقبل ليس مواظبة — نتجاهله بدل أن نبني عليه سلسلة وهمية.
    days = tuple(day for day in days if day <= today)

    if not days:
        return StreakSummary(
            current_streak=0,
            longest_streak=0,
            total_active_days=0,
            active_today=False,
            last_active_on=None,
            at_risk=False,
        )

    current = _current_run(days, today)
    last = days[-1]
    active_today = last == today
    return StreakSummary(
        current_streak=current,
        longest_streak=max(_longest_run(days), current),
        total_active_days=len(days),
        active_today=active_today,
        last_active_on=last,
        at_risk=current > 0 and not active_today,
    )
