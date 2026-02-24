from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.content_service import ContentService

router = APIRouter(prefix="/v1/content", tags=["content"])


class ContentItemResponse(BaseModel):
    id: str
    type: str
    title: str | None = None
    level: str | None = None
    subject: str | None = None
    year: int | None = None
    lang: str | None = None


class ContentSearchResponse(BaseModel):
    items: list[ContentItemResponse]


def get_content_service(db: AsyncSession = Depends(get_db)) -> ContentService:
    return ContentService(db)


@router.get("/search", response_model=ContentSearchResponse)
async def search_content(
    q: str | None = Query(None, description="Search query"),
    level: str | None = None,
    subject: str | None = None,
    service: ContentService = Depends(get_content_service),
):
    """
    Search content items.
    """
    rows = await service.search_content(q, level, subject)
    items = []
    for row in rows:
        items.append(
            ContentItemResponse(
                id=row["id"],
                type=row["type"],
                title=row["title"],
                level=row["level"],
                subject=row["subject"],
                year=row["year"],
                lang=row["lang"],
            )
        )

    return ContentSearchResponse(items=items)


@router.get("/{id}")
async def get_content(id: str, service: ContentService = Depends(get_content_service)):
    """
    Get content metadata and raw content.
    """
    return await service.get_content(id)


@router.get("/{id}/raw")
async def get_content_raw(id: str, service: ContentService = Depends(get_content_service)):
    """
    Get raw markdown content.
    """
    content = await service.get_content_raw(id)
    return {"content": content}


@router.get("/{id}/solution")
async def get_content_solution(id: str, service: ContentService = Depends(get_content_service)):
    """
    Get official solution.
    """
    return await service.get_content_solution(id)
