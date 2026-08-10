# حقيقة المصادقة التشغيلية — الحالة بدليل

> **الحالة لا القانون.** القانون في
> [`docs/architecture/AUTHENTICATION_DOCTRINE.md`](../docs/architecture/AUTHENTICATION_DOCTRINE.md)
> والقرار في `.memory/decisions.md` **D-236** والبلاغ في `.memory/issues.md` **ISS-152**.
> كل صفٍّ يحمل **دليلاً ملفّياً يجب أن يوجد** وتاريخَ تحقّق (D-188: رقمٌ بلا تشغيلٍ
> يُنسَب إليه يتقادم ثمّ يكذب).
>
> **آخر تحقّق حيّ: 2026-08-10** — FastAPI حقيقي على `:8000` (Python 3.12 · uvicorn)
> فوق PostgreSQL 16.13 محلّي، بحسابَي الإنتاج الحقيقيَّين.
>
> **الإسناد (provenance).** كل رقمٍ هنا مربوطٌ بما أنتجه، لا بتاريخٍ وحده — رصدت
> مراجعة CodeRabbit أنّ التاريخ وحده لا يُعيد إنتاج شيء:
>
> | المصدر | ما يُنسَب إليه | كيف يُعاد |
> |--------|----------------|-----------|
> | فرع `claude/login-failed-fix-trc2aw` · قاعدة الـPR `543163a` | كل صفوف §4 (حالة القدرات) | البرهان الملفّي في العمود الثالث |
> | Supabase `aocnuqhxrhxgbfcgbxfy` عبر MCP على HTTPS (2026-08-10) | كل صفوف §3 (صفوف الإنتاج) | استعلام `SELECT count(*)` على نفس الجداول |
> | خادم محلّي · `.memory/runbooks/login_e2e_verification.md` | القياسات الأربعة | الأوامر في الـrunbook حرفياً |
> | تشغيل Qodana على `d8fae16` (تقرير `nRL7al`) | أرقام `.memory/code_quality_truth.md §0` | تنزيل أثر `qodana-report` وفرز SARIF |

---

## 1) القيد الشبكي — يُقال صراحةً

منفذا Postgres إلى Supabase (**6543** و**5432**) **محجوبان** من بيئة التطوير هذه —
مُثبَتٌ بمهلة اتصال، وهو نفس الحجب الموصوف في `CLAUDE.md` لـCodespaces. فلا يستطيع
`asyncpg` فتح اتصال سلكي بـSupabase من هنا.

**لذلك جرى التحقّق على مسارين، وكلاهما على بيانات الإنتاج الحقيقية:**

| المسار | ما تحقّق منه | كيف |
|--------|--------------|-----|
| **Supabase الحقيقية عبر HTTPS** (MCP) | المخطّط · صفوف المستخدمين · تجزئات كلمات السرّ · سجلّ التدقيق | استعلامات SQL حقيقية على `aocnuqhxrhxgbfcgbxfy` |
| **مرآة محلّية** (PostgreSQL 16.13) | سلوك HTTP الحيّ: الدخول · الرفض · القفل · الرموز | uvicorn حقيقي + `httpx` حقيقي |

⛔ **لم يتّصل التطبيق بـSupabase مباشرةً، ولا يُدَّعى ذلك** (§0: ما لا يحدث لا يُكتب
أنه حدث).

---

## 2) ما قِيس على قاعدة الإنتاج الحيّة (2026-08-10)

| القياس | القيمة | الدلالة |
|--------|--------|---------|
| `users` | 24 | — |
| `refresh_tokens` | 135 · **8 مستخدمين · 135 عائلة** · آخرها **2026-05-28** | `families = tokens` ⇒ **صفر تدوير**: كل دخول يفتح عائلة جديدة ولا أحد ينادي `/auth/refresh` — لأن الواجهة لم تكن تتسلّم رمز تحديث أصلاً |
| `audit_log` (مفرد) | **1170 صفّاً** | سجلّ التدقيق **يعمل** |
| `audit_logs` (جمع) | **0 صفّاً · بلا كاتبٍ وُجد** | ⚠️ جدولٌ يتيم بالأرجحية لا باليقين: الصفر مقيس، و«بلا كاتب» **استنتاجٌ من بحثٍ نصّي** عن الاسم في `app/` و`microservices/` و`shared/` — وهو لا يُغطّي SQL مُركَّباً في وقت التشغيل ولا كاتباً خارج المستودع. رصدت مراجعة CodeRabbit أن «صفر صفوف» لا يُثبت «لا كاتب» (D-189: الوجود ليس صحّة، وعكسُه كذلك). يبقى مفتوحاً ولم يُحذَف في هذا الـPR |
| `AUTH_SUCCEEDED` | 131 · آخرها **2026-05-28** | مسار UMS لم يُستعمَل منذ ذلك التاريخ |
| `ADMIN_BOOTSTRAPPED` | **1043** · آخرها **2026-08-09** · منها **1022 `noop`** | التطبيق أقلع ألف مرّة، وكلمة سرّ الإداري **مستقرّة** (`noop` = التجزئة تطابق الإعداد) |

**تصحيحٌ مُسجَّل:** ادّعيتُ أوّلاً أن «سجلّ التدقيق لم يكتب شيئاً قطّ» بناءً على
استعلام `audit_logs` (الجمع). كان الاستعلام على **الجدول الخطأ**؛ الـORM يكتب في
`audit_log` (المفرد، `app/core/domain/audit.py:26`) وفيه 1170 صفّاً. النتيجة السلبية
تُسجَّل ولا تُمحى (D-228).

