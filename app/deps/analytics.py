"""مُزوِّد الاعتماد لتحليلات المنتج (D-197)."""

from __future__ import annotations

from fastapi import Depends

from app.core.database import get_db
from app.services.analytics.product_events import ProductAnalyticsService

__all__ = ["get_product_analytics_service"]


async def get_product_analytics_service(db=Depends(get_db)) -> ProductAnalyticsService:
    """يُركِّب خدمة التحليلات على جلسة الطلب."""
    return ProductAnalyticsService(db)
