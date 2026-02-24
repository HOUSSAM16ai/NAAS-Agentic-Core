"""
User Service Client.
Provides a typed interface to the User Service Microservice.
Decouples the Monolith from the Identity Provider.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Final

import httpx
import jwt

from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings

logger = logging.getLogger("user-service-client")

DEFAULT_USER_SERVICE_URL: Final[str] = "http://user-service:8003"


class UserServiceClient:
    """
    Client for interacting with the User Service.
    """

    def __init__(self, base_url: str | None = None) -> None:
        settings = get_settings()
        # Ensure we use the configuration from settings if available
        env_url = getattr(settings, "USER_SERVICE_URL", None)
        resolved_url = base_url or env_url or DEFAULT_USER_SERVICE_URL
        self.base_url = resolved_url.rstrip("/")
        self.config = HTTPClientConfig(
            name="user-service-client",
            timeout=10.0,  # Fail fast for auth
            max_connections=50,
        )
        self.secret_key = settings.SECRET_KEY

    async def _get_client(self) -> httpx.AsyncClient:
        return get_http_client(self.config)

    def _generate_service_token(self) -> str:
        """Generate a short-lived service token for internal communication."""
        payload = {
            "sub": "service-account",
            "role": "ADMIN",  # Service account has admin privileges
            "type": "service",
            "exp": datetime.now(datetime.UTC) + timedelta(minutes=5),
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    async def register_user(self, full_name: str, email: str, password: str) -> dict[str, Any]:
        """
        Register a new user via the User Service.
        """
        url = f"{self.base_url}/auth/register"
        payload = {
            "full_name": full_name,
            "email": email,
            "password": password,
        }

        client = await self._get_client()
        try:
            logger.info(f"Dispatching registration to User Service: {email}")
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Re-raise status errors (400, 401, etc.)
            logger.warning(f"User Service returned error for registration: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to register user via service: {e}", exc_info=True)
            raise

    async def login_user(
        self, email: str, password: str, user_agent: str | None = None, ip: str | None = None
    ) -> dict[str, Any]:
        """
        Authenticate user via the User Service.
        """
        url = f"{self.base_url}/auth/login"
        payload = {
            "email": email,
            "password": password,
        }
        headers = {}
        if user_agent:
            headers["User-Agent"] = user_agent

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service returned error for login: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to login user via service: {e}", exc_info=True)
            raise

    async def get_me(self, token: str) -> dict[str, Any]:
        """
        Get current user details using the token.
        """
        url = f"{self.base_url}/user/me"
        headers = {"Authorization": f"Bearer {token}"}

        client = await self._get_client()
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service returned error for get_me: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to get user via service: {e}", exc_info=True)
            raise

    async def verify_token(self, token: str) -> bool:
        """
        Verify if a token is valid.
        """
        url = f"{self.base_url}/token/verify"
        payload = {"token": token}

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("data", {}).get("valid", False)
        except Exception as e:
            logger.error(f"Failed to verify token via service: {e}")
            return False

    async def get_users(self) -> list[dict[str, Any]]:
        """
        Get list of users (Admin only).
        """
        url = f"{self.base_url}/admin/users"
        token = self._generate_service_token()
        headers = {"Authorization": f"Bearer {token}"}

        client = await self._get_client()
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            raise

    async def get_user_count(self) -> int:
        """
        Get total user count (Admin only).
        """
        try:
            users = await self.get_users()
            return len(users)
        except Exception as e:
            logger.error(f"Failed to get user count: {e}")
            raise

    async def update_profile(
        self, token: str, full_name: str | None = None, email: str | None = None
    ) -> dict[str, Any]:
        """Update current user profile."""
        url = f"{self.base_url}/users/me"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {}
        if full_name:
            payload["full_name"] = full_name
        if email:
            payload["email"] = email

        client = await self._get_client()
        try:
            response = await client.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to update profile: {e}", exc_info=True)
            raise

    async def change_password(
        self, token: str, current_password: str, new_password: str
    ) -> dict[str, Any]:
        """Change current user password."""
        url = f"{self.base_url}/users/me/change-password"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"current_password": current_password, "new_password": new_password}

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to change password: {e}", exc_info=True)
            raise

    async def forgot_password(self, email: str) -> dict[str, Any]:
        """Request password reset."""
        url = f"{self.base_url}/auth/password/forgot"
        payload = {"email": email}

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to request password reset: {e}", exc_info=True)
            raise

    async def reset_password(self, token: str, new_password: str) -> dict[str, Any]:
        """Reset password using token."""
        url = f"{self.base_url}/auth/password/reset"
        payload = {"token": token, "new_password": new_password}

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to reset password: {e}", exc_info=True)
            raise

    async def create_user_admin(
        self, token: str, full_name: str, email: str, password: str, is_admin: bool = False
    ) -> dict[str, Any]:
        """Admin create user."""
        url = f"{self.base_url}/admin/users"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "is_admin": is_admin,
        }

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to create user (admin): {e}", exc_info=True)
            raise

    async def update_user_status(self, token: str, user_id: int, status: str) -> dict[str, Any]:
        """Admin update user status."""
        url = f"{self.base_url}/admin/users/{user_id}/status"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"status": status}

        client = await self._get_client()
        try:
            response = await client.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to update user status: {e}", exc_info=True)
            raise

    async def assign_role(self, token: str, user_id: int, role_name: str) -> dict[str, Any]:
        """Admin assign role."""
        url = f"{self.base_url}/admin/users/{user_id}/roles"
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"role_name": role_name}

        client = await self._get_client()
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service error: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to assign role: {e}", exc_info=True)
            raise


# Singleton
user_service_client = UserServiceClient()
user_client = user_service_client  # Alias for backward compatibility
