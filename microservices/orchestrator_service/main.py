import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure models are registered with SQLModel
import microservices.orchestrator_service.src.models.mission  # noqa: F401
from microservices.orchestrator_service.src.api import routes
from microservices.orchestrator_service.src.core.config import settings
from microservices.orchestrator_service.src.core.database import (
    async_session_factory,
    close_db,
    get_checkpointer,
    init_db,
)
from microservices.orchestrator_service.src.core.event_bus import event_bus
from microservices.orchestrator_service.src.services.overmind.state import MissionStateManager
from microservices.orchestrator_service.src.services.tools.registry import register_all_tools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator_service")

# MemorySaver singleton — يُنشأ مرة واحدة على مستوى الـ module لضمان استمرارية الذاكرة
# بين الطلبات عند غياب Postgres checkpointer. لا تُنشئ instance جديداً داخل lifespan.
try:
    from langgraph.checkpoint.memory import MemorySaver as _MemorySaver

    _memory_saver: _MemorySaver | None = _MemorySaver()
except ModuleNotFoundError:
    _memory_saver = None


async def _run_outbox_relay_once() -> dict[str, int]:
    """ينفذ دورة relay واحدة لسجلات Outbox مع عزل جلسة قاعدة البيانات."""

    async with async_session_factory() as session:
        manager = MissionStateManager(session=session)
        return await manager.relay_outbox_events(
            batch_size=settings.OUTBOX_RELAY_BATCH_SIZE,
            max_failed_attempts=settings.OUTBOX_RELAY_MAX_FAILED_ATTEMPTS,
            processing_timeout_seconds=settings.OUTBOX_RELAY_PROCESSING_TIMEOUT_SECONDS,
        )


