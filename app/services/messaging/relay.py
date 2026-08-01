"""حلقة الاستهلاك الخلفية داخل المونوليث (D-201).

لماذا حلقة وليس استهلاكاً متزامناً بعد النشر
--------------------------------------------
استهلاكٌ متزامن بعد النشر مباشرةً يُعيد الاقتران الذي جاء الناقل ليفكّه: يصير دور
الطالب ينتظر عمل المستهلك، فيتحوّل بطء الإشعارات إلى بطء إجابة. الحلقة تفصل الإيقاعين.

الحلقة تعمل فقط مع السائق في الذاكرة: مع Kafka يتولّى مستهلكٌ حقيقي في عمليةٍ مستقلّة
نفس الحلقة (`consume_once`) بنفس السجلّ — لا كودَ ثانٍ يُحافَظ عليه.

**كل الأخطاء مُحتواة هنا**: حلقةٌ خلفية تسقط بصمت تعني نظاماً يبدو حيّاً بلا استهلاك،
وهو ما يمنعه §0. كل دورة تُسجَّل بملخّصها.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from shared.messaging import InMemoryEventBus

logger = logging.getLogger("cogniforge.messaging.relay")

#: الفاصل بين الدورات. الإشعارات ليست حرجة زمنياً، والدورة الأسرع تشتري تأخيراً
#: لا يلاحظه أحد بثمن استيقاظاتٍ دائمة.
RELAY_INTERVAL_SECONDS = 5.0


async def run_relay_once() -> dict[str, int]:
    """
    دورةٌ واحدة. يُرجِع ملخّصاً — دورةٌ لا تقول ماذا فعلت غير قابلة للتشخيص.

    الملخّص فارغ حين لا يكون السائق في الذاكرة: مع Kafka لا يوجد ما يُسحَب محلياً.
    """
    from app.services.messaging.consumers import drain_all
    from app.services.messaging.runtime import get_event_publisher

    publisher = get_event_publisher()
    if not isinstance(publisher, InMemoryEventBus):
        return {}
    return await drain_all(publisher)


async def relay_loop(stop_event: asyncio.Event) -> None:
    """حلقةٌ حتى الإيقاف. لا تنتشر منها استثناءات."""
    while not stop_event.is_set():
        try:
            summary = await run_relay_once()
            if summary and any(summary.values()):
                logger.info("messaging_relay_cycle summary=%s", summary)
        except Exception:
            logger.warning("messaging_relay_cycle_failed", exc_info=True)
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=RELAY_INTERVAL_SECONDS)


class RelayHandle:
    """
    مقبض التشغيل — يبقي الإقلاع والإيقاف سطرَين في النواة.

    النواة تجمّع مكوّنات؛ تفاصيل دورة حياة المستهلك تعيش مع المستهلك (`check_router
    _domain_logic` بروحه: طبقة التركيب لا تحمل منطق النطاق).
    """

    def __init__(self) -> None:
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """يُسجِّل المشتركين ثمّ يُطلق الحلقة. الترتيب مقصود — انظر النواة."""
        from app.services.messaging.notifications import register_subscribers

        register_subscribers()
        self._task = asyncio.create_task(relay_loop(self._stop))

    async def stop(self) -> None:
        """يوقف الحلقة. آمنٌ إن لم تبدأ."""
        self._stop.set()
        if self._task is None:
            return
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()


__all__ = ["RELAY_INTERVAL_SECONDS", "RelayHandle", "relay_loop", "run_relay_once"]
