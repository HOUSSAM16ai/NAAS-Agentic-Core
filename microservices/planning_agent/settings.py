"""
إعدادات وكيل التخطيط (Planning Agent).

تضمن هذه الإعدادات عمل الوكيل بشكل مستقل وقابل للتكوين.
"""

import functools
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class PlanningAgentSettings(BaseSettings):
    """
    إعدادات وكيل التخطيط بصورة مستقلة وبسيطة.
    """

    SERVICE_NAME: str = Field("planning-agent", description="اسم الوكيل")
    SERVICE_VERSION: str = Field("1.0.0", description="إصدار الوكيل")

    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = Field(
        "development", description="بيئة التشغيل"
    )
    DEBUG: bool = Field(False, description="تفعيل وضع التصحيح")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", description="مستوى السجلات"
    )

    DATABASE_URL: str = Field(
        "sqlite+aiosqlite:///./planning_agent.db",
        description="رابط قاعدة البيانات الخاصة بالوكيل",
    )

    # Security
    SECRET_KEY: str = Field(
        "super_secret_key_change_in_production",
        validation_alias="SECRET_KEY",
        description="مفتاح التشفير المشترك",
    )

    # AI Settings
    OPENROUTER_API_KEY: SecretStr | None = Field(None, description="مفتاح API لخدمة OpenRouter")
    AI_MODEL: str = Field(
        "nvidia/nemotron-3-nano-30b-a3b:free",
        description="اسم النموذج المستخدم في التخطيط",
    )
    AI_BASE_URL: str = Field(
        "https://openrouter.ai/api/v1",
        description="الرابط الأساسي لخدمة الذكاء الاصطناعي",
    )

    model_config = SettingsConfigDict(env_prefix="PLANNING_", env_file=".env", extra="ignore")


@functools.lru_cache(maxsize=1)
def get_settings() -> PlanningAgentSettings:
    """يبني إعدادات الوكيل مع تخزينها للاستخدام المتكرر."""
    return PlanningAgentSettings()
