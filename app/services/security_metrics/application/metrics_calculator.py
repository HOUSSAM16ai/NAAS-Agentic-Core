"""
Metrics Calculator Application Service
Calculates comprehensive security metrics
"""

import warnings
from datetime import datetime, timedelta

from app.services.security_metrics.domain.models import (
    SecurityFinding,
    SecurityMetrics,
    Severity,
    TrendDirection,
)
from app.services.security_metrics.domain.ports import MetricsCalculatorPort


class ComprehensiveMetricsCalculator(MetricsCalculatorPort):
    """
    Calculate comprehensive security metrics.
    DEPRECATED: Use ObservabilityServiceClient instead.
    """

    def __init__(self):
        warnings.warn(
            "ComprehensiveMetricsCalculator is deprecated. Use ObservabilityServiceClient.",
            DeprecationWarning,
            stacklevel=2,
        )

    def calculate_metrics(
        self, findings: list[SecurityFinding], code_metrics: dict | None = None
    ) -> SecurityMetrics:
        """Calculate all security metrics"""
        code_metrics = code_metrics or {}
        lines_of_code = code_metrics.get("lines_of_code", 10000)

        severity_counts = self._count_by_severity(findings)
        velocity_metrics = self._calculate_velocity_metrics(findings)
        quality_metrics = self._calculate_quality_metrics(findings)
        team_metrics = self._calculate_team_metrics(findings)

        return SecurityMetrics(
            total_findings=len(findings),
            critical_count=severity_counts[Severity.CRITICAL],
            high_count=severity_counts[Severity.HIGH],
            medium_count=severity_counts[Severity.MEDIUM],
            low_count=severity_counts[Severity.LOW],
            findings_per_1000_loc=round((len(findings) / lines_of_code) * 1000, 2),
            new_findings_last_24h=velocity_metrics["new_24h"],
            fixed_findings_last_24h=velocity_metrics["fixed_24h"],
            false_positive_rate=quality_metrics["fp_rate"],
            mean_time_to_detect=quality_metrics["mttd"],
            mean_time_to_fix=quality_metrics["mttf"],
            overall_risk_score=0.0,  # Calculated separately
            security_debt_score=0.0,  # Calculated separately
            trend_direction=TrendDirection.STABLE,
            findings_per_developer=team_metrics["findings_per_dev"],
            fix_rate_per_developer=team_metrics["fix_rate_per_dev"],
        )

    def _count_by_severity(self, findings: list[SecurityFinding]) -> dict[Severity, int]:
        """Count findings by severity"""
        counts = dict.fromkeys(Severity, 0)
        for finding in findings:
            if not finding.fixed and not finding.false_positive:
                counts[finding.severity] += 1
        return counts

    def _calculate_velocity_metrics(self, findings: list[SecurityFinding]) -> dict:
        """Calculate velocity metrics"""
        now = datetime.now()
        cutoff_24h = now - timedelta(hours=24)

        new_24h = sum(1 for f in findings if f.first_seen >= cutoff_24h)
        fixed_24h = sum(1 for f in findings if f.fixed and f.last_seen >= cutoff_24h)

        return {"new_24h": new_24h, "fixed_24h": fixed_24h}

    def _calculate_quality_metrics(self, findings: list[SecurityFinding]) -> dict:
        """Calculate quality metrics"""
        total = len(findings)
        false_positives = sum(1 for f in findings if f.false_positive)
        fp_rate = (false_positives / total * 100) if total > 0 else 0.0

        fix_times = [f.fix_time_hours for f in findings if f.fix_time_hours is not None]
        mttf = sum(fix_times) / len(fix_times) if fix_times else 0.0

        return {"fp_rate": round(fp_rate, 2), "mttd": 0.0, "mttf": round(mttf, 2)}

    def _calculate_team_metrics(self, findings: list[SecurityFinding]) -> dict:
        """Calculate team metrics"""
        findings_per_dev = {}
        fix_rate_per_dev = {}

        for finding in findings:
            if finding.developer_id:
                findings_per_dev[finding.developer_id] = (
                    findings_per_dev.get(finding.developer_id, 0) + 1
                )

        for dev_id in findings_per_dev:
            dev_findings = [f for f in findings if f.developer_id == dev_id]
            fixed = sum(1 for f in dev_findings if f.fixed)
            total = len(dev_findings)
            fix_rate_per_dev[dev_id] = round((fixed / total * 100) if total > 0 else 0.0, 2)

        return {"findings_per_dev": findings_per_dev, "fix_rate_per_dev": fix_rate_per_dev}
