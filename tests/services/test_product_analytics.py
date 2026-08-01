"""اختبارات عمود تحليلات المنتج — D-197.

يُثبت أنّ المنصّة صارت تجيب على السؤال الذي لم تملك له جواباً: **هل نجح ما بنيناه؟**
وأنّ التتبّع **لا يكسر دور طالب أبداً** — تحليلاتٌ تُسقِط تعليماً أسوأ من ألّا تكون.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.services.analytics.product_events import (
    DEFAULT_FUNNEL,
    ProductAnalyticsService,
    record_product_event,
)
from shared.analytics import EventName

NOW = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


async def _make_user(db_session, email: str) -> int:
    result = await db_session.execute(
        text(
            "INSERT INTO users (external_id, full_name, email, password_hash, "
            "is_admin, is_active, status) VALUES (:e, :n, :e, 'x', 0, 1, 'active')"
        ),
        {"e": email, "n": email.split("@")[0]},
    )
    await db_session.commit()
    return int(result.lastrowid)


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


# ── الكتابة ────────────────────────────────────────────────────────────────────


def test_a_canonical_event_is_written(event_loop, db_session) -> None:
    async def scenario() -> None:
        user_id = await _make_user(db_session, "event-writer@example.com")
        assert (
            await record_product_event(
                event_name=EventName.CHAT_TURN_STARTED, user_id=user_id, session_id=7
            )
            is True
        )
        count = await db_session.scalar(
            text(
                "SELECT COUNT(*) FROM product_events "
                "WHERE user_id = :u AND event_name = 'chat_turn_started'"
            ),
            {"u": user_id},
        )
        assert count == 1

    _run(event_loop, scenario())


def test_an_unregistered_event_name_is_refused_and_writes_nothing(event_loop, db_session) -> None:
    """
    اسمٌ خارج السجلّ خطأُ مبرمج — يُرفَض عند الكتابة لا يُكتشَف بعد شهرٍ في لوحة.
    """

    async def scenario() -> None:
        user_id = await _make_user(db_session, "bad-event@example.com")
        assert await record_product_event(event_name="chat_start", user_id=user_id) is False
        count = await db_session.scalar(
            text("SELECT COUNT(*) FROM product_events WHERE user_id = :u"), {"u": user_id}
        )
        assert count == 0

    _run(event_loop, scenario())


def test_a_write_failure_is_swallowed(event_loop, monkeypatch) -> None:
    """عقد العزل: التحليلات لا تكسر دوراً."""

    def boom() -> None:
        raise RuntimeError("database is gone")

    monkeypatch.setattr("app.core.database.async_session_factory", boom)
    assert (
        _run(event_loop, record_product_event(event_name=EventName.USER_SIGNED_IN, user_id=1))
        is False
    )


def test_an_event_may_precede_authentication(event_loop, db_session) -> None:
    async def scenario() -> None:
        assert await record_product_event(event_name=EventName.USER_SIGNED_UP) is True
        count = await db_session.scalar(
            text("SELECT COUNT(*) FROM product_events WHERE user_id IS NULL")
        )
        assert count == 1

    _run(event_loop, scenario())


# ── القراءة ────────────────────────────────────────────────────────────────────


async def _seed_event(db_session, *, user_id: int | None, name: str, when: datetime) -> None:
    await db_session.execute(
        text("INSERT INTO product_events (user_id, event_name, occurred_at) VALUES (:u, :n, :t)"),
        {"u": user_id, "n": name, "t": when},
    )
    await db_session.commit()


def test_retention_reads_real_rows(event_loop, db_session) -> None:
    async def scenario() -> None:
        signup_moment = NOW - timedelta(days=40)
        user_id = await _make_user(db_session, "retained@example.com")
        await _seed_event(
            db_session, user_id=user_id, name=EventName.USER_SIGNED_UP, when=signup_moment
        )
        await _seed_event(
            db_session,
            user_id=user_id,
            name=EventName.CHAT_TURN_STARTED,
            when=signup_moment + timedelta(days=1),
        )

        report = await ProductAnalyticsService(db_session).retention(today=NOW.date())
        cohort = next(c for c in report.cohorts if c.size and c.retained.get(1) is not None)
        assert cohort.retained[1] == pytest.approx(1.0)

    _run(event_loop, scenario())


def test_users_without_a_signup_event_fall_back_to_their_account_date(
    event_loop, db_session
) -> None:
    """
    حساباتٌ سبقت تشغيل التتبّع لا تختفي.

    بدون السقوط إلى `users.created_at` تبدو المنصّة بلا تاريخ يوم تشغيل التتبّع — وهو
    رقمٌ خاطئ يُقرأ كانهيار.
    """

    async def scenario() -> None:
        user_id = await _make_user(db_session, "legacy-account@example.com")
        report = await ProductAnalyticsService(db_session).retention(today=NOW.date())
        assert sum(c.size for c in report.cohorts) >= 1
        assert user_id is not None

    _run(event_loop, scenario())


def test_a_duplicate_signup_event_keeps_the_earliest(event_loop, db_session) -> None:
    """
    الفوج يُحدَّد بأوّل تسجيل لا بآخره.

    حدثٌ مُكرَّر (إعادة محاولة، أو ترحيل) كان سينقل المستخدم إلى فوجٍ أحدث فيُفسد
    كلّ صفٍّ في جدول الاحتفاظ بأثرٍ رجعي.
    """

    async def scenario() -> None:
        user_id = await _make_user(db_session, "duplicate-signup@example.com")
        first = NOW - timedelta(days=40)
        await _seed_event(db_session, user_id=user_id, name=EventName.USER_SIGNED_UP, when=first)
        await _seed_event(
            db_session,
            user_id=user_id,
            name=EventName.USER_SIGNED_UP,
            when=first + timedelta(days=5),
        )
        await _seed_event(
            db_session,
            user_id=user_id,
            name=EventName.CHAT_TURN_STARTED,
            when=first + timedelta(days=1),
        )

        report = await ProductAnalyticsService(db_session).retention(today=NOW.date())
        cohort = next(c for c in report.cohorts if c.cohort_date == first.date())
        assert cohort.retained[1] == pytest.approx(1.0)

    _run(event_loop, scenario())


def test_the_conversion_funnel_follows_the_commercial_path(event_loop, db_session) -> None:
    """تسجيل ⇒ دور ⇒ مراجعة ⇒ دعوة الوليّ ⇒ قبول الوليّ."""

    async def scenario() -> None:
        deep = await _make_user(db_session, "deep-user@example.com")
        shallow = await _make_user(db_session, "shallow-user@example.com")

        for name in DEFAULT_FUNNEL:
            await _seed_event(db_session, user_id=deep, name=name, when=NOW - timedelta(days=1))
        await _seed_event(
            db_session,
            user_id=shallow,
            name=EventName.USER_SIGNED_UP,
            when=NOW - timedelta(days=1),
        )
        await _seed_event(
            db_session,
            user_id=shallow,
            name=EventName.CHAT_TURN_STARTED,
            when=NOW - timedelta(days=1),
        )

        steps = await ProductAnalyticsService(db_session).conversion_funnel()
        assert [step.event_name for step in steps] == list(DEFAULT_FUNNEL)
        assert steps[0].users == 2
        assert steps[1].users == 2
        assert steps[2].users == 1
        assert steps[-1].users == 1
        assert all(step.conversion_from_start <= 1.0 for step in steps)

    _run(event_loop, scenario())


def test_events_outside_the_window_are_excluded(event_loop, db_session) -> None:
    async def scenario() -> None:
        user_id = await _make_user(db_session, "stale-events@example.com")
        await _seed_event(
            db_session,
            user_id=user_id,
            name=EventName.CHAT_TURN_STARTED,
            when=NOW - timedelta(days=400),
        )
        steps = await ProductAnalyticsService(db_session).conversion_funnel(window_days=30)
        assert steps[1].users == 0

    _run(event_loop, scenario())


# ── التوصيل الحيّ ───────────────────────────────────────────────────────────────


def test_signup_over_http_records_the_first_cohort_point(event_loop, client, db_session) -> None:
    """
    قانون «لا ZOMBIE»: الحدث يُكتَب من المسار الحيّ لا من اختبارٍ فقط.
    """
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Cohort Student",
            "email": "cohort-signup@example.com",
            "password": "Str0ng!Passw0rd",
        },
    )
    assert response.status_code == 201, response.text

    async def check() -> int:
        return await db_session.scalar(
            text("SELECT COUNT(*) FROM product_events WHERE event_name = 'user_signed_up'")
        )

    assert _run(event_loop, check()) >= 1


def test_review_queue_view_is_recorded(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    token = _run(event_loop, register_and_login_test_user(db_session, "queue-event@example.com"))
    assert (
        client.get("/api/v1/review/due", headers={"Authorization": f"Bearer {token}"}).status_code
        == 200
    )

    async def check() -> int:
        return await db_session.scalar(
            text("SELECT COUNT(*) FROM product_events WHERE event_name = 'review_queue_viewed'")
        )

    assert _run(event_loop, check()) == 1


def test_guardian_link_issue_is_recorded(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    token = _run(event_loop, register_and_login_test_user(db_session, "link-event@example.com"))
    assert (
        client.post(
            "/api/v1/guardian/link-code", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )

    async def check() -> int:
        return await db_session.scalar(
            text("SELECT COUNT(*) FROM product_events WHERE event_name = 'guardian_link_issued'")
        )

    assert _run(event_loop, check()) == 1


# ── نقاط النهاية الإدارية ───────────────────────────────────────────────────────


def test_analytics_endpoints_require_admin(
    event_loop, client, db_session, register_and_login_test_user
) -> None:
    """أرقام المنصّة ليست عامّة."""
    token = _run(event_loop, register_and_login_test_user(db_session, "not-admin@example.com"))
    for path in ("/api/v1/analytics/retention", "/api/v1/analytics/funnel"):
        response = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403, path


def test_analytics_endpoints_reject_anonymous_callers(client) -> None:
    for path in ("/api/v1/analytics/retention", "/api/v1/analytics/funnel"):
        assert client.get(path).status_code in (401, 403)


async def _admin_token(db_session, email: str) -> str:
    """ينشئ إدارياً بدورٍ حقيقي في RBAC (لا مجرّد `is_admin` في الـ JWT)."""
    from datetime import timedelta as _timedelta

    import jwt
    from sqlalchemy import select

    from app.core.config import get_settings
    from app.core.domain.user import User
    from app.services.rbac import ADMIN_ROLE, RBACService

    await db_session.execute(
        text(
            "INSERT INTO users (external_id, full_name, email, password_hash, "
            "is_admin, is_active, status) VALUES (:e, 'Admin', :e, 'x', 1, 1, 'active')"
        ),
        {"e": email},
    )
    await db_session.commit()

    rbac = RBACService(db_session)
    await rbac.ensure_seed()
    user = await db_session.scalar(select(User).where(User.email == email))
    await rbac.assign_role(user, ADMIN_ROLE)

    return jwt.encode(
        {
            "sub": str(user.id),
            "type": "access",
            "exp": datetime.now(UTC) + _timedelta(hours=1),
        },
        get_settings().SECRET_KEY,
        algorithm="HS256",
    )


def test_an_admin_can_read_retention_and_the_funnel(event_loop, client, db_session) -> None:
    """المسار الإداري السعيد — العقد يُرجِع الشكل المُعلَن."""
    token = _run(event_loop, _admin_token(db_session, "analytics-admin@example.com"))
    headers = {"Authorization": f"Bearer {token}"}

    retention = client.get("/api/v1/analytics/retention", headers=headers)
    assert retention.status_code == 200, retention.text
    body = retention.json()
    assert body["horizons"] == [1, 7, 30]
    assert set(body) == {"generated_for", "horizons", "overall", "cohorts"}

    funnel_response = client.get("/api/v1/analytics/funnel", headers=headers)
    assert funnel_response.status_code == 200, funnel_response.text
    assert [step["event_name"] for step in funnel_response.json()] == list(DEFAULT_FUNNEL)


def test_handlers_shape_the_response_directly(event_loop, db_session) -> None:
    """
    نداءٌ مباشر للمعالِجات.

    معالِجات ASGI تعمل في خيط عاملٍ تحت `TestClient` فلا يتتبّعها `coverage`؛ النداء
    المباشر يُثبِّت تحويل العقد في الخيط الرئيسي.
    """
    from app.api.routers.analytics import conversion_funnel, retention

    service = ProductAnalyticsService(db_session)
    stub_user = type("U", (), {"user": type("I", (), {"id": 1})()})()

    report = _run(event_loop, retention(window_days=30, _=stub_user, service=service))
    assert report.horizons == [1, 7, 30]
    assert isinstance(report.cohorts, list)

    steps = _run(event_loop, conversion_funnel(window_days=30, _=stub_user, service=service))
    assert [step.event_name for step in steps] == list(DEFAULT_FUNNEL)


def test_retention_window_is_bounded(event_loop, client, db_session) -> None:
    token = _run(event_loop, _admin_token(db_session, "window-check@example.com"))
    response = client.get(
        "/api/v1/analytics/retention?window_days=9999",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422
