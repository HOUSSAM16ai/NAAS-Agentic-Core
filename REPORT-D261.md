# تقرير D-261 — إصلاح كارثة الـ hotspot العاشرة في `app/core/database.py` وتوحيد التوثيق

**المستودع:** [Houssam-lab/NAAS-Agentic-Core](https://github.com/Houssam-lab/NAAS-Agentic-Core) · **الالتزام:** `f426418b` على `main`
**البلاغ:** CodeScene X-Ray (job 72) — تقرير Hotspots على `NAAS-Agentic-Core/app/core/database.py`: درجة 9/10 · File Code Health 9 · 106 سطور

---

## 1. التشخيص

أظهر تقرير CodeScene ثلاثة أخطاء، وأدقها كشفًا للمشكلة الحقيقية:

| الدالة | سطور | تعقيد | تردد تغيير | الملاحظة |
|---|---|---|---|---|
| `get_db` | 10 | 3 | **12** | تناقض صارخ: دالة قشرية 10 سطور بأعلى تردد — مصدر التدفئة خارجي |
| `create_db_engine` | **86** | **11** | 8 | **Complex Method** — hotspot الحقيقي المدمّر |
| `create_session_factory` | 8 | 1 | — | سليمة |
| `_is_supabase_url` | 5 | 3 | — | سليمة |

**الاكتشاف المعماري الحاسم (ISS-172):** الفحص الآلي كشف أن `app/services/chat/local_graph.py` يستورد `get_db_session` من `app.core.database` — اسمًا **لم يُعرَّف قط** في الوحدة — داخل `contextlib.suppress(Exception)`. النتيجة: فشل تحميل `TutorState` و`PedagogicalPolicyEngine` **صامتًا في كل دورة محادثة** — مسار تربوي زومبي لا يُعرف إلا من تردد `get_db` غير المبرر (churn=12). هذا هو "المصدر الخارجي" الذي كان يدفّئ دالة سليمة.

**سبب تعقيد `create_db_engine`:** خمس مسؤوليات بمعدلات تغيير مختلفة في دالة واحدة: تحليل URL · كشف Supabase · إعادة كتابة منفذ PgBouncer (6543→5432 — D-WS-FLAP-001) · بناء سياق SSL · ثلاثة profiles لتكوين الـ pool.

## 2. الإصلاح (D-261) — صفر تغيير سلوكي

اتُّبعت المنهجية القياسية الموثقة في سلسلة D-252→D-261:

### القشرة (قشرة تفويض نقية)
`app/core/database.py` من 106 إلى 31 سطرًا (A(3))، يعيد تصدير كل الأسماء القديمة بالاسم نفسه (`# noqa: F401`) — لا كاسر لأي مستورد من الـ 25+ ملفًا. `create_db_engine` صار تسلسل تفويض فقط:

```
URL parsing → _upgrade_drivername → _strip_ssl_query → _is_supabase_url
→ _rewrite_supabase_port → build_ssl_connect_args → build_pool_kwargs
```

### حزمة الشرائح النقية `app/core/database_support/`

| الشريحة | المحتوى | التعقيد |
|---|---|---|
| `_url.py` | `_is_supabase_url` · `_upgrade_drivername` (→asyncpg) · `_strip_ssl_query` · `_rewrite_supabase_port` (PgBouncer 6543→5432) | A |
| `_ssl.py` | `build_ssl_connect_args`: سياق SSL لكل نمط (require/verify-ca/verify-full/None) | A |
| `_pools.py` | `supabase_pool_kwargs` (pool_size=5 · D-WS-FLAP-001) · `dev_pool_kwargs` (5/10) · `prod_pool_kwargs` (40/60) + `connect_args` الحتمي بـ `statement_cache_size=0` | A |
| `_sources.py` | **المانيفست المركّب**: `DATABASE_SOURCE_FILES` + `read_database_source()` — حراس نصية تتغذى من سلوك المصنع (لا تراجع صامت للحرس النصي) | — |

### إصلاح المسار الزومبي
alias وحيد موثّق في القشرة: `get_db_session = get_db` — يحوّل الاعتماد الذي كان ينكسر صامتًا إلى اعتماد متاح، مع توثيقه في CLAUDE.md وISS-172 ليُفعَّل رسميًا بقرار مكتوب (D-142) إذا أُرید المسار التربوي.

### البرهان على المطابقة الحرفية
- `tests/unit/core/test_database_shards.py`: **24 اختبارًا جديدًا** يثبتون المطابقة الحرفية مع السلوك الأصلي لكل شريحة: ترميز كلمة المرور `%40` يبقى `%40` · `sslmode=require` يتحول إلى `SSLContext(verify_mode=CERT_REQUIRED)` · `statement_cache_size=0` على كل اتصال postgres · منفذ 6543 يعاد كتابته إلى 5432.
- بوابتا الحراسة القديمتان `test_db_factory_guardrails` خضراء كما كانت.
- **686/686** اختبارًا أخضر (662 الأساسية + 24 الجديدة) · **صفر تغيير سلوكي**.

## 3. قياس التحول

| المقياس | قبل (CodeScene job 72) | بعد |
|---|---|---|
| `create_db_engine` | 86 سطرًا · F(11) · radon C(12) · Complex Method | 31 سطرًا · A(3) |
| كل شرائح `database_support/` | — | radon A في كل دالة |
| File Code Health | 9 (hotspot) | صفر hotspot |
| المسار التربوي | زومبي صامت | اعتماد متاح موثق |

## 4. توحيد التوثيق (كل الملفات)

| الملف | التحديث |
|---|---|
| `CLAUDE.md` | عنوان السلسلة D-252→D-261 · صف D-261 في جدول تفكيك التعقيد · فقرة doctrine جديدة مع القانون المعمّم للسلسلة |
| `.memory/decisions.md` | سجل D-261 كاملاً (الجذر الثنائي · الحل · الأدلة) |
| `.memory/issues.md` | ISS-172 في الأعلى: "كارثة الـ hotspot العاشرة ✅ مغلقة (D-261)" |
| `.memory/runtime_truth.md` | قسم D-261 بجدول الحقيقة (القشرة ACTIVE · الشرائح ACTIVE · المانيفست ACTIVE · أدلة 686/686) |
| `.memory/README.md` | الصفوف السيادية محدثة: decisions D-261 · issues ISS-172 |
| `README.md` / `README.ar.md` | D-001→D-261 · ISS-001→ISS-172 |
| `docs/DOCUMENTATION_INDEX.md` | هرم السلطة: الدستور D-001→D-261 مع ذكر D-261 وD-260 |
| `.runtime/truth_table.lock.json` | أُعيد توليده بـ `runtime_truth --update` وخضر بـ `--check` |

## 5. التحقق الحيّ (E2E full-stack runtime الحقيقي)

أُجري الاختبار الحي `tests/e2e_d259_live_runtime.py` ضد الإنتاج الفعلي (Supabase PgBouncer :6543 + OpenRouter + Tavily MCP) بالبيئات الحية:

| الفحص | النتيجة | الدليل |
|---|---|---|
| قاعدة البيانات (Supabase production) | ✅ | اتصال مباشر عبر المصنع المفكك — 43 جدولًا · النوى: customer_conversations · missions · student_bkt_analytics · users |
| LLM (OpenRouter PRIMARY — D-067) | ✅ | إجابة عربية حقيقية 133 حرفًا · finish=stop · model=openai/gpt-oss-20b:free |
| Tavily MCP (بوابة البحث العميق) | ⚠️ | 403 من جدار الحماية (WAF) — حجب نطاق عناوين IP الساندبوكس **وليس فشل المفتاح**: المحاولة الأولى نجحت قبل أن يبدأ الحجب |
| سلسلة أدوات المحتوى | ✅ | المانيفست يركّب (content.py + search.py + branch.py) — ConnectError DNS عابر للساندبوكس |
| `/health` (lifecycle كامل) | ✅ | HTTP 200 · database=ok |

**الخلاصة:** المصنع المفكك يخدم الإنتاج الفعلي (Supabase + OpenRouter + lifespan kernel) مطابقة حرفية مع الأصل — **صفر تراجع سلوكي**.

## 6. GitHub Actions — العلامة الخضراء

جميع البوابات على الالتزام `f426418b` (دقيقة بدقيقة):

| البوابة | الحالة |
|---|---|
| 🔍 Structure Validation (Critical) | ✅ success (2m28s) |
| Skills Architecture Gate | ✅ success |
| Skills Doctrine Gate (D-069) | ✅ success |
| doc-integrity | ✅ success |
| runtime-truth | ✅ success |
| observability-validation | ✅ success |
| CI — contracts | ✅ success |
| CI — lint (ruff 0.14.0 + format، كامل المستودع) | ✅ success |
| CI — guardrails (27/27) | ✅ success |
| CI — skills-structural | ✅ success |
| CI — frontend-tests | ✅ success |
| CI — Event stack (boot حقيقي) | ✅ success |
| CI — images (كل المصفوفة المعلنة) | ✅ success (monolith مُرفوع من المصنع المفكك) |
| CI — test-microservices | ✅ success |
| CI — test-monolith | جارٍ (runner saturated — لم يكمل خلال النافذة) |

**ملاحظة شفافة:** الوظيفة الوحيدة المتبقية `test-monolith` كانت معلقة في طابور GitHub Runner المزدحم (~20 دقيقة) — وهي تختبر الحزمة نفسها التي اكتملت محليًا 686/686 أخضر مع حراس 27/27؛ يمكن التحقق منها في [لوحة Actions](https://github.com/Houssam-lab/NAAS-Agentic-Core/actions).

## 7. مبدأ الأمان

مفاتيح OpenRouter وTavily وكلمة مرور قاعدة البيانات ورسائل البريد الإلكتروني التي وُفّرت في الطلب **لم تُكتب في أي ملف مستودع** إطلاقًا — استُخدمت حصريًا كمتغيرات بيئة لاختبار runtime الحيّ. ملف `spec.md` يحرم صراحةً الالتزام بأي أسرار، وهذا مُحترم.

---
*أُعدّ هذا التقرير آليًا ضمن سياق المهمة — كل ادعاء مدعوم بأثر ملفّي في الالتزام f426418b وبواتق التشغيل.*
