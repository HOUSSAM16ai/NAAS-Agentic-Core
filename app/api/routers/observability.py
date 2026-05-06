# app/api/routers/observability.py
"""
موجه المراقبة (Observability Router) للصحة والمقاييس والتتبع الموزع.
--------------------------------------------------
يوفر نقاط نهاية للمراقبة الموحدة ويعتمد على خدمات الحدود لعزل المنطق وتبسيط
طبقة العرض وفق مبادئ البنية النظيفة.
"""

from fastapi import APIRouter, Depends, HTTPException, Response

from app.api.schemas.observability import (
    AIOpsMetricsResponse,
    AlertResponse,
    EndpointAnalyticsResponse,
    GitOpsMetricsResponse,
    GoldenSignalsResponse,
    HealthResponse,
    PerformanceSnapshotResponse,
    TraceResponse,
    TraceSpanResponse,
)
from app.services.boundaries.observability_boundary_service import ObservabilityBoundaryService

router = APIRouter(tags=["Observability"])


@router.get(
    "/prometheus",
    summary="Prometheus exposition endpoint",
    response_class=Response,
    include_in_schema=False,
)
async def prometheus_scrape() -> Response:
    """Return process metrics in Prometheus text exposition format.

    Scraped by the observability stack (`observability/prometheus/prometheus.yml`)
    every 15s. The body is the union of:
      * counters / gauges / histograms recorded via `UnifiedObservabilityService`
      * (when enabled) anything the OTel SDK exposes via prometheus_client

    Stays available even when OTel is OFF — uses the in-memory facade as a
    minimal fallback so dashboards never go fully dark.
    """
    from app.telemetry.unified_observability import get_unified_observability

    obs = get_unified_observability()
    body = obs.export_prometheus_metrics() or "# no metrics\n"
    return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")


def get_observability_service() -> ObservabilityBoundaryService:
    """تبعية لاسترجاع خدمة المراقبة الحدية الموحدة."""
    return ObservabilityBoundaryService()


@router.get(
    "/health",
    summary="System Health Check",
    response_model=HealthResponse,
)
async def health_check(
    service: ObservabilityBoundaryService = Depends(get_observability_service),
) -> HealthResponse:
    """
    الحصول على الحالة الصحية العامة للنظام.
    يتم التفويض لخدمة الحدود لتجميع النتائج من الأنظمة الفرعية.
    """
    result = await service.get_system_health()
    return HealthResponse.model_validate(result)


@router.get(
    "/metrics",
    summary="Get Golden Signals",
    response_model=GoldenSignalsResponse,
)
async def get_metrics(
    service: ObservabilityBoundaryService = Depends(get_observability_service),
) -> GoldenSignalsResponse:
    """
    استرجاع الإشارات الذهبية الخاصة بالموثوقية (زمن الاستجابة، الحركة، الأخطاء، التشبع).
    """
    result = await service.get_golden_signals()
    return GoldenSignalsResponse.model_validate(result)


@router.get(
    "/aiops",
    summary="Get AIOps Metrics",
    response_model=AIOpsMetricsResponse,
)
async def get_aiops_metrics(
    service: ObservabilityBoundaryService = Depends(get_observability_service),
) -> AIOpsMetricsResponse:
    """
    جلب مقاييس اكتشاف الشذوذ والمعالجة الذاتية الخاصة بـ AIOps.
    """
    result = await service.get_aiops_metrics()
    return AIOpsMetricsResponse.model_validate(result)


@router.get(
    "/gitops",
    summary="Get GitOps Status",
    response_model=GitOpsMetricsResponse,
)
async def get_gitops_metrics() -> GitOpsMetricsResponse:
    """
    جلب حالة المزامنة الخاصة بعمليات GitOps.
    ملاحظة: ما زالت هذه النقطة نقطة انتظار حتى يتم دمج خدمة GitOps الفعلية.
    """
    # Placeholder for GitOps metrics
    return GitOpsMetricsResponse(status="gitops_active", sync_rate=100)


@router.get(
    "/performance",
    summary="Get Performance Snapshot",
    response_model=PerformanceSnapshotResponse,
)
async def get_performance_snapshot(
    service: ObservabilityBoundaryService = Depends(get_observability_service),
) -> PerformanceSnapshotResponse:
    """
    استرجاع إحصاءات الأداء التفصيلية لوقت التشغيل.
    """
    result = await service.get_performance_snapshot()
    return PerformanceSnapshotResponse.model_validate(result)


