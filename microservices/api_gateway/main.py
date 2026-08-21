import asyncio
import hashlib
import importlib
import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import uvicorn
from fastapi import Depends, FastAPI, Request, WebSocket
from fastapi.responses import Response, StreamingResponse

# Local imports
from microservices.api_gateway import prom_metrics
from microservices.api_gateway.config import settings
from microservices.api_gateway.middleware import (
    RequestIdMiddleware,
    StructuredLoggingMiddleware,
    TraceContextMiddleware,
)
from microservices.api_gateway.proxy import GatewayProxy
from microservices.api_gateway.security import create_service_token, verify_gateway_request
from microservices.api_gateway.websockets import websocket_proxy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api_gateway")

# Initialize the proxy handler
proxy_handler = GatewayProxy()
legacy_ws_sessions_total: dict[str, int] = {}

ALL_HTTP_METHODS = [
    "GET",
    "POST",
    "PUT",
    "DELETE",
    "PATCH",
    "OPTIONS",
    "HEAD",
]


def _record_ws_session_metric(route_id: str) -> None:
    """يسجل عداد جلسات WS الحديثة مع وسم route_id وlegacy_flag=false."""
    legacy_ws_sessions_total[route_id] = legacy_ws_sessions_total.get(route_id, 0) + 1
    logger.info(
        "legacy_ws_sessions_total=%s route_id=%s legacy_flag=false",
        legacy_ws_sessions_total[route_id],
        route_id,
    )


def _rollout_bucket(identity: str) -> int:
    """يولّد Bucket حتمي بين 0 و99 لدعم canary تدريجي آمن وقابل للإرجاع."""
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _should_route_to_conversation(identity: str, rollout_percent: int) -> bool:
    """يحدد قرار التوجيه التدريجي إلى Conversation Service وفق نسبة مئوية مضبوطة."""
    normalized = max(0, min(100, rollout_percent))
    if normalized == 0:
        return False
    if normalized == 100:
        return True
    return _rollout_bucket(identity) < normalized


