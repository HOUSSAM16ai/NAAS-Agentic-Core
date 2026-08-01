"""اختبارات خطط سير العمل — D-201.

الخطّة **بيانات**، فتُختبَر بلا خادم Temporal. منطقٌ يعيش داخل ديكوريتر المحرّك لا
يُختبَر إلّا بخادم، فيُشحَن بلا اختبار ويُكتشَف عطبه في الإنتاج.
"""

from __future__ import annotations

import pytest

from shared.workflows import (
    WORKFLOW_PLANS,
    WorkflowError,
    WorkflowName,
    WorkflowPlan,
    WorkflowStep,
    plan_for,
    total_timeout_seconds,
)


def test_every_declared_workflow_has_a_plan() -> None:
    assert set(WORKFLOW_PLANS) == set(WorkflowName)


def test_an_unknown_workflow_raises_rather_than_returning_empty() -> None:
    """خطّة فارغة تُشغَّل بصمتٍ ولا تفعل شيئاً — والصفر المضلِّل ممنوع (§0)."""
    with pytest.raises(WorkflowError, match="unknown workflow"):
        plan_for("nightly_magic")


def test_a_known_workflow_is_resolved_by_string_or_enum() -> None:
    assert plan_for("corpus_ingestion") is plan_for(WorkflowName.CORPUS_INGESTION)


def test_a_workflow_without_steps_is_rejected() -> None:
    with pytest.raises(WorkflowError, match="no steps"):
        WorkflowPlan(name=WorkflowName.CORPUS_INGESTION, steps=())


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"activity": "", "timeout_seconds": 10}, "activity"),
        ({"activity": "a", "timeout_seconds": 0}, "timeout_seconds"),
        ({"activity": "a", "timeout_seconds": 10, "max_attempts": 0}, "max_attempts"),
    ],
)
def test_an_incoherent_step_is_rejected(kwargs, message) -> None:
    with pytest.raises(WorkflowError, match=message):
        WorkflowStep(**kwargs)


def test_every_workflow_is_cancellable() -> None:
    """سيرٌ لا يُلغى يعني عمليةً لا يمكن إيقافها عند حادثة."""
    assert all(plan.cancellable for plan in WORKFLOW_PLANS.values())


def test_every_workflow_describes_itself() -> None:
    assert all(plan.description for plan in WORKFLOW_PLANS.values())


def test_the_scheduled_workflows_run_in_the_students_evening_not_utcs() -> None:
    """
    ١٧:٠٠ UTC = ١٨:٠٠ بالجزائر — قبل المساء الدراسي. التذكير على توقيت UTC يصل
    منتصف النهار الدراسي، وهو نفس صنف عطب المواظبة الذي عالجه D-195.
    """
    assert plan_for(WorkflowName.STREAK_REMINDER_FANOUT).cron_schedule == "0 17 * * *"
    assert plan_for(WorkflowName.GUARDIAN_WEEKLY_REPORT).cron_schedule == "0 5 * * 0"


def test_corpus_ingestion_is_on_demand_not_scheduled() -> None:
    assert plan_for(WorkflowName.CORPUS_INGESTION).cron_schedule is None


def test_validation_comes_before_the_expensive_work() -> None:
    """
    مدوّنة فاسدة تُكتشَف في دقيقة لا بعد ساعة تضمين — درسٌ دفعناه في `ingest_knowledge`.
    """
    steps = plan_for(WorkflowName.CORPUS_INGESTION).steps
    assert steps[0].activity == "validate_corpus"
    assert steps[0].timeout_seconds < steps[2].timeout_seconds


def test_notification_steps_are_not_critical() -> None:
    """
    تقريرٌ بُني ولم يُبلَّغ يبقى مقروءاً؛ وإيقاف السير لأجل إشعارٍ فاشل يحرم البقيّة.
    """
    steps = plan_for(WorkflowName.GUARDIAN_WEEKLY_REPORT).steps
    assert steps[-1].activity == "queue_guardian_notifications"
    assert steps[-1].critical is False


def test_the_total_timeout_accounts_for_retries() -> None:
    """
    مهلةٌ عليا تتجاهل إعادة المحاولة تقتل سيراً كان سينجح في محاولته الثالثة.
    """
    plan = WorkflowPlan(
        name=WorkflowName.CORPUS_INGESTION,
        steps=(WorkflowStep(activity="a", timeout_seconds=10, max_attempts=3),),
    )
    assert total_timeout_seconds(plan) == 30


def test_every_real_plan_has_a_bounded_ceiling() -> None:
    """سيرٌ بلا مهلة عليا يبقى «قيد التشغيل» إلى الأبد فتبدو المنظومة عاملة."""
    assert all(total_timeout_seconds(plan) > 0 for plan in WORKFLOW_PLANS.values())
