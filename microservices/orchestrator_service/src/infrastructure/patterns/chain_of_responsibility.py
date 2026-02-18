"""سلسلة المسؤوليات لمعالجة الطلبات بأسلوب قابل للتوسعة."""

from abc import ABC, abstractmethod
from typing import TypeVar

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")


class Handler[TRequest, TResponse](ABC):
    """معالج تجريدي يمثل حلقة في سلسلة المسؤوليات."""

    def __init__(self):
        self._next_handler: Handler[TRequest, TResponse] | None = None

    def set_next(self, handler: "Handler[TRequest, TResponse]") -> "Handler[TRequest, TResponse]":
        """يضبط الحلقة التالية في السلسلة ويعيدها للسماح بالتسلسل."""
        self._next_handler = handler
        return handler

    def handle(self, request: TRequest) -> TResponse | None:
        """يعالج الطلب أو يمرره إلى الحلقة التالية عند غياب نتيجة."""
        result = self._process(request)

        if result is not None:
            return result

        if self._next_handler:
            return self._next_handler.handle(request)

        return None

    @abstractmethod
    def _process(self, request: TRequest) -> TResponse | None:
        """ينفذ منطق الحلقة. إرجاع None يسمح بتمرير الطلب."""


class RequestContext:
    """حاوية بيانات الطلب ومسار التحقق عبر السلسلة."""

    def __init__(self, data: dict[str, object] | None = None):
        self.data: dict[str, object] = data or {}
        self.metadata: dict[str, object] = {}
        self.errors: list[str] = []
        self.stopped = False

    def stop_chain(self) -> None:
        """يوقف تنفيذ بقية السلسلة بشكل صريح."""
        self.stopped = True

    def add_error(self, error: str) -> None:
        """يسجل خطأ في السياق للمراجعة أو الاستجابة."""
        self.errors.append(error)

    def has_errors(self) -> bool:
        """يتحقق من وجود أخطاء متراكمة في السياق."""
        return len(self.errors) > 0


class AuthenticationHandler(Handler[RequestContext, RequestContext]):
    """حلقة مصادقة تتحقق من صلاحية رمز الوصول."""

    def _process(self, request: RequestContext) -> RequestContext | None:
        """يتأكد من وجود رمز مصادقة صالح قبل متابعة السلسلة."""
        token = request.data.get("auth_token")

        if not token:
            request.add_error("Missing authentication token")
            request.stop_chain()
            return request

        if not self._validate_token(str(token)):
            request.add_error("Invalid authentication token")
            request.stop_chain()
            return request

        request.metadata["authenticated"] = True
        return None

    def _validate_token(self, token: str) -> bool:
        """يتحقق من سلامة رمز المصادقة."""
        return len(token) > 0


class AuthorizationHandler(Handler[RequestContext, RequestContext]):
    """حلقة تفويض تتحقق من امتلاك الصلاحيات المناسبة."""

    def _process(self, request: RequestContext) -> RequestContext | None:
        """يتحقق من توفر الصلاحيات بعد نجاح المصادقة."""
        if not bool(request.metadata.get("authenticated")):
            request.add_error("Not authenticated")
            request.stop_chain()
            return request

        required_permission = request.data.get("required_permission")
        user_permissions_raw = request.data.get("user_permissions", [])
        user_permissions = user_permissions_raw if isinstance(user_permissions_raw, list) else []

        if isinstance(required_permission, str) and required_permission not in user_permissions:
            request.add_error(f"Missing permission: {required_permission}")
            request.stop_chain()
            return request

        request.metadata["authorized"] = True
        return None


class RateLimitHandler(Handler[RequestContext, RequestContext]):
    """حلقة تحديد المعدل لضبط عدد الطلبات المسموح به."""

    def __init__(self, max_requests: int = 100):
        super().__init__()
        self.max_requests = max_requests
        self._request_counts: dict[str, int] = {}

    def _process(self, request: RequestContext) -> RequestContext | None:
        """يتابع عدد الطلبات لكل مستخدم لضمان عدم تجاوز الحد."""
        user_id_raw = request.data.get("user_id", "anonymous")
        user_id = user_id_raw if isinstance(user_id_raw, str) else "anonymous"
        count = self._request_counts.get(user_id, 0)

        if count >= self.max_requests:
            request.add_error("Rate limit exceeded")
            request.stop_chain()
            return request

        self._request_counts[user_id] = count + 1
        request.metadata["rate_limit_remaining"] = self.max_requests - count - 1
        return None


class ValidationHandler(Handler[RequestContext, RequestContext]):
    """حلقة تحقق من اكتمال بيانات الطلب."""

    def __init__(self, required_fields: list[str] | None = None):
        super().__init__()
        self.required_fields = required_fields or []

    def _process(self, request: RequestContext) -> RequestContext | None:
        """يتحقق من توفر الحقول المطلوبة ويوقف السلسلة عند النقص."""
        for field in self.required_fields:
            if field not in request.data:
                request.add_error(f"Missing required field: {field}")

        if request.has_errors():
            request.stop_chain()
            return request

        request.metadata["validated"] = True
        return None


class LoggingHandler(Handler[RequestContext, RequestContext]):
    """حلقة تسجيل لمتابعة معرّفات الطلبات."""

    def _process(self, request: RequestContext) -> RequestContext | None:
        """يسجل الطلب الحالي ثم يسمح بمتابعة السلسلة."""
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Processing request: {request.data.get('request_id', 'unknown')}")

        return None


class CachingHandler(Handler[RequestContext, RequestContext]):
    """حلقة تخزين مؤقت لتجنب المعالجة المكررة للطلبات."""

    def __init__(self):
        super().__init__()
        self._cache: dict[str, dict[str, str | int | bool]] = {}

    def _process(self, request: RequestContext) -> RequestContext | None:
        """يتحقق من وجود استجابة مخزنة مسبقًا قبل متابعة السلسلة."""
        cache_key_raw = request.data.get("cache_key")
        cache_key = cache_key_raw if isinstance(cache_key_raw, str) else None

        if cache_key and cache_key in self._cache:
            request.data["cached_response"] = self._cache[cache_key]
            request.metadata["from_cache"] = True
            return request

        return None

    def cache_response(self, key: str, response: dict[str, str | int | bool]) -> None:
        """يخزن استجابة صالحة لإعادة استخدامها لاحقًا."""
        self._cache[key] = response


def build_request_pipeline() -> Handler[RequestContext, RequestContext]:
    """ينشئ سلسلة المعالجة القياسية للطلبات من مصادقة إلى تسجيل."""
    auth = AuthenticationHandler()
    authz = AuthorizationHandler()
    rate_limit = RateLimitHandler()
    validation = ValidationHandler()
    logging_handler = LoggingHandler()

    auth.set_next(authz).set_next(rate_limit).set_next(validation).set_next(logging_handler)

    return auth
