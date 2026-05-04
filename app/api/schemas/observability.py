from pydantic import ConfigDict, Field

from app.core.schemas import RobustBaseModel


class TraceSpanResponse(RobustBaseModel):
    """بيانات span واحد ضمن trace موزع."""

    span_id: str = Field(..., description="معرف الـ span")
    parent_span_id: str | None = Field(None, description="معرف الـ span الأصل")
    operation_name: str = Field(..., description="اسم العملية")
    service_name: str = Field(..., description="اسم الخدمة")
    start_time: float = Field(..., description="وقت البداية (Unix timestamp)")
    end_time: float | None = Field(None, description="وقت النهاية")
    duration_ms: float | None = Field(None, description="المدة بالميلي ثانية")
    status: str = Field(..., description="الحالة: OK / ERROR / SKIP")
    tags: dict[str, object] = Field(default_factory=dict, description="وسوم البيانات الوصفية")
    metrics: dict[str, float] = Field(default_factory=dict, description="مقاييس الـ span")
    error_message: str | None = Field(None, description="رسالة الخطأ إن وجدت")


class TraceResponse(RobustBaseModel):
    """trace موزع كامل مع كل spans وسجلاته المرتبطة."""

    trace_id: str = Field(..., description="معرف التتبع الموزع")
    start_time: float = Field(..., description="وقت بداية التتبع")
    end_time: float | None = Field(None, description="وقت نهاية التتبع")
    total_duration_ms: float | None = Field(None, description="المدة الكلية")
    error_count: int = Field(0, description="عدد الأخطاء المسجلة")
    critical_path_ms: float | None = Field(None, description="المسار الحرج")
    spans: list[TraceSpanResponse] = Field(default_factory=list, description="قائمة الـ spans")
    correlated_logs: list[dict[str, object]] = Field(
        default_factory=list, description="السجلات المرتبطة بهذا التتبع"
    )


class HealthComponent(RobustBaseModel):
    """مكون صحة فرعي يوضح حالة نظام محدد."""

    status: str
    details: dict[str, object] | None = None


class HealthResponse(RobustBaseModel):
    """
    نموذج استجابة الصحة العامة.
    """

    status: str = Field(..., description="الحالة العامة للنظام")
    components: dict[str, HealthComponent] | None = Field(None, description="حالة المكونات الفرعية")


class LatencyMetrics(RobustBaseModel):
    """مقاييس زمن الاستجابة للمسارات الساخنة."""

    model_config = ConfigDict(populate_by_name=True)

    p50: float = Field(..., description="الوسيط")
    p95: float = Field(..., description="النسبة المئوية 95")
    p99: float = Field(..., description="النسبة المئوية 99")
    p99_9: float = Field(..., alias="p99.9", description="النسبة المئوية 99.9")
    avg: float = Field(..., description="المتوسط العام")


class TrafficMetrics(RobustBaseModel):
    """إحصاءات حركة المرور على مستوى الخدمة."""

    requests_per_second: float = Field(..., description="عدد الطلبات في الثانية")
    total_requests: int = Field(..., description="إجمالي الطلبات في النافذة الزمنية")


class ErrorMetrics(RobustBaseModel):
    """مقاييس الأخطاء ونسبة فشل الطلبات."""

    error_rate: float = Field(..., description="معدل الأخطاء بالنسبة المئوية")
    error_count: int = Field(..., description="عدد الأخطاء الملاحظة")


class SaturationMetrics(RobustBaseModel):
    """مؤشرات التشبع واستهلاك الموارد."""

    active_requests: int = Field(..., description="عدد الطلبات النشطة")
    queue_depth: int = Field(..., description="عمق طابور التنفيذ")
    active_spans: int | None = Field(None, description="عدد المقاطع التتبعية الفعّالة")
    resource_utilization: float | None = Field(None, description="نسبة استهلاك الموارد")


class GoldenSignalsResponse(RobustBaseModel):
    """
    نموذج الإشارات الذهبية (SRE Golden Signals).
    """

    latency: LatencyMetrics = Field(..., description="مقاييس زمن الاستجابة")
    traffic: TrafficMetrics = Field(..., description="حركة المرور")
    errors: ErrorMetrics = Field(..., description="نسبة الأخطاء")
    saturation: SaturationMetrics = Field(..., description="مؤشرات التشبع")


class AIOpsMetricsResponse(RobustBaseModel):
    """
    نموذج مقاييس الذكاء الاصطناعي للعمليات (AIOps).
    """

    anomaly_score: float = Field(..., description="درجة الشذوذ")
    self_healing_events: int = Field(0, description="عدد أحداث المعالجة الذاتية")
    predictions: dict[str, object] | None = Field(None, description="توقعات مستقبلية")


class GitOpsMetricsResponse(RobustBaseModel):
    """
    نموذج مقاييس GitOps.
    """

    status: str = Field(..., description="حالة المزامنة")
    sync_rate: float = Field(..., description="معدل المزامنة (%)")
    last_sync: str | None = Field(None, description="توقيت آخر مزامنة")


class PerformanceSnapshotResponse(RobustBaseModel):
    """
    نموذج لقطة الأداء.
    """

    cpu_usage: float = Field(..., description="استهلاك المعالج (%)")
    memory_usage: float = Field(..., description="استهلاك الذاكرة (%)")
    active_requests: int = Field(..., description="عدد الطلبات النشطة")


class EndpointAnalyticsResponse(RobustBaseModel):
    """
    نموذج تحليلات نقطة النهاية.
    """

    path: str = Field(..., description="مسار نقطة النهاية")
    avg_latency: float = Field(..., description="متوسط زمن الاستجابة")
    p95_latency: float = Field(..., description="P95 Latency")
    error_count: int = Field(0, description="عدد الأخطاء")
    total_calls: int = Field(0, description="إجمالي الاستدعاءات")


class AlertResponse(RobustBaseModel):
    """
    نموذج التنبيه.
    """

    id: str
    severity: str
    message: str
    timestamp: str
    status: str
