# CogniForge — Claude Code Context

> منصة تعليمية ذكية (AI Tutor) لطلاب البكالوريا في الجزائر.
> بنية تشغيلية هجينة: Reality Kernel في `app/` + شبكة خدمات مصغّرة في `microservices/`.

---

## 1) التشريح المعماري الكامل (Code-Verified)

### A. طبقة الدخول (Ingress)
- **الويب/العميل**: واجهات ثابتة وواجهات React/Next حسب بيئة التشغيل.
- **API Gateway/Kernel**:
  - `app/main.py` نقطة تشغيل التطبيق.
  - `app/kernel.py` يُنشئ التطبيق عبر خط أنابيب تركيبي (تهيئة + Middleware + Routers + فحوصات التوافق).
  - `app/api/routers/registry.py` سجل مركزي للـ routers.

### B. نواة التركيب (Reality Kernel as Evaluator)
- النمط المعتمد: **Functional Core, Imperative Shell**.
- تمثيل الـ middleware والـ routes كبيانات declarative في `app/core/app_blueprint.py` ثم تطبيقها عبر دوال تركيب.
- النتيجة: تبديل/إضافة Middleware أو Router بدون كسر الطبقات الأعلى.

### C. طبقة الـ API داخل `app/`
- الملفات تحت `app/api/routers/` تعمل كطبقة توجيه فقط (HTTP boundary).
- منطق الأعمال يجب أن يبقى في الخدمات (`app/services/`) أو طبقات المجال، وليس داخل handlers مباشرة.
- العقود (schemas) تحت `app/api/schemas/`.

### D. طبقة الخدمات والنواة المشتركة
- `app/core/` يحتوي البنية التحتية العرضية: أخطاء، بروتوكولات، resilience patterns، db wiring، event contracts.
- `app/services/` يحتوي منطق التنفيذ الخاص بالمجالات داخل الـ shell.
- `app/infrastructure/clients/` يفرض حدود الاتصال عبر HTTP مع الخدمات المستقلة.

### E. طبقة الخدمات المصغرة (Microservices Mesh)
المجلد `microservices/` يحتوي خدمات مستقلة تشغيليًا، أهمها:
- `api_gateway`
- `user_service`
- `observability_service`
- `reasoning_agent`
- `research_agent`
- (وفي البيئات/الفروع الداعمة: orchestrator/planning/memory بحسب التفعيل)

لكل خدمة: نقطة دخول، إعدادات، طبقة API، طبقة domain/service، واعتمادات تشغيل (Dockerfile/requirements).

### F. تدفقات التكامل بين الطبقات
- الاتصال بين الخدمات يتم عبر HTTP clients (مبدأ API-First).
- ممنوع الوصول المباشر لقاعدة بيانات خدمة أخرى.
- `X-Correlation-ID` مطلوب لضمان التتبع الموزع.

---

## 2) خريطة التنفيذ (Execution Topology)

```text
Client/UI
  -> FastAPI Kernel (app/main.py -> app/kernel.py)
    -> Router Registry (app/api/routers/registry.py)
      -> Local service/domain execution (app/services + app/core)
      -> Remote delegation (app/infrastructure/clients/*)
         -> microservices/<service>/...
```

---

## 3) مناطق المسؤولية (Boundaries)

1. `app/*` = بوابة التركيب والتنسيق العام (Control Plane).
2. `microservices/*` = وحدات أعمال مستقلة (Execution Plane).
3. `docs/architecture/*` = الدستور المعماري وقرارات التصميم.
4. `.memory/*` = ذاكرة تشغيلية مختصرة يجب أن تعكس الواقع التنفيذي الفعلي.

---

## 4) مخاطر معمارية حالية

1. **Drift بين الوثائق والكود** عند تطور الخدمات بسرعة.
2. **Coupling خفي** إذا تم تمرير نماذج داخلية بين خدمات بدل عقود API صريحة.
3. **اختلاط أدوار app shell** إذا زاد منطق الأعمال داخل route handlers.
4. **تباين جاهزية الخدمات** بين local/dev/prod بدون health contracts موحدة.

---

## 5) قواعد تشغيلية إلزامية عند التعديل

- قبل أي تعديل معماري: راجع `docs/architecture/MICROSERVICES_CONSTITUTION.md`.
- أي تغيير في طوبولوجيا النظام يستلزم تحديثًا متزامنًا لـ:
  1) `CLAUDE.md`
  2) `.memory/architecture.md`
  3) `.memory/decisions.md`
  4) `.memory/context.md`
- لا توثّق فرضيات بيئية غير مثبتة بالكود.
- أي claim معماري يجب أن يُربط بملف/مسار تنفيذي واضح.

---

## 6) أوامر التحقق السريع

```bash
ruff check .
mypy app/ microservices/
pytest
```

