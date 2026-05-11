"""
مسارات API لـ reasoning-agent.

/execute — تنفيذ سير عمل التفكير (MCTS + LLM) مع تسجيل مقاييس Prometheus.

ملاحظة: /health و /metrics مُعرَّفان في main.py مباشرةً لتجنب التكرار.
"""

import time

from fastapi import APIRouter

from microservices.reasoning_agent import prom_metrics
from microservices.reasoning_agent.src.core.logging import get_logger
from microservices.reasoning_agent.src.domain.models import AgentRequest, AgentResponse
from microservices.reasoning_agent.src.services.reasoning_service import reasoning_workflow

logger = get_logger("api-routes")
router = APIRouter()


@router.post("/execute", response_model=AgentResponse, tags=["Agent"])
async def execute(request: AgentRequest) -> AgentResponse:
    """
    تنفيذ سير عمل التفكير العميق.

    الإجراءات المدعومة: reason, solve_deeply
    يُسجِّل: invocation_total + invocation_duration + fallback_responses في Prometheus.
    """
    start_time = time.monotonic()
    prom_metrics.set_active_connections(1)
    logger.info(f"Received request from {request.caller_id}: {request.action}")

    try:
        if request.action in {"reason", "solve_deeply"}:
            query = str(request.payload.get("query", ""))
            context = str(request.payload.get("context", ""))

            if not query:
                prom_metrics.record_reasoning_invocation(
                    action=request.action,
                    status="error",
                    duration_seconds=prom_metrics.elapsed_since(start_time),
                )
                prom_metrics.set_active_connections(0)
                return AgentResponse(status="error", error="Query is required for reasoning.")

            result = await reasoning_workflow.run(query=query, context=context)
            duration = prom_metrics.elapsed_since(start_time)

            # تسجيل نتيجة ناجحة
            status = "fallback" if "Mock response" in str(result) else "success"
            prom_metrics.record_reasoning_invocation(
                action=request.action,
                status=status,
                duration_seconds=duration,
            )
            if status == "fallback":
                prom_metrics.record_fallback_response(reason="no_api_key")

            prom_metrics.record_http_request(
                method="POST",
                endpoint="/execute",
                status_code=200,
                duration_seconds=duration,
            )
            prom_metrics.set_active_connections(0)

            return AgentResponse(
                status="success",
                data={"answer": str(result)},
                metrics={"duration_ms": duration * 1000},
            )

        prom_metrics.record_reasoning_invocation(
            action=request.action,
            status="unsupported",
            duration_seconds=prom_metrics.elapsed_since(start_time),
        )
        prom_metrics.set_active_connections(0)
        return AgentResponse(status="error", error=f"Action '{request.action}' not supported.")

    except Exception as e:
        duration = prom_metrics.elapsed_since(start_time)
        prom_metrics.record_reasoning_invocation(
            action=request.action,
            status="error",
            duration_seconds=duration,
        )
        prom_metrics.record_mcts_error(error_type=type(e).__name__)
        prom_metrics.record_http_request(
            method="POST",
            endpoint="/execute",
            status_code=500,
            duration_seconds=duration,
        )
        prom_metrics.set_active_connections(0)
        logger.error(f"Execution failed: {e}", exc_info=True)
        return AgentResponse(status="error", error=str(e))
