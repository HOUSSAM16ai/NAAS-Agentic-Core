"""
المخطط المعماري للنواة (Kernel Blueprint).

يحوّل الإعدادات إلى مواصفات تشغيلية صريحة وفق مسار:
Config -> AppState -> WeavedApp
مع الالتزام بالجوهر الوظيفي والقشرة الإجرائية.
"""

import os
from dataclasses import dataclass

from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routers.registry import RouterSpec, base_router_registry
from app.core.config import AppSettings
from app.middleware.observability.observability_middleware import ObservabilityMiddleware
from app.middleware.remove_blocking_headers import RemoveBlockingHeadersMiddleware
from app.middleware.security.rate_limit_middleware import RateLimitMiddleware
from app.middleware.security.security_headers import SecurityHeadersMiddleware

__all__ = [
    "BASE_CORS_OPTIONS",
    "KernelConfig",
    "KernelSpec",
    "MiddlewareSpec",
    "RouterSpec",
    "StaticFilesSpec",
    "build_cors_options",
    "build_kernel_config",
    "build_kernel_spec",
    "build_middleware_stack",
    "build_router_registry",
    "build_static_files_spec",
    "is_dev_environment",
    "normalize_settings",
]


type MiddlewareSpec = tuple[type[BaseHTTPMiddleware] | type, dict[str, object]]

BASE_CORS_OPTIONS: dict[str, object] = {
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],
    "allow_headers": [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
    "expose_headers": ["Content-Length", "Content-Range"],
}


@dataclass(frozen=True, slots=True)
class KernelConfig:
    """حاوية إعدادات النواة بشكل صريح وقابل للتمرير."""

    settings_obj: AppSettings
    settings_dict: dict[str, object]
    enable_static_files: bool


@dataclass(frozen=True, slots=True)
class KernelSpec:
    """مواصفات تشغيلية تُشتق من إعدادات النواة كبيانات."""

    config: KernelConfig
    middleware_stack: list[MiddlewareSpec]
    router_registry: list[RouterSpec]
    is_dev_environment: bool
    static_files_spec: "StaticFilesSpec"


@dataclass(frozen=True, slots=True)
class StaticFilesSpec:
    """مواصفات الملفات الثابتة كبيانات قابلة للتفسير."""

    enabled: bool
    serve_spa: bool


def normalize_settings(
    settings: AppSettings | dict[str, object],
) -> tuple[AppSettings, dict[str, object]]:
    """
    يطبع إعدادات التطبيق على شكل كائن وقاموس بطريقة موحدة.

    Args:
        settings: إعدادات التطبيق بصيغة كائن أو قاموس.

    Returns:
        tuple[AppSettings, dict[str, object]]: الكائن الكامل وقاموس القيم.
    """
    if isinstance(settings, dict):
        if "DATABASE_URL" not in settings and os.getenv("PYTEST_CURRENT_TEST"):
            settings = {**settings, "DATABASE_URL": "sqlite+aiosqlite:///:memory:"}
        settings_obj = AppSettings(**settings)
        settings_dict = settings_obj.model_dump()
        return settings_obj, settings_dict

    return settings, settings.model_dump()


def build_kernel_config(
    settings: AppSettings | dict[str, object],
    *,
    enable_static_files: bool,
) -> KernelConfig:
    """
    يبني حاوية إعدادات النواة ضمن مسار Config.

    Args:
        settings: إعدادات التطبيق بصيغة كائن أو قاموس.
        enable_static_files: تفعيل خدمة الملفات الثابتة.

    Returns:
        KernelConfig: حاوية الإعدادات.
    """
    settings_obj, settings_dict = normalize_settings(settings)
    return KernelConfig(
        settings_obj=settings_obj,
        settings_dict=settings_dict,
        enable_static_files=enable_static_files,
    )


def build_kernel_spec(
    config: KernelConfig,
) -> KernelSpec:
    """
    يبني مواصفات النواة التشغيلية وفق مسار AppState.

    Args:
        config: حاوية إعدادات النواة.

    Returns:
        KernelSpec: مواصفات التشغيل.
    """
    middleware_stack = build_middleware_stack(config.settings_obj)
    router_registry = build_router_registry()
    return KernelSpec(
        config=config,
        middleware_stack=middleware_stack,
        router_registry=router_registry,
        is_dev_environment=is_dev_environment(config.settings_dict),
        static_files_spec=build_static_files_spec(config),
    )


