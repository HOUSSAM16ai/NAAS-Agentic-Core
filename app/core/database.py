"""
Canonical Database Factory for CogniForge.

D-261 (2026-08-16 — CodeScene X-Ray job 72 · ISS-172): `create_db_engine` was a
hotspot (86 LOC · complexity F(11) · churn 8 · Complex Method), and `get_db`
carried churn 12 because of a zombie pedagogical import elsewhere (ISS-172).
The factory was decomposed into a pure delegation shell over the
`app.core.database_support` shard package — zero behavioral change. All legacy
names are re-exported unchanged (no shadowing — late-binding law from D-252).
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# NullPool removed: replaced by small pool (pool_size=5) for Supabase — D-WS-FLAP-001
from app.core.database_support import (
    _is_supabase_url,
    _rewrite_supabase_port,
    _strip_ssl_query,
    _upgrade_drivername,
    build_pool_kwargs,
    build_ssl_connect_args,
)
from app.core.settings.base import BaseServiceSettings, get_settings

logger = logging.getLogger(__name__)

__all__ = [
    "async_session_factory",
    "create_db_engine",
    "create_session_factory",
    "engine",
    "get_db",
    "get_db_session",  # D-261 (ISS-172): canonical alias for legacy pedagogical callers
]


def create_db_engine(settings: BaseServiceSettings) -> AsyncEngine:
    """Build the canonical async engine, delegating all logic to pure shards (D-261)."""
    db_url = settings.DATABASE_URL
    if not db_url:
        raise ValueError("DATABASE_URL is not set in settings.")

    # --- SQLite ---
    if "sqlite" in db_url:
        logger.info(f"SQLite database: {settings.SERVICE_NAME}")
        return create_async_engine(
            db_url,
            echo=settings.DEBUG,
            pool_pre_ping=True,
            pool_recycle=1800,
            connect_args={"check_same_thread": False},
        )

    # --- PostgreSQL (all logic delegated to pure URL/SSL/pool shards) ---
    url_obj = _upgrade_drivername(make_url(db_url))
    url_obj, ssl_mode = _strip_ssl_query(url_obj)
    is_supabase = _is_supabase_url(url_obj.host, url_obj.port)
    url_obj = _rewrite_supabase_port(url_obj, is_supabase)

    final_url = url_obj.render_as_string(hide_password=False)
    ssl_args = build_ssl_connect_args(ssl_mode)
    pool_kwargs = build_pool_kwargs(
        debug=settings.DEBUG,
        is_supabase=is_supabase,
        environment=settings.ENVIRONMENT,
        ssl_args=ssl_args,
        port=url_obj.port,
    )
    return create_async_engine(final_url, **pool_kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


# Global Singleton (legacy app/core usage only)
_legacy_settings = get_settings()
engine: AsyncEngine = create_db_engine(_legacy_settings)
async_session_factory = create_session_factory(engine)


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


# D-261 (ISS-172): legacy pedagogical callers in `app/services/chat/local_graph.py`
# imported `get_db_session` — a name that never existed in this module, so the
# whole tutor-state path failed silently inside `contextlib.suppress(Exception)`
# (zombie pedagogical state). The canonical alias is exported here so the path
# can be re-enabled deliberately (D-142) or retired with a written decision —
# never again by silent import failure. The alias is the ONLY behavioral change:
# it turns a silent failure into an available dependency, consumed nowhere new.
get_db_session = get_db
