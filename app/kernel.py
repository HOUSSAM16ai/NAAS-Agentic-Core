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

D-260 (2026-08-15): تفكيك hotspot CodeScene X-Ray — هذه قشرةٌ تفويضٍ نصّية:
`__init__`(churn=18) · `_construct_app`(churn=7 · 50 LOC) · `_handle_lifespan_events`
(radon B(8) · churn=9 · Bumpy Road) · `_validate_contract_alignment` (radon B(7) ·
35 LOC · Complex Method). المنطق انتقل إلى حزمة شرائحٍ نقيةٍ بلا حالةٍ
`app/core/kernel_support/` (lifecycle · contracts · otel · compose) والمانيفست
المركّب `read_kernel_source()` يتغذى منه كل حاجزٍ نصي (runtime truth · العقيدة) —
صفر تغيير سلوكي، وكل استدعاءٍ قديمٍ بالاسم الأصلي يعمل بلا تعديل (late-binding D-252).
"""

import logging
import weakref
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING, Final

from fastapi import FastAPI

if TYPE_CHECKING:
    pass

from app.core.agents.system_principles import (
    validate_architecture_system_principles,
    validate_system_principles,
)
from app.core.app_blueprint import build_kernel_config, build_kernel_spec
from app.core.config import AppSettings
from app.core.kernel_state import apply_app_state, build_app_state
from app.core.kernel_support._sources import (
    KERNEL_SOURCE_FILES,
    read_kernel_source,
)
from app.core.kernel_support.compose import (
    _apply_middleware,
    _configure_static_files,
    _mount_routers,
)
from app.core.kernel_support.contracts import (
    _validate_contract_alignment,
    build_contract_violations,
)
from app.core.kernel_support.lifecycle import (
    _announce_startup_health,
    _start_messaging_relay,
    _stop_messaging_relay,
    run_shutdown_phase,
    run_startup_phase,
)
from app.core.kernel_support.otel import _bootstrap_otel_sdk, _instrument_app
from app.middleware.fastapi_error_handlers import add_error_handlers

logger = logging.getLogger(__name__)

__all__ = [
    # إعادة تصدير شرائح D-260 بالاسم الأصلي (late-binding D-252) —
    # أي monkeypatch/اختبار يستورد هذه الأسماء من `app.kernel` يظل فعالًا.
    "KERNEL_SOURCE_FILES",
    # RealityKernel — مُنفذ النظام (القشرة التفويضية D-260).
    "RealityKernel",
    "_announce_startup_health",
    "_apply_middleware",
    "_bootstrap_otel_sdk",
    "_configure_static_files",
    "_instrument_app",
    "_mount_routers",
    "_start_messaging_relay",
    "_stop_messaging_relay",
    "_validate_contract_alignment",
    "build_contract_violations",
    "read_kernel_source",
    "run_shutdown_phase",
    "run_startup_phase",
]


class RealityKernel:
    """
    نواة الواقع الإدراكي (Cognitive Reality Weaver).

    تعمل هذه الفئة الآن كـ "مُنسق" (Orchestrator) يقوم بتجميع التطبيق من خلال
    تطبيق دوال نقية على حالة النظام — كل منطقٍ انتقل إلى شرائح
    `app/core/kernel_support/` والقشرة تفوَّض فقط (D-260).
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
        self.kernel_config = build_kernel_config(
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
        بناء التطبيق باستخدام منهجية Pipeline — تفويضٌ كامل للشرائح (D-260).

        الخطوات:
        0. OpenTelemetry SDK bootstrap (no-op when stack absent)
        1. الحالة الأساسية (Base State)
        2. الحصول على المواصفات (Data Acquisition)
        3. تحويل الحالة (Transformations) - API Core فقط
        4. إعداد الواجهة الأمامية (Optional - منفصل عن API)
        5. عقود OpenAPI/AsyncAPI + per-app OTel instrumentation
        """
        # 0. OpenTelemetry SDK — قبل تغليف FastAPI حتى يرى FastAPIInstrumentor
        # التطبيق عند البناء. Hard no-op عند غياب OTEL_EXPORTER_OTLP_ENDPOINT.
        _bootstrap_otel_sdk(self.settings_obj.PROJECT_NAME)

        # 1. Base State
        app = self._create_base_app_instance()

        # 2. Data Acquisition (Pure)
        kernel_spec = build_kernel_spec(self.kernel_config)

        # 3. Transformations - API Core (100% API-First)
        app = _apply_middleware(app, kernel_spec.middleware_stack)
        add_error_handlers(app)  # Legacy helper
        app = _mount_routers(app, kernel_spec.router_registry)
        # 4. Static Files (Optional - Frontend Support)
        # Principle: API-First - يمكن تشغيل API بدون frontend
        # يتم الإعداد أخيراً لضمان عدم تداخل المسارات مع API
        app = _configure_static_files(app, kernel_spec.static_files_spec)
        # 5. Contract alignment (OpenAPI soft · AsyncAPI hard) + instrumentation
        _validate_contract_alignment(app)
        _instrument_app(app)

        return app

    def _create_base_app_instance(self) -> FastAPI:
        """إنشاء مثيل FastAPI الخام مع مدير دورة الحياة — تفويضٌ لشريحة lifecycle."""

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
        """معالجة أحداث النظام الحيوية — تفويضٌ كامل لشريحة lifecycle (D-260)."""
        messaging_relay = await run_startup_phase(self.settings_obj)
        try:
            yield
        finally:
            await run_shutdown_phase(messaging_relay)
