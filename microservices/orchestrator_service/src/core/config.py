from pydantic_settings import BaseSettings
import os
from typing import Optional

class AppSettings(BaseSettings):
    PROJECT_NAME: str = "Orchestrator Service"
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    PLANNING_AGENT_URL: str = "http://localhost:8000"
    RESEARCH_AGENT_URL: str = "http://localhost:8003"
    MEMORY_AGENT_URL: str = "http://localhost:8004"
    REASONING_AGENT_URL: str = "http://localhost:8005"
    REDIS_URL: str = "redis://localhost:6379/0"
    ENVIRONMENT: str = "testing"
    OPENAI_API_KEY: Optional[str] = "test_key"
    OPENROUTER_API_KEY: Optional[str] = "test_key"
    AI_MODEL: str = "test-model"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]
    CODESPACES: bool = False
    GITPOD_WORKSPACE_ID: str = ""
    DEBUG: bool = False
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SECRET_KEY: str = "test-secret-key-for-ci-pipeline-secure-length"

    class Config:
        env_file = ".env"

def get_settings():
    return AppSettings()

settings = AppSettings()
