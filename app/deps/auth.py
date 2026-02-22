"""
تبعيات المصادقة والتفويض لمسارات FastAPI.

تفصل هذه الوحدة منطق استخراج الرموز والتحقق من الأدوار عن الموجهات
لضمان إعادة الاستخدام والاختبار السهل مع توثيق عربي موحّد.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from fastapi import Depends, HTTPException, Request, status

from app.core.config import get_settings
from app.core.database import get_db
from app.core.domain.user import User, UserStatus
from app.infrastructure.clients.user_client import user_service_client
from app.services.auth import AuthService


@dataclass
class CurrentUser:
    """تمثيل المستخدم الحالي مع الأدوار والصلاحيات."""

    user: User
    roles: list[str]
    permissions: set[str]


async def get_auth_service(db=Depends(get_db)) -> AuthService:
    return AuthService(db, get_settings())


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization")
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing"
        )
    return header.split(" ", maxsplit=1)[1]


async def get_current_user(
    request: Request,
) -> CurrentUser:
    token = _extract_bearer_token(request)
    try:
        user_resp = await user_service_client.get_me(token)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token or expired session"
            )
        raise e
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Auth service unavailable: {e}",
        )

    if not user_resp.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")

    # Convert status str to Enum safely
    try:
        status_enum = UserStatus(user_resp.status)
    except ValueError:
        status_enum = UserStatus.ACTIVE

    user = User(
        id=user_resp.id,
        email=user_resp.email,
        full_name=user_resp.full_name or user_resp.name or "",
        is_admin=user_resp.is_admin,
        is_active=user_resp.is_active,
        status=status_enum,
    )

    return CurrentUser(
        user=user,
        roles=user_resp.roles,
        permissions=set(user_resp.permissions),
    )


def require_roles(*roles: str):
    async def dependency(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(current.roles).intersection(set(roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return current

    return dependency


def require_permissions(*permissions: str):
    async def dependency(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not set(permissions).issubset(current.permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing permissions")
        return current

    return dependency


def require_permissions_or_admin(*permissions: str):
    """تبعيات تفويض تمنح استثناءً للمستخدمين الإداريين مع احترام الصلاحيات الصريحة.

    Args:
        *permissions: قائمة الصلاحيات المطلوب تحققها.

    Returns:
        CurrentUser: كائن المستخدم الحالي بعد التحقق من الصلاحيات أو صفة الإداري.

    Raises:
        HTTPException: في حال غياب الصلاحيات المطلوبة لمستخدم غير إداري.
    """

    async def dependency(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current.user.is_admin:
            return current

        if not set(permissions).issubset(current.permissions):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing permissions")

        return current

    return dependency


def reauth_dependency():
    async def dependency(
        request: Request,
        current: CurrentUser = Depends(get_current_user),
        auth_service: AuthService = Depends(get_auth_service),
    ) -> CurrentUser:
        token = request.headers.get("X-Reauth-Token")
        password = request.headers.get("X-Reauth-Password")
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        if token:
            await auth_service.verify_reauth_proof(
                token,
                user=current.user,
                ip=client_ip,
                user_agent=user_agent,
            )
            return current

        if password and current.user.check_password(password):
            return current

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Re-authentication required"
        )

    return dependency
