import os
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.core.database import create_db_engine, create_session_factory
from app.core.security import verify_password
from app.core.settings.base import BaseServiceSettings
from app.security.passwords import pwd_context

pytestmark = pytest.mark.asyncio


@pytest.fixture
def db_settings():
    db_url = os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///:memory:")

    return BaseServiceSettings(
        DATABASE_URL=db_url, ENVIRONMENT="testing", SERVICE_NAME="TestAuthChat"
    )


@pytest_asyncio.fixture
async def db_session(db_settings):
    engine = create_db_engine(db_settings)
    session_factory = create_session_factory(engine)

    # We must ensure tables exist in sqlite memory
    if "sqlite" in db_settings.DATABASE_URL:
        async with engine.begin() as conn:
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_name VARCHAR(150) NOT NULL,
                    email VARCHAR(150) NOT NULL UNIQUE,
                    password_hash VARCHAR(256),
                    is_active BOOLEAN DEFAULT 1
                );
            """)
            )
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS customer_conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title VARCHAR(500) NOT NULL,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            )
            await conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS customer_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES customer_conversations(id) ON DELETE CASCADE,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL
                );
            """)
            )

    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_auth_login_and_chat_creation(db_session):
    test_email = f"test_super_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "SuperSecretPassword123"

    # 1. Create a new user
    hashed_pw = pwd_context.hash(test_password)
    result = await db_session.execute(
        text("""
        INSERT INTO users (full_name, email, password_hash, is_active)
        VALUES (:name, :email, :pw, 1)
        RETURNING id;
        """),
        {"name": "Super Tester", "email": test_email, "pw": hashed_pw},
    )
    user_id = result.scalar_one()
    assert user_id is not None

    # 2. Test Login Authentication
    res = await db_session.execute(
        text("SELECT password_hash FROM users WHERE email = :email"), {"email": test_email}
    )
    db_hash = res.scalar_one()
    assert verify_password(test_password, db_hash) is True

    # 3. Create a chat conversation
    conv_res = await db_session.execute(
        text("""
        INSERT INTO customer_conversations (title, user_id)
        VALUES (:title, :uid)
        RETURNING id;
        """),
        {"title": "اختبار البحث الثوري", "uid": user_id},
    )
    conv_id = conv_res.scalar_one()
    assert conv_id is not None

    # 4. Send a message in the chat
    msg_res = await db_session.execute(
        text("""
        INSERT INTO customer_messages (conversation_id, role, content)
        VALUES (:cid, :role, :content)
        RETURNING id;
        """),
        {"cid": conv_id, "role": "user", "content": "أريد سؤال المتغير العشوائي من بكالوريا 2024"},
    )
    msg_id = msg_res.scalar_one()
    assert msg_id is not None

    # Clean up DB state created during test
    await db_session.rollback()
