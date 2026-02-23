"""
خدمة حدود المصادقة (Auth Boundary Service).

تمثل هذه الخدمة الواجهة الموحدة (Facade) لعمليات المصادقة، حيث تقوم بتنسيق منطق الأعمال
بين طبقة العرض (Router) وطبقة البيانات (Persistence).

المعايير المطبقة (Standards Applied):
- CS50 2025: توثيق عربي احترافي، صرامة في الأنواع.
- SOLID: فصل المسؤوليات (Separation of Concerns).
- Security First: تكامل مع درع الدفاع الزمني (Chrono-Kinetic Defense Shield).
- Microservices First: استخدام خدمة المستخدمين (User Service) مع خطة طوارئ (Fallback).
"""

from __future__ import annotations

import datetime
from datetime import timezone
import logging
import os

import httpx
import jwt
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.infrastructure.clients.user_client import user_service_client
from app.security.chrono_shield import chrono_shield
from app.services.rbac import STANDARD_ROLE, RBACService
from app.services.security.auth_persistence import AuthPersistence

logger = logging.getLogger(__name__)

__all__ = ["AuthBoundaryService"]


class AuthBoundaryService:
    """
    خدمة حدود المصادقة (Auth Boundary Service).

    المسؤوليات:
    - تنسيق عمليات تسجيل الدخول والتسجيل.
    - إدارة الرموز المميزة (JWT Management).
    - حماية النظام باستخدام درع كرونو (Chrono Shield Integration).
    - الوكيل (Proxy) لخدمة المستخدمين المصغرة (User Service).
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        تهيئة خدمة المصادقة.

        Args:
            db (AsyncSession): جلسة قاعدة البيانات غير المتزامنة.
        """
        self.db = db
        self.persistence = AuthPersistence(db)
        self.settings = get_settings()

    def _strict_microservice_auth_enabled(self) -> bool:
        """تحديد وضع المصادقة الصارم عبر الخدمات المصغّرة فقط."""
        configured = bool(getattr(self.settings, "AUTH_MICROSERVICE_ONLY", True))
        environment = str(getattr(self.settings, "ENVIRONMENT", "development"))
        explicit_env_override = os.getenv("AUTH_MICROSERVICE_ONLY")
        if environment == "testing" and explicit_env_override is None:
            return False
        return configured


    @staticmethod
    def _as_dict(payload: object) -> dict[str, object]:
        """تحويل الحمولة الواردة إلى قاموس بشكل آمن."""
        if isinstance(payload, dict):
            return payload
        return {}

    @staticmethod
    def _pick_user_name(user_data: dict[str, object]) -> str | None:
        """استخراج اسم المستخدم بشكل متوافق مع صيغ الاستجابة المختلفة."""
        raw_name = user_data.get("full_name") or user_data.get("name")
        if isinstance(raw_name, str):
            normalized = raw_name.strip()
            return normalized or None
        return None

    def _normalize_user_payload(
        self,
        user_data: dict[str, object],
        fallback_email: str | None = None,
        fallback_name: str | None = None,
    ) -> dict[str, object]:
        """توحيد بنية المستخدم بين المونوليث والخدمة المصغّرة دون كسر التوافق."""
        email_value = user_data.get("email")
        remote_email = email_value if isinstance(email_value, str) else ""
        email = remote_email or (fallback_email or "")

        resolved_name = self._pick_user_name(user_data)
        if not resolved_name and fallback_name:
            fallback_name_clean = fallback_name.strip()
            resolved_name = fallback_name_clean or None
        if not resolved_name:
            resolved_name = email.split("@", maxsplit=1)[0] if "@" in email else "Unknown User"

        return {
            "id": user_data.get("id"),
            "name": resolved_name,
            "email": email,
            "is_admin": bool(user_data.get("is_admin", False)),
        }

    async def register_user(self, full_name: str, email: str, password: str) -> dict[str, object]:
        """
        تسجيل مستخدم جديد في النظام.

        يحاول استخدام خدمة المستخدمين (User Service) أولاً.
        في حال فشل الاتصال، يعود لاستخدام النظام المحلي (Monolith).

        Args:
            full_name (str): الاسم الكامل.
            email (str): البريد الإلكتروني.
            password (str): كلمة المرور.

        Returns:
            dict[str, object]: تفاصيل العملية والمستخدم المسجل.

        Raises:
            HTTPException: في حال وجود البريد الإلكتروني مسبقاً (400).
        """
        # محاولة التسجيل عبر الخدمة المصغرة (Microservice)
        try:
            response = await user_service_client.register_user(full_name, email, password)
            # تحويل استجابة الخدمة إلى التنسيق المتوقع محلياً
            # response format: {"user": {...}, "message": "..."}
            user_data = self._as_dict(response.get("user", {}))
            normalized_user = self._normalize_user_payload(
                user_data,
                fallback_email=email,
                fallback_name=full_name,
            )
            return {
                "status": "success",
                "message": response.get("message", "User registered successfully"),
                "user": {
                    "id": normalized_user["id"],
                    "full_name": normalized_user["name"],
                    "email": normalized_user["email"],
                    "is_admin": normalized_user["is_admin"],
                },
            }
        except httpx.HTTPStatusError as e:
            # إذا رفضت الخدمة الطلب (مثلاً البريد موجود)، نرفع الخطأ كما هو
            # باستثناء الحالات التي تدل غالباً على عدم جاهزية الخدمة أو رفض على مستوى البوابة
            # (مثل 401/403/5xx) حيث ننتقل إلى الخطة المحلية البديلة.
            logger.warning(f"User Service rejected registration: {e}")
            if e.response.status_code == 400:
                raise HTTPException(status_code=400, detail="Email already registered") from e
            if e.response.status_code not in {401, 403, 404, 429} and e.response.status_code < 500:
                raise HTTPException(status_code=e.response.status_code, detail=str(e)) from e
            if self._strict_microservice_auth_enabled():
                raise HTTPException(status_code=503, detail="Authentication service unavailable") from e
            logger.error(
                "User Service registration endpoint unavailable (%s), using local fallback.",
                e.response.status_code,
            )
        except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
            if self._strict_microservice_auth_enabled():
                raise HTTPException(status_code=503, detail="Authentication service unavailable") from e
            # في حال فشل الاتصال، نستخدم الخطة البديلة (Local Fallback)
            logger.error(f"User Service unreachable for registration ({e}), using local fallback.")

        # ==============================================================================
        # Local Fallback (Monolith Logic)
        # ==============================================================================
        if await self.persistence.user_exists(email):
            raise HTTPException(status_code=400, detail="Email already registered")

        new_user = await self.persistence.create_user(
            full_name=full_name,
            email=email,
            password=password,
            is_admin=False,
        )
        rbac_service = RBACService(self.db)
        await rbac_service.ensure_seed()
        await rbac_service.assign_role(new_user, STANDARD_ROLE)

        return {
            "status": "success",
            "message": "User registered successfully",
            "user": {
                "id": new_user.id,
                "full_name": new_user.full_name,
                "email": new_user.email,
                "is_admin": new_user.is_admin,
            },
        }

    async def authenticate_user(
        self, email: str, password: str, request: Request
    ) -> dict[str, object]:
        """
        المصادقة على المستخدم وإصدار رمز الدخول (JWT).

        محاولة المصادقة عبر User Service أولاً، ثم العودة للنظام المحلي.

        Args:
            email (str): البريد الإلكتروني.
            password (str): كلمة المرور.
            request (Request): كائن الطلب الحالي.

        Returns:
            dict[str, object]: رمز الدخول (Access Token) وتفاصيل المستخدم.
        """
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("User-Agent")

        # محاولة المصادقة عبر الخدمة المصغرة
        try:
            response = await user_service_client.login_user(
                email=email, password=password, ip=ip, user_agent=user_agent
            )
            # response format: {"access_token": "...", "user": {...}, "status": "..."}
            user_data = self._as_dict(response.get("user", {}))
            normalized_user = self._normalize_user_payload(user_data, fallback_email=email)
            is_admin = bool(normalized_user["is_admin"])
            landing_path = "/admin" if is_admin else "/app/chat"

            return {
                "access_token": response.get("access_token"),
                "token_type": "Bearer",
                "user": normalized_user,
                "status": "success",
                "landing_path": landing_path,
            }
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service rejected login: {e}")
            if self._strict_microservice_auth_enabled():
                detail = "Authentication failed"
                if e.response.status_code >= 500:
                    detail = "Authentication service unavailable"
                raise HTTPException(status_code=e.response.status_code, detail=detail) from e
            # إذا قالت الخدمة 401 قد يكون المستخدم غير موجود هناك أصلاً في طور الترحيل.
            pass
        except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
            if self._strict_microservice_auth_enabled():
                raise HTTPException(status_code=503, detail="Authentication service unavailable") from e
            logger.error(f"User Service unreachable for login ({e}), using local fallback.")

        # ==============================================================================
        # Local Fallback (Monolith Logic with ChronoShield)
        # ==============================================================================
        # 0. تفعيل درع الدفاع الزمني
        await chrono_shield.check_allowance(request, email)

        # 1. جلب بيانات المستخدم
        user = await self.persistence.get_user_by_email(email)

        # 2. التحقق من كلمة المرور
        is_valid = False
        if user:
            try:
                is_valid = user.verify_password(password)
            except Exception as e:
                logger.error(f"Password verification error for user {user.id}: {e}")
                is_valid = False
        else:
            chrono_shield.phantom_verify(password)
            is_valid = False

        if not is_valid:
            chrono_shield.record_failure(request, email)
            logger.warning(f"Failed login attempt for {email}")
            raise HTTPException(status_code=401, detail="Invalid email or password")

        chrono_shield.reset_target(email)

        # 3. توليد رمز JWT
        role = "admin" if user.is_admin else "user"
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": role,
            "is_admin": user.is_admin,
            "exp": datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=24),
        }

        token = jwt.encode(payload, self.settings.SECRET_KEY, algorithm="HS256")

        landing_path = "/admin" if user.is_admin else "/app/chat"
        return {
            "access_token": token,
            "token_type": "Bearer",
            "user": {
                "id": user.id,
                "name": user.full_name,
                "email": user.email,
                "is_admin": user.is_admin,
            },
            "status": "success",
            "landing_path": landing_path,
        }

    async def get_current_user(self, token: str) -> dict[str, object]:
        """
        جلب بيانات المستخدم الحالي من رمز JWT.

        يحاول التحقق عبر User Service أولاً.

        Args:
            token (str): رمز JWT الخام.

        Returns:
            dict[str, object]: تفاصيل المستخدم.
        """
        # محاولة التحقق عبر الخدمة المصغرة
        try:
            user_data = self._as_dict(await user_service_client.get_me(token))
            return self._normalize_user_payload(user_data)
        except httpx.HTTPStatusError as e:
            if self._strict_microservice_auth_enabled():
                raise HTTPException(status_code=e.response.status_code, detail="Invalid token") from e
            # الرمز غير صالح بالنسبة للخدمة، أو المستخدم غير موجود هناك
            pass
        except (httpx.RequestError, httpx.TimeoutException, Exception) as e:
            if self._strict_microservice_auth_enabled():
                raise HTTPException(status_code=503, detail="Authentication service unavailable") from e
            logger.error(f"User Service unreachable for get_me ({e}), using local fallback.")

        # ==============================================================================
        # Local Fallback
        # ==============================================================================
        try:
            payload = jwt.decode(token, self.settings.SECRET_KEY, algorithms=["HS256"])
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token payload")
        except jwt.PyJWTError as e:
            logger.warning(f"Token decoding failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid token") from e

        user = await self.persistence.get_user_by_id(int(user_id))

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": user.id,
            "name": user.full_name,
            "email": user.email,
            "is_admin": user.is_admin,
        }

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
