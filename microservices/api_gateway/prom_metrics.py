"""Prometheus metrics for api-gateway (D-174 — observability parity).

Independent ``CollectorRegistry`` (never the default REGISTRY — avoids
``Duplicated timeseries`` when several services run in one process/tests).
Defensive import: if ``prometheus_client`` is missing the module still imports
via silent stubs, so wiring ``/metrics`` never breaks startup.

Exported metrics (7 × ``cogniforge_gateway_*``):
  cogniforge_gateway_requests_total
  cogniforge_gateway_request_duration_seconds
  cogniforge_gateway_active_connections
  cogniforge_gateway_proxy_forwards_total
  cogniforge_gateway_proxy_errors_total
  cogniforge_gateway_ws_sessions_total
  cogniforge_gateway_startup_info
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
    "cogniforge_gateway_requests_total",
    "Total HTTP requests handled by api-gateway",
    ["method", "endpoint", "status_code"],
    registry=_REGISTRY,
)
_http_duration = Histogram(
    "cogniforge_gateway_request_duration_seconds",
    "api-gateway HTTP response time in seconds",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=_REGISTRY,
)
_active_connections = Gauge(
    "cogniforge_gateway_active_connections",
    "Current active connections in api-gateway",
    registry=_REGISTRY,
)
_proxy_forwards = Counter(
    "cogniforge_gateway_proxy_forwards_total",
    "Total requests proxied downstream, labelled by target service",
    ["target"],
    registry=_REGISTRY,
)
_proxy_errors = Counter(
    "cogniforge_gateway_proxy_errors_total",
    "Total proxy errors, labelled by error type",
    ["error_type"],
    registry=_REGISTRY,
)
_ws_sessions = Counter(
    "cogniforge_gateway_ws_sessions_total",
    "Total WebSocket sessions accepted, labelled by route id",
    ["route_id"],
    registry=_REGISTRY,
)
_startup_info = Gauge(
    "cogniforge_gateway_startup_info",
    "api-gateway startup info — always 1.0 when up",
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


def record_proxy_forward(target: str) -> None:
    """Record a request proxied to a downstream service."""
    _proxy_forwards.labels(target=target).inc()


def record_proxy_error(error_type: str = "unknown") -> None:
    """Record a proxy error by type."""
    _proxy_errors.labels(error_type=error_type).inc()


def record_ws_session(route_id: str) -> None:
    """Record an accepted WebSocket session."""
    _ws_sessions.labels(route_id=route_id).inc()
