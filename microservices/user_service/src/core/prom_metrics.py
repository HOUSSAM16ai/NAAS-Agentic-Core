"""
مقاييس Prometheus لخدمة المستخدمين (User Service).

تُعرِّف هذه الوحدة جميع counters و gauges و histograms الخاصة بـ user-service.
تُنشأ مرة واحدة على مستوى الـ module (singleton) وتُستخدم من أي مكان في الخدمة.

المقاييس المُعرَّفة:
  - cogniforge_user_requests_total              — إجمالي الطلبات HTTP (counter)
  - cogniforge_user_request_duration_seconds    — زمن الاستجابة (histogram)
  - cogniforge_user_active_connections          — الاتصالات النشطة (gauge)
  - cogniforge_user_auth_operations_total       — عمليات المصادقة (counter)
  - cogniforge_user_auth_duration_seconds       — زمن عمليات المصادقة (histogram)
  - cogniforge_user_registrations_total         — تسجيلات المستخدمين (counter)
  - cogniforge_user_logins_total                — عمليات تسجيل الدخول (counter)
  - cogniforge_user_token_verifications_total   — عمليات التحقق من الرمز (counter)
  - cogniforge_user_db_operations_total         — عمليات قاعدة البيانات (counter)
  - cogniforge_user_db_duration_seconds         — زمن عمليات قاعدة البيانات (histogram)
  - cogniforge_user_startup_info                — معلومات الإقلاع (gauge)

نمط التصميم:
  - Registry مستقل (لا يشارك REGISTRY الافتراضي مع المونوليث أو orchestrator-service)
  - استيراد دفاعي (try/except ImportError) — stub classes عند غياب prometheus_client
  - دوال عامة بسيطة للتسجيل — لا تعتمد على state خارجي
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# ── استيراد prometheus_client بشكل دفاعي ────────────────────────────────────
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
except ImportError:  # pragma: no cover
    _PROMETHEUS_AVAILABLE = False
    logger.warning("prometheus_client غير مثبّت — /metrics سيُعيد نصاً فارغاً")

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    class _Stub:  # type: ignore[no-redef]
        """Stub بسيط يُحاكي واجهة prometheus_client عند غيابه."""

        def __init__(self, *a: object, **kw: object) -> None: ...

        def labels(self, **kw: object) -> "_Stub":
            return self

        def inc(self, v: float = 1) -> None: ...

        def set(self, v: float) -> None: ...

        def observe(self, v: float) -> None: ...

        def time(self) -> "_Stub":
            return self

        def __enter__(self) -> "_Stub":
            return self

        def __exit__(self, *a: object) -> None: ...

    Counter = Gauge = Histogram = _Stub  # type: ignore[misc,assignment]

    class CollectorRegistry:  # type: ignore[no-redef]
        """Stub لـ CollectorRegistry."""

    def generate_latest(registry: object = None) -> bytes:  # type: ignore[misc]
        return b"# prometheus_client not installed\n"


# ── Registry مستقل ──────────────────────────────────────────────────────────
_REGISTRY: CollectorRegistry | None = None


def _get_registry() -> CollectorRegistry:
    """يُعيد registry مستقل — يُنشأ مرة واحدة (lazy singleton)."""
    global _REGISTRY  # noqa: PLW0603 — Singleton: initialised once at startup
    if _REGISTRY is None and _PROMETHEUS_AVAILABLE:
        _REGISTRY = CollectorRegistry()
    return _REGISTRY  # type: ignore[return-value]


# ── تعريف المقاييس (lazy — تُنشأ عند أول استدعاء) ───────────────────────────
_metrics: dict[str, object] = {}


def _get_metrics() -> dict[str, object]:
    """يُعيد قاموس المقاييس — يُنشأ مرة واحدة."""
    global _metrics  # noqa: PLW0603
    if _metrics or not _PROMETHEUS_AVAILABLE:
        return _metrics

    reg = _get_registry()

    _metrics["requests_total"] = Counter(
        "cogniforge_user_requests_total",
        "إجمالي طلبات HTTP لخدمة المستخدمين",
        ["method", "endpoint", "status_code"],
        registry=reg,
    )
    _metrics["request_duration"] = Histogram(
        "cogniforge_user_request_duration_seconds",
        "زمن استجابة طلبات HTTP لخدمة المستخدمين",
        ["method", "endpoint"],
        buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
        registry=reg,
    )
    _metrics["active_connections"] = Gauge(
        "cogniforge_user_active_connections",
        "عدد الاتصالات النشطة الحالية",
        registry=reg,
    )
    _metrics["auth_operations_total"] = Counter(
        "cogniforge_user_auth_operations_total",
        "إجمالي عمليات المصادقة",
        ["operation", "result"],
        registry=reg,
    )
    _metrics["auth_duration"] = Histogram(
        "cogniforge_user_auth_duration_seconds",
        "زمن عمليات المصادقة",
        ["operation"],
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
        registry=reg,
    )
    _metrics["registrations_total"] = Counter(
        "cogniforge_user_registrations_total",
        "إجمالي تسجيلات المستخدمين الجدد",
        ["result"],
        registry=reg,
    )
    _metrics["logins_total"] = Counter(
        "cogniforge_user_logins_total",
        "إجمالي عمليات تسجيل الدخول",
        ["result"],
        registry=reg,
    )
    _metrics["token_verifications_total"] = Counter(
        "cogniforge_user_token_verifications_total",
        "إجمالي عمليات التحقق من رمز JWT",
        ["result"],
        registry=reg,
    )
    _metrics["db_operations_total"] = Counter(
        "cogniforge_user_db_operations_total",
        "إجمالي عمليات قاعدة البيانات",
        ["operation", "result"],
        registry=reg,
    )
    _metrics["db_duration"] = Histogram(
        "cogniforge_user_db_duration_seconds",
        "زمن عمليات قاعدة البيانات",
        ["operation"],
        buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
        registry=reg,
    )
    _metrics["startup_info"] = Gauge(
        "cogniforge_user_startup_info",
        "معلومات إقلاع user-service (1 = نشط)",
        ["version", "environment", "db_backend", "step"],
        registry=reg,
    )

    return _metrics


# ── دوال التسجيل العامة ──────────────────────────────────────────────────────


def record_http_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """يُسجِّل طلب HTTP مكتمل مع زمن الاستجابة."""
    m = _get_metrics()
    if not m:
        return
    m["requests_total"].labels(  # type: ignore[attr-defined]
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    m["request_duration"].labels(  # type: ignore[attr-defined]
        method=method,
        endpoint=endpoint,
    ).observe(duration_seconds)


def record_auth_operation(
    operation: str,
    result: str,
    duration_seconds: float,
) -> None:
    """يُسجِّل عملية مصادقة (register / login / logout / refresh / verify).

    Args:
        operation: نوع العملية (register | login | logout | refresh | verify_token)
        result: نتيجة العملية (success | failure | invalid_credentials | user_exists)
        duration_seconds: زمن تنفيذ العملية بالثواني
    """
    m = _get_metrics()
    if not m:
        return
    m["auth_operations_total"].labels(  # type: ignore[attr-defined]
        operation=operation,
        result=result,
    ).inc()
    m["auth_duration"].labels(operation=operation).observe(duration_seconds)  # type: ignore[attr-defined]

    # مقاييس متخصصة للعمليات الرئيسية
    if operation == "register":
        m["registrations_total"].labels(result=result).inc()  # type: ignore[attr-defined]
    elif operation == "login":
        m["logins_total"].labels(result=result).inc()  # type: ignore[attr-defined]
    elif operation == "verify_token":
        m["token_verifications_total"].labels(result=result).inc()  # type: ignore[attr-defined]


def record_db_operation(
    operation: str,
    result: str,
    duration_seconds: float,
) -> None:
    """يُسجِّل عملية قاعدة بيانات.

    Args:
        operation: نوع العملية (select | insert | update | delete | seed)
        result: نتيجة العملية (success | failure | not_found)
        duration_seconds: زمن تنفيذ العملية بالثواني
    """
    m = _get_metrics()
    if not m:
        return
    m["db_operations_total"].labels(  # type: ignore[attr-defined]
        operation=operation,
        result=result,
    ).inc()
    m["db_duration"].labels(operation=operation).observe(duration_seconds)  # type: ignore[attr-defined]


def set_active_connections(count: int) -> None:
    """يضبط عدد الاتصالات النشطة الحالية."""
    m = _get_metrics()
    if not m:
        return
    m["active_connections"].set(count)  # type: ignore[attr-defined]


def set_startup_info(
    version: str,
    environment: str,
    db_backend: str,
) -> None:
    """يُسجِّل معلومات إقلاع الخدمة — يُستدعى مرة واحدة في lifespan.

    Args:
        version: إصدار الخدمة (مثل "1.0.0")
        environment: بيئة التشغيل (development | staging | production)
        db_backend: نوع قاعدة البيانات (postgresql | sqlite)
    """
    m = _get_metrics()
    if not m:
        return
    m["startup_info"].labels(  # type: ignore[attr-defined]
        version=version,
        environment=environment,
        db_backend=db_backend,
        step="5",
    ).set(1)


def export_prometheus_text() -> tuple[bytes, str]:
    """يُصدِّر جميع المقاييس بصيغة Prometheus text format.

    Returns:
        (content_bytes, content_type) — جاهز للإرسال مباشرة في HTTP response
    """
    if not _PROMETHEUS_AVAILABLE:
        return b"# prometheus_client not installed\n", CONTENT_TYPE_LATEST

    reg = _get_registry()
    _get_metrics()  # تأكد من تهيئة المقاييس
    return generate_latest(reg), CONTENT_TYPE_LATEST


def get_request_timer() -> float:
    """يُعيد timestamp الحالي لقياس زمن الطلب."""
    return time.monotonic()


def elapsed_since(start: float) -> float:
    """يحسب الزمن المنقضي منذ start بالثواني."""
    return time.monotonic() - start
