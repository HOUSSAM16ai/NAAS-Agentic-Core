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

## 2) تشريح WebSocket Streaming (الحالة التشغيلية الحالية)

### A. نقاط الدخول المعتمدة للدردشة اللحظية
1. **المسار الحديث (Modern Entry Point):**
   - `microservices/api_gateway/main.py` عبر:
     - `/api/chat/ws`
     - `/admin/api/chat/ws`
   - البوابة تنفّذ:
     - تحديد identity للجلسة (`route_id + upstream_path + session scope`) لأغراض stickiness.
     - تمرير الاتصال إلى `websocket_proxy` داخل `microservices/api_gateway/websockets.py`.
2. **المسار التوافقي (Compatibility Facade):**
   - مسارات WebSocket داخل `app/api/routers/customer_chat.py` و`app/api/routers/admin.py` ما تزال موجودة كصمام توافق/rollback في بعض السيناريوهات.

### B. خط الأنابيب الفعلي للـ streaming
```text
Client
  -> API Gateway WS Route (/api/chat/ws | /admin/api/chat/ws)
    -> Target resolution (_resolve_chat_ws_target)
      -> websocket_proxy (bidirectional relay)
        -> Upstream chat engine (orchestrator/conversation بحسب التوجيه)
          -> event normalization contract
            -> Client render loop
```

### C. المخاطر البنيوية في WebSocket Streaming
- **Split-Brain ownership:** وجود مسار حديث في البوابة + مسارات توافقية بالمونوليث يخلق ازدواجية قرار التوجيه.
- **Contract Drift:** اختلاف envelope بين بعض المنتجين (`delta` مقابل `assistant_delta` تاريخيًا) يسبب أخطاء parsing صامتة.
- **Session Affinity Fragility:** أي تعديل في خوارزمية routing identity قد يزعزع ثبات تموضع الجلسات أثناء reconnect.

### D. الحواجز التشغيلية المطلوبة (Guardrails)
- البوابة هي **نقطة الدخول الوحيدة** للإنتاج متى ما اكتمل purge.
- كل حدث stream يجب أن يمر بعقد موحّد قبل العميل.
- أي rollback يجب أن يكون عبر feature flags ونافذة زمنية مضبوطة، لا عبر bypass عشوائي.

---

## 3) حالة Monolith vs Microservices (2026-05-05)

### A. الواقع الحالي
- المنظومة **ليست monolith خالصًا** وليست **microservices pure** بالكامل.
- الحالة الصحيحة: **Hybrid Transitional Architecture**:
  - `app/` ما يزال يملك وظائف تكامل وتوافق تاريخي.
  - `microservices/` يملك مسارات تنفيذ حديثة مستقلة لعدة قدرات.

### B. أين ما زال المونوليث حاضرًا؟
- في بعض واجهات الدردشة/التوافق ومسارات orchestration التاريخية.
- في طبقة composition العامة (Reality Kernel) التي ما تزال تدير جزءًا من control-plane.

### C. أين أصبحت microservices ناضجة؟
- وجود `api_gateway` كنقطة edge routing مستقلة.
- وجود خدمات domain مخصصة (user/observability/reasoning/research...) بحدود نشر وتشغيل مستقلة.

### D. التقييم التنفيذي المختصر
- **Target State:** API-First Microservices بنسبة تشغيلية كاملة.
- **Current State:** Hybrid with controlled strangler pattern.
- **Gap:** إزالة آخر facades التوافقية للمحادثة وتثبيت ownership أحادي لمسار WS + عقود events موحّدة.

---

## 4) خريطة التنفيذ (Execution Topology)

```text
Client/UI
  -> FastAPI Kernel (app/main.py -> app/kernel.py)
    -> Router Registry (app/api/routers/registry.py)
      -> Local service/domain execution (app/services + app/core)
      -> Remote delegation (app/infrastructure/clients/*)
         -> microservices/<service>/...
```

---

## 5) مناطق المسؤولية (Boundaries)

1. `app/*` = بوابة التركيب والتنسيق العام (Control Plane).
2. `microservices/*` = وحدات أعمال مستقلة (Execution Plane).
3. `docs/architecture/*` = الدستور المعماري وقرارات التصميم.
4. `.memory/*` = ذاكرة تشغيلية مختصرة يجب أن تعكس الواقع التنفيذي الفعلي.

---

## 6) قواعد تشغيلية إلزامية عند التعديل

- قبل أي تعديل معماري: راجع `docs/architecture/MICROSERVICES_CONSTITUTION.md`.
- أي تغيير في طوبولوجيا النظام يستلزم تحديثًا متزامنًا لـ:
  1) `CLAUDE.md`
  2) `.memory/architecture.md`
  3) `.memory/decisions.md`
  4) `.memory/context.md`
- لا توثّق فرضيات بيئية غير مثبتة بالكود.
- أي claim معماري يجب أن يُربط بملف/مسار تنفيذي واضح.

---

## 7) أوامر التحقق السريع

```bash
ruff check .
mypy app/ microservices/
pytest
```

---