def _to_ws_base_url(http_base_url: str) -> str:
    """يحوّل عنوان HTTP إلى WS بشكل صريح لتوحيد وجهة التوجيه بين HTTP وWebSocket."""
    parsed = urlparse(http_base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    netloc = parsed.netloc
    return f"{scheme}://{netloc}".rstrip("/")


def _extract_session_id(websocket: WebSocket) -> str | None:
    """Extracts the session_id from query parameters or headers for sticky routing."""
    query_session_id = websocket.query_params.get("session_id")
    if query_session_id and len(query_session_id) >= 8:
        logger.debug("session_id source=query")
        return query_session_id

    header_session_id = websocket.headers.get("x-session-id")
    if header_session_id and len(header_session_id) >= 8:
        logger.debug("session_id source=header")
        return header_session_id

    logger.debug("session_id source=absent")
    return None


def _emit_gateway_identity_log(route_name: str, websocket: WebSocket) -> None:
    """يسجل تشخيص الهوية في البوابة لربط session_id مع مسار WS ومضيف التنفيذ."""
    session_id = _extract_session_id(websocket)
    thread_id = websocket.query_params.get("thread_id") or websocket.headers.get("x-thread-id")
    conversation_id = websocket.query_params.get("conversation_id") or websocket.headers.get(
        "x-conversation-id"
    )
    hostname = os.getenv("HOSTNAME", "").strip() or "unknown"
    logger.info(
        "[GATEWAY_IDENTITY_DIAGNOSTIC] route=%s conversation_id=%s thread_id=%s session_id=%s "
        "hostname=%s",
        route_name,
        conversation_id or "missing",
        thread_id or "missing",
        session_id or "missing",
        hostname,
    )


def _build_routing_identity(route_id: str, upstream_path: str, session_id: str | None) -> str:
    """Builds a routing identity prioritizing session_id to maintain sticky routing."""
    if session_id:
        return f"session:{session_id}"
    return f"{route_id}:{upstream_path}:{uuid.uuid4().hex[:8]}"


def _resolve_chat_target_base(route_id: str, identity: str, rollout_percent: int) -> str:
    """يوحد قرار الوجهة بين HTTP وWS ويمنع التوجيه إلى Conversation قبل إثبات parity."""
    return settings.ORCHESTRATOR_SERVICE_URL.rstrip("/")


def _conversation_ws_base_url() -> str:
    """يحدد عنوان WS لخدمة Conversation مع fallback آمن نحو تحويل عنوان HTTP."""

    configured_ws_url = str(settings.CONVERSATION_WS_URL).strip()
    if configured_ws_url:
        return configured_ws_url.rstrip("/")

    return _to_ws_base_url(settings.CONVERSATION_SERVICE_URL.rstrip("/"))


def _resolve_chat_ws_target(route_id: str, upstream_path: str, websocket: WebSocket) -> str:
    """يحدد هدف WS الحديث باستخدام نفس محرك القرار الخاص بمسار HTTP."""
    session_id = _extract_session_id(websocket)
    identity = _build_routing_identity(route_id, upstream_path, session_id)

    target_base = _resolve_chat_target_base(
        route_id=route_id,
        identity=identity,
        rollout_percent=settings.ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT,
    )
    logger.info(
        "ws_routing session_id=%s bucket=%s",
        "present" if session_id else "absent",
        _rollout_bucket(identity),
    )
    normalized_conversation_base = settings.CONVERSATION_SERVICE_URL.rstrip("/")
    if target_base.rstrip("/") == normalized_conversation_base:
        ws_base = _conversation_ws_base_url()
    else:
        ws_base = _to_ws_base_url(target_base)

    target_url = f"{ws_base}/{upstream_path}"
    if websocket.url.query:
        target_url = f"{target_url}?{websocket.url.query}"
    return target_url


def _chat_route_uses_conversation() -> bool:
    """يحدد ما إذا كانت مسارات chat الإنتاجية قد تُوجَّه فعليًا نحو conversation-service."""

    return (
        settings.ROUTE_CHAT_HTTP_CONVERSATION_ROLLOUT_PERCENT > 0
        or settings.ROUTE_CHAT_WS_CONVERSATION_ROLLOUT_PERCENT > 0
    )


def _health_dependency_targets() -> dict[str, str]:
    """يبني قائمة التبعيات الصحية مع مراعاة الخدمة الفعلية لمسارات chat."""

    services = {
        "planning_agent": settings.PLANNING_AGENT_URL,
        "memory_agent": settings.MEMORY_AGENT_URL,
        "user_service": settings.USER_SERVICE_URL,
        "observability_service": settings.OBSERVABILITY_SERVICE_URL,
        "research_agent": settings.RESEARCH_AGENT_URL,
        "reasoning_agent": settings.REASONING_AGENT_URL,
        "orchestrator_service": settings.ORCHESTRATOR_SERVICE_URL,
    }

    if _chat_route_uses_conversation():
        services["conversation_service"] = settings.CONVERSATION_SERVICE_URL

    return services


class _NoOpSpan:
    """يمثل Span افتراضيًا لا ينفذ أي تتبع عند غياب حزمة OpenTelemetry."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _NoOpTracer:
    """يوفّر واجهة تتبع بديلة تضمن استمرار عمل البوابة دون تبعيات اختيارية."""

    def start_as_current_span(self, _name: str, attributes: dict[str, str] | None = None):
        _ = attributes
        return _NoOpSpan()


def _build_tracer() -> object:
    """ينشئ كائن التتبع الحقيقي إذا توفر OpenTelemetry وإلا يعيد بديلًا آمنًا."""
    if importlib.util.find_spec("opentelemetry"):
        import opentelemetry.trace

        return opentelemetry.trace.get_tracer(__name__)
    return _NoOpTracer()


def _inject_trace_context(headers: dict[str, str]) -> None:
    """يحقن سياق التتبع داخل الترويسات عند توفر وحدة propagate."""
    try:
        propagate_spec = importlib.util.find_spec("opentelemetry.propagate")
    except ModuleNotFoundError:
        return

    if propagate_spec is None:
        return

    propagate_module = importlib.import_module("opentelemetry.propagate")
    propagate_module.inject(headers)


tracer = _build_tracer()


def log_telemetry(event_name: str, trace_id: str) -> None:
    """يسجل حدث قياس عن بعد بتشخيص الحدث ومعرف التتبع."""
    logger.info("TELEMETRY: %s [trace_id: %s]", event_name, trace_id)


def _should_probe_startup_dependencies() -> bool:
    """يحدد ما إذا كان يجب تنفيذ فحص جاهزية الخدمات عند إقلاع البوابة."""

    environment = settings.ENVIRONMENT.lower().strip()
    if environment in {"testing", "test"}:
        return False

    if os.getenv("PYTEST_CURRENT_TEST"):
        return False

    return os.getenv("SKIP_GATEWAY_STARTUP_PROBE") != "1"


async def _probe_startup_dependencies() -> None:
    """يفحص جاهزية orchestrator-service عند الإقلاع بتراجع أسي حتى ثلاث محاولات."""
    orchestrator_url = settings.ORCHESTRATOR_SERVICE_URL
    if not orchestrator_url:
        raise RuntimeError("ORCHESTRATOR_SERVICE_URL is missing")

    for attempt in range(3):
        try:
            # Short timeout for health checks
            resp = await proxy_handler.client.get(f"{orchestrator_url}/health", timeout=2.0)
            if resp.status_code == 200:
                log_telemetry("gateway.ready", trace_id=str(uuid.uuid4()))
                return
        except Exception:
            pass
        if attempt == 2:
            raise RuntimeError("orchestrator-service is down")
        await asyncio.sleep(2**attempt)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    _ = app
    logger.info("Starting API Gateway...")
    try:
        if _should_probe_startup_dependencies():
            await _probe_startup_dependencies()
        else:
            logger.info("Skipping startup dependency probe in testing/override mode.")

        yield
    finally:
        logger.info("Shutting down API Gateway...")
        await proxy_handler.close()


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

# Add Middleware
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(TraceContextMiddleware)
prom_metrics.set_startup_info(environment=os.getenv("ENVIRONMENT", "development"))


# --- Shared health check logic ---


async def _check_service_health(name: str, url: str) -> tuple[str, str]:
    """يفحص صحة خدمة downstream واحدة ويعيد (اسم_الخدمة، الحالة)."""
    try:
        # Short timeout for health checks
        resp = await proxy_handler.client.get(f"{url}/health", timeout=2.0)
        status = "UP" if resp.status_code == 200 else f"DOWN ({resp.status_code})"
        return name, status
    except Exception as exc:
        return name, f"DOWN ({exc!s})"


# --- WebSocket Routes MUST BE FIRST to avoid being shadowed by wildcard API routes ---


async def _handle_chat_ws(
    websocket: WebSocket, route_id: str, upstream_path: str, error_message: str
) -> None:
    """ينفّذ منطق وكيل دردشة WS المشترك (تتبع · هوية · توجيه · معالجة الأخطاء)."""
    from starlette.websockets import WebSocketState

    with tracer.start_as_current_span("ws.proxy", attributes={"agent": "orchestrator"}):
        headers: dict[str, str] = {}
        _inject_trace_context(headers)
        logger.info(
            "Chat WebSocket route_id=%s legacy_flag=false traceparent=%s",
            route_id,
            headers.get("traceparent", "unknown"),
        )
        _emit_gateway_identity_log(f"gateway_ws_{route_id.rsplit('_', maxsplit=1)[-1]}", websocket)
        session_id = _extract_session_id(websocket)
        logger.info(
            "session_id presence: %s in %s",
            "present" if session_id else "absent",
            route_id,
        )

        _record_ws_session_metric(route_id)
        target_url = _resolve_chat_ws_target(route_id, upstream_path, websocket)
        try:
            await websocket_proxy(websocket, target_url)
        except Exception:
            log_telemetry("ws.proxy.failed", trace_id=str(uuid.uuid4()))
            if websocket.client_state == WebSocketState.UNCONNECTED:
                await websocket.accept()
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({"error": error_message, "request_id": str(uuid.uuid4())})
                await websocket.close()


@app.websocket("/api/chat/ws")
async def chat_ws_proxy(websocket: WebSocket) -> None:
    """
    Customer Chat WebSocket (Modern Target).
    TARGET: Orchestrator Service / Conversation Service
    """
    await _handle_chat_ws(
        websocket, "chat_ws_customer", "api/chat/ws", "تعذر فتح جلسة الدردشة حالياً."
    )


@app.websocket("/admin/api/chat/ws")
async def admin_chat_ws_proxy(websocket: WebSocket) -> None:
    """
    Admin Chat WebSocket (Modern Target).
    TARGET: Orchestrator Service / Conversation Service
    """
    await _handle_chat_ws(
        websocket,
        "chat_ws_admin",
        "admin/api/chat/ws",
        "تعذر فتح جلسة الدردشة الإدارية حالياً.",
    )


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus scrape endpoint (cogniforge_gateway_*). Hidden from OpenAPI."""
    content, content_type = prom_metrics.export_prometheus_text()
    return Response(content=content, media_type=content_type)


@app.get("/health")
async def health_check() -> dict[str, object]:
    """
    Health check endpoint that verifies connectivity to downstream services.
    Returns a detailed status report.
    """
    services = _health_dependency_targets()

    # Run checks concurrently
    results = await asyncio.gather(
        *(_check_service_health(name, url) for name, url in services.items())
    )
    dependencies = dict(results)

    # Determine overall status
    overall_status = "ok"
    if any(str(status).startswith("DOWN") for status in dependencies.values()):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "service": "api-gateway",
        "dependencies": dependencies,
        "chat_route_mode": "conversation" if _chat_route_uses_conversation() else "orchestrator",
    }


