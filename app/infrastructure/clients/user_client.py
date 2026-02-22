"""
User Service Client.
Provides a typed interface to the User Service.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Final

import httpx
import jwt
from pydantic import BaseModel, Field

from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings

logger = logging.getLogger("user-client")

DEFAULT_USER_SERVICE_URL: Final[str] = "http://user-service:8003"


# --- Local Schemas mirroring User Service ---


class UserResponse(BaseModel):
    id: int
    email: str
    name: str | None = None
    full_name: str | None = None
    is_admin: bool = False
    is_active: bool = True
    status: str = "active"
    permissions: list[str] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: UserResponse
    status: str = "success"
    landing_path: str = "/app/chat"


class RegisterResponse(BaseModel):
    status: str
    message: str
    user: UserResponse


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"


class PasswordResetResponse(BaseModel):
    status: str
    reset_token: str | None = None
    expires_in: int | None = None


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    status: str
    roles: list[str] = []


class UserServiceClient:
    """
    Client for interacting with the User Service Microservice.
    Handles Auth and UMS operations.
    """

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        # Prefer settings, fall back to arg, then default
        resolved_url = settings.USER_SERVICE_URL or base_url or DEFAULT_USER_SERVICE_URL
        self.base_url = resolved_url.rstrip("/")
        self.config = HTTPClientConfig(
            name="user-service-client",
            timeout=30.0,
            max_connections=100,
        )

    def _get_service_token(self) -> str:
        """Generate a service token for internal communication."""
        settings = get_settings()
        payload = {
            "sub": "api-gateway",
            "iat": datetime.datetime.now(datetime.UTC),
            "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=5),
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    async def _get_client(self) -> httpx.AsyncClient:
        return await get_http_client(self.config)

    def _get_headers(self, token: str | None = None) -> dict[str, str]:
        headers = {
            "X-Service-Token": self._get_service_token(),
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def health_check(self) -> dict[str, Any]:
        url = f"{self.base_url}/health"
        client = await self._get_client()
        # Health usually doesn't need auth, but if protected:
        resp = await client.get(url, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    # --- Auth Operations ---

    async def register(self, full_name: str, email: str, password: str) -> RegisterResponse:
        url = f"{self.base_url}/api/v1/auth/register"
        payload = {"full_name": full_name, "email": email, "password": password}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers())
        resp.raise_for_status()
        return RegisterResponse(**resp.json())

    async def login(
        self, email: str, password: str, user_agent: str | None = None, ip: str | None = None
    ) -> AuthResponse:
        url = f"{self.base_url}/api/v1/auth/login"
        payload = {"email": email, "password": password}
        headers = self._get_headers()
        if user_agent:
            headers["User-Agent"] = user_agent

        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=headers)
        if resp.status_code == 401:
            # Raise specific exception or let caller handle httpx error
            pass
        resp.raise_for_status()
        return AuthResponse(**resp.json())

    async def get_me(self, token: str) -> UserResponse:
        url = f"{self.base_url}/api/v1/auth/user/me"
        client = await self._get_client()
        resp = await client.get(url, headers=self._get_headers(token))
        resp.raise_for_status()
        return UserResponse(**resp.json())

    async def verify_token(self, token: str) -> dict[str, Any]:
        url = f"{self.base_url}/api/v1/auth/token/verify"
        payload = {"token": token}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    async def refresh_token(self, refresh_token: str) -> TokenPair:
        url = f"{self.base_url}/api/v1/auth/refresh"
        payload = {"refresh_token": refresh_token}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers())
        resp.raise_for_status()
        return TokenPair(**resp.json())

    async def logout(self, refresh_token: str) -> dict[str, str]:
        url = f"{self.base_url}/api/v1/auth/logout"
        payload = {"refresh_token": refresh_token}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    # --- UMS Operations ---

    async def update_me(
        self, token: str, full_name: str | None = None, email: str | None = None
    ) -> UserOut:
        url = f"{self.base_url}/api/v1/users/me"
        payload = {}
        if full_name:
            payload["full_name"] = full_name
        if email:
            payload["email"] = email

        client = await self._get_client()
        resp = await client.patch(url, json=payload, headers=self._get_headers(token))
        resp.raise_for_status()
        return UserOut(**resp.json())

    async def change_password(self, token: str, current_pass: str, new_pass: str) -> dict[str, str]:
        url = f"{self.base_url}/api/v1/users/me/change-password"
        payload = {"current_password": current_pass, "new_password": new_pass}

        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers(token))
        resp.raise_for_status()
        return resp.json()

    async def request_password_reset(self, email: str) -> PasswordResetResponse:
        url = f"{self.base_url}/api/v1/auth/password/forgot"
        payload = {"email": email}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers())
        resp.raise_for_status()
        return PasswordResetResponse(**resp.json())

    async def reset_password(self, token: str, new_password: str) -> dict[str, str]:
        url = f"{self.base_url}/api/v1/auth/password/reset"
        payload = {"token": token, "new_password": new_password}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers())
        resp.raise_for_status()
        return resp.json()

    # --- Admin Operations ---

    async def list_users(self, token: str) -> list[UserOut]:
        url = f"{self.base_url}/api/v1/admin/users"
        client = await self._get_client()
        resp = await client.get(url, headers=self._get_headers(token))
        resp.raise_for_status()
        return [UserOut(**u) for u in resp.json()]

    async def create_user_admin(
        self, token: str, full_name: str, email: str, password: str, is_admin: bool = False
    ) -> UserOut:
        url = f"{self.base_url}/api/v1/admin/users"
        payload = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "is_admin": is_admin,
        }
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers(token))
        resp.raise_for_status()
        return UserOut(**resp.json())

    async def update_user_status(self, token: str, user_id: int, status: str) -> UserOut:
        url = f"{self.base_url}/api/v1/admin/users/{user_id}/status"
        payload = {"status": status}
        client = await self._get_client()
        resp = await client.patch(url, json=payload, headers=self._get_headers(token))
        resp.raise_for_status()
        return UserOut(**resp.json())

    async def assign_role(
        self, token: str, user_id: int, role_name: str, justification: str | None = None
    ) -> UserOut:
        url = f"{self.base_url}/api/v1/admin/users/{user_id}/roles"
        payload = {"role_name": role_name, "justification": justification}
        client = await self._get_client()
        resp = await client.post(url, json=payload, headers=self._get_headers(token))
        resp.raise_for_status()
        return UserOut(**resp.json())

    async def get_user_count(self) -> int:
        # Legacy support / Fallback
        url = f"{self.base_url}/users/count"
        client = await self._get_client()
        resp = await client.get(url, headers=self._get_headers())
        if resp.status_code == 404:
            return 0
        resp.raise_for_status()
        data = resp.json()
        return data.get("count", 0) if isinstance(data, dict) else 0


# Singleton
user_service_client = UserServiceClient()
user_client = user_service_client