async def _outbox_relay_loop(stop_event: asyncio.Event) -> None:
    """حلقة relay دورية قابلة للإيقاف الآمن أثناء shutdown."""

    interval_seconds = max(1, int(settings.OUTBOX_RELAY_INTERVAL_SECONDS))
    while not stop_event.is_set():
        try:
            summary = await _run_outbox_relay_once()
            if summary["processed"] > 0:
                logger.info("outbox_relay_cycle summary=%s", summary)
        except Exception as exc:  # pragma: no cover - دفاعي تشغيلي
            logger.error("outbox_relay_cycle_failed: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """يدير دورة حياة الخدمة مع ضمان الإقلاع حتى عند غياب تبعيات اختيارية.

    مراحل الإقلاع (لا تُوقف الخدمة إلا عند فشل قاعدة البيانات):
      PHASE 1 — DB init          : حرج — يوقف الخدمة عند الفشل
      PHASE 2 — Tools registry   : حرج — يوقف الخدمة عند الفشل
      PHASE 3 — Graph compile    : غير حرج — يُسجَّل كـ DEGRADED ولا يوقف الخدمة
      PHASE 4 — Warmup probe     : غير حرج — timeout 30s، يُسجَّل كـ DEGRADED
      PHASE 5 — Outbox relay     : غير حرج — يُطلق في الخلفية

    حالة الجاهزية (app.state.startup_state):
      "ready"    — كل المراحل نجحت
      "degraded" — الخدمة تعمل لكن Graph أو Warmup فشلا
      "db_error" — لا يُصل إليها (الخدمة لا تبدأ)
    """
    logger.info("Orchestrator Service Starting...")

    # ═══ PHASE 1: DB INIT — CRITICAL ═══════════════════════════
    # فشل قاعدة البيانات يوقف الخدمة — لا يمكن العمل بدونها
    await init_db()

    # ═══ PHASE 2: TOOLS REGISTRY — CRITICAL ════════════════════
    from microservices.orchestrator_service.src.services.tools.registry import get_registry

    register_all_tools()

    tool_registry = get_registry()
    required = [
        "admin.count_python_files",
        "admin.count_database_tables",
        "admin.get_user_count",
        "admin.list_microservices",
        "admin.calculate_full_stats",
    ]
    missing = [t for t in required if not tool_registry.get(t)]
    if missing:
        raise RuntimeError(f"STARTUP BLOCKED — missing tools: {missing}")

    # تهيئة حالة التطبيق — يُعدَّل في المراحل اللاحقة
    app.state.admin_app = None
    app.state.app_graph = None
    app.state.startup_state = "degraded"  # يُرفع إلى "ready" عند نجاح الـ warmup
    app.state.startup_errors: list[str] = []
    app.state.outbox_relay_stop_event = asyncio.Event()
    app.state.outbox_relay_task = None

    # ═══ PHASE 3: GRAPH COMPILE — NON-CRITICAL ═════════════════
    # فشل التجميع لا يوقف الخدمة — /health يُبلِّغ عن DEGRADED
    try:
        from microservices.orchestrator_service.src.services.overmind.graph.admin import admin_graph
        from microservices.orchestrator_service.src.services.overmind.graph.main import (
            create_unified_graph,
        )

        # يستخدم Postgres checkpointer إذا كان متاحاً، وإلا يعود إلى MemorySaver singleton
        # (لا تُنشئ MemorySaver جديداً هنا — يجب أن يكون نفس الـ instance طوال عمر العملية)
        active_checkpointer = get_checkpointer() or _memory_saver
        app.state.admin_app = admin_graph.compile(
            checkpointer=active_checkpointer, interrupt_before=[]
        )
        app.state.app_graph = create_unified_graph(
            admin_app=app.state.admin_app, checkpointer=active_checkpointer
        )
        logger.info("✅ Graph compiled successfully")

    except ModuleNotFoundError as error:
        msg = f"Graph bootstrap skipped — missing dependency: {error}"
        logger.warning(msg)
        app.state.startup_errors.append(msg)
    except Exception as error:  # pragma: no cover — دفاعي تشغيلي
        msg = f"Graph compile failed (non-fatal): {error}"
        logger.error(msg)
        app.state.startup_errors.append(msg)

    # ═══ PHASE 4: WARMUP PROBE — NON-CRITICAL, TIMEOUT-GUARDED ═
    # الـ warmup يثبت أن الـ graph يستدعي الأدوات فعلاً.
    # timeout=30s يمنع الإقلاع من الانتظار إلى الأبد عند بطء الشبكة أو LLM.
    if app.state.admin_app is not None:
        try:
            result = await asyncio.wait_for(
                app.state.admin_app.ainvoke(
                    {"query": "كم عدد ملفات بايثون", "is_admin_user": True},
                    config={"configurable": {"thread_id": "warmup"}},
                ),
                timeout=30.0,
            )
            final_res = result.get("final_response", {})
            if final_res.get("tool_name"):
                app.state.startup_state = "ready"
                logger.info("✅ SYSTEM READY | warmup tool=%s", final_res["tool_name"])
            else:
                msg = "Warmup completed but graph did not invoke a tool — check ExecuteToolNode"
                logger.warning(msg)
                app.state.startup_errors.append(msg)
        except TimeoutError:
            msg = "Warmup timed out after 30s — graph is DEGRADED (LLM/network slow?)"
            logger.warning(msg)
            app.state.startup_errors.append(msg)
        except Exception as error:  # pragma: no cover — دفاعي تشغيلي
            msg = f"Warmup probe failed (non-fatal): {error}"
            logger.error(msg)
            app.state.startup_errors.append(msg)
    else:
        app.state.startup_errors.append("Warmup skipped — graph not compiled")

    if app.state.startup_state == "degraded":
        logger.warning(
            "⚠️  Orchestrator started in DEGRADED mode. Errors: %s",
            app.state.startup_errors,
        )
    else:
        logger.info("✅ Orchestrator fully operational")

    # ═══ PHASE 5: OUTBOX RELAY — NON-CRITICAL BACKGROUND TASK ══
    if settings.OUTBOX_RELAY_ENABLED:
        app.state.outbox_relay_task = asyncio.create_task(
            _outbox_relay_loop(app.state.outbox_relay_stop_event)
        )
        logger.info("✅ Outbox relay loop started")

    yield

    # ═══ SHUTDOWN ═══════════════════════════════════════════════
    relay_task = app.state.outbox_relay_task
    if relay_task is not None:
        app.state.outbox_relay_stop_event.set()
        relay_task.cancel()
        with suppress(asyncio.CancelledError):
            await relay_task

    from microservices.orchestrator_service.src.api.routes import close_conv_service_client

    await close_conv_service_client()
    await event_bus.close()
    await close_db()
    tool_registry.clear()
    if hasattr(app.state, "admin_app"):
        del app.state.admin_app
    if hasattr(app.state, "app_graph"):
        del app.state.app_graph


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)


@app.get("/health")
async def health_check():
    """فحص صحة الخدمة مع الكشف عن حالة الإقلاع الفعلية.

    يُميِّز بين ثلاث حالات:
      ok       — الخدمة جاهزة بالكامل (graph + warmup نجحا)
      degraded — الخدمة تعمل لكن graph أو warmup فشلا
      starting — الخدمة لا تزال في مرحلة الإقلاع
    """
    startup_state = getattr(app.state, "startup_state", "starting")
    errors = getattr(app.state, "startup_errors", [])
    graph_ready = getattr(app.state, "app_graph", None) is not None

    return {
        "status": "ok" if startup_state == "ready" else startup_state,
        "service": "orchestrator-service",
        "graph_ready": graph_ready,
        "startup_state": startup_state,
        **({"startup_errors": errors} if errors else {}),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "microservices.orchestrator_service.main:app", host="0.0.0.0", port=8000, reload=True
    )
