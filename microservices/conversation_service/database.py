"""
قاعدة بيانات conversation-service — lazy singleton.

يستخدم postgresql+asyncpg:// في الإنتاج و sqlite+aiosqlite:///:memory: في الاختبارات.
يُحوِّل postgresql:// إلى postgresql+asyncpg:// تلقائياً (ISS-038-B).
"""

from __future__ import annotations

import os
import re

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── تحويل URL تلقائي ──────────────────────────────────────────────────────────


def _normalize_db_url(url: str) -> str:
    """يُحوِّل postgresql:// إلى postgresql+asyncpg:// ويُزيل sslmode."""
    url = re.sub(r"^postgresql://", "postgresql+asyncpg://", url)
    url = re.sub(r"^postgres://", "postgresql+asyncpg://", url)
    url = re.sub(r"\?sslmode=\w+", "", url)
    return re.sub(r"&sslmode=\w+", "", url)


# ── Lazy Engine Singleton ─────────────────────────────────────────────────────

# Singleton: مُهيَّأ عند أول استخدام، لا عند import
_engine: object | None = None


def _get_raw_url() -> str:
    """يقرأ DATABASE_URL من البيئة مع fallback لـ SQLite."""
    raw = (
        os.environ.get("CONV_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or "sqlite+aiosqlite:///:memory:"
    )
    return _normalize_db_url(raw)


def get_engine():
    """يُعيد الـ engine — lazy singleton."""
    global _engine
    if _engine is None:
        url = _get_raw_url()
        connect_args = {}
        if "asyncpg" in url:
            connect_args = {"statement_cache_size": 0}
        _engine = create_async_engine(url, echo=False, connect_args=connect_args)
    return _engine


# ── Compatibility alias ───────────────────────────────────────────────────────
# يُستخدم في main.py lifespan للتحقق من الاتصال
engine = get_engine()

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_conv_db_session():
    """Dependency injection لـ FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session