@app.get("/gateway/health")
async def gateway_health_check() -> dict[str, object]:
    """
    Alias for /health.
    Matches legacy documentation expectations.
    """
    return await health_check()


# --- Declarative HTTP route registry (Data as Code — SICP abstraction barrier) ---


class _HttpRoute:
    """وصف تصريحي لمسار وكيل HTTP واحد في البوابة."""

    def __init__(
        self,
        path: str,
        target: str,
        rewrite: str | None = None,
        methods: list[str] | None = None,
        name: str = "",
        include_in_schema: bool = True,
        deprecated: bool = False,
        auth: bool = True,
        log: str | None = None,
    ):
        self.path = path
        self.target = target
        self.rewrite = rewrite
        self.methods = methods or ALL_HTTP_METHODS
        self.name = name
        self.include_in_schema = include_in_schema
        self.deprecated = deprecated
        self.auth = auth
        self.log = log


# Registry: each entry is data, interpreted by `_build_proxy_handler` below.
# Never hard-code a route handler — add a row here instead.
HTTP_ROUTES: list[_HttpRoute] = [
    _HttpRoute(
        "/api/v1/planning/{path:path}",
        target=settings.PLANNING_AGENT_URL,
        name="planning_proxy",
    ),
    _HttpRoute(
        "/api/v1/memory/{path:path}",
        target=settings.MEMORY_AGENT_URL,
        name="memory_proxy",
    ),
    _HttpRoute(
        "/api/v1/users/{path:path}",
        target=settings.USER_SERVICE_URL,
        name="user_proxy",
    ),
    _HttpRoute(
        "/api/v1/auth/{path:path}",
        target=settings.USER_SERVICE_URL,
        rewrite="api/v1/auth/{path}",
        name="auth_proxy",
    ),
    _HttpRoute(
        "/api/v1/observability/{path:path}",
        target=settings.OBSERVABILITY_SERVICE_URL,
        name="observability_proxy",
    ),
    _HttpRoute(
        "/api/v1/research/{path:path}",
        target=settings.RESEARCH_AGENT_URL,
        name="research_proxy",
    ),
    _HttpRoute(
        "/api/v1/reasoning/{path:path}",
        target=settings.REASONING_AGENT_URL,
        name="reasoning_proxy",
    ),
    _HttpRoute(
        "/api/v1/overmind/{path:path}",
        target=settings.ORCHESTRATOR_SERVICE_URL,
        name="orchestrator_proxy",
    ),
    _HttpRoute(
        "/api/v1/missions",
        target=settings.ORCHESTRATOR_SERVICE_URL,
        rewrite="missions",
        name="missions_root_proxy",
    ),
    _HttpRoute(
        "/api/v1/missions/{path:path}",
        target=settings.ORCHESTRATOR_SERVICE_URL,
        rewrite="missions/{path}",
        name="missions_path_proxy",
    ),
    # --- COMPATIBILITY ROUTES (MICROSERVICES TARGETS) ---
    _HttpRoute(
        "/admin/ai-config",
        target=settings.USER_SERVICE_URL,
        rewrite="api/v1/admin/ai-config",
        methods=["GET", "PUT", "OPTIONS", "HEAD"],
        name="admin_ai_config_proxy",
        include_in_schema=False,
        deprecated=True,
        auth=False,
        log="Route accessed: /admin/ai-config -> user-service",
    ),
    _HttpRoute(
        "/admin/api/conversations",
        target=settings.ORCHESTRATOR_SERVICE_URL,
        rewrite="admin/api/conversations",
        methods=["GET", "OPTIONS", "HEAD"],
        name="admin_conversations_proxy",
        include_in_schema=False,
        auth=False,
    ),
    _HttpRoute(
        "/admin/api/conversations/{conversation_id}",
        target=settings.ORCHESTRATOR_SERVICE_URL,
        rewrite="admin/api/conversations/{conversation_id}",
        methods=["GET", "OPTIONS", "HEAD"],
        name="admin_conversation_details_proxy",
        include_in_schema=False,
        auth=False,
    ),
    _HttpRoute(
        "/admin/{path:path}",
        target=settings.USER_SERVICE_URL,
        rewrite="api/v1/admin/{path}",
        name="admin_proxy",
        include_in_schema=False,
        auth=False,
    ),
    _HttpRoute(
        "/api/security/{path:path}",
        target=settings.USER_SERVICE_URL,
        rewrite="api/v1/auth/{path}",
        name="security_proxy",
        include_in_schema=False,
        auth=False,
        log="Proxy Security routes to User Service (Auth). Rewrite: /api/security/{path} -> /api/v1/auth/{path}",
    ),
    _HttpRoute(
        "/api/chat/{path:path}",
        target=settings,
        rewrite="api/chat/{path}",
        name="chat_http_proxy",
        include_in_schema=False,
        deprecated=True,
        auth=False,
        log="Route accessed: /api/chat/%s (modern routing)",
    ),
    _HttpRoute(
        "/v1/content/{path:path}",
        target=settings.RESEARCH_AGENT_URL,
        rewrite="v1/content/{path}",
        name="content_proxy",
        include_in_schema=False,
        deprecated=True,
        auth=False,
        log="Route accessed: /v1/content/%s -> research-agent",
    ),
    _HttpRoute(
        "/api/v1/data-mesh/{path:path}",
        target=settings.OBSERVABILITY_SERVICE_URL,
        rewrite="api/v1/data-mesh/{path}",
        name="datamesh_proxy",
        include_in_schema=False,
        deprecated=True,
        auth=False,
        log="Route accessed: /api/v1/data-mesh/%s -> observability-service",
    ),
    _HttpRoute(
        "/system/{path:path}",
        target=settings.ORCHESTRATOR_SERVICE_URL,
        rewrite="system/{path}",
        name="system_proxy",
        include_in_schema=False,
        deprecated=True,
        auth=False,
        log="Route accessed: /system/%s -> orchestrator-service",
    ),
]


