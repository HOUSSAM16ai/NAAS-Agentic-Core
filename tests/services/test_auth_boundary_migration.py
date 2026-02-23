"""
Tests for Auth Boundary Service Migration (Shadow Mode).
Verifies that the service correctly delegates to User Service and falls back to Local Persistence.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException

from app.services.boundaries.auth_boundary_service import AuthBoundaryService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return AuthBoundaryService(mock_db)


@pytest.mark.asyncio
async def test_register_user_success_remote(service):
    """
    Test successful registration via User Service.
    Should return remote user data and NOT call local persistence.
    """
    # Mock User Service Client
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.register_user = AsyncMock(
            return_value={
                "user": {
                    "id": 100,
                    "full_name": "Remote User",
                    "email": "remote@test.com",
                    "is_admin": False,
                },
                "message": "Remote success",
            }
        )

        # Mock Local Persistence (should NOT be called)
        service.persistence.user_exists = AsyncMock()
        service.persistence.create_user = AsyncMock()

        result = await service.register_user("Remote User", "remote@test.com", "password")

        assert result["status"] == "success"
        assert result["user"]["email"] == "remote@test.com"
        assert result["user"]["id"] == 100

        # Verify calls
        mock_client.register_user.assert_called_once_with(
            "Remote User", "remote@test.com", "password"
        )
        service.persistence.user_exists.assert_not_called()
        service.persistence.create_user.assert_not_called()




@pytest.mark.asyncio
async def test_register_user_remote_missing_name_uses_input_full_name(service):
    """
    عند غياب الاسم من استجابة التسجيل البعيدة يجب الحفاظ على الاسم المُدخل محلياً.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.register_user = AsyncMock(
            return_value={
                "user": {
                    "id": 777,
                    "email": "remote-no-name@test.com",
                    "is_admin": False,
                },
                "message": "Remote success",
            }
        )

        result = await service.register_user("Provided Name", "remote-no-name@test.com", "password")

        assert result["status"] == "success"
        assert result["user"]["full_name"] == "Provided Name"
        assert result["user"]["email"] == "remote-no-name@test.com"

