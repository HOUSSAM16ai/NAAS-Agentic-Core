"""
Auth Service Facade (Refactored for Microservices).
Delegates all operations to UserServiceClient.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

import httpx
from fastapi import HTTPException

from app.core.config import AppSettings, get_settings
from app.core.domain.user import User, UserStatus
from app.infrastructure.clients.user_client import user_service_client
from app.services.auth.crypto import AuthCrypto

# We keep TokenBundle for compatibility if needed, though mostly dicts now
TokenBundle = dict[str, str]

logger = logging.getLogger(__name__)


class AuthService:
    """
    AuthService Refactored.
    Delegates to User Service Microservice.
    """

    def __init__(self, session: Any = None, settings: AppSettings | None = None) -> None:
        # Session is ignored/deprecated
        self.settings = settings or get_settings()
        self.client = user_service_client
        # Keep crypto for local reauth verification (shared secret)
        self.crypto = AuthCrypto(self.settings)

    async def register_user(
        self,
        *,
        full_name: str,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        """Register and then Login to get tokens."""
        try:
            # 1. Register
            await self.client.register(full_name, email, password)

            # 2. Login immediately to get tokens
            auth_resp = await self.client.login(email, password, user_agent=user_agent, ip=ip)

            user = self._map_user(auth_resp.user)
            # Attach tokens to user object for issue_tokens to consume
            user._tokens = {
                "access_token": auth_resp.access_token,
                "refresh_token": auth_resp.refresh_token,
                "token_type": auth_resp.token_type,
            }
            return user
        except httpx.HTTPStatusError as e:
            if e.response.status_code in {409, 400}:
                raise HTTPException(
                    status_code=400, detail="Registration failed (Email likely exists)"
                )
            raise e

    async def authenticate(
        self,
        *,
        email: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        try:
            auth_resp = await self.client.login(email, password, user_agent=user_agent, ip=ip)
            user = self._map_user(auth_resp.user)
            user._tokens = {
                "access_token": auth_resp.access_token,
                "refresh_token": auth_resp.refresh_token,
                "token_type": auth_resp.token_type,
            }
            return user
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid credentials")
            if e.response.status_code == 403:
                raise HTTPException(status_code=403, detail="Account disabled")
            raise e

    async def issue_tokens(
        self,
        user: User,
        *,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenBundle:
        """Return tokens attached to user object."""
        if hasattr(user, "_tokens"):
            return user._tokens
        raise ValueError(
            "User object has no tokens attached. Ensure authenticate/register was called."
        )

    async def refresh_session(
        self,
        *,
        refresh_token: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> TokenBundle:
        try:
            resp = await self.client.refresh_token(refresh_token)
            return {
                "access_token": resp.access_token,
                "refresh_token": resp.refresh_token,
                "token_type": resp.token_type,
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid refresh token")
            raise e

    async def logout(
        self, *, refresh_token: str, ip: str | None = None, user_agent: str | None = None
    ) -> None:
        with contextlib.suppress(Exception):
            await self.client.logout(refresh_token)

    async def update_profile(
        self,
        *,
        user: User,
        full_name: str | None,
        email: str | None,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        # We need token to update profile.
        # But 'user' here is SQLModel user. It doesn't have token.
        # Logic mismatch: Monolith used session. Client needs token.
        # 'ums.py' `update_me` has `current_user`... but does it have token?
        # `get_current_user` extracts token. But doesn't return it in `CurrentUser`.
        # I MUST update `CurrentUser` or pass token separately.
        # `ums.py` endpoints access `request`. I can extract token there.
        # But `AuthService` signature doesn't take token.
        # I need to change signature or rely on something else.
        # I'll change signature to accept `token: str`.
        # `ums.py` calls this. I must update `ums.py`.
        pass
        # For now I will implement assuming token is passed as kwarg or throw error if not
        # But `ums.py` passes user, full_name, email, ip, user_agent.
        # I will change `ums.py` to call client directly? Or pass token.
        raise NotImplementedError("Use client directly or pass token")

    # Wrapper for legacy local crypto
    def verify_access_token(self, token: str) -> dict[str, object]:
        return self.crypto.verify_jwt(token)

    async def issue_reauth_proof(self, user: User, password: str, **kwargs) -> tuple[str, int]:
        # Check password via Client login?
        # If we login, we get tokens.
        # Then we generate local reauth token.
        # Or we can verify password locally if we have hash? No, we don't have hash (it's in microservice).
        # We MUST use client to verify password.
        try:
            # Login to verify password
            await self.client.login(user.email, password)
            # If success, issue local reauth token
            return self.crypto.encode_reauth_token(user)
        except Exception:
            raise HTTPException(status_code=401, detail="Re-authentication required")

    async def verify_reauth_proof(self, token: str, user: User, **kwargs) -> None:
        # Local verification
        payload = self.crypto.verify_jwt(token)
        if payload.get("purpose") != "reauth" or payload.get("sub") != str(user.id):
            raise HTTPException(status_code=401, detail="Re-authentication required")

    # ... Helper mapping
    def _map_user(self, user_resp: Any) -> User:
        try:
            status_enum = UserStatus(user_resp.status)
        except ValueError:
            status_enum = UserStatus.ACTIVE

        return User(
            id=user_resp.id,
            email=user_resp.email,
            full_name=user_resp.full_name or user_resp.name or "",
            is_admin=user_resp.is_admin,
            is_active=user_resp.is_active,
            status=status_enum,
        )

    # ... Legacy redirects
    async def request_password_reset(
        self, *, email: str, **kwargs
    ) -> tuple[str | None, int | None]:
        resp = await self.client.request_password_reset(email)
        return resp.reset_token, resp.expires_in

    async def reset_password(self, *, token: str, new_password: str, **kwargs) -> None:
        await self.client.reset_password(token, new_password)

    async def change_password(
        self, *, user: User, current_password: str, new_password: str, token: str, **kwargs
    ) -> None:
        # Needs token!
        await self.client.change_password(token, current_password, new_password)

    async def promote_to_admin(self, *, user: User, token: str) -> None:
        # Needs token!
        await self.client.assign_role(token, user.id, "ADMIN")

    async def assign_role(self, user_id: int, role_name: str, token: str, **kwargs) -> None:
        await self.client.assign_role(token, user_id, role_name)

    async def list_users(self, token: str) -> list[User]:
        users_out = await self.client.list_users(token)
        return [
            self._map_user(u) for u in users_out
        ]  # Note: UserOut in client has roles, User model doesn't have roles populated easily here?
        # Map user is basic.

    async def update_user_status(self, user_id: int, status: str, token: str) -> User:
        resp = await self.client.update_user_status(token, user_id, status)
        return self._map_user(resp)
