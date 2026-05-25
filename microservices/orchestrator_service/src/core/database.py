"""
طبقة قاعدة البيانات لـ orchestrator-service.

تُدير هذه الوحدة:
  1. AsyncEngine (SQLAlchemy + asyncpg) — للـ ORM والـ migrations
  2. AsyncPostgresSaver (LangGraph) — checkpointer دائم للـ StateGraph [Step 10]
  3. مقاييس Prometheus لكل عملية checkpointer

قواعد ISS-040 (PgBouncer):
  - SQLAlchemy engine: يستخدم statement_cache_size=0 لتوافق PgBouncer
  - AsyncPostgresSaver: يستخدم psycopg مباشرةً — يحتاج postgresql:// لا postgresql+asyncpg://
  - كلاهما يستخدم port 5432 (direct PG) لا 6543 (PgBouncer transaction mode)

قاعدة ISS-038-B (asyncpg URL):
  - create_async_engine يحتاج postgresql+asyncpg://
  - AsyncConnectionPool يحتاج postgresql:// (psycopg)
"""

from __future__ import annotations

import logging
import ssl
import time
from collections.abc import AsyncGenerator

from psycopg_pool import AsyncConnectionPool
from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from microservices.orchestrator_service.src.core.config import settings
from microservices.orchestrator_service.src.models.mission import OrchestratorSQLModel

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ModuleNotFoundError:
    AsyncPostgresSaver = None  # type: ignore[assignment,misc]


# ── مقاييس Prometheus — استيراد دفاعي ────────────────────────────────────────
try:
    from microservices.orchestrator_service.src.core.prom_metrics import (
        record_checkpointer_error,
        record_checkpointer_read,
        record_checkpointer_write,
        set_checkpointer_active_threads,
        set_checkpointer_backend_info,
    )

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False

    def record_checkpointer_write(*_: object, **__: object) -> None: ...
    def record_checkpointer_read(*_: object, **__: object) -> None: ...
    def record_checkpointer_error(*_: object, **__: object) -> None: ...
    def set_checkpointer_active_threads(*_: object, **__: object) -> None: ...
    def set_checkpointer_backend_info(*_: object, **__: object) -> None: ...


# ── Checkpointer wrapper مع مقاييس Prometheus ────────────────────────────────
# يرث من AsyncPostgresSaver مباشرةً لأن LangGraph يتحقق من isinstance(BaseCheckpointSaver).
# نُنشئ الـ class بشكل مشروط لتجنب NameError عند غياب langgraph-checkpoint-postgres.


def _make_instrumented_class(base_class: type) -> type:
    """
    يُنشئ _InstrumentedCheckpointer كـ subclass من base_class (AsyncPostgresSaver).

    هذا النهج يضمن أن LangGraph يقبل الـ checkpointer (isinstance check)
    بينما نُضيف مقاييس Prometheus على كل عملية.

    مبدأ "Instrumentation before visualization": كل عملية checkpoint
    مرئية في Grafana قبل أي dashboard.
    """

    class _InstrumentedCheckpointer(base_class):  # type: ignore[valid-type]
        """
        AsyncPostgresSaver مُعزَّز بمقاييس Prometheus.

        يرث كل سلوك AsyncPostgresSaver ويُضيف تسجيل Prometheus
        على aput / aget / aget_tuple / setup.
        """

        def __init__(self, pool: object) -> None:
            super().__init__(pool)  # type: ignore[arg-type]
            # مجموعة thread_ids النشطة — تُستخدم لـ cogniforge_checkpointer_active_threads
            self._active_threads: set[str] = set()

        async def aput(  # type: ignore[override]
            self,
            config: dict[str, object],
            checkpoint: object,
            metadata: object,
            new_versions: object,
        ) -> object:
            """يكتب checkpoint مع تسجيل Prometheus."""
            thread_id: str = (
                config.get("configurable", {}).get("thread_id", "unknown")  # type: ignore[union-attr]
                if isinstance(config.get("configurable"), dict)
                else "unknown"
            )
            prefix = thread_id.split(":", maxsplit=1)[0] if ":" in thread_id else thread_id[:8]
            t0 = time.monotonic()
            try:
                result = await super().aput(config, checkpoint, metadata, new_versions)
                duration = time.monotonic() - t0
                record_checkpointer_write(prefix, "success", duration)
                self._active_threads.add(thread_id)
                set_checkpointer_active_threads(len(self._active_threads))
                return result
            except Exception as exc:
                duration = time.monotonic() - t0
                record_checkpointer_write(prefix, "error", duration)
                error_type = type(exc).__name__.lower()
                if "connection" in error_type or "pool" in error_type:
                    record_checkpointer_error("connection_error")
                elif "serial" in error_type or "json" in error_type:
                    record_checkpointer_error("serialization_error")
                elif "timeout" in error_type:
                    record_checkpointer_error("timeout")
                else:
                    record_checkpointer_error("unknown")
                raise

        async def aget(self, config: dict[str, object]) -> object:  # type: ignore[override]
            """يقرأ checkpoint مع تسجيل Prometheus."""
            thread_id: str = (
                config.get("configurable", {}).get("thread_id", "unknown")  # type: ignore[union-attr]
                if isinstance(config.get("configurable"), dict)
                else "unknown"
            )
            prefix = thread_id.split(":", maxsplit=1)[0] if ":" in thread_id else thread_id[:8]
            t0 = time.monotonic()
            try:
                result = await super().aget(config)
                duration = time.monotonic() - t0
                status = "hit" if result is not None else "miss"
                record_checkpointer_read(prefix, status, duration)
                return result
            except Exception as exc:
                duration = time.monotonic() - t0
                record_checkpointer_read(prefix, "error", duration)
                error_type = type(exc).__name__.lower()
                record_checkpointer_error(
                    "connection_error" if "connection" in error_type else "unknown"
                )
                raise

        async def aget_tuple(self, config: dict[str, object]) -> object:  # type: ignore[override]
            """يقرأ checkpoint tuple مع تسجيل Prometheus."""
            thread_id: str = (
                config.get("configurable", {}).get("thread_id", "unknown")  # type: ignore[union-attr]
                if isinstance(config.get("configurable"), dict)
                else "unknown"
            )
            prefix = thread_id.split(":", maxsplit=1)[0] if ":" in thread_id else thread_id[:8]
            t0 = time.monotonic()
            try:
                result = await super().aget_tuple(config)
                duration = time.monotonic() - t0
                status = "hit" if result is not None else "miss"
                record_checkpointer_read(prefix, status, duration)
                return result
            except Exception:
                duration = time.monotonic() - t0
                record_checkpointer_read(prefix, "error", duration)
                record_checkpointer_error("unknown")
                raise

        async def setup(self) -> None:
            """يُهيِّئ جداول checkpoint مع تسجيل Prometheus."""
            t0 = time.monotonic()
            try:
                await super().setup()
                duration = time.monotonic() - t0
                logger.info("[CHECKPOINTER] setup() completed in %.3fs", duration)
            except Exception:
                record_checkpointer_error("setup_error")
                raise

    return _InstrumentedCheckpointer


