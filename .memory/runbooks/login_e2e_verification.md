# كيف يُعاد إنتاج عطب «Login failed» والتحقّق من إصلاحه

> **إجراء لا حالة.** الأرقام المقيسة في `.memory/auth_runtime_truth.md`، والقرار
> D-236، والبلاغ ISS-152.

## لماذا محلّياً وليس على Supabase مباشرةً

منفذا Postgres (**6543** · **5432**) محجوبان من بيئة التطوير — مُثبَتٌ بمهلة اتصال،
وهو نفس حجب Codespaces الموصوف في `CLAUDE.md`. فـ`asyncpg` لا يستطيع فتح اتصال سلكي
بـSupabase من هنا. الحلّ **مسارٌ مزدوج**: قاعدة الإنتاج تُستجوَب عبر HTTPS (Supabase
MCP) للمخطّط والصفوف والتجزئات، والتطبيق يعمل فوق مرآة PostgreSQL محلّية.

⛔ **لا يُدَّعى أن التطبيق اتصل بـSupabase مباشرةً** (§0).

## التهيئة

```bash
# 1) مفسّر 3.12 — المستودع يستعمل PEP 695 (`type X = ...`) فيرفض 3.11
uv venv --python 3.12 /tmp/venv312
uv pip install --python /tmp/venv312/bin/python -r requirements.txt

# 2) قاعدة محلّية
service postgresql start
su postgres -c "psql -tAc \"CREATE ROLE cogniforge LOGIN PASSWORD '<local>';\""
su postgres -c "psql -tAc \"CREATE DATABASE cogniforge OWNER cogniforge;\""

# 3) البيئة (خارج المستودع — لا تُلتزَم أبداً)
export DATABASE_URL="postgresql+asyncpg://cogniforge:<local>@127.0.0.1:5432/cogniforge"
export SECRET_KEY="<32+ chars>"  ENVIRONMENT=development
export ADMIN_EMAIL="<admin>"     ADMIN_PASSWORD="<pass>"

# 4) الإقلاع — المخطّط يُنشَأ تلقائياً عند الإقلاع (app/kernel.py)
/tmp/venv312/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

⚠️ `pgvector` غير مثبَّت محلّياً، فثلاثة جداول بحثية تفشل في الإنشاء وتُسجَّل. **لا
تمسّ مسار المصادقة** — و`/health` يُرجع `database: ok`.

## القياسات الأربعة

1. **عقد الأخطاء.** `POST /api/security/login` بكلمة سرّ خاطئة، ثمّ **افحص الجسم
   الخام**: يجب أن يحمل `detail` و`message` بنفس القيمة و`error_code` و`request_id`.
   ⛔ لا تكتفِ برمز الحالة — العطب كان في **شكل الجسم** لا في الرمز.
2. **القفل لا يعاقب البريء.** أرسل ≥20 محاولة فاشلة بعناوين بريد **مختلفة وغير
   موجودة**، ثمّ سجّل دخولاً **صحيحاً** لمستخدم آخر ⇒ يجب أن يكون **200**.
   (قبل الإصلاح: **429**.)
3. **الرمز يقول نوعه.** فكّ حمولة رمز الوصول: `type='access'` · `jti` · `iat` ·
   `roles` · `permissions`. واطلب `reauth_token` ثمّ استعمله على `/api/v1/users/me`
   ⇒ يجب **401**.
4. **تدوير رمز التحديث.** `POST /api/v1/auth/refresh` بالرمز ⇒ 200؛ ثمّ **أعد
   استعماله** ⇒ يجب **401** (كشف السرقة يُبطل العائلة).

## التشغيل الآلي

```bash
# ٢١ عقد انحدار (تفشل على الكود القديم — شرط الإغلاق)
pytest tests/security/test_login_failed_regression.py -q

# البوّابة التي تمنع عودة الصنف
python scripts/fitness/check_error_contract_parity.py
```

**تجربتان سلبيتان على البوّابة نفسها** (بوّابةٌ لا تفشل ليست بوّابة): احذف `detail`
من `build_error_payload` ⇒ أحمر · أعد `setError('Login failed')` إلى أي عميل ⇒ أحمر.
