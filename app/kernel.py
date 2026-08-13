"""
نواة الواقع الإدراكي (Reality Kernel) - 100% API-First.

هذا الملف يمثل القلب النابض للنظام (The Beating Heart) ومُنفذ (Evaluator) التطبيق.
يعتمد منهجية SICP (جامعة بيركلي) في التركيب الوظيفي (Functional Composition) وفصل التجريد.

المبدأ الأساسي: API-First Architecture
- النواة تركز 100% على API endpoints
- Frontend (static files) اختياري ومنفصل تماماً
- يمكن تشغيل النظام بدون frontend (API-only mode)
- Separation of Concerns: API Core لا يعرف شيئاً عن UI

المعايير المطبقة (Standards Applied):
- SICP: حواجز التجريد (Abstraction Barriers)، البيانات ككود (Code as Data).
- CS50 2025: صرامة النوع والتوثيق (Type Strictness & Documentation).
- SOLID: مبادئ التصميم القوي (Robust Design).
- API-First: النظام يعمل بشكل مستقل عن UI.
"""

import logging
import weakref
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Final

from fastapi import FastAPI

if TYPE_CHECKING:
    from app.services.messaging.relay import RelayHandle

from app.core.agents.system_principles import (
    validate_architecture_system_principles,
    validate_system_principles,
)
from app.core.app_blueprint import (
    KernelConfig,
    KernelSpec,
    MiddlewareSpec,
    RouterSpec,
    StaticFilesSpec,
    build_kernel_config,
    build_kernel_spec,
)
from app.core.asyncapi_contracts import (
    default_asyncapi_contract_path,
    validate_asyncapi_contract_structure,
)
from app.core.config import AppSettings
from app.core.database import async_session_factory
from app.core.db_health import probe_database_connection
from app.core.db_schema import validate_schema_on_startup
from app.core.kernel_state import apply_app_state, build_app_state
from app.core.openapi_contracts import (
    compare_contract_to_runtime,
    default_contract_path,
    load_contract_operations,
)
from app.core.providers_health import probe_providers_health
from app.core.redis_bus import get_redis_bridge
from app.middleware.fastapi_error_handlers import add_error_handlers
from app.middleware.static_files_middleware import StaticFilesConfig, setup_static_files_middleware
from app.services.bootstrap import bootstrap_admin_account
from app.telemetry.unified_observability import get_unified_observability

logger = logging.getLogger(__name__)

__all__ = ["RealityKernel"]


def _apply_middleware(app: FastAPI, stack: list[MiddlewareSpec]) -> FastAPI:
    """
    Combinator: تطبيق قائمة الميدل وير على التطبيق.
    """
    # Starlette يطبق الميدل وير بنمط LIFO، لذا نعكس القائمة للحفاظ على ترتيب الإعلان FIFO.
    for mw_cls, mw_options in reversed(stack):
        app.add_middleware(mw_cls, **mw_options)
    return app


def _mount_routers(app: FastAPI, registry: list[RouterSpec]) -> FastAPI:
    """
    Combinator: ربط الموجهات بالتطبيق.
    """
    for router, prefix in registry:
        app.include_router(router, prefix=prefix)
    return app


def _configure_static_files(app: FastAPI, spec: StaticFilesSpec) -> FastAPI:
    """يضبط خدمة الملفات الثابتة بشكل صريح مع احترام وضع API-only."""

    if spec.enabled:
        static_config = StaticFilesConfig(
            enabled=True,
            serve_spa=spec.serve_spa,
        )
        setup_static_files_middleware(app, static_config)
    else:
        logger.info("🚀 Running in API-only mode (no static files)")
    return app


# ==============================================================================
# The Evaluator (مُنفذ النظام)
# ==============================================================================


