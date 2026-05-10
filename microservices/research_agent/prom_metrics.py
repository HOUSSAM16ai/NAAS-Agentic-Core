"""
وحدة مقاييس Prometheus لـ research-agent (الخطوة 7).

تُصدِّر 11 مقياساً مستقلاً عبر CollectorRegistry خاص بها،
لا تتشارك مع REGISTRY الافتراضي لـ prometheus_client.

المقاييس:
  - cogniforge_research_requests_total
  - cogniforge_research_request_duration_seconds
  - cogniforge_research_active_connections
  - cogniforge_research_searches_total
  - cogniforge_research_search_duration_seconds
  - cogniforge_research_tavily_calls_total
  - cogniforge_research_tavily_errors_total
  - cogniforge_research_deep_research_total
  - cogniforge_research_db_operations_total
  - cogniforge_research_db_duration_seconds
  - cogniforge_research_startup_info
"""

from __future__ import annotations

import time

# ── استيراد دفاعي — stub classes عند غياب prometheus_client ─────────────────
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False

    class _Stub:  # type: ignore[no-redef]
        """Stub بسيط يمتص أي استدعاء عند غياب prometheus_client."""

        def __init__(self, *a: object, **kw: object) -> None:
            pass

        def labels(self, **kw: object) -> _Stub:
            return self

        def inc(self, amount: float = 1) -> None:
            pass

        def set(self, value: float) -> None:
            pass

        def observe(self, value: float) -> None:
            pass

        def info(self, val: dict[str, str]) -> None:
            pass

    CollectorRegistry = _Stub  # type: ignore[misc,assignment]
    Counter = _Stub  # type: ignore[misc,assignment]
    Gauge = _Stub  # type: ignore[misc,assignment]
    Histogram = _Stub  # type: ignore[misc,assignment]
    Info = _Stub  # type: ignore[misc,assignment]
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest(registry: object) -> bytes:  # type: ignore[misc]
        return b"# prometheus_client not installed\n"


# ── Registry مستقل — لا يتعارض مع المونوليث أو الخدمات الأخرى ───────────────
_REGISTRY = CollectorRegistry(auto_describe=True)

# ── 1. HTTP Requests ─────────────────────────────────────────────────────────
_http_requests = Counter(
    "cogniforge_research_requests_total",
    "إجمالي طلبات HTTP الواردة إلى research-agent",
    ["method", "endpoint", "status_code"],
    registry=_REGISTRY,
)

_http_duration = Histogram(
    "cogniforge_research_request_duration_seconds",
    "مدة معالجة طلبات HTTP في research-agent (ثانية)",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=_REGISTRY,
)

_active_connections = Gauge(
    "cogniforge_research_active_connections",
    "عدد الاتصالات النشطة الحالية في research-agent",
    registry=_REGISTRY,
)

# ── 2. Search Operations ─────────────────────────────────────────────────────
_searches = Counter(
    "cogniforge_research_searches_total",
    "إجمالي عمليات البحث المُنفَّذة (حسب النوع والنتيجة)",
    ["search_type", "result"],
    registry=_REGISTRY,
)