def _resolve_chat_target(path: str, request: Request) -> str:
    """يحدد وجهة مسار chat الحديث وفق محرك القرار المشترك مع WS."""
    identity = request.headers.get("x-request-id", request.url.path)
    target_base = _resolve_chat_target_base(
        route_id="chat_http",
        identity=identity,
        rollout_percent=settings.ROUTE_CHAT_HTTP_CONVERSATION_ROLLOUT_PERCENT,
    )
    return f"{target_base}/{path}"


def _build_proxy_handler(route: _HttpRoute):
    """يولّد معالج وكيل HTTP بمسار ديناميكي من وصف تصريحي دون تكرار منطق proxy_handler.forward."""

    async def proxy_handler_endpoint(path: str, request: Request) -> StreamingResponse:
        return await _forward_for_route(route, path, request)

    proxy_handler_endpoint.__name__ = route.name or "proxy_handler_endpoint"
    return proxy_handler_endpoint


async def _forward_for_route(
    route: _HttpRoute, path: str | None, request: Request | None
) -> StreamingResponse:
    """يعيد توجيه طلب HTTP إلى الوجهة المحددة في السجل مع إعادة كتابة المسار عند الحاجة."""
    if route.log is not None and request is not None:
        logger.info(route.log, path)

    if route.target is settings:
        # Chat modern target: target resolved at request time (canary rollout).
        target = _resolve_chat_target_base(
            route_id="chat_http",
            identity=request.headers.get("x-request-id", request.url.path),
            rollout_percent=settings.ROUTE_CHAT_HTTP_CONVERSATION_ROLLOUT_PERCENT,
        )
        rewritten = f"api/chat/{path}" if path else "api/chat"
        return await proxy_handler.forward(
            request, target, rewritten, service_token=create_service_token()
        )

    if route.rewrite is None:
        rewritten = path or ""
    else:
        rewritten = route.rewrite.format(path=path) if path else route.rewrite

    return await proxy_handler.forward(
        request,
        route.target,
        rewritten,
        service_token=create_service_token(),
    )


