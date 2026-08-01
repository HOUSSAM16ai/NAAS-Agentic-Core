"""
تسجيل أحداث المنتج وقراءة الاحتفاظ (D-197).

`record_product_event(...)` هي نقطة الكتابة الوحيدة من المسار الحيّ: تملك جلستها،
وتتحقّق من الاسم مقابل السجلّ القانوني، و**لا ترفع أبداً**. تحليلاتٌ تُسقِط دور طالب
أسوأ من ألّا تكون موجودة.

`ProductAnalyticsService` يقرأ فقط: يجلب الصفوف الخام ويسلّمها لطبقة الحساب الحتمية في
`shared/analytics/retention.py` — التعريف يعيش هناك مرّةً واحدة (SQLite وPostgres
يختلفان في دوالّ التاريخ، ونسختان من التعريف تعنيان رقمين لنفس السؤال).
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.product_event import ProductEvent
from app.core.domain.user import User
from shared.analytics import (
    DEFAULT_HORIZONS,
    AnalyticsError,
    EventName,
    FunnelStep,
    RetentionReport,
    funnel,
    retention_report,
    validate_event_name,
)

logger = logging.getLogger("cogniforge.analytics.product")

#: القُمع التجاري: الطالب يبدأ ⇒ يراجع ⇒ يربط وليّه ⇒ الوليّ يقرأ.
#: هذا هو المسار الذي يقرّر إن كان المنتج يتحوّل إلى اشتراك.
DEFAULT_FUNNEL: tuple[str, ...] = (
    EventName.USER_SIGNED_UP,
    EventName.CHAT_TURN_STARTED,
    EventName.REVIEW_QUEUE_VIEWED,
    EventName.GUARDIAN_LINK_ISSUED,
    EventName.GUARDIAN_LINK_ACCEPTED,
)


async def record_product_event(
    *,
    event_name: str,
    user_id: int | None = None,
    session_id: int | None = None,
    props: dict | None = None,
    occurred_at: datetime | None = None,
) -> bool:
    """
    يكتب حدثاً في سجلّ المنتج. **لا يرفع أبداً** — يُرجِع نجاح الكتابة.

    الجلسة مملوكة هنا (لا في المُوجِّه): إدارة الجلسات منطق نطاق
    (`check_router_domain_logic`)، والجلسة المستقلّة تمنع تلويث دور الطالب.
    """
    try:
        validate_event_name(event_name)
    except AnalyticsError:
        # اسمٌ خارج السجلّ خطأُ مبرمج — يُسجَّل بصوتٍ ولا يُكتَب صفٌّ يُفسد التجميع.
        logger.warning("product_event_rejected name=%s (not in the canonical registry)", event_name)
        return False

    try:
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            db.add(
                ProductEvent(
                    user_id=user_id,
                    event_name=event_name,
                    session_id=session_id,
                    props=props,
                    occurred_at=occurred_at or datetime.now(UTC),
                )
            )
            await db.commit()
        return True
    except Exception as exc:
        logger.warning("product_event_write_failed name=%s: %s", event_name, exc)
        return False


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)


class ProductAnalyticsService:
    """قراءة الاحتفاظ والقُمع — لا كتابة، لا LLM، لا تقدير."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _signups(self, since: datetime) -> dict[int, datetime]:
        """
        لحظة تسجيل كلّ مستخدم.

        نُفضِّل حدث `user_signed_up` حين يوجد، ونسقط إلى `users.created_at` للحسابات
        السابقة لهذا السجلّ — وإلّا بدت المنصّة بلا تاريخ يوم تشغيل التتبّع.
        """
        rows = await self.db.execute(
            select(ProductEvent.user_id, ProductEvent.occurred_at).where(
                ProductEvent.event_name == EventName.USER_SIGNED_UP,
                ProductEvent.user_id.is_not(None),
                ProductEvent.occurred_at >= since,
            )
        )
        signups: dict[int, datetime] = {}
        for user_id, occurred_at in rows.all():
            moment = _as_utc(occurred_at)
            if user_id not in signups or moment < signups[user_id]:
                signups[user_id] = moment

        legacy = await self.db.execute(
            select(User.id, User.created_at).where(User.created_at >= since)
        )
        for user_id, created_at in legacy.all():
            if user_id not in signups and created_at is not None:
                signups[user_id] = _as_utc(created_at)
        return signups

    async def _activity(self, since: datetime) -> dict[int, list[datetime]]:
        """لحظات النشاط — دور الطالب هو تعريف «نشِط»."""
        rows = await self.db.execute(
            select(ProductEvent.user_id, ProductEvent.occurred_at).where(
                ProductEvent.event_name == EventName.CHAT_TURN_STARTED,
                ProductEvent.user_id.is_not(None),
                ProductEvent.occurred_at >= since,
            )
        )
        activity: dict[int, list[datetime]] = {}
        for user_id, occurred_at in rows.all():
            activity.setdefault(user_id, []).append(_as_utc(occurred_at))
        return activity

    async def retention(
        self,
        *,
        today: date | None = None,
        window_days: int = 90,
        horizons: tuple[int, ...] = DEFAULT_HORIZONS,
    ) -> RetentionReport:
        """تقرير الاحتفاظ بالأفواج. الحساب في `shared/analytics` — مصدر تعريفٍ واحد."""
        reference = today or datetime.now(UTC).date()
        since = datetime.now(UTC) - timedelta(days=window_days)
        return retention_report(
            signups=await self._signups(since),
            activity=await self._activity(since),
            today=reference,
            horizons=horizons,
        )

    async def conversion_funnel(
        self, *, steps: tuple[str, ...] = DEFAULT_FUNNEL, window_days: int = 90
    ) -> tuple[FunnelStep, ...]:
        """قُمع التحويل التجاري عبر النافذة."""
        since = datetime.now(UTC) - timedelta(days=window_days)
        rows = await self.db.execute(
            select(ProductEvent.event_name, ProductEvent.user_id).where(
                ProductEvent.event_name.in_(list(steps)),
                ProductEvent.user_id.is_not(None),
                ProductEvent.occurred_at >= since,
            )
        )
        users_by_event: dict[str, set[int]] = {}
        for event_name, user_id in rows.all():
            users_by_event.setdefault(event_name, set()).add(user_id)
        return funnel(steps=steps, users_by_event=users_by_event)


__all__ = ["DEFAULT_FUNNEL", "ProductAnalyticsService", "record_product_event"]
