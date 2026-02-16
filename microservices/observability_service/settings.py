"""
إعدادات خدمة المراقبة.

تحافظ على استقلالية الخدمة وسهولة تهيئتها.
"""

import functools
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    """إعدادات خدمة المراقبة بصورة مستقلة وبسيطة."""

    SERVICE_NAME: str = Field("observability-service", description="اسم الخدمة")
    SERVICE_VERSION: str = Field("1.0.0", description="إصدار الخدمة")

    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = Field(
        "development", description="بيئة التشغيل"
    )
    DEBUG: bool = Field(False, description="تفعيل وضع التصحيح")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", description="مستوى السجلات"
    )

    # Security Override
    SECRET_KEY: str = Field(
        "super_secret_key_change_in_production",
        validation_alias="SECRET_KEY",
        description="مفتاح التشفير المشترك",
    )

    model_config = SettingsConfigDict(env_prefix="OBSERVABILITY_", env_file=".env", extra="ignore")


@functools.lru_cache(maxsize=1)
def get_settings() -> ObservabilitySettings:
    """يبني إعدادات الخدمة مع التخزين المؤقت."""

    return ObservabilitySettings()
