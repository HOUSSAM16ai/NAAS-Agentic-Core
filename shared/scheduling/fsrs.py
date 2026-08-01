"""FSRS — مُجدوِل التكرار المتباعد الحرّ، حتمي و dep-free (D-194).

لماذا FSRS ولا SM-2
--------------------
SM-2 (خوارزمية Anki القديمة، ١٩٨٧) تحمل **عامل سهولة** واحداً لكلّ بطاقة وتضربه في فاصل
ثابت. FSRS يفصل **ثلاثة** مقادير ذات معنى فيزيائي: الاستقرار `S` (كم يوماً حتى ينزل
احتمال التذكّر إلى الهدف)، والصعوبة `D` (١..١٠)، وقابلية الاسترجاع `R(t,S)` (منحنى نسيان
متّصل). ذلك يجعل الفاصل مُشتقّاً من **احتمال تذكّر مطلوب** بدل ثابتٍ اعتباطي — وهو ما
يسمح للمنصّة أن تقول للطالب «راجع هذا اليوم» بمعنى محدّد: «احتمال أن تتذكّره هبط إلى ٩٠٪».

الصلة بالطبقة المعرفية القائمة
------------------------------
`app/services/skills/bkt_engine.py` يحسب أصلاً `durable_mastery` و`delay_hours`
و`support_level` — أي **منحنى نسيان وإشارة دعم** — ثمّ **يرميها**. هذه الوحدة هي الطرف
المستقبِل: BKT يقيس، وFSRS يجدول. لا تكرار للقياس ولا اختراع لتتبّع إتقانٍ ثانٍ
(CLAUDE.md D-074: «أيّ قدرة تكيّفية تُبنى فوق BKT، ولا تُعيد اختراع تتبّع الإتقان»).

عقد الأخطاء
-----------
كلّ خرقٍ للمجال يرفع `SchedulingError`. **لا قيمة افتراضية مضلِّلة**: فاصلٌ صفري بسبب
استقرارٍ سالب سيُغرِق الطالب بمراجعاتٍ لا معنى لها بدل أن يصرخ (§0: لا فشل صامت).

عقد الموقع
----------
stdlib فقط. لا استيراد من `app/` ولا من أيّ خدمة (قانون الحدود §6.7.و) — فهذه الوحدة
تُوَرَّد إلى `microservices/scheduling_service/` وتحرس تطابقها `check_fsrs_parity`.

المرجع
------
FSRS-5 (Jarrett Ye et al.). المعاملات الافتراضية أدناه هي المعاملات المُدرَّبة المنشورة
على مجموعة مراجعات مفتوحة؛ تُستبدَل لاحقاً بمعاملات مُدرَّبة على بيانات المنصّة نفسها
عبر `parameters=` — وهذا بالضبط سبب تمريرها معاملاً بدل تثبيتها.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import IntEnum
from typing import Final

__all__ = [
    "DECAY",
    "DEFAULT_PARAMETERS",
    "FACTOR",
    "MAXIMUM_INTERVAL_DAYS",
    "MAX_DIFFICULTY",
    "MINIMUM_INTERVAL_DAYS",
    "MIN_DIFFICULTY",
    "REQUEST_RETENTION",
    "Rating",
    "ReviewState",
    "SchedulingError",
    "initial_state",
    "interval_days",
    "is_due",
    "retrievability",
    "review",
]


class SchedulingError(ValueError):
    """خرقٌ لمجال الجدولة — استقرار غير موجب، زمن سالب، أو تقدير خارج المدى."""


class Rating(IntEnum):
    """تقدير المراجعة الرباعي القياسي في FSRS."""

    AGAIN = 1  # لم يتذكّر — انتكاسة
    HARD = 2  # تذكّر بصعوبة
    GOOD = 3  # تذكّر
    EASY = 4  # تذكّر بسهولة تامّة


#: منحنى النسيان: `R(t,S) = (1 + FACTOR·t/S)^DECAY`.
DECAY: Final = -0.5
FACTOR: Final = 19.0 / 81.0

#: احتمال التذكّر المستهدَف عند حلول موعد المراجعة.
REQUEST_RETENTION: Final = 0.90

MIN_DIFFICULTY: Final = 1.0
MAX_DIFFICULTY: Final = 10.0
MINIMUM_INTERVAL_DAYS: Final = 1.0
MAXIMUM_INTERVAL_DAYS: Final = 365.0 * 2

#: معاملات FSRS-5 الافتراضية (١٩ معاملاً، `w[0]`…`w[18]`).
DEFAULT_PARAMETERS: Final[tuple[float, ...]] = (
    0.40255,
    1.18385,
    3.17300,
    15.69105,
    7.19490,
    0.53450,
    1.46040,
    0.00460,
    1.54575,
    0.11920,
    1.01925,
    1.93950,
    0.11000,
    0.29605,
    2.26980,
    0.23150,
    2.98980,
    0.51655,
    0.66210,
)

_EXPECTED_PARAMETER_COUNT: Final = 19


@dataclass(frozen=True)
class ReviewState:
    """حالة عنصرٍ قابل للمراجعة عند لحظةٍ بعينها.

    `stability` باليوم · `difficulty` في [1,10] · `due_at` لحظة استحقاق المراجعة.
    الحقول مُجمَّدة: كلّ مراجعة تُنتِج حالةً **جديدة**، فالسجلّ يبقى سلسلةً زمنية
    قابلة للتدقيق (نفس انضباط `student_bkt_analytics` المُلحَق-فقط، D-074).
    """

    stability: float
    difficulty: float
    due_at: datetime
    last_reviewed_at: datetime
    reps: int = 1
    lapses: int = 0
    state: str = "review"

    def __post_init__(self) -> None:
        if not math.isfinite(self.stability) or self.stability <= 0.0:
            raise SchedulingError(f"stability must be finite and > 0, got {self.stability!r}")
        if not MIN_DIFFICULTY <= self.difficulty <= MAX_DIFFICULTY:
            raise SchedulingError(
                f"difficulty must be within [{MIN_DIFFICULTY},{MAX_DIFFICULTY}], "
                f"got {self.difficulty!r}"
            )
        if self.reps < 0 or self.lapses < 0:
            raise SchedulingError("reps and lapses cannot be negative")
        if self.state not in ("learning", "review", "relearning"):
            raise SchedulingError(f"unknown state: {self.state!r}")
        for label, moment in (("due_at", self.due_at), ("last_reviewed_at", self.last_reviewed_at)):
            if moment.tzinfo is None:
                raise SchedulingError(f"{label} must be timezone-aware")


# ─────────────────────────────────────────────────────────────────────────────
# مساعدات المجال
# ─────────────────────────────────────────────────────────────────────────────


def _validate_parameters(parameters: tuple[float, ...]) -> tuple[float, ...]:
    if len(parameters) != _EXPECTED_PARAMETER_COUNT:
        raise SchedulingError(
            f"FSRS-5 needs exactly {_EXPECTED_PARAMETER_COUNT} parameters, got {len(parameters)}"
        )
    if any(not math.isfinite(value) for value in parameters):
        raise SchedulingError("parameters must all be finite")
    return parameters


def _validate_retention(request_retention: float) -> float:
    if not 0.0 < request_retention < 1.0:
        raise SchedulingError(
            f"request_retention must be strictly within (0,1), got {request_retention!r}"
        )
    return request_retention


def _as_rating(rating: Rating | int) -> Rating:
    try:
        return Rating(int(rating))
    except ValueError:
        raise SchedulingError(
            f"rating must be one of {[r.value for r in Rating]}, got {rating!r}"
        ) from None


def _clamp_difficulty(value: float) -> float:
    return min(MAX_DIFFICULTY, max(MIN_DIFFICULTY, value))


# ─────────────────────────────────────────────────────────────────────────────
# منحنى النسيان
# ─────────────────────────────────────────────────────────────────────────────


def retrievability(elapsed_days: float, stability: float) -> float:
    """احتمال تذكّر العنصر بعد `elapsed_days` يوماً من آخر مراجعة.

    `R(t,S) = (1 + FACTOR·t/S)^DECAY` — يساوي ١ عند `t=0` وينزل إلى `REQUEST_RETENTION`
    عند `t=S` بالضبط (وهذا هو تعريف الاستقرار).
    """
    if stability <= 0.0 or not math.isfinite(stability):
        raise SchedulingError(f"stability must be finite and > 0, got {stability!r}")
    if elapsed_days < 0.0:
        raise SchedulingError(f"elapsed_days cannot be negative, got {elapsed_days!r}")
    return float((1.0 + FACTOR * elapsed_days / stability) ** DECAY)


def interval_days(
    stability: float,
    request_retention: float = REQUEST_RETENTION,
    maximum_interval: float = MAXIMUM_INTERVAL_DAYS,
) -> float:
    """يعكس منحنى النسيان: كم يوماً حتى ينزل التذكّر إلى `request_retention`."""
    if stability <= 0.0 or not math.isfinite(stability):
        raise SchedulingError(f"stability must be finite and > 0, got {stability!r}")
    _validate_retention(request_retention)
    if maximum_interval < MINIMUM_INTERVAL_DAYS:
        raise SchedulingError(
            f"maximum_interval must be >= {MINIMUM_INTERVAL_DAYS}, got {maximum_interval!r}"
        )
    raw = (stability / FACTOR) * (request_retention ** (1.0 / DECAY) - 1.0)
    return float(min(maximum_interval, max(MINIMUM_INTERVAL_DAYS, raw)))


def is_due(state: ReviewState, now: datetime) -> bool:
    """هل حلّ موعد المراجعة؟ يرفض الأزمنة العارية من المنطقة الزمنية."""
    if now.tzinfo is None:
        raise SchedulingError("now must be timezone-aware")
    return now >= state.due_at


# ─────────────────────────────────────────────────────────────────────────────
# معادلات FSRS-5
# ─────────────────────────────────────────────────────────────────────────────


def _initial_stability(rating: Rating, w: tuple[float, ...]) -> float:
    return max(0.1, w[rating.value - 1])


def _initial_difficulty(rating: Rating, w: tuple[float, ...]) -> float:
    return _clamp_difficulty(w[4] - math.exp(w[5] * (rating.value - 1)) + 1.0)


def _next_difficulty(difficulty: float, rating: Rating, w: tuple[float, ...]) -> float:
    """تحديث الصعوبة مع ارتدادٍ نحو المتوسّط — يمنع انحراف الصعوبة بلا حدّ."""
    delta = -w[6] * (rating.value - 3.0)
    damped = difficulty + delta * (10.0 - difficulty) / 9.0
    reverted = w[7] * _initial_difficulty(Rating.EASY, w) + (1.0 - w[7]) * damped
    return _clamp_difficulty(reverted)


def _stability_after_recall(
    stability: float, difficulty: float, r: float, rating: Rating, w: tuple[float, ...]
) -> float:
    hard_penalty = w[15] if rating is Rating.HARD else 1.0
    easy_bonus = w[16] if rating is Rating.EASY else 1.0
    growth = (
        math.exp(w[8])
        * (11.0 - difficulty)
        * (stability ** -w[9])
        * (math.exp(w[10] * (1.0 - r)) - 1.0)
        * hard_penalty
        * easy_bonus
    )
    return float(stability * (1.0 + growth))


def _stability_after_lapse(
    stability: float, difficulty: float, r: float, w: tuple[float, ...]
) -> float:
    """
    الاستقرار بعد انتكاسة — **لا يزيد أبداً** عن الاستقرار السابق.

    قيد FSRS-5 هذا ليس تجميلاً: بدونه يستطيع الفشلُ أن يطيل الفاصل، فيُكافَأ الطالب
    على النسيان — وهو النقيض التامّ لغرض النظام.
    """
    raw = (
        w[11]
        * (difficulty ** -w[12])
        * ((stability + 1.0) ** w[13] - 1.0)
        * math.exp(w[14] * (1.0 - r))
    )
    return float(max(0.1, min(raw, stability)))


# ─────────────────────────────────────────────────────────────────────────────
# السطح العامّ
# ─────────────────────────────────────────────────────────────────────────────


def initial_state(
    rating: Rating | int,
    now: datetime,
    *,
    parameters: tuple[float, ...] = DEFAULT_PARAMETERS,
    request_retention: float = REQUEST_RETENTION,
    maximum_interval: float = MAXIMUM_INTERVAL_DAYS,
) -> ReviewState:
    """أوّل لقاءٍ بمفهوم: يشتقّ الاستقرار والصعوبة الابتدائيَّين ثمّ الموعد."""
    w = _validate_parameters(parameters)
    grade = _as_rating(rating)
    if now.tzinfo is None:
        raise SchedulingError("now must be timezone-aware")

    stability = _initial_stability(grade, w)
    difficulty = _initial_difficulty(grade, w)
    days = interval_days(stability, request_retention, maximum_interval)
    return ReviewState(
        stability=stability,
        difficulty=difficulty,
        due_at=now + timedelta(days=days),
        last_reviewed_at=now,
        reps=1,
        lapses=1 if grade is Rating.AGAIN else 0,
        state="relearning" if grade is Rating.AGAIN else "review",
    )


def review(
    state: ReviewState,
    rating: Rating | int,
    now: datetime,
    *,
    parameters: tuple[float, ...] = DEFAULT_PARAMETERS,
    request_retention: float = REQUEST_RETENTION,
    maximum_interval: float = MAXIMUM_INTERVAL_DAYS,
) -> ReviewState:
    """يطبّق مراجعةً على حالةٍ قائمة ويُرجِع الحالة التالية (لا يُعدِّل الأصل)."""
    w = _validate_parameters(parameters)
    grade = _as_rating(rating)
    if now.tzinfo is None:
        raise SchedulingError("now must be timezone-aware")
    if now < state.last_reviewed_at:
        raise SchedulingError("a review cannot happen before the previous one")

    elapsed = (now - state.last_reviewed_at).total_seconds() / 86400.0
    r = retrievability(elapsed, state.stability)

    if grade is Rating.AGAIN:
        stability = _stability_after_lapse(state.stability, state.difficulty, r, w)
        lapses = state.lapses + 1
        next_state = "relearning"
    else:
        stability = _stability_after_recall(state.stability, state.difficulty, r, grade, w)
        lapses = state.lapses
        next_state = "review"

    difficulty = _next_difficulty(state.difficulty, grade, w)
    days = interval_days(stability, request_retention, maximum_interval)

    return replace(
        state,
        stability=stability,
        difficulty=difficulty,
        due_at=now + timedelta(days=days),
        last_reviewed_at=now,
        reps=state.reps + 1,
        lapses=lapses,
        state=next_state,
    )


def _utcnow() -> datetime:  # pragma: no cover - trivial indirection for callers
    return datetime.now(UTC)
