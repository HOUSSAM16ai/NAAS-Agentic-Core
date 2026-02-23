"""
In-Memory Repositories
Simple in-memory implementations for testing and development
"""

from datetime import datetime, timedelta

from app.services.security_metrics.domain.models import SecurityFinding, SecurityMetrics


class InMemoryFindingsRepository:
    """In-memory findings repository"""

    def __init__(self):
        self._findings: dict[str, SecurityFinding] = {}

    def save_finding(self, finding: SecurityFinding) -> None:
        """Save a finding"""
        self._findings[finding.id] = finding

    def get_findings(self, filters: dict | None = None) -> list[SecurityFinding]:
        """Get findings with optional filters"""
        findings = list(self._findings.values())

        if not filters:
            return findings

        if "severity" in filters:
            findings = [f for f in findings if f.severity == filters["severity"]]

        if "fixed" in filters:
            findings = [f for f in findings if f.fixed == filters["fixed"]]

        if "developer_id" in filters:
            findings = [f for f in findings if f.developer_id == filters["developer_id"]]

        return findings

    def update_finding(self, finding_id: str, updates: dict) -> None:
        """Update a finding"""
        if finding_id in self._findings:
            finding = self._findings[finding_id]
            for key, value in updates.items():
                if hasattr(finding, key):
                    setattr(finding, key, value)


class InMemoryMetricsRepository:
    """In-memory metrics repository"""

    def __init__(self):
        self._metrics: list[SecurityMetrics] = []

    def save_metrics(self, metrics: SecurityMetrics) -> None:
        """Save metrics"""
        self._metrics.append(metrics)

    def get_historical_metrics(self, days: int = 30) -> list[SecurityMetrics]:
        """Get historical metrics"""
        cutoff = datetime.now() - timedelta(days=days)
        return [m for m in self._metrics if m.timestamp >= cutoff]
