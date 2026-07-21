"""Prometheus metrics for memory-agent (D-174 — observability parity).

Independent ``CollectorRegistry`` (never the default REGISTRY). Defensive import:
if ``prometheus_client`` is missing the module still imports via silent stubs.

Exported metrics (7 × ``cogniforge_memory_*``):
  cogniforge_memory_requests_total
  cogniforge_memory_request_duration_seconds
  cogniforge_memory_active_connections
  cogniforge_memory_created_total
  cogniforge_memory_searches_total
  cogniforge_memory_errors_total
  cogniforge_memory_startup_info
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

        def set(self, value: float) -> None:
            pass

        def observe(self, value: float) -> None:
            pass

    CollectorRegistry = _Stub  # type: ignore[misc]
    Counter = Histogram = Gauge = _Stub  # type: ignore[misc]
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest(registry=None) -> bytes:  # type: ignore[misc]
        return b""


_REGISTRY = CollectorRegistry()

_http_requests = Counter(
    "cogniforge_memory_requests_total",
    "Total HTTP requests handled by memory-agent",
    ["method", "endpoint", "status_code"],
    registry=_REGISTRY,
)
_http_duration = Histogram(
    "cogniforge_memory_request_duration_seconds",
    "memory-agent HTTP response time in seconds",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=_REGISTRY,
)
_active_connections = Gauge(
    "cogniforge_memory_active_connections",
    "Current active connections in memory-agent",
    registry=_REGISTRY,
)
_created = Counter(
    "cogniforge_memory_created_total",
    "Total memory nodes created, labelled by status",
    ["status"],
    registry=_REGISTRY,
)
_searches = Counter(
    "cogniforge_memory_searches_total",
    "Total memory searches, labelled by status",
    ["status"],
    registry=_REGISTRY,
)
_errors = Counter(
    "cogniforge_memory_errors_total",
    "Total memory-agent errors, labelled by operation and error type",
    ["operation", "error_type"],
    registry=_REGISTRY,
)
_startup_info = Gauge(
    "cogniforge_memory_startup_info",
    "memory-agent startup info — always 1.0 when up",
    ["version", "environment"],
    registry=_REGISTRY,
)


def export_prometheus_text() -> tuple[bytes, str]:
    """Return (metrics payload, content type) for the /metrics endpoint."""
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST


def set_startup_info(version: str = "1.0.0", environment: str = "development") -> None:
    """Record startup info as a gauge with value 1.0."""
    _startup_info.labels(version=version, environment=environment).set(1.0)


def record_http_request(
    method: str, endpoint: str, status_code: int, duration_seconds: float
) -> None:
    """Record one HTTP request with its latency."""
    _http_requests.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    _http_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)


def record_memory_created(status: str = "success") -> None:
    """Record a memory-node creation by status."""
    _created.labels(status=status).inc()


def record_memory_search(status: str = "success") -> None:
    """Record a memory search by status."""
    _searches.labels(status=status).inc()


def record_error(operation: str, error_type: str = "unknown") -> None:
    """Record a memory-agent error by operation and type."""
    _errors.labels(operation=operation, error_type=error_type).inc()
