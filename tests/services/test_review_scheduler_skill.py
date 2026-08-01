"""اختبارات مهارة جدولة المراجعة — D-194.

العقد المركزي المُختبَر: **الدعم يُقصِّر الفاصل**. إجابةٌ صحيحة بسقالةٍ كاملة لا تستحقّ
موعداً بعيداً، وإلّا صار الجدول يقيس الأداء اللحظي فيُؤتمِت وَهْم الطلاقة بدل محاربته
(§0.6 — فجوة الوهم هي مقياس النجاح الوحيد).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.services.skills.review_scheduler_skill import (
    DURABLE_MASTERY_FOR_EASY,
    LIGHT_SUPPORT_LEVEL,
    UNAIDED_SUPPORT_LEVEL,
    ReviewDecision,
    ReviewSchedulerInput,
    ReviewSchedulerSkill,
    derive_rating,
    get_review_scheduler_skill,
)
from shared.scheduling.fsrs import Rating, ReviewState, initial_state

NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


def _payload(**overrides: object) -> ReviewSchedulerInput:
    base: dict[str, object] = {
        "concept_id": "probability",
        "evidence_correct": True,
        "correctness_signal": "correct",
        "durable_mastery": 0.5,
        "support_level": 3,
    }
    base.update(overrides)
    return ReviewSchedulerInput(**base)  # type: ignore[arg-type]


# ── اشتقاق التقدير ──────────────────────────────────────────────────────────────


def test_incorrect_evidence_is_a_lapse() -> None:
    assert derive_rating(_payload(evidence_correct=False, correctness_signal="incorrect")) is (
        Rating.AGAIN
    )


def test_unknown_signal_yields_no_rating_at_all() -> None:
    """لا دليل ⇒ لا قرار. الجدولة على لا-دليل ضجيجٌ يُغرِق الطالب."""
    assert derive_rating(_payload(correctness_signal="unknown")) is None


def test_unaided_and_durable_earns_easy() -> None:
    rating = derive_rating(
        _payload(support_level=UNAIDED_SUPPORT_LEVEL, durable_mastery=DURABLE_MASTERY_FOR_EASY)
    )
    assert rating is Rating.EASY


def test_light_support_earns_good() -> None:
    assert derive_rating(_payload(support_level=LIGHT_SUPPORT_LEVEL)) is Rating.GOOD


def test_heavy_support_earns_hard_even_when_correct() -> None:
    """قلب العقد: صحيحٌ بسقالةٍ كاملة ⇒ `HARD` لا `GOOD`."""
    assert derive_rating(_payload(support_level=1, durable_mastery=0.99)) is Rating.HARD


def test_missing_support_level_is_treated_as_heavily_supported() -> None:
    """
    الافتراض الآمن: غياب المعلومة ليس دليل استقلال.

    في الدردشة الحرّة `support_level=None`؛ افتراض «بلا دعم» كان سيمنح فواصل طويلة
    بلا أيّ دليل على إتقانٍ دائم.
    """
    assert derive_rating(_payload(support_level=None, durable_mastery=0.99)) is Rating.HARD


def test_unaided_but_not_durable_does_not_earn_easy() -> None:
    rating = derive_rating(_payload(support_level=UNAIDED_SUPPORT_LEVEL, durable_mastery=0.40))
    assert rating is Rating.GOOD


# ── القرار الكامل ───────────────────────────────────────────────────────────────


def test_first_contact_schedules_and_reports_first_review() -> None:
    decision = get_review_scheduler_skill().decide(_payload(), now=NOW)
    assert decision.scheduled is True
    assert decision.reason == "first_review"
    assert decision.due_at is not None and decision.due_at > NOW
    assert decision.interval_days is not None and decision.interval_days > 0
    assert decision.state == "review"


def test_no_evidence_returns_an_unscheduled_decision_not_an_exception() -> None:
    decision = get_review_scheduler_skill().decide(_payload(correctness_signal="unknown"), now=NOW)
    assert decision == ReviewDecision(
        concept_id="probability", scheduled=False, reason="no_evidence"
    )


def test_supported_correctness_yields_a_shorter_interval_than_unaided() -> None:
    """البرهان العددي على العقد — لا مجرّد اختلاف التقدير."""
    skill = get_review_scheduler_skill()
    supported = skill.decide(_payload(support_level=1, durable_mastery=0.95), now=NOW)
    unaided = skill.decide(
        _payload(support_level=UNAIDED_SUPPORT_LEVEL, durable_mastery=0.95), now=NOW
    )
    assert supported.interval_days is not None
    assert unaided.interval_days is not None
    assert supported.interval_days < unaided.interval_days


def test_recurring_review_builds_on_the_previous_state() -> None:
    skill = get_review_scheduler_skill()
    previous = initial_state(Rating.GOOD, NOW)
    decision = skill.decide(_payload(), now=previous.due_at, previous=previous)
    assert decision.reason == "recurring_review"
    assert decision.stability is not None and decision.stability > previous.stability


def test_a_lapse_after_progress_shortens_the_schedule_and_counts() -> None:
    skill = get_review_scheduler_skill()
    state = initial_state(Rating.GOOD, NOW)
    for _ in range(3):
        state = initial_state(Rating.GOOD, NOW) if state is None else state
        decision = skill.decide(_payload(), now=state.due_at, previous=state)
        state = ReviewState(
            stability=decision.stability,  # type: ignore[arg-type]
            difficulty=decision.difficulty,  # type: ignore[arg-type]
            due_at=decision.due_at,  # type: ignore[arg-type]
            last_reviewed_at=state.due_at,
            reps=state.reps + 1,
            lapses=decision.lapses or 0,
            state=decision.state or "review",
        )
    lapsed = skill.decide(
        _payload(evidence_correct=False, correctness_signal="incorrect"),
        now=state.due_at,
        previous=state,
    )
    assert lapsed.lapses == state.lapses + 1
    assert lapsed.state == "relearning"
    assert lapsed.stability is not None and lapsed.stability <= state.stability


def test_scheduling_error_is_reported_not_raised() -> None:
    """
    مسار الطالب لا يُسقَط بخطأ جدولة.

    نمرّر حالةً سابقة لاحقةً زمنياً للحظة المراجعة — خرقٌ يرفعه المحرّك، ويجب أن
    يصل هنا **قراراً** لا استثناءً.
    """
    previous = initial_state(Rating.GOOD, NOW)
    decision = get_review_scheduler_skill().decide(
        _payload(), now=NOW - timedelta(days=2), previous=previous
    )
    assert decision.scheduled is False
    assert decision.reason.startswith("scheduling_error")


# ── عقد المهارة ────────────────────────────────────────────────────────────────


def test_skill_identity_and_singleton() -> None:
    assert ReviewSchedulerSkill.name == "review_scheduler"
    assert get_review_scheduler_skill() is get_review_scheduler_skill()


def test_run_delegates_to_decide() -> None:
    skill = get_review_scheduler_skill()
    payload = _payload()
    assert skill.run(payload, now=NOW) == skill.decide(payload, now=NOW)


def test_skill_is_registered_with_a_live_consumer() -> None:
    """قانون «لا ZOMBIE»: المهارة مُسجَّلة ولها مُستهلك مُصرَّح."""
    from app.services.skills.registry import get_skill_registry

    descriptor = get_skill_registry().get("review_scheduler")
    assert descriptor is not None
    assert descriptor.status == "ACTIVE"
    assert "customer_chat._evaluate_bkt_cards" in descriptor.consumed_by


@pytest.mark.parametrize("support", [0, 6, -1])
def test_support_level_outside_the_five_point_ladder_is_rejected(support: int) -> None:
    with pytest.raises(ValueError):
        ReviewSchedulerInput(
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            support_level=support,
        )
