# CS61 Application Guide | دليل تطبيق CS61
# ==========================================

**Complete guide for applying CS61 principles across the CogniForge codebase.**

---

## 🎯 Overview | نظرة عامة

This guide shows how to apply CS61 Systems Programming principles throughout the codebase using the three core modules:

1. **cs61_profiler.py** - Performance monitoring
2. **cs61_memory.py** - Memory management
3. **cs61_concurrency.py** - Thread safety & concurrency

---

## 📊 1. Performance Profiling | قياس الأداء

### When to Use Profiling

- **API endpoints** - Track request latency
- **Database queries** - Identify slow queries
- **AI/LLM calls** - Monitor model performance
- **Heavy computations** - Find bottlenecks

### Example: Profile API Endpoint

```python
from fastapi import APIRouter
from app.core.cs61_profiler import profile_async

router = APIRouter()

@router.get("/users/{user_id}")
@profile_async  # CS61: Auto-profile this endpoint
async def get_user(user_id: int):
    # This function's performance is now tracked
    user = await fetch_user(user_id)
    return user
```

### Example: Profile Database Operations

```python
from app.core.cs61_profiler import profile_async
from app.core.database import get_db

@profile_async
async def get_user_by_id(db: AsyncSession, user_id: int) -> User:
    """CS61: Profiled database query."""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()
```

### Example: Get Performance Report

```python
from app.core.cs61_profiler import print_performance_report

# In your admin panel or CLI command:
print_performance_report()
```

**Output:**
```
================================================================================
CS61 PERFORMANCE REPORT | تقرير الأداء
================================================================================

📊 get_user
   Calls: 1250
   Total: 3450.23ms
   Avg:   2.76ms
   Range: [1.23ms - 45.67ms]
   P50:   2.50ms
   P95:   5.80ms
   P99:   12.30ms
```

---

## 💾 2. Memory Management | إدارة الذاكرة

### When to Use Memory Management

- **Caching** - Bounded caches prevent memory exhaustion
- **Recent items** - Keep only last N entries
- **Object pooling** - Reuse expensive objects
- **Memory leak detection** - Track object lifecycles

### Example: Bounded Cache

```python
from app.core.cs61_memory import BoundedDict

# CS61: LRU cache with fixed memory footprint
user_cache = BoundedDict[User](maxsize=1000)

async def get_user_cached(user_id: int) -> User:
    """Cached user lookup with bounded memory."""
    cache_key = f"user:{user_id}"
    
    # Check cache
    if cache_key in user_cache:
        return user_cache[cache_key]
    
    # Fetch from database
    user = await db.get(User, user_id)
    
    # Store in cache (auto-evicts oldest if full)
    user_cache[cache_key] = user
    
    return user
```

### Example: Recent Activity List

```python
from app.core.cs61_memory import BoundedList

# CS61: Keep only last 100 activities (bounded memory)
recent_activities = BoundedList[dict](maxlen=100)

def log_activity(user_id: int, action: str):
    """Log activity with automatic old entry removal."""
    activity = {
        'user_id': user_id,
        'action': action,
        'timestamp': time.time()
    }
    recent_activities.append(activity)  # Old entries auto-removed
```

### Example: Object Pooling

```python
from app.core.cs61_memory import ObjectPool
import httpx

# CS61: Reuse HTTP clients instead of creating/destroying
def create_http_client():
    return httpx.AsyncClient(timeout=30.0)

http_pool = ObjectPool(factory=create_http_client, size=10)

async def fetch_external_data(url: str):
    """Use pooled HTTP client."""
    with http_pool.acquire() as client:
        response = await client.get(url)
        return response.json()
```

### Example: Memory Leak Detection

```python
from app.core.cs61_memory import MemoryTracker

# CS61: Track objects to detect leaks
tracker = MemoryTracker()

def create_user_session(user_id: int):
    session = UserSession(user_id)
    tracker.track(session, 'user_sessions')
    return session

# Later: Check for leaks
tracker.print_report()
```

---

## 🔄 3. Concurrency & Thread Safety | التزامن والأمان

### When to Use Concurrency Tools

- **Rate limiting** - Prevent API abuse
- **Thread-safe counters** - Atomic operations
- **Resource pools** - Limit concurrent operations
- **Worker pools** - Process tasks in parallel

### Example: Rate Limiting

```python
from fastapi import HTTPException
from app.core.cs61_concurrency import ThreadSafeRateLimiter

# CS61: Sliding window rate limiter
rate_limiter = ThreadSafeRateLimiter(
    requests_per_window=100,  # 100 requests
    window_seconds=60.0       # per minute
)

@router.post("/api/generate")
async def generate_content(request: Request):
    """Rate-limited API endpoint."""
    user_id = request.state.user.id
    
    if not rate_limiter.allow_request(f"user:{user_id}"):
        raise HTTPException(status_code=429, detail="Too many requests")
    
    # Process request
    return await generate_ai_content()
```

### Example: Thread-Safe Counter

```python
from app.core.cs61_concurrency import ThreadSafeCounter

# CS61: Atomic counter for concurrent access
request_counter = ThreadSafeCounter()

async def handle_request():
    """Thread-safe request counting."""
    request_counter.increment()
    
    try:
        # Process request
        pass
    finally:
        request_counter.decrement()

# Get current count (thread-safe)
active_requests = request_counter.value
```

### Example: Semaphore Pool

```python
from app.core.cs61_concurrency import SemaphorePool

# CS61: Limit concurrent AI requests
ai_pool = SemaphorePool(max_concurrent=5)

async def call_ai_model(prompt: str):
    """Limit concurrent AI calls to prevent overload."""
    async with ai_pool.acquire():
        # Only 5 AI calls run simultaneously
        response = await ai_client.generate(prompt)
        return response
```