def build_middleware_stack(settings: AppSettings) -> list[MiddlewareSpec]:
    """
    تكوين قائمة البرمجيات الوسيطة كبيانات وصفية (Declarative Data).

    Args:
        settings: إعدادات التطبيق.

    Returns:
        list[MiddlewareSpec]: قائمة المواصفات.
    """
    cors_options = build_cors_options(settings.BACKEND_CORS_ORIGINS)

    stack: list[MiddlewareSpec] = [
        (TrustedHostMiddleware, {"allowed_hosts": settings.ALLOWED_HOSTS}),
        (CORSMiddleware, cors_options),
        (ObservabilityMiddleware, {}),
        (SecurityHeadersMiddleware, {}),
        (RemoveBlockingHeadersMiddleware, {}),
        (GZipMiddleware, {"minimum_size": 1000}),
    ]

    if settings.ENVIRONMENT != "testing":
        stack.insert(4, (RateLimitMiddleware, {}))

    return stack


def build_cors_options(origins: str | list[str]) -> dict[str, object]:
    """
    بناء خيارات CORS بشكل واضح ومتسق.

    D-WS-CODESPACES-001: Starlette CORSMiddleware لا تدعم wildcard subdomains
    (مثل https://*.app.github.dev) كـ literal strings — تُعامَل كنص حرفي ولا تُطابق.
    الحل: نُحوِّل الـ wildcard patterns إلى allow_origin_regex.

    Args:
        origins: قائمة الأصول المسموح بها (list أو CSV string).

    Returns:
        dict[str, object]: قاموس خيارات CORS الجاهز للاستخدام.
    """
    import re

    # D-WS-002: field_validator يُحوِّل str → list[str] قبل هذه الدالة،
    # لكن نُضيف guard دفاعياً لضمان list دائماً.
    if isinstance(origins, str):
        from app.core.settings.helpers import _normalize_csv_or_list

        origins = _normalize_csv_or_list(origins)

    allow_origins = origins or ["*"]
    options = dict(BASE_CORS_OPTIONS)

    # فصل الـ origins الحرفية عن الـ wildcard patterns
    # Starlette CORSMiddleware تدعم allow_origin_regex للـ patterns المعقدة
    literal_origins: list[str] = []
    regex_parts: list[str] = []

    for origin in allow_origins:
        if origin == "*":
            # allow_all_origins — نُمرِّره مباشرة
            literal_origins.append(origin)
        elif "*" in origin:
            # wildcard pattern مثل https://*.app.github.dev
            # نُحوِّله إلى regex: https://[^.]+.app.github.dev
            escaped = re.escape(origin).replace(r"\*", r"[^.]+(?:\.[^.]+)*")
            regex_parts.append(escaped)
        else:
            literal_origins.append(origin)

    options["allow_origins"] = literal_origins if literal_origins else ["*"]

    if regex_parts:
        # دمج كل الـ patterns في regex واحد
        combined_regex = "^(" + "|".join(regex_parts) + ")$"
        options["allow_origin_regex"] = combined_regex

    return options


def build_router_registry() -> list[RouterSpec]:
    """
    سجل الموجهات (Router Registry) كبيانات.

    Returns:
        list[RouterSpec]: قائمة (الموجه، البادئة).
    """
    return base_router_registry()


def build_static_files_spec(config: KernelConfig) -> StaticFilesSpec:
    """
    يبني مواصفات الملفات الثابتة ضمن سياق API-First.

    Args:
        config: حاوية إعدادات النواة.

    Returns:
        StaticFilesSpec: مواصفات الملفات الثابتة.
    """
    return StaticFilesSpec(
        enabled=config.enable_static_files,
        serve_spa=True,
    )


def is_dev_environment(settings_dict: dict[str, object]) -> bool:
    """يتحقق من أن البيئة تطويرية لتفعيل وثائق الـ API فقط حين الحاجة."""
    return settings_dict.get("ENVIRONMENT") == "development"
