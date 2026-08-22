# Core Infrastructure | البنية الأساسية

> **الغرض:** المكونات الأساسية والبنية التحتية للنظام  
> **Purpose:** Core components and infrastructure for the system

---

## 📋 Overview | نظرة عامة

هذا المجلد يحتوي على **المكونات الأساسية** (Core Components) التي يعتمد عليها النظام بأكمله:
- قاعدة البيانات (Database)
- الأمان (Security)
- بوابة الذكاء الاصطناعي (AI Gateway)
- معالجة الأخطاء (Error Handling)
- الأنماط المعمارية (Architectural Patterns)

This directory contains the **core infrastructure components** that the entire system depends on:
- Database connectivity and session management
- Security and authentication
- AI/LLM gateway integration
- Error handling and resilience
- Architectural patterns and utilities

---

## 📦 Key Components | المكونات الرئيسية

### 1. Database Layer | طبقة قاعدة البيانات
**الملفات:**
- `database.py` - اتصال SQLAlchemy وإدارة الجلسات
- `db_schema.py` - التحقق من schema والـ migrations
- `self_healing_db.py` - استشفاء تلقائي من أخطاء DB

**الاستخدام:**
```python
from app.core.database import get_db

async def get_users(db: AsyncSession = Depends(get_db)):
    """Get database session via dependency injection."""
    users = await db.execute(select(User))
    return users.scalars().all()
```

**المسؤوليات:**
- ✅ إنشاء وإدارة database sessions
- ✅ Connection pooling and optimization
- ✅ Transaction management
- ✅ Schema validation on startup

---

### 2. Security Layer | طبقة الأمان
**الملفات:**
- `security.py` - Authentication & password hashing
- `jwt.py` - JWT token generation and validation
- `rate_limiter.py` - Rate limiting utilities

**الاستخدام:**
```python
from app.core.security import verify_password, hash_password

# Hash password for storage
hashed = hash_password("user_password")

# Verify on login
is_valid = verify_password("user_password", hashed)
```

**المسؤوليات:**
- ✅ Password hashing (bcrypt)
- ✅ JWT token management
- ✅ Rate limiting implementation
- ✅ Security utilities

---

### 3. AI Gateway | بوابة الذكاء الاصطناعي
**الملفات:**
- `ai_gateway.py` - OpenRouter integration
- `prompts/` - Prompt templates and management

**الاستخدام:**
```python
from app.core.ai_gateway import get_ai_client, AIClient

async def chat(ai: AIClient = Depends(get_ai_client)):
    """Get AI client via dependency injection."""
    response = await ai.chat_completion(
        messages=[{"role": "user", "content": "Hello"}],
        model="gpt-4"
    )
    return response
```

**المسؤوليات:**
- ✅ OpenRouter API integration
- ✅ Multiple LLM support (GPT-4, Claude, etc.)
- ✅ Streaming support
- ✅ Error handling and retries

---

### 4. Dependency Injection | حقن التبعيات
**الملفات:**
- `di.py` - Dependency injection utilities
- `dependencies.py` - Common dependencies

**الاستخدام:**
```python
from app.core.di import get_logger

logger = get_logger(__name__)
logger.info("Application started")
```

**المسؤوليات:**
- ✅ Logger factory
- ✅ Service dependencies
- ✅ Configuration injection

---

### 5. Error Handling | معالجة الأخطاء
**الملفات:**
- `resilience/` - Resilience patterns (Circuit Breaker, Retry)

**الاستخدام:**
```python
from app.core.resilience.circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(failure_threshold=3)

@breaker
async def risky_operation():
    """Auto-wrapped with circuit breaker protection."""
    return await external_api_call()
```

**المسؤوليات:**
- ✅ Circuit breaker pattern
- ✅ Retry logic with exponential backoff
- ✅ Graceful degradation

---

### 6. Architectural Patterns | الأنماط المعمارية
**الملفات:**
- `patterns/strategy.py` - Strategy pattern implementation
- `domain_events/` - Domain events system
- `cs61_*.py` - CS61 educational patterns

**الاستخدام:**
```python
from app.core.patterns.strategy import Strategy, StrategyRegistry

# Define strategies
class ConcreteStrategy(Strategy):
    async def execute(self, context):
        return "result"

# Use registry
registry = StrategyRegistry()
registry.register("my_strategy", ConcreteStrategy())
```

**المسؤوليات:**
- ✅ Strategy pattern for flexible algorithms
- ✅ Domain events for loose coupling
- ✅ Educational patterns (CS61 Berkeley)

---

## 🏗️ Architecture Principles | المبادئ المعمارية

### 1. Separation of Concerns | فصل الاهتمامات
كل component له مسؤولية واحدة فقط:
- `database.py` → Database only
- `security.py` → Security only
- `ai_gateway.py` → AI integration only

