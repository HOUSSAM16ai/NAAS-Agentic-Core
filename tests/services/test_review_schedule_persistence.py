"""اختبارات تخزين جدول المراجعة + نقطة `/api/v1/review/due` — D-194.

تُثبِت الدورة الكاملة على قاعدة بيانات حقيقية: تقييمٌ يُنتِج موعداً ⇒ الموعد يُخزَّن
مُلحَقاً ⇒ الطابور يُرجِعه حين يحين ⇒ الترتيب بوزن الامتحان لا بالصدفة.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.services.review import ReviewScheduleService
from app.services.review.persistence import _as_utc

NOW = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)


async def _make_user(db_session, email: str = "review-student@example.com") -> int:
    result = await db_session.execute(
        text(
            "INSERT INTO users (external_id, full_name, email, password_hash, "
            "is_admin, is_active, status) VALUES (:e, :n, :e, 'x', 0, 1, 'active')"
        ),
        {"e": email, "n": "Review Student"},
    )
    await db_session.commit()
    return int(result.lastrowid)


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


# ── الدورة الكاملة ──────────────────────────────────────────────────────────────


def test_a_correct_unaided_answer_creates_a_real_future_review(event_loop, db_session) -> None:
    """العقد الحيّ: إشارة BKT التي كانت تُرمى صارت صفّاً في قاعدة البيانات."""

    async def scenario() -> None:
        user_id = await _make_user(db_session)
        service = ReviewScheduleService(db_session)

        decision = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        )

        assert decision is not None
        assert decision.scheduled is True
        assert decision.due_at is not None and decision.due_at > NOW

        stored = await service.latest_state(user_id, "probability")
        assert stored is not None
        assert stored.stability == pytest.approx(decision.stability)
        assert stored.reps == 1

    _run(event_loop, scenario())


def test_no_evidence_writes_no_row(event_loop, db_session) -> None:
    """لا دليل ⇒ لا صفّ. الجدول لا يمتلئ بضجيج."""

    async def scenario() -> None:
        user_id = await _make_user(db_session, "no-evidence@example.com")
        service = ReviewScheduleService(db_session)

        decision = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="unknown",
            durable_mastery=0.5,
            support_level=3,
            now=NOW,
        )

        assert decision is not None and decision.scheduled is False
        assert await service.latest_state(user_id, "probability") is None

    _run(event_loop, scenario())


def test_the_log_is_append_only_and_reps_accumulate(event_loop, db_session) -> None:
    """
    مراجعتان ⇒ صفّان، والحيّ هو الأحدث.

    السلسلة الكاملة لازمة لإعادة تدريب معاملات FSRS على بيانات المنصّة لاحقاً؛
    التحديث في المكان يُهدِرها بلا رجعة.
    """

    async def scenario() -> None:
        user_id = await _make_user(db_session, "append-only@example.com")
        service = ReviewScheduleService(db_session)

        first = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        )
        assert first is not None and first.due_at is not None

        second = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=first.due_at,
        )
        assert second is not None and second.scheduled

        rows = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM student_review_schedule "
                "WHERE user_id = :u AND concept_id = 'probability'"
            ),
            {"u": user_id},
        )
        assert rows.scalar() == 2

        latest = await service.latest_state(user_id, "probability")
        assert latest is not None
        assert latest.reps == 2
        assert latest.stability > first.stability  # type: ignore[operator]

    _run(event_loop, scenario())


def test_a_lapse_shortens_the_next_due_date(event_loop, db_session) -> None:
    async def scenario() -> None:
        user_id = await _make_user(db_session, "lapse@example.com")
        service = ReviewScheduleService(db_session)

        good = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="integration",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        )
        assert good is not None and good.interval_days is not None

        lapse = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="integration",
            evidence_correct=False,
            correctness_signal="incorrect",
            durable_mastery=0.9,
            support_level=5,
            now=good.due_at,  # type: ignore[arg-type]
        )
        assert lapse is not None and lapse.interval_days is not None
        assert lapse.interval_days < good.interval_days
        assert lapse.state == "relearning"

    _run(event_loop, scenario())


# ── الطابور ─────────────────────────────────────────────────────────────────────


def test_due_queue_only_returns_what_is_actually_due(event_loop, db_session) -> None:
    async def scenario() -> None:
        user_id = await _make_user(db_session, "queue@example.com")
        service = ReviewScheduleService(db_session)

        await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        )

        assert await service.due_reviews(user_id, now=NOW) == []

        later = NOW + timedelta(days=400)
        due = await service.due_reviews(user_id, now=later)
        assert [item.concept_id for item in due] == ["probability"]
        assert due[0].overdue_days > 0
        assert due[0].title == "الاحتمالات"

    _run(event_loop, scenario())


def test_due_queue_is_ordered_by_exam_weight(event_loop, db_session) -> None:
    """
    ترتيب الطابور قرارٌ تربوي لا تفصيل عرض.

    وقت الطالب محدود: مفهومٌ متواتر في مادةٍ معاملها ٦ يسبق مفهوماً نادراً في مادة
    معاملها ٢ — وإلّا صار «ماذا أراجع اليوم؟» جواباً عشوائياً.
    """

    async def scenario() -> None:
        user_id = await _make_user(db_session, "weighted@example.com")
        service = ReviewScheduleService(db_session)

        for concept_id in ("statistics", "immunology", "probability"):
            await service.schedule_from_evaluation(
                user_id=user_id,
                concept_id=concept_id,
                evidence_correct=False,
                correctness_signal="incorrect",
                durable_mastery=0.1,
                support_level=1,
                now=NOW,
            )

        due = await service.due_reviews(user_id, now=NOW + timedelta(days=10))
        weights = [item.exam_weight for item in due]
        assert weights == sorted(weights, reverse=True)
        # علوم الطبيعة معاملها ٦ وتواترها ٠٫٩ ⇒ تسبق الإحصاء (معامل ٥، تواتر ٠٫٣).
        assert due[0].concept_id == "immunology"
        assert due[-1].concept_id == "statistics"

    _run(event_loop, scenario())


def test_a_concept_outside_the_registry_still_appears_without_a_weight(
    event_loop, db_session
) -> None:
    """صفٌّ قديم بمُعرَّف مجهول يُعرَض بلا وزن — لا يختفي ولا يُسقِط الطابور."""

    async def scenario() -> None:
        user_id = await _make_user(db_session, "legacy-concept@example.com")
        await db_session.execute(
            text(
                "INSERT INTO student_review_schedule (user_id, concept_id, rating, stability,"
                " difficulty, reps, lapses, state, interval_days, reviewed_at, due_at)"
                " VALUES (:u, 'phlogiston', 3, 5.0, 5.0, 1, 0, 'review', 5.0, :t, :d)"
            ),
            {"u": user_id, "t": NOW, "d": NOW},
        )
        await db_session.commit()

        due = await ReviewScheduleService(db_session).due_reviews(
            user_id, now=NOW + timedelta(days=1)
        )
        assert [item.concept_id for item in due] == ["phlogiston"]
        assert due[0].exam_weight == 0.0
        assert due[0].title == "phlogiston"

    _run(event_loop, scenario())


def test_the_queue_respects_its_limit(event_loop, db_session) -> None:
    async def scenario() -> None:
        user_id = await _make_user(db_session, "limit@example.com")
        service = ReviewScheduleService(db_session)
        for concept_id in ("probability", "integration", "immunology"):
            await service.schedule_from_evaluation(
                user_id=user_id,
                concept_id=concept_id,
                evidence_correct=False,
                correctness_signal="incorrect",
                durable_mastery=0.1,
                support_level=1,
                now=NOW,
            )
        due = await service.due_reviews(user_id, now=NOW + timedelta(days=5), limit=2)
        assert len(due) == 2

    _run(event_loop, scenario())


# ── العزل: الجدولة لا تكسر دور الطالب أبداً ──────────────────────────────────────


def test_scheduling_failure_is_swallowed_not_raised(event_loop, db_session, monkeypatch) -> None:
    """
    عقد العزل (نفس عقد BKT — D-074).

    نُفشِل الكتابة عمداً ونتأكّد أنّ المُستدعي يتلقّى `None` لا استثناءً: دورُ الطالب
    أهمّ من جدوله.
    """

    async def scenario() -> None:
        user_id = await _make_user(db_session, "isolated@example.com")
        service = ReviewScheduleService(db_session)

        async def boom() -> None:
            raise RuntimeError("database is on fire")

        monkeypatch.setattr(service.db, "commit", boom)

        result = await service.schedule_from_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        )
        assert result is None

    _run(event_loop, scenario())


def test_a_corrupt_row_does_not_freeze_the_schedule_forever(event_loop, db_session) -> None:
    """صفٌّ تالف (استقرار صفري) يُتجاوَز بصوت، فيبدأ الطالب من جديد بدل أن يعلق."""

    async def scenario() -> None:
        user_id = await _make_user(db_session, "corrupt@example.com")
        await db_session.execute(
            text(
                "INSERT INTO student_review_schedule (user_id, concept_id, rating, stability,"
                " difficulty, reps, lapses, state, interval_days, reviewed_at, due_at)"
                " VALUES (:u, 'probability', 3, 0.0, 5.0, 1, 0, 'review', 1.0, :t, :d)"
            ),
            {"u": user_id, "t": NOW, "d": NOW},
        )
        await db_session.commit()

        assert await ReviewScheduleService(db_session).latest_state(user_id, "probability") is None

    _run(event_loop, scenario())


def test_the_chat_entry_point_owns_its_session(event_loop, db_session) -> None:
    """
    `schedule_review_after_evaluation` تفتح جلستها بنفسها.

    الجلسة لا تُدار في المُوجِّه: إدارة الجلسات منطق نطاق، وتفرض ذلك بوّابة
    `check_router_domain_logic` بدَينٍ مُجمَّد **يتقلّص فقط** — فرفعُه لتمرير وصلةٍ
    جديدة كان سيحوّل الحدّ المعماري إلى شعار.
    """
    from app.services.review import schedule_review_after_evaluation

    async def scenario() -> None:
        user_id = await _make_user(db_session, "owns-session@example.com")
        decision = await schedule_review_after_evaluation(
            user_id=user_id,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        )
        assert decision is not None and decision.scheduled is True

        # الصفّ كُتب في جلسةٍ أخرى — نراه من هذه الجلسة.
        count = await db_session.scalar(
            text(
                "SELECT COUNT(*) FROM student_review_schedule "
                "WHERE user_id = :u AND concept_id = 'probability'"
            ),
            {"u": user_id},
        )
        assert count == 1

    _run(event_loop, scenario())


def test_the_chat_entry_point_swallows_a_broken_session(event_loop, monkeypatch) -> None:
    """فشل فتح الجلسة يُبتلَع — دورُ الطالب لا يسقط بسبب جدوله."""
    from app.services.review import persistence, schedule_review_after_evaluation

    def boom() -> None:
        raise RuntimeError("no database today")

    monkeypatch.setattr("app.core.database.async_session_factory", boom)

    result = _run(
        event_loop,
        schedule_review_after_evaluation(
            user_id=1,
            concept_id="probability",
            evidence_correct=True,
            correctness_signal="correct",
            durable_mastery=0.9,
            support_level=5,
            now=NOW,
        ),
    )
    assert result is None
    assert persistence.schedule_review_after_evaluation is schedule_review_after_evaluation


def test_naive_timestamps_from_sqlite_are_normalised_to_utc() -> None:
    """
    SQLite يُعيد أزمنةً عارية وFSRS يرفضها عمداً.

    بلا هذا التطبيع تعمل الجدولة على Postgres وتنكسر على SQLite — أسوأ صنف عطب.
    """
    naive = datetime(2026, 8, 1, 9, 0)
    assert _as_utc(naive).tzinfo is UTC
    aware = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
    assert _as_utc(aware) is aware


# ── نقطة النهاية ───────────────────────────────────────────────────────────────


def test_due_endpoint_requires_authentication(client) -> None:
    assert client.get("/api/v1/review/due").status_code in (401, 403)


def test_due_endpoint_returns_the_students_queue(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    async def seed() -> str:
        token = await register_and_login_test_user(db_session, "queue-api@example.com")
        user_id = await db_session.scalar(
            text("SELECT id FROM users WHERE email = 'queue-api@example.com'")
        )
        await db_session.execute(
            text(
                "INSERT INTO student_review_schedule (user_id, concept_id, rating, stability,"
                " difficulty, reps, lapses, state, interval_days, reviewed_at, due_at)"
                " VALUES (:u, 'immunology', 1, 1.0, 6.0, 1, 1, 'relearning', 1.0, :t, :d)"
            ),
            {
                "u": user_id,
                "t": datetime.now(UTC) - timedelta(days=3),
                "d": datetime.now(UTC) - timedelta(days=2),
            },
        )
        await db_session.commit()
        return token

    token = _run(event_loop, seed())

    response = client.get("/api/v1/review/due", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["concept_id"] == "immunology"
    assert body["items"][0]["title"] == "المناعة"
    assert body["items"][0]["overdue_days"] > 0


def test_due_endpoint_falls_back_to_the_default_stream_on_a_bad_one(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    token = _run(event_loop, register_and_login_test_user(db_session, "bad-stream@example.com"))
    response = client.get(
        "/api/v1/review/due?stream=philosophy",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["stream"] == "experimental_sciences"


def test_due_endpoint_rejects_an_out_of_range_limit(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    token = _run(event_loop, register_and_login_test_user(db_session, "limit-api@example.com"))
    response = client.get(
        "/api/v1/review/due?limit=999", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 422
