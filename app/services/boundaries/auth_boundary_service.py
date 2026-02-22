"""
خدمة حدود المصادقة (Auth Boundary Service).

تمثل هذه الخدمة الواجهة الموحدة (Facade) لعمليات المصادقة، حيث تقوم بتنسيق منطق الأعمال
بين طبقة العرض (Router) وطبقة البيانات (Persistence).

المعايير المطبقة (Standards Applied):
- CS50 2025: توثيق عربي احترافي، صرامة في الأنواع.
- SOLID: فصل المسؤوليات (Separation of Concerns).
- Security First: تكامل مع درع الدفاع الزمني (Chrono-Kinetic Defense Shield).
"""

from __future__ import annotations

import logging

import httpx
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.clients.user_client import user_service_client
from app.security.chrono_shield import chrono_shield

logger = logging.getLogger(__name__)

__all__ = ["AuthBoundaryService"]


class AuthBoundaryService:
    """
    خدمة حدود المصادقة (Auth Boundary Service).

    المسؤوليات:
    - تنسيق عمليات تسجيل الدخول والتسجيل.
    - إدارة الرموز المميزة (JWT Management) عبر الخدمة المصغرة.
    - حماية النظام باستخدام درع كرونو (Chrono Shield Integration).
    """

    def __init__(self, db: AsyncSession | None = None) -> None:
        """
        تهيئة خدمة المصادقة.

        Args:
            db (AsyncSession): جلسة قاعدة البيانات (مهملة بعد الانتقال للخدمات المصغرة).
        """
        self.settings = get_settings()

    async def register_user(self, full_name: str, email: str, password: str) -> dict[str, object]:
        """
        تسجيل مستخدم جديد في النظام عبر خدمة المستخدمين.
        """
        try:
            resp = await user_service_client.register(full_name, email, password)
            return {
                "status": resp.status,
                "message": resp.message,
                "user": resp.user.model_dump(),
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:  # User Service returns 400 for existing email?
                # Check detail
                detail = e.response.json().get("detail", "")
                if "already registered" in str(detail) or "exists" in str(detail):
                    raise HTTPException(status_code=400, detail="Email already registered") from e
            raise e
        except Exception as e:
            logger.error(f"Registration failed: {e}")
            raise HTTPException(status_code=500, detail="Registration service unavailable") from e

    async def authenticate_user(
        self, email: str, password: str, request: Request
    ) -> dict[str, object]:
        """
        المصادقة على المستخدم وإصدار رمز الدخول (JWT) عبر خدمة المستخدمين.
        محمية بواسطة درع الدفاع الزمني.
        """
        # 0. تفعيل درع الدفاع الزمني
        await chrono_shield.check_allowance(request, email)

        try:
            resp = await user_service_client.login(
                email,
                password,
                user_agent=request.headers.get("User-Agent"),
                ip=request.client.host if request.client else None,
            )

            # نجاح: إعادة تعيين مستوى التهديد
            chrono_shield.reset_target(email)

            return {
                "access_token": resp.access_token,
                "token_type": resp.token_type,
                "user": resp.user.model_dump(),
                "status": resp.status,
                "landing_path": resp.landing_path,
            }

        except Exception as e:
            # تسجيل الأثر الحركي للفشل
            chrono_shield.record_failure(request, email)
            # التحقق الشبحي (محاكاة التأخير المحلي إذا لزم الأمر، لكن الشبكة تضيف تأخيراً أصلاً)
            # chrono_shield.phantom_verify(password)
            logger.warning(f"Failed login attempt for {email}: {e}")
            raise HTTPException(status_code=401, detail="Invalid email or password") from e

    async def get_current_user(self, token: str) -> dict[str, object]:
        """
        جلب بيانات المستخدم الحالي من رمز JWT عبر خدمة المستخدمين.
        """
        try:
            resp = await user_service_client.get_me(token)
            return resp.model_dump()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise HTTPException(status_code=401, detail="Invalid token") from e
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="User not found") from e
            raise e
        except Exception as e:
            logger.error(f"Get user failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid token or service error") from e

    @staticmethod
    def extract_token_from_request(request: Request) -> str:
        """
        استخراج رمز JWT من ترويسة التفويض.
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authorization header missing")

        parts = auth_header.split(" ")
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid Authorization header format")
        return parts[1]
