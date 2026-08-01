"""خطط سير العمل الدائمة — حتمية ومستقلّة عن المحرّك (D-201).

لماذا الخطّة منفصلة عن Temporal
-------------------------------
منطقٌ يعيش داخل ديكوريتر `@workflow.defn` لا يُختبَر إلّا بخادم Temporal، فيُشحَن بلا
اختبار ويُكتشَف عطبه في الإنتاج. الخطّة هنا **بيانات**: خطوات، وسياسة إعادة، ومهلة —
كلّها قابلة للفحص بلا شبكة. الغلاف في `app/workflows/` يترجمها إلى نداءات المحرّك.

النتيجة العملية: قرارُ «ماذا يجري ومتى يستسلم» مُختبَرٌ بالكامل اليوم، ولو استُبدل
Temporal غداً بقى القرار كما هو.

لماذا سير عمل دائم أصلاً
------------------------
ثلاثة أعمال فقط تستحقّه، ومعيارها واحد: **تعمل لدقائق أو ساعات، ويجب أن تنجو من إعادة
تشغيل، وتحتاج إلغاءً وملاحظةً.** تقرير الوليّ الأسبوعي (تجميعٌ عبر آلاف الطلاب)،
واستيعاب مدوّنة التمارين (تقطيع + تضمين)، وبثّ تذكيرات المواظبة (فان-آوت واسع). ما
عدا ذلك مهمّة خلفية عادية، وتشغيله على محرّك سير عمل تعقيدٌ بلا مقابل.

عقد الموقع: stdlib فقط. لا استيراد من `app/` ولا من خدمة ولا من `temporalio`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final

__all__ = [
    "WORKFLOW_PLANS",
    "WorkflowError",
    "WorkflowName",
    "WorkflowPlan",
    "WorkflowStep",
    "plan_for",
    "total_timeout_seconds",
]


class WorkflowError(ValueError):
    """خرقٌ لعقد سير العمل — خطوة بلا اسم أو مهلة غير صالحة."""


class WorkflowName(StrEnum):
    """سير العمل المُعلَن. الإضافة قرارٌ يُراجَع، لا تفصيلٌ عابر."""

    GUARDIAN_WEEKLY_REPORT = "guardian_weekly_report"
    CORPUS_INGESTION = "corpus_ingestion"
    STREAK_REMINDER_FANOUT = "streak_reminder_fanout"


@dataclass(frozen=True)
class WorkflowStep:
    """خطوة واحدة — نشاطٌ باسمٍ ومهلة وسقف محاولات."""

    activity: str
    timeout_seconds: int
    max_attempts: int = 3
    #: هل يجوز تخطّيها عند الفشل؟ خطوةٌ حرجة تُوقف السير؛ وغيرها تُسجَّل وتمرّ.
    critical: bool = True

    def __post_init__(self) -> None:
        if not self.activity:
            raise WorkflowError("activity name is required")
        if self.timeout_seconds < 1:
            raise WorkflowError("timeout_seconds must be >= 1")
        if self.max_attempts < 1:
            raise WorkflowError("max_attempts must be >= 1")


@dataclass(frozen=True)
class WorkflowPlan:
    """خطّة سير عمل كاملة."""

    name: WorkflowName
    steps: tuple[WorkflowStep, ...]
    #: جدولٌ بصيغة cron، أو `None` لسيرٍ يُطلَق عند الطلب.
    cron_schedule: str | None = None
    description: str = ""
    #: مقصودٌ توثيقُه: سيرٌ لا يُلغى يعني عمليةً لا يمكن إيقافها عند حادثة.
    cancellable: bool = True
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.steps:
            raise WorkflowError("a workflow with no steps is not a workflow")


WORKFLOW_PLANS: Final[dict[WorkflowName, WorkflowPlan]] = {
    WorkflowName.GUARDIAN_WEEKLY_REPORT: WorkflowPlan(
        name=WorkflowName.GUARDIAN_WEEKLY_REPORT,
        # الأحد ٠٦:٠٠ بتوقيت الجزائر = ٠٥:٠٠ UTC. التقويم تقويم الطالب لا UTC (D-195):
        # الحساب على UTC يزيح التقرير يوماً كاملاً لمن يدرس ليلاً.
        cron_schedule="0 5 * * 0",
        description="تجميع أسبوعي حتمي لأولياء الأمور المرتبطين برضا الطالب (D-196).",
        steps=(
            WorkflowStep(activity="collect_linked_guardians", timeout_seconds=60),
            WorkflowStep(activity="build_weekly_reports", timeout_seconds=600),
            # الإشعار غير حرج: تقريرٌ بُني ولم يُبلَّغ يبقى مقروءاً في اللوحة، بينما
            # إيقاف السير كلّه بسبب إشعارٍ فاشل يحرم بقيّة الأولياء من تقاريرهم.
            WorkflowStep(
                activity="queue_guardian_notifications", timeout_seconds=120, critical=False
            ),
        ),
        tags=("guardian", "weekly"),
    ),
    WorkflowName.CORPUS_INGESTION: WorkflowPlan(
        name=WorkflowName.CORPUS_INGESTION,
        cron_schedule=None,
        description="استيعاب مدوّنة التمارين: تحقّق ⇒ تقطيع ⇒ تضمين ⇒ فهرسة.",
        steps=(
            # التحقّق أوّلاً وبمهلة قصيرة: مدوّنة فاسدة تُكتشَف في دقيقة لا بعد ساعة
            # تضمين — ونفس الدرس دفعناه في `ingest_knowledge.py` (الحذف غير المشروط).
            WorkflowStep(activity="validate_corpus", timeout_seconds=120),
            WorkflowStep(activity="chunk_documents", timeout_seconds=900),
            WorkflowStep(activity="embed_chunks", timeout_seconds=3600, max_attempts=5),
            WorkflowStep(activity="index_chunks", timeout_seconds=600),
        ),
        tags=("corpus", "retrieval"),
    ),
    WorkflowName.STREAK_REMINDER_FANOUT: WorkflowPlan(
        name=WorkflowName.STREAK_REMINDER_FANOUT,
        # ١٨:٠٠ بتوقيت الجزائر = ١٧:٠٠ UTC — قبل المساء الدراسي لا بعده.
        cron_schedule="0 17 * * *",
        description="تذكير المواظبة: يُحسَب بتقويم الطالب (Africa/Algiers) لا UTC.",
        steps=(
            WorkflowStep(activity="select_students_at_risk", timeout_seconds=120),
            WorkflowStep(activity="publish_reminder_events", timeout_seconds=300, critical=False),
        ),
        tags=("habit", "notifications"),
    ),
}


def plan_for(name: str | WorkflowName) -> WorkflowPlan:
    """خطّة سير عمل. ترفع `WorkflowError` إن لم يكن مُعلَناً."""
    try:
        return WORKFLOW_PLANS[WorkflowName(str(name))]
    except ValueError as exc:
        known = ", ".join(sorted(item.value for item in WorkflowName))
        raise WorkflowError(f"unknown workflow {name!r}; declared: {known}") from exc


def total_timeout_seconds(plan: WorkflowPlan) -> int:
    """
    أقصى زمنٍ يمكن أن يستغرقه السير — مجموع الخطوات × محاولاتها.

    الرقم يُستعمل كمهلة تنفيذٍ عليا: سيرٌ بلا مهلة عليا يمكن أن يبقى «قيد التشغيل»
    إلى الأبد، فتبدو المنظومة عاملة بينما لا يتقدّم شيء (§0).
    """
    return sum(step.timeout_seconds * step.max_attempts for step in plan.steps)
