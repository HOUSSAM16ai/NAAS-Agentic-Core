from dataclasses import dataclass, field
from enum import Enum


class SamplingDecision(Enum):
    SAMPLE = "sample"
    DROP = "drop"
    DEFER = "defer"


class AlertSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MetricType(Enum):
    """أنواع المقاييس المدعومة."""

    LATENCY = "latency"
    ERROR_RATE = "error_rate"
    REQUEST_RATE = "request_rate"
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    DISK_USAGE = "disk_usage"
    NETWORK_IO = "network_io"
    COUNTER = "counter"
    GAUGE = "gauge"


@dataclass
class TraceContext:
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    sampled: bool = True
    baggage: dict[str, str] = field(default_factory=dict)

    def to_headers(self) -> dict[str, str]:
        flags = "01" if self.sampled else "00"
        headers = {"traceparent": f"00-{self.trace_id}-{self.span_id}-{flags}"}
        if self.baggage:
            tracestate = ",".join(f"{k}={v}" for k, v in self.baggage.items())
            headers["tracestate"] = tracestate
        return headers

    @classmethod
    def from_headers(cls, headers: dict[str, str]) -> "TraceContext | None":
        traceparent = headers.get("traceparent") or headers.get("Traceparent")
        if not traceparent:
            return None
        try:
            parts = traceparent.split("-")
            if len(parts) != 4:
                return None
            _version, trace_id, parent_span_id, flags = parts
            sampled = flags == "01"
            baggage = {}
            tracestate = headers.get("tracestate") or headers.get("Tracestate", "")
            for item in tracestate.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    baggage[k.strip()] = v.strip()

            return cls(
                trace_id=trace_id,
                span_id=parent_span_id,
                parent_span_id=parent_span_id,
                sampled=sampled,
                baggage=baggage,
            )
        except Exception:
            return None


@dataclass
class UnifiedSpan:
    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation_name: str
    service_name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    tags: dict[str, object] = field(default_factory=dict)
    events: list[dict[str, object]] = field(default_factory=list)
    status: str = "OK"
    error_message: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    baggage: dict[str, str] = field(default_factory=dict)

    def finalize(self) -> None:
        if self.end_time:
            self.duration_ms = (self.end_time - self.start_time) * 1000


@dataclass
class UnifiedTrace:
    trace_id: str
    root_span: UnifiedSpan
    spans: list[UnifiedSpan] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float | None = None
    total_duration_ms: float | None = None
    error_count: int = 0
    critical_path_ms: float | None = None
    bottleneck_span_id: str | None = None

    def analyze_critical_path(self) -> None:
        if not self.spans:
            return
        max_duration = 0.0
        bottleneck = None
        for span in self.spans:
            if span.duration_ms and span.duration_ms > max_duration:
                max_duration = span.duration_ms
                bottleneck = span.span_id
        self.critical_path_ms = max_duration
        self.bottleneck_span_id = bottleneck


@dataclass
class MetricSample:
    value: float
    timestamp: float
    labels: dict[str, str] = field(default_factory=dict)
    exemplar_trace_id: str | None = None
    exemplar_span_id: str | None = None
    name: str | None = None
    metric_type: str | MetricType | None = None


@dataclass
class CorrelatedLog:
    timestamp: float
    level: str
    message: str
    trace_id: str | None = None
    span_id: str | None = None
    context: dict[str, object] = field(default_factory=dict)
    exception: dict[str, object] | None = None


@dataclass
class AnomalyAlert:
    alert_id: str
    timestamp: float
    severity: AlertSeverity
    anomaly_type: str
    description: str
    metrics: dict[str, object]
    trace_ids: list[str] = field(default_factory=list)
    recommended_action: str = ""
    resolved: bool = False