_search_duration = Histogram(
    "cogniforge_research_search_duration_seconds",
    "مدة تنفيذ عمليات البحث (ثانية)",
    ["search_type"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=_REGISTRY,
)

# ── 3. Tavily Web Search ─────────────────────────────────────────────────────
_tavily_calls = Counter(
    "cogniforge_research_tavily_calls_total",
    "إجمالي استدعاءات Tavily API (حسب النتيجة)",
    ["result"],
    registry=_REGISTRY,
)

_tavily_errors = Counter(
    "cogniforge_research_tavily_errors_total",
    "إجمالي أخطاء Tavily API (حسب نوع الخطأ)",
    ["error_type"],
    registry=_REGISTRY,
)

# ── 4. Deep Research ─────────────────────────────────────────────────────────
_deep_research = Counter(
    "cogniforge_research_deep_research_total",
    "إجمالي عمليات البحث العميق (SuperSearchOrchestrator)",
    ["result"],
    registry=_REGISTRY,
)

# ── 5. Database Operations ───────────────────────────────────────────────────
_db_operations = Counter(
    "cogniforge_research_db_operations_total",
    "إجمالي عمليات قاعدة البيانات في research-agent",
    ["operation", "result"],
    registry=_REGISTRY,
)

_db_duration = Histogram(
    "cogniforge_research_db_duration_seconds",
    "مدة عمليات قاعدة البيانات في research-agent (ثانية)",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=_REGISTRY,
)

# ── 6. Startup Info ──────────────────────────────────────────────────────────
_startup_info = Info(
    "cogniforge_research_startup",
    "معلومات إقلاع research-agent (الإصدار، البيئة، Tavily)",
    registry=_REGISTRY,
)


# ── Public API ────────────────────────────────────────────────────────────────


def export_prometheus_text() -> tuple[bytes, str]:
    """
    يُصدِّر جميع المقاييس بصيغة Prometheus text format.

    العائد:
        (body_bytes, content_type_str)
    """
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST


def set_startup_info(
    version: str,
    environment: str,
    db_backend: str,
    tavily_available: str,
) -> None:
    """
    يُسجِّل معلومات الإقلاع كـ Info metric.

    المعاملات:
        version: إصدار الخدمة
        environment: بيئة التشغيل (development/production)
        db_backend: نوع قاعدة البيانات (postgresql/sqlite)
        tavily_available: هل Tavily API متاح ("true"/"false")
    """
    _startup_info.info(
        {
            "version": version,
            "environment": environment,
            "db_backend": db_backend,
            "tavily_available": tavily_available,
            "step": "7",
        }
    )


def record_http_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """
    يُسجِّل طلب HTTP واحد مع مدته.

    المعاملات:
        method: فعل HTTP (GET/POST/...)
        endpoint: مسار الـ endpoint
        status_code: رمز الاستجابة
        duration_seconds: مدة المعالجة بالثانية
    """
    _http_requests.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    _http_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)


def record_search(
    search_type: str,
    result: str,
    duration_seconds: float,
) -> None:
    """
    يُسجِّل عملية بحث واحدة.

    المعاملات:
        search_type: نوع البحث (db/tavily/deep/rerank/refine)
        result: نتيجة البحث (success/error/empty)
        duration_seconds: مدة البحث بالثانية
    """
    _searches.labels(search_type=search_type, result=result).inc()
    _search_duration.labels(search_type=search_type).observe(duration_seconds)


def record_tavily_call(result: str) -> None:
    """
    يُسجِّل استدعاء Tavily API.

    المعاملات:
        result: نتيجة الاستدعاء (success/error/unavailable)
    """
    _tavily_calls.labels(result=result).inc()


def record_tavily_error(error_type: str) -> None:
    """
    يُسجِّل خطأ Tavily API.

    المعاملات:
        error_type: نوع الخطأ (timeout/rate_limit/api_error/import_error)
    """
    _tavily_errors.labels(error_type=error_type).inc()


def record_deep_research(result: str) -> None:
    """
    يُسجِّل عملية بحث عميق (SuperSearchOrchestrator).

    المعاملات:
        result: نتيجة البحث (success/error)
    """
    _deep_research.labels(result=result).inc()


def record_db_operation(operation: str, result: str, duration_seconds: float) -> None:
    """
    يُسجِّل عملية قاعدة بيانات.

    المعاملات:
        operation: نوع العملية (select/insert/update/delete)
        result: نتيجة العملية (success/error)
        duration_seconds: مدة العملية بالثانية
    """
    _db_operations.labels(operation=operation, result=result).inc()
    _db_duration.labels(operation=operation).observe(duration_seconds)


def set_active_connections(count: int) -> None:
    """
    يُحدِّث عداد الاتصالات النشطة.

    المعاملات:
        count: العدد الحالي للاتصالات
    """
    _active_connections.set(count)


def get_request_timer() -> float:
    """
    يُعيد الوقت الحالي لقياس مدة الطلب.

    العائد:
        الوقت الحالي بالثانية (monotonic)
    """
    return time.monotonic()


def elapsed_since(start: float) -> float:
    """
    يحسب الوقت المنقضي منذ نقطة البداية.

    المعاملات:
        start: وقت البداية من get_request_timer()

    العائد:
        المدة المنقضية بالثانية
    """
    return time.monotonic() - start
