# 🧪 دليل اختبار API-First | API-First Testing Guide

> **اختبارات شاملة لضمان جودة معايير API-First**

---

## 📋 فهرس المحتويات

1. [أنواع الاختبارات](#أنواع-الاختبارات)
2. [إعداد بيئة الاختبار](#إعداد-بيئة-الاختبار)
3. [Unit Tests](#unit-tests)
4. [Integration Tests](#integration-tests)
5. [Contract Tests](#contract-tests)
6. [Security Tests](#security-tests)
7. [Performance Tests](#performance-tests)
8. [E2E Tests](#e2e-tests)

---

## 🎯 أنواع الاختبارات

### 1. Unit Tests (اختبارات الوحدة)
- اختبار كل دالة بشكل منفصل
- Mocking للتبعيات الخارجية
- سريعة جداً (<10ms per test)

### 2. Integration Tests (اختبارات التكامل)
- اختبار API endpoints كاملة
- قاعدة بيانات test
- التحقق من request/response

### 3. Contract Tests (اختبارات العقود)
- التحقق من OpenAPI spec
- ضمان التوافق مع clients
- Backward compatibility

### 4. Security Tests (اختبارات الأمان)
- Authentication & Authorization
- Rate limiting
- Input validation
- SQL injection, XSS

### 5. Performance Tests (اختبارات الأداء)
- Load testing
- Stress testing
- Latency measurements

### 6. E2E Tests (اختبارات شاملة)
- سيناريوهات كاملة
- Multi-step workflows
- Real user scenarios

---

## ⚙️ إعداد بيئة الاختبار

### تثبيت المتطلبات

```bash
pip install pytest pytest-asyncio pytest-cov httpx faker
```

### هيكل ملفات الاختبار

```
tests/
├── unit/
│   ├── test_services/
│   ├── test_models/
│   └── test_utils/
├── integration/
│   ├── test_api_security.py
│   ├── test_api_crud.py
│   └── test_api_admin.py
├── contract/
│   └── test_openapi_compliance.py
├── security/
│   └── test_api_security_full.py
├── performance/
│   └── test_api_performance.py
└── conftest.py  # Fixtures مشتركة
```

---

## 🧪 Unit Tests

### مثال: اختبار Service

```python
# tests/unit/test_services/test_user_service.py
import pytest
from unittest.mock import AsyncMock, Mock
from app.services.users.user_service import UserService
from app.models import User

@pytest.fixture
def mock_session():
    """Mock لجلسة قاعدة البيانات"""
    session = AsyncMock()
    return session

@pytest.fixture
def user_service(mock_session):
    """إنشاء UserService مع session محاكى"""
    return UserService(session=mock_session)

@pytest.mark.asyncio
async def test_create_user_success(user_service, mock_session):
    """اختبار إنشاء مستخدم بنجاح"""
    # Arrange
    mock_session.execute.return_value.scalar.return_value = None  # لا يوجد مستخدم مكرر
    
    # Act
    result = await user_service.create_new_user(
        full_name="Test User",
        email="test@example.com",
        password="SecurePass123!",
        is_admin=False
    )
    
    # Assert
    assert result["status"] == "success"
    assert mock_session.add.called
    assert mock_session.commit.called

@pytest.mark.asyncio
async def test_create_user_duplicate_email(user_service, mock_session):
    """اختبار إنشاء مستخدم ببريد مكرر"""
    # Arrange
    existing_user = User(email="test@example.com", full_name="Existing")
    mock_session.execute.return_value.scalar.return_value = existing_user
    
    # Act
    result = await user_service.create_new_user(
        full_name="Test User",
        email="test@example.com",
        password="SecurePass123!",
    )
    
    # Assert
    assert result["status"] == "error"
    assert "already exists" in result["message"]
    assert not mock_session.add.called
```

### مثال: اختبار Models

```python
# tests/unit/test_models/test_user.py
from app.models import User

def test_user_password_hashing():
    """اختبار تشفير كلمة المرور"""
    user = User(email="test@example.com", full_name="Test")
    user.set_password("mypassword123")
    
    # Password should be hashed, not plaintext
    assert user.password_hash != "mypassword123"
    assert user.password_hash is not None
    
    # Check password should work
    assert user.check_password("mypassword123") is True
    assert user.check_password("wrongpassword") is False

def test_user_to_dict():
    """اختبار تحويل User إلى dict"""
    user = User(
        id=1,
        email="test@example.com",
        full_name="Test User",
        is_admin=False
    )
    
    user_dict = user.to_dict()
    
    assert user_dict["id"] == 1
    assert user_dict["email"] == "test@example.com"
    assert "password_hash" not in user_dict  # يجب عدم تضمين password
```

---

## 🔗 Integration Tests

### مثال: اختبار API Endpoints

```python
# tests/integration/test_api_security.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_register_success():
    """اختبار تسجيل مستخدم جديد"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/security/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User"
            }
        )
    
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "user" in data["data"]
    assert data["data"]["user"]["email"] == "newuser@example.com"

@pytest.mark.asyncio
async def test_login_success():
    """اختبار تسجيل دخول مستخدم"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First, register user
        await client.post(
            "/api/security/register",
            json={
                "email": "user@example.com",
                "password": "SecurePass123!",
                "full_name": "Test User"
            }
        )
        
        # Then, login
        response = await client.post(
            "/api/security/login",
            json={
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "Bearer"

@pytest.mark.asyncio
async def test_login_invalid_credentials():
    """اختبار تسجيل دخول ببيانات خاطئة"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/security/login",
            json={
                "email": "user@example.com",
                "password": "WrongPassword!"
            }
        )
    
    assert response.status_code == 401
    data = response.json()
    assert data["status"] == "error"
    assert data["error"]["code"] == "INVALID_CREDENTIALS"

@pytest.mark.asyncio
async def test_protected_endpoint_without_token():
    """اختبار endpoint محمي بدون token"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/security/user/me")
    
    assert response.status_code == 401
    data = response.json()
    assert data["status"] == "error"
    assert "token" in data["error"]["message"].lower()

@pytest.mark.asyncio
async def test_protected_endpoint_with_valid_token():
    """اختبار endpoint محمي مع token صحيح"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Register and login
        await client.post(
            "/api/security/register",
            json={
                "email": "user@example.com",
                "password": "SecurePass123!",
                "full_name": "Test User"
            }
        )
        
        login_response = await client.post(
            "/api/security/login",
            json={
                "email": "user@example.com",
                "password": "SecurePass123!"
            }
        )
        token = login_response.json()["data"]["access_token"]
        
        # Access protected endpoint
        response = await client.get(
            "/api/security/user/me",
            headers={"Authorization": f"Bearer {token}"}
        )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["user"]["email"] == "user@example.com"
```

---

## 📜 Contract Tests

### التحقق من OpenAPI Compliance

```python
# tests/contract/test_openapi_compliance.py
import pytest
import yaml
from pathlib import Path
from httpx import AsyncClient
from app.main import app

@pytest.fixture
def openapi_spec():
    """تحميل OpenAPI spec"""
    spec_path = Path("docs/contracts/openapi/core-api-v1.yaml")
    with open(spec_path) as f:
        return yaml.safe_load(f)

@pytest.mark.asyncio
async def test_endpoints_match_spec(openapi_spec):
    """التحقق من أن جميع endpoints المذكورة في spec موجودة"""
    paths = openapi_spec.get("paths", {})
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        for path, methods in paths.items():
            for method in methods.keys():
                if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                    # Test that endpoint exists (may return 401/404, but not 404 for wrong path)
                    response = await getattr(client, method.lower())(path)
                    # Should not be 404 (Not Found for wrong path)
                    assert response.status_code != 404, f"{method.upper()} {path} not found"

@pytest.mark.asyncio
async def test_response_matches_schema(openapi_spec):
    """التحقق من أن responses تتطابق مع schemas المحددة"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test login response
        response = await client.post(
            "/api/security/login",
            json={
                "email": "test@example.com",
                "password": "password123"
            }
        )
        
        data = response.json()
        
        # Verify structure matches ErrorResponse or AuthResponse
        assert "status" in data
        assert data["status"] in ["success", "error"]
        
        if data["status"] == "error":
            assert "error" in data
            assert "code" in data["error"]
            assert "message" in data["error"]
            assert "timestamp" in data
```

---

## 🔒 Security Tests

### اختبارات أمان شاملة

```python
# tests/security/test_api_security_full.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_sql_injection_protection():
    """اختبار الحماية من SQL Injection"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/security/login",
            json={
                "email": "admin' OR '1'='1",
                "password": "anything"
            }
        )
    
    # Should not return 500 or allow access
    assert response.status_code in [400, 401]
    data = response.json()
    assert data["status"] == "error"

@pytest.mark.asyncio
async def test_xss_protection():
    """اختبار الحماية من XSS"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/security/register",
            json={
                "email": "test@example.com",
                "password": "SecurePass123!",
                "full_name": "<script>alert('xss')</script>"
            }
        )
    
    if response.status_code == 201:
        data = response.json()
        # Script tags should be escaped or rejected
        assert "<script>" not in data["data"]["user"]["full_name"]

@pytest.mark.asyncio
async def test_rate_limiting():
    """اختبار Rate Limiting"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make many requests quickly
        responses = []
        for _ in range(150):  # More than typical rate limit
            response = await client.post(
                "/api/security/login",
                json={
                    "email": "test@example.com",
                    "password": "password"
                }
            )
            responses.append(response.status_code)
        
        # Should have some 429 (Too Many Requests)
        assert 429 in responses

@pytest.mark.asyncio
async def test_cors_headers():
    """اختبار CORS headers"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.options("/api/security/login")
    
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers

@pytest.mark.asyncio
async def test_security_headers():
    """اختبار Security Headers"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/security/health")
    
    # Check for security headers
    headers = response.headers
    assert "x-content-type-options" in headers
    # May have more: x-frame-options, strict-transport-security, etc.
```

---

## ⚡ Performance Tests

### اختبارات الأداء

```python
# tests/performance/test_api_performance.py
import pytest
import time
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_endpoint_latency():
    """قياس زمن استجابة endpoints"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        start = time.time()
        response = await client.get("/api/security/health")
        elapsed = time.time() - start
    
    assert response.status_code == 200
    assert elapsed < 0.1  # Should respond in <100ms

@pytest.mark.asyncio
async def test_concurrent_requests():
    """اختبار الطلبات المتزامنة"""
    import asyncio
    
    async def make_request():
        async with AsyncClient(app=app, base_url="http://test") as client:
            return await client.get("/api/security/health")
    
    # Make 100 concurrent requests
    start = time.time()
    tasks = [make_request() for _ in range(100)]
    responses = await asyncio.gather(*tasks)
    elapsed = time.time() - start
    
    # All should succeed
    assert all(r.status_code == 200 for r in responses)
    # Should handle 100 requests in reasonable time
    assert elapsed < 5  # <5 seconds for 100 requests

@pytest.mark.asyncio
async def test_pagination_performance():
    """اختبار أداء Pagination"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        start = time.time()
        response = await client.get("/api/v1/resources/missions?page=1&per_page=100")
        elapsed = time.time() - start
    
    # Pagination should be fast even with large per_page
    assert elapsed < 0.5  # <500ms
```

---

## 🎬 E2E Tests

### سيناريو كامل: إنشاء مستخدم ومهمة

```python
# tests/e2e/test_full_user_workflow.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_complete_user_workflow():
    """
    سيناريو كامل:
    1. تسجيل مستخدم جديد
    2. تسجيل دخول
    3. إنشاء mission
    4. الحصول على missions
    5. تحديث mission
    6. حذف mission
    """
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Register
        register_response = await client.post(
            "/api/security/register",
            json={
                "email": "workflow@example.com",
                "password": "SecurePass123!",
                "full_name": "Workflow User"
            }
        )
        assert register_response.status_code == 201
        
        # 2. Login
        login_response = await client.post(
            "/api/security/login",
            json={
                "email": "workflow@example.com",
                "password": "SecurePass123!"
            }
        )
        assert login_response.status_code == 200
        token = login_response.json()["data"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 3. Create mission
        create_response = await client.post(
            "/api/v1/resources/missions",
            headers=headers,
            json={
                "title": "Test Mission",
                "description": "A test mission"
            }
        )
        assert create_response.status_code == 201
        mission_id = create_response.json()["data"]["id"]
        
        # 4. Get missions
        list_response = await client.get(
            "/api/v1/resources/missions",
            headers=headers
        )
        assert list_response.status_code == 200
        missions = list_response.json()["data"]
        assert len(missions) >= 1
        
        # 5. Update mission
        update_response = await client.put(
            f"/api/v1/resources/missions/{mission_id}",
            headers=headers,
            json={
                "title": "Updated Mission",
                "description": "Updated description"
            }
        )
        assert update_response.status_code == 200
        
        # 6. Delete mission
        delete_response = await client.delete(
            f"/api/v1/resources/missions/{mission_id}",
            headers=headers
        )
        assert delete_response.status_code == 204
```

---

## 🛠️ تشغيل الاختبارات

### تشغيل جميع الاختبارات

```bash
pytest
```

### تشغيل نوع محدد

```bash
pytest tests/unit/                    # Unit tests only
pytest tests/integration/             # Integration tests only
pytest tests/security/                # Security tests only
```

### مع تقرير التغطية

```bash
pytest --cov=app --cov-report=html
```

### مع تقرير مفصل

```bash
pytest -v --tb=short
```

### تشغيل اختبارات محددة

```bash
pytest tests/integration/test_api_security.py::test_login_success
```

---

## 📊 معايير النجاح

### Code Coverage
- ✅ **Target**: 80%+ coverage
- ✅ **Critical paths**: 100% coverage
- ✅ **Services**: 90%+ coverage

### Performance
- ✅ **API latency**: <100ms (P95)
- ✅ **Concurrent requests**: 100 req/s minimum
- ✅ **Database queries**: <50ms

### Security
- ✅ **No SQL injection vulnerabilities**
- ✅ **XSS protection active**
- ✅ **Rate limiting working**
- ✅ **Authentication/Authorization enforced**

---

## 🎯 Continuous Integration

### GitHub Actions Example

```yaml
name: API Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install pytest pytest-asyncio pytest-cov
    
    - name: Run tests
      run: |
        pytest --cov=app --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v2
```

---

**Built with ❤️ for Quality Assurance**
