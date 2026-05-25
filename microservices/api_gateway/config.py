from __future__ import annotations

import os
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """إعدادات بوابة الواجهات مع ضوابط صارمة لاكتشاف الخدمات وحماية الإنتاج."""

    # Service URLs (Defaults for local development/Docker Compose)
    PLANNING_AGENT_URL: str = "http://planning-agent:8001"
    MEMORY_AGENT_URL: str = "http://memory-agent:8002"
    USER_SERVICE_URL: str = "http://user-service:8003"
    OBSERVABILITY_SERVICE_URL: str = "http://observability-service:8005"
    RESEARCH_AGENT_URL: str = "http://research-agent:8007"
    REASONING_AGENT_URL: str = "http://reasoning-agent:8008"
    ORCHESTRATOR_SERVICE_URL: str = "http://orchestrator-service:8006"
    CONVERSATION_SERVICE_URL: str = "http://conversation-service:8010"
    CORE_KERNEL_URL: str | None = None

    # Deployment profile
    ENVIRONMENT: str = "development"
    # str type avoids pydantic-settings v2 DotEnvSettingsSource failing on CSV values.
    # Use the `allowed_hosts` / `cors_origins` properties for the parsed lists.
    ALLOWED_HOSTS: str = Field(default="*")
    BACKEND_CORS_ORIGINS: str = Field(default="*")
    ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR: bool = False

    # Per-route cutover flags (Phase 0 defaults keep behavior unchanged)
    ROUTE_CHAT_HTTP_CONVERSATION_ROLLOUT_PERCENT: int = 0
    ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT: int = 0

    # Safety gate: conversation service cannot receive critical traffic before parity proof.
    CONVERSATION_PARITY_VERIFIED: bool = True
    CONVERSATION_CAPABILITY_LEVEL: str = "stub"

    # Candidate target for WS cutover (kept disabled by default in PR#1)
    CONVERSATION_WS_URL: str = "ws://conversation-service:8010"

    # Gateway Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "CogniForge API Gateway"
    SECRET_KEY: str = "super_secret_key_change_in_production"

    # Resiliency Settings
    CONNECT_TIMEOUT: float = 5.0
    READ_TIMEOUT: float = 60.0
    WRITE_TIMEOUT: float = 60.0
    POOL_LIMIT: int = 100

    # Circuit Breaker Settings
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: float = 30.0

    # Retry Settings
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 0.5

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )

    @field_validator("ALLOWED_HOSTS", "BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _parse_csv_or_json(cls, v: object) -> str:
        """يُعيد القيمة كـ str — التحويل إلى list يتم عبر الـ properties."""
        if isinstance(v, list):
            return ",".join(v)
        return str(v) if v is not None else "*"

    @property
    def allowed_hosts(self) -> list[str]:
        """يُحوِّل ALLOWED_HOSTS إلى قائمة — يقبل JSON أو فواصل."""
        v = self.ALLOWED_HOSTS.strip()
        if v.startswith("["):
            import json
            return json.loads(v)
        return [x.strip() for x in v.split(",") if x.strip()]

    @property
    def cors_origins(self) -> list[str]:
        """يُحوِّل BACKEND_CORS_ORIGINS إلى قائمة — يقبل JSON أو فواصل."""
        v = self.BACKEND_CORS_ORIGINS.strip()
        if v.startswith("["):
            import json
            return json.loads(v)
        return [x.strip() for x in v.split(",") if x.strip()]

    @staticmethod
    def _is_container_runtime() -> bool:
        """يكشف بيئات الحاويات/العنقود لمنع localhost كوجهة بين الخدمات دون تصريح."""
        return (
            os.path.exists("/.dockerenv")
            or os.getenv("KUBERNETES_SERVICE_HOST") is not None
            or os.getenv("CONTAINER") == "true"
        )

    @model_validator(mode="after")
    def validate_security_and_discovery(self) -> Settings:
        """يفرض الأمان في الإنتاج ويمنع drift في ORCHESTRATOR_SERVICE_URL داخل الحاويات."""
        env = self.ENVIRONMENT.lower()
        if env in {"production", "staging"}:
            if (
                self.SECRET_KEY == "super_secret_key_change_in_production"
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError("SECRET_KEY غير آمن لبيئة production/staging")
            if self.allowed_hosts == ["*"]:
                raise ValueError("ALLOWED_HOSTS لا يمكن أن تكون '*' في production/staging")
            if self.cors_origins == ["*"]:
                raise ValueError("BACKEND_CORS_ORIGINS لا يمكن أن تكون '*' في production/staging")

        rollout_requested = (
            self.ROUTE_CHAT_HTTP_CONVERSATION_ROLLOUT_PERCENT > 0
            or self.ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT > 0
        )
        if rollout_requested and not self.CONVERSATION_PARITY_VERIFIED:
            raise ValueError(
                "Conversation rollout > 0 requires CONVERSATION_PARITY_VERIFIED=true to prevent accidental cutover to a parity stub."
            )

        capability = self.CONVERSATION_CAPABILITY_LEVEL.lower().strip()
        allowed_capabilities = {"parity_ready", "production_eligible"}
        if rollout_requested and capability not in allowed_capabilities:
            raise ValueError(
                "Conversation rollout > 0 requires CONVERSATION_CAPABILITY_LEVEL in {parity_ready, production_eligible}."
            )

        host = (urlparse(self.ORCHESTRATOR_SERVICE_URL).hostname or "").lower()
        if (
            host in {"localhost", "127.0.0.1"}
            and self._is_container_runtime()
            and not self.ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR
        ):
            raise ValueError(
                "ORCHESTRATOR_SERVICE_URL يشير إلى localhost داخل حاوية. "
                "استخدم DNS داخلياً مثل orchestrator-service أو فعّل المتغير "
                "ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR صراحة في التطوير المحلي فقط."
            )

        return self


settings = Settings()
