"""
موجّه تحليلات المنتج (D-197) — **للإدارة حصراً**.

  • `GET /api/v1/analytics/retention` — احتفاظ الأفواج D1/D7/D30.
  • `GET /api/v1/analytics/funnel`    — قُمع التحويل التجاري.

هذا هو الجزء الوحيد من المنصّة الذي يقيس **هل نجح ما بنيناه**. بدونه تبقى كلّ ميزةٍ
جديدة رأياً.

**فوجٌ غير ناضج يُرجِع `null` لا صفراً**: من سجّل أمس لا يُقاس احتفاظ اليوم السابع لديه،
وصفرٌ هنا يقرأ «فقدناهم» بينما الحقيقة «لم يحن الوقت» (§0: المجهول أفضل من يقين زائف).

> الموجِّه رقيق: كلّ الحساب في `shared/analytics/` والاستعلام في `app/services/analytics/`.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.deps.analytics import get_product_analytics_service
from app.deps.auth import CurrentUser, require_roles
from app.services.analytics.product_events import ProductAnalyticsService
from app.services.rbac import ADMIN_ROLE

router = APIRouter(prefix="/api/v1/analytics", tags=["Product Analytics"])


class CohortItem(RobustBaseModel):
    cohort_date: date
    size: int
    retained: dict[int, float | None] = Field(
        ..., description="الأفق باليوم → النسبة، أو null إن لم ينضج الفوج"
    )


class RetentionResponse(RobustBaseModel):
    generated_for: date
    horizons: list[int]
    overall: dict[int, float | None]
    cohorts: list[CohortItem]


class FunnelStepItem(RobustBaseModel):
    event_name: str
    users: int
    conversion_from_start: float
    conversion_from_previous: float


@router.get("/retention", response_model=RetentionResponse, summary="Cohort retention")
async def retention(
    window_days: int = Query(90, ge=1, le=365),
    _: CurrentUser = Depends(require_roles(ADMIN_ROLE)),
    service: ProductAnalyticsService = Depends(get_product_analytics_service),
) -> RetentionResponse:
    """احتفاظ الأفواج — الفوج يوم التسجيل بتقويم الطالب المحلّي (D-195)."""
    report = await service.retention(window_days=window_days)
    return RetentionResponse(
        generated_for=report.generated_for,
        horizons=list(report.horizons),
        overall=dict(report.overall),
        cohorts=[
            CohortItem(cohort_date=item.cohort_date, size=item.size, retained=dict(item.retained))
            for item in report.cohorts
        ],
    )


@router.get("/funnel", response_model=list[FunnelStepItem], summary="Conversion funnel")
async def conversion_funnel(
    window_days: int = Query(90, ge=1, le=365),
    _: CurrentUser = Depends(require_roles(ADMIN_ROLE)),
    service: ProductAnalyticsService = Depends(get_product_analytics_service),
) -> list[FunnelStepItem]:
    """تسجيل ⇒ دور ⇒ مراجعة ⇒ دعوة الوليّ ⇒ قبول الوليّ."""
    return [
        FunnelStepItem(
            event_name=step.event_name,
            users=step.users,
            conversion_from_start=round(step.conversion_from_start, 4),
            conversion_from_previous=round(step.conversion_from_previous, 4),
        )
        for step in await service.conversion_funnel(window_days=window_days)
    ]
