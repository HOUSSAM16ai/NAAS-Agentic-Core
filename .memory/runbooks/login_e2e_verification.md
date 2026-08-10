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

> ⚠️ **كل قياسٍ يبدأ من حالةٍ نظيفة، والفشلُ يُوقِف الإجراء.** رصدت مراجعة
> CodeRabbit عطبين متتاليين هنا: النسخة الأولى أعطت **نتائج متوقَّعة بلا أوامر**
> (إجراءٌ لا يُنفَّذ ليس إجراءً)، والثانية أعطت أوامرَ **تطبع ولا تؤكّد** — فكان
> خادمٌ معطوب يُنتِج تشغيلاً يبدو مكتملاً. الآن: `set -euo pipefail`، وتأكيدٌ
> صريح لكل حالة ومفتاح ومطالبة، وحسابٌ جديد لكل سيناريو (`fresh`) فلا يرث
> قياسٌ عدّادات ما قبله.

```bash
set -euo pipefail
API=http://127.0.0.1:8000
PW='Pw-verify-Aa1!'

# ⚠️ **كل قياسٍ بحسابٍ جديد.** الدرع يقفل على الهوية، فحسابٌ جديد لكل سيناريو
# يعني عدّاداً صفرياً بالبناء — بلا إعادة إقلاع وبلا مسٍّ لحالةٍ داخلية.
# (متّجه العنوان مشترك، وسقفه 200، والسيناريوهات أدناه لا تقترب منه.)
fresh() { echo "$1-$(date +%s%N)@example.com"; }
expect() { # expect <المتوقَّع> <الفعلي> <الوصف>
  [ "$1" = "$2" ] || { echo "❌ $3: متوقَّع=$1 فعلي=$2" >&2; exit 1; }
  echo "✅ $3 ($2)"
}
register() { curl -sS -o /dev/null -X POST "$API/api/security/register" \
  -H 'Content-Type: application/json' \
  -d "{\"full_name\":\"V\",\"email\":\"$1\",\"password\":\"$PW\"}"; }
login() { curl -sS -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$1\",\"password\":\"$2\"}"; }
code() { curl -sS -o /dev/null -w '%{http_code}' "$@"; }

# ── 1) عقد الأخطاء: الجسم الخام لا رمز الحالة ────────────────────────────────
GHOST=$(fresh ghost)
login "$GHOST" wrong | python3 -c '
import json,sys
b=json.load(sys.stdin)
need={"status","detail","message","error_code","data","request_id","timestamp"}
missing=need-set(b)
assert not missing, f"مفاتيح ناقصة: {sorted(missing)}"
assert b["detail"]==b["message"], "detail != message"
assert b["error_code"]=="unauthorized", b["error_code"]
assert b["request_id"], "request_id فارغ"
print("✅ عقد الأخطاء: المفاتيح السبعة · detail==message · unauthorized")'
# قبل الإصلاح: ['data','message','status','timestamp'] — بلا `detail` إطلاقاً.

# ── 2) القفل لا يعاقب البريء ────────────────────────────────────────────────
VICTIM=$(fresh victim); register "$VICTIM"
for i in $(seq 1 25); do login "$(fresh stranger)" wrong >/dev/null; done
expect 200 "$(code -X POST "$API/api/security/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$VICTIM\",\"password\":\"$PW\"}")" "الضحيّة بكلمة سرّها الصحيحة"
# قبل الإصلاح: 429.

# ── 3) الرمز يقول نوعه ──────────────────────────────────────────────────────
CLAIMS=$(fresh claims); register "$CLAIMS"
TOKEN=$(login "$CLAIMS" "$PW" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
python3 -c '
import base64,json,sys
s=sys.argv[1].split(".")[1]; s+="="*(-len(s)%4)
c=json.loads(base64.urlsafe_b64decode(s))
assert c.get("type")=="access", c.get("type")
assert c.get("jti") and c.get("iat"), "jti/iat مفقودان"
print("✅ المطالبات: type=access · jti · iat")' "$TOKEN"

REAUTH=$(curl -sS -X POST "$API/api/v1/auth/reauth" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d "{\"password\":\"$PW\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["reauth_token"])')
expect 401 "$(code "$API/api/v1/users/me" -H "Authorization: Bearer $REAUTH")" \
  "رمز reauth مرفوضٌ كرمز وصول"
# قبل الإصلاح كان يُقبَل — التوقيع ليس تفويضاً.

# ── 4) التدوير يُبدِل الرمز، وإعادةُ الاستعمال تُبطِل العائلة ────────────────
ROT=$(fresh rot); register "$ROT"
R1=$(login "$ROT" "$PW" | python3 -c 'import json,sys; print(json.load(sys.stdin)["refresh_token"])')
R2=$(curl -sS -X POST "$API/api/v1/auth/refresh" -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$R1\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["refresh_token"])')
[ -n "$R2" ] && [ "$R1" != "$R2" ] \
  || { echo "❌ التدوير لم يُصدر رمزاً بديلاً مختلفاً" >&2; exit 1; }
echo "✅ التدوير أصدر رمزاً بديلاً مختلفاً"

# إعادةُ استعمال الرمز **المُستهلَك** = كشف سرقة.
expect 401 "$(code -X POST "$API/api/v1/auth/refresh" -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$R1\"}")" "إعادة استعمال الرمز القديم مرفوضة"

# ⛔ والأهمّ: البديل نفسه يسقط معه — العائلة كلّها أُبطلت، لا الرمز وحده.
expect 401 "$(code -X POST "$API/api/v1/auth/refresh" -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"$R2\"}")" "البديل أُبطل أيضاً (إبطال العائلة)"
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
