import pytest
from pydantic_settings import SettingsConfigDict

pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from app.core.settings.base import BaseServiceSettings


class _TestSettings(BaseServiceSettings):
    SERVICE_NAME: str = "TestService"
    # Disable .env file loading so tests are not affected by the project .env
    model_config = SettingsConfigDict(env_file=None, extra="ignore")  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """ينظف متغيرات البيئة الحساسة لضمان اختبار موثوق."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("APP_DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)


def test_database_url_falls_back_in_development() -> None:
    # Development now requires explicit DATABASE_URL
    with pytest.raises(ValueError, match="DATABASE_URL is missing"):
        _TestSettings(ENVIRONMENT="development")


def test_database_url_missing_in_production_raises() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL is missing"):
        _TestSettings(ENVIRONMENT="production")


def test_production_settings_accept_strong_secret() -> None:
    settings = _TestSettings(
        ENVIRONMENT="production",
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        SECRET_KEY="s" * 64,
        DEBUG=False,
    )
    assert settings.is_production is True


def test_production_rejects_debug_true() -> None:
    with pytest.raises(ValueError, match="DEBUG must be False"):
        _TestSettings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            SECRET_KEY="s" * 64,
            DEBUG=True,
        )


def test_production_rejects_weak_secret() -> None:
    with pytest.raises(ValueError, match="SECRET_KEY is too weak"):
        _TestSettings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
            SECRET_KEY="changeme",
        )


def test_production_requires_explicit_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # monkeypatch.delenv already removes SECRET_KEY via autouse fixture.
    # This test just verifies the validator fires when SECRET_KEY is absent from env.
    with pytest.raises(ValueError, match="SECRET_KEY must be set"):
        _TestSettings(
            ENVIRONMENT="production",
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/db",
        )
