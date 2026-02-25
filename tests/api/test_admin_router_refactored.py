import uuid
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.models import AdminConversation, AdminMessage, User

# Use existing fixtures from conftest.py
# 'test_app' fixture creates the app and sets up overrides
# 'db_session' fixture provides the async session


@pytest.fixture
def local_admin_user(db_session: AsyncSession, event_loop):
    """إنشاء مستخدم إداري محلي للاختبارات التكاملية."""

    @dataclass(slots=True)
    class LocalAdminIdentity:
        """يمثل هوية مسؤول محلية خفيفة لاختبارات المسارات الإدارية."""

        id: int

    async def _create_user() -> LocalAdminIdentity:
        unique_email = f"refactor_admin_{uuid.uuid4().hex}@test.com"
        user = User(email=unique_email, full_name="Refactor Admin", is_admin=True)
        user.set_password("password")
        insert_statement = text(
            """
            INSERT INTO users (
                external_id,
                full_name,
                email,
                password_hash,
                is_admin,
                is_active,
                status
            )
            VALUES (:external_id, :full_name, :email, :password_hash, :is_admin, :is_active, :status)
            """
        )
        result = await db_session.execute(
            insert_statement,
            {
                "external_id": str(uuid.uuid4()),
                "full_name": user.full_name,
                "email": unique_email,
                "password_hash": user.password_hash,
                "is_admin": True,
                "is_active": True,
                "status": "active",
            },
        )
        await db_session.commit()
        return LocalAdminIdentity(id=int(result.lastrowid))

    return event_loop.run_until_complete(_create_user())


@pytest.fixture
def client(test_app, local_admin_user, event_loop):
    """تهيئة عميل HTTP غير متزامن مع حقن هوية المسؤول."""

    from app.api.routers.admin import get_current_user_id

    test_app.dependency_overrides[get_current_user_id] = lambda: local_admin_user.id

    client_cm = AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")
    client_instance = event_loop.run_until_complete(client_cm.__aenter__())

    try:
        yield client_instance
    finally:
        event_loop.run_until_complete(client_cm.__aexit__(None, None, None))
        if get_current_user_id in test_app.dependency_overrides:
            del test_app.dependency_overrides[get_current_user_id]


@pytest.mark.asyncio
async def test_get_latest_chat_integration(client, db_session: AsyncSession, local_admin_user):
    # 1. Setup Data
    conv = AdminConversation(user_id=local_admin_user.id, title="Test Conv")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg = AdminMessage(conversation_id=conv.id, role="user", content="Hello")
    db_session.add(msg)
    await db_session.commit()

    # 2. Call API (Auth is patched via dependency_override in fixture)
    response = await client.get("/admin/api/chat/latest")

    # 3. Verify
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["conversation_id"] == conv.id
    assert data["title"] == "Test Conv"
    assert len(data["messages"]) == 1
    assert data["messages"][0]["content"] == "Hello"


@pytest.mark.asyncio
async def test_list_conversations_integration(client, db_session: AsyncSession, local_admin_user):
    # 1. Setup Data
    conv1 = AdminConversation(user_id=local_admin_user.id, title="Conv 1")
    conv2 = AdminConversation(user_id=local_admin_user.id, title="Conv 2")
    db_session.add_all([conv1, conv2])
    await db_session.commit()

    # 2. Call API
    response = await client.get("/admin/api/conversations")

    # 3. Verify
    assert response.status_code == 200, response.text
    data = response.json()
    # Filter by our user in case other tests left data
    user_convs = [c for c in data if c["title"] in ["Conv 1", "Conv 2"]]
    # The order might not be guaranteed or might be by date, so check containment
    titles = [c["title"] for c in user_convs]
    assert "Conv 1" in titles
    assert "Conv 2" in titles


@pytest.mark.asyncio
async def test_get_conversation_details_integration(
    client, db_session: AsyncSession, local_admin_user
):
    # 1. Setup Data
    conv = AdminConversation(user_id=local_admin_user.id, title="Specific Conv")
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    msg = AdminMessage(conversation_id=conv.id, role="assistant", content="Response")
    db_session.add(msg)
    await db_session.commit()

    # 2. Call API
    response = await client.get(f"/admin/api/conversations/{conv.id}")

    # 3. Verify
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["conversation_id"] == conv.id
    assert data["messages"][0]["content"] == "Response"
