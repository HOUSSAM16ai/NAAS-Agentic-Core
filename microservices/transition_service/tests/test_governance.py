"""Unit tests for the four-level governance gate.

Key invariants (project charter §5):
1. Informational decisions (recommendations) never execute — the human always decides.
2. High-risk triggers (فصل / termination / رفض / salary reduction ...) are
   automatically rejected and referred to a human board — this is the
   EU AI Act Art. 6 employment classification made executable.
3. Low-risk execution is only allowed for explicitly named action keys, and
   bounded by the 90-day / 5M-budget caps.
4. Every decision is logged with request id, agent, action key — auditable.
"""

import uuid

import pytest

from microservices.transition_service.src.core.governance import (
    ALLOWED_LOW_RISK_ACTIONS,
    GOVERNANCE_LOG,
    DecisionLevel,
    classify_decision,
)
from microservices.transition_service.src.core.service import TransitionService
from microservices.transition_service.src.schemas import GovernanceApprovalRequest


@pytest.fixture(autouse=True)
def clear_log() -> None:
    GOVERNANCE_LOG.clear()


def _approve(action_key: str, description: str, days: int = 0, budget: float = 0.0) -> None:
    req = GovernanceApprovalRequest(
        request_id=str(uuid.uuid4()),
        agent="test_agent",
        action_key=action_key,
        description=description,
        duration_days=days,
        budget=budget,
    )
    service = TransitionService()
    return service.decide_action(req)


class TestDecisionLevels:
    def test_default_decisions_are_informational(self) -> None:
        # Generic actions default to informational — agents never execute by default.
        dec = classify_decision("some_generic_action", "general labor-market bulletin")
        assert dec.allowed is True
        assert dec.level == DecisionLevel.INFORMATIVE
        assert dec.human_oversight_required is False
        assert "بشري" in dec.human_action_description

    def test_high_risk_triggers_rejected(self) -> None:
        for description in ("فصل العامل", "termination of contract", "رفض التوظيف", "خفض الأجر"):
            dec = classify_decision("any_action", description)
            assert dec.allowed is False, description
            assert dec.level == DecisionLevel.HIGH_RISK_REJECT, description
            assert dec.human_oversight_required is True, description

    def test_low_risk_allowed_keys_executable(self) -> None:
        key = next(iter(ALLOWED_LOW_RISK_ACTIONS))
        dec = classify_decision(key, "safe templated action")
        assert dec.allowed is True
        assert dec.level == DecisionLevel.LOW_RISK_EXEC

    def test_high_risk_key_in_description_overrides(self) -> None:
        key = next(iter(ALLOWED_LOW_RISK_ACTIONS))
        dec = classify_decision(key, "فصل العمال قبل التنفيذ")
        assert dec.allowed is False  # description trigger words win

    def test_covers_distinct_levels(self) -> None:
        levels = {classify_decision(key, "t").level for key in list(ALLOWED_LOW_RISK_ACTIONS)[:3]}
        levels.add(classify_decision("notify_workers", "ت").level)
        levels.add(classify_decision("terminate_contract", "فصل").level)
        assert DecisionLevel.LOW_RISK_EXEC in levels
        assert DecisionLevel.INFORMATIVE in levels
        assert DecisionLevel.HIGH_RISK_REJECT in levels


class TestCaps:
    def test_low_risk_exceeding_duration_downgraded(self) -> None:
        service = TransitionService()
        req = GovernanceApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent="test_agent",
            action_key="generate_report",
            description="Quarterly benchmark report",
            duration_days=100,  # exceeds 90-day cap
            budget=0.0,
        )
        res = service.decide_action(req)
        assert res.allowed is True
        assert res.decision_level == DecisionLevel.ASSISTIVE.name

    def test_low_risk_exceeding_budget_downgraded(self) -> None:
        service = TransitionService()
        req = GovernanceApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent="test_agent",
            action_key="generate_report",
            description="Quarterly benchmark report",
            duration_days=0,
            budget=6_000_000.0,  # exceeds 5M cap
        )
        res = service.decide_action(req)
        assert res.decision_level == DecisionLevel.ASSISTIVE.name

    def test_within_caps_unchanged(self) -> None:
        service = TransitionService()
        req = GovernanceApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent="test_agent",
            action_key="generate_report",
            description="Quarterly benchmark report",
            duration_days=30,
            budget=100_000.0,
        )
        res = service.decide_action(req)
        assert res.decision_level == DecisionLevel.LOW_RISK_EXEC.name


class TestDecisionLog:
    def test_every_decision_logged(self) -> None:
        service = TransitionService()
        req = GovernanceApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent="sim_agent",
            action_key="generate_report",
            description="Quarterly benchmark report",
        )
        service.decide_action(req)
        entries = GOVERNANCE_LOG.entries()
        assert len(entries) == 1
        assert entries[0].request_id == req.request_id
        assert entries[0].agent == "sim_agent"
        assert entries[0].decision.level == DecisionLevel.LOW_RISK_EXEC

    def test_rejected_decisions_counted(self) -> None:
        service = TransitionService()
        req = GovernanceApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent="sim_agent",
            action_key="terminate_worker",
            description="فصل العامل رقم 42",
        )
        service.decide_action(req)
        assert GOVERNANCE_LOG.rejected_count() == 1
        assert GOVERNANCE_LOG.rejected_count() == len(
            [e for e in GOVERNANCE_LOG.entries() if not e.decision.allowed]
        )

    def test_log_exportable(self) -> None:
        service = TransitionService()
        req = GovernanceApprovalRequest(
            request_id=str(uuid.uuid4()),
            agent="log_agent",
            action_key="generate_report",
            description="report",
        )
        service.decide_action(req)
        row = GOVERNANCE_LOG.export_row()
        assert len(row) == 1
        assert row[0]["decision_level"] == DecisionLevel.LOW_RISK_EXEC.name
