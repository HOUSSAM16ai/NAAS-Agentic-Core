# Memory Agent Service

## الدور والمسؤولية
خدمة مستقلة لإدارة الذاكرة والسياق (التخزين، البحث، الاسترجاع).

## دليل قاطع من الشيفرة (Code-Backed Facts)

### 1) الخدمة تعمل كـ FastAPI مستقل مع عزل دورة حياة
- التطبيق يُنشأ عبر `create_app()` ويُشغَّل بـ `lifespan` خاص به.
- قاعدة البيانات تُهيَّأ عند الإقلاع عبر `init_db()`.
- التهيئة، التسجيل، ومعالجة الأخطاء كلها محلية داخل الخدمة.

### 2) مبدأ Zero Trust مطبق فعليًا
- المسارات العامة (`/health`) منفصلة.
- مسارات الذاكرة والمعرفة تُحمى عبر `Depends(verify_service_token)`.
- هذا يعني أن أي استدعاء بين الخدمات يحتاج هوية خدمة صالحة.

### 3) الطبقات مفصولة بوضوح (Functional Core + Imperative Shell)
- API Layer: في `main.py` و`src/api/knowledge.py`.
- Service Layer: في `src/services/memory_service.py`.
- Repository Layer: في `src/repositories/memory_repository.py`.
- النتيجة: منطق الأعمال لا يحتوي SQL مباشر، والوصول للبيانات لا يحتوي منطق واجهات.

### 4) دليل الربط الهجين مع المونوليث
- المونوليث لا يستورد نماذج المايكروسرفيس مباشرة؛ بل يعيد تعريف DTOs محليًا لكسر الاقتران.
- التواصل يتم عبر HTTP فقط (`httpx.AsyncClient`) داخل `app/infrastructure/clients/memory_client.py`.
- هذا يؤكد نمط: API Shell (app) + Remote Capability (memory_agent).

### 5) سلوك البحث في الذاكرة مثبت في repository
- البحث النصي يستخدم `ilike` على المحتوى والوسوم.
- البحث المتقدم يدعم مرشحات الوسوم مع `IN` و`outerjoin`.
- الاسترجاع يتم بتحميل الوسوم (`selectinload`) لتقليل مشاكل N+1.

## التشغيل محليًا

```bash
uvicorn microservices.memory_agent.main:app --reload --host 0.0.0.0 --port 8002
```

## الإعدادات الأساسية

- `DATABASE_URL`: سلسلة اتصال قاعدة البيانات (افتراضيًا SQLite داخلية).
- `SERVICE_NAME`: اسم الخدمة المعروض في `/health`.

## نقاط النهاية الأساسية

- `GET /health`
- `POST /memories`
- `GET /memories/search`
- `POST /memories/search`
- `GET /memories/{id}`
- `GET /knowledge/concepts/search`
- `GET /knowledge/concepts/{concept_id}`
- `GET /knowledge/concepts/{concept_id}/prerequisites`
- `GET /knowledge/concepts/{concept_id}/related`
- `GET /knowledge/concepts/{concept_id}/next`
- `POST /knowledge/paths`
- `POST /knowledge/readiness`

## الاختبارات

```bash
pytest tests/services/memory_agent
```

## التصحيح (Debug)

- تأكد من صحة بيانات الإدخال في عمليات الحفظ والبحث.
- راجع إعدادات قاعدة البيانات عند ظهور أخطاء اتصال.
