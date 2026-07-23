"""Prometheus metrics for foundations-service (D-183).

"Instrumentation before visualization": every compute call is recorded before
any dashboard exists. Independent ``CollectorRegistry`` — never shares the global
REGISTRY (the "never share a CollectorRegistry across microservices" rule).

Metrics:
  cogniforge_foundations_requests_total            — total HTTP requests {endpoint, status}
  cogniforge_foundations_request_duration_seconds  — request latency histogram
  cogniforge_foundations_active_connections        — in-flight requests gauge
  cogniforge_foundations_compute_invocations_total — compute calls {domain, status}
  cogniforge_foundations_compute_duration_seconds  — compute latency histogram {domain}
  cogniforge_foundations_compute_errors_total      — compute failures {domain, error}
  cogniforge_foundations_domain_operations_total   — operations per domain {domain, operation}
  cogniforge_foundations_startup_info              — startup info {step, version, domains}
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry()

_requests = Counter(
    "cogniforge_foundations_requests_total",
    "Total foundations-service HTTP requests",
    ["endpoint", "status"],
    registry=REGISTRY,
)

_request_duration = Histogram(
    "cogniforge_foundations_request_duration_seconds",
    "foundations-service request latency (seconds)",
    ["endpoint"],
    registry=REGISTRY,
)

_active = Gauge(
    "cogniforge_foundations_active_connections",
    "In-flight foundations-service requests",
    registry=REGISTRY,
)

_compute_invocations = Counter(
    "cogniforge_foundations_compute_invocations_total",
    "Deterministic compute invocations",
    ["domain", "status"],
    registry=REGISTRY,
)

_compute_duration = Histogram(
    "cogniforge_foundations_compute_duration_seconds",
    "Deterministic compute latency (seconds)",
    ["domain"],
    registry=REGISTRY,
)

_compute_errors = Counter(
    "cogniforge_foundations_compute_errors_total",
    "Deterministic compute failures",
    ["domain", "error"],
    registry=REGISTRY,
)

_domain_operations = Counter(
    "cogniforge_foundations_domain_operations_total",
    "Operations executed per domain",
    ["domain", "operation"],
    registry=REGISTRY,
)

_startup_info = Gauge(
    "cogniforge_foundations_startup_info",
    "foundations-service startup info",
    ["step", "version", "domains"],
    registry=REGISTRY,
)


def record_request(endpoint: str, status: str, duration_s: float) -> None:
    """Record one HTTP request outcome + latency."""
    _requests.labels(endpoint=endpoint, status=status).inc()
    _request_duration.labels(endpoint=endpoint).observe(duration_s)


def record_compute(domain: str, operation: str, status: str, duration_s: float) -> None:
    """Record one deterministic compute invocation."""
    _compute_invocations.labels(domain=domain, status=status).inc()
    _compute_duration.labels(domain=domain).observe(duration_s)
    _domain_operations.labels(domain=domain, operation=operation).inc()


def record_compute_error(domain: str, error: str) -> None:
    """Record a compute failure by error type."""
    _compute_errors.labels(domain=domain, error=error).inc()


def inc_active() -> None:
    _active.inc()


def dec_active() -> None:
    _active.dec()


def set_startup_info(step: str, version: str, domains: str) -> None:
    """Record startup info once at boot."""
    _startup_info.labels(step=step, version=version, domains=domains).set(1.0)
