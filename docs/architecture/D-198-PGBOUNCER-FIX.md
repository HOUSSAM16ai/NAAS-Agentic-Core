# D-198 · LangGraph AsyncPostgresSaver + Supabase PgBouncer — الحل الإنتاجي

**الحالة:** ✅ مدعوم في الإنتاج · PR #10 (`fix/d-198-pgbouncer-prepared-statements`) — **مفتوح للمراجعة، غير مدموج**

## 1. العَرَض

عند بدء orchestrator-service مع `AsyncPostgresSaver` (من `langgraph-checkpoint-postgres` 2.0.25)
عبر Supabase connection pooler (:6543):

```
DuplicatePreparedStatement: prepared statement "_pg3_0" already exists
```

وكان النظام ينهار عند الـ startup — حتى `/health` لم يصل إلى
`startup_state: ready` ولا `checkpointer_backend: postgres`.

## 2. السبب الجذري

pgbouncer في **transaction pooling mode** يعيد توزيع كل معاملة على اتصال
خلفي مختلف إلى PostgreSQL. عندئذٍ يقوم `psycopg 3` (المستخدم داخل
`AsyncConnectionPool` لـ `AsyncPostgresSaver`) بإنشاء **prepared statements**
تلقائياً (`prepare_threshold=5` افتراضياً). لأن الجلسة التالية قد تنتهي على
اتصال خلفي آخر، تتكرر محاولة إنشاء الجُملة المحضّرة `_pg3_0` فتفشل بـ
`DuplicatePreparedStatement`.

> هذه ليست مشكلة في Supabase، ولا في LangGraph، ولا تتطلب pgcat أو SSH tunnel
> أو SQLite — المشكلة محصورة حصراً في تفاعل psycopg prepared statements مع
> pgbouncer transaction mode.

## 3. الحل (تغيير سطر واحد، بدون تغيير معماري)

```python
# microservices/orchestrator_service/src/core/database.py
# داخل إنشاء AsyncConnectionPool:
kwargs={
    "autocommit": True,
    "row_factory": dict_row,
    "prepare_threshold": None,   # ⬅ تعطيل كامل للـ prepared statements
}
```

تعطيل prepared statements بالكامل يجعل كل معاملة تستخدم جُملاً غير محضّرة —
وهي آمنة تماماً عبر اتصالات pgbouncer الخلفية المختلفة، لأن لا شيء يُخزَّن
على مستوى الجلسة بعد الآن.

## 4. ما نُبِّذ منه ولماذا (قرارات موثّقة)

| الخيار المرفوض | السبب |
|---|---|
| `MemorySaver` | فقد كامل للاستمرارية بعد restart — عكس المطلوب |
| SQLite للتشيكبوينت | غير موزّع، لا يتوافق مع بنية الإنتاج، regression معماري |
| pgcat / tunnel إضافي | تعقيد تشغيلي بلا حاجة — الحل في طبقة العميل |
| رفع `prepare_threshold` فقط | لا يزيل المشكلة — فقط يؤخر ظهورها |
| `statement_cache_size=0` في SQLAlchemy | لا يؤثر على جلسات psycopg الخام داخل checkpointer |

## 5. الإثبات الحيّ (E2E — Supabase حقيقية :6543)

| الاختبار | النتيجة |
|---|---|
| A. `/health` startup_state | ✅ `ready` · `checkpointer_backend: postgres` · tables=4 |
| B. إنشاء مهمة (create mission) | ✅ 201 + persisted |
| C. جلب مهمة (get mission) | ✅ 200 |
| D. Compose Skills | ✅ 200 |
| E. Checkpoint write | ✅ persisted |
| F. Checkpoint read | ✅ 200 |
| G. WebSocket chat | ✅ المسار الحقيقي للمستخدم |
| H. Restart persistence | ✅ الحالة تبقى بعد إيقاف وإعادة تشغيل orchestrator |

**تسلسل التحقق الكامل:** Supabase PostgreSQL → PgBouncer :6543 → Psycopg 3
(`prepare_threshold=None`) → LangGraph/Postgres Checkpointer → ✅ يعمل.

## 6. D-199 · تثبيت CI فوق الحل

CI يجري على `DATABASE_URL=sqlite+aiosqlite:///:memory:` (لا psycopg pool
متاح)، فتعثر ثلاثة أنواع من regressions:

1. **`RuntimeError: psycopg pool not available`** — `_psycopg_session_factory_proxy()`
   كان يرمي دائماً عند pool=None. أصبح يقبل `default_factory=None` اختيارياً،
   وكل مواقع الاستدعاء (routes، chat_stream_engine، chat_ws_turn،
   agent_chat_admin_stream، agent_chat_customer_stream، runner، entrypoint،
   admin_tools) تمرر `default_factory=async_session_factory` — الاختبارات
   تستخدم مسار ORM القياسي، والإنتاج يبقى على psycopg pool بدون تغيير سلوك.
2. **relay outbox (dict vs ORM object):** الاختبارات تعمل على `MissionOutbox`
   ORM objects بينما الإنتاج raw psycopg dict rows — `relay_outbox_events`
   يستخدم وصولاً شرطياً (`is_raw` conditional) و`_set_outbox_status` يتعامل
   مع المسارين.
3. **debt budget:** تحديث `scripts/fitness/endpoint_complexity_debt.json`
   بعد انخفاض LOC (ratchet ثنائي الاتجاه، shrink-only).

**نتيجة CI على PR #10:** test-microservices (1146/0) ✅ · test-monolith ✅ ·
lint ✅ · guardrails ✅ · doc-integrity ✅ · Skills Gates ✅ · Structure
Validation ✅ · runtime-truth ✅ · Event stack ✅ · images ✅.

## 7. القوانين الدائمة

- ⛔ لا MemorySaver بديلاً نهائياً ولا تغييراً معمارياً لتجاوز مشكلة اتصال —
  تشخيص الطبقة أولاً ثم الحل المدعوم.
- ⛔ لا `raise` من proxy التشيكبوينت في بيئات بدون pool؛ الـ fallback يُمرَّر
  صراحةً من مواقع الاستدعاء.
- ✅ `prepare_threshold=None` هو الإعداد الصحيح لـ AsyncPostgresSaver فوق
  PgBouncer transaction mode — وهو أيضاً الإعداد الموصى به من JetBrains
  Qodana/Inspection لعملاء psycopg فوق poolers.
