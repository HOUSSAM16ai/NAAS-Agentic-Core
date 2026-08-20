"""نسخة مورّدة من ``shared/http_client/correlated.py`` (D-185 · نمط التوريد).

**D-189 · D4:** حقن `X-Correlation-ID` و`traceparent` على كل نداء صادر — مصدر
واحد داخل الخدمة بدل بناءات متفرّقة لـ `httpx.AsyncClient`. الخدمات المصغّرة
لا تستورد `shared` (قانون حدود الخدمات)، فيُورَّد المصدر الواحد داخل كل خدمة
(هذا الملف منسوخٌ حرفياً من `shared/http_client/correlated.py`)، وتراقب بوابة
`scripts/fitness/check_correlated_http.py` حدود المصانع المسموحة عبر AST —
أما مطابقة النسخة المورّدة للمصدر فموجّهٌ في وصف هذه الخدمة (`microservices/transition_service/README.md`)،
حيث إن إنشاء بوابة «توريد» عامةٍ خارج نطاق هذه الدفعة يكسر قاعدة `check_governance_registry.py`
(لا بوّاباتٍ مذكورةً بلا ملفّ — D-266).

## ما يفعله

- ``correlated_client(timeout=...)`` — مدير سياق يُعيد ``httpx.AsyncClient``
  بترويسات افتراضية تحمل ``X-Correlation-ID`` و``traceparent``، وبمهلة صريحة
  إلزامية (لا انتظار مفتوح).
- ``current_correlation_id()`` — يقرأ المعرف المحيط عبر **مزوّد مسجّل**؛ بلا
  مزوّد ⇒ يُولَّد معرّف جديد (تدهور رشيق، لا انفجار).

## ما لا يفعله

لا يلمس سلسلة النماذج ولا مسار توليد إجابة (محروس أمنياً ISS-079/D-067).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager

import httpx

CORRELATION_HEADER = "X-Correlation-ID"
TRACEPARENT_HEADER = "traceparent"

# مهلة افتراضية صريحة: `httpx` بلا timeout ينتظر إلى الأبد، وانتظارٌ مفتوح
# على حدّ خدمة يحوّل خدمةً بطيئة إلى تعليقٍ كامل («Degraded ≠ Dead»).
DEFAULT_TIMEOUT_SECONDS = 10.0

_CorrelationProvider = Callable[[], str | None]
_provider: _CorrelationProvider | None = None


def set_correlation_provider(provider: _CorrelationProvider | None) -> None:
    """يُسجِّل مصدر المعرف المحيط لهذه العملية (يُستدعى مرة عند الإقلاع).

    التمرير ``None`` يلغي التسجيل — مفيد لعزل الاختبارات.
    """
    global _provider
    _provider = provider


def current_correlation_id(explicit: str | None = None) -> str:
    """يُرجع المعرف الواجب إرساله: الصريح، ثم المحيط، ثم مولَّد جديد.

    الترتيب مقصود: **مدّ** السلسلة الواردة أولاً؛ التوليد ملاذ أخير حتى لا
    نقطع الأثر كما كان يحدث في مواضع الحقن القديمة.
    """
    if explicit:
        return explicit

    if _provider is not None:
        try:
            ambient = _provider()
        except Exception:
            ambient = None
        if ambient:
            return ambient

    return uuid.uuid4().hex


def _traceparent(correlation_id: str) -> str:
    """يبني ترويسة W3C ``traceparent`` مشتقة من المعرف نفسه.

    اشتقاق trace-id من المعرف (لا عشوائياً) يجعل الأثر والسجل قابلين للربط
    بمعرف واحد — وإلا صار لدينا هويتان لنفس الدور.
    """
    digits = "".join(
        character for character in correlation_id.lower() if character in "0123456789abcdef"
    )
    trace_id = (digits * 2)[:32].ljust(32, "0") if digits else uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    return f"00-{trace_id}-{span_id}-01"


def correlation_headers(
    extra: Mapping[str, str] | None = None,
    *,
    correlation_id: str | None = None,
) -> dict[str, str]:
    """يُرجع ترويسات النداء الصادر حاملةً هوية التتبع.

    ترويسات المستدعي تُحترم: إن كان ``extra`` يحمل ``X-Correlation-ID``
    صريحاً فهو الأولى (المستدعي أعرف بسياقه)، ولا يُطمس بمعرّف مولَّد.
    """
    provided = dict(extra or {})
    inbound = next(
        (value for key, value in provided.items() if key.lower() == CORRELATION_HEADER.lower()),
        None,
    )
    resolved = current_correlation_id(correlation_id or inbound)

    headers = {
        key: value for key, value in provided.items() if key.lower() != CORRELATION_HEADER.lower()
    }
    headers[CORRELATION_HEADER] = resolved
    headers.setdefault(TRACEPARENT_HEADER, _traceparent(resolved))
    return headers


@asynccontextmanager
async def correlated_client(
    *,
    timeout: float | httpx.Timeout | None = None,
    headers: Mapping[str, str] | None = None,
    correlation_id: str | None = None,
    **client_kwargs: object,
) -> AsyncIterator[httpx.AsyncClient]:
    """مدير سياق يُعيد ``httpx.AsyncClient`` مصححاً بالتتبع ومقيداً بمهلة.

    يُستعمل حيث كان ``async with httpx.AsyncClient(...)`` يُبنى مباشرةً::

        async with correlated_client(timeout=5.0) as client:
            response = await client.post(url, json=payload)

    ``timeout=None`` يعني «استعمل الافتراضي الصريح» لا «بلا مهلة» — ``httpx``
    يفهم ``None`` بأنها انتظار مفتوح، وهذا ما نمنعه.
    """
    resolved_timeout = DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout
    async with httpx.AsyncClient(
        timeout=resolved_timeout,
        headers=correlation_headers(headers, correlation_id=correlation_id),
        **client_kwargs,  # type: ignore[arg-type]
    ) as client:
        yield client
