# دليل نشر الخدمات المصغرة (Microservices Deployment Guide)

## 🎯 نظرة عامة

هذا الدليل يوضح كيفية نشر وتشغيل نظام CogniForge كمنصة خدمات مصغرة كاملة 100% API-First.

## 🏗️ البنية المعمارية

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway (Port 8000)                 │
│  - التوجيه الذكي                                            │
│  - المصادقة والتفويض                                        │
│  - Circuit Breaker                                           │
│  - Rate Limiting                                             │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Planning    │ │   Memory     │ │    User      │
│   Agent      │ │   Agent      │ │   Service    │
│  (Port 8001) │ │ (Port 8002)  │ │ (Port 8003)  │
└──────────────┘ └──────────────┘ └──────────────┘
        │            │            │
        └────────────┼────────────┘
                     │
        ┌────────────┼────────────┐
        │            │            │
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐
│ Orchestrator │ │Observability │
│   Service    │ │   Service    │
│ (Port 8004)  │ │ (Port 8005)  │
└──────────────┘ └──────────────┘
        │            │
        └────────────┘
                │
                ▼
        ┌──────────────┐
        │  Event Bus   │
        │  (Internal)  │
        └──────────────┘
```

## 📋 المتطلبات الأساسية

### البرمجيات المطلوبة
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.12+
- Git

### الموارد المطلوبة
- CPU: 4 cores minimum
- RAM: 8GB minimum
- Disk: 20GB minimum

## 🚀 التشغيل السريع

### 1. استنساخ المشروع

```bash
git clone https://github.com/Houssam-lab/NAAS-Agentic-Core.git
cd NAAS-Agentic-Core
```

### 2. إعداد المتغيرات البيئية

```bash
cp .env.example .env
# قم بتحرير .env وتعيين القيم المناسبة
```

### 3. بناء وتشغيل الخدمات

```bash
# بناء جميع الخدمات
docker-compose -f docker-compose.microservices.yml build

# تشغيل جميع الخدمات
docker-compose -f docker-compose.microservices.yml up -d

# عرض السجلات
docker-compose -f docker-compose.microservices.yml logs -f
```

### 4. التحقق من الصحة

```bash
# فحص صحة API Gateway
curl http://localhost:8000/gateway/health

# فحص صحة Planning Agent
curl http://localhost:8001/health

# فحص صحة Memory Agent
curl http://localhost:8002/health

# فحص صحة User Service
curl http://localhost:8003/health

# فحص صحة Orchestrator
curl http://localhost:8004/health

# فحص صحة Observability
curl http://localhost:8005/health
```

## 🔧 التكوين المتقدم

### تكوين API Gateway

```yaml
# في docker-compose.microservices.yml
environment:
  - PLANNING_AGENT_URL=http://planning-agent:8001
  - MEMORY_AGENT_URL=http://memory-agent:8002
  - USER_SERVICE_URL=http://user-service:8003
  - ORCHESTRATOR_SERVICE_URL=http://orchestrator-service:8004
  - OBSERVABILITY_SERVICE_URL=http://observability-service:8005
```

### تكوين Circuit Breaker

```python
# في app/gateway/config.py
from app.gateway.circuit_breaker import CircuitBreakerConfig

circuit_breaker_config = CircuitBreakerConfig(
    failure_threshold=5,      # عدد الفشل قبل فتح الدائرة
    success_threshold=2,      # عدد النجاح لإغلاق الدائرة
    timeout=60,               # مدة بقاء الدائرة مفتوحة (ثواني)
    half_open_max_calls=3,    # عدد الطلبات في حالة نصف مفتوحة
)
```

### تكوين Service Discovery

```python
# في app/gateway/discovery.py
discovery = ServiceDiscovery(
    registry=service_registry,
    health_check_interval=30,  # فترة فحص الصحة (ثواني)
    heartbeat_timeout=90,       # مهلة نبضة القلب (ثواني)
)
```

## 📊 المراقبة والتشخيص

### عرض حالة جميع الخدمات

```bash
# عبر API Gateway
curl http://localhost:8000/gateway/health | jq

# النتيجة:
{
  "gateway": "healthy",
  "services": {
    "planning-agent": {
      "healthy": true,
      "response_time_ms": 15.2,
      "last_check": "2024-01-08T19:30:00Z"
    },
    "memory-agent": {
      "healthy": true,
      "response_time_ms": 12.8,
      "last_check": "2024-01-08T19:30:00Z"
    }
  },
  "summary": {
    "healthy": 5,
    "total": 5,
    "percentage": 100.0
  }
}
```

### عرض الخدمات المسجلة

```bash
curl http://localhost:8000/gateway/services | jq
```

### عرض إحصائيات Circuit Breaker

```bash
# سيتم إضافة endpoint مخصص
curl http://localhost:8000/gateway/circuit-breakers | jq
```

## 🔄 التوسع (Scaling)

### توسيع خدمة معينة

```bash
# توسيع Planning Agent إلى 3 نسخ
docker-compose -f docker-compose.microservices.yml up -d --scale planning-agent=3

