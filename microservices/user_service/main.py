"""
نقطة الدخول الرئيسية لخدمة المستخدمين.

Step 5 (2026-05-10): إضافة /metrics endpoint بصيغة Prometheus الحقيقية.
يُشغَّل كـ uvicorn process مستقل على :8001 في Codespaces (بدون Docker).
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.responses import Response

from microservices.user_service.database import async_session_factory, init_db
from microservices.user_service.errors import setup_exception_handlers
from microservices.user_service.health import HealthResponse, build_health_payload
from microservices.user_service.logging import get_logger, setup_logging
from microservices.user_service.security import verify_service_token
from microservices.user_service.settings import UserServiceSettings, get_settings
from microservices.user_service.src.api.routes import auth as auth_router
from microservices.user_service.src.api.routes import ums as ums_router
from microservices.user_service.src.core.prom_metrics import (
    export_prometheus_text,
    set_startup_info,
)
from microservices.user_service.src.core.seed import seed_initial_data

logger = get_logger("user-service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """دورة حياة الخدمة — تهيئة قاعدة البيانات وتسجيل مقاييس الإقلاع."""
    settings = get_settings()
    setup_logging(settings.SERVICE_NAME)
    logger.info("user-service starting (Step 5 — Prometheus metrics active)...")

    # Phase 1: تهيئة قاعدة البيانات
    await init_db()

    # Phase 2: بذر البيانات الأولية
    async with async_session_factory() as session:
        await seed_initial_data(session)

    # Phase 3: تسجيل معلومات الإقلاع في Prometheus
    db_backend = "postgresql" if "postgresql" in (settings.DATABASE_URL or "") else "sqlite"
    set_startup_info(
        version=settings.SERVICE_VERSION,
        environment=settings.ENVIRONMENT,
        db_backend=db_backend,
    )
    logger.info(
        "user-service ready | port=8001 | db=%s | env=%s",
        db_backend,
        settings.ENVIRONMENT,
    )

    yield

    logger.info("user-service shutting down...")


def create_app(settings: UserServiceSettings | None = None) -> FastAPI:
    """يبني تطبيق FastAPI لخدمة المستخدمين."""
    effective_settings = settings or get_settings()

    app = FastAPI(
        title=effective_settings.SERVICE_NAME,
        description="Isolated microservice for user management.",
        version=effective_settings.SERVICE_VERSION,
        lifespan=lifespan,
        openapi_tags=[
            {"name": "System", "description": "System health and metrics"},
            {"name": "Auth", "description": "Authentication operations"},
            {"name": "UMS", "description": "User Management System"},
        ],
    )

    setup_exception_handlers(app)

    # ── نقاط النهاية العامة ──────────────────────────────────────────────────

    @app.get("/health", response_model=HealthResponse, tags=["System"])
    def health_check() -> HealthResponse:
        """فحص صحة الخدمة — يُعيد status=ok عند الجاهزية."""
        return build_health_payload(effective_settings)

    @app.get("/metrics", tags=["System"], include_in_schema=False)
    def prometheus_metrics() -> Response:
        """يُصدِّر مقاييس Prometheus بصيغة text format.

        يُستخدم من Prometheus scraper على localhost:8001/metrics.
        المقاييس: cogniforge_user_* (requests, auth, db, startup_info).
        """
        content, content_type = export_prometheus_text()
        return Response(content=content, media_type=content_type)

    # ── نقاط النهاية المحمية (Service Token من Gateway) ─────────────────────

    # Auth Router (Login/Register — وصول عام عبر Gateway)
    app.include_router(
        auth_router.router,
        prefix="/api/v1/auth",
        dependencies=[Depends(verify_service_token)],
    )

    # UMS Router (محمي بمصادقة المستخدم)
    app.include_router(
        ums_router.router,
        prefix="/api/v1",
        dependencies=[Depends(verify_service_token)],
    )

    return app


app = create_app()
