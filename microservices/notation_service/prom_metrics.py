"""Prometheus metrics for notation-service (D-185).

"Instrumentation before visualization": every resolve/define call is recorded before
any dashboard exists. Independent ``CollectorRegistry`` — never shares the global
REGISTRY (the "never share a CollectorRegistry across microservices" rule).

No high-cardinality labels: ``result`` is a bounded enum and ``symbol`` is bounded by
the registry itself (11 entries), never free student text.

Metrics:
  cogniforge_notation_requests_total            — total HTTP requests {endpoint, status}
  cogniforge_notation_request_duration_seconds  — request latency histogram {endpoint}
  cogniforge_notation_active_connections        — in-flight requests gauge
  cogniforge_notation_resolutions_total         — resolve calls {result}
  cogniforge_notation_definitions_total         — define calls {result}
  cogniforge_notation_symbol_hits_total         — per-symbol resolution hits {symbol}
  cogniforge_notation_unknown_total             — questions that matched no symbol
  cogniforge_notation_startup_info              — startup info {step, version, registry_version}
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

REGISTRY = CollectorRegistry()

_requests = Counter(
    "cogniforge_notation_requests_total",
    "Total notation-service HTTP requests",
    ["endpoint", "status"],
    registry=REGISTRY,
)

_request_duration = Histogram(
    "cogniforge_notation_request_duration_seconds",
    "notation-service request latency (seconds)",
    ["endpoint"],
    registry=REGISTRY,
)

_active = Gauge(
    "cogniforge_notation_active_connections",
    "In-flight notation-service requests",
    registry=REGISTRY,
)

_resolutions = Counter(
    "cogniforge_notation_resolutions_total",
    "Free-text symbol resolutions",
    ["result"],
    registry=REGISTRY,
)

_definitions = Counter(
    "cogniforge_notation_definitions_total",
    "Direct symbol definition lookups",
    ["result"],
    registry=REGISTRY,
)

_symbol_hits = Counter(
    "cogniforge_notation_symbol_hits_total",
    "Resolutions per symbol (bounded by the registry)",
    ["symbol"],
    registry=REGISTRY,
)

_unknown = Counter(
    "cogniforge_notation_unknown_total",
    "Definitional questions that matched no known symbol",
    registry=REGISTRY,
)

_startup_info = Gauge(
    "cogniforge_notation_startup_info",
    "notation-service startup info",
    ["step", "version", "registry_version", "symbols"],
    registry=REGISTRY,
)


def record_request(endpoint: str, status: str, duration_seconds: float) -> None:
    """يسجّل طلب HTTP واحداً: عدّاد الحالة + مدرّج الزمن."""
    _requests.labels(endpoint=endpoint, status=status).inc()
    _request_duration.labels(endpoint=endpoint).observe(duration_seconds)


def record_resolution(symbol: str | None) -> None:
    """يسجّل محاولة تحويل نصّ حرّ إلى رمز — hit مع اسم الرمز، أو miss."""
    if symbol is None:
        _resolutions.labels(result="miss").inc()
        _unknown.inc()
        return
    _resolutions.labels(result="hit").inc()
    _symbol_hits.labels(symbol=symbol).inc()


def record_definition(found: bool) -> None:
    """يسجّل استعلام تعريف رمزٍ بعينه."""
    _definitions.labels(result="hit" if found else "miss").inc()


def inc_active() -> None:
    """يرفع عدّاد الطلبات الجارية."""
    _active.inc()


def dec_active() -> None:
    """يخفض عدّاد الطلبات الجارية."""
    _active.dec()


def set_startup_info(*, step: str, version: str, registry_version: str, symbols: int) -> None:
    """يثبّت معلومات الإقلاع — دليل runtime على أي سجلّ يخدم الطلبات."""
    _startup_info.labels(
        step=step,
        version=version,
        registry_version=registry_version,
        symbols=str(symbols),
    ).set(1)
