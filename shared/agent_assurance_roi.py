"""نموذج حتمي ومتحفظ لقياس عائد تجربة ضمان أفعال الوكلاء."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


def _require_non_negative(name: str, value: Decimal) -> None:
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a finite, non-negative amount")


def _require_probability(name: str, value: Decimal) -> None:
    if not value.is_finite() or value < 0 or value > 1:
        raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class AgentAssuranceROIInputs:
    """مدخلات يقدّمها العميل ويجب إرفاق مصدر كل منها في حزمة التجربة."""

    annual_review_hours: Decimal
    loaded_hourly_cost: Decimal
    annual_incident_count: Decimal
    mean_incident_cost: Decimal
    review_reduction_rate: Decimal
    incident_reduction_rate: Decimal
    annual_assurance_cost: Decimal
    avoided_launch_delay_value: Decimal = Decimal("0")

    def validate(self) -> None:
        """يرفض القيم السالبة أو الاحتمالات غير الصالحة بدلاً من تجميل العائد."""

        for name in (
            "annual_review_hours",
            "loaded_hourly_cost",
            "annual_incident_count",
            "mean_incident_cost",
            "annual_assurance_cost",
            "avoided_launch_delay_value",
        ):
            _require_non_negative(name, getattr(self, name))
        _require_probability("review_reduction_rate", self.review_reduction_rate)
        _require_probability("incident_reduction_rate", self.incident_reduction_rate)


@dataclass(frozen=True, slots=True)
class AgentAssuranceROIResult:
    """نتيجة شفافة تفصل المنافع عن الكلفة ولا تخفي عدم قابلية الاسترداد."""

    review_savings: Decimal
    incident_loss_avoided: Decimal
    total_benefit: Decimal
    net_benefit: Decimal
    roi_ratio: Decimal | None
    payback_months: Decimal | None


def calculate_agent_assurance_roi(inputs: AgentAssuranceROIInputs) -> AgentAssuranceROIResult:
    """يحسب عائداً سنوياً محافظاً من مدخلات موثقة دون افتراض نمو أو امتثال."""

    inputs.validate()
    review_savings = (
        inputs.annual_review_hours * inputs.loaded_hourly_cost * inputs.review_reduction_rate
    )
    incident_loss_avoided = (
        inputs.annual_incident_count * inputs.mean_incident_cost * inputs.incident_reduction_rate
    )
    total_benefit = review_savings + incident_loss_avoided + inputs.avoided_launch_delay_value
    net_benefit = total_benefit - inputs.annual_assurance_cost

    if inputs.annual_assurance_cost == 0:
        roi_ratio = None
    else:
        roi_ratio = net_benefit / inputs.annual_assurance_cost

    if total_benefit == 0:
        payback_months = None
    else:
        payback_months = inputs.annual_assurance_cost / total_benefit * Decimal("12")

    return AgentAssuranceROIResult(
        review_savings=review_savings,
        incident_loss_avoided=incident_loss_avoided,
        total_benefit=total_benefit,
        net_benefit=net_benefit,
        roi_ratio=roi_ratio,
        payback_months=payback_months,
    )
