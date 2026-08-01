"""
ربط وليّ الأمر بالطالب — برضا الطالب حصراً (D-196).

ثلاث عمليات فقط:

1. `issue_code(student_user_id)` — الطالب يُولِّد رمز ربط.
2. `redeem_code(guardian_user_id, code)` — الوليّ يستبدله فيصير الرابط فعّالاً.
3. `revoke(...)` — أيّ طرف يفكّ الرابط في أيّ وقت.

**قواعد دائمة:**
- الرمز عشوائي تعمويّاً (`secrets`) ولا يحمل أيّ معلومة عن الطالب. رمزٌ متسلسل أو مُشتقّ
  من المُعرَّف يسمح بالتخمين، وهذا ربطٌ بحساب قاصر بلا رضاه.
- **الاستبدال مرّة واحدة**: الرمز المُستهلَك لا يُقبل ثانيةً. بدون ذلك يستطيع من رأى
  الرمز مرّةً أن يربط نفسه لاحقاً.
- الطالب لا يربط نفسه بنفسه (`guardian != student`).
- الفكّ لا يحذف الصفّ بل يُعلِّمه `revoked` — سجلّ من رأى بيانات مَن يجب أن يبقى.
"""

from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.guardian import GuardianLink

logger = logging.getLogger("cogniforge.guardian.linking")

#: طول رمز الربط بالمحارف. ٨ محارف من أبجدية ٣٢ ⇒ ٤٠ بت — يتعذّر تخمينه عملياً،
#: ويبقى قابلاً للإملاء صوتياً على الهاتف.
CODE_LENGTH = 8

#: أبجدية بلا محارف مُلتبِسة (0/O · 1/I/L) — الرمز يُملى شفاهةً غالباً.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


class GuardianLinkError(ValueError):
    """خرقٌ لقواعد الربط — رمز مجهول أو مُستهلَك أو ربطٌ ذاتي."""


@dataclass(frozen=True)
class LinkedStudent:
    """طالبٌ مرتبط بوليّ، كما يراه الوليّ."""

    student_user_id: int
    linked_since: datetime


def generate_link_code() -> str:
    """رمز ربطٍ عشوائي تعمويّاً، بلا محارف مُلتبِسة."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(CODE_LENGTH))


class GuardianLinkService:
    """يدير روابط أولياء الأمور ضمن جلسة `AsyncSession` واحدة."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def issue_code(self, student_user_id: int) -> str:
        """يُولِّد رمز ربطٍ جديداً للطالب. الرموز المعلّقة السابقة تبقى صالحة."""
        code = generate_link_code()
        self.db.add(
            GuardianLink(
                guardian_user_id=None,
                student_user_id=student_user_id,
                link_code=code,
                status="pending",
            )
        )
        await self.db.commit()
        logger.info("guardian_link_issued student_user_id=%s", student_user_id)
        return code

    async def redeem_code(self, guardian_user_id: int, code: str) -> LinkedStudent:
        """
        يستبدل الوليُّ الرمز فيصير الرابط فعّالاً.

        يرفع `GuardianLinkError` على رمزٍ مجهول أو مُستهلَك أو ربطٍ ذاتي — الصمت هنا
        يعني ربطاً وهمياً يظنّ الوليّ أنّه تمّ.
        """
        normalized = (code or "").strip().upper()
        link = await self.db.scalar(
            select(GuardianLink).where(GuardianLink.link_code == normalized)
        )
        if link is None:
            raise GuardianLinkError("unknown link code")
        if link.status != "pending" or link.guardian_user_id is not None:
            raise GuardianLinkError("this link code has already been used")
        if link.student_user_id == guardian_user_id:
            raise GuardianLinkError("a student cannot be their own guardian")

        link.guardian_user_id = guardian_user_id
        link.status = "active"
        link.accepted_at = datetime.now(UTC)
        self.db.add(link)
        await self.db.commit()
        logger.info(
            "guardian_link_accepted guardian=%s student=%s", guardian_user_id, link.student_user_id
        )
        return LinkedStudent(
            student_user_id=link.student_user_id,
            linked_since=link.accepted_at,
        )

    async def linked_students(self, guardian_user_id: int) -> list[LinkedStudent]:
        """الطلاب المرتبطون فعلياً بهذا الوليّ."""
        rows = await self.db.execute(
            select(GuardianLink).where(
                GuardianLink.guardian_user_id == guardian_user_id,
                GuardianLink.status == "active",
            )
        )
        return [
            LinkedStudent(
                student_user_id=link.student_user_id,
                linked_since=link.accepted_at or link.created_at,
            )
            for link in rows.scalars().all()
        ]

    async def is_linked(self, guardian_user_id: int, student_user_id: int) -> bool:
        """
        بوّابة التفويض الوحيدة لكلّ قراءة تخصّ طالباً.

        كلّ نقطة نهاية لوليّ الأمر **يجب** أن تمرّ من هنا: بدونها يصير مُعرَّف الطالب
        في المسار كافياً لقراءة تقدّم أيّ طفل — أخطر عطبٍ ممكن في منتجٍ يخدم قاصرين.
        """
        found = await self.db.scalar(
            select(GuardianLink.id).where(
                GuardianLink.guardian_user_id == guardian_user_id,
                GuardianLink.student_user_id == student_user_id,
                GuardianLink.status == "active",
            )
        )
        return found is not None

    async def revoke(self, *, student_user_id: int, guardian_user_id: int) -> bool:
        """يفكّ الرابط. يُعلِّم الصفّ `revoked` ولا يحذفه — أثر الوصول يبقى."""
        link = await self.db.scalar(
            select(GuardianLink).where(
                GuardianLink.guardian_user_id == guardian_user_id,
                GuardianLink.student_user_id == student_user_id,
                GuardianLink.status == "active",
            )
        )
        if link is None:
            return False
        link.status = "revoked"
        link.revoked_at = datetime.now(UTC)
        self.db.add(link)
        await self.db.commit()
        logger.info(
            "guardian_link_revoked guardian=%s student=%s", guardian_user_id, student_user_id
        )
        return True


__all__ = [
    "CODE_LENGTH",
    "GuardianLinkError",
    "GuardianLinkService",
    "LinkedStudent",
    "generate_link_code",
]
