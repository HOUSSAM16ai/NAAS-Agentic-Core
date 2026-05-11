"""
نقطة دخول reasoning-agent (الخطوة 8).

يُشغِّل FastAPI على :8008 مع:
  - /health  — فحص الصحة الحي
  - /metrics — مقاييس Prometheus (cogniforge_reasoning_*)
  - /execute — تنفيذ سير عمل التفكير (MCTS + LLM)

الإصلاحات المُطبَّقة:
  - ISS-039-B: AIService يُنشأ كـ lazy singleton لتجنب OpenAIError عند الإقلاع بدون مفتاح API.
  - الـ lifespan يُسجِّل startup_info في Prometheus عند الإقلاع الناجح.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import Response

from microservices.reasoning_agent import prom_metrics
from microservices.reasoning_agent.src.api.routes import router
from microservices.reasoning_agent.src.core.config import settings
from microservices.reasoning_agent.src.core.logging import setup_logging


def _detect_llm_backend() -> str:
    """
    يكتشف خلفية نموذج اللغة المُستخدَمة بناءً على متغيرات البيئة.

    العائد:
        str: "openrouter" | "openai" | "mock"
    """
    if os.environ.get("OPENROUTER_API_KEY") or settings.OPENROUTER_API_KEY:
        return "openrouter"
    if os.environ.get("OPENAI_API_KEY") or settings.OPENAI_API_KEY:
        return "openai"
    return "mock"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    دورة حياة reasoning-agent.

    المرحلة 1 (إقلاع): تهيئة التسجيل + تسجيل startup_info في Prometheus.
    المرحلة 2 (إيقاف): تسجيل رسالة الإيقاف.
    """
    setup_logging()

    llm_backend = _detect_llm_backend()
    environment = os.environ.get("ENVIRONMENT", settings.ENVIRONMENT)

    prom_metrics.set_startup_info(
        version="1.0.0",
        environment=environment,
        llm_backend=llm_backend,
        mcts_enabled="true",
    )

    print(
        f"🚀 {settings.SERVICE_NAME} started | "
        f"env={environment} | llm={llm_backend} | step=8 | port=8008"
    )

    yield

    print(f"🛑 {settings.SERVICE_NAME} stopped")


def create_app() -> FastAPI:
    """
    يُنشئ تطبيق FastAPI مع جميع الـ routes والـ lifespan.

    العائد:
        FastAPI: التطبيق المُهيَّأ
    """
    application = FastAPI(
        title="Reasoning Agent",
        description="خدمة التفكير العميق — MCTS + LLM | الخطوة 8 من مسار الخدمات المصغرة",
        version="2.0.0",
        lifespan=lifespan,
    )

    application.include_router(router)

    @application.get(
        "/metrics",
        tags=["Observability"],
        summary="Prometheus metrics",
        response_class=Response,
    )
    async def metrics_endpoint() -> Response:
        """
        يُصدِّر مقاييس Prometheus بصيغة text/plain.

        يُستخدَم من قِبَل Prometheus scraper على :8008/metrics.
        المقاييس: cogniforge_reasoning_* (11 مقياساً).
        """
        content, content_type = prom_metrics.export_prometheus_text()
        return Response(content=content, media_type=content_type)

    @application.get(
        "/health",
        tags=["System"],
        summary="Health check",
    )
    async def health_check() -> dict:
        """
        فحص صحة reasoning-agent الحي.

        يُعيد: status + service + step + llm_backend + mcts_enabled
        """
        llm_backend = _detect_llm_backend()
        return {
            "status": "healthy",
            "service": "reasoning-agent",
            "step": "8",
            "llm_backend": llm_backend,
            "mcts_enabled": "true",
        }

    return application


app = create_app()
