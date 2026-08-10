"""
اختبار صارم لعملية تسجيل الدخول (Strict Login Verification Test)
====================================================================

This test suite implements ultra-strict verification for login functionality:
- Password verification accuracy
- Error handling robustness
- Security measures (timing attacks, etc.)
- Database integration integrity
- JWT token generation and validation

المعايير المطبقة (Applied Standards):
- CS50 2025: Comprehensive testing, Arabic documentation
- Security First: Defense in depth testing
- SOLID: Test isolation and clarity
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_success_with_correct_credentials(async_client: AsyncClient):
    """
    Test 1: Login succeeds with correct credentials
    التحقق من نجاح تسجيل الدخول مع بيانات صحيحة
    """
    # Register user first
    register_payload = {
        "full_name": "Secure User",
        "email": "secure@example.com",
        "password": "SecurePassword123!",
    }
    reg_response = await async_client.post("/api/security/register", json=register_payload)
    assert reg_response.status_code == 200, f"Registration failed: {reg_response.text}"

    # Strict verification of registration response
    reg_data = reg_response.json()
    assert reg_data["status"] == "success"
    assert reg_data["user"]["email"] == "secure@example.com"
    assert reg_data["user"]["full_name"] == "Secure User"
    assert reg_data["user"]["is_admin"] is False

    # Login with correct credentials
    login_payload = {"email": "secure@example.com", "password": "SecurePassword123!"}
    login_response = await async_client.post("/api/security/login", json=login_payload)

    # Strict verification of login success
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    login_data = login_response.json()

    # Verify response structure
    assert "access_token" in login_data, "Missing access_token"
    assert "token_type" in login_data, "Missing token_type"
    assert "user" in login_data, "Missing user data"
    assert "status" in login_data, "Missing status"

    # Verify response values
    assert login_data["status"] == "success"
    assert login_data["token_type"] == "Bearer"
    assert len(login_data["access_token"]) > 50, "Token too short"

    # Verify user data in response
    assert login_data["user"]["email"] == "secure@example.com"
    # Note: API returns 'full_name' not 'name'
    assert "name" in login_data["user"] or "full_name" in login_data["user"]
    user_name = login_data["user"].get("name") or login_data["user"].get("full_name")
    assert user_name == "Secure User"
    assert login_data["user"]["is_admin"] is False


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_fails_with_wrong_password(async_client: AsyncClient):
    """
    Test 2: Login fails with wrong password
    التحقق من فشل تسجيل الدخول مع كلمة مرور خاطئة
    """
    # Register user
    register_payload = {
        "full_name": "Test Wrong Password",
        "email": "wrong_pass@example.com",
        "password": "CorrectPassword123!",
    }
    await async_client.post("/api/security/register", json=register_payload)

    # Try login with wrong password
    login_payload = {"email": "wrong_pass@example.com", "password": "WrongPassword456!"}
    login_response = await async_client.post("/api/security/login", json=login_payload)

    # Strict verification of failure
    assert login_response.status_code == 401, "Should return 401 Unauthorized"
    error_data = login_response.json()
    assert "message" in error_data  # Using 'message' as per error handler
    assert "invalid" in error_data["message"].lower()


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_fails_with_nonexistent_email(async_client: AsyncClient):
    """
    Test 3: Login fails with non-existent email
    التحقق من فشل تسجيل الدخول مع بريد إلكتروني غير موجود
    """
    login_payload = {
        "email": "nonexistent@example.com",
        "password": "AnyPassword123!",
    }
    login_response = await async_client.post("/api/security/login", json=login_payload)

    # Strict verification
    assert login_response.status_code == 401
    error_data = login_response.json()
    assert "message" in error_data  # Using 'message' as per error handler
    # Should not reveal whether email exists (security best practice)
    assert "invalid" in error_data["message"].lower()


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_case_insensitive_email(async_client: AsyncClient):
    """
    Test 4: Login is case-insensitive for email
    التحقق من أن البريد الإلكتروني غير حساس لحالة الأحرف
    """
    # Register with lowercase
    register_payload = {
        "full_name": "Case Test User",
        "email": "casetest@example.com",
        "password": "Password123!",
    }
    await async_client.post("/api/security/register", json=register_payload)

    # Login with uppercase
    login_payload = {"email": "CASETEST@EXAMPLE.COM", "password": "Password123!"}
    login_response = await async_client.post("/api/security/login", json=login_payload)

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["status"] == "success"


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_password_is_case_sensitive(async_client: AsyncClient):
    """
    Test 5: Password IS case-sensitive (security requirement)
    التحقق من أن كلمة المرور حساسة لحالة الأحرف
    """
    # Register
    register_payload = {
        "full_name": "Password Case User",
        "email": "passcase@example.com",
        "password": "Password123!",
    }
    await async_client.post("/api/security/register", json=register_payload)

    # Try login with different case
    login_payload = {"email": "passcase@example.com", "password": "PASSWORD123!"}
    login_response = await async_client.post("/api/security/login", json=login_payload)

    # Must fail - passwords are case-sensitive
    assert login_response.status_code == 401


@pytest.mark.asyncio
@pytest.mark.security
async def test_jwt_token_contains_correct_claims(async_client: AsyncClient):
    """
    Test 6: JWT token contains correct user claims
    التحقق من أن JWT يحتوي على البيانات الصحيحة
    """
    import os

    import jwt

    # Register and login
    register_payload = {
        "full_name": "JWT Test User",
        "email": "jwttest@example.com",
        "password": "Password123!",
    }
    await async_client.post("/api/security/register", json=register_payload)

    login_payload = {"email": "jwttest@example.com", "password": "Password123!"}
    login_response = await async_client.post("/api/security/login", json=login_payload)

    login_data = login_response.json()
    token = login_data["access_token"]

    # Decode token (without verification for testing)
    secret_key = os.getenv(
        "SECRET_KEY", "test-secret-key-that-is-very-long-and-secure-enough-for-tests-v4"
    )
    decoded = jwt.decode(token, secret_key, algorithms=["HS256"])

    # D-236 · ISS-152 — عقد المطالبات تغيّر عمداً.
    #
    # كان هذا المسار يسكّ رمزاً بيده يحمل `email` و`role` نصّيتين، بلا `jti` ولا
    # `iat` ولا نوع، وعمره ٢٤ ساعة. صار يُفوَّض إلى `AuthService` — المحرّك
    # القانوني — فحلّت `roles[]`/`permissions[]` (من RBAC) محلّ `role` النصّية،
    # وأُضيفت `type` التي تُغلق التباس أنواع الرموز.
    #
    # ⛔ `email` حُذفت عمداً: مُعرِّف الحساب في `sub`، وحملُ البريد داخل رمزٍ
    # يُمرَّر في روابط WebSocket (`?token=`) يسرّب بيانات شخصية إلى سجلّات
    # الوسطاء بلا مقابل.
    #
    # لا مستهلك فقد شيئاً: مصادقة WebSocket تشتقّ الإدارة من `is_admin` أو من
    # `ADMIN` داخل `roles` (`customer_chat.py:196`)، و`/api/v1` يقرأ الصلاحيات
    # من قاعدة البيانات لا من الرمز (`app/deps/auth.py:get_current_user`).
    assert "sub" in decoded, "Missing 'sub' claim"
    assert "roles" in decoded, "Missing 'roles' claim"
    assert "permissions" in decoded, "Missing 'permissions' claim"
    assert "is_admin" in decoded, "Missing 'is_admin' claim"
    assert "type" in decoded, "Missing 'type' claim"
    assert "jti" in decoded, "Missing 'jti' claim"
    assert "iat" in decoded, "Missing 'iat' claim"
    assert "exp" in decoded, "Missing 'exp' claim"

    assert decoded["type"] == "access"
    assert decoded["is_admin"] is False
    assert isinstance(decoded["roles"], list)


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_multiple_sequential_attempts(async_client: AsyncClient):
    """
    Test 7: Multiple sequential login attempts work correctly
    التحقق من عمل تسجيلات دخول متعددة بشكل صحيح
    """
    # Register user
    register_payload = {
        "full_name": "Multi Login User",
        "email": "multilogin@example.com",
        "password": "Password123!",
    }
    await async_client.post("/api/security/register", json=register_payload)

    # Perform multiple logins
    for i in range(3):
        login_payload = {"email": "multilogin@example.com", "password": "Password123!"}
        login_response = await async_client.post("/api/security/login", json=login_payload)

        assert login_response.status_code == 200, f"Login {i + 1} failed"
        login_data = login_response.json()
        assert login_data["status"] == "success"
        assert "access_token" in login_data


@pytest.mark.asyncio
@pytest.mark.security
async def test_login_with_special_characters_in_password(async_client: AsyncClient):
    """
    Test 8: Login works with special characters in password
    التحقق من دعم الأحرف الخاصة في كلمة المرور
    """
    # Register with complex password
    register_payload = {
        "full_name": "Special Chars User",
        "email": "specialchars@example.com",
        "password": "P@$$w0rd!#%&*()[]{}",
    }
    await async_client.post("/api/security/register", json=register_payload)

    # Login with same complex password
    login_payload = {
        "email": "specialchars@example.com",
        "password": "P@$$w0rd!#%&*()[]{}",
    }
    login_response = await async_client.post("/api/security/login", json=login_payload)

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["status"] == "success"


@pytest.mark.asyncio
@pytest.mark.security
async def test_password_verification_uses_secure_comparison(async_client: AsyncClient):
    """
    Test 9: Verify password hashing and verification is secure
    التحقق من أن تشفير كلمة المرور آمن
    """
    from app.core.domain.models import User

    # Test password hashing directly
    user = User(full_name="Hash Test", email="hash@test.com", is_admin=False)
    user.set_password("TestPassword123!")

    # Password hash should be different from plain password
    assert user.password_hash != "TestPassword123!"
    assert len(user.password_hash) > 50  # Argon2 hashes are long

    # Correct password verification
    assert user.verify_password("TestPassword123!") is True

    # Wrong password verification
    assert user.verify_password("WrongPassword") is False
    assert user.verify_password("TestPassword123") is False  # Missing '!'
