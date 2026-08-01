"""
موجّه المراجعة المتباعدة (D-194).

  • `GET /api/v1/review/due` — طابور المراجعة المستحقّ للطالب الحالي.

يُجيب على السؤال الذي لم تكن المنصّة تملك له جواباً: **«ماذا أراجع اليوم؟»**

> الموجِّه رقيق عمداً (`check_router_domain_logic`): كلّ المنطق في
> `app/services/review/` والمحرّك في `shared/scheduling/fsrs.py`. لا حساب هنا.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.deps.auth import CurrentUser, get_current_user
from app.deps.review import get_review_schedule_service
from app.services.review import ReviewScheduleService
from app.services.review.persistence import DEFAULT_STREAM
from shared.curriculum import CANONICAL_STREAMS

router = APIRouter(prefix="/api/v1/review", tags=["Spaced Repetition"])


class DueReviewItem(RobustBaseModel):
    """عنصرٌ واحد في طابور اليوم."""

    concept_id: str
    title: str
    due_at: datetime
    overdue_days: float = Field(..., description="كم يوماً مضى على الاستحقاق")
    stability: float = Field(..., description="الاستقرار باليوم")
    difficulty: float = Field(..., ge=1.0, le=10.0)
    lapses: int = Field(..., ge=0)
    exam_weight: float = Field(..., description="معامل المادة × تواتر الظهور في البكالوريا")


class DueReviewResponse(RobustBaseModel):
    total: int
    stream: str
    generated_at: datetime
    items: list[DueReviewItem]


@router.get("/due", response_model=DueReviewResponse, summary="Today's review queue")
async def due_reviews(
    stream: str = Query(DEFAULT_STREAM, description="شعبة البكالوريا — تحدّد ترتيب الأولوية"),
    limit: int = Query(20, ge=1, le=100),
    current: CurrentUser = Depends(get_current_user),
    service: ReviewScheduleService = Depends(get_review_schedule_service),
) -> DueReviewResponse:
    """يُرجِع المفاهيم المستحقّة للمراجعة، مرتّبة بوزن الامتحان ثمّ بالتأخّر."""
    selected = stream if stream in CANONICAL_STREAMS else DEFAULT_STREAM
    now = datetime.now(tz=None).astimezone()
    items = await service.due_reviews(current.user.id, now=now, stream=selected, limit=limit)
    return DueReviewResponse(
        total=len(items),
        stream=selected,
        generated_at=now,
        items=[
            DueReviewItem(
                concept_id=item.concept_id,
                title=item.title,
                due_at=item.due_at,
                overdue_days=round(item.overdue_days, 3),
                stability=round(item.stability, 4),
                difficulty=round(item.difficulty, 4),
                lapses=item.lapses,
                exam_weight=round(item.exam_weight, 4),
            )
            for item in items
        ],
    )