class RealityKernel:
    """
    نواة الواقع الإدراكي (Cognitive Reality Weaver).

    تعمل هذه الفئة الآن كـ "مُنسق" (Orchestrator) يقوم بتجميع التطبيق من خلال
    تطبيق دوال نقية على حالة النظام.
    """

    def __init__(
        self,
        *,
        settings: AppSettings | dict[str, object],
        enable_static_files: bool = False,
    ) -> None:
        """
        تهيئة النواة.

        Args:
            settings (AppSettings | dict[str, object]): الإعدادات.
            enable_static_files (bool): تفعيل خدمة الملفات الثابتة (افتراضي: False).
                                       يمكن تعطيله لوضع API-only.
        """
        validate_system_principles()
        validate_architecture_system_principles()
        self.kernel_config: KernelConfig = build_kernel_config(
            settings,
            enable_static_files=enable_static_files,
        )
        self.settings_obj: AppSettings = self.kernel_config.settings_obj
        self.settings_dict: dict[str, object] = self.kernel_config.settings_dict

        # بناء التطبيق فور الإنشاء
        self.app: Final[FastAPI] = self._construct_app()

    def get_app(self) -> FastAPI:
        """يعيد التطبيق النهائي بعد إتمام عملية البناء."""
        return self.app

    def _construct_app(self) -> FastAPI:
        """
        بناء التطبيق باستخدام منهجية Pipeline.

        الخطوات:
        1. الحالة الأساسية (Base State)
        2. الحصول على المواصفات (Data Acquisition)
        3. تحويل الحالة (Transformations) - API Core فقط
        4. إعداد الواجهة الأمامية (Optional - منفصل عن API)
        5. OpenTelemetry SDK bootstrap (no-op when stack absent)
        """
        # 0. OpenTelemetry SDK — must be set up BEFORE FastAPI is wrapped so
        # the FastAPIInstrumentor sees the app at construction. The function
        # is a hard no-op when OTEL_EXPORTER_OTLP_ENDPOINT is unset, so
        # nothing changes for default Codespaces.
        try:
            from app.telemetry.otel_setup import setup_otel

            setup_otel(service_name=self.settings_obj.PROJECT_NAME or "cogniforge-monolith")
        except Exception:
            logger.debug("otel_setup invocation failed at kernel boot", exc_info=True)

        # 1. Base State
        app = self._create_base_app_instance()

        # 2. Data Acquisition (Pure)
        kernel_spec: KernelSpec = build_kernel_spec(
            self.kernel_config,
        )

        # 3. Transformations - API Core (100% API-First)
        app = _apply_middleware(app, kernel_spec.middleware_stack)
        add_error_handlers(app)  # Legacy helper
        app = _mount_routers(app, kernel_spec.router_registry)
        # 4. Static Files (Optional - Frontend Support)
        # Principle: API-First - يمكن تشغيل API بدون frontend
        # يتم الإعداد أخيراً لضمان عدم تداخل المسارات مع API
        app = _configure_static_files(app, kernel_spec.static_files_spec)
        _validate_contract_alignment(app)

        # 5. Per-app OTel instrumentation — wraps every route/middleware so
        # spans land in Tempo. No-op when OTel was not initialized in step 0.
        try:
            from app.telemetry.otel_setup import instrument_fastapi_app

            instrument_fastapi_app(app)
        except Exception:
            logger.debug("instrument_fastapi_app invocation failed", exc_info=True)

        return app

    def _create_base_app_instance(self) -> FastAPI:
        """
        إنشاء مثيل FastAPI الخام مع مدير دورة الحياة.
        """

        kernel_ref: weakref.ReferenceType[RealityKernel] = weakref.ref(self)

        @asynccontextmanager
        async def lifespan(fastapi_app: FastAPI) -> AsyncGenerator[None, None]:
            """Lifecycle Manager Closure."""
            kernel = kernel_ref()
            if kernel is None:
                raise RuntimeError("RealityKernel reference is unavailable during lifespan.")
            lifecycle_events = kernel._handle_lifespan_events()
            await anext(lifecycle_events)
            apply_app_state(fastapi_app, build_app_state())
            try:
                yield
            finally:
                with suppress(StopAsyncIteration):
                    await anext(lifecycle_events)

        is_dev = self.settings_obj.ENVIRONMENT == "development"

        return FastAPI(
            title=self.settings_obj.PROJECT_NAME,
            version=self.settings_obj.VERSION,
            docs_url="/docs" if is_dev else None,
            redoc_url="/redoc" if is_dev else None,
            lifespan=lifespan,
        )

    async def _handle_lifespan_events(self) -> AsyncGenerator[None, None]:
        """
        معالجة أحداث النظام الحيوية.
        """
        logger.info("🚀 CogniForge System Initializing... (Strict Mode Active)")
        observability = get_unified_observability()
        redis_bridge = get_redis_bridge()

        # D-245 (2026-08-13): مجسّات صادقة عند الإقلاع — بلاها، بيئةٌ محجوبةٌ
        # عنها قاعدة البيانات (GitHub Codespaces — منفذا Supabase محجوبان) تبدأ
        # بكلّ شيءٍ أخضر بينما تموت كل عمليةٍ تعتمد على DB: "login failed" ·
        # لا رسائل · لا إجابات. يُضغط في دالةٍ واحدةٍ لتجنّب PLR0915.
        await _announce_startup_health()

        try:
            await validate_schema_on_startup()
            logger.info("✅ Database Schema Validated")
        except Exception:
            logger.warning("⚠️ Schema validation warning", exc_info=True)

        try:
            async with async_session_factory() as session:
                await bootstrap_admin_account(session, settings=self.settings_obj)
                logger.info("✅ Admin account bootstrapped and validated")
        except Exception:
            logger.exception("❌ Failed to bootstrap admin account")

        # Start Observability Sync (Metric Stream to Microservice)
        try:
            await observability.start_background_sync()
            logger.info("✅ Unified Observability Sync Started")
        except Exception:
            logger.warning("⚠️ Failed to start observability sync", exc_info=True)

        # Start Redis Event Bridge (Streaming BFF)
        try:
            await redis_bridge.start()
        except Exception:
            logger.warning("⚠️ Failed to start Redis Event Bridge", exc_info=True)

        # D-201 — ناقل الأحداث: تسجيل المشتركين ثمّ إطلاق حلقة الاستهلاك.
        # الترتيب مقصود: حلقةٌ تبدأ قبل التسجيل تسحب أحداثاً بلا مستهلك فتُسقِطها.
        messaging_relay = await _start_messaging_relay()

        # Pre-warm LangGraph local engine (catches import errors at startup)
        try:
            from app.services.chat.local_graph import get_local_graph

            get_local_graph()
            logger.info("✅ LangGraph local engine initialized")
        except Exception:
            logger.warning("⚠️ LangGraph local engine failed to initialize", exc_info=True)

        logger.info("✅ System Ready")
        try:
            yield
        finally:
            # Stop the messaging relay first: a consumer still draining while the
            # database session factory is torn down logs failures that mean nothing.
            await _stop_messaging_relay(messaging_relay)

            # Shutdown Redis Event Bridge
            try:
                await redis_bridge.stop()
            except Exception:
                logger.warning("⚠️ Failed to stop Redis Event Bridge", exc_info=True)

            # Stop Observability Sync
            try:
                await observability.stop_background_sync()
                logger.info("✅ Unified Observability Sync Stopped")
            except Exception:
                logger.warning("⚠️ Failed to stop observability sync", exc_info=True)

            logger.info("👋 CogniForge System Shutting Down...")


