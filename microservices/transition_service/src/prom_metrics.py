"""Prometheus metrics for transition-service (D-174 — observability parity).
Independent ``CollectorRegistry`` (never the default REGISTRY). Defensive import:
if ``prometheus_client`` is missing the module still imports via silent stubs.
Exported metrics (7 × ``cogniforge_transition_*``):
  cogniforge_transition_requests_total
  cogniforge_transition_request_duration_seconds
  cogniforge_transition_active_connections
  cogniforge_transition_agent_calls_total
  cogniforge_transition_governance_decisions_total
  cogniforge_transition_errors_total
  cogniforge_transition_startup_info
"""

from __future__ import annotations

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover - prometheus_client is in requirements-ci
    _PROMETHEUS_AVAILABLE = False

    class _Stub:  # type: ignore[no-redef]
        def __init__(self, *a, **kw) -> None:
            pass

        def labels(self, **kw) -> _Stub:
            return self

        def inc(self, amount: float = 1) -> None:
            pass

        def dec(self, amount: float = 1) -> None:
            pass

        def set(self, value: float) -> None:
            pass

        def observe(self, value: float) -> None:
            pass

        def info(self, *a, **kw) -> None:
            pass

    class _RegistryStub:
        def __init__(self) -> None:
            pass

        def register(self, *a, **kw) -> None:
            pass

    CollectorRegistry = _RegistryStub  # type: ignore[misc]
    Counter = Histogram = Gauge = _Stub  # type: ignore[misc]
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest(registry=None) -> bytes:  # type: ignore[misc]
        return b""


registry = CollectorRegistry()  # مستقلة — لا تلمس REGISTRY الافتراضية

REQUESTS = Counter(
    "cogniforge_transition_requests_total",
    "Total HTTP requests to transition-service",
    ["method", "endpoint", "status"],
    registry=registry,
)
DURATION = Histogram(
    "cogniforge_transition_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint"],
    registry=registry,
)
ACTIVE = Gauge(
    "cogniforge_transition_active_connections",
    "Active connections",
    registry=registry,
)
AGENT_CALLS = Counter(
    "cogniforge_transition_agent_calls_total",
    "Agent invocations",
    ["agent", "outcome"],
    registry=registry,
)
GOV_DECISIONS = Counter(
    "cogniforge_transition_governance_decisions_total",
    "Governance gate decisions",
    ["level", "allowed"],
    registry=registry,
)
ERRORS = Counter(
    "cogniforge_transition_errors_total",
    "Unhandled errors",
    registry=registry,
)
STARTUP = Gauge(
    "cogniforge_transition_startup_info",
    "Startup info (value=1, labels=service,version)",
    ["service", "version"],
    registry=registry,
)


def set_startup_info() -> None:
    import contextlib

    with contextlib.suppress(Exception):
        STARTUP.labels(service="transition-service", version="1.0.0").set(1)


def export_prometheus_text() -> tuple[str, str]:
    return generate_latest(registry).decode("utf-8"), CONTENT_TYPE_LATEST
