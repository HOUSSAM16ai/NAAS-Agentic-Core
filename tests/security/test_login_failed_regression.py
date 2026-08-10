"""عقود انحدار «Login failed» (D-236 · ISS-152).

الطالب كان يرى **`Login failed`** — سلسلة إنجليزية حرفية على منصّة عربية، تُخفي
السبب الحقيقي أيّاً كان (401 · 429 · 422 · 500). أُعيد إنتاج العطب حيّاً على خادم
حقيقي **قبل** أي إصلاح، وكل اختبار هنا يقفل واحداً من الأعطاب المقيسة:

```text
POST /api/security/login (كلمة سرّ خاطئة) -> 401
TOP-LEVEL KEYS: ['data', 'message', 'status', 'timestamp']
HAS 'detail' KEY: False                    ← العقد المكسور
==> FRONTEND WOULD DISPLAY: 'Login failed'

19 محاولة فاشلة بعناوين بريد **مختلفة** ⇒ المحاولة 20 = 429
ثمّ الضحيّة بكلمة سرّها **الصحيحة**       ⇒ 429   ← القفل العالمي
```

⛔ هذه الاختبارات تفشل على الكود القديم — وهو شرط إغلاق البلاغ (D-186 §6).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import ClassVar

import pytest
from fastapi import HTTPException
from httpx import AsyncClient

from app.security.chrono_shield import chrono_shield
from app.services.auth.crypto import ACCESS_TOKEN_TYPE

pytestmark = pytest.mark.security


#: كلمة مرور خاطئة عمداً. مُعرَّفة مرّةً واحدة لا مكرّرة في كل استدعاء:
#: التكرار يُنتج «شيفرة مُضاعفة» ويجعل المحلّلات تقرؤها سرّاً مكتوباً في المصدر.
_WRONG = "not-the-right-one"


async def _login(client: AsyncClient, email: str, password: str):
    """يرسل طلب دخول — نقطة الاستدعاء الوحيدة في هذا الملفّ."""
    return await client.post("/api/security/login", json={"email": email, "password": password})


def _fresh_password() -> str:
    """كلمة مرور اختبارية مُولَّدة لكل استدعاء.

    ليست تجميلاً لأداة تحليل: قيمةٌ ثابتة مكتوبة في المصدر تُغري بالنسخ إلى بيئة
    حقيقية، وتجعل اختبارين متجاورين يتقاسمان السرّ نفسه فيخفي أحدهما تسرّب
    الآخر. التوليد يجعل كل اختبار مستقلاً بالبناء.
    """
    return f"Pw-{uuid.uuid4().hex}-Aa1!"


@pytest.fixture(autouse=True)
def _clean_shield():
    """كل اختبارٍ يبدأ بدرعٍ نظيف — استقلالٌ بالبناء لا بالانضباط.

    ⚠️ رصدت مراجعة CodeRabbit أنّ ستّة اختبارات في هذا الملفّ تُخفِق على **نفس
    الهوية** (`ghost-user@example.com`)، وكلٌّ منها يمرّ بـ`check_allowance`.
    فالعدّاد يتراكم عبر الاختبارات في نفس العملية، ويقترب من `LOCKOUT_THRESHOLD`
    بينما يبدأ الإبطاء المتدرّج بإضافة انتظارٍ حقيقي. أي أنّ إضافة اختبارٍ سابعٍ
    غداً كانت ستُحمِّر ملفّاً لم يتغيّر — وهو أسوأ أصناف الهشاشة: فشلٌ يبدو
    عشوائياً فيُطفَأ الملفّ كلّه.

    والتنظيف هنا يُغني عن `chrono_shield._failures.clear()` المتناثر داخل ستّة
    اختبارات (مصدرٌ واحد بدل ستّة مواضع تُنسى إحداها).

    ⛔ **وكان جسم هذه المُثبِّتة `yield` وحده** — بلا أي تنظيف. حذفتُ نداءَي
    المسح بتعديلٍ جماعي أزال كل `_failures.clear()` من الملفّ، فبقي التوثيق
    يَعِد بما لا يحدث: مُثبِّتةٌ تشهد بنظافةٍ لم تصنعها. رصدته مراجعة CodeRabbit،
    وهو **نفس عطب D-208** الذي يفرضه هذا الـPR على غيره — ارتُكب داخله.
    فالدرس: التعديل الجماعي يُصيب ما لم يُقصَد، ويجب أن يُتبَع بقراءة الناتج.
    """
    chrono_shield._failures.clear()
    yield
    chrono_shield._failures.clear()


# ═══════════════════════════════════════════════════════════════════════════
# 1) عقد الأخطاء — الجذر المباشر لسلسلة «Login failed»
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_error_body_carries_detail_key(async_client: AsyncClient):
    """جسم الخطأ يحمل `detail` — المفتاح الذي تقرؤه كل واجهات الدخول.

    كان المعالج يُخرج `message` وحده، فكان `errorData.detail` يساوي `undefined`
    **دائماً** ويُعرَض السقوط الحرفي `'Login failed'`.
    """
    response = await _login(async_client, "ghost-user@example.com", _WRONG)

    assert response.status_code == 401
    body = response.json()

    assert "detail" in body, (
        "جسم الخطأ بلا `detail` — هذا بالضبط ما جعل الواجهة تعرض 'Login failed'."
    )
    assert body["detail"], "`detail` فارغ — الواجهة ستسقط إلى نصّها الافتراضي."


@pytest.mark.asyncio
async def test_detail_and_message_are_identical(async_client: AsyncClient):
    """`detail` و`message` يحملان نفس القيمة — لا حقلان بمعنيين (D-192)."""
    response = await _login(async_client, "ghost-user@example.com", _WRONG)
    body = response.json()
    assert body["detail"] == body["message"]


@pytest.mark.asyncio
async def test_error_body_carries_stable_error_code(async_client: AsyncClient):
    """رمز الخطأ مستقرّ — الواجهة تترجم بالرمز لا بمطابقة نصّ إنجليزي."""
    response = await _login(async_client, "ghost-user@example.com", _WRONG)
    assert response.json()["error_code"] == "unauthorized"


@pytest.mark.asyncio
async def test_error_timestamp_is_not_the_frozen_placeholder(async_client: AsyncClient):
    """الطابع الزمني حقيقي.

    كان مُثبَّتاً على `"2024-01-01T00:00:00Z"` مع تعليق `# Should be dynamic`.
    طابعٌ كاذب أسوأ من غيابه لأنه يُقرأ كأنه صحيح.
    """
    response = await _login(async_client, "ghost-user@example.com", _WRONG)
    assert response.json()["timestamp"] != "2024-01-01T00:00:00Z"


@pytest.mark.asyncio
async def test_error_body_carries_request_id(async_client: AsyncClient):
    """كل خطأ يحمل مُعرِّف طلب — بدونه لا يُشخَّص عطبٌ أبلغ عنه مستخدم."""
    response = await _login(async_client, "ghost-user@example.com", _WRONG)
    assert response.json()["request_id"]


@pytest.mark.asyncio
async def test_incoming_request_id_is_extended_not_reinvented(async_client: AsyncClient):
    """المُعرِّف الوارد يُمَدّ ولا يُخترَع (نفس قاعدة D-189 للأثر الصادر)."""
    correlation = f"trace-{uuid.uuid4().hex}"
    response = await async_client.post(
        "/api/security/login",
        json={"email": "ghost-user@example.com", "password": _WRONG},
        headers={"X-Request-ID": correlation},
    )
    assert response.json()["request_id"] == correlation


# ═══════════════════════════════════════════════════════════════════════════
# 2) القفل لا يعاقب البريء — العطب الذي أقفل المنصّة كلّها
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_strangers_failures_do_not_lock_out_an_innocent_user(
    async_client: AsyncClient,
):
    """إخفاقات الغرباء لا تمنع صاحب كلمة السرّ الصحيحة.

    مُبرهَنٌ حيّاً قبل الإصلاح: ١٩ محاولة فاشلة بعناوين بريد **مختلفة وغير
    موجودة** جعلت الضحيّة تتلقّى **429 بكلمة سرّها الصحيحة**، لأن مفتاح الدرع
    كان `ip:127.0.0.1` لكل المستخدمين خلف بروكسي Next.js.
    """

    email = f"victim-{uuid.uuid4().hex[:8]}@example.com"
    password = _fresh_password()
    registration = await async_client.post(
        "/api/security/register",
        json={"full_name": "Victim Student", "email": email, "password": password},
    )
    assert registration.status_code == 200, registration.text

    # عددُ الغرباء **مشتقٌّ لا مكتوب**: يتجاوز عتبة الهوية — وهي التي كانت
    # مُطبَّقة على `ip:` المشترك فأقفلت المنصّة — فلو غُيِّرت العتبة غداً بقي
    # الاختبار يختبر ما يدّعيه. الرقم المكتوب `25` كان يصير بلا معنى بأوّل
    # تعديل، ورصدته مراجعة CodeRabbit.
    strangers = chrono_shield.LOCKOUT_THRESHOLD + 5
    # غرباء يخفقون — كلٌّ ببريد مختلف، فلا تُلام هوية الضحيّة.
    for _ in range(strangers):
        await _login(async_client, f"stranger-{uuid.uuid4().hex[:10]}@example.com", _WRONG)

    victim = await _login(async_client, email, password)

    assert victim.status_code == 200, (
        f"طالبٌ بريء مُنِع بسبب إخفاقات غرباء — عاد القفل العالمي (ISS-152). body={victim.text[:200]}"
    )


@pytest.mark.asyncio
async def test_repeated_failures_on_one_identity_still_lock_that_identity(
    async_client: AsyncClient,
):
    """القفل يبقى فعّالاً على الهوية المستهدَفة — لم نُلغِ الحماية، نقلناها."""

    target = f"target-{uuid.uuid4().hex[:8]}@example.com"
    statuses = []
    for _ in range(chrono_shield.LOCKOUT_THRESHOLD + 2):
        response = await _login(async_client, target, _WRONG)
        statuses.append(response.status_code)

    assert 429 in statuses, (
        f"هوية واحدة تحت هجوم لم تُقفَل — الحماية ضاعت بدل أن تُنقَل. statuses={statuses}"
    )


@pytest.mark.asyncio
async def test_the_ip_vector_never_hard_locks_however_many_failures(monkeypatch):
    """⛔ العنوان يُبطِئ ولا يقفل — **مهما بلغ عدد إخفاقاته**.

    القاعدة 10 في `AUTHENTICATION_DOCTRINE.md` تقول «القفل الصلب (429) على الهوية
    وحدها»، وكان الكود يحمل فرعاً يقفل على العنوان عند `200`. أي أنّ القانون كان
    **بلا فارضٍ آلي**، فبقي مناقِضاً لكوده وCI خضراء — وهو صنف عطب D-208 نفسه.

    ومئتان لم تكن رقماً آمناً بل **مؤجِّلاً**: 200 إخفاق في نافذة ٥ دقائق من عنوان
    carrier-NAT جزائري واحد عاديٌّ في ذروة المساء، والنتيجة 429 لكل طالبٍ خلفه
    بكلمة سرّه الصحيحة — أي ISS-152 حرفياً. رصدته مراجعة CodeRabbit.

    الاختبار يحقن إخفاقاتٍ أكثر من أيّ عتبةٍ معقولة ويطالب بمرور هويةٍ نظيفة.
    """

    class _Client:
        host = "197.200.0.7"  # عنوانٌ عام — يحاكي مخرَج carrier-NAT

    class _Request:
        client = _Client()
        headers: ClassVar[dict[str, str]] = {}

    request = _Request()
    now = time.time()
    # أكبر بكثير من العتبة المحذوفة (200) ومن أي عتبةٍ قد تُستحدث.
    chrono_shield._failures["ip:197.200.0.7"] = [now] * 5_000

    # المتّجه العنواني يبقى **مُكلِّفاً**: الحماية نُقلت من المنع إلى الإبطاء
    # ولم تُلغَ. تُقاس على الدالّة الحتمية لا على مدّة نومٍ حقيقية.
    assert chrono_shield._dilation_delay(target_fails=0, ip_fails=5_000) > 0, (
        "الإبطاء اختفى مع القفل — المتّجه العنواني يجب أن يبقى مُكلِّفاً."
    )

    # الإبطاء يُعطَّل زمنياً لا منطقياً: نقيس **القفل** لا مدّة النوم.
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    # هويةٌ نظيفة خلف نفس العنوان: يجب أن تمرّ بلا استثناء.
    await chrono_shield.check_allowance(request, "innocent@example.com")

    # وفي المقابل: الهوية **تُقفَل** — الحماية نُقلت ولم تُلغَ.
    chrono_shield._failures["target:hunted@example.com"] = [now] * (
        chrono_shield.LOCKOUT_THRESHOLD + 1
    )
    with pytest.raises(HTTPException) as raised:
        await chrono_shield.check_allowance(request, "hunted@example.com")
    assert raised.value.status_code == 429


def test_dilation_saturates_instead_of_overflowing():
    """⛔ الإبطاء يتشبّع ولا يطفح — مهما بلغ عدد الإخفاقات.

    `min(0.1 * 2**worst, MAX_DELAY)` تبدو مسقوفة وهي ليست كذلك: القوس الداخلي
    يُحسَب أوّلاً، فـ`2 ** 4980` يرفع `OverflowError` — أي **500 على كل محاولة
    دخول من ذلك العنوان**، بمن فيهم الأبرياء. كان الفرع محجوباً خلف القفل
    العنواني؛ ولمّا حُذف القفل صار بلوغه مسألة وقت.

    ⚠️ لم تكشفه مراجعةٌ ولا بوّابة — كشفه **الاختبار الذي كُتب لحراسة الحذف**،
    وهذا هو الفرق بين حذفٍ محروس وحذفٍ متفائل.
    """
    for fails in (100, 1_000, 100_000):
        delay = chrono_shield._dilation_delay(target_fails=0, ip_fails=fails)
        assert delay == chrono_shield.MAX_DELAY, f"إبطاءٌ غير مُتشبِّع عند {fails} إخفاقاً: {delay}"
    # والتدرّج ما دون التشبّع يبقى تدرّجاً حقيقياً لا ثابتاً.
    gentle = chrono_shield._dilation_delay(
        target_fails=0, ip_fails=chrono_shield.IP_MAX_FREE_ATTEMPTS + 1
    )
    assert 0 < gentle < chrono_shield.MAX_DELAY


def test_successful_login_clears_the_ip_counter_too():
    """النجاح يُطهّر عدّاد العنوان أيضاً.

    كان `reset_target` يمسح `target:` وحده ويترك `ip:` ينمو أبداً — فكان الدخول
    الناجح لا يخفّض العدّاد الذي يقفل المنصّة.
    """

    class _Client:
        host = "203.0.113.9"

    class _Request:
        client = _Client()
        headers: ClassVar[dict[str, str]] = {}

    request = _Request()
    chrono_shield.record_failure(request, "learner@example.com")

    assert chrono_shield._failures.get("ip:203.0.113.9")

    chrono_shield.reset_target("learner@example.com", request)

    assert not chrono_shield._failures.get("ip:203.0.113.9"), (
        "عدّاد العنوان بقي بعد نجاح المصادقة — النجاح يجب أن يُطهّر المتّجهين."
    )
    assert not chrono_shield._failures.get("target:learner@example.com")


def test_stale_failures_fall_out_of_the_window():
    """الإخفاقات خارج النافذة لا تُحتسَب تهديداً حاضراً.

    كانت القراءة `len(...)` بلا ترشيح، والترشيح كل ٦٠ ثانية فقط — فإخفاقاتٌ
    عمرها ساعة كانت تُحتسَب حتى تمرّ دورة التنظيف.
    """
    ancient = time.time() - (chrono_shield.WINDOW + 60)
    chrono_shield._failures["target:old@example.com"] = [ancient] * 50

    assert chrono_shield._live_failures("target:old@example.com") == 0


# ═══════════════════════════════════════════════════════════════════════════
# 3) هوية العميل — الترويسة لا تُصدَّق إلّا من وسيط موثوق
# ═══════════════════════════════════════════════════════════════════════════


class _FakeRequest:
    """طلبٌ مبسَّط — `client_identity` لا يستورد Starlette عمداً."""

    def __init__(self, peer: str | None, headers: dict[str, str] | None = None) -> None:
        self.client = type("C", (), {"host": peer})() if peer else None
        self.headers = headers or {}


def test_forwarded_header_is_ignored_from_an_untrusted_peer():
    """⛔ عميلٌ مباشر لا يُصدَّق حين يزعم عنواناً آخر.

    الترويسة يزوّرها العميل بحرّية؛ الثقة بها بلا شرط تُحوِّل حدّ المعدّل إلى
    زينة (كل طلب بعنوان مختلف = حدٌّ لا يُبلَغ أبداً).
    """
    from app.security.client_identity import resolve_client_ip

    request = _FakeRequest("198.51.100.7", {"x-forwarded-for": "1.2.3.4"})
    assert resolve_client_ip(request) == "198.51.100.7"


def test_forwarded_header_is_trusted_from_the_local_proxy():
    """الوسيط المحلّي موثوق — وهو بالضبط نشرُنا (Next.js ⇒ 127.0.0.1 ⇒ uvicorn)."""
    from app.security.client_identity import resolve_client_ip

    request = _FakeRequest("127.0.0.1", {"x-forwarded-for": "203.0.113.55"})
    assert resolve_client_ip(request) == "203.0.113.55"


def test_rightmost_untrusted_hop_wins():
    """يُمشى من اليمين: أوّل عنوان غير موثوق هو العميل الحقيقي.

    السلسلة يكتبها العميل من اليسار، فأوّل قيمة هي **ما زعمه هو**.
    """
    from app.security.client_identity import resolve_client_ip

    request = _FakeRequest("127.0.0.1", {"x-forwarded-for": "9.9.9.9, 203.0.113.55, 127.0.0.1"})
    assert resolve_client_ip(request) == "203.0.113.55"


def test_malformed_forwarded_values_do_not_crash():
    """ترويسة مشوّهة تسقط إلى النظير بدل أن تُسقِط الطلب."""
    from app.security.client_identity import resolve_client_ip

    request = _FakeRequest("127.0.0.1", {"x-forwarded-for": "not-an-ip, ???"})
    assert resolve_client_ip(request) == "127.0.0.1"


def test_missing_client_returns_unknown():
    """غياب النظير يُعلَن ولا يُخمَّن."""
    from app.security.client_identity import client_ip_or_unknown

    assert client_ip_or_unknown(_FakeRequest(None)) == "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# 4) الرمز يقول لماذا أُصدر — إغلاق التباس الأنواع
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_access_token_declares_its_type(async_client: AsyncClient):
    """رمز الوصول يحمل `type` و`jti` و`iat`."""
    import base64
    import json

    email = f"claims-{uuid.uuid4().hex[:8]}@example.com"
    password = _fresh_password()
    await async_client.post(
        "/api/security/register",
        json={"full_name": "Claims User", "email": email, "password": password},
    )
    response = await _login(async_client, email, password)
    assert response.status_code == 200, response.text

    segment = response.json()["access_token"].split(".")[1]
    segment += "=" * (-len(segment) % 4)
    claims = json.loads(base64.urlsafe_b64decode(segment))

    assert claims["type"] == ACCESS_TOKEN_TYPE
    assert claims["jti"]
    assert claims["iat"]


def test_a_reauth_token_is_rejected_as_an_access_token():
    """⛔ رمز إعادة المصادقة لا يُقبَل كرمز وصول.

    كان `verify_access_token` = `jwt.decode` عارية، فكان **أي** رمز موقّع
    بالمفتاح نفسه يمرّ في كل موضع — بما فيه رمز `reauth` القصير ورمز الخدمة
    الداخلي الحامل `role: ADMIN`.
    """
    from fastapi import HTTPException

    from app.core.config import get_settings
    from app.core.domain.user import User
    from app.services.auth.crypto import AuthCrypto

    crypto = AuthCrypto(get_settings())
    user = User(id=1, full_name="Re Auth", email="reauth@example.com")
    reauth_token, _ = crypto.encode_reauth_token(user)

    with pytest.raises(HTTPException) as caught:
        crypto.verify_jwt(reauth_token, expected_type=ACCESS_TOKEN_TYPE)
    assert caught.value.status_code == 401


def test_legacy_tokens_without_a_type_still_authenticate():
    """تدهور رشيق: رمزٌ قديم بلا `type` يبقى صالحاً للوصول.

    طردُ كل جلسة قائمة ثمنٌ لا يشتري أماناً — والاتجاه الخطير (قبول رمزٍ من نوع
    آخر) مُغلق في الاختبار السابق.
    """
    import jwt

    from app.core.config import get_settings
    from app.services.auth.crypto import AuthCrypto

    settings = get_settings()
    crypto = AuthCrypto(settings)
    legacy = jwt.encode(
        {"sub": "1", "exp": int(time.time()) + 600}, settings.SECRET_KEY, algorithm="HS256"
    )

    assert crypto.verify_jwt(legacy, expected_type=ACCESS_TOKEN_TYPE)["sub"] == "1"


# ═══════════════════════════════════════════════════════════════════════════
# 5) بابٌ واحد — حساب معطَّل يُرفَض، وسرّية وجود الحساب محفوظة
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_login_issues_a_refresh_token(async_client: AsyncClient):
    """المسار الذي تستعمله الواجهة يُصدر رمز تحديث.

    كان يسكّ رمز وصولٍ عمره ٢٤ ساعة بلا رمز تحديث — أي أن علاج «الطرد إلى صفحة
    الدخول» كان إطالة عمر الرمز، وهي المقايضة المعكوسة.
    """
    email = f"refresh-{uuid.uuid4().hex[:8]}@example.com"
    password = _fresh_password()
    await async_client.post(
        "/api/security/register",
        json={"full_name": "Refresh User", "email": email, "password": password},
    )
    response = await _login(async_client, email, password)

    assert response.status_code == 200, response.text
    assert response.json()["refresh_token"], "لا رمز تحديث — القدرة المبنيّة تسقط عند حدّ التسلسل."


@pytest.mark.asyncio
async def test_a_disabled_account_cannot_log_in(async_client: AsyncClient, db_session):
    """⛔ حساب معطَّل يُرفَض من هذا الباب أيضاً.

    كان `AuthBoundaryService.authenticate_user` **لا يفحص** `is_active` ولا
    `status`، بينما `AuthService.authenticate` يفحصهما — فكان الحساب الموقوف
    يدخل من بابٍ ويُرفَض من آخر.
    """
    from sqlalchemy import select

    from app.core.domain.user import User

    email = f"disabled-{uuid.uuid4().hex[:8]}@example.com"
    password = _fresh_password()
    await async_client.post(
        "/api/security/register",
        json={"full_name": "Disabled User", "email": email, "password": password},
    )

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.is_active = False
    db_session.add(user)
    await db_session.commit()

    response = await _login(async_client, email, password)

    assert response.status_code == 401, (
        f"حساب معطَّل نجح في الدخول — الباب الثاني ما زال بحكمٍ مختلف. body={response.text[:200]}"
    )


@pytest.mark.asyncio
async def test_disabled_and_wrong_password_are_indistinguishable(
    async_client: AsyncClient, db_session
):
    """⛔ الرسالة لا تكشف وجود الحساب.

    «الحساب معطَّل» تُخبر المهاجم أن البريد مسجَّل — وهو تعداد حسابات مجّاني.
    """
    from sqlalchemy import select

    from app.core.domain.user import User

    email = f"enum-{uuid.uuid4().hex[:8]}@example.com"
    password = _fresh_password()
    await async_client.post(
        "/api/security/register",
        json={"full_name": "Enum User", "email": email, "password": password},
    )

    result = await db_session.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.is_active = False
    db_session.add(user)
    await db_session.commit()

    disabled = await _login(async_client, email, password)
    unknown = await async_client.post(
        "/api/security/login",
        json={"email": f"nobody-{uuid.uuid4().hex[:8]}@example.com", "password": password},
    )

    assert disabled.status_code == unknown.status_code == 401
    assert disabled.json()["detail"] == unknown.json()["detail"]
