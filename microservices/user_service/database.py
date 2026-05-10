"""
وحدة قاعدة البيانات لخدمة المستخدمين.

تُبقي هذه الوحدة التهيئة محلية لخدمة المستخدمين دون اعتماد مشترك.

ملاحظة SSL: asyncpg لا يقبل sslmode في query string — يجب تحويله إلى
ssl context في connect_args (نفس نمط app/core/database.py في المونوليث).
"""

import asyncio
import logging
import os
import ssl
from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from microservices.user_service.models import SQLModel
from microservices.user_service.settings import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
runtime_settings = settings
if os.getenv("ENVIRONMENT") == "testing":
    runtime_settings = settings.model_copy(update={"DATABASE_URL": "sqlite+aiosqlite:///:memory:"})


def create_db_engine(
    *,
    database_url: str,
    environment: str,
    echo: bool,
    service_name: str,
) -> AsyncEngine:
    """إنشاء محرك قاعدة البيانات بشكل صريح ومبسّط.

    يُعالج sslmode في query string بتحويله إلى ssl context في connect_args
    لأن asyncpg لا يقبل sslmode كـ query parameter مباشرة.
    """

    if not database_url:
        raise ValueError("DATABASE_URL غير مُعدّ لخدمة المستخدمين.")

    engine_args: dict[str, object] = {
        "echo": echo,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

    url_obj = make_url(database_url)
    if "sqlite" in url_obj.drivername:
        engine_args["connect_args"] = {"check_same_thread": False}
        logger.info("Database (SQLite): %s", service_name)
    elif "postgresql" in url_obj.drivername:
        # ── تحويل driver إلى asyncpg ──────────────────────────────────────
        if url_obj.drivername in ("postgresql", "postgres"):
            url_obj = url_obj.set(drivername="postgresql+asyncpg")

        # ── استخراج sslmode من query string ──────────────────────────────
        # asyncpg يرفض sslmode كـ query param — يجب تمريره عبر connect_args
        qs = dict(url_obj.query)
        ssl_mode = qs.pop("sslmode", None) or qs.pop("ssl", None)

        # ── Supabase PgBouncer: port 6543 → 5432 ─────────────────────────
        # PgBouncer على 6543 يعمل بـ transaction mode — يُسبب
        # DuplicatePreparedStatementError حتى مع statement_cache_size=0.
        # المنفذ 5432 يتصل بـ session pool مباشرة ويدعم prepared statements.
        is_supabase = "supabase.com" in (url_obj.host or "")
        if is_supabase and url_obj.port == 6543:
            url_obj = url_obj.set(port=5432)
            logger.info("Supabase: rewrote port 6543 → 5432 (session mode)")

        url_obj = url_obj.set(query=qs)
        database_url = url_obj.render_as_string(hide_password=False)

        connect_args: dict[str, object] = {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }

        if ssl_mode in ("require", "verify-ca", "verify-full"):
            ctx = ssl.create_default_context()
            if ssl_mode == "require":
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            connect_args["ssl"] = ctx
            logger.info("SSL enabled (mode: %s) for %s", ssl_mode, service_name)

        logger.info("Database (Postgres/Supabase): %s", service_name)

        if is_supabase:
            # NullPool: لا connection pooling — Supabase يدير الـ pool
            return create_async_engine(
                database_url,
                echo=echo,
                poolclass=NullPool,
                connect_args=connect_args,
            )

        is_dev = environment in ("development", "testing")
        engine_args["connect_args"] = connect_args
        engine_args["pool_size"] = 5 if is_dev else 40
        engine_args["max_overflow"] = 10 if is_dev else 60

    return create_async_engine(database_url, **engine_args)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """إنشاء مصنع جلسات لقاعدة البيانات."""

    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


engine = create_db_engine(
    database_url=runtime_settings.DATABASE_URL,
    environment=runtime_settings.ENVIRONMENT,
    echo=runtime_settings.DEBUG,
    service_name=runtime_settings.SERVICE_NAME,
)
async_session_factory = create_session_factory(engine)

_init_lock = asyncio.Lock()
_is_initialized = False


async def init_db() -> None:
    """
    تهيئة مخطط قاعدة البيانات.

    يُسمح بذلك فقط في التطوير والاختبار.
    """

    if settings.ENVIRONMENT not in ("development", "testing"):
        return

    # Deduplicate indexes to handle potential accumulation from multiple test runs
    # This prevents "index already exists" errors in tests where metadata is shared
    for table in SQLModel.metadata.tables.values():
        unique_indexes = {}
        if hasattr(table, "indexes"):
            for index in table.indexes:
                if index.name not in unique_indexes:
                    unique_indexes[index.name] = index
            table.indexes = set(unique_indexes.values())

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def _ensure_initialized() -> None:
    global _is_initialized
    if _is_initialized:
        return
    async with _init_lock:
        if _is_initialized:
            return
        await init_db()
        _is_initialized = True


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """اعتماد جلسة قاعدة بيانات لخدمة المستخدمين."""

    await _ensure_initialized()
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
