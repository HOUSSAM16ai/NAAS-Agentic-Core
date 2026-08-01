"""اختبارات عامل Temporal بلا خادم — D-201.

**الحدّ الصادق:** خادم Temporal غير مُشغَّل في هذه البيئة، فالعامل نفسه DORMANT.
المُختبَر هنا هو ما **يمكن** إثباته: أنّ كل نشاطٍ تسمّيه خطّة موصولٌ فعلاً، وأنّ
الأنشطة تعمل كدوالّ عادية على قاعدة بيانات حقيقية، وأنّ المهلة العليا مشتقّة لا مُصلَّبة.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.workflows.temporal_worker import (
    ACTIVITIES,
    build_weekly_reports,
    collect_linked_guardians,
    missing_activities,
    queue_guardian_notifications,
    workflow_execution_timeout,
)
from shared.workflows import WorkflowName, plan_for


def _run(event_loop, coro):
    return event_loop.run_until_complete(coro)


def test_the_guardian_workflow_names_only_implemented_activities() -> None:
    """
    خطوةٌ تسمّي نشاطاً غائباً تفشل بعد ستّة أيام من الانتظار — أسوأ وقتٍ لاكتشاف خطأ
    مطبعي. الفحص ينقله إلى زمن الاختبار.
    """
    assert missing_activities(WorkflowName.GUARDIAN_WEEKLY_REPORT) == ()


@pytest.mark.parametrize(
    "name", [WorkflowName.CORPUS_INGESTION, WorkflowName.STREAK_REMINDER_FANOUT]
)
def test_the_unimplemented_workflows_declare_their_gap_rather_than_pretending(name) -> None:
    """
    سيران لم يُنفَّذا بعد. الاختبار يُثبت أنّ الفجوة **مرئية ومحسوبة** — لا خطّة تبدو
    جاهزة ثمّ تسقط عند أوّل تشغيل (§6.6: الادّعاء أسوأ من الغياب).
    """
    gap = missing_activities(name)
    assert gap
    assert set(gap) <= {step.activity for step in plan_for(name).steps}


def test_every_implemented_activity_is_named_by_some_plan() -> None:
    """نشاطٌ لا تسمّيه خطّة ZOMBIE — كودٌ يُصان ولا يُستدعى."""
    named = {step.activity for name in WorkflowName for step in plan_for(name).steps}
    assert set(ACTIVITIES) <= named


def test_the_execution_timeout_is_derived_from_the_plan() -> None:
    plan = plan_for(WorkflowName.GUARDIAN_WEEKLY_REPORT)
    expected = sum(step.timeout_seconds * step.max_attempts for step in plan.steps)
    assert workflow_execution_timeout(WorkflowName.GUARDIAN_WEEKLY_REPORT) == timedelta(
        seconds=expected
    )


def test_collecting_guardians_on_an_empty_database_returns_nothing(event_loop, db_session) -> None:
    """قائمة فارغة صادقة — لا استثناء ولا صفر مضلِّل."""
    assert _run(event_loop, collect_linked_guardians()) == []


def test_building_reports_for_nobody_builds_nothing(event_loop, db_session) -> None:
    assert _run(event_loop, build_weekly_reports([])) == 0


def test_queueing_notifications_publishes_one_envelope_per_guardian(event_loop) -> None:
    from app.services.messaging.runtime import get_event_publisher, reset_event_publisher
    from shared.messaging import InMemoryEventBus, Topic

    reset_event_publisher()
    publisher = get_event_publisher()
    assert isinstance(publisher, InMemoryEventBus)

    queued = _run(event_loop, queue_guardian_notifications([11, 12]))

    assert queued == 2
    envelopes = publisher.drain(Topic.NOTIFICATIONS_REQUESTED)
    assert [envelope.partition_key for envelope in envelopes] == ["user:11", "user:12"]
    reset_event_publisher()


def test_a_linked_pair_produces_one_report(event_loop, db_session) -> None:
    """
    المسار الحقيقي: رابطٌ نشط ⇒ تقريرٌ مبنيّ. بلا هذا الاختبار يبقى النشاط كوداً
    يعمل «نظرياً» على قاعدة فارغة فقط.
    """
    from app.core.domain.guardian import GuardianLink
    from app.core.domain.user import User

    async def _seed() -> None:
        guardian = User(full_name="Guardian", email="guardian@example.com")
        guardian.set_password("GuardianPass123!")
        student = User(full_name="Student", email="student@example.com")
        student.set_password("StudentPass123!")
        db_session.add(guardian)
        db_session.add(student)
        await db_session.commit()
        await db_session.refresh(guardian)
        await db_session.refresh(student)
        db_session.add(
            GuardianLink(
                guardian_user_id=guardian.id,
                student_user_id=student.id,
                link_code="ABC123",
                status="active",
            )
        )
        await db_session.commit()

    _run(event_loop, _seed())

    guardians = _run(event_loop, collect_linked_guardians())
    assert len(guardians) == 1
    assert _run(event_loop, build_weekly_reports(guardians)) == 1


def test_a_failing_report_does_not_stop_the_others(event_loop, db_session, monkeypatch) -> None:
    """
    عطبٌ في تقرير طالبٍ واحد كان سيحرم كلّ أولياء الأمور من تقريرهم الأسبوعي.
    """
    from app.core.domain.guardian import GuardianLink
    from app.core.domain.user import User
    from app.services.guardian.report import GuardianReportService

    async def _seed() -> list[int]:
        guardian = User(full_name="G", email="g2@example.com")
        guardian.set_password("GuardianPass123!")
        db_session.add(guardian)
        await db_session.commit()
        await db_session.refresh(guardian)
        for index in range(2):
            student = User(full_name=f"S{index}", email=f"s{index}@example.com")
            student.set_password("StudentPass123!")
            db_session.add(student)
            await db_session.commit()
            await db_session.refresh(student)
            db_session.add(
                GuardianLink(
                    guardian_user_id=guardian.id,
                    student_user_id=student.id,
                    link_code=f"CODE{index}",
                    status="active",
                )
            )
        await db_session.commit()
        return [guardian.id]

    guardians = _run(event_loop, _seed())

    original = GuardianReportService.build
    calls = {"count": 0}

    async def flaky(self, student_user_id: int, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("report engine hiccup")
        return await original(self, student_user_id, **kwargs)

    monkeypatch.setattr(GuardianReportService, "build", flaky)

    assert _run(event_loop, build_weekly_reports(guardians)) == 1
    assert calls["count"] == 2
