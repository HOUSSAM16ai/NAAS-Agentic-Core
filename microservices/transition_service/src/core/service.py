"""الخدمة الأساسية لخدمة التحول — منسّق الوكلاء الثلاثة عشر.

طبقة التنسيق (وثيقة المشروع §5): موجّه حتمي يرسل كل طلب للوكيل المختص،
ويُمرّر كل طلب «اتخاذ إجراء» عبر بوابة الحوكمة الأربعة مستويات قبل أي تنفيذ.
الوكلاء كلها نقية (pure) وحتمية في حساباتها — المحرك اللغوي للنص التفسيري فقط.
"""

from __future__ import annotations

from microservices.transition_service.src.agents import (
    dialogue,
    early_warning,
    education,
    equity,
    evaluation,
    exposure,
    governance,
    job_creation,
    red_team,
    simulation,
    skills_gap,
    social_protection,
    transition,
)
from microservices.transition_service.src.core.governance import (
    GOVERNANCE_LOG,
    DecisionLogEntry,
    classify_decision,
)
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


class TransitionService:
    """منسّق وكلاء منظومة تحول الذكاء الاصطناعي."""

    AGENTS = (
        "early_warning",
        "occupation_exposure",
        "skills_gap",
        "career_transition",
        "education",
        "job_creation",
        "social_protection",
        "governance",
        "equity",
        "simulation",
        "dialogue",
        "evaluation",
        "red_team",
    )

    async def early_warning(self, request: EarlyWarningRequest) -> StandardResponse:
        return await early_warning.early_warning(request)

    async def occupation_exposure(self, request: ExposureRequest) -> StandardResponse:
        return await exposure.occupation_exposure(request)

    async def skills_gap(self, request: SkillsGapRequest) -> StandardResponse:
        return await skills_gap.skills_gap(request)

    async def career_transition(self, request: TransitionRequest) -> StandardResponse:
        return await transition.career_transition(request)

    async def education(self, request: EducationRequest) -> StandardResponse:
        return await education.education(request)

    async def job_creation(self, request: JobCreationRequest) -> StandardResponse:
        return await job_creation.job_creation(request)

    async def social_protection(self, request: SocialProtectionRequest) -> StandardResponse:
        return await social_protection.social_protection(request)

    async def governance(self, request: GovernanceRequest) -> StandardResponse:
        return await governance.governance(request)

    async def equity(self, request: EquityRequest) -> StandardResponse:
        return await equity.equity(request)

    async def simulation(self, request: SimulationRequest) -> StandardResponse:
        return await simulation.simulation(request)

    async def dialogue(self, request: DialogueRequest) -> StandardResponse:
        return await dialogue.dialogue(request)

    async def evaluation(self, request: EvaluationRequest) -> StandardResponse:
        return await evaluation.evaluation(request)

    async def red_team(self, request: RedTeamRequest) -> StandardResponse:
        return await red_team.red_team(request)

    def decide_action(self, request: GovernanceApprovalRequest) -> DecisionResponse:
        """بوابة القرار الأربعة مستويات — أي إجراء تنفيذي يمر من هنا."""
        decision = classify_decision(request.action_key, request.description)
        # تقييد السقف الزمني والمالي للإجراءات منخفضة المخاطر
        if decision.level == 3 and (request.duration_days > 90 or request.budget > 5_000_000):
            decision = classify_decision(
                request.action_key, request.description + " [exceeds caps]"
            )
            # يتحول تلقائياً إلى مستوى استشارة — لا يتخطى السقوف
            from microservices.transition_service.src.core.governance import (
                DecisionLevel,
                GovernanceDecision,
            )

            decision = GovernanceDecision(
                level=DecisionLevel.ASSISTIVE,
                allowed=True,
                reason=(
                    "الإجراء ضمن القوالب المنخفضة المخاطر لكنه يتجاوز السقف الزمني (90 يوماً) "
                    "أو المالي (5,000,000) — يُخفَّض إلى مستوى مساند بمراجعة بشرية"
                ),
                human_oversight_required=True,
                human_action_description="مراجعة بشرية لصلاحيات السقف قبل التنفيذ",
            )
        entry = GOVERNANCE_LOG.log(
            DecisionLogEntry(
                request_id=request.request_id,
                agent=request.agent,
                action_key=request.action_key,
                description=request.description,
                decision=decision,
            )
        )
        return DecisionResponse(
            allowed=decision.allowed,
            decision_level=decision.level.name,
            reason=decision.reason,
            human_action_description=decision.human_action_description,
            decision_log=entry.to_dict(),
        )

    async def dispatch(self, agent_name: str, payload: dict[str, object]) -> StandardResponse:
        """موجّه الطلبات — للاستخدام العام (orchestration layer)."""
        if agent_name not in self.AGENTS:
            raise ValueError(f"unknown agent: {agent_name}")
        dispatch_map = {
            "early_warning": early_warning.EarlyWarningRequest,
            "occupation_exposure": exposure.ExposureRequest,
            "skills_gap": skills_gap.SkillsGapRequest,
            "career_transition": transition.TransitionRequest,
            "education": education.EducationRequest,
            "job_creation": job_creation.JobCreationRequest,
            "social_protection": social_protection.SocialProtectionRequest,
            "governance": governance.GovernanceRequest,
            "equity": equity.EquityRequest,
            "simulation": simulation.SimulationRequest,
            "dialogue": dialogue.DialogueRequest,
            "evaluation": evaluation.EvaluationRequest,
            "red_team": red_team.RedTeamRequest,
        }
        handler = {
            "early_warning": self.early_warning,
            "occupation_exposure": self.occupation_exposure,
            "skills_gap": self.skills_gap,
            "career_transition": self.career_transition,
            "education": self.education,
            "job_creation": self.job_creation,
            "social_protection": self.social_protection,
            "governance": self.governance,
            "equity": self.equity,
            "simulation": self.simulation,
            "dialogue": self.dialogue,
            "evaluation": self.evaluation,
            "red_team": self.red_team,
        }[agent_name]
        return await handler(dispatch_map[agent_name].model_validate(payload))

    def governance_overview(self) -> dict[str, object]:
        """نظرة عامة على سجل الحوكمة — يقرأه وكيل التقييم."""
        return {
            "total_decisions": len(GOVERNANCE_LOG.entries()),
            "rejected_count": GOVERNANCE_LOG.rejected_count(),
            "by_agent": {
                agent: len(GOVERNANCE_LOG.entries_by_agent(agent)) for agent in self.AGENTS
            },
        }
