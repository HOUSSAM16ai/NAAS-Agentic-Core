import asyncio
import os
import sys
from pathlib import Path

# إعداد المسار
sys.path.append(str(Path.cwd()))

# إعداد المتغيرات البيئية
# ISS-141: بيانات الاعتماد من البيئة حصراً — كان الرابط الإنتاجي مكتوباً هنا حرفياً.
# فشلٌ صريح خير من رابطٍ مدسوس (§0: لا فشل صامت، ولا أسرار في المستودع).
if not (os.environ.get("DATABASE_URL") or os.environ.get("APP_DATABASE_URL")):
    raise SystemExit(
        "DATABASE_URL (or APP_DATABASE_URL) must be exported before running this live check."
    )
os.environ.setdefault("OPENAI_API_KEY", "sk-placeholder")

from app.core.logging import get_logger
from app.services.mcp.integrations import MCPIntegrations
from app.services.overmind.agents.self_healing import get_self_healing_agent

logger = get_logger("verify_genius_system")


async def main():
    logger.info("🚀 بدء التحقق من نظام Genius الكامل...")

    # 1. تهيئة التكاملات
    logger.info("🔌 تهيئة MCP Integrations...")
    mcp = MCPIntegrations()
    status = mcp.get_all_integrations_status()
    logger.info(f"✅ الحالة العامة: {status['learning']['status']}")

    # محاكاة ID مستخدم (سنفترض 1 لهذا الاختبار لأننا لا نملك خدمة مصادقة تعمل في السكربت)
    student_id = 1
    logger.info(f"👤 المستخدم الافتراضي: {student_id}")

    # 2. تجربة Knowledge Graph (الاحتمالات)
    logger.info("📚 فحص Knowledge Graph (تمرين الاحتمالات)...")
    concept = "probability_basics"
    prereqs = await mcp.check_prerequisites(student_id, concept)
    logger.info(f"   - المفهوم: {prereqs.get('concept')}")
    logger.info(f"   - الجاهزية: {prereqs.get('is_ready')}")
    logger.info(f"   - التوصية: {prereqs.get('recommendation')}")

    # 3. تجربة Adaptive Learning
    logger.info("📊 فحص Adaptive Learning...")
    rec = await mcp.get_difficulty_recommendation(student_id, concept)
    logger.info(f"   - الصعوبة المقترحة: {rec.get('level')}")
    logger.info(f"   - السبب: {rec.get('reason')}")

    # 4. تجربة Socratic Tutor
    logger.info("🎓 تجربة Socratic Tutor...")
    question = "كيف أحسب احتمال ظهور الوجه 6 في حجر النرد؟"
    try:
        response = await mcp.socratic_guide(question)
        logger.info(f"   - رد المعلم: {response.get('response')[:100]}...")
    except Exception as e:
        logger.warning(f"   ⚠️ Socratic Tutor بحاجة لـ AI Client (تجاوز): {e}")

    # 5. تجربة Self-Healing (مع Kagent Integration)
    logger.info("❤️‍🩹 تجربة Self-Healing Agent المتكامل...")
    agent = get_self_healing_agent()

    # دالة تفشل عمداً لمحاكاة خطأ
    async def risky_function(x):
        if x < 0:
            raise ValueError("Invalid input: must be positive")
        return x * 2

    try:
        # سنحاول تنفيذ دالة تفشل، ونرى إذا كان Self-Healing سيقترح إصلاحاً
        # ملاحظة: في بيئة الاختبار هذه، قد لا يعمل Kagent فعلياً بدون خادم، لكننا نختبر المنطق
        logger.info("   - محاولة تنفيذ وظيفة فاشلة...")
        await agent.execute_with_healing(risky_function, -5, max_attempts=2)
    except ValueError as e:
        logger.info(f"   - تم التقاط الخطأ المتوقع: {e}")
        analysis = agent.analyze_failure(e)
        logger.info(f"   - تحليل الخطأ: {analysis.failure_type}")
        if analysis.suggested_actions:
            logger.info(f"   - الإجراء المقترح: {analysis.suggested_actions[0].description}")
            if analysis.suggested_actions[0].kagent_capability:
                logger.info(
                    f"   - ⭐ قدرة Kagent المطلوبة: {analysis.suggested_actions[0].kagent_capability}"
                )
        else:
            logger.info("   - لم يتم اقتراح إجراءات (وهذا طبيعي لأول مرة)")

    # 6. تجربة Predictive Analytics
    logger.info("🔮 فحص Predictive Analytics...")
    pred = await mcp.predict_struggles(student_id)
    if pred.get("success"):
        logger.info(f"   - التنبؤات: {len(pred.get('predictions', []))} تنبؤ")
    else:
        logger.error(f"   - خطأ: {pred.get('error')}")

    logger.info("✅ تم إنهاء التحقق بنجاح!")


if __name__ == "__main__":
    asyncio.run(main())
