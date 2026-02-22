"""
إعدادات خدمة المستخدمين.

تعزل هذه الإعدادات الخدمة عن أي اعتماد مشترك مع بقية الخدمات.
"""

import functools
import os
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    """يوفّر أساس إعدادات الخدمة مع ضوابط أمان وتشغيل محلية."""

    SERVICE_NAME: str = Field(..., description="اسم الخدمة")
    SERVICE_VERSION: str = Field("0.1.0", description="إصدار الخدمة")

    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = Field(
        "development", description="بيئة التشغيل"
    )
    DEBUG: bool = Field(False, description="وضع التصحيح")

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", description="مستوى السجل"
    )

    DATABASE_URL: str | None = Field(None, description="رابط قاعدة البيانات")
    SECRET_KEY: str = Field("changeme", description="المفتاح السري")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> "BaseServiceSettings":
        """يتأكد من صحة إعدادات الأمان في بيئة الإنتاج."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production")
            if self.SECRET_KEY == "changeme" or len(self.SECRET_KEY) < 32:
                raise ValueError("SECRET_KEY must be strong in production")
        return self


class UserServiceSettings(BaseServiceSettings):
    """إعدادات خدمة المستخدمين مع قواعد تشغيل محلية مستقلة."""

    SERVICE_NAME: str = Field("user-service", description="اسم الخدمة")
    SERVICE_VERSION: str = Field("1.0.0", description="إصدار الخدمة")
    DATABASE_URL: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./user_service.db"),
        description="رابط قاعدة بيانات خدمة المستخدمين",
    )

    # Security Override (Ensure global SECRET_KEY is used)
    SECRET_KEY: str = Field(
        default_factory=lambda: os.getenv("SECRET_KEY", "super_secret_key_change_in_production"),
        validation_alias="SECRET_KEY",
        description="مفتاح التشفير المشترك",
    )

    model_config = SettingsConfigDict(
        env_prefix="USER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@functools.lru_cache(maxsize=1)
def get_settings() -> UserServiceSettings:
    """يبني إعدادات الخدمة مع التخزين المؤقت."""
    return UserServiceSettings()
