"""مساعدات قراءة معلومات البيئة لمعرفة المشروع."""

from microservices.orchestrator_service.src.core.config import AppSettings


def build_environment_info(settings: AppSettings) -> dict[str, object]:
    """يبني قاموس معلومات البيئة بدون كشف الأسرار الحساسة."""
    codespaces = settings.CODESPACES
    gitpod = bool(_read_env("GITPOD_WORKSPACE_ID"))
    ai_configured = bool(_read_env("OPENROUTER_API_KEY"))
    supabase_configured = bool(_read_env("SUPABASE_URL"))

    return {
        "environment": settings.ENVIRONMENT,
        "debug_mode": settings.DEBUG,
        "database_configured": bool(settings.DATABASE_URL),
        "ai_configured": ai_configured,
        "supabase_configured": supabase_configured,
        "runtime": {
            "codespaces": codespaces,
            "gitpod": gitpod,
            "local": not (codespaces or gitpod),
        },
    }


def _read_env(key: str) -> str | None:
    """يقرأ متغير البيئة المطلوب دون أي معالجة إضافية."""
    import os

    return os.getenv(key)