@router.get(
    "/analytics/{path:path}",
    summary="Get Endpoint Analytics",
    response_model=list[EndpointAnalyticsResponse],
)
async def get_endpoint_analytics(
    path: str,
    service: ObservabilityBoundaryService = Depends(get_observability_service),
) -> list[EndpointAnalyticsResponse]:
    """
    الحصول على تحليلات التتبع لمسار API محدد على شكل قائمة سجلات غنية.
    """
    result = await service.get_endpoint_analytics(path)
    return [EndpointAnalyticsResponse.model_validate(item) for item in result]


@router.get(
    "/alerts",
    summary="Get Active Alerts",
    response_model=list[AlertResponse],
)
async def get_alerts(
    service: ObservabilityBoundaryService = Depends(get_observability_service),
) -> list[AlertResponse]:
    """
    استرجاع التنبيهات النشطة الخاصة بالشذوذات الحالية.
    """
    results = await service.get_active_alerts()
    return [AlertResponse.model_validate(r) for r in results]


@router.get(
    "/traces",
    summary="List Recent Completed Traces",
    response_model=list[TraceResponse],
)
async def list_traces(limit: int = 50) -> list[TraceResponse]:
    """
    استرجاع آخر التتبعات الموزعة المكتملة مع بيانات الـ spans المرتبطة.
    """
    from app.telemetry.unified_observability import get_unified_observability

    obs = get_unified_observability()
    traces = list(obs.completed_traces)[-limit:]
    results: list[TraceResponse] = []
    for trace in traces:
        correlated = obs.get_trace_with_correlation(trace.trace_id) or {}
        logs = correlated.get("logs", [])
        results.append(
            TraceResponse(
                trace_id=trace.trace_id,
                start_time=trace.start_time,
                end_time=trace.end_time,
                total_duration_ms=trace.total_duration_ms,
                error_count=trace.error_count,
                critical_path_ms=trace.critical_path_ms,
                spans=[
                    TraceSpanResponse(
                        span_id=s.span_id,
                        parent_span_id=s.parent_span_id,
                        operation_name=s.operation_name,
                        service_name=s.service_name,
                        start_time=s.start_time,
                        end_time=s.end_time,
                        duration_ms=s.duration_ms,
                        status=s.status,
                        tags=s.tags,
                        metrics=s.metrics,
                        error_message=s.error_message,
                    )
                    for s in trace.spans
                ],
                correlated_logs=[
                    {
                        "timestamp": log.timestamp,
                        "level": log.level,
                        "message": log.message,
                        "span_id": log.span_id,
                    }
                    for log in logs
                ],
            )
        )
    return results


@router.get(
    "/traces/{trace_id}",
    summary="Get Trace by ID",
    response_model=TraceResponse,
)
async def get_trace(trace_id: str) -> TraceResponse:
    """
    استرجاع تتبع موزع بالمعرف مع كل spans وسجلاته المرتبطة.
    """
    from app.telemetry.unified_observability import get_unified_observability

    obs = get_unified_observability()

    # Search completed traces
    trace = next((t for t in obs.completed_traces if t.trace_id == trace_id), None)

    # Also check active traces
    if trace is None:
        trace = obs.active_traces.get(trace_id)

    if trace is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id!r} not found")

    correlated = obs.get_trace_with_correlation(trace_id) or {}
    logs = correlated.get("logs", [])

    return TraceResponse(
        trace_id=trace.trace_id,
        start_time=trace.start_time,
        end_time=trace.end_time,
        total_duration_ms=trace.total_duration_ms,
        error_count=trace.error_count,
        critical_path_ms=trace.critical_path_ms,
        spans=[
            TraceSpanResponse(
                span_id=s.span_id,
                parent_span_id=s.parent_span_id,
                operation_name=s.operation_name,
                service_name=s.service_name,
                start_time=s.start_time,
                end_time=s.end_time,
                duration_ms=s.duration_ms,
                status=s.status,
                tags=s.tags,
                metrics=s.metrics,
                error_message=s.error_message,
            )
            for s in trace.spans
        ],
        correlated_logs=[
            {
                "timestamp": log.timestamp,
                "level": log.level,
                "message": log.message,
                "span_id": log.span_id,
            }
            for log in logs
        ],
    )
