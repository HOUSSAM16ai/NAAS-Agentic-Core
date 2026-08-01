"""مُزوِّدات الاعتماد لطبقة وليّ الأمر (D-196)."""

from __future__ import annotations

from fastapi import Depends

from app.core.database import get_db
from app.services.guardian import GuardianLinkService, GuardianReportService

__all__ = ["get_guardian_link_service", "get_guardian_report_service"]


async def get_guardian_link_service(db=Depends(get_db)) -> GuardianLinkService:
    """يُركِّب خدمة الربط على جلسة الطلب."""
    return GuardianLinkService(db)


async def get_guardian_report_service(db=Depends(get_db)) -> GuardianReportService:
    """يُركِّب خدمة التقرير على جلسة الطلب."""
    return GuardianReportService(db)
