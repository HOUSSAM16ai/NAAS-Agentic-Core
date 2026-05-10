"""
مقاييس Prometheus لوكيل التخطيط (Planning Agent).

سجل مستقل تماماً — لا يشارك الـ default REGISTRY مع المونوليث أو أي خدمة أخرى.
يُصدِّر النص عبر export_prometheus_text() → /metrics endpoint.

المقاييس (11 مقياساً):
  cogniforge_planning_requests_total          — إجمالي الطلبات HTTP
  cogniforge_planning_request_duration_seconds — زمن الاستجابة (histogram)
  cogniforge_planning_active_connections       — الاتصالات النشطة (gauge)
  cogniforge_planning_plans_total             — الخطط المُنشأة (counter)
  cogniforge_planning_plan_duration_seconds   — زمن توليد الخطة (histogram)
  cogniforge_planning_dspy_invocations_total  — استدعاءات DSPy (counter)
  cogniforge_planning_dspy_errors_total       — أخطاء DSPy (counter)
  cogniforge_planning_fallback_plans_total    — الخطط الاحتياطية (counter)
  cogniforge_planning_db_operations_total     — عمليات قاعدة البيانات (counter)
  cogniforge_planning_db_duration_seconds     — زمن عمليات DB (histogram)
  cogniforge_planning_startup_info            — معلومات الإقلاع (info gauge)
"""

from __future__ import annotations

import time

# ── استيراد دفاعي — stub classes عند غياب prometheus_client ──────────────────
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

    class CollectorRegistry:  # type: ignore[no-redef]
        """Stub عند غياب prometheus_client."""

    class Counter:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def labels(self, **kw): return self
        def inc(self, n=1): pass

    class Gauge:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def labels(self, **kw): return self
        def set(self, v): pass
        def inc(self, n=1): pass
        def dec(self, n=1): pass

    class Histogram:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def labels(self, **kw): return self
        def observe(self, v): pass

    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest(registry=None) -> bytes:  # type: ignore[misc]
        return b"# prometheus_client not installed\n"


# ── السجل المستقل ─────────────────────────────────────────────────────────────
PLANNING_REGISTRY = CollectorRegistry()

# ── تعريف المقاييس ────────────────────────────────────────────────────────────

_requests_total = Counter(
    "cogniforge_planning_requests_total",
    "إجمالي طلبات HTTP الواردة إلى planning-agent",
    ["method", "endpoint", "status_code"],
    registry=PLANNING_REGISTRY,
)

_request_duration = Histogram(
    "cogniforge_planning_request_duration_seconds",
    "زمن معالجة طلبات HTTP في planning-agent",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    registry=PLANNING_REGISTRY,
)

_active_connections = Gauge(
    "cogniforge_planning_active_connections",
    "عدد الاتصالات النشطة الحالية في planning-agent",
    registry=PLANNING_REGISTRY,
)

_plans_total = Counter(
    "cogniforge_planning_plans_total",
    "إجمالي الخطط المُنشأة بواسطة planning-agent",
    ["strategy", "result"],
    registry=PLANNING_REGISTRY,
)

_plan_duration = Histogram(
    "cogniforge_planning_plan_duration_seconds",
    "زمن توليد خطة واحدة (من الطلب حتى الحفظ في DB)",
    ["strategy"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=PLANNING_REGISTRY,
)

_dspy_invocations_total = Counter(
    "cogniforge_planning_dspy_invocations_total",
    "إجمالي استدعاءات DSPy/LangGraph في planning-agent",
    ["result"],
    registry=PLANNING_REGISTRY,
)

_dspy_errors_total = Counter(
    "cogniforge_planning_dspy_errors_total",
    "إجمالي أخطاء DSPy/LangGraph في planning-agent",
    ["error_type"],
    registry=PLANNING_REGISTRY,
)

_fallback_plans_total = Counter(
    "cogniforge_planning_fallback_plans_total",
    "إجمالي الخطط الاحتياطية المُولَّدة (عند فشل DSPy أو غياب API key)",
    ["reason"],
    registry=PLANNING_REGISTRY,
)

_db_operations_total = Counter(
    "cogniforge_planning_db_operations_total",
    "إجمالي عمليات قاعدة البيانات في planning-agent",
    ["operation", "result"],
    registry=PLANNING_REGISTRY,
)

_db_duration = Histogram(
    "cogniforge_planning_db_duration_seconds",
    "زمن عمليات قاعدة البيانات في planning-agent",
    ["operation"],
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0],
    registry=PLANNING_REGISTRY,
)

_startup_info = Gauge(
    "cogniforge_planning_startup_info",
    "معلومات إقلاع planning-agent (step=6)",
    ["version", "environment", "db_backend", "dspy_available", "step"],
    registry=PLANNING_REGISTRY,
)


# ── الدوال العامة ─────────────────────────────────────────────────────────────


def export_prometheus_text() -> tuple[bytes, str]:
    """
    يُصدِّر جميع مقاييس planning-agent بصيغة Prometheus text format.

    الإرجاع: (body_bytes, content_type_str)
    """
    return generate_latest(PLANNING_REGISTRY), CONTENT_TYPE_LATEST


def set_startup_info(
    version: str,
    environment: str,
    db_backend: str,
    dspy_available: bool,
) -> None:
    """
    يُسجِّل معلومات الإقلاع كـ gauge ثابت.
    يُستدعى مرة واحدة في lifespan بعد اكتمال التهيئة.
    """
    _startup_info.labels(
        version=version,
        environment=environment,
        db_backend=db_backend,
        dspy_available=str(dspy_available).lower(),
        step="6",
    ).set(1.0)


def record_http_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """يُسجِّل طلب HTTP واحد مع زمن الاستجابة."""
    _requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    _request_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)


def record_plan_created(
    strategy: str,
    duration_seconds: float,
    is_fallback: bool = False,
    fallback_reason: str = "none",
) -> None:
    """
    يُسجِّل إنشاء خطة واحدة.

    المعاملات:
        strategy: اسم الاستراتيجية (Generated Strategy / Fallback Strategy)
        duration_seconds: زمن التوليد الكامل
        is_fallback: True إذا كانت خطة احتياطية
        fallback_reason: سبب اللجوء للخطة الاحتياطية
    """
    result = "fallback" if is_fallback else "success"
    _plans_total.labels(strategy=strategy, result=result).inc()
    _plan_duration.labels(strategy=strategy).observe(duration_seconds)

    if is_fallback:
        _fallback_plans_total.labels(reason=fallback_reason).inc()


def record_dspy_invocation(success: bool, error_type: str = "none") -> None:
    """يُسجِّل استدعاء DSPy/LangGraph واحد."""
    result = "success" if success else "error"
    _dspy_invocations_total.labels(result=result).inc()
    if not success:
        _dspy_errors_total.labels(error_type=error_type).inc()


def record_db_operation(operation: str, success: bool, duration_seconds: float) -> None:
    """يُسجِّل عملية DB واحدة (insert / select / commit)."""
    result = "success" if success else "error"
    _db_operations_total.labels(operation=operation, result=result).inc()
    _db_duration.labels(operation=operation).observe(duration_seconds)


def set_active_connections(count: int) -> None:
    """يُحدِّث عداد الاتصالات النشطة."""
    _active_connections.set(count)


def get_request_timer() -> float:
    """يُرجع الوقت الحالي كنقطة بداية لقياس المدة."""
    return time.monotonic()


def elapsed_since(start: float) -> float:
    """يحسب المدة المنقضية منذ start بالثواني."""
    return time.monotonic() - start
