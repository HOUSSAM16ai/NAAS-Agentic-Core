"""
موجه منصّة الـ Skills — رصد + تركيب (Observability + Composition).

CLAUDE.md §0.5 + §6.21 (عقد المقياس-المُصدِر): كل ما يُعرَض هنا له مُصدِر حقيقي.
  • `GET  /api/v1/skills`          — قائمة الـ Skills + عقودها + consumed_by (رصد، عام).
  • `GET  /api/v1/skills/{name}`   — تفاصيل Skill واحد.
  • `POST /api/v1/skills/refine`   — خط تنقية الإجابة المُركَّب (auth).
  • `POST /api/v1/skills/retrieve` — RetrievalRerankSkill (auth، خلف علم — 503 عند التعطيل).
  • `POST /api/v1/skills/mcp`      — MCPToolSkill (auth، خلف علم — 503 عند التعطيل).

> الموجِّه قراءة-أولاً وإضافي بالكامل — لا يلمس المسار الحيّ للدردشة.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.core.schemas import RobustBaseModel
from app.deps.auth import CurrentUser, get_current_user
from app.services.skills.registry import compose_text_refinement, get_skill_registry

router = APIRouter(prefix="/api/v1/skills", tags=["Skills Platform"])


class SkillsListResponse(RobustBaseModel):
    total: int
    active: int
    flagged: int
    skills: list[dict[str, Any]]


class RefineRequest(RobustBaseModel):
    text: str
    question: str = ""
    intent: str = "educational"


class RefineResponse(RobustBaseModel):
    text: str
    applied_steps: list[str]
    failed_steps: list[str]


class RetrieveRequest(RobustBaseModel):
    query: str
    top_k: int = 8
    top_n: int = 5
    documents: list[str] | None = None
    filters: dict[str, Any] | None = None


class MCPRequest(RobustBaseModel):
    action: str = "list"
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None


@router.get("", response_model=SkillsListResponse, summary="List registered skills")
async def list_skills() -> SkillsListResponse:
    """يُعيد كل الـ Skills المُسجَّلة مع عقودها وحالتها (للرصد)."""
    reg = get_skill_registry()
    skills = reg.list()
    return SkillsListResponse(
        total=len(skills),
        active=len(reg.by_status("ACTIVE")),
        flagged=len(reg.by_status("FLAGGED")),
        skills=[d.as_dict() for d in skills],
    )


@router.get("/{name}", summary="Skill detail")
async def get_skill(name: str) -> dict[str, Any]:
    """تفاصيل Skill واحد، أو 404 إن لم يوجد."""
    descriptor = get_skill_registry().get(name)
    if descriptor is None:
        raise HTTPException(status_code=404, detail=f"Skill not found: {name}")
    return descriptor.as_dict()


@router.post("/refine", response_model=RefineResponse, summary="Run answer-refinement pipeline")
async def refine_endpoint(
    payload: RefineRequest,
    _: CurrentUser = Depends(get_current_user),
) -> RefineResponse:
    """يُشغِّل خط التنقية المُركَّب (exercise_alignment → answer_quality → firewall → topic_lock)."""
    result = compose_text_refinement(
        payload.text,
        {"question": payload.question, "intent": payload.intent},
    )
    return RefineResponse(
        text=result.text,
        applied_steps=list(result.applied_steps),
        failed_steps=list(result.failed_steps),
    )


@router.post("/retrieve", summary="Semantic retrieval + rerank (flagged)")
async def retrieve_endpoint(
    payload: RetrieveRequest,
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """RetrievalRerankSkill — يتطلّب ENABLE_RETRIEVAL_RERANK_SKILL=true (وإلا 503)."""
    from app.services.skills.retrieval_rerank_skill import (
        RetrievalRerankInput,
        get_retrieval_rerank_skill,
    )

    out = await get_retrieval_rerank_skill().retrieve(
        RetrievalRerankInput(
            query=payload.query,
            top_k=payload.top_k,
            top_n=payload.top_n,
            documents=payload.documents,
            filters=payload.filters,
        )
    )
    if out is None:
        raise HTTPException(
            status_code=503,
            detail="RetrievalRerankSkill disabled (set ENABLE_RETRIEVAL_RERANK_SKILL=true).",
        )
    return out.model_dump()


@router.post("/mcp", summary="MCP tool bridge (flagged)")
async def mcp_endpoint(
    payload: MCPRequest,
    _: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """MCPToolSkill — يتطلّب ENABLE_MCP_TOOL_SKILL=true (وإلا 503)."""
    from app.services.skills.mcp_tool_skill import MCPToolInput, get_mcp_tool_skill

    action = payload.action if payload.action in ("list", "call") else "list"
    out = await get_mcp_tool_skill().call(
        MCPToolInput(
            action=action,  # type: ignore[arg-type]
            tool_name=payload.tool_name,
            arguments=payload.arguments,
        )
    )
    if out is None:
        raise HTTPException(
            status_code=503,
            detail="MCPToolSkill disabled (set ENABLE_MCP_TOOL_SKILL=true).",
        )
    return out.model_dump()
