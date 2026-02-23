"""
Security Metrics Domain Models
Domain entities for security metrics and findings
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Severity(StrEnum):
    """Security finding severity levels"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TrendDirection(StrEnum):
    """Security trend direction"""

    IMPROVING = "IMPROVING"
    DEGRADING = "DEGRADING"
    STABLE = "STABLE"


@dataclass
class SecurityFinding:
    """Security finding entity"""

    id: str
    severity: Severity
    rule_id: str
    file_path: str
    line_number: int
    message: str
    cwe_id: str | None = None
    owasp_category: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    false_positive: bool = False
    fixed: bool = False
    fix_time_hours: float | None = None
    developer_id: str | None = None

    def __post_init__(self):
        if not self.first_seen:
            self.first_seen = datetime.now()
        if not self.last_seen:
            self.last_seen = datetime.now()


@dataclass
class SecurityMetrics:
    """Security metrics aggregate"""

    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings_per_1000_loc: float
    new_findings_last_24h: int
    fixed_findings_last_24h: int
    false_positive_rate: float
    mean_time_to_detect: float
    mean_time_to_fix: float
    overall_risk_score: float
    security_debt_score: float
    trend_direction: TrendDirection
    findings_per_developer: dict[str, int]
    fix_rate_per_developer: dict[str, float]
    timestamp: datetime | None = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class RiskPrediction:
    """Risk prediction result"""

    predicted_risk: float
    confidence: float
    trend: TrendDirection
    slope: float
    current_risk: float
