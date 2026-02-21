"""
Analytics Agent (Ported).
"""

from collections.abc import AsyncGenerator

from microservices.orchestrator_service.src.core.logging import get_logger
from microservices.orchestrator_service.src.services.llm.client import AIClient
from microservices.orchestrator_service.src.services.overmind.utils.intent_detector import (
    ChatIntent,
)
from microservices.orchestrator_service.src.services.overmind.utils.tools import ToolRegistry

logger = get_logger("analytics-agent")


class AnalyticsAgent:
    """
    Analytics Agent (Superhuman Edition).
    """

    def __init__(self, tools: ToolRegistry, ai_client: AIClient | None = None) -> None:
        self.tools = tools
        self.ai_client = ai_client

    async def process(self, context: dict[str, object]) -> AsyncGenerator[str, None]:
        logger.info("Analytics agent started processing (Superhuman Mode)")

        user_id = context.get("user_id")
        if not user_id:
            yield "عذراً، لم أتمكن من تحديد هوية المستخدم لتحليل بياناته."
            return

        if not self.ai_client:
            yield "⚠️ خطأ داخلي: لم يتم تزويد الوكيل بمحرك الذكاء الاصطناعي."
            return

        yield "🔍 **جاري استدعاء سجلاتك الدراسية وتحليل محادثاتك السابقة بالكامل...**\n"

        try:
            data = await self.tools.execute(
                "fetch_comprehensive_student_history", {"user_id": user_id}
            )
        except Exception as e:
            logger.error(f"Error fetching comprehensive history: {e}")
            yield "حدث خطأ أثناء جلب البيانات."
            return

        if not data:
            data = {
                "chat_history_text": "No logs available.",
                "missions_summary": {},
                "profile_stats": {},
            }

        chat_logs = str(data.get("chat_history_text", "No logs."))
        missions = data.get("missions_summary", {})
        stats = data.get("profile_stats", {})
        intent = context.get("intent")

        system_prompt, user_prompt = self._build_analysis_prompts(
            chat_logs=chat_logs,
            missions=missions,
            stats=stats,
            intent=intent,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        yield "\n"

        try:
            async for chunk in self.ai_client.stream_chat(messages):
                content = ""
                if hasattr(chunk, "choices") and chunk.choices:
                    content = chunk.choices[0].delta.content or ""

                if content:
                    yield content

        except Exception as exc:
            logger.error(f"AI Analysis Failed: {exc}")
            yield "\n⚠️ حدث خطأ أثناء توليد التحليل الذكي. يرجى المحاولة لاحقاً."

    def _build_analysis_prompts(
        self,
        *,
        chat_logs: str,
        missions: dict[str, object],
        stats: dict[str, object],
        intent: object,
    ) -> tuple[str, str]:
        base_data = (
            "بيانات الطالب:\n"
            f"1) سجلات المحادثة (آخر ~60 رسالة):\n{chat_logs}\n\n"
            f"2) سجل المهام التعليمية:\n{missions}\n\n"
            f"3) إحصاءات الأداء:\n{stats}\n"
        )

        if intent == ChatIntent.LEARNING_SUMMARY:
            system_prompt = (
                "أنت Overmind، محلل تعليمي فائق التطور.\n"
                "مهمتك: تقديم ملخص عميق ومهني لكل ما تعلمه الطالب حتى الآن، "
                "مع تحليل معرفي وسلوكي يوضح تطور الفهم، الخرائط المفاهيمية، "
                "ونقاط التحول في طريقة التفكير.\n\n"
                "متطلبات الإخراج:\n"
                "- لغة عربية احترافية دقيقة.\n"
                "- تحليل متعدد الطبقات (مفاهيم، مهارات، أنماط تفكير، تطبيقات).\n"
                "- إبراز ما تم اكتسابه وما يزال يحتاج تثبيتاً.\n"
                "- اقتراح 3 خطوات متقدمة مبنية على الدليل.\n"
                "- استخدم Markdown بعناوين واضحة وقوائم منظمة.\n\n"
                f"{base_data}"
            )
            user_prompt = "قدّم ملخصاً تحليلياً عميقاً لكل ما تعلمته حتى الآن."
            return system_prompt, user_prompt

        system_prompt = (
            "أنت Overmind، المرشد الأكاديمي العبقري.\n"
            "هدفك تحليل تاريخ تفاعل الطالب بالكامل لتقديم تشخيص معرفي وأكاديمي عميق.\n"
            "لا تكتفِ بعرض الأرقام، بل حلّل المحتوى والأسئلة والسياق.\n\n"
            "متطلبات الإخراج:\n"
            "- نبرة احترافية مشجعة وبصيرة عالية.\n"
            "- تحليل طريقة التفكير ونمط الاستيعاب.\n"
            "- مواءمة التقدم مع خارطة منهج قياسية.\n"
            "- تحديد نقاط الضعف المفاهيمية الحقيقية.\n"
            "- خطة عمل بثلاث خطوات محددة.\n"
            "- تنسيق Markdown بعناوين ورموز تعبيرية.\n\n"
            f"{base_data}"
        )
        user_prompt = "حلل أدائي الدراسي بناءً على كل ما تعرفه عني."
        return system_prompt, user_prompt