### 2. Dependency Inversion | عكس التبعيات
Components تعتمد على abstractions وليس concrete implementations:
```python
# Good ✅
class Service:
    def __init__(self, db: AsyncSession):
        self.db = db

# Bad ❌
class Service:
    def __init__(self):
        self.db = create_engine(...)  # Hard-coded dependency
```

### 3. Configuration over Code | الإعدادات بدلاً من الكود
استخدام environment variables للإعدادات:
```python
from app.core.config import get_settings

settings = get_settings()
DATABASE_URL = settings.DATABASE_URL  # From environment
```

---

## 📚 Directory Structure | هيكل المجلد

```
app/core/
├── database.py              # Database session management
├── security.py              # Authentication & security
├── ai_gateway.py            # AI/LLM integration
├── di.py                    # Dependency injection
│
├── resilience/              # Resilience patterns
│   ├── circuit_breaker.py   # Circuit breaker
│   ├── retry.py             # Retry logic
│   └── timeout.py           # Timeout handling
│
├── patterns/                # Architectural patterns
│   ├── strategy.py          # Strategy pattern
│   ├── observer.py          # Observer pattern
│   └── factory.py           # Factory pattern
│
├── domain_events/           # Domain events system
│   ├── __init__.py
│   ├── bus.py               # Event bus
│   └── handlers.py          # Event handlers
│
├── gateway/                 # API Gateway patterns
│   ├── mesh.py              # Service mesh
│   └── router.py            # Request routing
│
├── prompts/                 # AI prompt templates
│   └── templates.py
│
└── cs61_*.py                # Educational patterns (Berkeley CS61)
    ├── cs61_concurrency.py  # Concurrency patterns
    ├── cs61_memory.py       # Memory management
    └── cs61_profiler.py     # Performance profiling
```

---

## 🔧 Best Practices | أفضل الممارسات

### 1. استخدام Dependency Injection دائماً
```python
# Good ✅
async def my_endpoint(
    db: AsyncSession = Depends(get_db),
    ai: AIClient = Depends(get_ai_client),
):
    # Dependencies injected
    pass

# Bad ❌
async def my_endpoint():
    db = get_db_directly()  # Hard-coded
    pass
```

### 2. استخدام Type Hints دائماً
```python
# Good ✅
async def get_user(user_id: int, db: AsyncSession) -> User | None:
    return await db.get(User, user_id)

# Bad ❌
async def get_user(user_id, db):
    return await db.get(User, user_id)
```

### 3. معالجة الأخطاء بشكل صحيح
```python
# Good ✅
try:
    result = await risky_operation()
except SpecificException as e:
    logger.error(f"Operation failed: {e}")
    raise HTTPException(status_code=500, detail="Operation failed")

# Bad ❌
try:
    result = await risky_operation()
except:  # Catching all exceptions
    pass  # Silently ignoring
```

---

## 🧪 Testing Guidelines | إرشادات الاختبار

### Unit Tests
اختبار كل component بشكل معزول:
```python
async def test_hash_password():
    """Test password hashing."""
    password = "secure_password"
    hashed = hash_password(password)
    
    assert hashed != password
    assert verify_password(password, hashed)
```

### Integration Tests
اختبار التكامل بين components:
```python
async def test_db_connection():
    """Test database connection."""
    async with get_db() as db:
        result = await db.execute(select(1))
        assert result.scalar() == 1
```

---

## 📖 Related Documentation | الوثائق ذات الصلة

### Core Documentation
- [Database Guide](../../docs/db/SESSION_FACTORY.md)
- [Security Guide](../../docs/audit_and_privacy.md)
- [AI Gateway Guide](../../docs/gateways/AI_GATEWAY.md)

### Architecture Documentation
- [Clean Architecture](../../docs/architecture/)
- [Dependency Injection](../../docs/core/DEPENDENCY_LAYER.md)
- [Domain Events](../../docs/architecture_map.md)

### Best Practices
- [SOLID Principles](../../docs/ARCHITECTURE.md)
- [Error Handling](../../docs/ARCHITECTURE.md)
- [Testing Guide](../../docs/guides/TESTING_GUIDE.md)

---

## 🤝 Contributing | المساهمة

### قبل إضافة component جديد:
1. ✅ تأكد أنه core component (يستخدم من عدة layers)
2. ✅ اتبع Single Responsibility Principle
3. ✅ أضف type hints كاملة
4. ✅ اكتب tests شاملة
5. ✅ وثّق في README

### Code Style
- استخدم black للـ formatting
- استخدم mypy للـ type checking
- استخدم ruff للـ linting

---

## 📞 Support | الدعم

للأسئلة والمساعدة:
- 📖 اقرأ [BEGINNER_GUIDE.md](../../docs/guides/BEGINNER_GUIDE.md)
- 💬 افتح issue في GitHub
- 📧 راسل الفريق التقني

---

**Last Updated:** 2026-01-03  
**Version:** 2.0  
**Maintainer:** CogniForge Team
