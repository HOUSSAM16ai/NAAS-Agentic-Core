"""عامل Temporal — يُترجم الخطط الحتمية إلى سيرٍ دائم (D-201).

**الحالة الصادقة (§6.6):** هذا العامل **DORMANT بلا `TEMPORAL_ADDRESS` وخادمٍ مُشغَّل**.
لم يُثبَت حياً في بيئة هذه الجلسة (لا Docker daemon)، وهذا مُسجَّل في
`.memory/runtime_truth.md` كحدٍّ لا كنجاح. ما **أُثبِت** هو الخطط نفسها
(`shared/workflows`) بتغطية كاملة، والأنشطة أدناه بوصفها دوالّ عادية.

لماذا الغلاف رقيق إلى هذا الحدّ
-------------------------------
كلّ قرار — ما الخطوات، ما مهلها، ما الحرج منها — يعيش في `shared/workflows/plans.py`
بوصفه بيانات. هنا يبقى نداء المحرّك فقط. النتيجة: استبدال Temporal لا يمسّ قراراً
واحداً، واختبار القرارات لا يحتاج خادماً.

التشغيل: `python -m app.workflows.temporal_worker`
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from shared.workflows import WorkflowName, plan_for, total_timeout_seconds

logger = logging.getLogger("cogniforge.workflows")


async def collect_linked_guardians() -> list[int]:
    """أولياء الأمور المرتبطين **برضا الطالب** حصراً (D-196)."""
    from app.core.database import async_session_factory
    from app.services.guardian.linking import GuardianLinkService

    async with async_session_factory() as db:
        return await GuardianLinkService(db).linked_guardian_ids()


async def build_weekly_reports(guardian_ids: list[int]) -> int:
    """
    يبني تقرير كل وليّ. **لا يستعلم عن `content` إطلاقاً** — حمايةٌ بنيوية لا مُرشِّح:
    مقتطفٌ واحد يجعل لوحة الوليّ باباً خلفياً إلى الحلّ الممنوع (D-113/D-196).
    """
    from app.core.database import async_session_factory
    from app.services.guardian.linking import GuardianLinkService
    from app.services.guardian.report import GuardianReportService

    built = 0
    async with async_session_factory() as db:
        links = GuardianLinkService(db)
        reports = GuardianReportService(db)
        for guardian_id in guardian_ids:
            for student in await links.linked_students(guardian_id):
                try:
                    await reports.build(student.student_user_id)
                    built += 1
                except Exception:
                    # طالبٌ واحد فاشل لا يُسقِط تقارير البقيّة — وإلّا حرم عطبٌ واحد
                    # كلّ أولياء الأمور من تقريرهم الأسبوعي.
                    logger.warning(
                        "guardian_report_failed student_id=%s",
                        student.student_user_id,
                        exc_info=True,
                    )
    return built


async def queue_guardian_notifications(guardian_ids: list[int]) -> int:
    """يضع طلبات إشعار على الناقل. غير حرجة — التقرير مقروءٌ في اللوحة بلا إشعار."""
    from app.services.messaging.runtime import build_envelope, publish_event
    from shared.messaging import Topic

    queued = 0
    for guardian_id in guardian_ids:
        published = await publish_event(
            build_envelope(
                topic=Topic.NOTIFICATIONS_REQUESTED,
                event_name="guardian_weekly_report_ready",
                payload={"user_id": guardian_id},
                partition_key=f"user:{guardian_id}",
            )
        )
        queued += int(published)
    return queued


#: الأنشطة المُعلَنة. الاسم هو العقد بين الخطّة والتنفيذ — خطوةٌ تسمّي نشاطاً غير
#: موجود يجب أن تفشل عند الإقلاع لا عند التشغيل الأسبوعي بعد ستّة أيام.
ACTIVITIES: dict[str, Any] = {
    "collect_linked_guardians": collect_linked_guardians,
    "build_weekly_reports": build_weekly_reports,
    "queue_guardian_notifications": queue_guardian_notifications,
}


def missing_activities(name: WorkflowName) -> tuple[str, ...]:
    """
    الأنشطة التي تسمّيها الخطّة ولا تُنفَّذ.

    تُستدعى عند الإقلاع: سيرٌ يسمّي نشاطاً غائباً يفشل بعد ستّة أيام من الانتظار،
    وهو أسوأ وقتٍ ممكن لاكتشاف خطأٍ مطبعي.
    """
    return tuple(step.activity for step in plan_for(name).steps if step.activity not in ACTIVITIES)


def workflow_execution_timeout(name: WorkflowName) -> timedelta:
    """المهلة العليا المشتقّة من الخطّة — لا رقمٌ مُصلَّب هنا."""
    return timedelta(seconds=total_timeout_seconds(plan_for(name)))


async def run_worker() -> None:  # pragma: no cover - يتطلّب خادم Temporal حيّاً
    """
    يُشغِّل العامل. يرفع بوضوح إن غاب العنوان أو المكتبة — لا عاملٌ يبدو حيّاً ولا يعمل.
    """
    from app.core.config import get_settings

    settings = get_settings()
    address = getattr(settings, "TEMPORAL_ADDRESS", None)
    if not address:
        raise RuntimeError("TEMPORAL_ADDRESS is not set — the worker has nothing to connect to")

    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ImportError as exc:
        raise RuntimeError("temporalio is not installed — install it to run the worker") from exc

    client = await Client.connect(
        address, namespace=getattr(settings, "TEMPORAL_NAMESPACE", "default")
    )
    worker = Worker(
        client,
        task_queue=getattr(settings, "TEMPORAL_TASK_QUEUE", "cogniforge"),
        activities=list(ACTIVITIES.values()),
    )
    logger.info("temporal_worker_started address=%s", address)
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())


__all__ = [
    "ACTIVITIES",
    "build_weekly_reports",
    "collect_linked_guardians",
    "missing_activities",
    "queue_guardian_notifications",
    "run_worker",
    "workflow_execution_timeout",
]
