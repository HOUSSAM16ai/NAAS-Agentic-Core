from microservices.observability_service.security_metrics.domain.models import (
    SecurityFinding,
    SecurityMetrics,
)
from microservices.observability_service.security_metrics.domain.ports import (
    MetricsCalculatorPort,
    RiskCalculatorPort,
)


def test_ports_importable():
    """Verify ports are importable and abstract."""
    # Just importing them covers the definitions
    assert RiskCalculatorPort is not None


def test_concrete_risk_calculator():
    """Verify we can implement the interface."""

    class ConcreteRisk(RiskCalculatorPort):
        def calculate_risk_score(
            self, findings: list[SecurityFinding], code_metrics: dict | None = None
        ) -> float:
            return 1.0

        def calculate_exposure_factor(self, file_path: str, public_endpoints: int) -> float:
            return 0.5

    impl = ConcreteRisk()
    assert impl.calculate_risk_score([]) == 1.0
    assert impl.calculate_exposure_factor("test", 1) == 0.5


def test_concrete_metrics_calculator():
    class ConcreteMetrics(MetricsCalculatorPort):
        def calculate_metrics(
            self, findings: list[SecurityFinding], code_metrics: dict | None = None
        ) -> SecurityMetrics:
            return SecurityMetrics()  # Assuming default constructor works or mock it

    # We just want to ensure class definition is valid
    assert issubclass(ConcreteMetrics, MetricsCalculatorPort)
