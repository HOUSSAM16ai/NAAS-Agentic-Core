"""
مقاييس Prometheus لـ conversation-service — الخطوة 12.

كل مقياس له عقد دلالي واضح:
  - cogniforge_conversation_requests_total       ← عدد الطلبات الكلي
  - cogniforge_conversation_request_duration_seconds ← زمن الاستجابة
  - cogniforge_conversation_active_connections   ← اتصالات WebSocket النشطة
  - cogniforge_conversation_messages_total       ← الرسائل المُعالَجة
  - cogniforge_conversation_sessions_total       ← الجلسات المُنشأة
  - cogniforge_conversation_session_duration_seconds ← مدة الجلسة
  - cogniforge_conversation_graph_invocations_total  ← استدعاءات StateGraph
  - cogniforge_conversation_graph_duration_seconds   ← زمن StateGraph
  - cogniforge_conversation_graph_errors_total       ← أخطاء StateGraph
  - cogniforge_conversation_db_operations_total      ← عمليات قاعدة البيانات
  - cogniforge_conversation_startup_info             ← معلومات الإقلاع

قانون: كل مقياس له emitter حقيقي في الكود — لا zombie metrics.
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# ── Registry مستقل — لا يتعارض مع microservices أخرى ─────────────────────────
REGISTRY = CollectorRegistry()

# ── مقاييس الطلبات ────────────────────────────────────────────────────────────
conversation_requests_total = Counter(
    "cogniforge_conversation_requests_total",
    "إجمالي طلبات HTTP لـ conversation-service",
    ["method", "endpoint", "status_code"],
    registry=REGISTRY,
)

conversation_request_duration = Histogram(
    "cogniforge_conversation_request_duration_seconds",
    "زمن معالجة طلبات HTTP",
    ["endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=REGISTRY,
)

# ── مقاييس WebSocket ──────────────────────────────────────────────────────────
conversation_active_connections = Gauge(
    "cogniforge_conversation_active_connections",
    "عدد اتصالات WebSocket النشطة حالياً",
    registry=REGISTRY,
)

conversation_messages_total = Counter(
    "cogniforge_conversation_messages_total",
    "إجمالي الرسائل المُعالَجة عبر WebSocket",
    ["direction", "route"],  # direction: inbound|outbound, route: customer|admin
    registry=REGISTRY,
)

# ── مقاييس الجلسات ────────────────────────────────────────────────────────────
conversation_sessions_total = Counter(
    "cogniforge_conversation_sessions_total",
    "إجمالي جلسات المحادثة المُنشأة",
    ["route", "status"],  # status: opened|closed|error
    registry=REGISTRY,
)

conversation_session_duration = Histogram(
    "cogniforge_conversation_session_duration_seconds",
    "مدة جلسة المحادثة من الفتح حتى الإغلاق",
    ["route"],
    buckets=[1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0],
    registry=REGISTRY,
)

# ── مقاييس LangGraph StateGraph ───────────────────────────────────────────────
conversation_graph_invocations_total = Counter(
    "cogniforge_conversation_graph_invocations_total",
    "إجمالي استدعاءات LangGraph StateGraph",
    ["node", "status"],  # node: supervisor|chat, status: success|error|timeout
    registry=REGISTRY,
)

conversation_graph_duration = Histogram(
    "cogniforge_conversation_graph_duration_seconds",
    "زمن تنفيذ LangGraph StateGraph",
    ["node"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
    registry=REGISTRY,
)

conversation_graph_errors_total = Counter(
    "cogniforge_conversation_graph_errors_total",
    "أخطاء LangGraph StateGraph مُصنَّفة حسب النوع",
    ["error_type"],  # timeout|llm_error|state_error|unknown
    registry=REGISTRY,
)

# ── مقاييس قاعدة البيانات ─────────────────────────────────────────────────────
conversation_db_operations_total = Counter(
    "cogniforge_conversation_db_operations_total",
    "إجمالي عمليات قاعدة البيانات",
    ["operation", "status"],  # operation: import|read|write, status: success|error
    registry=REGISTRY,
)

# ── معلومات الإقلاع ───────────────────────────────────────────────────────────
conversation_startup_info = Gauge(
    "cogniforge_conversation_startup_info",
    "معلومات إقلاع conversation-service — 1.0 = نشط",
    [
        "step",
        "version",
        "graph_ready",
        "db_ready",
        "ws_enabled",
    ],
    registry=REGISTRY,
)


# ── دوال التسجيل ──────────────────────────────────────────────────────────────


def record_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    """يُسجِّل طلب HTTP واحد مع زمنه."""
    conversation_requests_total.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
    ).inc()
    conversation_request_duration.labels(endpoint=endpoint).observe(duration_seconds)


def record_ws_connection(delta: int) -> None:
    """يُحدِّث عداد اتصالات WebSocket النشطة (+1 فتح، -1 إغلاق)."""
    conversation_active_connections.inc(delta)


def record_message(direction: str, route: str) -> None:
    """يُسجِّل رسالة WebSocket واحدة."""
    conversation_messages_total.labels(direction=direction, route=route).inc()


def record_session(route: str, status: str, duration_seconds: float | None = None) -> None:
    """يُسجِّل جلسة محادثة مع حالتها ومدتها الاختيارية."""
    conversation_sessions_total.labels(route=route, status=status).inc()
    if duration_seconds is not None:
        conversation_session_duration.labels(route=route).observe(duration_seconds)


def record_graph_invocation(node: str, status: str, duration_seconds: float) -> None:
    """يُسجِّل استدعاء LangGraph node واحد."""
    conversation_graph_invocations_total.labels(node=node, status=status).inc()
    conversation_graph_duration.labels(node=node).observe(duration_seconds)


def record_graph_error(error_type: str) -> None:
    """يُسجِّل خطأ LangGraph مُصنَّفاً."""
    conversation_graph_errors_total.labels(error_type=error_type).inc()


def record_db_operation(operation: str, status: str) -> None:
    """يُسجِّل عملية قاعدة بيانات واحدة."""
    conversation_db_operations_total.labels(operation=operation, status=status).inc()


def set_startup_info(
    step: str,
    version: str,
    graph_ready: bool,
    db_ready: bool,
    ws_enabled: bool,
) -> None:
    """يُسجِّل معلومات الإقلاع — يُستدعى مرة واحدة في lifespan."""
    conversation_startup_info.labels(
        step=step,
        version=version,
        graph_ready=str(graph_ready).lower(),
        db_ready=str(db_ready).lower(),
        ws_enabled=str(ws_enabled).lower(),
    ).set(1.0)


def get_metrics_output() -> bytes:
    """يُعيد مخرجات Prometheus بصيغة text/plain."""
    return generate_latest(REGISTRY)
