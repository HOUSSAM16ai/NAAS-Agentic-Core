import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.domain.models import User


@pytest.mark.asyncio
async def test_admin_blocked_from_customer_chat(test_app, db_session: AsyncSession) -> None:
    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db

    admin_user = User(email="admin_branch@example.com", full_name="Admin", is_admin=True)
    admin_user.set_password("Secret123!")
    db_session.add(admin_user)
    await db_session.commit()

    transport = ASGITransport(app=test_app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login_resp = await ac.post(
                "/api/security/login",
                json={"email": "admin_branch@example.com", "password": "Secret123!"},
            )
            assert login_resp.status_code == 200
            token = login_resp.json()["access_token"]

            with TestClient(test_app) as client:
                from starlette.websockets import WebSocketDisconnect

                with pytest.raises(WebSocketDisconnect) as exc:
                    with client.websocket_connect(f"/api/chat/ws?token={token}") as websocket:
                        websocket.send_json({"question": "اشرح التكامل"})
                        websocket.receive_json()
                assert exc.value.code == 4403
    finally:
        test_app.dependency_overrides.clear()
