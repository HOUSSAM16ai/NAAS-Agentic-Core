"""
Tests for User Service Authentication.
"""
import os
import pytest
from datetime import datetime, timedelta, UTC
import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

# Set environment variables for testing
os.environ["USER_DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
# Ensure this matches the secret used to sign the token
TEST_SECRET = "test-secret-key-for-ci-pipeline"
os.environ["USER_SECRET_KEY"] = TEST_SECRET
os.environ["USER_ENVIRONMENT"] = "testing"

from microservices.user_service.main import create_app
from microservices.user_service.database import init_db

@pytest.fixture(scope="module")
def service_token():
    return jwt.encode(
        {"sub": "api-gateway", "exp": datetime.now(UTC) + timedelta(hours=1)},
        TEST_SECRET,
        algorithm="HS256"
    )

@pytest.fixture(scope="module")
def client():
    # Patch init_db to avoid actual DB creation if needed, or rely on in-memory SQLite
    # Since we use :memory:, each connection is fresh, but with async session we need careful handling.
    # Ideally, we should use a session override.

    # For now, let's just create the app.
    app = create_app()
    with TestClient(app) as c:
        yield c

def test_register_flow(client, service_token):
    headers = {"X-Service-Token": service_token}

    # 1. Register
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "password123"
        },
        headers=headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["user"]["email"] == "test@example.com"

    # 2. Login
    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        },
        headers=headers
    )
    assert login_response.status_code == 200, login_response.text
    login_data = login_response.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == "test@example.com"

def test_token_generate_mock(client, service_token):
    headers = {"X-Service-Token": service_token}

    response = client.post(
        "/api/v1/auth/token/generate",
        json={"user_id": 123},
        headers=headers
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["access_token"] == "mock_token"

def test_missing_service_token(client):
    response = client.post(
        "/api/v1/auth/token/generate",
        json={"user_id": 123}
    )
    # Depending on DEBUG setting, might be 401 or allowed.
    # USER_ENVIRONMENT=testing usually implies DEBUG=False unless specified.
    # In settings.py: DEBUG: bool = Field(False...
    assert response.status_code == 401
