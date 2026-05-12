import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from app.core.domain.chat import CustomerConversation, CustomerMessage, MessageRole
from app.core.domain.user import User
from app.services.customer.chat_persistence import CustomerChatPersistence


@pytest_asyncio.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    SessionLocal = async_sessionmaker(  # noqa: N806
        autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def setup_test_user(async_db_session):
    user = User(
        email="test_immunity@example.com",
        username="test_immunity",
        full_name="Test Immunity User",
        password_hash="fake",
        is_active=True,
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_duplicate_guard_prevents_dual_write(async_db_session, setup_test_user):
    user = setup_test_user  # pytest fixture — already resolved, not a coroutine
    persistence = CustomerChatPersistence(async_db_session)

    conv = CustomerConversation(title="Immunity Test", user_id=user.id)
    async_db_session.add(conv)
    await async_db_session.commit()
    await async_db_session.refresh(conv)

    # First write (simulating orchestrator fail-safe or primary write)
    msg1 = await persistence.save_message(
        conv.id, MessageRole.ASSISTANT, "This is an immune system test response."
    )
    assert msg1.id is not None

    # Second write within window (simulating dual-write bug regression)
    msg2 = await persistence.save_message(
        conv.id, MessageRole.ASSISTANT, "This is an immune system test response."
    )

    # The guard should return the existing message instead of duplicating
    assert msg1.id == msg2.id

    # Verify no duplication occurred at the database level
    from sqlalchemy import select

    result = await async_db_session.execute(
        select(CustomerMessage).where(
            CustomerMessage.conversation_id == conv.id,
            CustomerMessage.role == MessageRole.ASSISTANT,
            CustomerMessage.content == "This is an immune system test response.",
        )
    )
    messages = result.scalars().all()
    assert len(messages) == 1
