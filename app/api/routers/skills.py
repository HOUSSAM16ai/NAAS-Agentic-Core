"""
موجه منصّة الـ Skills — رصد + تركيب (Observability + Composition).

CLAUDE.md §0.5 + §6.21 (عقد المقياس-المُصدِر): كل ما يُعرَض هنا له مُصدِر حقيقي.
  • `GET  /api/v1/skills`          — قائمة الـ Skills + عقودها + consumed_by (رصد، عام).
  • `GET  /api/v1/skills/{name}`   — تفاصيل Skill واحد.
  • `POST /api/v1/skills/refine`   — خط تنقية الإجابة المُركَّب (auth).
  • `POST /api/v1/skills/reason`   — النواة المعرفية للتفكير المُركَّبة (auth — D-181).
  • `POST /api/v1/skills/retrieve` — RetrievalRerankSkill (auth، خلف علم — 503 عند التعطيل).
  • `POST /api/v1/skills/mcp`      — MCPToolSkill (auth، خلف علم — 503 عند التعطيل).

> الموجِّه قراءة-أولاً وإضافي بالكامل — لا يلمس المسار الحيّ للدردشة.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from app.core.schemas import RobustBaseModel
from app.deps.auth import CurrentUser, get_current_user

# عقد فجوة الوهم يُستورَد ولا يُكرَّر (D-212). حزمة `app.services.skills` تُحمَّل أصلاً
# عبر `registry` أدناه، فالاستيراد هنا لا يضيف كلفةً — ونسخةٌ ثانية من العقد كانت ستنحرف.
from app.services.skills.illusion_gap_skill import IllusionGapInput, IllusionGapReport
from app.services.skills.registry import (
    compose_reasoning,
    compose_text_refinement,
    get_skill_registry,
)

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


class ReasonRequest(RobustBaseModel):
    """طلب النواة المعرفية للتفكير (D-181) — سؤال حرّ + مدخلات مُهيكَلة اختيارية."""

    question: str = ""
    premises: list[str] | None = None
    conclusion: str | None = None
    edges: list[list[str]] | None = None
    classify_pair: list[str] | None = None
    counterfactual_node: str | None = None
    instances: list[dict[str, Any]] | None = None
    sequence: list[float] | None = None
    source: dict[str, Any] | None = None
    target: dict[str, Any] | None = None
    relations: list[list[str]] | None = None
    dynamics: list[list[str]] | None = None
    concept_name: str | None = None
    # D-183: طلب حساب حتمي اختياري يُوجَّه إلى FoundationsComputeSkill عبر compose_reasoning.
    compute: dict[str, Any] | None = None


class ReasonResponse(RobustBaseModel):
    """أثر تفكير مُركَّب — الأنماط المُفعَّلة + نتائج المهارات + سرد حتمي."""

    question: str
    modes: list[str]
    results: dict[str, Any]
    narrative: str


class ComputeRequest(RobustBaseModel):
    """طلب النواة الحاسوبية للأسس (D-183) — مجال + عملية + وسائط مُهيكَلة."""

    domain: str
    operation: str
    args: dict[str, Any] = Field(default_factory=dict)


class ComputeResponse(RobustBaseModel):
    """مخرج حساب حتمي — النتيجة أو رسالة الخطأ (لا يرفع استثناءً)."""

    domain: str
    operation: str
    ok: bool
    result: Any = None
    error: str | None = None


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


@router.post("/reason", response_model=ReasonResponse, summary="Cognitive reasoning core (D-181)")
async def reason_endpoint(
    payload: ReasonRequest,
    _: CurrentUser = Depends(get_current_user),
) -> ReasonResponse:
    """يُشغِّل النواة المعرفية للتفكير المُركَّبة (تفكيك + نقد + منطق/سببية/تجريد/نموذج).

    كلّ المهارات حتمية (fail-open) — يُرجِع دائماً مسار تفكير مُهيكَل لأي سؤال.
    """
    context: dict[str, Any] = {
        k: v
        for k, v in {
            "premises": payload.premises,
            "conclusion": payload.conclusion,
            "edges": payload.edges,
            "classify_pair": payload.classify_pair,
            "counterfactual_node": payload.counterfactual_node,
            "instances": payload.instances,
            "sequence": payload.sequence,
            "source": payload.source,
            "target": payload.target,
            "relations": payload.relations,
            "dynamics": payload.dynamics,
            "model_name": payload.concept_name,
            "compute": payload.compute,
        }.items()
        if v is not None
    }
    composition = compose_reasoning(payload.question, context)
    return ReasonResponse(
        question=composition.question,
        modes=list(composition.modes),
        results=composition.results,
        narrative=composition.narrative,
    )


class NotationRequest(RobustBaseModel):
    """سؤال الطالب الحرّ عن رمز رياضي («ماذا نقصد بحرف C»)."""

    question: str = Field(..., min_length=1, max_length=2000)


class NotationResponse(RobustBaseModel):
    """الرمز المُعرَّف — `found=false` جواب مشروع لا خطأ."""

    found: bool
    symbol: str | None = None
    title: str | None = None
    definition: str | None = None
    example: str | None = None
    concept_id: str | None = None


@router.post("/notation", response_model=NotationResponse, summary="Notation layer (D-185)")
async def notation_endpoint(
    payload: NotationRequest,
    _: CurrentUser = Depends(get_current_user),
) -> NotationResponse:
    """يُعرِّف رمزاً رياضياً من سؤال الطالب الحرّ — «النظام يعرّف كل رمز يطبعه» (D-185).

    حتمي 100% وبلا LLM (CLAUDE.md §0: الحقيقة الرمزية قبل اللغة). يعكس عقد
    `notation-service :8011`، ويعمل كاملاً بدونها (تدهور رشيق — قانون المهارات ٥).
    التعريف **ليس إجابة**: الأمثلة محايدة فلا تسريب لأرقام التمرين الجاري (D-113).
    """
    from app.services.skills.notation_skill import get_notation_skill

    entry = get_notation_skill().resolve(payload.question)
    if entry is None:
        return NotationResponse(found=False)
    return NotationResponse(
        found=True,
        symbol=entry.symbol,
        title=entry.title,
        definition=entry.definition,
        example=entry.example,
        concept_id=entry.concept_id,
    )


@router.post("/illusion", response_model=IllusionGapReport, summary="Illusion-gap map (D-212)")
async def illusion_endpoint(
    payload: IllusionGapInput,
    _: CurrentUser = Depends(get_current_user),
) -> IllusionGapReport:
    """يبني خريطة فجوة الوهم من قياسات BKT/FSRS — حتمي 100% وبلا LLM (D-212).

    فجوة الوهم هي مقياس النجاح الوحيد المُعتمَد (§0.6)، وهذه هي نقطة تحويلها من إشارةٍ
    داخلية إلى مخرَجٍ قابل للعرض. **دون `MIN_OBS` ملاحظةً غير مدعومة لا يُصنَّف مفهوم**:
    يُعَدّ في `immature_suppressed` ويُعرَض — تقريرٌ يلوّن المنهاج بعد جلستين تقريرٌ كاذب.

    ⛔ لا يُعيد حلاًّ ولا خطوةَ اشتقاق: الخريطة تصف **الحالة المعرفية** لا الجواب (D-113).

    العقد **مُستورَد لا مُكرَّر**: `IllusionGapInput`/`IllusionGapReport` هما نفسهما عقد
    المهارة، فلا تنحرف نسخةٌ ثانية عن الأولى — والاستيراد هنا مجّاني لأن
    `app.services.skills.registry` أعلى الملفّ يُحمِّل الحزمة أصلاً.
    """
    from app.services.skills.illusion_gap_skill import get_illusion_gap_skill

    return get_illusion_gap_skill().build(payload)


@router.post("/compute", response_model=ComputeResponse, summary="Foundations compute core (D-183)")
async def compute_endpoint(
    payload: ComputeRequest,
    _: CurrentUser = Depends(get_current_user),
) -> ComputeResponse:
    """يُشغِّل النواة الحاسوبية للأسس (D-183) — جبر خطّي/تفاضل/إحصاء/تحسين/رسوم/لغات صورية/تعقيد.

    حتمي 100% وبلا LLM — الأرقام والبنى من محرّكات `app/core/foundations` المُتحقَّقة.
    fail-open: خطأ المجال يُبلَّغ في `error` ولا يرفع استثناءً.
    """
    from app.services.skills.foundations_compute_skill import (
        FoundationsComputeInput,
        get_foundations_compute_skill,
    )

    out = get_foundations_compute_skill().compute(
        FoundationsComputeInput(
            domain=payload.domain, operation=payload.operation, args=payload.args
        )
    )
    return ComputeResponse(
        domain=out.domain,
        operation=out.operation,
        ok=out.ok,
        result=out.result,
        error=out.error,
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
