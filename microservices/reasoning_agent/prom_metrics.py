"""
وحدة مقاييس Prometheus لـ reasoning-agent (الخطوة 8).

تستخدم CollectorRegistry مستقلاً لتجنب التعارض مع REGISTRY الافتراضي
عند تشغيل خدمات متعددة في نفس العملية أو في الاختبارات.

المقاييس المُصدَّرة (11 مقياساً):
  cogniforge_reasoning_requests_total
  cogniforge_reasoning_request_duration_seconds
  cogniforge_reasoning_active_connections
  cogniforge_reasoning_invocations_total
  cogniforge_reasoning_invocation_duration_seconds
  cogniforge_reasoning_mcts_expansions_total
  cogniforge_reasoning_mcts_errors_total
  cogniforge_reasoning_llm_calls_total
  cogniforge_reasoning_llm_errors_total
  cogniforge_reasoning_fallback_responses_total
  cogniforge_reasoning_startup_info
"""

from __future__ import annotations

import time

# ── استيراد دفاعي: stub classes عند غياب prometheus_client ──────────────────
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
        """Stub صامت عند غياب prometheus_client."""

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

        def info(self, val: dict) -> None:
            pass

        def time(self):
            import contextlib
            return contextlib.nullcontext()

    CollectorRegistry = _Stub  # type: ignore[misc]
    Counter = Histogram = Gauge = Info = _Stub  # type: ignore[misc]
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    def generate_latest(registry=None) -> bytes:  # type: ignore[misc]
        return b""


# ── Registry مستقل ───────────────────────────────────────────────────────────
_REGISTRY = CollectorRegistry()

# ── 1. HTTP traffic ──────────────────────────────────────────────────────────
_http_requests = Counter(
    "cogniforge_reasoning_requests_total",
    "إجمالي طلبات HTTP الواردة إلى reasoning-agent مُصنَّفة حسب المسار والطريقة والحالة",
    ["method", "endpoint", "status_code"],
    registry=_REGISTRY,
)

_http_duration = Histogram(
    "cogniforge_reasoning_request_duration_seconds",
    "زمن استجابة HTTP لـ reasoning-agent بالثواني",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=_REGISTRY,
)

_active_connections = Gauge(
    "cogniforge_reasoning_active_connections",
    "عدد الاتصالات النشطة الحالية في reasoning-agent",
    registry=_REGISTRY,
)

# ── 2. Reasoning invocations ─────────────────────────────────────────────────
_invocations = Counter(
    "cogniforge_reasoning_invocations_total",
    "إجمالي استدعاءات سير عمل التفكير مُصنَّفة حسب الإجراء والنتيجة",
    ["action", "status"],
    registry=_REGISTRY,
)

_invocation_duration = Histogram(
    "cogniforge_reasoning_invocation_duration_seconds",
    "زمن تنفيذ سير عمل التفكير الكامل بالثواني",
    ["action"],
    buckets=[0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
    registry=_REGISTRY,
)

# ── 3. MCTS strategy ─────────────────────────────────────────────────────────
_mcts_expansions = Counter(
    "cogniforge_reasoning_mcts_expansions_total",
    "إجمالي توسعات شجرة MCTS في استراتيجية التفكير",
    ["depth"],
    registry=_REGISTRY,
)

_mcts_errors = Counter(
    "cogniforge_reasoning_mcts_errors_total",
    "إجمالي أخطاء MCTS مُصنَّفة حسب نوع الخطأ",
    ["error_type"],
    registry=_REGISTRY,
)

# ── 4. LLM calls ─────────────────────────────────────────────────────────────
_llm_calls = Counter(
    "cogniforge_reasoning_llm_calls_total",
    "إجمالي استدعاءات نموذج اللغة مُصنَّفة حسب النموذج والنتيجة",
    ["model", "status"],
    registry=_REGISTRY,
)

_llm_errors = Counter(
    "cogniforge_reasoning_llm_errors_total",
    "إجمالي أخطاء نموذج اللغة مُصنَّفة حسب نوع الخطأ",
    ["error_type"],
    registry=_REGISTRY,
)

# ── 5. Fallback ──────────────────────────────────────────────────────────────
_fallback_responses = Counter(
    "cogniforge_reasoning_fallback_responses_total",
    "إجمالي الاستجابات الاحتياطية عند غياب مفتاح API أو فشل النموذج",
    ["reason"],
    registry=_REGISTRY,
)

# ── 6. Startup info ──────────────────────────────────────────────────────────
_startup_info = Gauge(
    "cogniforge_reasoning_startup_info",
    "معلومات إقلاع reasoning-agent — القيمة دائماً 1.0 عند التشغيل الناجح",
    ["version", "environment", "step", "llm_backend", "mcts_enabled"],
    registry=_REGISTRY,
)


# ── واجهات عامة ──────────────────────────────────────────────────────────────

def export_prometheus_text() -> tuple[bytes, str]:
    """
    يُصدِّر جميع المقاييس بصيغة Prometheus text format.

    العائد:
        tuple[bytes, str]: (المحتوى المُشفَّر, نوع المحتوى)
    """
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST


def set_startup_info(
    version: str = "1.0.0",
    environment: str = "development",
    llm_backend: str = "openrouter",
    mcts_enabled: str = "true",
) -> None:
    """
    يُسجِّل معلومات الإقلاع كـ Gauge بقيمة 1.0.

    المعاملات:
        version: إصدار الخدمة
        environment: بيئة التشغيل (development/production)
        llm_backend: خلفية نموذج اللغة (openrouter/openai/mock)
        mcts_enabled: هل MCTS مُفعَّل (true/false)
    """
    _startup_info.labels(
        version=version,
        environment=environment,
        step="8",
        llm_backend=llm_backend,
        mcts_enabled=mcts_enabled,
    ).set(1.0)


def record_http_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """
    يُسجِّل طلب HTTP واحد مع زمن الاستجابة.

    المعاملات:
        method: طريقة HTTP (GET/POST/...)
        endpoint: مسار الـ endpoint
        status_code: رمز الحالة HTTP
        duration_seconds: زمن المعالجة بالثواني
    """
    _http_requests.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    _http_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)


