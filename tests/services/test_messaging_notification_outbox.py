"""أثرُ المستهلك في قاعدة البيانات — D-201.

هذا الملفّ هو ما يمنع الناقل من أن يكون ZOMBIE: حدثٌ يعبر الناقل ⇒ **صفٌّ حقيقي** في
`notification_outbox`. بلا هذا الاختبار يبقى الادّعاء «الطبقة حيّة» بلا الساق الثالثة
من البرهان (§6.6: import + call chain + **runtime evidence**).
"""

from __future__ import annotations

from sqlalchemy import text

from app.services.messaging import consumers
from app.services.messaging.notifications import handle_product_event
from app.services.messaging.runtime import build_envelope
from shared.messaging import Topic


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


def _outbox_rows(event_loop, db_session) -> list[tuple]:
    result = _run(
        event_loop,
        db_session.execute(
            text("SELECT event_id, user_id, template, status FROM notification_outbox")
        ),
    )
    return list(result.fetchall())


def test_a_guardian_link_event_becomes_a_queued_notification(event_loop, db_session) -> None:
    envelope = build_envelope(
        topic=Topic.PRODUCT_EVENTS,
        event_name="guardian_link_accepted",
        payload={"user_id": 41},
    )

    _run(event_loop, handle_product_event(envelope))

    rows = _outbox_rows(event_loop, db_session)
    assert len(rows) == 1
    assert rows[0][0] == envelope.event_id
    assert rows[0][1] == 41
    assert rows[0][2] == "guardian_linked"
    assert rows[0][3] == "pending"


def test_an_event_without_a_rule_writes_nothing(event_loop, db_session) -> None:
    """الافتراض هو الصمت — لا صفَّ «احتياطاً»."""
    _run(
        event_loop,
        handle_product_event(
            build_envelope(
                topic=Topic.PRODUCT_EVENTS,
                event_name="chat_turn_started",
                payload={"user_id": 41},
            )
        ),
    )
    assert _outbox_rows(event_loop, db_session) == []


def test_a_redelivered_event_does_not_notify_the_student_twice(event_loop, db_session) -> None:
    """
    إعادة التسليم هي الوضع **الطبيعي**. الحَكَم قيدٌ فريد في قاعدة البيانات لا فحصٌ في
    التطبيق: «افحص ثمّ اكتب» نافذة سباق يعبرها طلبان متزامنان فيصل الطالبَ إشعاران.
    """
    envelope = build_envelope(
        topic=Topic.PRODUCT_EVENTS,
        event_name="guardian_link_accepted",
        payload={"user_id": 41},
    )

    _run(event_loop, handle_product_event(envelope))
    _run(event_loop, handle_product_event(envelope))

    assert len(_outbox_rows(event_loop, db_session)) == 1


def test_the_full_path_from_the_bus_writes_the_row(event_loop, db_session) -> None:
    """المسار كاملاً: نشرٌ ⇒ سحبٌ ⇒ مشترك ⇒ صفّ. هذا هو دليل السلسلة الحيّة."""
    from shared.messaging import InMemoryEventBus

    consumers.reset_subscribers()
    consumers.reset_ledger()
    from app.services.messaging.notifications import register_subscribers

    register_subscribers()

    bus = InMemoryEventBus()
    _run(
        event_loop,
        bus.publish(
            build_envelope(
                topic=Topic.PRODUCT_EVENTS,
                event_name="guardian_link_accepted",
                payload={"user_id": 9},
            )
        ),
    )

    outcomes = _run(event_loop, consumers.drain(bus, Topic.PRODUCT_EVENTS))

    assert [outcome.handled for outcome in outcomes] == [True]
    assert len(_outbox_rows(event_loop, db_session)) == 1
    consumers.reset_subscribers()
    consumers.reset_ledger()
