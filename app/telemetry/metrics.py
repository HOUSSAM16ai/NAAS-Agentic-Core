from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from app.telemetry.models import MetricSample, MetricType

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MetricRecord:
    """يمثل حمولة تسجيل مقياس واحدة بشكل منظم وواضح للمبتدئين."""

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    trace_id: str | None = None
    span_id: str | None = None
    metric_type: MetricType = MetricType.LATENCY

    def metric_key(self) -> str:
        """يبني مفتاحاً متناسقاً للمقاييس يعتمد على الاسم والوسوم المرفقة."""

        if not self.labels:
            return self.name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(self.labels.items()))
        return f"{self.name}{{{label_str}}}"


class MetricsManager:
    """مدير المقاييس المركزي مع واجهة عربية مبسطة ودون معلمات متفرقة."""

    def __init__(self) -> None:
        self.metrics_buffer: deque[MetricSample] = deque(maxlen=100000)
        self.counters: dict[str, float] = defaultdict(float)
        self.gauges: dict[str, float] = {}
        self.histograms: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=10000))
        self.trace_metrics: dict[str, list[MetricSample]] = defaultdict(list)
        self.lock = threading.RLock()
        self.stats = {"metrics_recorded": 0}

    def record_metric(self, record: MetricRecord) -> None:
        """
        يسجل مقياساً واحداً باستخدام كائن تكوين واضح يحوي جميع الحقول اللازمة.

        هذا التصميم يشجع المطورين الجدد على إنشاء حمولة واحدة متماسكة بدلاً من
        تمرير عدة معلمات متفرقة، ويضمن أيضاً تخزين بيانات التتبع عند توفرها.
        """

        sample = MetricSample(
            value=record.value,
            timestamp=time.time(),
            labels=record.labels,
            exemplar_trace_id=record.trace_id,
            exemplar_span_id=record.span_id,
            name=record.name,
            metric_type=record.metric_type,
        )
        with self.lock:
            self.metrics_buffer.append(sample)
            self.stats["metrics_recorded"] += 1
            # Only add to histograms if it's a latency or generic value, not explicit counter/gauge updates
            # (unless we want distribution of counter increments, which is rare)
            self.histograms[record.name].append(record.value)
            if record.trace_id:
                self.trace_metrics[record.trace_id].append(sample)

    def record_named_metric(
        self,
        name: str,
        value: float,
        labels: dict[str, str] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> None:
        """غلاف توافق يسهّل الانتقال إلى واجهة الكائنات المهيكلة."""

        self.record_metric(
            MetricRecord(
                name=name,
                value=value,
                labels=labels or {},
                trace_id=trace_id,
                span_id=span_id,
            )
        )

    def increment_counter(
        self, name: str, amount: float = 1.0, labels: dict[str, str] | None = None
    ) -> None:
        key = self._metric_key(name, labels)
        with self.lock:
            self.counters[key] += amount
            # Add to buffer for export
            self.metrics_buffer.append(
                MetricSample(
                    value=amount,
                    timestamp=time.time(),
                    labels=labels or {},
                    name=name,
                    metric_type=MetricType.COUNTER,
                )
            )

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        key = self._metric_key(name, labels)
        with self.lock:
            self.gauges[key] = value
            # Add to buffer for export
            self.metrics_buffer.append(
                MetricSample(
                    value=value,
                    timestamp=time.time(),
                    labels=labels or {},
                    name=name,
                    metric_type=MetricType.GAUGE,
                )
            )

    def get_percentiles(self, metric_name: str) -> dict[str, float]:
        with self.lock:
            values = list(self.histograms.get(metric_name, []))

        if not values:
            return {"p50": 0, "p90": 0, "p95": 0, "p99": 0, "p99.9": 0}

        sorted_values = sorted(values)
        return {
            "p50": self._percentile(sorted_values, 50),
            "p90": self._percentile(sorted_values, 90),
            "p95": self._percentile(sorted_values, 95),
            "p99": self._percentile(sorted_values, 99),
            "p99.9": self._percentile(sorted_values, 99.9),
        }

    def _metric_key(self, name: str, labels: dict[str, str] | None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def _percentile(self, sorted_data: list[float], percentile: float) -> float:
        if not sorted_data:
            return 0.0
        index = (len(sorted_data) - 1) * (percentile / 100.0)
        lower = int(index)
        fraction = index - lower
        if lower + 1 < len(sorted_data):
            return sorted_data[lower] + fraction * (sorted_data[lower + 1] - sorted_data[lower])
        return sorted_data[lower]

    def export_prometheus_metrics(self) -> str:
        """تصدير المقاييس بصيغة Prometheus exposition صالحة.

        المهمات الثلاث المنجزة هنا:
          1) ترجمة الاسم: ``http.requests.total`` → ``cogniforge_http_requests_total``
             (Prometheus يرفض النقاط في الأسماء؛ يضاف بادئة ``cogniforge_``).
          2) تنسيق الـ labels بعلامات اقتباس مزدوجة كما يتطلب Prometheus
             (الصيغة الداخلية ``key=value`` غير صالحة عند الـ scrape).
          3) إصدار histograms كاملة (``_bucket`` + ``_count`` + ``_sum``)
             لكي تعمل لوحات p95/p99 latency في Grafana.

        تطابق Mission Control الذي يفترض ``cogniforge_http_*`` و
        ``cogniforge_ws_chat_*`` (راجع ``observability/grafana/dashboards/``).
        """

        # Standard SRE histogram buckets (seconds). Covers from sub-millisecond
        # to 10s — the realistic range for HTTP + WS turn latency in this app.
        hist_buckets: list[float] = [
            0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0
        ]
        # Metric names whose histogram data we want exposed as Prometheus
        # histograms (rather than just counters/gauges). These are the
        # "_seconds" latency series that the dashboards rely on.
        hist_names: set[str] = {
            "http.request.duration_seconds",
            "ws.chat.turn.duration_seconds",
            # LangGraph per-node latency — feeds cogniforge_langgraph_node_duration_seconds
            # panels in observability/grafana/dashboards/20-langgraph.json
            "langgraph.node.duration_seconds",
            # Orchestrator StateGraph node latency — feeds 50-microservices-transition.json
            # graph="orchestrator" label distinguishes from local graph="local"
            "orchestrator.node.duration_seconds",
        }

        def _translate_name(raw: str) -> str:
            """``http.requests.total`` → ``cogniforge_http_requests_total``."""
            sanitized = raw.replace(".", "_").replace("-", "_")
            if sanitized.startswith("cogniforge_"):
                return sanitized
            return f"cogniforge_{sanitized}"

        def _quote_labels(label_blob: str) -> str:
            """Internal ``k=v,k=v`` → Prometheus ``{k="v",k="v"}``.

            Returns ``""`` when there are no labels — Prometheus accepts an
            unlabeled metric line like ``cogniforge_metric 5``.
            """
            if not label_blob:
                return ""
            parts = []
            for kv in label_blob.split(","):
                k, _, v = kv.partition("=")
                # Escape backslash + double-quote per Prometheus spec.
                v_escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                parts.append(f'{k}="{v_escaped}"')
            return "{" + ",".join(parts) + "}"

        def _split_key(key: str) -> tuple[str, str]:
            """Returns (raw_name, raw_label_blob)."""
            if "{" in key and key.endswith("}"):
                idx = key.index("{")
                return key[:idx], key[idx + 1 : -1]
            return key, ""

        lines: list[str] = []
        emitted_types: set[str] = set()

        with self.lock:
            counters_snapshot = dict(self.counters)
            gauges_snapshot = dict(self.gauges)
            histograms_snapshot = {
                name: list(values) for name, values in self.histograms.items()
            }

        # ---- Counters -------------------------------------------------------
        # Group counter keys by translated name so we can emit ``# TYPE`` once.
        counter_by_name: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for raw_key, value in counters_snapshot.items():
            raw_name, raw_labels = _split_key(raw_key)
            prom_name = _translate_name(raw_name)
            counter_by_name[prom_name].append((raw_labels, value))

        for prom_name, samples in sorted(counter_by_name.items()):
            if prom_name not in emitted_types:
                lines.append(f"# TYPE {prom_name} counter")
                emitted_types.add(prom_name)
            for raw_labels, value in samples:
                lines.append(f"{prom_name}{_quote_labels(raw_labels)} {value}")

        # ---- Gauges ---------------------------------------------------------
        gauge_by_name: dict[str, list[tuple[str, float]]] = defaultdict(list)
        for raw_key, value in gauges_snapshot.items():
            raw_name, raw_labels = _split_key(raw_key)
            prom_name = _translate_name(raw_name)
            gauge_by_name[prom_name].append((raw_labels, value))

        for prom_name, samples in sorted(gauge_by_name.items()):
            if prom_name not in emitted_types:
                lines.append(f"# TYPE {prom_name} gauge")
                emitted_types.add(prom_name)
            for raw_labels, value in samples:
                lines.append(f"{prom_name}{_quote_labels(raw_labels)} {value}")

        # ---- Histograms -----------------------------------------------------
        # Latency series go through ``record_metric`` which appends to
        # ``self.histograms[name]`` — UNLABELED (the current impl doesn't
        # carry labels into histograms, see metrics.py:68). MVP: emit one
        # aggregate histogram per series so Grafana p95/p99 panels work.
        for raw_name in sorted(hist_names & set(histograms_snapshot.keys())):
            values = histograms_snapshot[raw_name]
            prom_name = _translate_name(raw_name)
            if prom_name not in emitted_types:
                lines.append(f"# TYPE {prom_name} histogram")
                emitted_types.add(prom_name)
            # Per-bucket cumulative counts.
            for bound in hist_buckets:
                count = sum(1 for v in values if v <= bound)
                lines.append(f'{prom_name}_bucket{{le="{bound}"}} {count}')
            # +Inf bucket equals total count (Prometheus convention).
            lines.append(f'{prom_name}_bucket{{le="+Inf"}} {len(values)}')
            lines.append(f"{prom_name}_count {len(values)}")
            lines.append(f"{prom_name}_sum {sum(values)}")

        # Trailing newline keeps Prometheus's text parser happy.
        return "\n".join(lines) + "\n"
