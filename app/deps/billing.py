"""مُزوِّدات الاعتماد للقسائم وحقوق الوصول (D-198)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.core.database import get_db
from app.deps.auth import CurrentUser, get_current_user
from app.services.billing import VoucherService

__all__ = ["get_voucher_service", "require_active_entitlement"]


async def get_voucher_service(db=Depends(get_db)) -> VoucherService:
    """يُركِّب خدمة القسائم على جلسة الطلب."""
    return VoucherService(db)


async def require_active_entitlement(
    current: CurrentUser = Depends(get_current_user),
    service: VoucherService = Depends(get_voucher_service),
) -> CurrentUser:
    """
    بوّابة الاشتراك — **اعتمادٌ واحد**، لا فحصٌ مبعثر في المعالِجات.

    فحصُ الاشتراك المنسوخ في كلّ معالِج ينسى موضعاً حتماً، والموضع المنسيّ يصير ميزةً
    مجانية لا يعرف بها أحد. تعريفٌ واحد يُطبَّق بالتصريح.
    """
    status_now = await service.entitlement_status(current.user.id)
    if not status_now.active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="An active subscription is required",
        )
    return current
