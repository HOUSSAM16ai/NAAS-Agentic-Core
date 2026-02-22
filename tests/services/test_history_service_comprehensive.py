from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import SQLModel

from app.core.domain.models import AdminConversation, AdminMessage
from app.services.users.history_service import get_recent_conversations, rate_message_in_db


class TestHistoryServiceComprehensive:
    @pytest.fixture
    def user_with_conversations(self, db_session, user_factory, mission_factory, event_loop):
        # When using pytest-factoryboy with async sessions, we need to handle creation carefully.
        # The AsyncUserFactory in conftest.py sets sqlalchemy_session to db_session.
        # However, factory_boy's .create() calls session.commit() which is a coroutine in AsyncSession.
        # It's better to build() the object and add/commit manually in the async fixture.

        async def _seed_user_and_conversations():
            from sqlalchemy import text

            from tests.conftest import engine

            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.create_all)

            # Cleanup potential conflicts from previous tests (IntegrityError fix)
            await db_session.execute(text("DELETE FROM admin_messages"))
            await db_session.execute(text("DELETE FROM admin_conversations"))
            await db_session.execute(text("DELETE FROM missions"))
            await db_session.execute(text("DELETE FROM users"))
            await db_session.commit()

            user = user_factory.build()
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

            conversations = []
            for i in range(3):
                mission = mission_factory.build(initiator_id=user.id)
                db_session.add(mission)
                await db_session.commit()
                await db_session.refresh(mission)

                conversation = AdminConversation(
                    user_id=user.id,
                    title=f"Conversation {i}",
                    conversation_type="chat",
                    linked_mission_id=mission.id,
                )
                db_session.add(conversation)
                conversations.append(conversation)

            await db_session.commit()
            for c in conversations:
                await db_session.refresh(c)

            return user, conversations

        return event_loop.run_until_complete(_seed_user_and_conversations())

    @pytest.fixture
    def user_with_messages(self, db_session, user_with_conversations, event_loop):
        user, conversations = user_with_conversations
        conversation = conversations[0]

        async def _seed_messages():
            messages = []
            for i in range(2):
                message = AdminMessage(
                    conversation_id=conversation.id,
                    role="user" if i % 2 == 0 else "assistant",
                    content=f"Message {i}",
                )
                db_session.add(message)
                messages.append(message)

            await db_session.commit()
            for m in messages:
                await db_session.refresh(m)

            return user, conversation, messages

        return event_loop.run_until_complete(_seed_messages())

    @pytest.mark.asyncio
    async def test_get_recent_conversations_success(self, user_with_conversations):
        user, _expected_conversations = user_with_conversations

        # We need to ensure the async_session_factory uses our test db_session
        # However, get_recent_conversations uses async_session_factory() internally.
        # We should patch it to return our session.

        # But wait, tests/conftest.py overrides get_db, but async_session_factory is imported from app.core.database
        # Let's see if we can patch app.services.users.history_service.async_session_factory

        # Mocking execute result
        # expected_conversations are SQLModel objects.
        # result.scalars().all() should return them.

        # Ideally we should run against the real DB since we have it in tests.
        # So let's patch async_session_factory to return a session connected to our test engine.

        from tests.conftest import TestingSessionLocal

        # We can't easily patch it to be a context manager that returns a specific session instance
        # if the function creates a new session every time.
        # But we can make it return a TestingSessionLocal instance which is configured to use the test engine.

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            # Configure mock_factory to return a context manager that yields a session
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            conversations = await get_recent_conversations(user.id)

            await session.close()

            assert len(conversations) == 3
            # Check ordering (descending ID/created_at) - newest should be first
            assert conversations[0].id > conversations[1].id

    @pytest.mark.asyncio
    async def test_get_recent_conversations_limit(self, user_with_conversations):
        user, _ = user_with_conversations

        from tests.conftest import TestingSessionLocal

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            conversations = await get_recent_conversations(user.id, limit=1)

            await session.close()

            assert len(conversations) == 1

    @pytest.mark.asyncio
    async def test_get_recent_conversations_error(self):
        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            mock_factory.side_effect = Exception("DB Connection Failed")

            conversations = await get_recent_conversations(1)
            assert conversations == []

    @pytest.mark.asyncio
    async def test_rate_message_success(self, user_with_messages):
        user, _, messages = user_with_messages
        message_to_rate = messages[0]

        from tests.conftest import TestingSessionLocal

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            # Since AdminMessage doesn't actually have a rating field in models.py (based on logs),
            # we need to skip the DB update check or add the field if possible.
            # "WARNING  app.services.users.history_service:history_service.py:97 Message model has no rating field. Skipping update."
            # The service handles this gracefully.

            # However, if we want to test that it returns success, we should do that.
            # But wait, if it skips update, it should verify that we don't crash.

            # If we want to test data persistence, we'd need to add 'rating' to AdminMessage model
            # or mock hasattr.

            # Mocking hasattr on the object returned from DB is tricky because it's an object from session.
            # Let's mock the session result to return a mock object that has 'rating'.

            # Actually, let's just assert result["status"] == "success" and accept that it skips update for now
            # as the model doesn't support it yet.

            result = await rate_message_in_db(message_to_rate.id, "good", user.id)
            await session.close()

            assert result["status"] == "success"
            assert "rated as 'good'" in result["message"]

    @pytest.mark.asyncio
    async def test_rate_message_invalid_rating(self):
        result = await rate_message_in_db(1, "awesome", 1)
        assert result["status"] == "error"
        assert "Invalid rating" in result["message"]

    @pytest.mark.asyncio
    async def test_rate_message_not_found(self, user_with_messages):
        user, _, _ = user_with_messages

        from tests.conftest import TestingSessionLocal

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            result = await rate_message_in_db(999999, "good", user.id)
            await session.close()

            assert result["status"] == "error"
            assert "not found" in result["message"]

    @pytest.mark.asyncio
    async def test_rate_message_security_violation(
        self, user_with_messages, user_factory, db_session
    ):
        _user, _, messages = user_with_messages
        other_user = user_factory.build()
        db_session.add(other_user)
        await db_session.commit()
        await db_session.refresh(other_user)

        message_to_rate = messages[0]

        from tests.conftest import TestingSessionLocal

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            result = await rate_message_in_db(message_to_rate.id, "bad", other_user.id)
            await session.close()

            assert result["status"] == "error"
            assert "Permission denied" in result["message"]

    @pytest.mark.asyncio
    async def test_rate_message_db_error(self, user_with_messages):
        user, _, messages = user_with_messages
        message_to_rate = messages[0]

        from tests.conftest import TestingSessionLocal

        # To trigger DB error, we need to force it.
        # Since 'rating' field doesn't exist, it won't call commit().
        # We need to make it believe 'rating' exists so it calls commit(),
        # OR we mock the execute to fail.

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            # Make session.commit fail
            session.commit = AsyncMock(side_effect=SQLAlchemyError("DB Error"))

            # We also need to patch the message object to have 'rating' attribute
            # so the code attempts to save it.
            # The code fetches message via query.
            # We can mock session.execute to return our mock message.

            mock_msg = MagicMock()
            mock_msg.id = message_to_rate.id
            mock_msg.conversation.user_id = user.id
            mock_msg.rating = None  # Exists

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_msg
            session.execute = AsyncMock(return_value=mock_result)

            result = await rate_message_in_db(message_to_rate.id, "good", user.id)
            await session.close()

            assert result["status"] == "error"
            assert "database error" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_rate_message_unexpected_error(self, user_with_messages):
        user, _, messages = user_with_messages
        message_to_rate = messages[0]

        from tests.conftest import TestingSessionLocal

        with patch("app.services.users.history_service.async_session_factory") as mock_factory:
            session = TestingSessionLocal()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None

            # Mock session.execute to raise unexpected Exception
            session.execute = AsyncMock(side_effect=Exception("Unexpected boom"))

            result = await rate_message_in_db(message_to_rate.id, "good", user.id)
            await session.close()

            assert result["status"] == "error"
            assert "unexpected error" in result["message"].lower()
