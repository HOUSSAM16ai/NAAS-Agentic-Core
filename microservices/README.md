# 🚀 CogniForge Microservices Platform

## نظام خدمات مصغرة 100% API-First احترافي

[![API-First](https://img.shields.io/badge/Architecture-API--First-blue)](../docs/API_FIRST_ARCHITECTURE.md)
[![Microservices](https://img.shields.io/badge/Pattern-Microservices-green)](../docs/MICROSERVICES_PLATFORM.md)
[![Python](https://img.shields.io/badge/Python-3.12+-yellow)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-teal)](https://fastapi.tiangolo.com)

---

## 📋 جدول المحتويات

- [نظرة عامة](#-نظرة-عامة)
- [البنية المعمارية](#-البنية-المعمارية)
- [الخدمات المصغرة](#-الخدمات-المصغرة)
- [التشغيل السريع](#-التشغيل-السريع)
- [الميزات الرئيسية](#-الميزات-الرئيسية)
- [الاختبارات](#-الاختبارات)
- [الوثائق](#-الوثائق)
- [المساهمة](#-المساهمة)

---

## 🎯 نظرة عامة

CogniForge هو نظام تعليمي ذكي مبني على معمارية **Microservices API-First** بشكل كامل. يتبع النظام أفضل الممارسات العالمية من:

- ✅ **Harvard CS50 2025**: صرامة النوع والوضوح
- ✅ **Berkeley SICP**: حواجز التجريد والتركيب الوظيفي
- ✅ **API-First Design**: العقود قبل التنفيذ
- ✅ **Domain-Driven Design**: سياقات محددة واضحة
- ✅ **Zero Trust Security**: كل طلب يتم التحقق منه

---

## 🏗️ البنية المعمارية

### المكونات الأساسية

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway (8000)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Routing    │  │ Circuit      │  │ Rate         │      │
│  │   Engine     │  │ Breaker      │  │ Limiting     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
        ▼            ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Planning    │ │   Memory     │ │    User      │ │ Orchestrator │
│   Agent      │ │   Agent      │ │   Service    │ │   Service    │
│  (8001)      │ │  (8002)      │ │  (8003)      │ │  (8004)      │
│              │ │              │ │              │ │              │
│ - Plans      │ │ - Memories   │ │ - Users      │ │ - Tasks      │
│ - Goals      │ │ - Context    │ │ - Auth       │ │ - Agents     │
│ - Steps      │ │ - Tags       │ │ - Profiles   │ │ - Workflow   │
└──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘
        │            │            │            │
        └────────────┴────────────┴────────────┘
                     │
                     ▼
        ┌────────────────────────┐
        │     Event Bus          │
        │  (Pub/Sub Pattern)     │
        │                        │
        │ - user.created         │
        │ - plan.created         │
        │ - memory.stored        │
        │ - learning.progress    │
        └────────────────────────┘
```

### المبادئ المعمارية

#### 1. API-First
- **العقود أولاً**: OpenAPI/AsyncAPI قبل التنفيذ
- **التوثيق التلقائي**: Swagger UI + ReDoc
- **التحقق التلقائي**: Pydantic schemas
- **الإصدارات**: Semantic versioning

#### 2. Bounded Contexts
- **Planning Agent**: التخطيط التعليمي فقط
- **Memory Agent**: إدارة الذاكرة والسياق
- **User Service**: إدارة المستخدمين والمصادقة
- **Orchestrator**: تنسيق الوكلاء
- **Observability**: المراقبة والتشخيص

#### 3. Communication Patterns
- **Synchronous**: REST API عبر Gateway
- **Asynchronous**: Event Bus للأحداث
- **Service Discovery**: تسجيل واكتشاف ديناميكي

#### 4. Resilience Patterns
- **Circuit Breaker**: حماية من الفشل المتتالي
- **Retry Logic**: إعادة المحاولة التلقائية
- **Timeout**: مهلة محددة لكل طلب
- **Fallback**: قيم احتياطية عند الفشل

---

## 🔧 الخدمات المصغرة

### 1. API Gateway (Port 8000)

**المسؤولية**: نقطة الدخول المركزية

**الميزات**:
- ✅ توجيه ذكي للطلبات
- ✅ مصادقة وتفويض مركزي
- ✅ Circuit Breaker لكل خدمة
- ✅ Rate Limiting
- ✅ فحص صحة الخدمات
- ✅ موازنة الحمل

**API Endpoints**:
```
GET  /gateway/health          - صحة البوابة والخدمات
GET  /gateway/services        - الخدمات المسجلة
GET  /gateway/{service}/{path} - توجيه الطلبات
```

**Contract**: [gateway-api.yaml](../docs/contracts/openapi/gateway-api.yaml)

---

### 2. Planning Agent (Port 8001)

**المسؤولية**: توليد الخطط التعليمية

**الميزات**:
- ✅ إنشاء خطط مخصصة
- ✅ تجزئة الأهداف
- ✅ تسلسل الخطوات
- ✅ تحسين الخطط

**API Endpoints**:
```
GET  /health                  - فحص الصحة
POST /plans                   - إنشاء خطة جديدة
GET  /plans                   - عرض جميع الخطط
GET  /plans/{id}              - تفاصيل خطة
```

**Contract**: [planning_agent-openapi.json](../docs/contracts/openapi/planning_agent-openapi.json)

**Database**: SQLite (مستقل)

**Service README**: [microservices/planning_agent/README.md](planning_agent/README.md)

---

### 3. Memory Agent (Port 8002)

**المسؤولية**: إدارة الذاكرة والسياق

**الميزات**:
- ✅ حفظ الذاكرة
- ✅ البحث الدلالي
- ✅ الوسوم (Tags)
- ✅ استرجاع السياق

**API Endpoints**:
```
GET  /health                  - فحص الصحة
POST /memories                - حفظ ذاكرة جديدة
GET  /memories/search         - البحث في الذاكرة
GET  /memories/{id}           - تفاصيل ذاكرة
```

**Contract**: [memory_agent-openapi.json](../docs/contracts/openapi/memory_agent-openapi.json)

**Database**: SQLite (مستقل)

**Service README**: [microservices/memory_agent/README.md](memory_agent/README.md)

---

### 4. User Service (Port 8003)

**المسؤولية**: إدارة المستخدمين

**الميزات**:
- ✅ تسجيل المستخدمين
- ✅ المصادقة
- ✅ الملفات الشخصية
- ✅ الصلاحيات

**API Endpoints**:
```
GET  /health                  - فحص الصحة
POST /users                   - إنشاء مستخدم
GET  /users                   - عرض المستخدمين
GET  /users/{id}              - تفاصيل مستخدم
PUT  /users/{id}              - تحديث مستخدم
```

**Contract**: [user_service-openapi.json](../docs/contracts/openapi/user_service-openapi.json)

**Database**: SQLite (مستقل)

**Service README**: [microservices/user_service/README.md](user_service/README.md)

---

### 5. Orchestrator Service (Port 8004)

**المسؤولية**: تنسيق الوكلاء

**الميزات**:
- ✅ تسجيل الوكلاء
- ✅ توزيع المهام
- ✅ تتبع التقدم
- ✅ إدارة Workflow

**API Endpoints**:
```
GET  /health                  - فحص الصحة
GET  /orchestrator/agents     - الوكلاء المسجلين
POST /orchestrator/tasks      - إنشاء مهمة
GET  /orchestrator/tasks      - عرض المهام
```

**Contract**: [orchestrator_service-openapi.json](../docs/contracts/openapi/orchestrator_service-openapi.json)

**Database**: SQLite (مستقل)

**Service README**: [orchestrator_service/](orchestrator_service/)

---

### 6. Observability Service (Port 8005)

**المسؤولية**: المراقبة والتشخيص

**الميزات**:
- ✅ جمع المقاييس
- ✅ التنبؤ بالحمل
- ✅ تحليل الأداء
- ✅ اكتشاف الشذوذ

**API Endpoints**:
```
GET  /health                  - فحص الصحة
POST /telemetry               - جمع البيانات
GET  /metrics                 - المقاييس
POST /forecast                - التنبؤ
```

**Contract**: [observability_service-openapi.json](../docs/contracts/openapi/observability_service-openapi.json)

**Service README**: [microservices/observability_service/README.md](observability_service/README.md)

---

## 🚀 التشغيل السريع

### المتطلبات

```bash
# التحقق من الإصدارات
docker --version    # 20.10+
docker-compose --version  # 2.0+
python --version    # 3.12+
```

### التثبيت

```bash
# 1. استنساخ المشروع
git clone https://github.com/Houssam-lab/NAAS-Agentic-Core.git
cd NAAS-Agentic-Core

# 2. تثبيت المتطلبات
make install

# 3. بناء الخدمات
make microservices-build

# 4. تشغيل الخدمات
make microservices-up

# 5. فحص الصحة
make microservices-health
```

### الوصول إلى الخدمات

```bash
# API Gateway
open http://localhost:8000/docs

# Planning Agent
open http://localhost:8001/docs

# Memory Agent
open http://localhost:8002/docs

# User Service
open http://localhost:8003/docs

# Orchestrator
open http://localhost:8004/docs

# Observability
open http://localhost:8005/docs
```

---

## ✨ الميزات الرئيسية

### 1. Service Discovery

في بيئات الخدمات المصغّرة يُفضّل الاعتماد على أدوات اكتشاف الخدمات (مثل Consul أو DNS)
بدلاً من الاعتماد على مكتبات مشتركة بين الخدمات. مثال مبسّط باستخدام DNS:

```python
service_base_url = "http://user-service:8003"
response = await http_client.get(f"{service_base_url}/health")
```

### 2. Circuit Breaker

يُفضّل تطبيق قاطع الدارة على مستوى كل خدمة (أو عبر Service Mesh)
بدون مشاركة منطق عبر مكتبات مشتركة:

```python
try:
    result = await http_client.post("http://planning-agent:8001/plan", json=payload)
except TimeoutError:
    result = fallback_value
```

### 3. Event Bus

التكامل عبر الأحداث يجب أن يتم عبر ناقل رسائل مستقل (Kafka/RabbitMQ)
مع عقود واضحة بدل مشاركة كود منطقي بين الخدمات:

```python
await event_bus.publish(
    topic="user.created",
    payload={"user_id": "123"},
    source="user-service",
)
```

---

## 🧪 الاختبارات

### تشغيل جميع الاختبارات

```bash
make microservices-test
```

### اختبارات محددة

```bash
# Gateway
make gateway-test

# Event Bus
make event-bus-test

# Circuit Breaker
make circuit-breaker-test

# Integration
make integration-test
```

### تغطية الاختبارات

```bash
pytest --cov=app --cov-report=html
open htmlcov/index.html
```

---

## 📚 الوثائق

### API Contracts

- [Core API](../docs/contracts/openapi/core-api-v1.yaml)
- [Gateway API](../docs/contracts/openapi/gateway-api.yaml)
- [Event Bus](../docs/contracts/asyncapi/event-bus.yaml)

### Architecture Docs

- [API-First Architecture](../docs/API_FIRST_ARCHITECTURE.md)ECTURE.md)
- [Microservices Platform](../docs/MICROSERVICES_PLATFORM.md)
- [Deployment Guide](../docs/MICROSERVICES_DEPLOYMENT_GUIDE.md)

### Code Documentation

```bash
# توليد الوثائق
make docs

# عرض الوثائق
open docs/_build/html/index.html
```

---

## 🤝 المساهمة

نرحب بالمساهمات! يرجى اتباع الخطوات التالية:

1. Fork المشروع
2. إنشاء فرع للميزة (`git checkout -b feature/amazing-feature`)
3. Commit التغييرات (`git commit -m 'Add amazing feature'`)
4. Push إلى الفرع (`git push origin feature/amazing-feature`)
5. فتح Pull Request

### معايير الكود

```bash
# قبل الـ commit
make quality
make test
```

---

## 📄 الترخيص

MIT License - انظر [LICENSE](../LICENSE) للتفاصيل.

---

## 🙏 شكر وتقدير

- **Harvard CS50**: للمعايير الصارمة
- **Berkeley SICP**: للمبادئ المعمارية
- **FastAPI**: للإطار الممتاز
- **Python Community**: للدعم المستمر

---

## 📞 التواصل

- **GitHub**: [@HOUSSAM16ai](https://github.com/HOUSSAM16ai)
- **Email**: support@cogniforge.ai
- **Documentation**: https://docs.cogniforge.ai

---

**Built with ❤️ using API-First Microservices Architecture**
