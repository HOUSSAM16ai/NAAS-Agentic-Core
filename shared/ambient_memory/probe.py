"""مسبار توفّر طبقة الهوية المعرفية المحيطة — D-269.

## لماذا مسبارٌ لا «تكامل»

وجودُ مفتاحٍ في البيئة ليس دليلاً على قدرة. هذا هو البرهان الثلاثي (§6.6) مطبَّقاً
على طرفٍ ثالث: ``import`` + سلسلة نداء + **دليل تشغيل**. والمسبار هو الساق الثالثة.

وهو **قراءةٌ محضة**: ``POST {base}/{version}/workspaces/list`` — يسأل «هل تقبلني؟»
ولا يكتب شيئاً ولا يقرأ محادثةً. ⛔ صفر بيانات طالبٍ تغادر المنصّة في هذه المرحلة؛
مسارُ الكتابة `SEAM` مُعلَنة بصفر كود وشرطُ ترقيتها منطوق في
``.memory/ambient_identity_truth.md``.

## قواعد دائمة يفرضها هذا الملفّ

* **لا يرفع في وجه المُنادي أبداً.** فشلُ طرفٍ ثالث يصير حالةً تُعلَن، لا استثناءً
  يتسلّق إلى دور طالب (نمط D-074: «البنية المعرفية لا تكسر الدردشة أبداً»).
* **مهلة صريحة دائماً** — الانتظار المفتوح على حدّ طرفٍ ثالث يحوّل البطء إلى تعليق
  (D-189 البند 4).
* **الأثر يُمَدّ ولا يُخترَع**: النداء عبر ``shared.http_client.correlated_client``
  وحده (D-189)، فلا مُعرَّف تتبّعٍ جديد يقطع السلسلة.
* ⛔ **لا يُطبَع المفتاح ولا جزءٌ منه** في أيّ رسالة — ولا حتى في نصّ خطأ.
* ⛔ **صفر تبعيةٍ جديدة**: لا ``honcho-ai``. حزمةٌ إضافية على منصّةٍ تخدم قاصرين
  سطحُ هجومٍ يُدفَع ثمنه، ونداءُ REST واحدٌ لا يستحقّه.
"""

from __future__ import annotations

import httpx

from shared.ambient_memory.contract import AmbientMemoryConfig, AmbientMemoryProbeResult
from shared.http_client import correlated_client

#: رسالة الحالة غير المُهيَّأة. تُقال بوضوح: الغياب مُعلَن ولا يُقرأ نجاحاً ولا عطلاً
#: (D-206 L11).
_NOT_CONFIGURED_DETAIL = "HONCHO_API_KEY غير مضبوط — الطبقة اختيارية ولا يتأثّر دور الطالب."


def _unauthorized(status_code: int) -> AmbientMemoryProbeResult:
    return AmbientMemoryProbeResult(
        state="unauthorized",
        detail=("المفتاح حاضرٌ ومرفوض من الطرف الثالث — عطلُ إعدادٍ صريح لا انقطاعُ شبكة."),
        status_code=status_code,
    )


def _parse_workspaces(payload: object) -> int | None:
    """عدد مساحات العمل إن كان الجسم بالشكل المتوقَّع، وإلّا ``None``.

    ⛔ لا يُقرأ من الجسم شيءٌ سوى **عدد**: لا أسماء، ولا بيانات، ولا نصّ. جسمٌ بشكلٍ
    غير متوقَّع يُترك بلا عدد بدل أن يُخمَّن — والمجهول أفضل من يقينٍ زائف (§0).
    """
    if not isinstance(payload, dict):
        return None
    total = payload.get("total")
    if isinstance(total, bool) or not isinstance(total, int):
        return None
    return total


def _classify(response: httpx.Response) -> AmbientMemoryProbeResult:
    """يترجم ردّ الطرف الثالث إلى حالةٍ من القائمة المغلقة — دالّةٌ نقيّة بلا شبكة."""
    if response.status_code in (401, 403):
        return _unauthorized(response.status_code)

    if response.status_code >= 400:
        return AmbientMemoryProbeResult(
            state="unreachable",
            detail="ردَّ الطرف الثالث بخطأ — لا نعرف حالة الطبقة.",
            status_code=response.status_code,
        )

    try:
        payload: object = response.json()
    except ValueError:
        return AmbientMemoryProbeResult(
            state="unreachable",
            detail="ردٌّ غير قابل للتفسير — الشكل غير المتوقَّع لا يُقرأ نجاحاً.",
            status_code=response.status_code,
        )

    return AmbientMemoryProbeResult(
        state="reachable",
        detail="الطبقة متاحة (استعلام قراءةٍ فقط — ⛔ لا بيانات طالبٍ تُرسَل).",
        workspace_count=_parse_workspaces(payload),
        status_code=response.status_code,
    )


async def _fetch(config: AmbientMemoryConfig) -> httpx.Response | AmbientMemoryProbeResult:
    """يُنفِّذ الاستعلام، أو يُعيد حالةَ تعذّرٍ — ⛔ ولا يرفع في وجه المُنادي أبداً."""
    try:
        async with correlated_client(
            timeout=config.timeout_seconds,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            return await client.post(config.workspaces_list_url(), json={})
    except httpx.TimeoutException:
        return AmbientMemoryProbeResult(
            state="unreachable",
            detail=(
                f"انتهت المهلة بعد {config.timeout_seconds:g}s — "
                f"⚠️ هذا يعني «لا نعرف» لا «سليم» (D-215)."
            ),
        )
    except httpx.HTTPError as exc:
        # ⛔ اسمُ الصنف لا نصّ الاستثناء: نصُّ httpx قد يحمل الـURL كاملاً بترويساته.
        return AmbientMemoryProbeResult(
            state="unreachable",
            detail=f"تعذّر الوصول إلى الطبقة ({type(exc).__name__}).",
        )


async def probe_ambient_memory(config: AmbientMemoryConfig) -> AmbientMemoryProbeResult:
    """يسأل الطبقة «هل تقبلني؟» ويُعيد حالةً مُعلَنة — ولا يرفع أبداً."""
    if not config.configured:
        return AmbientMemoryProbeResult(state="not_configured", detail=_NOT_CONFIGURED_DETAIL)

    outcome = await _fetch(config)
    if isinstance(outcome, AmbientMemoryProbeResult):
        return outcome
    return _classify(outcome)
