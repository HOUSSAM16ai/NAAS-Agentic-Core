import logging
import ssl
from collections.abc import AsyncGenerator
from typing import Any

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


def create_engine() -> AsyncEngine:
    """
    يُنشئ AsyncEngine مع دعم كامل لـ Supabase PgBouncer (transaction mode).

    PgBouncer في وضع transaction لا يدعم prepared statements.
    الحل: استخدام asyncpg.create_pool مع statement_cache_size=0 عبر creator.
    """
    import asyncpg

    db_url = settings.DATABASE_URL
    url_obj = make_url(db_url)

    qs = dict(url_obj.query)
    ssl_mode = qs.pop("sslmode", None) or qs.pop("ssl", None)

    # بناء connect_kwargs لـ asyncpg مباشرة
    connect_kwargs: dict = {
        "host": url_obj.host,
        "port": url_obj.port or 5432,
        "database": url_obj.database,
        "user": url_obj.username,
        "password": url_obj.password,
        "statement_cache_size": 0,  # PgBouncer compatibility
    }

    if ssl_mode in ("require", "verify-ca", "verify-full"):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # Supabase self-signed cert
        connect_kwargs["ssl"] = ctx

    async def _creator() -> asyncpg.Connection:
        return await asyncpg.connect(**connect_kwargs)

    # نُنشئ engine بدون URL مباشر — نستخدم creator لتجاوز SQLAlchemy dialect
    # لكن نحتاج URL صالح للـ dialect — نُزيل sslmode
    clean_url = url_obj.set(query=qs).render_as_string(hide_password=False)

    return create_async_engine(
        clean_url,
        echo=False,
        future=True,
        connect_args={
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
            "ssl": connect_kwargs.get("ssl"),
        } if "ssl" in connect_kwargs else {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        },
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


# backward-compat alias — resolved lazily via get_engine()
engine = None  # type: ignore[assignment]

# Lazy session factory — bound to engine on first call to avoid import-time DB connection
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


# backward-compat: modules that call async_session_factory() directly
class _LazySessionFactory:
    """Proxy يُحيل الاستدعاء إلى _get_session_factory() عند أول استخدام."""

    def __call__(self, *args, **kwargs):  # type: ignore[override]
        return _get_session_factory()(*args, **kwargs)

    def __getattr__(self, name: str):
        return getattr(_get_session_factory(), name)


async_session_factory = _LazySessionFactory()

_postgres_pool: AsyncConnectionPool | None = None
postgres_checkpointer: Any | None = None


def get_checkpointer() -> Any | None:
    return postgres_checkpointer


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"Database session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database schema."""
    global _postgres_pool, postgres_checkpointer
    try:
        # Import models here or ensure they are imported before calling this
        # We rely on main.py importing them.
        async with get_engine().begin() as conn:
            await conn.run_sync(OrchestratorSQLModel.metadata.create_all)

        # Initialize LangGraph Postgres checkpointer pool
        # Need to re-create a proper psycopg string from settings.DATABASE_URL
        # We will use psycopg's kwargs mapping or simple asyncpg string since it is similar
        if AsyncPostgresSaver is None:
            logger.warning(
                "LangGraph postgres checkpointer is unavailable; skipping checkpointer setup."
            )
        else:
            pool_kwargs = {
                "conninfo": settings.DATABASE_URL.replace(
                    "postgresql+asyncpg",
                    "postgresql",
                )
            }
            _postgres_pool = AsyncConnectionPool(**pool_kwargs)
            await _postgres_pool.open()

            async with _postgres_pool.connection() as conn:
                await conn.execute("SELECT 1")

            postgres_checkpointer = AsyncPostgresSaver(_postgres_pool)
            await postgres_checkpointer.setup()

            test_config = {"configurable": {"thread_id": "test_init"}}
            checkpoint = await postgres_checkpointer.aget(test_config)
            logger.info(f"Checkpointer OK: {checkpoint is not None}")

        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


async def close_db() -> None:
    """Close the database and checkpointer pool."""
    if _postgres_pool:
        await _postgres_pool.close()