# نُنشئ الـ class فقط إذا كان AsyncPostgresSaver متاحاً
if AsyncPostgresSaver is not None:
    _InstrumentedCheckpointer = _make_instrumented_class(AsyncPostgresSaver)
else:
    # Stub بسيط عند غياب langgraph-checkpoint-postgres
    class _InstrumentedCheckpointer:  # type: ignore[no-redef]
        def __init__(self, pool: object) -> None:
            self._active_threads: set[str] = set()


# ── SQLAlchemy Engine ─────────────────────────────────────────────────────────


def create_engine() -> AsyncEngine:
    """
    يُنشئ AsyncEngine مع دعم كامل لـ Supabase PgBouncer (transaction mode).

    PgBouncer في وضع transaction لا يدعم prepared statements.
    الحل: statement_cache_size=0 في connect_args.
    """
    db_url = settings.DATABASE_URL
    url_obj = make_url(db_url)

    qs = dict(url_obj.query)
    ssl_mode = qs.pop("sslmode", None) or qs.pop("ssl", None)

    connect_kwargs: dict[str, object] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }

    if ssl_mode in ("require", "verify-ca", "verify-full"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_kwargs["ssl"] = ctx

    clean_url = url_obj.set(query=qs).render_as_string(hide_password=False)

    return create_async_engine(
        clean_url,
        echo=False,
        future=True,
        connect_args=connect_kwargs,
    )


# Singleton: lazy-initialised on first get_engine() call to avoid import-time
# connection errors when ORCHESTRATOR_DATABASE_URL is not yet in the environment.
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """يُعيد AsyncEngine مُهيَّأً بشكل كسول (lazy singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


# backward-compat alias
engine = None  # type: ignore[assignment]

_session_factory: async_sessionmaker | None = None  # type: ignore[type-arg]


def _get_session_factory() -> async_sessionmaker:  # type: ignore[type-arg]
    """يُعيد async_sessionmaker مُهيَّأً بشكل كسول."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


class _LazySessionFactory:
    """Proxy يُحيل الاستدعاء إلى _get_session_factory() عند أول استخدام."""

    def __call__(self, *args: object, **kwargs: object) -> AsyncSession:
        return _get_session_factory()(*args, **kwargs)  # type: ignore[return-value]

    def __getattr__(self, name: str) -> object:
        return getattr(_get_session_factory(), name)


async_session_factory = _LazySessionFactory()

# ── Postgres Checkpointer (Step 10) ──────────────────────────────────────────

_postgres_pool: AsyncConnectionPool | None = None
postgres_checkpointer: _InstrumentedCheckpointer | None = None

# عدد connections في pool — يُستخدم في مقاييس Prometheus
_POOL_SIZE: int = 5


def get_checkpointer() -> _InstrumentedCheckpointer | None:
    """يُعيد الـ checkpointer المُهيَّأ أو None إذا لم يكن متاحاً."""
    return postgres_checkpointer


def _build_psycopg_conninfo(database_url: str) -> str:
    """
    يُحوِّل DATABASE_URL إلى psycopg conninfo string.

    psycopg يحتاج postgresql:// (لا postgresql+asyncpg://).
    يُزيل sslmode من query string ويُضيف sslmode=require مباشرةً.
    """
    url_obj = make_url(database_url)
    qs = dict(url_obj.query)
    ssl_mode = qs.pop("sslmode", "require")

    scheme = "postgresql"
    clean_url = url_obj.set(drivername=scheme, query=qs).render_as_string(hide_password=False)

    sep = "&" if "?" in clean_url else "?"
    return f"{clean_url}{sep}sslmode={ssl_mode}"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """يُعيد AsyncSession للاستخدام في FastAPI Depends."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as exc:
            logger.error("Database session error: %s", exc)
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    يُهيِّئ قاعدة البيانات والـ checkpointer.

    المراحل:
      1. إنشاء جداول SQLModel (ORM)
      2. إنشاء AsyncConnectionPool لـ psycopg
      3. تهيئة AsyncPostgresSaver وإنشاء جداول checkpoint
      4. تسجيل معلومات backend في Prometheus
    """
    global _postgres_pool, postgres_checkpointer

    # ── PHASE 1: SQLModel tables ──────────────────────────────────────────
    # غير حرج في بيئة التطوير — الـ sandbox يحجب Postgres egress (port 5432/6543).
    # الخدمة تبدأ في وضع DEGRADED إذا فشل الاتصال بقاعدة البيانات.
    try:
        async with get_engine().begin() as conn:
            await conn.run_sync(OrchestratorSQLModel.metadata.create_all)
        logger.info("[DB] SQLModel tables created/verified.")
    except Exception as exc:
        logger.warning(
            "[DB] SQLModel table creation failed (non-fatal in dev): %s — "
            "service will start in DEGRADED mode.",
            exc,
        )
        if _METRICS_AVAILABLE:
            record_checkpointer_error("db_init_failed")
        return

    # ── PHASE 2 & 3: Postgres Checkpointer ───────────────────────────────
    if AsyncPostgresSaver is None:
        logger.warning(
            "[CHECKPOINTER] langgraph-checkpoint-postgres not installed — "
            "falling back to MemorySaver."
        )
        set_checkpointer_backend_info(backend="none", step="10", pool_size=0, tables_ready=False)
        return

    try:
        conninfo = _build_psycopg_conninfo(settings.DATABASE_URL)
        _postgres_pool = AsyncConnectionPool(
            conninfo=conninfo,
            min_size=1,
            max_size=_POOL_SIZE,
            open=False,
        )
        await _postgres_pool.open()
        logger.info("[CHECKPOINTER] psycopg pool opened (max_size=%d).", _POOL_SIZE)

        # تحقق من الاتصال
        async with _postgres_pool.connection() as conn:
            await conn.execute("SELECT 1")

        # أنشئ _InstrumentedCheckpointer (subclass من AsyncPostgresSaver)
        # يقبله LangGraph لأنه isinstance(BaseCheckpointSaver)
        postgres_checkpointer = _InstrumentedCheckpointer(_postgres_pool)
        await postgres_checkpointer.setup()
        logger.info("[CHECKPOINTER] AsyncPostgresSaver.setup() completed — tables ready.")

        # تحقق من الجداول
        async with _postgres_pool.connection() as conn:
            result = await conn.execute(
                "SELECT COUNT(*) FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'checkpoint%'"
            )
            row = await result.fetchone()
            tables_count = row[0] if row else 0

        tables_ready = tables_count >= 3
        logger.info("[CHECKPOINTER] checkpoint tables found: %d", tables_count)

        set_checkpointer_backend_info(
            backend="postgres",
            step="10",
            pool_size=_POOL_SIZE,
            tables_ready=tables_ready,
        )

        # اختبار قراءة حقيقي
        test_config = {"configurable": {"thread_id": "step10_init_probe"}}
        checkpoint = await postgres_checkpointer.aget(test_config)
        logger.info(
            "[CHECKPOINTER] ACTIVE — backend=postgres step=10 tables=%d pool_size=%d probe_hit=%s",
            tables_count,
            _POOL_SIZE,
            checkpoint is not None,
        )

    except Exception as exc:
        logger.error("[CHECKPOINTER] init failed (non-fatal): %s", exc)
        record_checkpointer_error("connection_error")
        set_checkpointer_backend_info(backend="none", step="10", pool_size=0, tables_ready=False)

    logger.info("[DB] init_db() completed.")


async def close_db() -> None:
    """يُغلق pool الـ checkpointer عند shutdown."""
    global _postgres_pool
    if _postgres_pool is not None:
        try:
            await _postgres_pool.close()
            logger.info("[CHECKPOINTER] psycopg pool closed.")
        except Exception as exc:
            logger.warning("[CHECKPOINTER] pool close error: %s", exc)
        _postgres_pool = None