def _register_http_routes(application: FastAPI) -> None:
    """يسجل كل مسارات وكيل HTTP التصريحية على التطبيق وفق الترتيب في السجل."""
    for route in HTTP_ROUTES:
        kwargs: dict[str, Any] = {
            "methods": route.methods,
            "name": route.name,
        }
        if not route.include_in_schema:
            kwargs["include_in_schema"] = False
        if route.deprecated:
            kwargs["deprecated"] = True
        if route.auth:
            kwargs["dependencies"] = [Depends(verify_gateway_request)]

        path = route.path
        has_path_param = "{path:path}" in path

        if has_path_param:
            handler = _build_proxy_handler(route)
            application.api_route(path, **kwargs)(handler)
        else:
            # Root-path routes (e.g. /api/v1/missions, /admin/api/conversations).

            def _make_root_handler(current_route: _HttpRoute):
                async def _root_proxy(request: Request) -> StreamingResponse:
                    return await _forward_for_route(current_route, None, request)

                _root_proxy.__name__ = current_route.name
                return _root_proxy

            root_handler = _make_root_handler(route)
            application.api_route(path, **kwargs)(root_handler)


_register_http_routes(app)


if __name__ == "__main__":
    uvicorn.run("microservices.api_gateway.main:app", host="0.0.0.0", port=8000, reload=True)
