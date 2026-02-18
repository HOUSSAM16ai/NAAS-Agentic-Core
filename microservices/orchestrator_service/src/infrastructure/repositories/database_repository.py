"""
تنفيذ مستودع قاعدة البيانات باستخدام SQLAlchemy.

يطبق عقد `DatabaseRepository` مع التزام توثيق عربي ومؤشرات نوعية واضحة
تسهل التحقق الآلي من سلامة الاتصال.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class SQLAlchemyDatabaseRepository:
    """تطبيق SQLAlchemy لواجهة `DatabaseRepository`."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def check_connection(self) -> bool:
        """يتحقق من سلامة اتصال قاعدة البيانات عبر استعلام خفيف الوزن."""
        try:
            await self._session.execute(text("SELECT 1"))
            return True
        except Exception:  # pragma: no cover - الدفاع ضد حالات تعطل الاتصال
            return False