**فرضيةٌ مُفنَّدة:** خمّنتُ أن `bootstrap_admin_account` يُعيد ضبط كلمة سرّ الإداري في
كل إقلاع فيكسر دخوله. **خطأ** — 1022 من 1043 إقلاعاً سجّلت `["noop"]`، أي أن التجزئة
كانت مطابقة. الجذر كان في مكانٍ آخر تماماً.

---

## 3) العطب كما قِيس حيّاً **قبل** الإصلاح

```text
POST /api/security/login  (كلمة سرّ خاطئة) -> 401
RAW BODY: {"status":"error","message":"Invalid email or password","data":null,
           "timestamp":"2024-01-01T00:00:00Z"}
TOP-LEVEL KEYS: ['data', 'message', 'status', 'timestamp']
HAS 'detail' KEY: False
==> FRONTEND WOULD DISPLAY: 'Login failed'

CLAIMS: ['email', 'exp', 'is_admin', 'role', 'sub']
   jti: False · iat: False · type: False        الصلاحية: 24 ساعة · refresh_token: ABSENT

19 محاولة فاشلة بعناوين بريد **مختلفة وغير موجودة**:
   [401 ×19, 429, 429]
ثمّ الضحيّة بكلمة سرّها **الصحيحة**  -> 429
==> FRONTEND SHOWS: 'Login failed'
```

**وتحقّقٌ حاسم:** كلمة السرّ التي يستعملها المالك تُطابق تجزئتَي الإنتاج
(`argon2id`) بـ`verify → True` للحسابَين. **فالعطب لم يكن في بيانات الاعتماد قطّ.**

---

## 4) الحالة بعد الإصلاح (نفس السيناريو، نفس الخادم)

```text
POST /api/security/login  (كلمة سرّ خاطئة) -> 401
TOP-LEVEL KEYS: ['data','detail','error_code','message','request_id','status','timestamp']
HAS 'detail' KEY: True
==> FRONTEND WOULD DISPLAY: 'Invalid email or password'  →  بالعربية عبر error_code

CLAIMS: ['exp','iat','is_admin','jti','permissions','roles','sub','type']
   jti: True · iat: True · type: 'access'       refresh_token: PRESENT

21 محاولة فاشلة بعناوين بريد مختلفة: [401 ×21]
ثمّ الضحيّة بكلمة سرّها الصحيحة  -> 200 ✅
```

| المكوّن | الحالة | الدليل الملفّي |
|---------|--------|----------------|
| عقد الأخطاء الموحَّد | **ACTIVE** | `app/middleware/fastapi_error_handlers.py` (`build_error_payload`) |
| هوية العميل (وسيط موثوق) | **ACTIVE** | `app/security/client_identity.py` |
| الدرع: قفلٌ على الهوية | **ACTIVE** | `app/security/chrono_shield.py` |
| بابٌ واحد فوق `AuthService` | **ACTIVE** | `app/services/boundaries/auth_boundary_service.py` |
| نوع الرمز مفروض | **ACTIVE** | `app/services/auth/crypto.py` (`verify_jwt(expected_type=…)`) |
| رمز التحديث يصل الواجهة | **ACTIVE** | `app/api/schemas/security.py` (`AuthResponse.refresh_token`) |
| تدوير الرمز في الواجهة | **ACTIVE** | `frontend/app/utils/sessionRefresh.js` + مُجدوِلٌ في `CogniForgeApp.jsx` يستهلك `/api/v1/auth/refresh` · **43 عقداً** في `frontend/tests/d236_session_refresh.test.mjs` (مُثبَتٌ **أحمر** على `762bf52`: 3 إخفاقات) |
| `iss`/`aud` | **ABSENT (مُعلَن)** | نتيجة سلبية مُسجَّلة — العقيدة §1.هـ.22 |
| `audit_logs` (الجمع) اليتيم | **UNKNOWN** | صفرُ صفوفٍ **مقيس**، وغيابُ الكاتب **غير مُثبَت** (بحثٌ نصّي لا يُغطّي SQL المُركَّب وقت التشغيل) — و«UNKNOWN» أصدق من «ZOMBIE» هنا (§6.6: دليلٌ غير كافٍ). لم يُحذَف في هذا الـPR |

---

## 5) فوارضها الآلية

| الفارض | ما يمنعه |
|--------|----------|
| `scripts/fitness/check_error_contract_parity.py` | عقدٌ يُعلنه طرفٌ ولا يقرؤه الآخر · إنجليزيةٌ تصل الطالب |
| `tests/security/test_login_failed_regression.py` | ٢١ عقداً — **مُثبَتةٌ حمراء على الكود القديم** (9 فشل + 12 خطأ) |
| `tests/security/test_hyper_defense.py` | مضادّ التدوير (هو ما أسقط أوّل صياغة للإصلاح حين حذفت متّجه العنوان) |
| `frontend/tests/d236_session_refresh.test.mjs` | رمزُ تحديثٍ يُهمَل مرّةً أخرى · و**تعميمُ الفشل**: أنّ 5xx أو انقطاعَ شبكةٍ يطرد الطالب (يُفحَص على ٩ حالات) |

**تجربتان سلبيتان مُثبَتتان على البوّابة نفسها:** حذف `detail` من المعالج ⇒ أحمر ·
إعادة `'Login failed'` إلى عميل ⇒ أحمر · واستعادة ⇒ أخضر.
