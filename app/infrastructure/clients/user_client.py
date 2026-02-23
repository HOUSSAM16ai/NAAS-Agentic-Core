"""عميل خدمة المستخدمين.

يوفّر واجهة موحّدة للتعامل مع خدمة المستخدمين المصغّرة مع الحفاظ على
التوافق العكسي أثناء الانتقال من المسارات القديمة (monolith) إلى
مسارات API-First الخاصة بالخدمة المصغّرة.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Final

import httpx
import jwt

from app.core.http_client_factory import HTTPClientConfig, get_http_client
from app.core.settings.base import get_settings

logger = logging.getLogger("user-service-client")

DEFAULT_USER_SERVICE_URL: Final[str] = "http://user-service:8003"


class UserServiceClient:
    """عميل للتفاعل مع خدمة المستخدمين عبر واجهات HTTP."""

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
        self._preferred_auth_path_by_suffix: dict[str, str] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        return get_http_client(self.config)

    def _generate_service_token(self) -> str:
        """توليد رمز خدمة قصير العمر لمصادقة Service-to-Service."""
        payload = {
            "sub": "api-gateway",
            "role": "ADMIN",
            "type": "service",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _build_service_headers(self, extra_headers: dict[str, str] | None = None) -> dict[str, str]:
        """بناء ترويسات الطلب مع رمز الخدمة المطلوب من خدمة المستخدمين."""
        headers: dict[str, str] = {"X-Service-Token": self._generate_service_token()}
        if extra_headers:
            headers.update(extra_headers)
        return headers

    @staticmethod
    def _auth_paths(suffix: str) -> tuple[str, ...]:
        """إرجاع مسارات المصادقة المتاحة في بيئات الترحيل المختلفة."""
        return (f"/api/v1/auth/{suffix}", f"/api/security/{suffix}", f"/auth/{suffix}")


    def _ordered_paths(self, suffix: str) -> tuple[str, ...]:
        """إرجاع ترتيب مسارات المصادقة مع تفضيل المسار الذي نجح سابقاً."""
        paths = list(self._auth_paths(suffix))
        preferred = self._preferred_auth_path_by_suffix.get(suffix)
        if preferred and preferred in paths:
            paths.remove(preferred)
            paths.insert(0, preferred)
        return tuple(paths)

    def _remember_preferred_path(self, suffix: str, path: str) -> None:
        """حفظ المسار الناجح لتقليل طلبات الاستكشاف اللاحقة."""
        self._preferred_auth_path_by_suffix[suffix] = path

    async def _post_with_fallback(
        self,
        suffix: str,
        payload: dict[str, object],
        headers: dict[str, str],
    ) -> dict[str, object]:
        """تنفيذ POST مع دعم fallback للمسارات القديمة عند 404 فقط."""
        client = await self._get_client()
        last_error: httpx.HTTPStatusError | None = None

        paths = self._ordered_paths(suffix)
        for path in paths:
            url = f"{self.base_url}{path}"
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 404:
                continue
            try:
                response.raise_for_status()
                self._remember_preferred_path(suffix, path)
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                break

        if last_error:
            raise last_error
        raise httpx.HTTPStatusError(
            "User Service endpoint not found",
            request=httpx.Request(method="POST", url=f"{self.base_url}{paths[0]}"),
            response=httpx.Response(status_code=404),
        )

    async def _get_with_fallback(self, suffix: str, headers: dict[str, str]) -> dict[str, object]:
        """تنفيذ GET مع دعم fallback للمسارات القديمة عند 404 فقط."""
        client = await self._get_client()
        last_error: httpx.HTTPStatusError | None = None

        paths = self._ordered_paths(suffix)
        for path in paths:
            url = f"{self.base_url}{path}"
            response = await client.get(url, headers=headers)
            if response.status_code == 404:
                continue
            try:
                response.raise_for_status()
                self._remember_preferred_path(suffix, path)
                return response.json()
            except httpx.HTTPStatusError as exc:
                last_error = exc
                break

        if last_error:
            raise last_error
        raise httpx.HTTPStatusError(
            "User Service endpoint not found",
            request=httpx.Request(method="GET", url=f"{self.base_url}{paths[0]}"),
            response=httpx.Response(status_code=404),
        )

    async def register_user(self, full_name: str, email: str, password: str) -> dict[str, object]:
        """تسجيل مستخدم جديد عبر خدمة المستخدمين."""
        payload = {
            "full_name": full_name,
            "email": email,
            "password": password,
        }
        headers = self._build_service_headers()
        try:
            logger.info(f"Dispatching registration to User Service: {email}")
            return await self._post_with_fallback("register", payload, headers)
        except httpx.HTTPStatusError as e:
            # Re-raise status errors (400, 401, etc.)
            logger.warning(f"User Service returned error for registration: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to register user via service: {e}", exc_info=True)
            raise

    async def login_user(
        self, email: str, password: str, user_agent: str | None = None, ip: str | None = None
    ) -> dict[str, object]:
        """مصادقة المستخدم عبر خدمة المستخدمين."""
        payload = {
            "email": email,
            "password": password,
        }
        headers: dict[str, str] = {}
        if user_agent:
            headers["User-Agent"] = user_agent
        service_headers = self._build_service_headers(headers)

        try:
            return await self._post_with_fallback("login", payload, service_headers)
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service returned error for login: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to login user via service: {e}", exc_info=True)
            raise

    async def get_me(self, token: str) -> dict[str, object]:
        """جلب بيانات المستخدم الحالي بالاعتماد على رمز الدخول."""
        headers = self._build_service_headers({"Authorization": f"Bearer {token}"})
        try:
            return await self._get_with_fallback("user/me", headers)
        except httpx.HTTPStatusError as e:
            logger.warning(f"User Service returned error for get_me: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"Failed to get user via service: {e}", exc_info=True)
            raise

    async def verify_token(self, token: str) -> bool:
        """التحقق من صلاحية رمز الدخول."""
        payload = {"token": token}
        headers = self._build_service_headers()
        try:
            data = await self._post_with_fallback("token/verify", payload, headers)
            return data.get("data", {}).get("valid", False)
        except Exception as e:
            logger.error(f"Failed to verify token via service: {e}")
            return False

    async def get_users(self) -> list[dict[str, object]]:
        """جلب قائمة المستخدمين (لصلاحيات الإدارة)."""
        url = f"{self.base_url}/admin/users"
        token = self._generate_service_token()
        headers = self._build_service_headers({"Authorization": f"Bearer {token}"})

        client = await self._get_client()
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            raise

    async def get_user_count(self) -> int:
        """جلب إجمالي عدد المستخدمين (لصلاحيات الإدارة)."""
        try:
            users = await self.get_users()
            return len(users)
        except Exception as e:
            logger.error(f"Failed to get user count: {e}")
            raise


# Singleton
user_service_client = UserServiceClient()
user_client = user_service_client  # Alias for backward compatibility
