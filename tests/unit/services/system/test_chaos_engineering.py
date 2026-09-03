import pytest

from app.services.system.chaos_engineering import (
    ChaosEngineer,
    ChaosExperiment,
    FaultInjection,
    FaultType,
    SteadyStateHypothesis,
)


def test_rollback_faults_raises_not_implemented():
    """Verify that _rollback_faults raises NotImplementedError."""
    engineer = ChaosEngineer()
    hypothesis = SteadyStateHypothesis(
        hypothesis_id="test-1", description="test", validation_function=lambda: True
    )
    experiment = ChaosExperiment(
        experiment_id="test-exp-1",
        name="test-exp",
        description="Test",
        steady_state_hypothesis=hypothesis,
        fault_injections=[
            FaultInjection(fault_id="f1", fault_type=FaultType.LATENCY, target_service="svc")
        ],
    )
    with pytest.raises(NotImplementedError, match=r"Fault rollback is not yet implemented\."):
        engineer._rollback_faults(experiment)
