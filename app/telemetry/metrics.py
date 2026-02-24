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
        lines: list[str] = []
        with self.lock:
            for key, value in self.counters.items():
                lines.append(f"{key} {value}")
            for key, value in self.gauges.items():
                lines.append(f"{key} {value}")
        return "\n".join(lines)
