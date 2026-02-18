"""
خدمة البوابة المركزية (Gateway Service).

تمثل هذه الخدمة نقطة الدخول الموحدة لجميع الطلبات، وتطبق سياسات الأمان،
والتوجيه الذكي، والتخزين المؤقت لضمان أداء عالٍ وحماية قوية.

المبادئ (Principles):
- Functional Core: معالجة الطلبات كسلسلة من التحويلات الوظيفية.
- Defense in Depth: تطبيق السياسات في وقت مبكر.
- Observability: تسجيل المقاييس والأخطاء بدقة.
- SOLID - Dependency Inversion: حقن التبعيات (Router, Cache, Policy) بدلاً من إنشائها داخلياً.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from functools import wraps

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.types import JSON, JSONDict

from .cache import CacheFactory, generate_cache_key
from .models import GatewayRoute, PolicyRule, ProtocolType, UpstreamService
from .policy import PolicyEngine
from .protocols.base import ProtocolAdapter
from .protocols.cache import CacheProviderProtocol
from .protocols.graphql import GraphQLAdapter
from .protocols.grpc import GRPCAdapter
from .protocols.rest import RESTAdapter
from .routing import IntelligentRouter

logger = logging.getLogger(__name__)


class APIGatewayService:
    """
    خدمة بوابة API الخارقة - Superhuman API Gateway Service

    المميزات:
    - استقبال موحد لجميع الطلبات.
    - محولات بروتوكولات (REST/GraphQL/gRPC).
    - محرك توجيه ذكي.
    - تخزين مؤقت ديناميكي.
    - تطبيق سياسات الأمان.
    - مصمم بمبدأ Dependency Injection.
    """

    def __init__(
        self,
        router: IntelligentRouter,
        policy_engine: PolicyEngine,
        cache_provider: CacheProviderProtocol,
        adapters: dict[str, ProtocolAdapter] | None = None,
    ) -> None:
        """
        تهيئة البوابة مع حقن التبعيات.

        Args:
            router: موجه الطلبات الذكي.
            policy_engine: محرك تطبيق السياسات.
            cache_provider: مزود التخزين المؤقت.
            adapters: محولات البروتوكولات (اختياري).
        """
        self.intelligent_router = router
        self.policy_engine = policy_engine
        self.cache = cache_provider

        self.protocol_adapters: dict[str, ProtocolAdapter] = adapters or {
            ProtocolType.REST.value: RESTAdapter(),
            ProtocolType.GRAPHQL.value: GraphQLAdapter(),
            ProtocolType.GRPC.value: GRPCAdapter(),
        }

        self.routes: dict[str, GatewayRoute] = {}
        self.upstream_services: dict[str, UpstreamService] = {}

        self._initialize_default_policies()

        logger.info("API Gateway Service initialized successfully with injected dependencies")

    def _initialize_default_policies(self) -> None:
        """تهيئة سياسات الأمان الافتراضية."""
        self.policy_engine.add_policy(
            PolicyRule(
                rule_id="require_auth",
                name="Require Authentication",
                condition="auth_required and not authenticated",
                action="deny",
                priority=100,
                enabled=True,
            )
        )

    def register_route(self, route: GatewayRoute) -> None:
        """تسجيل مسار جديد في البوابة."""
        self.routes[route.route_id] = route
        logger.info(f"Registered route: {route.route_id} -> {route.path_pattern}")

    def register_upstream_service(self, service: UpstreamService) -> None:
        """تسجيل خدمة خلفية جديدة."""
        self.upstream_services[service.service_id] = service
        logger.info(f"Registered upstream service: {service.service_id}")

    async def process_request(
        self,
        request: Request,
        protocol: ProtocolType = ProtocolType.REST,
        route_id: str | None = None,
    ) -> tuple[JSONDict, int]:
        """
        معالجة الطلب عبر البوابة (Process Request).

        تمر العملية بخمس مراحل:
        1. تكييف البروتوكول (Adaptation).
        2. تطبيق السياسات (Policy Enforcement).
        3. فحص التخزين المؤقت (Cache Check).
        4. التوجيه وتنفيذ الطلب (Routing & Execution).
        5. تحديث التخزين المؤقت (Cache Update).

        Returns:
            tuple[JSONDict, int]: بيانات الاستجابة ورمز الحالة.
        """
        start_time = time.time()

        try:
            # 1. تكييف البروتوكول والتحقق من الطلب
            adapter = self.protocol_adapters.get(protocol.value)
            request_data = await self._adapt_and_validate(adapter, request, protocol)

            # 2. تطبيق السياسات
            await self._enforce_policies(request)

            # 3. فحص التخزين المؤقت
            cache_key = generate_cache_key(request_data)
            cached_response = await self._check_cache(cache_key)
            if cached_response:
                return cached_response, 200

            # 4. التوجيه وتنفيذ الطلب (محاكاة)
            response_data = self._simulate_upstream_call(protocol, start_time)

            # 5. تحديث التخزين المؤقت
            await self._update_cache_if_needed(request.method, cache_key, response_data)

            return response_data, 200

        except ValueError as e:
            return {"error": str(e)}, 400
        except PermissionError as e:
            return {"error": str(e), "status": "forbidden"}, 403
        except Exception as e:
            logger.error(f"Gateway processing error: {e}", exc_info=True)
            return {"error": "Internal gateway error", "status": "error", "message": str(e)}, 500

    async def _adapt_and_validate(
        self, adapter: ProtocolAdapter | None, request: Request, protocol: ProtocolType
    ) -> JSON:
        if not adapter:
            raise ValueError(f"Unsupported protocol: {protocol.value}")

        is_valid, error_msg = await adapter.validate_request(request)
        if not is_valid:
            raise ValueError(error_msg or "Invalid request")

        return await adapter.transform_request(request)

    async def _enforce_policies(self, request: Request) -> None:
        request_context = self._build_request_context(request)
        allowed, deny_reason = self.policy_engine.evaluate(request_context)
        if not allowed:
            raise PermissionError(deny_reason)

    def _build_request_context(self, request: Request) -> dict[str, object]:
        """
        بناء سياق الطلب لتطبيق السياسات الأمنية.

        يهدف هذا التابع إلى تجميع حقول التحقق بشكل واضح
        للحفاظ على وضوح واجهة التقييم داخل محرك السياسات.
        """
        user_id = getattr(request.state, "user_id", None)
        return {
            "user_id": user_id,
            "endpoint": request.url.path,
            "method": request.method,
            "authenticated": user_id is not None,
        }

    async def _check_cache(self, cache_key: str) -> JSONDict | None:
        """استرجاع الاستجابة من التخزين المؤقت عند توفرها."""
        cached_response = await self.cache.get(cache_key)
        if isinstance(cached_response, dict):
            return self._mark_cache_hit(cached_response)
        return None

    def _simulate_upstream_call(self, protocol: ProtocolType, start_time: float) -> JSONDict:
        """محاكاة استدعاء الخدمة الخلفية لحين تفعيل الربط الحقيقي."""
        # في الإنتاج، هنا يتم استدعاء IntelligentRouter و UpstreamService
        return {
            "status": "success",
            "message": "Gateway processed request",
            "gateway_version": "1.0",
            "protocol": protocol.value,
            "processing_time_ms": (time.time() - start_time) * 1000,
            "cache_hit": False,
        }

    async def _update_cache_if_needed(self, method: str, key: str, data: JSONDict) -> None:
        """تحديث التخزين المؤقت للطلبات القابلة للتخزين فقط."""
        if method == "GET":
            await self.cache.put(key, data, ttl=300)

    def _mark_cache_hit(self, cached_response: JSONDict) -> JSONDict:
        """
        إضافة إشارة ضربة التخزين المؤقت مع الحفاظ على الكائن الأصلي.

        Args:
            cached_response: الاستجابة المخزنة.

        Returns:
            JSONDict: نسخة محدثة مع مؤشر cache_hit.
        """
        response_copy = cached_response.copy()
        response_copy["cache_hit"] = True
        return response_copy

    async def get_gateway_stats(self) -> JSONDict:
        """الحصول على إحصائيات شاملة للبوابة."""
        return {
            "routes_registered": len(self.routes),
            "upstream_services": len(self.upstream_services),
            "cache_stats": await self.cache.get_stats(),
            "policy_violations": len(self.policy_engine.get_violations(limit=100)),
            "protocols_supported": list(self.protocol_adapters.keys()),
        }


# ======================================================================================
# FACTORY & SINGLETON
# ======================================================================================


def create_default_gateway() -> APIGatewayService:
    """
    إنشاء مثيل افتراضي من البوابة (Factory Method).
    يقوم بتهيئة التبعيات الافتراضية وحقنها في البوابة.
    """
    router = IntelligentRouter()
    policy_engine = PolicyEngine()

    # تهيئة التخزين المؤقت باستخدام Factory
    cache_provider = CacheFactory.get_provider(provider_type="memory", max_size_items=1000, ttl=300)

    return APIGatewayService(
        router=router, policy_engine=policy_engine, cache_provider=cache_provider
    )


api_gateway_service = create_default_gateway()


# ======================================================================================
# DECORATOR FOR GATEWAY PROCESSING
# ======================================================================================


def gateway_process(
    protocol: ProtocolType = ProtocolType.REST, _cacheable: bool = False
) -> Callable:
    """
    مُزخرف (Decorator) لمعالجة الطلبات عبر البوابة.

    يضمن مرور الطلب عبر دورة حياة البوابة الكاملة (Validation, Policy, Caching)
    قبل الوصول إلى الدالة الأصلية.
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        async def decorated_function(request: Request, *args: object, **kwargs: object) -> object:
            gateway_response = await _process_gateway_request(request, protocol)
            if gateway_response:
                return gateway_response

            return await _execute_endpoint(f, request, *args, **kwargs)

        return decorated_function

    return decorator


async def _process_gateway_request(request: Request, protocol: ProtocolType) -> JSONResponse | None:
    """
    معالجة الطلب عبر خدمة البوابة.

    Returns:
        JSONResponse | None: استجابة خطأ إذا فشلت المعالجة، أو None للمتابعة.
    """
    gateway = api_gateway_service
    response_data, status_code = await gateway.process_request(request, protocol=protocol)

    if status_code != 200:
        return JSONResponse(content=response_data, status_code=status_code)
    return None


async def _execute_endpoint(
    f: Callable, request: Request, *args: object, **kwargs: object
) -> object:
    """تنفيذ الدالة الأصلية بشكل آمن."""
    try:
        return await f(request, *args, **kwargs)
    except Exception as e:
        logger.error(f"Endpoint error: {e}", exc_info=True)
        return JSONResponse(content={"error": "Internal error", "message": str(e)}, status_code=500)


def get_gateway_service() -> APIGatewayService:
    """الحصول على النسخة الوحيدة (Singleton) من خدمة البوابة."""
    return api_gateway_service
