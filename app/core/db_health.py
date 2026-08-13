"""
فحص صحة قاعدة البيانات الحيّ (D-245 · 2026-08-13).

**المشكلة التي يعالجها:** `/api/security/health` و`get_system_health` كانا يردّان
`healthy` / `ok` **دائماً** — حتى حين تكون قاعدة البيانات محجوبة أو ميتة كلياً.
في بيئة GitHub Codespaces (حيث منفذا Supabase 6543/5432 محجوبان حسب
`CLAUDE.md` لـCodespaces) كان هذا يُنتج حالة "العملية حية والخدمة ميتة":
الـprocess يستقبل الطلبات ويُظهر /health أخضر بينما كل عمليات المصادقة
والتخزين والإجابات تموت — فيترجم المستخدم كل شيء إلى "login failed".

**القانون الدائم (D-245):** ⛔ لا نقطة صحة بلا مجسّ اتصالٍ حيّ بقاعدة البيانات؛
وحالة الإقلاع محفوظةٌ كحقيقةٍ واحدة يقرؤها كلُّEndpoint، فلا يتضارب /health
مع الواقع.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import text

logger = logging.getLogger(__name__)

__all__ = [
    "DB_HEALTH_UNREACHABLE",
    "DbHealthState",
    "get_db_health_state",
    "probe_database_connection",
]

DB_HEALTH_UNREACHABLE = "unreachable"
DB_HEALTH_OK = "ok"
DB_HEALTH_DEGRADED = "degraded"

PROBE_TIMEOUT_SECONDS = 6.0


def _utc_iso() -> str:
    """الوقت الحالي UTC بصيغة ISO مختصرة (ثوانٍ)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(slots=True)
class DbHealthState:
    """
    الحقيقة الوحيدة لصحة قاعدة البيانات — حالة لا قانون (D-188):
    تُحدَّث بالقياس الحيّ فقط، لا بالتخمين.
    """

    status: str = DB_HEALTH_UNREACHABLE
    checked_at: str = field(default_factory=_utc_iso)
    detail: str = ""

    def mark_ok(self, detail: str = "live probe: SELECT 1 succeeded") -> None:
        self.status = DB_HEALTH_OK
        self.checked_at = _utc_iso()
        self.detail = detail

    def mark_degraded(self, detail: str) -> None:
        self.status = DB_HEALTH_DEGRADED
        self.checked_at = _utc_iso()
        self.detail = detail

    def mark_unreachable(self, detail: str) -> None:
        self.status = DB_HEALTH_UNREACHABLE
        self.checked_at = _utc_iso()
        self.detail = detail


_STATE: DbHealthState = DbHealthState()


def get_db_health_state() -> DbHealthState:
    """
    الحقيقة الواحدة لحالة قاعدة البيانات.

    D-245 (2026-08-13): إذا كانت الحالة المعلنة `unreachable` (وهي حالةٌ
    صُمِّمت كحالةٍ جامدةٍ لتجنّب «الغطاء الأخضر الكاذب»)، فنعيد القياس الحيّ
    مرةً واحدةً بلا انتظارٍ طويل — لأن DNS/الشبكة قد يستعيدان الاتصال بعد
    الإقلاع، وتجميدُ «unreachable» للأبد كان يُبقي النظام معلِناً موته بينما
    هو حيٌّ فعلاً.
    """
    if _STATE.status == DB_HEALTH_UNREACHABLE:
        import asyncio

        with suppress(Exception):
            _reprobe_task = asyncio.create_task(_reprobe_once())
            _reprobe_task.add_done_callback(lambda _t: None)
    return _STATE


async def _reprobe_once() -> None:
    """إعادة قياسٍ صامتٍ وحيدٍ بعد فشلٍ سابق — يُحدِّث _STATE بحسب الواقع."""
    try:
        await probe_database_connection()
    except Exception:
        logger.debug("re-probe failed", exc_info=True)


async def probe_database_connection() -> str:
    """
    مجسّ اتصالٍ حيّ بقاعدة البيانات: `SELECT 1` داخل مهلة صريحة.

    Returns:
        DB_HEALTH_OK عند نجاح الاتصال، وإلا DB_HEALTH_UNREACHABLE.
    """
    from app.core.database import engine  # import كسول لتجنّب حلقة الاستيراد

    # إعادة محاولةٍ ثلاثٍ: DNS عند الإقلاع (boot) قد يفشل مؤقتاً
    # (socket.gaierror «Temporary failure in name resolution») بينما يعمل
    # بعدها بثوانٍ — محاولةٌ واحدةٌ بمعلةٍ قصيرةٍ كانت تُنتج
    # «unreachable» خادعةً والنظامُ حيٌّ فعلاً. (D-245 · 2026-08-13)
    exc: Exception | None = None
    for attempt in range(3):
        try:
            async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            _STATE.mark_ok()
            logger.info("🔌 Database live probe OK (SELECT 1)")
            return DB_HEALTH_OK
        except Exception as probe_exc:  # طبقة صحة: أي عذر = غير قابل للوصول
            exc = probe_exc
            await asyncio.sleep(2 * (attempt + 1))
    # TimeoutError (وغيرها) قد لا تحمل نصاً — اسم النوع كافٍ كسببٍ سببي.
    _STATE.mark_unreachable(
        f"live probe failed: {type(exc).__name__}" + (f": {exc}" if str(exc) else "")
    )
    logger.error("❌ Database unreachable — /health must NOT claim healthy: %s", exc)
    return DB_HEALTH_UNREACHABLE


def get_startup_health_summary() -> str:
    """ملخصٌ نصيٌّ للحالة يُكتب في السجل عند الإقلاع."""
    st = _STATE
    if st.status == DB_HEALTH_OK:
        return f"database={st.status}"
    return (
        f"database={st.status} · detail={st.detail} · "
        "⚠️ every DB-dependent operation (login / persistence / answers) "
        "will fail until connectivity is restored"
    )
