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

## القياسات الأربعة — أوامرُ تُنفَّذ لا خطواتٌ تُقرأ

> ⚠️ **صفِّر الدرع قبل كل قياس.** الدرع يتذكّر إخفاقات الجلسة، فقياسٌ يتبع قياساً
> يبدأ من عدّادٍ غير صفري ويعطي نتيجةً لا تعني ما تظنّه. أعد إقلاع الخادم أو
> استعمل حساباً جديداً في كل قياس. رصدت مراجعة CodeRabbit أنّ النسخة الأولى من
> هذا الملفّ أعطت **نتائج متوقَّعة بلا أوامر** — وإجراءٌ لا يُنفَّذ ليس إجراءً.

```bash
API=http://127.0.0.1:8000
NEW=$(date +%s)                      # لاحقة تجعل كل تشغيل مستقلاً
PW='Pw-verify-Aa1!'

# ── 1) عقد الأخطاء: الجسم الخام لا رمز الحالة ────────────────────────────────
curl -s -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
  -d '{"email":"ghost-'"$NEW"'@example.com","password":"wrong"}' \
| python3 -c 'import json,sys; b=json.load(sys.stdin); print(sorted(b)); \
print("detail==message:", b.get("detail")==b.get("message")); \
print("error_code:", b.get("error_code"), "| request_id:", bool(b.get("request_id")))'
# متوقَّع: المفاتيح السبعة · detail==message: True · error_code: unauthorized
# قبل الإصلاح: ['data','message','status','timestamp'] — بلا `detail` إطلاقاً.

# ── 2) القفل لا يعاقب البريء ────────────────────────────────────────────────
curl -s -X POST "$API/api/security/register" -H 'Content-Type: application/json' \
  -d '{"full_name":"Victim","email":"victim-'"$NEW"'@example.com","password":"'"$PW"'"}' >/dev/null
for i in $(seq 1 25); do                    # غرباء، كلٌّ ببريد مختلف
  curl -s -o /dev/null -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
    -d '{"email":"stranger-'"$NEW"'-'"$i"'@example.com","password":"wrong"}'
done
curl -s -o /dev/null -w 'الضحيّة بكلمة سرّها الصحيحة: %{http_code}\n' \
  -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
  -d '{"email":"victim-'"$NEW"'@example.com","password":"'"$PW"'"}'
# متوقَّع: 200 — قبل الإصلاح: 429.

# ── 3) الرمز يقول نوعه ──────────────────────────────────────────────────────
TOKEN=$(curl -s -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
  -d '{"email":"victim-'"$NEW"'@example.com","password":"'"$PW"'"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
python3 -c 'import base64,json,sys
s=sys.argv[1].split(".")[1]; s+="="*(-len(s)%4)
c=json.loads(base64.urlsafe_b64decode(s))
print({k:c.get(k) for k in ("type","jti","iat","roles","permissions")})' "$TOKEN"
# متوقَّع: type=access · jti و iat موجودان.

REAUTH=$(curl -s -X POST "$API/api/v1/auth/reauth" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"password":"'"$PW"'"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["reauth_token"])')
curl -s -o /dev/null -w 'رمز reauth كرمز وصول: %{http_code}\n' \
  "$API/api/v1/users/me" -H "Authorization: Bearer $REAUTH"
# متوقَّع: 401 — قبل الإصلاح كان يُقبَل (التوقيع ليس تفويضاً).

# ── 4) تدوير رمز التحديث وكشف السرقة ────────────────────────────────────────
REFRESH=$(curl -s -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
  -d '{"email":"victim-'"$NEW"'@example.com","password":"'"$PW"'"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["refresh_token"])')
curl -s -o /dev/null -w 'تدوير أوّل: %{http_code}\n' -X POST "$API/api/v1/auth/refresh" \
  -H 'Content-Type: application/json' -d '{"refresh_token":"'"$REFRESH"'"}'
curl -s -o /dev/null -w 'إعادة استعمال الرمز نفسه: %{http_code}\n' -X POST "$API/api/v1/auth/refresh" \
  -H 'Content-Type: application/json' -d '{"refresh_token":"'"$REFRESH"'"}'
# متوقَّع: 200 ثمّ 401 — إعادة الاستعمال تُبطل العائلة كلّها (كشف السرقة).
```

## التشغيل الآلي

⚠️ **بالمفسّر المُهيَّأ أعلاه، لا بـ`python` المسار.** المستودع يستعمل PEP 695،
و`python` العام قد يكون 3.11 فيفشل الجمع بـ`SyntaxError` في `tests/conftest.py` —
وهو فشلٌ يبدو عطباً في الاختبارات وهو عطبٌ في البيئة (رصدته مراجعة CodeRabbit).

```bash
export PY=/tmp/venv312/bin/python

# ٢١ عقد انحدار (تفشل على الكود القديم — شرط الإغلاق)
$PY -m pytest tests/security/test_login_failed_regression.py -q

# البوّابة التي تمنع عودة الصنف
$PY scripts/fitness/check_error_contract_parity.py

# عقود الواجهة (Node، لا بايثون)
node frontend/tests/iss152_api_error_contract.test.mjs
node frontend/tests/d236_session_refresh.test.mjs
```

**تجربتان سلبيتان على البوّابة نفسها** (بوّابةٌ لا تفشل ليست بوّابة): احذف `detail`
من `build_error_payload` ⇒ أحمر · أعد `setError('Login failed')` إلى أي عميل ⇒ أحمر.
