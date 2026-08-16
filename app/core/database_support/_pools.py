"""شريحة تكوينات الـ pool (D-261 — تفكيك hotspot `app/core/database.py` — CodeScene X-Ray).
دوالٌ نقيةٌ ترجع معجم ``kwargs`` جاهزًا للتسليم إلى
``create_async_engine`` — واحدةٌ لكل نمط تشغيل، ولا تحمل أي حالة.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _connect_args(ssl_args: dict[str, object]) -> dict[str, object]:
    """asyncpg `connect_args` per profile (D-261).

    ``statement_cache_size=0`` + ``prepared_statement_cache_size=0`` disable
    asyncpg's prepared-statement caches so the engine stays compatible with
    any connection pooler (PgBouncer, Supabase pooler, or a plain Postgres).
    The legacy factory placed these inside ``connect_args`` (next to the SSL
    context) — the guardrail suite asserts exactly that shape, so the shard
    preserves it byte-for-byte.
    """
    return {
        **ssl_args,
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }


def _common_engine_kwargs(debug: bool) -> dict[str, object]:
    """Common async engine kwargs shared by every Postgres pool profile (D-261)."""
    return {
        "echo": debug,
        "pool_pre_ping": True,
    }


def supabase_pool_kwargs(
    debug: bool, ssl_args: dict[str, object], port: int | None
) -> dict[str, object]:
    """Supabase pool profile: small fixed pool (D-WS-FLAP-001 · D-261).

    NullPool opens a new TCP connection per session. Under concurrent WS turns
    (3-4 DB sessions each), this exhausts Supabase's connection limit (~60)
    and causes DB errors mid-stream, which propagate as WebSocket flapping.
    A small pool (5 connections) with statement_cache_size=0 avoids
    DuplicatePreparedStatementError at the asyncpg level.
    """
    logger.info(f"Supabase database (pool_size=5, no prepared statements, port {port})")
    return {
        **_common_engine_kwargs(debug),
        "pool_size": 5,
        "max_overflow": 5,
        "pool_recycle": 300,
        "connect_args": _connect_args(ssl_args),
    }


def dev_pool_kwargs(debug: bool, ssl_args: dict[str, object]) -> dict[str, object]:
    """Development/testing pool profile (D-261)."""
    logger.info("Postgres database (development/testing profile)")
    return {
        **_common_engine_kwargs(debug),
        "pool_recycle": 1800,
        "pool_size": 5,
        "max_overflow": 10,
        "connect_args": _connect_args(ssl_args),
    }


def prod_pool_kwargs(debug: bool, ssl_args: dict[str, object]) -> dict[str, object]:
    """Production pool profile (D-261)."""
    logger.info("Postgres database (production profile)")
    return {
        **_common_engine_kwargs(debug),
        "pool_recycle": 1800,
        "pool_size": 40,
        "max_overflow": 60,
        "connect_args": _connect_args(ssl_args),
    }


def build_pool_kwargs(
    *,
    debug: bool,
    is_supabase: bool,
    environment: str,
    ssl_args: dict[str, object],
    port: int | None,
) -> dict[str, object]:
    """Dispatch to the correct pool profile (D-261)."""
    if is_supabase:
        return supabase_pool_kwargs(debug, ssl_args, port)
    if environment in ("development", "testing"):
        return dev_pool_kwargs(debug, ssl_args)
    return prod_pool_kwargs(debug, ssl_args)
