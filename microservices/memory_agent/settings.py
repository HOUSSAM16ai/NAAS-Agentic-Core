"""
إعدادات وكيل الذاكرة (Memory Agent).

تضمن هذه الإعدادات استقلالية التخزين وعدم مشاركة قاعدة بيانات مركزية.
"""

import functools
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MemoryAgentSettings(BaseSettings):
    """
    إعدادات وكيل الذاكرة بصورة مستقلة وبسيطة.
    """

    SERVICE_NAME: str = Field("memory-agent", description="اسم الوكيل")
    SERVICE_VERSION: str = Field("1.0.0", description="إصدار الوكيل")

    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = Field(
        "development", description="بيئة التشغيل"
    )
    DEBUG: bool = Field(False, description="تفعيل وضع التصحيح")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        "INFO", description="مستوى السجلات"
    )

    DATABASE_URL: str = Field(
        "sqlite+aiosqlite:///./memory_agent.db",
        description="رابط قاعدة البيانات الخاصة بالوكيل",
    )

    # Security
    SECRET_KEY: str = Field(
        "super_secret_key_change_in_production",
        validation_alias="SECRET_KEY",
        description="مفتاح التشفير المشترك",
    )

    model_config = SettingsConfigDict(env_prefix="MEMORY_", env_file=".env", extra="ignore")


@functools.lru_cache(maxsize=1)
def get_settings() -> MemoryAgentSettings:
    """يبني إعدادات الوكيل مع تخزينها للاستخدام المتكرر."""
    return MemoryAgentSettings()
