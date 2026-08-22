# API Layer | طبقة API

> **الغرض:** REST API endpoints - طبقة العرض فقط  
> **Purpose:** REST API endpoints - Presentation layer only

---

## 📋 Overview | نظرة عامة

هذا المجلد يحتوي على **طبقة API** (API Layer) التي تمثل **Presentation Layer** في Clean Architecture.  
المسؤولية الوحيدة: استقبال HTTP requests وإرجاع HTTP responses.

This directory contains the **API layer** which represents the **Presentation Layer** in Clean Architecture.  
Single Responsibility: Receive HTTP requests and return HTTP responses.

---

## 🎯 API-First Architecture | بنية API-First

### مبدأ أساسي
النظام مصمم **API-First** - الـ API يعمل بشكل مستقل تماماً عن UI:

```
Frontend (Optional)
      ↓
┌─────────────────────────────┐
│   API Layer                 │ ← THIS LAYER
│   app/api/routers/          │   HTTP handling only
└─────────────────────────────┘
      ↓ Delegates to
┌─────────────────────────────┐
│   Boundary Services         │ ← Business logic
│   app/services/boundaries/  │
└─────────────────────────────┘
```

### ✅ فحص الحالة | API-First Status Check

- **لا يوجد HTTP app هنا:** لا يحتوي هذا المجلد على `main.py` أو كائنات `FastAPI`، ويتم تجميع الموجهات من `app/kernel.py` فقط لضمان أن الطبقة تعرض الواجهة دون خلط مسؤوليات.
- **الاعتماد على المخططات:** كل موجه يستخدم مخططات التحقق من `app/api/schemas/` قبل تفويض العمل للخدمات الحدودية.
- **لا تكامل واجهة أمامية:** لا توجد استيرادات أو تبعيات تخص UI؛ يمكن استهلاك الـ API مباشرةً عبر أي عميل HTTP.
- **تغطية التحقق:** اختبارات مثل `tests/api/test_admin_router_refactored.py` و `tests/test_cli_smoke.py` تؤكد سلامة نقاط النهاية وتشغيل التطبيق في وضع API فقط.

### المسؤوليات | Responsibilities

#### ✅ ما يجب أن يفعله API Layer:
1. **Request Validation** - التحقق من صحة الطلبات (Pydantic schemas)
2. **Response Formatting** - تنسيق الردود (Response schemas)
3. **Dependency Injection** - حقن التبعيات
4. **Error Handling** - معالجة الأخطاء وتحويلها لـ HTTP errors
5. **Authentication** - التحقق من الهوية (via middleware/dependencies)
6. **Documentation** - توثيق OpenAPI

#### ❌ ما يجب ألا يفعله API Layer:
1. ❌ Business Logic - منطق الأعمال
2. ❌ Database Queries - استعلامات قاعدة البيانات المباشرة
3. ❌ Data Transformation - تحويل معقد للبيانات
4. ❌ External API Calls - استدعاء APIs خارجية مباشرة
5. ❌ Complex Calculations - حسابات معقدة

---

## 📦 Directory Structure | هيكل المجلد

```
app/api/
│
├── routers/                 # API route modules
│   ├── admin.py             # Admin operations
│   ├── security.py          # Authentication & authorization
│   ├── crud.py              # CRUD operations
│   ├── observability.py     # Metrics & monitoring
│   ├── data_mesh.py         # Data mesh operations
│   ├── overmind.py          # AI/Overmind operations
│   └── system/              # System endpoints
│       ├── __init__.py
│       └── root.py          # Root system endpoints
│
├── schemas/                 # Request/Response schemas
│   ├── admin.py             # Admin schemas
│   ├── security.py          # Auth schemas
│   ├── crud.py              # CRUD schemas
│   ├── observability.py     # Observability schemas
│   └── system/              # System schemas
│
├── exceptions.py            # API exceptions
└── README.md                # This guide
```

> **ملاحظة API-First:** تم إزالة أي شيفرة إعداد إضافية (مثل `main.py` أو مجلد `v2/`) من طبقة API. يتم تضمين جميع الموجهات عبر مسجل البيانات في `app/kernel.py` لضمان أن الطبقة تعرض واجهة HTTP خالصة وتفوض العمل إلى خدمات الحدود فقط.

