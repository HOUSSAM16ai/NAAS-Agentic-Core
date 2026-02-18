"""
مشغل المهام في الخلفية (Mission Runner).

هذا الملف مسؤول عن تنفيذ مهام Overmind في الخلفية بشكل آمن ومستقل.
يضمن إنشاء جلسة قاعدة بيانات جديدة منفصلة عن دورة حياة الطلب (Request Lifecycle).

المبادئ:
- Isolation: عزل تنفيذ المهمة عن طلب HTTP.
- Resource Management: إدارة دورة حياة الجلسة بشكل صريح.
"""

import logging

from microservices.orchestrator_service.src.core.database import async_session_factory
from microservices.orchestrator_service.src.services.overmind.factory import create_overmind

logger = logging.getLogger(__name__)


async def run_mission_in_background(mission_id: int) -> None:
    """
    تنفيذ المهمة في الخلفية باستخدام جلسة قاعدة بيانات مستقلة.

    Args:
        mission_id (int): معرف المهمة.
    """
    logger.info(f"🚀 Starting background execution for mission {mission_id}")

    # استخدام سياق آمن لضمان إغلاق الجلسة بعد الانتهاء
    async with async_session_factory() as session:
        try:
            # إعادة تجميع الأوركسترا مع الجلسة الجديدة
            orchestrator = await create_overmind(session)

            # بدء التنفيذ
            await orchestrator.run_mission(mission_id)

        except Exception as e:
            logger.exception(f"❌ Background execution failed for mission {mission_id}: {e}")
            # لا نعيد رفع الخطأ هنا لأننا في الخلفية، لكن تم تسجيله
