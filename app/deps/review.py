"""مُزوِّدات الاعتماد لطبقة المراجعة المتباعدة (D-194).

الموجِّه لا يعرف الجلسات ولا الجداول — يطلب **خدمة** فيتلقّاها مُركَّبة. هذا هو نفس
النمط الذي يتبعه `app/deps/auth.py:get_auth_service`، وهو ما تفرضه بوّابة
`ci_guardrails` («طبقة الواجهة/الـAPI لا تستورد وحدة قاعدة البيانات»).
"""

from __future__ import annotations

from fastapi import Depends

from app.core.database import get_db
from app.services.review import ReviewScheduleService

__all__ = ["get_review_schedule_service"]


async def get_review_schedule_service(db=Depends(get_db)) -> ReviewScheduleService:
    """يُركِّب خدمة جدولة المراجعة على جلسة الطلب."""
    return ReviewScheduleService(db)