### Example: Worker Pool

```python
from app.core.cs61_concurrency import AsyncWorkerPool

# CS61: Process tasks with fixed worker count
worker_pool = AsyncWorkerPool(num_workers=10)

async def process_batch(items: list):
    """Process items using worker pool."""
    await worker_pool.start()
    
    for item in items:
        await worker_pool.submit(process_item, item)
    
    await worker_pool.shutdown(wait=True)
```

---

## 🏗️ 4. Complete Example: Enhanced Service

Here's a complete example showing all CS61 principles in a service:

```python
"""
Enhanced User Service with CS61 Principles
"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.cs61_profiler import profile_async
from app.core.cs61_memory import BoundedDict
from app.core.cs61_concurrency import ThreadSafeRateLimiter


class UserService:
    """
    خدمة المستخدمين المحسنة (CS61-Enhanced User Service).
    """
    
    def __init__(self):
        # CS61: Bounded cache (prevents memory exhaustion)
        self._cache = BoundedDict[User](maxsize=500)
        
        # CS61: Rate limiter (prevents abuse)
        self._rate_limiter = ThreadSafeRateLimiter(
            requests_per_window=100,
            window_seconds=60.0
        )
    
    @profile_async  # CS61: Performance monitoring
    async def get_user(
        self,
        db: AsyncSession,
        user_id: int
    ) -> User | None:
        """
        الحصول على مستخدم (Get user with caching).
        
        CS61 Optimizations:
        - Profiled for performance tracking
        - LRU cache with bounded memory
        - Efficient database queries
        """
        cache_key = f"user:{user_id}"
        
        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Query database
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        # Cache result
        if user:
            self._cache[cache_key] = user
        
        return user
    
    @profile_async
    async def create_user(
        self,
        db: AsyncSession,
        user_data: UserCreate,
        request_key: str
    ) -> User:
        """
        إنشاء مستخدم (Create user with rate limiting).
        
        CS61 Optimizations:
        - Rate limited to prevent abuse
        - Profiled for performance
        - Cache invalidation
        """
        # CS61: Check rate limit
        if not self._rate_limiter.allow_request(request_key):
            raise ValueError("Rate limit exceeded")
        
        # Create user
        user = User(**user_data.dict())
        db.add(user)
        await db.commit()
        await db.refresh(user)
        
        # Add to cache
        cache_key = f"user:{user.id}"
        self._cache[cache_key] = user
        
        return user
```

---

## 📈 5. Monitoring & Observability | المراقبة

### Get Performance Statistics

```python
from app.core.cs61_profiler import get_performance_stats

# Get all stats as JSON
stats = get_performance_stats()

# Example output:
{
    "get_user": {
        "calls": 1250,
        "avg_ms": 2.76,
        "p95_ms": 5.80,
        "p99_ms": 12.30
    },
    "create_user": {
        "calls": 45,
        "avg_ms": 15.23,
        "p95_ms": 25.40,
        "p99_ms": 35.10
    }
}
```

### Check Memory Usage

```python
from app.core.cs61_profiler import get_memory_usage

mem = get_memory_usage()
print(f"Memory: {mem['rss_mb']:.2f} MB")
print(f"Percent: {mem['percent']:.1f}%")
```

### Monitor Connection Pool

```python
from app.core.database import get_pool_status

pool_stats = get_pool_status()
print(f"Pool size: {pool_stats['size']}")
print(f"In use: {pool_stats['checked_out']}")
print(f"Available: {pool_stats['checked_in']}")
```

---

## 🎨 6. Best Practices | أفضل الممارسات

### ✅ DO: Profile Hot Paths

```python
@profile_async  # Always profile frequently called functions
async def get_user_feed(user_id: int):
    pass
```

### ✅ DO: Use Bounded Collections

```python
# Good: Bounded memory
cache = BoundedDict(maxsize=1000)

# Bad: Unbounded (memory leak risk)
cache = {}  # Can grow forever
```

### ✅ DO: Rate Limit External Calls

```python
# Good: Rate limited
if limiter.allow_request(user_id):
    await call_external_api()
```

### ✅ DO: Use Object Pools

```python
# Good: Reuse connections
with http_pool.acquire() as client:
    await client.get(url)

# Bad: Create/destroy every time
client = httpx.AsyncClient()  # Expensive!
```

### ❌ DON'T: Profile Everything

```python
# Bad: Too granular
@profile_async
def add_two_numbers(a, b):
    return a + b  # Too simple to profile
```

### ❌ DON'T: Use Unbounded Caches

```python
# Bad: Memory leak waiting to happen
cache = {}  # No size limit!
```

---

## 🔧 7. Migration Checklist | قائمة الترحيل

When applying CS61 to existing code:

- [ ] Add `@profile_async` to all database queries
- [ ] Add `@profile_async` to all API endpoints
- [ ] Replace `dict` caches with `BoundedDict`
- [ ] Replace `list` logs with `BoundedList`
- [ ] Add rate limiting to public APIs
- [ ] Add thread-safe counters for shared state
- [ ] Use `SemaphorePool` for expensive operations
- [ ] Track object pools with `MemoryTracker`
- [ ] Monitor performance with `print_performance_report()`
- [ ] Check connection pool with `get_pool_status()`

---

## 📚 8. Additional Resources | موارد إضافية

- **CS61_SYSTEMS_PROGRAMMING.md** - Complete theory guide
- **test_cs61_*.py** - 97 test examples
- **SIMPLIFICATION_GUIDE.md** - Migration from old abstractions

---

**Remember:** CS61 principles = Simple, Fast, Reliable

Built with ❤️ following Berkeley CS61
