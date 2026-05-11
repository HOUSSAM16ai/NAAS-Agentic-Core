"""
مقاييس Prometheus لـ content-retrieval-skill — الخطوة 11.

مبدأ "Instrumentation before visualization":
  كل استدعاء للـ Skill مُسجَّل قبل أي dashboard.

المقاييس:
  cogniforge_retrieval_requests_total       — إجمالي الطلبات {status, intent}
  cogniforge_retrieval_duration_seconds     — زمن الاستجابة histogram
  cogniforge_retrieval_intent_total         — توزيع النوايا {intent}
  cogniforge_retrieval_hits_total           — عدد النتائج الناجحة
  cogniforge_retrieval_misses_total         — عدد الطلبات بدون نتائج
  cogniforge_retrieval_knowledge_base_size  — حجم قاعدة المعرفة (عدد الملفات)
  cogniforge_retrieval_startup_info         — معلومات الإقلاع {step, version}
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)

# Registry مستقل — لا يتعارض مع microservices أخرى
REGISTRY = CollectorRegistry()

_requests = Counter(
    "cogniforge_retrieval_requests_total",
    "إجمالي طلبات content-retrieval-skill",
    ["status", "intent"],
    registry=REGISTRY,
)

_duration = Histogram(
    "cogniforge_retrieval_duration_seconds",
    "زمن معالجة طلب الاسترجاع",
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
    registry=REGISTRY,
)

_intent_counter = Counter(
    "cogniforge_retrieval_intent_total",
    "توزيع نوايا الاسترجاع المكتشفة",
    ["intent"],
    registry=REGISTRY,
)

_hits = Counter(
    "cogniforge_retrieval_hits_total",
    "عدد الطلبات التي أعادت نتائج من قاعدة المعرفة",
    registry=REGISTRY,
)

_misses = Counter(
    "cogniforge_retrieval_misses_total",
    "عدد الطلبات بدون نتائج (no_intent أو قاعدة المعرفة فارغة)",
    registry=REGISTRY,
)

_kb_size = Gauge(
    "cogniforge_retrieval_knowledge_base_size",
    "عدد الملفات في knowledge_base/",
    registry=REGISTRY,
)

_startup_info = Gauge(
    "cogniforge_retrieval_startup_info",
    "معلومات إقلاع content-retrieval-skill",
    ["step", "version", "kb_path"],
    registry=REGISTRY,
)


def record_request(status: str, intent: str, duration_s: float) -> None:
    """يُسجِّل طلب استرجاع مع حالته ونيته وزمنه."""
    _requests.labels(status=status, intent=intent).inc()
    _duration.observe(duration_s)
    _intent_counter.labels(intent=intent).inc()
    if status == "hit":
        _hits.inc()
    else:
        _misses.inc()


def set_kb_size(count: int) -> None:
    """يُحدِّث حجم قاعدة المعرفة."""
    _kb_size.set(count)


def set_startup_info(step: str, version: str, kb_path: str) -> None:
    """يُسجِّل معلومات الإقلاع."""
    _startup_info.labels(step=step, version=version, kb_path=kb_path).set(1.0)
