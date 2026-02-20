import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock heavy dependencies before importing app
sys.modules["redis"] = MagicMock()

mock_redis_module = MagicMock()
mock_redis_client = MagicMock()
mock_redis_client.close = AsyncMock()
mock_redis_module.from_url.return_value = mock_redis_client
sys.modules["redis.asyncio"] = mock_redis_module

sys.modules["dspy"] = MagicMock()
sys.modules["langgraph"] = MagicMock()
sys.modules["llama_index"] = MagicMock()
sys.modules["llama_index.core"] = MagicMock()
sys.modules["microservices.orchestrator_service.src.services.overmind.factory"] = MagicMock()
sys.modules["microservices.orchestrator_service.src.services.overmind.entrypoint"] = MagicMock()

# Set required environment variables
os.environ["SECRET_KEY"] = "test-secret-key"
# Use the correct validation alias and sqlite driver
os.environ["ORCHESTRATOR_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from microservices.orchestrator_service.main import app
from microservices.orchestrator_service.src.core.database import get_db
from microservices.orchestrator_service.src.core.event_bus import event_bus
from microservices.orchestrator_service.src.models.mission import Mission, MissionStatus

# Patch event_bus.redis.close to be awaitable
event_bus.redis.close = AsyncMock()

# Setup Async DB for testing
engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
TestingSessionLocal = sessionmaker(expire_on_commit=False, class_=AsyncSession, bind=engine)

@pytest.fixture(scope="function")
async def async_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

@pytest.fixture(scope="function")
def client(async_db):
    async def override_get_db():
        yield async_db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_and_list_missions(client, async_db):
    # 1. List - should be empty initially
    response = client.get("/missions")
    assert response.status_code == 200
    assert response.json() == []

    # 2. Create Mission
    # Mocking start_mission to avoid complex logic, or just let it fail if it depends on other services?
    # start_mission uses EventBus and potentially other things.
    # Ideally we mock start_mission logic in routes, or just test the route logic if we can.

    # Let's try to insert a mission directly into DB to test GET /missions list logic
    # because creating a mission involves background tasks and event bus which might be complex to mock fully here.

    mission = Mission(
        objective="Test Mission",
        initiator_id=1,
        status=MissionStatus.PENDING
    )
    async_db.add(mission)
    await async_db.commit()
    await async_db.refresh(mission)

    # 3. List again
    response = client.get("/missions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["objective"] == "Test Mission"
    assert data[0]["id"] == mission.id

@pytest.mark.asyncio
async def test_get_mission_detail(client, async_db):
    mission = Mission(
        objective="Detail Mission",
        initiator_id=1,
        status=MissionStatus.RUNNING
    )
    async_db.add(mission)
    await async_db.commit()
    await async_db.refresh(mission)

    response = client.get(f"/missions/{mission.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["objective"] == "Detail Mission"
    assert data["status"] == "running"
