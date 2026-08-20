"""خدمة التحول — منظومة وكلاء الذكاء الاصطناعي لإدارة تحول الذكاء الاصطناعي
في سوق العمل والتعليم والحوكمة (وثيقة المشروع).

13 وكيلاً متخصصاً + بوابة حوكمة من أربعة مستويات + سجل حوكمة قابل للتدقيق.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Response

from microservices.transition_service.src import prom_metrics
from microservices.transition_service.src.core.service import TransitionService
from microservices.transition_service.src.schemas import (
    DecisionResponse,
    DialogueRequest,
    EarlyWarningRequest,
    EducationRequest,
    EquityRequest,
    EvaluationRequest,
    ExposureRequest,
    GovernanceApprovalRequest,
    GovernanceRequest,
    JobCreationRequest,
    RedTeamRequest,
    SimulationRequest,
    SkillsGapRequest,
    SocialProtectionRequest,
    StandardResponse,
    TransitionRequest,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TransitionService")

app = FastAPI(title="Transition Service", version="1.0.0")

service = TransitionService()
prom_metrics.set_startup_info()


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint (cogniforge_transition_*). Hidden from OpenAPI."""
    content, content_type = prom_metrics.export_prometheus_text()
    return Response(content=content, media_type=content_type)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "transition"}


@app.get("/agents")
async def list_agents() -> dict[str, object]:
    return {"agents": list(TransitionService.AGENTS)}


@app.post("/early-warning", response_model=StandardResponse)
async def early_warning(request: EarlyWarningRequest) -> StandardResponse:
    return await service.early_warning(request)


@app.post("/exposure", response_model=StandardResponse)
async def occupation_exposure(request: ExposureRequest) -> StandardResponse:
    return await service.occupation_exposure(request)


@app.post("/skills-gap", response_model=StandardResponse)
async def skills_gap(request: SkillsGapRequest) -> StandardResponse:
    return await service.skills_gap(request)


@app.post("/transition", response_model=StandardResponse)
async def career_transition(request: TransitionRequest) -> StandardResponse:
    return await service.career_transition(request)


@app.post("/education", response_model=StandardResponse)
async def education(request: EducationRequest) -> StandardResponse:
    return await service.education(request)


@app.post("/job-creation", response_model=StandardResponse)
async def job_creation(request: JobCreationRequest) -> StandardResponse:
    return await service.job_creation(request)


@app.post("/social-protection", response_model=StandardResponse)
async def social_protection(request: SocialProtectionRequest) -> StandardResponse:
    return await service.social_protection(request)


@app.post("/governance", response_model=StandardResponse)
async def governance(request: GovernanceRequest) -> StandardResponse:
    return await service.governance(request)


@app.post("/equity", response_model=StandardResponse)
async def equity(request: EquityRequest) -> StandardResponse:
    return await service.equity(request)


@app.post("/simulation", response_model=StandardResponse)
async def simulation(request: SimulationRequest) -> StandardResponse:
    return await service.simulation(request)


@app.post("/dialogue", response_model=StandardResponse)
async def dialogue(request: DialogueRequest) -> StandardResponse:
    return await service.dialogue(request)


@app.post("/evaluation", response_model=StandardResponse)
async def evaluation(request: EvaluationRequest) -> StandardResponse:
    return await service.evaluation(request)


@app.post("/red-team", response_model=StandardResponse)
async def red_team(request: RedTeamRequest) -> StandardResponse:
    return await service.red_team(request)


@app.post("/governance/decide", response_model=DecisionResponse)
async def governance_decide(request: GovernanceApprovalRequest) -> DecisionResponse:
    """بوابة الحوكمة — أي إجراء تنفيذي يمر من هنا قبل تنفيذه."""
    return service.decide_action(request)


@app.get("/governance/log")
async def governance_log() -> dict[str, object]:
    return service.governance_overview()


@app.post("/dispatch/{agent_name}", response_model=StandardResponse)
async def dispatch(agent_name: str, payload: dict[str, object]) -> StandardResponse:
    """موجّه عام — للطبقة التنسيقية (orchestration layer)."""
    try:
        return await service.dispatch(agent_name, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("dispatch error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
