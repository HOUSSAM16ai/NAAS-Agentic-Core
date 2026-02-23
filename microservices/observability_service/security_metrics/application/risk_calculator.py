"""
Risk Calculator Application Service
Implements advanced risk scoring algorithms
"""

from datetime import datetime

from ..domain.models import SecurityFinding
from ..domain.ports import RiskCalculatorPort


class AdvancedRiskCalculator(RiskCalculatorPort):
    """
    Advanced risk calculator using FAANG-style algorithms
    Inspired by: Google's Risk Score, Meta's Security Score
    """

    def __init__(self):
        self.severity_weights = {
            "CRITICAL": 10.0,
            "HIGH": 7.5,
            "MEDIUM": 5.0,
            "LOW": 2.5,
            "INFO": 1.0,
        }

        self.cwe_risk_multipliers = {
            "CWE-89": 2.0,  # SQL Injection
            "CWE-79": 1.8,  # XSS
            "CWE-798": 2.5,  # Hard-coded credentials
            "CWE-327": 1.5,  # Broken crypto
            "CWE-22": 1.7,  # Path traversal
        }

    def calculate_risk_score(
        self, findings: list[SecurityFinding], code_metrics: dict | None = None
    ) -> float:
        """
        حساب درجة المخاطر المتقدمة | Calculate advanced risk score

        الصيغة: Risk = Σ(Severity × Age × Exposure × CWE_multiplier) / Normalization
        Formula: Risk = Σ(Severity × Age × Exposure × CWE_multiplier) / Normalization
        """
        if not findings:
            return 0.0

        code_metrics = code_metrics or {}
        public_endpoints = code_metrics.get("public_endpoints", 10)

        total_risk = self._calculate_total_risk(findings, public_endpoints)
        risk_score = self._normalize_risk_score(total_risk, len(findings))

        return round(risk_score, 2)

    def _calculate_total_risk(
        self, findings: list[SecurityFinding], public_endpoints: int
    ) -> float:
        """
        حساب إجمالي المخاطر | Calculate total risk

        Args:
            findings: قائمة الاكتشافات الأمنية | Security findings list
            public_endpoints: عدد النقاط العامة | Number of public endpoints

        Returns:
            إجمالي المخاطر | Total risk value
        """
        total_risk = 0.0

        for finding in findings:
            if finding.fixed or finding.false_positive:
                continue

            finding_risk = self._calculate_finding_risk(finding, public_endpoints)
            total_risk += finding_risk

        return total_risk

    def _calculate_finding_risk(self, finding: SecurityFinding, public_endpoints: int) -> float:
        """
        حساب مخاطر اكتشاف واحد | Calculate risk for a single finding

        Args:
            finding: اكتشاف أمني | Security finding
            public_endpoints: عدد النقاط العامة | Number of public endpoints

        Returns:
            قيمة المخاطر | Risk value
        """
        severity_score = self.severity_weights.get(finding.severity.value, 1.0)
        age_factor = self._calculate_age_factor(finding.first_seen)
        exposure_factor = self.calculate_exposure_factor(finding.file_path, public_endpoints)
        cwe_multiplier = self.cwe_risk_multipliers.get(finding.cwe_id, 1.0)

        return severity_score * age_factor * exposure_factor * cwe_multiplier

    def _normalize_risk_score(self, total_risk: float, num_findings: int) -> float:
        """
        تطبيع درجة المخاطر | Normalize risk score

        Args:
            total_risk: إجمالي المخاطر | Total risk
            num_findings: عدد الاكتشافات | Number of findings

        Returns:
            درجة المخاطر المطبعة (0-100) | Normalized risk score (0-100)
        """
        normalization_factor = num_findings * 10.0
        risk_score = (total_risk / normalization_factor) * 100
        return min(risk_score, 100.0)

    def calculate_exposure_factor(self, file_path: str, public_endpoints: int) -> float:
        """Calculate file exposure factor"""
        exposure = 1.0

        high_exposure_patterns = [
            "api/",
            "routes/",
            "views/",
            "controllers/",
            "auth/",
            "login",
            "admin/",
        ]

        for pattern in high_exposure_patterns:
            if pattern in file_path.lower():
                exposure *= 1.5

        low_exposure_patterns = ["test_", "tests/", "migrations/", "scripts/"]

        for pattern in low_exposure_patterns:
            if pattern in file_path.lower():
                exposure *= 0.5

        return min(exposure, 3.0)

    def _calculate_age_factor(self, first_seen: datetime) -> float:
        """Calculate age factor (older findings = higher risk)"""
        age_days = (datetime.now() - first_seen).days
        age_factor = 1 + (age_days / 30.0)
        return min(age_factor, 5.0)
