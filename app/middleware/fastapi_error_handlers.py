# app/middleware/fastapi_error_handlers.py
"""عقد الأخطاء الموحَّد (Unified Error Contract) — D-236 · ISS-152.

## لماذا يوجد هذا الملفّ بهذا الشكل

الطالب كان يرى **`Login failed`** — سلسلة إنجليزية حرفية على منصّة عربية، بلا سبب،
مهما كان الخطأ الحقيقي (401 · 429 · 422 · 500). والجذر **قياسٌ لا فرضية**:

```text
POST /api/security/login  (كلمة سرّ خاطئة) -> 401
RAW BODY: {"status":"error","message":"Invalid email or password","data":null,...}
TOP-LEVEL KEYS: ['data', 'message', 'status', 'timestamp']
HAS 'detail' KEY: False        ← المعالج لم يُخرج `detail` قطّ
==> FRONTEND WOULD DISPLAY: 'Login failed'
```

كان المعالج يُخرج `message`، وكل عملاء الواجهة الثلاثة يقرؤون `detail`
(`CogniForgeApp.jsx:53` · `frontend/public/js/legacy-app.jsx:384` ·
`app/static/js/legacy-app.jsx:360`) بالصيغة `errorData.detail || 'Login failed'`.
فـ`.detail` كان `undefined` **دائماً** ⇒ يُعرَض السقوط الحرفي، وتُرمى الرسالة الحقيقية.

**عقدان مختلفان بين الواجهة والخلفية، ولا بوّابة تحرس التطابق.** تحرسه الآن
`scripts/fitness/check_error_contract_parity.py`.

## القواعد الدائمة

1. **كل خطأ يحمل `detail` و`message` معاً.** `detail` عقد FastAPI/Starlette القياسي
   وما يقرأه كل عميل؛ و`message` يبقى لأن اختبارات قائمة تعتمده صراحةً
   (`tests/security/test_login_strict_verification.py:95`). القيمتان **متطابقتان
   دائماً** — حقلان بقيمتين مختلفتين يعيدان إنتاج نفس العطب بصيغة أخرى (D-192).
2. **`error_code` مستقرّ وقابل للترجمة.** الواجهة تترجم بالرمز لا بمطابقة نصّ
   إنجليزي — مطابقة النصّ تنكسر بأوّل إعادة صياغة.
3. **`timestamp` حقيقي.** كان مُثبَّتاً على `"2024-01-01T00:00:00Z"` مع تعليق
   `# Should be dynamic` — طابعٌ زمني كاذب أسوأ من غيابه، لأنه يُقرأ كأنه صحيح.
4. **لا تسريب داخلي في الإنتاج.** كان `general_exception_handler` يضع `str(exc)`
   في `data` في **كل** البيئات. صار محجوباً خارج التطوير، ويبقى في السجلّ مربوطاً
   بـ`request_id` — فيُشخَّص العطب بلا كشف بنية النظام للمهاجم.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

__all__ = [
    "ERROR_CODE_HEADER",
    "REQUEST_ID_HEADER",
    "ErrorContext",
    "add_error_handlers",
    "build_error_payload",
    "general_exception_handler",
    "http_exception_handler",
    "validation_exception_handler",
]

REQUEST_ID_HEADER: Final[str] = "X-Request-ID"
ERROR_CODE_HEADER: Final[str] = "X-Error-Code"

# رموز الأخطاء المستقرّة — الواجهة تترجمها، ولا تطابق النصّ الإنجليزي.
# ⛔ لا يُحذَف رمزٌ ولا يُعاد استعماله بمعنى آخر: الواجهة القديمة تبقى تقرؤه.
_STATUS_TO_ERROR_CODE: Final[dict[int, str]] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    423: "account_locked",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
    504: "upstream_timeout",
}


def _error_code_for(status_code: int) -> str:
    """يعيد رمز الخطأ المستقرّ الموافق لرمز حالة HTTP."""
    if status_code in _STATUS_TO_ERROR_CODE:
        return _STATUS_TO_ERROR_CODE[status_code]
    if 400 <= status_code < 500:
        return "client_error"
    return "server_error"


def _request_id(request: Request) -> str:
    """يستخرج مُعرِّف الطلب من الترويسة الواردة أو يولّده.

    يُمَدّ ولا يُخترَع متى وُجد (نفس قاعدة D-189 للأثر الصادر): مُعرِّفٌ جديد لكل
    طبقة يقطع السلسلة بدل مدّها، فتصير الترويسة موجودةً وبلا قيمة تشخيصية.
    """
    incoming = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
    if incoming:
        return incoming[:128]
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, str) and existing.strip():
        return existing.strip()[:128]
    return uuid.uuid4().hex


def _is_debug_environment() -> bool:
    """هل يُسمح بإرجاع التفاصيل الداخلية في جسم الاستجابة؟

    fail-closed: أي تعذّر في قراءة الإعدادات يعني **لا كشف**. حارسٌ يفشل مفتوحاً
    على مسار تسريبٍ ليس حارساً.
    """
    try:
        from app.core.settings.base import get_settings

        return str(get_settings().ENVIRONMENT).strip().lower() in {
            "development",
            "dev",
            "local",
            "testing",
            "test",
        }
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """كل ما يلزم لبناء جسم خطأ — كائنٌ واحد بدل خمسة وسائط.

    وُلد من قياس CodeScene («Excess Number of Function Arguments» على
    `build_error_payload`): خمسة وسائط مفتاحية تصف **شيئاً واحداً** هو الخطأ
    الجاري، فالأنسب تسميته نوعاً بدل تفريقه في توقيع.
    """

    message: str
    status_code: int
    request_id: str
    data: object | None = None
    error_code: str | None = None

    def resolved_error_code(self) -> str:
        """رمز الخطأ الصريح، أو المُشتَقّ من رمز الحالة."""
        return self.error_code or _error_code_for(self.status_code)


def build_error_payload(context: ErrorContext) -> dict[str, object]:
    """يبني جسم الخطأ الموحَّد.

    ``detail`` و``message`` يحملان **نفس القيمة** عمداً: الأوّل عقد FastAPI الذي
    يقرأه كل عميل، والثاني توافقٌ تاريخي تعتمده اختبارات قائمة. قيمتان مختلفتان
    لنفس المعنى هي بالضبط العطب الذي أنتج «Login failed».
    """
    message = context.message
    return {
        "status": "error",
        "detail": message,
        "message": message,
        "error_code": context.resolved_error_code(),
        "data": context.data,
        "request_id": context.request_id,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _json_error(context: ErrorContext, headers: dict[str, str] | None = None) -> JSONResponse:
    """يغلّف جسم الخطأ في استجابة JSON مع ترويسات التشخيص."""
    payload = build_error_payload(context)
    response_headers = dict(headers or {})
    response_headers[REQUEST_ID_HEADER] = context.request_id
    response_headers[ERROR_CODE_HEADER] = str(payload["error_code"])
    return JSONResponse(status_code=context.status_code, content=payload, headers=response_headers)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """يحوّل ``HTTPException`` إلى عقد الأخطاء الموحَّد.

    ⚠️ ترويسات الاستثناء تُمَرَّر (``Retry-After`` · ``WWW-Authenticate``): كانت
    تُسقَط صامتةً، فكان العميل يتلقّى 429 بلا أي إشارة إلى متى يعيد المحاولة.
    """
    context = ErrorContext(
        message=str(exc.detail),
        status_code=exc.status_code,
        request_id=_request_id(request),
    )
    return _json_error(context, headers=dict(getattr(exc, "headers", None) or {}))


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """يحوّل أخطاء التحقّق إلى نفس العقد.

    ``detail`` يبقى **نصّاً** لا قائمة: الواجهة تعرضه مباشرةً للطالب، وقائمة
    كائنات تُصيّر كـ``[object Object]`` أو تُسقِط الواجهة. التفاصيل البنيوية
    تعيش في ``data.errors`` لمن يحتاجها.
    """
    return _json_error(
        ErrorContext(
            message="Validation Error",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            request_id=_request_id(request),
            data={"errors": jsonable_errors(exc.errors())},
        )
    )


def jsonable_errors(errors: object) -> object:
    """يجعل تفاصيل أخطاء التحقّق قابلة للتسلسل إلى JSON.

    ``RequestValidationError.errors()`` قد يحمل استثناءً أصلياً تحت ``ctx``،
    وهو غير قابل للتسلسل — فيتحوّل ردّ 422 إلى 500 داخل مُسلسِل الاستجابة.
    """
    from fastapi.encoders import jsonable_encoder

    try:
        return jsonable_encoder(errors)
    except Exception:
        return [{"msg": "unserializable validation error"}]


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """يلتقط أي استثناء غير متوقّع.

    ⛔ لا يُعاد ``str(exc)`` في الإنتاج. يُسجَّل كاملاً مع ``request_id`` فيُشخَّص
    العطب بلا كشف بنية النظام لمن يطرق الباب.
    """
    request_id = _request_id(request)
    logger.exception(
        "Unhandled exception request_id=%s path=%s method=%s",
        request_id,
        request.url.path,
        request.method,
    )
    return _json_error(
        ErrorContext(
            message="Internal Server Error",
            status_code=500,
            request_id=request_id,
            data={"exception": str(exc)} if _is_debug_environment() else None,
        )
    )


def add_error_handlers(app: FastAPI) -> None:
    """يسجّل معالجات الأخطاء الثلاثة على التطبيق."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
