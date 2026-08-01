"""حساب الاحتفاظ والأفواج والقُمع — حتمي، dep-free (D-197).

لماذا الحساب هنا لا في SQL
--------------------------
منطق الاحتفاظ يجب أن يعمل بنفس النتيجة على SQLite (الاختبارات) وPostgres (الإنتاج).
`date_trunc` و`generate_series` و`INTERVAL` تختلف بين المحرّكين، ونسختان من التعريف
تعنيان رقمين مختلفين لنفس السؤال — وهذا أسوأ من ألّا يكون هناك رقم. لذا: SQL يجلب
الصفوف الخام، والتعريف يعيش هنا مرّةً واحدة ويُختبَر بلا قاعدة بيانات أصلاً.

التعاريف المُعتمَدة
-------------------
**الفوج** = يوم التسجيل (بتقويم الطالب المحلّي، لا UTC — نفس قاعدة D-195).
**احتفاظ اليوم N** = نسبة أعضاء الفوج الذين كان لهم نشاطٌ في **اليوم N بالضبط** بعد
التسجيل. هذا هو التعريف «الكلاسيكي» (bounded)، لا «unbounded» (نشاط في اليوم N أو
بعده). الفرق ليس تفصيلاً: unbounded يُعطي أرقاماً أعلى دائماً، وخلطُ التعريفين بين
لوحتين يجعل المقارنة كذباً. **إن غُيِّر التعريف يوماً فليُغيَّر هنا وحده.**

**فوجٌ غير ناضج لا يُحتسَب**: من سجّل أمس لا يمكن قياس احتفاظ اليوم السابع لديه. نُرجِع
`None` لا صفراً — صفرٌ هنا يعني «فقدناهم» بينما الحقيقة «لم يحن الوقت» (§0: المجهول
أفضل من يقين زائف).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

__all__ = [
    "DEFAULT_HORIZONS",
    "CohortRetention",
    "FunnelStep",
    "RetentionReport",
    "cohort_retention",
    "funnel",
    "retention_report",
]

#: آفاق الاحتفاظ المُبلَّغ عنها افتراضياً.
DEFAULT_HORIZONS: Final[tuple[int, ...]] = (1, 7, 30)

_ALGIERS: Final = "Africa/Algiers"


@dataclass(frozen=True)
class CohortRetention:
    """احتفاظ فوجٍ واحد (يوم تسجيل واحد)."""

    cohort_date: date
    size: int
    #: الأفق → النسبة [0,1]، أو `None` إن لم ينضج الفوج بعد.
    retained: Mapping[int, float | None]


@dataclass(frozen=True)
class RetentionReport:
    """تقرير الاحتفاظ الكامل."""

    generated_for: date
    horizons: tuple[int, ...]
    cohorts: tuple[CohortRetention, ...]
    #: المتوسّط المرجّح بحجم الفوج عبر الأفواج الناضجة فقط.
    overall: Mapping[int, float | None]


@dataclass(frozen=True)
class FunnelStep:
    """خطوة في قُمع التحويل."""

    event_name: str
    users: int
    #: النسبة من الخطوة الأولى [0,1].
    conversion_from_start: float
    #: النسبة من الخطوة السابقة [0,1].
    conversion_from_previous: float


def _zone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        raise ValueError(f"unknown timezone: {timezone_name!r}") from None


def _local_date(moment: datetime, zone: ZoneInfo) -> date:
    from datetime import UTC

    aware = moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
    return aware.astimezone(zone).date()


def cohort_retention(
    *,
    signups: Mapping[int, datetime],
    activity: Mapping[int, Iterable[datetime]],
    today: date,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    timezone_name: str = _ALGIERS,
) -> tuple[CohortRetention, ...]:
    """
    يحسب احتفاظ كلّ فوج.

    `signups`: مُعرَّف المستخدم → لحظة التسجيل.
    `activity`: مُعرَّف المستخدم → لحظات نشاطه.
    """
    if any(horizon < 1 for horizon in horizons):
        raise ValueError("horizons must all be >= 1")
    zone = _zone(timezone_name)

    cohorts: dict[date, list[int]] = {}
    joined_on: dict[int, date] = {}
    for user_id, moment in signups.items():
        day = _local_date(moment, zone)
        joined_on[user_id] = day
        cohorts.setdefault(day, []).append(user_id)

    active_days: dict[int, set[date]] = {
        user_id: {_local_date(moment, zone) for moment in moments}
        for user_id, moments in activity.items()
    }

    results: list[CohortRetention] = []
    for cohort_date in sorted(cohorts):
        members = cohorts[cohort_date]
        retained: dict[int, float | None] = {}
        for horizon in sorted(horizons):
            # فوجٌ لم ينضج: لا يمكن قياس اليوم N قبل مرور N يوماً.
            if (today - cohort_date).days < horizon:
                retained[horizon] = None
                continue
            target = cohort_date.fromordinal(cohort_date.toordinal() + horizon)
            hits = sum(1 for user_id in members if target in active_days.get(user_id, set()))
            retained[horizon] = hits / len(members)
        results.append(
            CohortRetention(cohort_date=cohort_date, size=len(members), retained=retained)
        )
    return tuple(results)


def retention_report(
    *,
    signups: Mapping[int, datetime],
    activity: Mapping[int, Iterable[datetime]],
    today: date,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    timezone_name: str = _ALGIERS,
) -> RetentionReport:
    """التقرير الكامل + المتوسّط المرجّح عبر الأفواج **الناضجة وحدها**."""
    cohorts = cohort_retention(
        signups=signups,
        activity=activity,
        today=today,
        horizons=horizons,
        timezone_name=timezone_name,
    )

    overall: dict[int, float | None] = {}
    for horizon in sorted(horizons):
        mature = [c for c in cohorts if c.retained.get(horizon) is not None]
        total = sum(c.size for c in mature)
        if not mature or total == 0:
            # لا فوج ناضج ⇒ لا رقم. صفرٌ هنا يقرأ «فقدنا الجميع» وهو كذب.
            overall[horizon] = None
            continue
        weighted = sum((c.retained[horizon] or 0.0) * c.size for c in mature)
        overall[horizon] = weighted / total

    return RetentionReport(
        generated_for=today,
        horizons=tuple(sorted(horizons)),
        cohorts=cohorts,
        overall=overall,
    )


def funnel(
    *,
    steps: Sequence[str],
    users_by_event: Mapping[str, Iterable[int]],
) -> tuple[FunnelStep, ...]:
    """
    قُمع تحويل مرتّب.

    كلّ خطوة تُحسَب على **من أتمّ كلّ الخطوات السابقة** لا على كلّ من أطلق الحدث: قُمعٌ
    بلا هذا الشرط يستطيع أن يُظهِر تحويلاً يفوق ١٠٠٪، وهو ما يجعل اللوحة بلا معنى.
    """
    if not steps:
        return ()

    remaining: set[int] | None = None
    first_count = 0
    previous_count = 0
    results: list[FunnelStep] = []

    for index, event_name in enumerate(steps):
        cohort = set(users_by_event.get(event_name, ()))
        remaining = cohort if remaining is None else remaining & cohort
        count = len(remaining)
        if index == 0:
            first_count = count
            previous_count = count
        results.append(
            FunnelStep(
                event_name=event_name,
                users=count,
                conversion_from_start=(count / first_count) if first_count else 0.0,
                conversion_from_previous=(count / previous_count) if previous_count else 0.0,
            )
        )
        previous_count = count
    return tuple(results)
