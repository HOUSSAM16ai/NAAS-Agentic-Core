"""
مقاييس Prometheus لخدمة المنسق (Orchestrator Service).

تُعرِّف هذه الوحدة جميع counters و gauges و histograms الخاصة بـ orchestrator-service.
تُنشأ مرة واحدة على مستوى الـ module (singleton) وتُستخدم من أي مكان في الخدمة.

المقاييس المُعرَّفة:
  - cogniforge_orchestrator_requests_total       — إجمالي الطلبات (counter)
  - cogniforge_orchestrator_request_duration_seconds — زمن الاستجابة (histogram)
  - cogniforge_orchestrator_active_connections   — الاتصالات النشطة (gauge)
  - cogniforge_outbox_relay_cycles_total         — دورات relay (counter)
  - cogniforge_outbox_relay_processed_total      — سجلات relay مُعالَجة (counter)
  - cogniforge_outbox_relay_failed_total         — سجلات relay فاشلة (counter)
  - cogniforge_outbox_relay_skipped_total        — سجلات relay متجاوزة (counter)
  - cogniforge_outbox_pending_gauge              — سجلات outbox معلقة (gauge)
  - cogniforge_stategraph_invocations_total      — استدعاءات StateGraph (counter)
  - cogniforge_stategraph_duration_seconds       — زمن StateGraph (histogram)
  - cogniforge_stategraph_errors_total           — أخطاء StateGraph (counter)
  - cogniforge_orchestrator_startup_info         — معلومات الإقلاع (gauge)
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ── استيراد prometheus_client بشكل دفاعي ────────────────────────────────────
# prometheus_client غير مثبّت في بيئات الاختبار الخفيفة.
# نستخدم stub بسيط لتجنب ImportError بدل تعطيل الخدمة.
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

    # ── Stub classes لتجنب NameError في بقية الكود ──────────────────────────
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"

    class _Stub:  # type: ignore[no-redef]
        def __init__(self, *a: object, **kw: object) -> None: ...
        def labels(self, **kw: object) -> _Stub: return self
        def inc(self, v: float = 1) -> None: ...
        def set(self, v: float) -> None: ...
        def observe(self, v: float) -> None: ...
        def time(self) -> _Stub: return self
        def __enter__(self) -> _Stub: return self
        def __exit__(self, *a: object) -> None: ...

    Counter = Gauge = Histogram = _Stub  # type: ignore[misc,assignment]

    class CollectorRegistry:  # type: ignore[no-redef]
        pass

    def generate_latest(registry: object = None) -> bytes:  # type: ignore[misc]
        return b"# prometheus_client not installed\n"


# ── Registry مستقل لتجنب التعارض مع المونوليث ──────────────────────────────
# نستخدم registry منفصل بدل REGISTRY الافتراضي لأن المونوليث قد يعمل
# في نفس process في بيئات الاختبار.
_REGISTRY: CollectorRegistry | None = None


def _get_registry() -> CollectorRegistry:
    """يُعيد registry مستقل — يُنشأ مرة واحدة (lazy singleton)."""
    global _REGISTRY
    if _REGISTRY is None and _PROMETHEUS_AVAILABLE:
        _REGISTRY = CollectorRegistry()
    return _REGISTRY  # type: ignore[return-value]


def _make_counter(name: str, doc: str, labels: list[str] | None = None) -> Counter:
    """ينشئ Counter مع registry مستقل."""
    if not _PROMETHEUS_AVAILABLE:
        return Counter()  # type: ignore[call-arg]
    return Counter(name, doc, labels or [], registry=_get_registry())


def _make_gauge(name: str, doc: str, labels: list[str] | None = None) -> Gauge:
    """ينشئ Gauge مع registry مستقل."""
    if not _PROMETHEUS_AVAILABLE:
        return Gauge()  # type: ignore[call-arg]
    return Gauge(name, doc, labels or [], registry=_get_registry())


def _make_histogram(
    name: str,
    doc: str,
    labels: list[str] | None = None,
    buckets: list[float] | None = None,
) -> Histogram:
    """ينشئ Histogram مع registry مستقل."""
    if not _PROMETHEUS_AVAILABLE:
        return Histogram()  # type: ignore[call-arg]
    kwargs: dict[str, object] = {"registry": _get_registry()}
    if buckets:
        kwargs["buckets"] = buckets
    return Histogram(name, doc, labels or [], **kwargs)  # type: ignore[arg-type]


# ═══════════════════════════════════════════════════════════════════════════
# HTTP / General
# ═══════════════════════════════════════════════════════════════════════════

REQUESTS_TOTAL: Counter = _make_counter(
    "cogniforge_orchestrator_requests_total",
    "إجمالي طلبات HTTP الواردة إلى orchestrator-service",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION: Histogram = _make_histogram(
    "cogniforge_orchestrator_request_duration_seconds",
    "زمن معالجة طلبات HTTP في orchestrator-service",
    ["method", "endpoint"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

ACTIVE_CONNECTIONS: Gauge = _make_gauge(
    "cogniforge_orchestrator_active_connections",
    "عدد اتصالات WebSocket النشطة حالياً",
    ["connection_type"],
)

# ═══════════════════════════════════════════════════════════════════════════
# Outbox Relay — المقاييس الجوهرية للخطوة 4
# ═══════════════════════════════════════════════════════════════════════════

OUTBOX_RELAY_CYCLES: Counter = _make_counter(
    "cogniforge_outbox_relay_cycles_total",
    "إجمالي دورات outbox relay منذ بدء الخدمة",
    ["result"],  # success | error
)

OUTBOX_RELAY_PROCESSED: Counter = _make_counter(
    "cogniforge_outbox_relay_processed_total",
    "إجمالي سجلات outbox التي جرى relay لها بنجاح",
)

OUTBOX_RELAY_FAILED: Counter = _make_counter(
    "cogniforge_outbox_relay_failed_total",
    "إجمالي سجلات outbox التي فشل relay لها (تجاوزت max_failed_attempts)",
)

OUTBOX_RELAY_SKIPPED: Counter = _make_counter(
    "cogniforge_outbox_relay_skipped_total",
    "إجمالي سجلات outbox التي تجاوزها relay (processing_inflight أو max_attempts)",
    ["reason"],  # max_failed_attempts | processing_inflight
)

OUTBOX_PENDING: Gauge = _make_gauge(
    "cogniforge_outbox_pending_gauge",
    "عدد سجلات outbox في حالة pending أو processing حالياً",
)

# ═══════════════════════════════════════════════════════════════════════════
# StateGraph — مقاييس الـ 13-node graph
# ═══════════════════════════════════════════════════════════════════════════

STATEGRAPH_INVOCATIONS: Counter = _make_counter(
    "cogniforge_stategraph_invocations_total",
    "إجمالي استدعاءات StateGraph (13-node) منذ بدء الخدمة",
    ["entry_point", "result"],  # entry_point: chat|admin|mission | result: success|error
)

STATEGRAPH_DURATION: Histogram = _make_histogram(
    "cogniforge_stategraph_duration_seconds",
    "زمن تنفيذ StateGraph من الاستدعاء حتى الاستجابة الأولى",
    ["entry_point"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

STATEGRAPH_ERRORS: Counter = _make_counter(
    "cogniforge_stategraph_errors_total",
    "إجمالي أخطاء StateGraph مصنَّفة حسب النوع",
    ["error_type"],  # timeout | llm_error | db_error | unknown
)

# ═══════════════════════════════════════════════════════════════════════════
# Skills Pipeline — مقاييس الـ Composition Engine (Step 9)
# ═══════════════════════════════════════════════════════════════════════════

PIPELINE_INVOCATIONS: Counter = _make_counter(
    "cogniforge_pipeline_invocations_total",
    "إجمالي استدعاءات Skills Pipeline منذ بدء الخدمة",
    ["mode"],  # full | partial | fallback
)

PIPELINE_DURATION: Histogram = _make_histogram(
    "cogniforge_pipeline_duration_seconds",
    "زمن تنفيذ Skills Pipeline الكامل (planning + research + reasoning)",
    ["mode"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

PIPELINE_SKILL_CALLS: Counter = _make_counter(
    "cogniforge_pipeline_skill_calls_total",
    "إجمالي استدعاءات كل Skill من الـ Pipeline",
    ["skill", "status"],  # skill: planning|research|reasoning | status: success|fallback|error
)

PIPELINE_SKILL_DURATION: Histogram = _make_histogram(
    "cogniforge_pipeline_skill_duration_seconds",
    "زمن استجابة كل Skill في الـ Pipeline",
    ["skill"],
    buckets=[0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

PIPELINE_ERRORS: Counter = _make_counter(
    "cogniforge_pipeline_errors_total",
    "إجمالي أخطاء Skills Pipeline مصنَّفة حسب النوع",
    ["error_type"],  # skill_unreachable | skill_timeout | skill_http_error | compose_error
)

PIPELINE_ACTIVE: Gauge = _make_gauge(
    "cogniforge_pipeline_active_gauge",
    "عدد طلبات Skills Pipeline النشطة حالياً",
)

# ═══════════════════════════════════════════════════════════════════════════
# Startup Info
# ═══════════════════════════════════════════════════════════════════════════

STARTUP_INFO: Gauge = _make_gauge(
    "cogniforge_orchestrator_startup_info",
    "معلومات إقلاع orchestrator-service (قيمة 1 دائماً — الـ labels تحمل البيانات)",
    ["version", "environment", "outbox_relay_enabled", "graph_ready", "pipeline_enabled"],
)


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def export_prometheus_text() -> tuple[bytes, str]:
    """
    يُصدِّر جميع المقاييس بصيغة Prometheus text format.

    يُعيد: (body_bytes, content_type)
    """
    if not _PROMETHEUS_AVAILABLE or _REGISTRY is None:
        return b"# prometheus_client not available\n", "text/plain"
    return generate_latest(_REGISTRY), CONTENT_TYPE_LATEST


def record_outbox_relay_cycle(summary: dict[str, int]) -> None:
    """
    يُسجِّل نتائج دورة outbox relay واحدة في Prometheus.

    يُستدعى من _outbox_relay_loop في main.py بعد كل دورة ناجحة.
    """
    processed = summary.get("processed", 0)
    failed = summary.get("failed", 0)
    skipped_max = summary.get("skipped_max_attempts", 0)
    skipped_inflight = summary.get("skipped_inflight", 0)

    OUTBOX_RELAY_CYCLES.labels(result="success").inc()
    if processed:
        OUTBOX_RELAY_PROCESSED.inc(processed)
    if failed:
        OUTBOX_RELAY_FAILED.inc(failed)
    if skipped_max:
        OUTBOX_RELAY_SKIPPED.labels(reason="max_failed_attempts").inc(skipped_max)
    if skipped_inflight:
        OUTBOX_RELAY_SKIPPED.labels(reason="processing_inflight").inc(skipped_inflight)


def record_outbox_relay_error() -> None:
    """يُسجِّل فشل دورة relay."""
    OUTBOX_RELAY_CYCLES.labels(result="error").inc()


def record_pipeline_invocation(
    mode: str,
    duration_seconds: float,
    skill_results: list[tuple[str, str, float]],
) -> None:
    """
    يُسجِّل نتيجة استدعاء Skills Pipeline في Prometheus.

    المدخلات:
        mode: "full" | "partial" | "fallback"
        duration_seconds: الزمن الكلي للـ Pipeline
        skill_results: قائمة من (skill_name, status, duration_seconds)
    """
    PIPELINE_INVOCATIONS.labels(mode=mode).inc()
    PIPELINE_DURATION.labels(mode=mode).observe(duration_seconds)

    for skill, status, skill_duration in skill_results:
        PIPELINE_SKILL_CALLS.labels(skill=skill, status=status).inc()
        PIPELINE_SKILL_DURATION.labels(skill=skill).observe(skill_duration)


def record_pipeline_error(error_type: str) -> None:
    """يُسجِّل خطأ في Skills Pipeline."""
    PIPELINE_ERRORS.labels(error_type=error_type).inc()


def set_pipeline_active(count: int) -> None:
    """يُحدِّث عداد الطلبات النشطة في الـ Pipeline."""
    PIPELINE_ACTIVE.set(count)


def set_startup_info(
    version: str,
    environment: str,
    outbox_relay_enabled: bool,
    graph_ready: bool,
    pipeline_enabled: bool = True,
) -> None:
    """يُسجِّل معلومات الإقلاع كـ gauge بقيمة 1."""
    STARTUP_INFO.labels(
        version=version,
        environment=environment,
        outbox_relay_enabled=str(outbox_relay_enabled).lower(),
        graph_ready=str(graph_ready).lower(),
        pipeline_enabled=str(pipeline_enabled).lower(),
    ).set(1)
