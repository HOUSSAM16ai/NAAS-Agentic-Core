"""اختبارات نموذج عائد ضمان أفعال الوكلاء."""

from decimal import Decimal

import pytest

from shared.agent_assurance_roi import (
    AgentAssuranceROIInputs,
    calculate_agent_assurance_roi,
)


def test_calculate_agent_assurance_roi_keeps_benefits_auditable() -> None:
    inputs = AgentAssuranceROIInputs(
        annual_review_hours=Decimal("1000"),
        loaded_hourly_cost=Decimal("50"),
        annual_incident_count=Decimal("4"),
        mean_incident_cost=Decimal("10000"),
        review_reduction_rate=Decimal("0.30"),
        incident_reduction_rate=Decimal("0.25"),
        annual_assurance_cost=Decimal("15000"),
        avoided_launch_delay_value=Decimal("5000"),
    )

    result = calculate_agent_assurance_roi(inputs)

    assert result.review_savings == Decimal("15000.00")
    assert result.incident_loss_avoided == Decimal("10000.00")
    assert result.total_benefit == Decimal("30000.00")
    assert result.net_benefit == Decimal("15000.00")
    assert result.roi_ratio == Decimal("1.00")
    assert result.payback_months == Decimal("6")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("annual_review_hours", Decimal("-1")),
        ("review_reduction_rate", Decimal("1.01")),
        ("incident_reduction_rate", Decimal("NaN")),
    ],
)
def test_calculate_agent_assurance_roi_rejects_invalid_inputs(field: str, value: Decimal) -> None:
    values = {
        "annual_review_hours": Decimal("100"),
        "loaded_hourly_cost": Decimal("50"),
        "annual_incident_count": Decimal("2"),
        "mean_incident_cost": Decimal("1000"),
        "review_reduction_rate": Decimal("0.2"),
        "incident_reduction_rate": Decimal("0.1"),
        "annual_assurance_cost": Decimal("5000"),
    }
    values[field] = value

    with pytest.raises(ValueError):
        calculate_agent_assurance_roi(AgentAssuranceROIInputs(**values))


def test_zero_cost_or_zero_benefit_is_explicitly_undefined() -> None:
    zero_cost = AgentAssuranceROIInputs(
        annual_review_hours=Decimal("1"),
        loaded_hourly_cost=Decimal("1"),
        annual_incident_count=Decimal("0"),
        mean_incident_cost=Decimal("0"),
        review_reduction_rate=Decimal("1"),
        incident_reduction_rate=Decimal("0"),
        annual_assurance_cost=Decimal("0"),
    )
    zero_benefit = AgentAssuranceROIInputs(
        annual_review_hours=Decimal("0"),
        loaded_hourly_cost=Decimal("0"),
        annual_incident_count=Decimal("0"),
        mean_incident_cost=Decimal("0"),
        review_reduction_rate=Decimal("0"),
        incident_reduction_rate=Decimal("0"),
        annual_assurance_cost=Decimal("1"),
    )

    assert calculate_agent_assurance_roi(zero_cost).roi_ratio is None
    assert calculate_agent_assurance_roi(zero_benefit).payback_months is None
