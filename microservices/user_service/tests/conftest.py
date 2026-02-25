from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.pool import StaticPool

if TYPE_CHECKING:
    from microservices.user_service.models import User


def _deduplicate_metadata_indexes() -> None:
    """يزيل الفهارس المكررة من SQLModel metadata لتجنب تعارض أسماء SQLite."""
    for table in SQLModel.metadata.tables.values():
        if not hasattr(table, "indexes"):
            continue
        unique_indexes: dict[str | None, object] = {}
        duplicate_indexes = []
        for index in list(table.indexes):
            index_name = getattr(index, "name", None)
            if index_name in unique_indexes:
                duplicate_indexes.append(index)
            else:
                unique_indexes[index_name] = index
        for duplicate in duplicate_indexes:
            table.indexes.remove(duplicate)


@pytest.fixture(name="session", scope="function")
def fixture_session(event_loop: asyncio.AbstractEventLoop) -> AsyncGenerator[AsyncSession, None]:
    """يوفر جلسة قاعدة بيانات غير متزامنة مع مخطط جاهز لكل اختبار."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    _deduplicate_metadata_indexes()

    async def _prepare_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    event_loop.run_until_complete(_prepare_schema())

    from sqlalchemy.orm import sessionmaker

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session_cm = async_session()
    session = event_loop.run_until_complete(session_cm.__aenter__())
    try:
        yield session
    finally:
        event_loop.run_until_complete(session_cm.__aexit__(None, None, None))
        event_loop.run_until_complete(engine.dispose())


@pytest.fixture(name="client")
def fixture_client(
    session: AsyncSession,
    event_loop: asyncio.AbstractEventLoop,
) -> AsyncGenerator[AsyncClient, None]:
    """يبني عميل HTTP للاختبار بعد حقن الاعتماديات الخاصة بالجلسة."""
    from microservices.user_service.main import app
    from microservices.user_service.security import get_auth_service, verify_service_token
    from microservices.user_service.settings import get_settings
    from microservices.user_service.src.services.auth.service import AuthService

    async def get_auth_service_override() -> AuthService:
        return AuthService(session)

    async def verify_service_token_override() -> bool:
        return True

    app.dependency_overrides[get_auth_service] = get_auth_service_override
    app.dependency_overrides[verify_service_token] = verify_service_token_override

    settings = get_settings()
    settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    settings.ENVIRONMENT = "testing"

    client_cm = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    client = event_loop.run_until_complete(client_cm.__aenter__())
    try:
        yield client
    finally:
        event_loop.run_until_complete(client_cm.__aexit__(None, None, None))
        app.dependency_overrides.clear()


@pytest.fixture
def admin_user(
    session: AsyncSession,
    event_loop: asyncio.AbstractEventLoop,
) -> User:
    """ينشئ مستخدمًا إداريًا مع جميع الصلاحيات المطلوبة لاختبارات الإدارة."""
    from microservices.user_service.src.services.auth.service import AuthService

    service = AuthService(session)

    async def _create_admin_user() -> User:
        await service.rbac.ensure_seed()
        user = await service.register_user(
            full_name="Admin User",
            email="admin@example.com",
            password="password123",
        )
        await service.promote_to_admin(user=user)
        return user

    return event_loop.run_until_complete(_create_admin_user())


@pytest.fixture
def admin_token(
    admin_user: User,
    session: AsyncSession,
    event_loop: asyncio.AbstractEventLoop,
) -> str:
    """يولد رمز وصول للمستخدم الإداري بهدف اختبار المسارات المحمية."""
    from microservices.user_service.src.services.auth.service import AuthService

    service = AuthService(session)

    async def _issue_token() -> str:
        tokens = await service.issue_tokens(admin_user)
        return tokens["access_token"]

    return event_loop.run_until_complete(_issue_token())