# توسيع Memory Agent إلى 2 نسخ
docker-compose -f docker-compose.microservices.yml up -d --scale memory-agent=2
```

### موازنة الحمل التلقائية

API Gateway يوفر موازنة حمل تلقائية بين نسخ الخدمات:

```python
# في app/gateway/discovery.py
def get_healthy_instance(self, name: str) -> ServiceInstance | None:
    """يحصل على مثيل صحي للخدمة (موازنة حمل)."""
    # يستخدم Round Robin بشكل افتراضي
    # يمكن تخصيص الخوارزمية حسب الحاجة
```

## 🧪 الاختبار

### اختبارات الوحدة

```bash
# اختبار Gateway
pytest tests/test_gateway.py -v

# اختبار Event Bus
pytest tests/test_event_bus.py -v

# اختبار Circuit Breaker
pytest tests/test_circuit_breaker.py -v
```

### اختبارات التكامل

```bash
# اختبار التكامل بين الخدمات
pytest tests/integration/test_microservices_integration.py -v
```

### اختبار الحمل

```bash
# استخدام Apache Bench
ab -n 1000 -c 10 http://localhost:8000/gateway/health

# استخدام wrk
wrk -t4 -c100 -d30s http://localhost:8000/gateway/health
```

## 🔐 الأمان

### المصادقة والتفويض

جميع الطلبات عبر API Gateway تتطلب JWT token:

```bash
# الحصول على token
curl -X POST http://localhost:8000/api/security/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "password"}'

# استخدام token
curl http://localhost:8000/gateway/planning-agent/plans \
  -H "Authorization: Bearer <token>"
```

### Rate Limiting

API Gateway يطبق تحديد معدل تلقائي:

```python
# في app/gateway/config.py
GatewayConfig(
    enable_rate_limiting=True,
    max_requests_per_minute=100,
)
```

## 📝 السجلات (Logging)

### عرض سجلات خدمة معينة

```bash
# Planning Agent
docker-compose -f docker-compose.microservices.yml logs -f planning-agent

# Memory Agent
docker-compose -f docker-compose.microservices.yml logs -f memory-agent

# API Gateway
docker-compose -f docker-compose.microservices.yml logs -f api-gateway
```

### تجميع السجلات

```bash
# جميع الخدمات
docker-compose -f docker-compose.microservices.yml logs -f

# خدمات محددة
docker-compose -f docker-compose.microservices.yml logs -f planning-agent memory-agent
```

## 🛠️ استكشاف الأخطاء

### الخدمة لا تستجيب

```bash
# 1. فحص حالة الحاوية
docker ps | grep cogniforge

# 2. فحص السجلات
docker logs cogniforge-planning-agent

# 3. إعادة تشغيل الخدمة
docker-compose -f docker-compose.microservices.yml restart planning-agent
```

### Circuit Breaker مفتوح

```bash
# 1. فحص حالة الخدمة
curl http://localhost:8001/health

# 2. إعادة تعيين Circuit Breaker
# سيتم إضافة endpoint مخصص

# 3. إعادة تشغيل الخدمة
docker-compose -f docker-compose.microservices.yml restart planning-agent
```

### مشاكل الاتصال بين الخدمات

```bash
# 1. فحص الشبكة
docker network inspect cogniforge-network

# 2. اختبار الاتصال
docker exec cogniforge-gateway ping planning-agent

# 3. فحص DNS
docker exec cogniforge-gateway nslookup planning-agent
```

## 🔄 التحديث والنشر

### نشر تحديث لخدمة معينة

```bash
# 1. بناء الصورة الجديدة
docker-compose -f docker-compose.microservices.yml build planning-agent

# 2. إيقاف الخدمة القديمة
docker-compose -f docker-compose.microservices.yml stop planning-agent

# 3. تشغيل الخدمة الجديدة
docker-compose -f docker-compose.microservices.yml up -d planning-agent
```

### نشر Blue-Green

```bash
# 1. تشغيل النسخة الجديدة على منفذ مختلف
docker-compose -f docker-compose.microservices.yml up -d planning-agent-v2

# 2. تحديث API Gateway للتوجيه إلى النسخة الجديدة
# (يتم عبر تحديث التكوين)

# 3. إيقاف النسخة القديمة
docker-compose -f docker-compose.microservices.yml stop planning-agent
```

## 📚 الموارد الإضافية

### الوثائق

- [API Contracts](./contracts/openapi/)
- [Event Bus Specification](./contracts/asyncapi/event-bus.yaml)
- [Gateway API](./contracts/openapi/gateway-api.yaml)

### أدوات مفيدة

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Dashboard**: http://localhost:8000/gateway/health

## 🎓 أفضل الممارسات

### 1. فصل المخاوف (Separation of Concerns)

كل خدمة مسؤولة عن مجال واحد فقط:
- Planning Agent: التخطيط فقط
- Memory Agent: الذاكرة فقط
- User Service: المستخدمين فقط

### 2. API-First

جميع الخدمات تعرض API موثق بالكامل قبل التنفيذ.

### 3. Zero Trust

كل طلب يتم التحقق منه، حتى الطلبات الداخلية.

### 4. Observability

جميع الخدمات توفر:
- Health checks
- Metrics
- Logs
- Traces

### 5. Resilience

استخدام:
- Circuit Breaker
- Retry Logic
- Timeout
- Fallback

## 🆘 الدعم

للحصول على المساعدة:
- GitHub Issues: https://github.com/Houssam-lab/NAAS-Agentic-Core/issues
- Email: support@cogniforge.ai
- Documentation: https://docs.cogniforge.ai
