"""
موجّه القسائم المدفوعة مسبقاً (D-198).

  • `POST /api/v1/vouchers/redeem`      — استبدال قسيمة (idempotent للفاعل نفسه).
  • `GET  /api/v1/vouchers/entitlement` — حالة اشتراك المستخدم الحالي.
  • `POST /api/v1/vouchers/issue`       — إصدار قسيمة (**إدارة**).

**لا بوّابة دفع هنا عمداً.** شريحة كبيرة من أولياء الأمور في الجزائر لا تملك بطاقةً
تعمل على الإنترنت، وSATIM يتطلّب تعاقداً وامتثالاً لا يُنجَزان في مستودع. القسيمة تُباع
في مكتبةٍ أو عبر تحويل وتُستبدَل في ثانية — فتُفتَح المنصّة تجارياً بلا انتظار طرفٍ ثالث.
SATIM مقعدٌ موثّق بلا كود (`docs/architecture/EXTENSION_SEAMS.md`).

> الموجِّه رقيق: المنطق في `app/services/billing/` والرمز في `shared/voucher/`.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.deps.auth import CurrentUser, get_current_user, require_roles
from app.deps.billing import get_voucher_service
from app.services.billing import VoucherRedemptionError, VoucherService
from app.services.rbac import ADMIN_ROLE

router = APIRouter(prefix="/api/v1/vouchers", tags=["Vouchers"])


class RedeemRequest(RobustBaseModel):
    code: str = Field(..., min_length=8, max_length=48)


class RedeemResponse(RobustBaseModel):
    plan: str
    expires_at: datetime
    already_redeemed_by_you: bool = Field(
        False, description="إعادة إرسالٍ لنفس الفاعل — لا تمديد مزدوج"
    )


class EntitlementResponse(RobustBaseModel):
    active: bool
    plan: str | None = None
    expires_at: datetime | None = None


class IssueRequest(RobustBaseModel):
    plan: str = Field("standard", max_length=32)
    duration_days: int = Field(30, ge=1, le=730)
    quantity: int = Field(1, ge=1, le=500)


class IssueResponse(RobustBaseModel):
    codes: list[str] = Field(..., description="تُعرَض مرّة واحدة — تُخزَّن مُجزَّأة")


@router.post("/redeem", response_model=RedeemResponse, summary="Redeem a prepaid voucher")
async def redeem_voucher(
    payload: RedeemRequest,
    current: CurrentUser = Depends(get_current_user),
    service: VoucherService = Depends(get_voucher_service),
) -> RedeemResponse:
    """يستبدل قسيمة ويمنح الاشتراك. إعادة الإرسال لا تمنح شهرين."""
    try:
        outcome = await service.redeem(user_id=current.user.id, raw_code=payload.code)
    except VoucherRedemptionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedeemResponse(
        plan=outcome.plan,
        expires_at=outcome.expires_at,
        already_redeemed_by_you=outcome.already_redeemed_by_you,
    )


@router.get("/entitlement", response_model=EntitlementResponse, summary="Subscription status")
async def entitlement(
    current: CurrentUser = Depends(get_current_user),
    service: VoucherService = Depends(get_voucher_service),
) -> EntitlementResponse:
    """حالة اشتراك المستخدم الحالي."""
    found = await service.entitlement_status(current.user.id)
    return EntitlementResponse(active=found.active, plan=found.plan, expires_at=found.expires_at)


@router.post(
    "/issue",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue vouchers (admin)",
)
async def issue_vouchers(
    payload: IssueRequest,
    _: CurrentUser = Depends(require_roles(ADMIN_ROLE)),
    service: VoucherService = Depends(get_voucher_service),
) -> IssueResponse:
    """يُصدِر قسائم. الرموز تُعرَض **مرّة واحدة** — لا تُخزَّن إلّا مُجزَّأة."""
    codes = [
        await service.issue(plan=payload.plan, duration_days=payload.duration_days)
        for _ in range(payload.quantity)
    ]
    return IssueResponse(codes=codes)