---

## 🔌 API Routers | موجهات API

### 1. Admin Router
**الملف:** `routers/admin.py`  
**البادئة:** `/admin`  
**الغرض:** Admin-specific operations

**Endpoints:**
```python
WS     /admin/api/chat/ws                        # Admin chat streaming (WebSocket)
GET    /admin/api/chat/latest                    # Get latest conversation snapshot
GET    /admin/api/conversations                  # List conversations
GET    /admin/api/conversations/{id}             # Get conversation details
```

**مثال:**
```python
@router.websocket("/api/chat/ws")
async def chat_stream_ws(...):
    """Admin chat streaming endpoint عبر WebSocket."""
```

---

### 2. Security Router
**الملف:** `routers/security.py`  
**البادئة:** `/security`  
**الغرض:** Authentication and authorization

**Endpoints:**
```python
POST   /security/login                           # User login
POST   /security/logout                          # User logout
POST   /security/refresh                         # Refresh token
GET    /security/me                              # Get current user
POST   /security/register                        # User registration
```

**مثال:**
```python
@router.post("/login")
async def login(
    credentials: LoginRequest,
    service: AuthBoundaryService = Depends(get_auth_service),
) -> TokenResponse:
    """User login endpoint."""
    # Delegate to auth service
    token = await service.authenticate_user(
        email=credentials.email,
        password=credentials.password,
    )
    return TokenResponse(access_token=token)
```

---

### 3. CRUD Router
**الملف:** `routers/crud.py`  
**البادئة:** `/crud`  
**الغرض:** Generic CRUD operations

**Endpoints:**
```python
GET    /crud/{resource}                          # List resources
POST   /crud/{resource}                          # Create resource
GET    /crud/{resource}/{id}                     # Get resource
PUT    /crud/{resource}/{id}                     # Update resource
DELETE /crud/{resource}/{id}                     # Delete resource
```

**مثال:**
```python
@router.get("/{resource}")
async def list_resources(
    resource: str,
    service: CrudBoundaryService = Depends(get_crud_service),
) -> ListResponse:
    """List resources endpoint."""
    # Delegate to CRUD service
    items = await service.list_items(resource)
    return ListResponse(items=items, total=len(items))
```

---

### 4. Observability Router
**الملف:** `routers/observability.py`  
**البادئة:** `/observability`  
**الغرض:** Metrics, monitoring, and health checks

**Endpoints:**
```python
GET    /observability/health                     # Health check
GET    /observability/metrics                    # System metrics
GET    /observability/traces                     # Distributed traces
```

---

### 5. Overmind Router
**الملف:** `routers/overmind.py`  
**البادئة:** `/overmind`  
**الغرض:** AI/Overmind operations

**Endpoints:**
```python
POST   /overmind/missions                        # Create mission
GET    /overmind/missions                        # List missions
GET    /overmind/missions/{id}                   # Get mission status
```

---

## 📝 Request/Response Schemas | نماذج الطلبات والردود

### Request Schemas
استخدام Pydantic للتحقق من الطلبات:

```python
from pydantic import BaseModel, Field, EmailStr

class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=8, description="User password")

class ChatRequest(BaseModel):
    """Chat request schema."""
    question: str = Field(..., min_length=1, max_length=5000)
    conversation_id: int | None = None
```

### Response Schemas
استخدام Pydantic للردود:

```python
class TokenResponse(BaseModel):
    """Token response schema."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600

class UserResponse(BaseModel):
    """User response schema."""
    id: int
    email: str
    name: str
    created_at: datetime
    
    class Config:
        from_attributes = True  # للتوافق مع SQLAlchemy models
```

---

## 🔧 Best Practices | أفضل الممارسات

### 1. Keep Endpoints Thin
الـ endpoints يجب أن تكون رفيعة - فقط تفويض:

