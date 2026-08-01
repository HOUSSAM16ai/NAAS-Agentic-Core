"""
موجّه وليّ الأمر (D-196).

  • `POST /api/v1/guardian/link-code`            — الطالب يُولِّد رمز ربط.
  • `POST /api/v1/guardian/link`                 — الوليّ يستبدل الرمز.
  • `GET  /api/v1/guardian/students`             — الطلاب المرتبطون بالوليّ.
  • `GET  /api/v1/guardian/students/{id}/weekly` — التقرير الأسبوعي.
  • `DELETE /api/v1/guardian/students/{id}`      — فكّ الرابط (أيّ طرف).

**قاعدة التفويض:** كلّ قراءة تخصّ طالباً تمرّ من `is_linked`. مُعرَّف الطالب في المسار
ليس تفويضاً — بدون هذا الفحص يصير تعدادُ الأرقام كافياً لقراءة تقدّم أيّ طفل.

> الموجِّه رقيق (`check_router_domain_logic`): المنطق في `app/services/guardian/`.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.deps.auth import CurrentUser, get_current_user
from app.deps.guardian import get_guardian_link_service, get_guardian_report_service
from app.services.analytics.product_events import record_product_event
from app.services.guardian import GuardianLinkService, GuardianReportService
from app.services.guardian.linking import GuardianLinkError
from shared.analytics import EventName

router = APIRouter(prefix="/api/v1/guardian", tags=["Guardian"])


class LinkCodeResponse(RobustBaseModel):
    link_code: str = Field(..., description="يسلّمه الطالب لوليّه — صالح للاستبدال مرّة واحدة")


class LinkRequest(RobustBaseModel):
    link_code: str = Field(..., min_length=4, max_length=32)


class LinkedStudentItem(RobustBaseModel):
    student_user_id: int
    linked_since: datetime


class ConceptProgressItem(RobustBaseModel):
    concept_id: str
    title: str
    subject: str
    interactions: int
    assisted_mastery: float
    durable_mastery: float
    illusion_gap: float
    improved: bool
    fragile: bool


class WeeklyReportResponse(RobustBaseModel):
    """
    تقريرٌ بالمقادير والمفاهيم فقط.

    لا يحمل هذا العقد أيّ حقلٍ نصّي حرّ من المحادثة — والحماية بنيوية: خدمةُ التقرير
    لا تستعلم عن عمود `content` إطلاقاً (D-113: الوليّ ليس باباً خلفياً إلى الحلّ).
    """

    student_user_id: int
    period_start: datetime
    period_end: datetime
    active_days: int
    current_streak: int
    longest_streak: int
    sessions: int
    concepts_practised: int
    reviews_completed: int
    reviews_due_now: int
    strongest: list[ConceptProgressItem]
    needs_attention: list[ConceptProgressItem]


@router.post("/link-code", response_model=LinkCodeResponse, summary="Issue a guardian link code")
async def issue_link_code(
    current: CurrentUser = Depends(get_current_user),
    service: GuardianLinkService = Depends(get_guardian_link_service),
) -> LinkCodeResponse:
    """الطالب يُولِّد رمزاً يسلّمه لوليّه. الربط يبدأ من الطالب دائماً."""
    code = await service.issue_code(current.user.id)
    # D-197: خطوة القُمع الحاسمة تجارياً — كم طالباً يدعو وليّه فعلاً؟
    await record_product_event(event_name=EventName.GUARDIAN_LINK_ISSUED, user_id=current.user.id)
    return LinkCodeResponse(link_code=code)


@router.post("/link", response_model=LinkedStudentItem, summary="Redeem a guardian link code")
async def redeem_link_code(
    payload: LinkRequest,
    current: CurrentUser = Depends(get_current_user),
    service: GuardianLinkService = Depends(get_guardian_link_service),
) -> LinkedStudentItem:
    """الوليّ يستبدل الرمز فيصير الرابط فعّالاً."""
    try:
        linked = await service.redeem_code(current.user.id, payload.link_code)
    except GuardianLinkError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    await record_product_event(event_name=EventName.GUARDIAN_LINK_ACCEPTED, user_id=current.user.id)
    return LinkedStudentItem(
        student_user_id=linked.student_user_id, linked_since=linked.linked_since
    )


@router.get("/students", response_model=list[LinkedStudentItem], summary="Linked students")
async def linked_students(
    current: CurrentUser = Depends(get_current_user),
    service: GuardianLinkService = Depends(get_guardian_link_service),
) -> list[LinkedStudentItem]:
    return [
        LinkedStudentItem(student_user_id=item.student_user_id, linked_since=item.linked_since)
        for item in await service.linked_students(current.user.id)
    ]


@router.get(
    "/students/{student_user_id}/weekly",
    response_model=WeeklyReportResponse,
    summary="Weekly progress report",
)
async def weekly_report(
    student_user_id: int,
    current: CurrentUser = Depends(get_current_user),
    links: GuardianLinkService = Depends(get_guardian_link_service),
    reports: GuardianReportService = Depends(get_guardian_report_service),
) -> WeeklyReportResponse:
    """تقرير الأسبوع لطالبٍ مرتبط. غير المرتبط ⇒ 404 لا 403 (لا نؤكّد وجود الحساب)."""
    if not await links.is_linked(current.user.id, student_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked student")

    report = await reports.build(student_user_id)
    await record_product_event(event_name=EventName.GUARDIAN_REPORT_VIEWED, user_id=current.user.id)
    return WeeklyReportResponse(
        student_user_id=report.student_user_id,
        period_start=report.period_start,
        period_end=report.period_end,
        active_days=report.active_days,
        current_streak=report.current_streak,
        longest_streak=report.longest_streak,
        sessions=report.sessions,
        concepts_practised=report.concepts_practised,
        reviews_completed=report.reviews_completed,
        reviews_due_now=report.reviews_due_now,
        strongest=[ConceptProgressItem(**vars(item)) for item in report.strongest],
        needs_attention=[ConceptProgressItem(**vars(item)) for item in report.needs_attention],
    )


@router.delete(
    "/students/{student_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke a guardian link",
)
async def revoke_link(
    student_user_id: int,
    current: CurrentUser = Depends(get_current_user),
    service: GuardianLinkService = Depends(get_guardian_link_service),
) -> Response:
    """يفكّ الرابط. الصفّ يبقى مُعلَّماً `revoked` — أثر من رأى بيانات مَن محفوظ."""
    if not await service.revoke(student_user_id=student_user_id, guardian_user_id=current.user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked student")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
