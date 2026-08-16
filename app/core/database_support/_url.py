"""شريحة تحويلات الـ URL (D-261 — تفكيك hotspot `app/core/database.py` — CodeScene X-Ray).
دوالٌ نقيةٌ بلا حالةٍ تحوّل رابط الاتصال قبل تسليمه للمصنع — واحدةٌ لكل مسؤولية:
الكشف · إعادة كتابة المنفذ · ترقية البروتوكول · تجريد معاملات SSL.
"""

from __future__ import annotations

import logging

from sqlalchemy.engine.url import URL

logger = logging.getLogger(__name__)


def _is_supabase_url(host: str | None, port: int | None) -> bool:
    """Return True for any Supabase connection."""
    if host and "supabase.com" in host:
        return True
    return port == 6543


def _upgrade_drivername(url_obj: URL) -> URL:
    """Raise plain Postgres drivers to their asyncpg variants (D-261)."""
    if url_obj.drivername in ("postgresql", "postgres"):
        return url_obj.set(drivername="postgresql+asyncpg")
    return url_obj


def _strip_ssl_query(url_obj: URL) -> tuple[URL, str | None]:
    """Strip sslmode/ssl from the query string — handled via an SSL context instead.

    Returns the rewritten URL and the extracted ssl mode (or None).
    """
    qs = dict(url_obj.query)
    ssl_mode: str | None = qs.pop("sslmode", None) or qs.pop("ssl", None)
    return url_obj.set(query=qs), ssl_mode


def _rewrite_supabase_port(url_obj: URL, is_supabase: bool) -> URL:
    """Rewrite PgBouncer port 6543 (transaction mode) → 5432 (session mode) (D-WS-FLAP-001).

    Port 6543 keeps prepared-statement names in PgBouncer's own cache across
    logical connections, so asyncpg hits DuplicatePreparedStatementError even
    with statement_cache_size=0 — the collision happens at the PgBouncer
    protocol layer. Port 5432 connects directly to the Supabase session pool,
    which correctly honors statement_cache_size=0.
    """
    if is_supabase and url_obj.port == 6543:
        logger.info("Rewrote Supabase port 6543 → 5432 (session mode)")
        return url_obj.set(port=5432)
    return url_obj