```python
# Good ✅
@router.post("/users")
async def create_user(
    user_data: UserCreateRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Create user - thin endpoint."""
    user = await service.create_user(
        email=user_data.email,
        password=user_data.password,
        name=user_data.name,
    )
    return UserResponse.model_validate(user)

# Bad ❌
@router.post("/users")
async def create_user(
    user_data: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create user - fat endpoint with business logic."""
    # Checking email uniqueness (business logic!)
    existing = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email exists")
    
    # Password validation (business logic!)
    if len(user_data.password) < 8:
        raise HTTPException(400, "Password too weak")
    
    # Hashing password (should be in service!)
    hashed = hash_password(user_data.password)
    
    # Creating user (should be in service!)
    user = User(email=user_data.email, password=hashed, name=user_data.name)
    db.add(user)
    await db.commit()
    
    return UserResponse.model_validate(user)
```

### 2. Use Dependency Injection
استخدام DI لجميع التبعيات:

```python
# Good ✅
@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get user by ID."""
    user = await service.get_user(user_id)
    return UserResponse.model_validate(user)

# Bad ❌
@router.get("/users/{user_id}")
async def get_user(user_id: int) -> UserResponse:
    """Get user by ID."""
    db = create_session()  # Hard-coded dependency
    service = UserService(db)  # Hard-coded dependency
    user = await service.get_user(user_id)
    return UserResponse.model_validate(user)
```

### 3. Proper Error Handling
معالجة الأخطاء بشكل صحيح:

```python
# Good ✅
@router.get("/users/{user_id}")
async def get_user(
    user_id: int,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Get user by ID."""
    try:
        user = await service.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Bad ❌
@router.get("/users/{user_id}")
async def get_user(user_id: int, service: UserService = Depends(...)):
    """Get user by ID."""
    user = await service.get_user(user_id)  # No error handling
    return UserResponse.model_validate(user)  # Can crash
```

### 4. Complete Type Hints
type hints كاملة دائماً:

```python
# Good ✅
@router.post("/users")
async def create_user(
    user_data: UserCreateRequest,
    service: UserService = Depends(get_user_service),
) -> UserResponse:
    """Create user with complete type hints."""
    user = await service.create_user(user_data)
    return UserResponse.model_validate(user)

# Bad ❌
@router.post("/users")
async def create_user(user_data, service = Depends(...)):
    """Create user without type hints."""
    user = await service.create_user(user_data)
    return user
```

---

## 🧪 Testing API Endpoints | اختبار نقاط النهاية

### Unit Testing
استخدام TestClient:

```python
from fastapi.testclient import TestClient

def test_login_endpoint():
    """Test login endpoint."""
    client = TestClient(app)
    
    response = client.post(
        "/security/login",
        json={
            "email": "test@example.com",
            "password": "secure123"
        }
    )
    
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Integration Testing
اختبار مع dependencies حقيقية:

```python
@pytest.mark.asyncio
async def test_create_user_integration(test_db):
    """Test user creation with real database."""
    client = TestClient(app)
    
    response = client.post(
        "/users",
        json={
            "email": "newuser@example.com",
            "password": "secure123",
            "name": "New User"
        }
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
```

---

## 📚 Related Documentation | الوثائق ذات الصلة

### API Documentation
- [API-First Architecture](../../docs/API_FIRST_ARCHITECTURE.md)
- [API Layer Compliance Report](../../docs/ARCHITECTURE.md)
- [API Style Guide](../../docs/contracts/API_STYLE_GUIDE.md)

### Architecture
- [Clean Architecture](../../docs/architecture/)
- [Boundaries Architecture](../../docs/ARCHITECTURE.md)

### Testing
- [Testing Guide](../../docs/guides/TESTING_GUIDE.md)
- [API Testing](../../docs/quality/testing.md)

---

## 🤝 Contributing | المساهمة

### قبل إضافة endpoint جديد:
1. ✅ تأكد أن الـ endpoint ضروري
2. ✅ اتبع REST conventions
3. ✅ استخدم Pydantic schemas
4. ✅ استخدم Dependency Injection
5. ✅ لا business logic في endpoint
6. ✅ معالجة أخطاء صحيحة
7. ✅ اكتب tests
8. ✅ وثّق في OpenAPI

### Code Review Checklist
- [ ] Endpoint is thin (no business logic)?
- [ ] Dependencies are injected?
- [ ] Schemas are defined?
- [ ] Error handling is proper?
- [ ] Tests are written?
- [ ] OpenAPI documentation is complete?

---

**Last Updated:** 2026-01-03  
**Version:** 2.0  
**Maintainer:** CogniForge Team
