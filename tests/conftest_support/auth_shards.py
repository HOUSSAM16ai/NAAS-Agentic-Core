"""Shard: تسجيل مستخدم الاختبار وإصدار رمزه JWT (D-258، CodeScene X-Ray).
**لماذا هذه الشريحة موجودة:** كان `_register` متداخًلا داخل fixture
`register_and_login_test_user` (54 سطرًا — churn=1 · LOC=54 في CodeScene) ويحمل
عبارةَ SQL كاملةً ومنطق الرمز معاً. فُصِل إلى `_insert_user` + `_mint_token` نقية
ببياناتٍ معلنة (`TestUserInsert`) — النمط D-249 (البيانات تحكم لا التوقيعات
المتناثرة) — **صفر تغيير سلوكي** (القشرة تفوض حرفيًا، والنمط القسري
`RETURNING id` لا `lastrowid` محفوظٌ نصًا كما يفرضه CLAUDE.md على auth).
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import jwt

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclasses.dataclass(frozen=True)
class TestUserInsert:
    """بيانات إدخال مستخدم اختبار معلنة (نمط D-249)."""

    external_id: str
    full_name: str = "Student User"
    email: str = "test-user@example.com"
    password_hash: str = "dummy_hash"
    is_admin: bool = False
    is_active: bool = True
    status: str = "active"


async def _insert_user(db_session: AsyncSession, insert: TestUserInsert) -> int:
    """يُدخل مستخدمًا نصيًا ويعيد `id` — `RETURNING id` لا `lastrowid` (قانون CLAUDE.md).

    ── `RETURNING id` لا `lastrowid` ─────────────────────────────────────
    هذا هو النمط الذي يفرضه CLAUDE.md على `auth_persistence.py` حرفيًا
    («lastrowid لا يعمل بموثوقية»). الأثر **مقيس**:
    `test_guardian_dashboard::test_redeeming_a_bad_code_over_http` يفشل بـ401 في
    ١ من كل ٥ تشغيلات حين يسبقه ملفٌ آخر يستعمل التركيبة نفسها — لأن `lastrowid`
    يُعيد صفَّ عبارةٍ أخرى على الاتصال المُجمَّع فيشير `sub` إلى مستخدمٍ غير
    موجود فيُرفض الرمز. القراءة **قبل** الـcommit لأن `RETURNING` تُستهلك من
    نتيجة العبارة نفسها.
    """
    from sqlalchemy import text

    insert_statement = text(
        """
        INSERT INTO users (
            external_id,
            full_name,
            email,
            password_hash,
            is_admin,
            is_active,
            status
        )
        VALUES (:external_id, :full_name, :email, :password_hash, :is_admin, :is_active, :status)
        RETURNING id
        """
    )
    result = await db_session.execute(
        insert_statement,
        {
            "external_id": insert.external_id,
            "full_name": insert.full_name,
            "email": insert.email,
            "password_hash": insert.password_hash,
            "is_admin": insert.is_admin,
            "is_active": insert.is_active,
            "status": insert.status,
        },
    )
    user_id = result.scalar_one()
    await db_session.commit()
    return user_id


def _mint_token(user_id: int) -> str:
    """يصدر رمز JWT وصولًا لساعة — نفس الحمولة التي كانت تُبنى داخل fixture."""
    from app.core.config import get_settings

    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, get_settings().SECRET_KEY, algorithm="HS256")


async def _register_user_and_mint_token(
    db_session: AsyncSession,
    email: str = "test-user@example.com",
) -> str:
    """يُدخل المستخدم ويُعيد رمزه — التركيب السابق كاملًا من fixture
    `register_and_login_test_user` بلا أي تغيير."""
    user_id = await _insert_user(
        db_session,
        TestUserInsert(external_id=email, email=email),
    )
    return _mint_token(user_id)
