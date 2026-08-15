"""Shard: تهيئة مخطّط الاختبار وخطوات دورة الحياة النقية (D-258، CodeScene X-Ray).
**لماذا هذه الشريحة موجودة (Bumpy Road Ahead):** كانت `_ensure_schema` متشابكةً مع
`db_lifecycle` و`_reset_db` المتداخلة داخل fixture — ثلاث خطوات (dedupe indexes ·
drop · create · validate) في كتلةٍ واحدة طويلة بلا فصلٍ وظيفي، وكانت CodeScene
تصنّف `db_lifecycle` تعقيدًا مرتفعًا مع Bumpy Road. فُكِّكت إلى خطواتٍ نقيةٍ معلنة
(`_dedupe_table_indexes` · `_drop_all_tables` · `_create_all_tables` · `_validate_schema`)
تُركِّبها `_reset_db_steps` كسلسلةٍ خطيةٍ واحدة — كل خطوةٍ تُفهم وتُختبر وحدها.
**صفر تغيير سلوكي**: القشرة `db_lifecycle` تستدعي السلسلة نفسها بالترتيب نفسه.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from .registry import _get_engine

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

_schema_initialized = False
_schema_lock = asyncio.Lock()


def _dedupe_table_indexes() -> None:
    """يزيل الفهارس المكررة باسمٍ واحد عبر جداول metadata — (Bumpy Road killer، جزء 1/4).

    تراكمُ الفهارس من تشغيلاتٍ متعددة أو من تعارض نماذج Monolith/Microservices على
    الجدول نفسه (`extend_existing`) يجعل إنشاءها يسقط بـ `IndexAlreadyExists`.
    """
    from sqlmodel import SQLModel

    for table in SQLModel.metadata.tables.values():
        if not hasattr(table, "indexes"):
            continue
        seen: dict[str | None, object] = {}
        duplicates = []
        for index in list(table.indexes):
            index_name = getattr(index, "name", None)
            if index_name in seen:
                duplicates.append(index)
            else:
                seen[index_name] = index
        for duplicate_index in duplicates:
            table.indexes.remove(duplicate_index)


async def _drop_all_tables(locked_engine: AsyncEngine) -> None:
    """إسقاط جميع الجداول لضمان بيئة نظيفة (يتفادى مشاكل FK) — جزء 2/4."""
    from sqlmodel import SQLModel

    async with locked_engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.drop_all)


async def _create_all_tables(locked_engine: AsyncEngine) -> None:
    """إعادة بناء المخطط كاملًا — جزء 3/4."""
    from sqlmodel import SQLModel

    async with locked_engine.begin() as connection:
        await connection.run_sync(SQLModel.metadata.create_all)


async def _validate_schema() -> None:
    """التحقق والإصلاح الافتراضي (بياناتٌ افتراضية أو تعديلاتٌ بنيوية) — جزء 4/4."""
    from app.core.db_schema import validate_and_fix_schema

    await validate_and_fix_schema(auto_fix=True)


async def _ensure_schema() -> None:
    """تهيئة مخطط قاعدة البيانات داخل الذاكرة لاختبارات SQLite — تهيئةٌ أولية فقط."""
    global _schema_initialized
    from .helpers import _db_dependencies_available

    if not _db_dependencies_available():
        return
    if _schema_initialized:
        return
    # قفلٌ متزامن يمنع تداخل مستدعين يتنافسان على التهيئة الأولى (ISS-113 class).
    async with _schema_lock:
        if _schema_initialized:  # فاز مستدعٍ آخر بالسباق أثناء انتظار القفل.
            return
        factory_engine = _get_engine()
        async with factory_engine.begin() as connection:
            from sqlmodel import SQLModel

            await connection.run_sync(SQLModel.metadata.create_all)
        await _validate_schema()
        _schema_initialized = True


def _load_context_models(is_microservice_test: bool) -> None:
    """تحميل نماذج السياق الصحيح قبل كل فحصٍ بنيوي (monolith أو microservices)."""
    from contextlib import suppress

    if is_microservice_test:
        with suppress(ImportError):
            # استيرادٌ صريح لنماذج الخدمات المصغّرة يضمن المخطط الصحيح حتى لو
            # لم تُحمَّل نماذج Monolith.
            import microservices.user_service.models  # noqa: F401
    else:
        # ضمان تحميل نماذج Monolith.
        from app.core.domain import audit, content, notification, user  # noqa: F401


async def _reset_db_steps(locked_engine: AsyncEngine, is_microservice_test: bool) -> None:
    """سلسلة خطوات دورة الحياة النقية بعد القفل — مرتبةٌ خطيًا بلا تداخل (D-258).

    0) تحميل نماذج السياق الصحيح · 1) dedupe indexes · 2) drop · 3) create ·
    4) validate. كان هذا سابقًا كتلةً واحدةً داخل `_reset_db` المتداخلة في
    fixture `db_lifecycle` — بumpy road الحقيقي في CodeScene.
    """
    # الخطوة 0: النماذج تُعرف قبل dedupe — أسماء الفهارس تأتي منها.
    _load_context_models(is_microservice_test)
    # الخطوة 1: إزالة الفهارس المكررة (تجنب `IndexAlreadyExists`).
    _dedupe_table_indexes()
    # الخطوة 2: إسقاط كل الجداول لبيئةٍ نظيفة (يتفادى مشاكل FK).
    await _drop_all_tables(locked_engine)
    # الخطوة 3: إعادة بناء المخطط كاملًا.
    await _create_all_tables(locked_engine)
    # الخطوة 4: التحقق والإصلاح الافتراضي (بياناتٌ افتراضية أو تعديلاتٌ بنيوية).
    await _validate_schema()