async def _start_messaging_relay() -> "RelayHandle | None":
    """
    يُقلع حلقة الرسائل (D-201) — استيرادٌ كسول فلا تتحمّل النواة تبعية الناقل.

    الفشل هنا لا يمنع الإقلاع: الناقل تابعٌ لا أصل، ودورُ الطالب يعمل بدونه.
    """
    try:
        from app.services.messaging.relay import RelayHandle

        relay = RelayHandle()
        await relay.start()
        logger.info("✅ Messaging relay started")
        return relay
    except Exception:
        logger.warning("⚠️ Failed to start messaging relay", exc_info=True)
        return None


async def _stop_messaging_relay(relay: "RelayHandle | None") -> None:
    """يوقف حلقة الرسائل. آمنٌ إن لم تُقلع."""
    if relay is None:
        return
    try:
        await relay.stop()
        logger.info("✅ Messaging relay stopped")
    except Exception:
        logger.warning("⚠️ Failed to stop messaging relay", exc_info=True)


def _validate_contract_alignment(app: FastAPI) -> None:
    """يتحقق من تطابق مخطط التشغيل مع عقد OpenAPI الأساسي."""

    spec_path = default_contract_path()
    contract_operations = load_contract_operations(spec_path)
    if not contract_operations:
        logger.warning("⚠️ لم يتم العثور على عقد OpenAPI للتحقق من التوافق.")
    else:
        report = compare_contract_to_runtime(
            contract_operations=contract_operations,
            runtime_schema=app.openapi(),
        )
        if report.is_clean():
            logger.info("✅ Contract alignment verified against runtime schema.")
        else:
            violations: list[str] = []
            if report.missing_paths:
                missing_paths = sorted(report.missing_paths)
                violations.append(f"missing_paths={missing_paths}")
                logger.error("❌ مسارات العقد غير موجودة في التشغيل: %s", missing_paths)

            if report.missing_operations:
                summary = {
                    path: sorted(methods) for path, methods in report.missing_operations.items()
                }
                violations.append(f"missing_operations={summary}")
                logger.error("❌ عمليات العقد غير موجودة في التشغيل: %s", summary)

            logger.warning("⚠️ OpenAPI contract validation failed: %s", "; ".join(violations))

    asyncapi_report = validate_asyncapi_contract_structure(default_asyncapi_contract_path())
    if not asyncapi_report.is_clean():
        raise ValueError(
            "AsyncAPI contract validation failed: " + "; ".join(asyncapi_report.errors)
        )


async def _announce_startup_health() -> None:
    """D-245 (2026-08-13): إعلانٌ صادقٌ لصحة قاعدة البيانات والمزودين عند الإقلاع.

    بدون هذا الإعلان كانت بيئةٌ محجوبةٌ عن قاعدة البيانات (GitHub Codespaces —
    منفذا Supabase 6543/5432 محجوبان حسب CLAUDE.md) تبدأ بكلّ شيءٍ أخضر
    بينما تموت كل عمليةٍ تعتمد على DB: "login failed" · لا رسائل محفوظة ·
    لا إجابات — ولا أي إشارةٍ معلنةٍ تسبق أول فشلٍ (ISS-163).
    """
    db_status = await probe_database_connection()
    if db_status == "ok":
        logger.info("✅ Database connectivity live at startup")
    else:
        logger.error(
            "❌ DATABASE UNREACHABLE AT STARTUP — health endpoints MUST NOT "
            "claim healthy; every DB operation (login / persistence / chat "
            "answers) will fail until connectivity is restored. See D-245."
        )
    providers = probe_providers_health()
    if providers.llm_provider == "missing":
        logger.error(
            "❌ LLM PROVIDER MISSING AT STARTUP — the chat engine will refuse "
            "every question with «🛑 خطأ في التكوين: مفتاح الذكاء الاصطناعي "
            "مفقود». اضبط OPENROUTER_API_KEY أو OPENAI_API_KEY في Secrets "
            "البيئة. See D-245."
        )
    else:
        logger.info("✅ LLM provider configured (%s)", providers.llm_detail)