@pytest.mark.asyncio
async def test_register_user_failure_network_fallback(service):
    """
    Test network failure during registration.
    Should catch exception and FALLBACK to local persistence.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        # Simulate Network Error
        mock_client.register_user.side_effect = httpx.RequestError("Connection failed")

        service.settings.AUTH_MICROSERVICE_ONLY = False

        # Mock Local Persistence (SHOULD be called)
        service.persistence.user_exists = AsyncMock(return_value=False)

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.full_name = "Local User"
        mock_user.email = "local@test.com"
        mock_user.is_admin = False
        service.persistence.create_user = AsyncMock(return_value=mock_user)

        # Mock RBAC
        with patch("app.services.boundaries.auth_boundary_service.RBACService") as mock_rbac_class:
            mock_rbac = mock_rbac_class.return_value
            mock_rbac.ensure_seed = AsyncMock()
            mock_rbac.assign_role = AsyncMock()

            result = await service.register_user("Local User", "local@test.com", "password")

            assert result["status"] == "success"
            assert result["user"]["email"] == "local@test.com"
            assert result["user"]["id"] == 1  # Local ID

            # Verify calls
            mock_client.register_user.assert_called_once()
            service.persistence.user_exists.assert_called_once_with("local@test.com")
            service.persistence.create_user.assert_called_once()


@pytest.mark.asyncio
async def test_register_user_failure_logical_400(service):
    """
    Test logical failure (400 Bad Request) from User Service.
    Should RAISE exception and NOT fallback.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        # Simulate 400 Error (e.g. Email exists remote)
        response = httpx.Response(400, json={"detail": "Email already registered"})
        mock_client.register_user.side_effect = httpx.HTTPStatusError(
            "400 Bad Request", request=None, response=response
        )

        # Mock Local Persistence (should NOT be called)
        service.settings.AUTH_MICROSERVICE_ONLY = True
        service.settings.ENVIRONMENT = "development"
        service.persistence.user_exists = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await service.register_user("User", "exists@test.com", "password")

        assert exc.value.status_code == 400
        service.persistence.user_exists.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_success_remote(service):
    """
    Test successful login via User Service.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.login_user = AsyncMock(
            return_value={
                "access_token": "remote_token",
                "token_type": "Bearer",
                "user": {
                    "id": 200,
                    "full_name": "Remote Login",
                    "email": "login@test.com",
                    "is_admin": False,
                },
                "status": "success",
            }
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "TestAgent"

        service.persistence.get_user_by_email = AsyncMock()

        result = await service.authenticate_user("login@test.com", "password", mock_request)

        assert result["access_token"] == "remote_token"
        assert result["user"]["id"] == 200

        mock_client.login_user.assert_called_once()
        service.persistence.get_user_by_email.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_fallback_on_401(service):
    """
    Test fallback behavior when User Service returns 401 (or connection error).
    Ideally, we try local just in case user is not migrated.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        # Simulate 401 from Remote (e.g. User not found remote)
        response = httpx.Response(401, json={"detail": "Invalid credentials"})
        mock_client.login_user.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=None, response=response
        )

        service.settings.AUTH_MICROSERVICE_ONLY = False

        # Mock Local Persistence (SHOULD be called for fallback)
        mock_user = MagicMock()
        mock_user.id = 2
        mock_user.email = "local_only@test.com"
        mock_user.is_admin = False
        mock_user.verify_password.return_value = True

        service.persistence.get_user_by_email = AsyncMock(return_value=mock_user)

        # Mock ChronoShield
        with patch("app.services.boundaries.auth_boundary_service.chrono_shield") as mock_shield:
            mock_shield.check_allowance = AsyncMock()
            mock_shield.reset_target = MagicMock()

            # Mock JWT
            with patch("app.services.boundaries.auth_boundary_service.jwt") as mock_jwt:
                mock_jwt.encode.return_value = "local_token"

                # Mock Settings
                service.settings = MagicMock()
                service.settings.SECRET_KEY = "secret"
                service.settings.AUTH_MICROSERVICE_ONLY = False
                service.settings.ENVIRONMENT = "testing"

                mock_request = MagicMock()

                result = await service.authenticate_user(
                    "local_only@test.com", "password", mock_request
                )

                assert result["access_token"] == "local_token"
                assert result["user"]["id"] == 2

                mock_client.login_user.assert_called_once()
                service.persistence.get_user_by_email.assert_called_once()


