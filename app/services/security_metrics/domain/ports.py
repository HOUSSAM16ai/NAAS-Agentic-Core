"""
Security Metrics Domain Ports
Interfaces for security metrics operations
"""

from abc import ABC, abstractmethod

from .models import RiskPrediction, SecurityFinding, SecurityMetrics


class RiskCalculatorPort(ABC):
    """Port for risk calculation"""

    @abstractmethod
    def calculate_risk_score(
        self, findings: list[SecurityFinding], code_metrics: dict | None = None
    ) -> float:
        """Calculate overall risk score"""
        pass

    @abstractmethod
    def calculate_exposure_factor(self, file_path: str, public_endpoints: int) -> float:
        """Calculate file exposure factor"""
        pass


class PredictiveAnalyticsPort(ABC):
    """Port for predictive analytics"""

    @abstractmethod
    def predict_future_risk(
        self, historical_metrics: list[SecurityMetrics], days_ahead: int = 30
    ) -> RiskPrediction:
        """Predict future risk based on historical data"""
        pass


class MetricsCalculatorPort(ABC):
    """Port for metrics calculation"""

    @abstractmethod
    def calculate_metrics(
        self, findings: list[SecurityFinding], code_metrics: dict | None = None
    ) -> SecurityMetrics:
        """Calculate comprehensive security metrics"""
        pass


class AnomalyDetectorPort(ABC):
    """Port for anomaly detection"""

    @abstractmethod
    def detect_anomalies(
        self, current_metrics: SecurityMetrics, historical_metrics: list[SecurityMetrics]
    ) -> list[dict]:
        """Detect anomalies in security metrics"""
        pass