def record_reasoning_invocation(
    action: str,
    status: str,
    duration_seconds: float,
) -> None:
    """
    يُسجِّل استدعاء سير عمل التفكير مع نتيجته وزمنه.

    المعاملات:
        action: نوع الإجراء (reason/solve_deeply/...)
        status: نتيجة التنفيذ (success/error/fallback)
        duration_seconds: زمن التنفيذ الكامل بالثواني
    """
    _invocations.labels(action=action, status=status).inc()
    _invocation_duration.labels(action=action).observe(duration_seconds)


def record_mcts_expansion(depth: int = 0) -> None:
    """
    يُسجِّل توسعة واحدة في شجرة MCTS.

    المعاملات:
        depth: عمق التوسعة في الشجرة
    """
    _mcts_expansions.labels(depth=str(depth)).inc()


def record_mcts_error(error_type: str = "unknown") -> None:
    """
    يُسجِّل خطأ في استراتيجية MCTS.

    المعاملات:
        error_type: نوع الخطأ (timeout/llm_error/parse_error/unknown)
    """
    _mcts_errors.labels(error_type=error_type).inc()


def record_llm_call(model: str, status: str = "success") -> None:
    """
    يُسجِّل استدعاء نموذج اللغة.

    المعاملات:
        model: اسم النموذج المستخدم
        status: نتيجة الاستدعاء (success/error/retry)
    """
    _llm_calls.labels(model=model, status=status).inc()


def record_llm_error(error_type: str = "unknown") -> None:
    """
    يُسجِّل خطأ في استدعاء نموذج اللغة.

    المعاملات:
        error_type: نوع الخطأ (rate_limit/timeout/auth/unknown)
    """
    _llm_errors.labels(error_type=error_type).inc()


def record_fallback_response(reason: str = "no_api_key") -> None:
    """
    يُسجِّل استجابة احتياطية عند تعذُّر استدعاء النموذج.

    المعاملات:
        reason: سبب الاستجابة الاحتياطية (no_api_key/llm_error/timeout)
    """
    _fallback_responses.labels(reason=reason).inc()


def set_active_connections(count: int) -> None:
    """
    يُحدِّث عداد الاتصالات النشطة.

    المعاملات:
        count: العدد الحالي للاتصالات النشطة
    """
    _active_connections.set(float(count))


def get_request_timer(method: str, endpoint: str):
    """
    يُعيد context manager لقياس زمن الطلب تلقائياً.

    المعاملات:
        method: طريقة HTTP
        endpoint: مسار الـ endpoint

    العائد:
        Histogram timer context manager
    """
    return _http_duration.labels(method=method, endpoint=endpoint).time()


def elapsed_since(start: float) -> float:
    """
    يحسب الزمن المنقضي منذ نقطة البداية.

    المعاملات:
        start: وقت البداية من time.monotonic()

    العائد:
        float: الزمن المنقضي بالثواني
    """
    return time.monotonic() - start