@pytest.mark.asyncio
async def test_get_current_user_success_remote(service):
    """
    Test successful get_current_user via User Service.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.get_me = AsyncMock(
            return_value={
                "id": 300,
                "full_name": "Remote Me",
                "email": "me@test.com",
                "is_admin": True,
            }
        )

        service.persistence.get_user_by_id = AsyncMock()

        result = await service.get_current_user("valid_remote_token")

        assert result["email"] == "me@test.com"
        assert result["id"] == 300

        mock_client.get_me.assert_called_once_with("valid_remote_token")
        service.persistence.get_user_by_id.assert_not_called()


@pytest.mark.asyncio
async def test_authenticate_user_remote_accepts_name_field(service):
    """
    عند استجابة الخدمة المصغّرة بحقل name فقط يجب الحفاظ على نجاح تسجيل الدخول.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.login_user = AsyncMock(
            return_value={
                "access_token": "remote_token",
                "user": {
                    "id": 201,
                    "name": "Remote Name",
                    "email": "name@test.com",
                    "is_admin": False,
                },
            }
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "TestAgent"

        result = await service.authenticate_user("name@test.com", "password", mock_request)

        assert result["access_token"] == "remote_token"
        assert result["user"]["name"] == "Remote Name"


@pytest.mark.asyncio
async def test_get_current_user_remote_accepts_name_field(service):
    """
    عند استجابة /user/me بحقل name فقط يجب إعادة الاسم بدون كسر التوافق.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.get_me = AsyncMock(
            return_value={
                "id": 301,
                "name": "Remote Me Name",
                "email": "me-name@test.com",
                "is_admin": True,
            }
        )

        result = await service.get_current_user("valid_remote_token")

        assert result["id"] == 301
        assert result["name"] == "Remote Me Name"
        assert result["email"] == "me-name@test.com"


@pytest.mark.asyncio
async def test_authenticate_user_remote_missing_name_uses_email_prefix(service):
    """
    عند غياب حقول الاسم من استجابة الخدمة المصغّرة يجب تعيين اسم افتراضي مستقر من البريد.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        mock_client.login_user = AsyncMock(
            return_value={
                "access_token": "remote_token",
                "user": {
                    "id": 202,
                    "email": "fallback-name@test.com",
                    "is_admin": False,
                },
            }
        )

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "TestAgent"

        result = await service.authenticate_user("fallback-name@test.com", "password", mock_request)

        assert result["access_token"] == "remote_token"
        assert result["user"]["name"] == "fallback-name"


@pytest.mark.asyncio
async def test_authenticate_user_local_fallback_uses_timezone_utc(service):
    """
    يجب أن يبقى المسار المحلي لتوليد JWT صالحاً ويعيد رمزاً دون أخطاء زمنية.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        response = httpx.Response(401, json={"detail": "Invalid credentials"})
        mock_client.login_user.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=None, response=response
        )

        mock_user = MagicMock()
        mock_user.id = 11
        mock_user.email = "local@test.com"
        mock_user.full_name = "Local Name"
        mock_user.is_admin = False
        mock_user.verify_password.return_value = True
        service.persistence.get_user_by_email = AsyncMock(return_value=mock_user)

        with patch("app.services.boundaries.auth_boundary_service.chrono_shield") as mock_shield:
            mock_shield.check_allowance = AsyncMock()
            mock_shield.reset_target = MagicMock()

            service.settings = MagicMock()
            service.settings.SECRET_KEY = "secret"
            service.settings.AUTH_MICROSERVICE_ONLY = False

            mock_request = MagicMock()
            mock_request.client.host = "127.0.0.1"
            mock_request.headers.get.return_value = "TestAgent"

            result = await service.authenticate_user("local@test.com", "password", mock_request)

            assert isinstance(result["access_token"], str)
            assert result["status"] == "success"
            assert result["user"]["id"] == 11


@pytest.mark.asyncio
async def test_authenticate_user_strict_mode_does_not_fallback_on_401(service):
    """
    في الوضع الصارم للخدمات المصغّرة لا يتم الرجوع للمونوليث عند رفض الخدمة البعيدة.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        response = httpx.Response(401, json={"detail": "Invalid credentials"})
        mock_client.login_user.side_effect = httpx.HTTPStatusError(
            "401 Unauthorized", request=None, response=response
        )

        service.settings.AUTH_MICROSERVICE_ONLY = True
        service.settings.ENVIRONMENT = "development"
        service.persistence.get_user_by_email = AsyncMock()

        mock_request = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers.get.return_value = "TestAgent"

        with pytest.raises(HTTPException) as exc:
            await service.authenticate_user("strict@test.com", "password", mock_request)

        assert exc.value.status_code == 401
        service.persistence.get_user_by_email.assert_not_called()


@pytest.mark.asyncio
async def test_register_user_strict_mode_no_local_fallback_on_unavailable(service):
    """
    في الوضع الصارم لا يتم إنشاء مستخدم محلي عند تعطل خدمة المستخدمين.
    """
    with patch("app.services.boundaries.auth_boundary_service.user_service_client") as mock_client:
        response = httpx.Response(503, json={"detail": "Service unavailable"})
        mock_client.register_user.side_effect = httpx.HTTPStatusError(
            "503 Service Unavailable", request=None, response=response
        )

        service.settings.AUTH_MICROSERVICE_ONLY = True
        service.settings.ENVIRONMENT = "development"
        service.persistence.user_exists = AsyncMock()

        with pytest.raises(HTTPException) as exc:
            await service.register_user("Strict User", "strict-user@test.com", "password")

        assert exc.value.status_code == 503
        service.persistence.user_exists.assert_not_called()
