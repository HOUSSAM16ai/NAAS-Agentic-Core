"""Shard: محرك الاختبار ومصنع الجلسات بعزلٍ حقيقي (D-258، CodeScene X-Ray).
**لماذا هذه الشريحة موجودة:** كان `_get_engine`/`_get_session_factory` يحملان حالتين
عامتين (`_engine`/`_session_factory`) بلا قفلٍ متزامن — اختباراتٌ متوازية على
الحلقة نفسها قد تُعيد بناء المحرك مرتين. فُصِلا إلى هذه الشريحة مع `asyncio.Lock`
لعزلٍ حقيقي (D-105 ISS-113: فئة بق «يمرّ منفردًا ويفشل بترتيب الحزمة الكاملة») —
**صفر تغيير سلوكي** من منظور أي اختبار: التوقيعات العامة قشور تفويض حرفية.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .helpers import _db_dependencies_available

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_registry_lock = asyncio.Lock()

engine: AsyncEngine | None
TestingSessionLocal: async_sessionmaker[AsyncSession] | None


def _get_engine() -> AsyncEngine:
    """يبني محرك SQLite داخل الذاكرة عند الحاجة فقط للاختبارات."""
    if not _db_dependencies_available():
        # D-258 follow-up: بيئاتٌ بلا اعتمادات (بوابة Skills Doctrine Gate — D-069)
        # لا تحمل sqlalchemy أصلًا — الخطأ يُرفَع صراحة بدل فشل استيراد غامض.
        raise ModuleNotFoundError(
            "sqlalchemy غير متوفر في هذه البيئة — لا تهيئة محرك اختباري ممكنة"
        )
    global _engine
    if _engine is not None:
        return _engine
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import StaticPool

    _engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    return _engine


async def _get_engine_locked() -> AsyncEngine:
    """نسخةٌ محمية بقفلٍ متزامن — تبني المحرك مرةً واحدة حتى مع تداخل مستدعين."""
    async with _registry_lock:
        return _get_engine()


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """يعيد مصنع الجلسات مع ضمان ربطه بنواة قواعد البيانات للاختبارات."""
    if not _db_dependencies_available():
        # D-258 follow-up: بيئاتٌ بلا اعتمادات (بوابة Skills Doctrine Gate — D-069).
        raise ModuleNotFoundError("sqlalchemy غير متوفر في هذه البيئة — لا مصنع جلسات اختباري ممكن")
    global _session_factory
    if _session_factory is not None:
        return _session_factory
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.core import database as core_database

    factory_engine = _get_engine()
    _session_factory = async_sessionmaker(
        factory_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    core_database.engine = factory_engine
    core_database.async_session_factory = _session_factory
    return _session_factory


async def _get_session_factory_locked() -> async_sessionmaker[AsyncSession]:
    """نسخةٌ محمية بقفلٍ متزامن — تبني المصنع مرةً واحدة حتى مع تداخل مستدعين."""
    async with _registry_lock:
        return _get_session_factory()


# D-258 follow-up: حراسةٌ مزدوجة — بيئاتٌ بلا اعتمادات قواعد البيانات
# (بوابة Skills Doctrine Gate في CI — D-069 لا تنصّب إلا pydantic) يجب أن
# تُجمَّع دون فشلٍ عند التحميل؛ `_db_dependencies_available` تحققٌ استباقي
# لكن `importlib.util.find_spec` قد يمرّر مسارات وهمية، فالحراسة هنا تمتص
# `ModuleNotFoundError` الفعلي من الاستيراد المتأخر.
try:
    if _db_dependencies_available():
        engine = _get_engine()
        TestingSessionLocal = _get_session_factory()
    else:
        engine = None
        TestingSessionLocal = None
except ModuleNotFoundError:  # pragma: no cover — بيئات بلا اعتمادات فقط
    engine = None
    TestingSessionLocal = None
