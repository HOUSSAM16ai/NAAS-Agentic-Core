"""شريحة دورة الحياة (D-260 — تفكيك hotspot `app/kernel.py` — CodeScene X-Ray).

يفكّ `_handle_lifespan_events` (radon B(8) · churn=9 · Bumpy Road) إلى
دالتين نقيتين بلا حالة: `run_startup_phase` / `run_shutdown_phase` —
كلٌ منهما دالةٌ واحدةٌ صغيرة تُجمع مراحلها declaratively في قائمة،
فلا تجمّع حراري بين الإقلاع والإيقاف ولا بين المجسات والناقل.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.db_schema import validate_schema_on_startup
from app.core.redis_bus import get_redis_bridge
from app.services.bootstrap import bootstrap_admin_account
from app.telemetry.unified_observability import get_unified_observability

if TYPE_CHECKING:
    from app.core.config import AppSettings
    from app.services.messaging.relay import RelayHandle

logger = logging.getLogger(__name__)


async def _announce_startup_health() -> None:
    """D-245 (2026-08-13): إعلانٌ صادقٌ لصحة قاعدة البيانات والمزودين عند الإقلاع.

    بدون هذا الإعلان كانت بيئةٌ محجوبةٌ عن قاعدة البيانات (GitHub Codespaces —
    منفذا Supabase 6543/5432 محجوبان حسب CLAUDE.md) تبدأ بكلّ شيءٍ أخضر
    بينما تموت كل عمليةٍ تعتمد على DB: "login failed" · لا رسائل محفوظة ·
    لا إجابات — ولا أي إشارةٍ معلنةٍ تسبق أول فشلٍ (ISS-163).
    """
    from app.core.db_health import probe_database_connection
    from app.core.providers_health import check_ambient_memory_reachable, probe_providers_health

    db_status = await probe_database_connection()
    if db_status == "ok":
        logger.info("✅ Database connectivity live at startup")
    else:
        logger.error(
            "❌ DATABASE UNREACHABLE AT STARTUP — health endpoints MUST NOT "
            "claim healthy; every DB operation (login / persistence / chat "
            "answers) will fail until connectivity is restored. See D-245."
        )
    providers = probe_providers_health()
    if providers.llm_provider == "missing":
        logger.error(
            "❌ LLM PROVIDER MISSING AT STARTUP — the chat engine will refuse "
            "every question with «🛑 خطأ في التكوين: مفتاح الذكاء الاصطناعي "
            "مفقود». اضبط OPENROUTER_API_KEY أو OPENAI_API_KEY في Secrets "
            "البيئة. See D-245."
        )
    else:
        logger.info("✅ LLM provider configured (%s)", providers.llm_detail)

    # D-269: الساق الثالثة من البرهان الثلاثي للطبقة الخامسة. مسبارٌ للقراءة فقط،
    # مُقيَّدٌ بمهلة، ⛔ بلا أيّ بيانات طالب — وغيابُ المفتاح ليس عطلاً.
    await check_ambient_memory_reachable()
    logger.info(
        "🧠 Ambient identity layer: %s (%s)",
        providers.ambient_memory,
        providers.ambient_memory_detail,
    )


async def _start_messaging_relay() -> RelayHandle | None:
    """
    يُقلع حلقة الرسائل (D-201) — استيرادٌ كسول فلا تتحمّل النواة تبعية الناقل.

    الفشل هنا لا يمنع الإقلاع: الناقل تابعٌ لا أصل، ودورُ الطالب يعمل بدونه.
    """
    try:
        from app.services.messaging.relay import RelayHandle

        relay = RelayHandle()
        await relay.start()
        logger.info("✅ Messaging relay started")
        return relay
    except Exception:
        logger.warning("⚠️ Failed to start messaging relay", exc_info=True)
        return None


async def _stop_messaging_relay(relay: RelayHandle | None) -> None:
    """يوقف حلقة الرسائل. آمنٌ إن لم تُقلع."""
    if relay is None:
        return
    try:
        await relay.stop()
        logger.info("✅ Messaging relay stopped")
    except Exception:
        logger.warning("⚠️ Failed to stop messaging relay", exc_info=True)


async def run_startup_phase(settings_obj: AppSettings) -> RelayHandle | None:
    """مرحلة الإقلاع الكاملة — قائمة مراحلٍ declarative بلا تجمّع حراري.

    كل مرحلةٍ تُنعَّل ذاتيًا (fail-soft): الفشل يُبلَّغ ولا يمنع المراحل
    اللاحقة — باستثناء الإعلان الصادق D-245 الذي يُصدر تنبيهًا ظاهرًا.
    الترتيب مقصود: D-201 يُسجَّل الناقل قبل حلقة الاستهلاك، وإلا سقطت
    الأحداث بلا مستهلك.
    """
    logger.info("🚀 CogniForge System Initializing... (Strict Mode Active)")
    observability = get_unified_observability()
    redis_bridge = get_redis_bridge()

    await _announce_startup_health()

    try:
        await validate_schema_on_startup()
        logger.info("✅ Database Schema Validated")
    except Exception:
        logger.warning("⚠️ Schema validation warning", exc_info=True)

    try:
        from app.core.database import async_session_factory

        async with async_session_factory() as session:
            await bootstrap_admin_account(session, settings=settings_obj)
            logger.info("✅ Admin account bootstrapped and validated")
    except Exception:
        logger.exception("❌ Failed to bootstrap admin account")

    try:
        await observability.start_background_sync()
        logger.info("✅ Unified Observability Sync Started")
    except Exception:
        logger.warning("⚠️ Failed to start observability sync", exc_info=True)

    try:
        await redis_bridge.start()
    except Exception:
        logger.warning("⚠️ Failed to start Redis Event Bridge", exc_info=True)

    # D-201 — ناقل الأحداث: تسجيل المشتركين ثمّ إطلاق حلقة الاستهلاك.
    messaging_relay = await _start_messaging_relay()

    # Pre-warm LangGraph local engine (catches import errors at startup)
    try:
        from app.services.chat.local_graph import get_local_graph

        get_local_graph()
        logger.info("✅ LangGraph local engine initialized")
    except Exception:
        logger.warning("⚠️ LangGraph local engine failed to initialize", exc_info=True)

    logger.info("✅ System Ready")
    return messaging_relay


async def run_shutdown_phase(
    messaging_relay: RelayHandle | None,
) -> None:
    """مرحلة الإيقاف الكاملة — ناقل الرسائل أولًا (D-201) لتجنب failures بلا معنى.

    استيقاف الناقل قبل تفكيك factory الجلسة يمنع سجلّات «consumer draining
    while DB torn down» التي لا تعني شيئًا — الترتيب معكوسٌ بالترتيب هنا عمدًا.
    """
    # Stop the messaging relay first (D-201 order): a consumer still draining
    # while the database session factory is torn down logs failures that
    # mean nothing.
    await _stop_messaging_relay(messaging_relay)

    redis_bridge = get_redis_bridge()
    try:
        await redis_bridge.stop()
    except Exception:
        logger.warning("⚠️ Failed to stop Redis Event Bridge", exc_info=True)

    observability = get_unified_observability()
    try:
        await observability.stop_background_sync()
        logger.info("✅ Unified Observability Sync Stopped")
    except Exception:
        logger.warning("⚠️ Failed to stop observability sync", exc_info=True)

    logger.info("👋 CogniForge System Shutting Down...")
