"""
Curriculum Agent (Ported).
"""

from collections.abc import AsyncGenerator

from microservices.orchestrator_service.src.core.logging import get_logger
from microservices.orchestrator_service.src.services.overmind.utils.tools import ToolRegistry

logger = get_logger("curriculum-agent")


class CurriculumAgent:
    """
    Instructional Designer Agent.
    """

    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def process(self, context: dict[str, object]) -> AsyncGenerator[str, None]:
        logger.info("Curriculum agent started processing")

        intent_type = context.get("intent_type", "recommendation")
        user_id = context.get("user_id")
        user_message = context.get("user_message", "")

        if not user_id:
            yield "عذراً، أحتاج لمعرفة هويتك لتقديم توصيات مناسبة."
            return

        if (
            "خطة" in str(user_message)
            or "plan" in str(user_message).lower()
            or "roadmap" in str(user_message).lower()
            or "ابدأ" in str(user_message)
        ):
            async for chunk in self._handle_study_plan(int(user_id), str(user_message)):
                yield chunk
        elif intent_type == "path_progress":
            yield await self._handle_path_progress(int(user_id))
        elif intent_type == "difficulty_adjust":
            yield await self._handle_difficulty_adjustment(
                int(user_id), str(context.get("feedback", "good"))
            )
        else:
            async for chunk in self._handle_recommendation(int(user_id)):
                yield chunk

    async def _handle_study_plan(
        self, user_id: int, request_text: str
    ) -> AsyncGenerator[str, None]:
        yield "🗺️ **جارٍ إعداد خريطتك الدراسية المخصصة...**\n"

        try:
            structure = await self.tools.execute("get_curriculum_structure", {})
        except Exception as e:
            logger.error(f"Error fetching curriculum structure: {e}")
            yield "حدث خطأ أثناء استرجاع المناهج المتاحة."
            return

        if not structure:
            yield "للاسف، لا يوجد محتوى تعليمي متاح حالياً في النظام لبناء خطة."
            return

        response_lines = ["### 🎓 الخطة الدراسية المقترحة\n"]
        response_lines.append(f"بناءً على طلبك: '{request_text}'، إليك المسار التعليمي المتاح:\n")

        for subject, levels in structure.items():
            response_lines.append(f"#### 📚 مادة: {subject}")
            for level, packs in levels.items():
                response_lines.append(f"**المستوى: {level}**")
                for pack_name, lessons in packs.items():
                    response_lines.append(f"- 📦 **{pack_name}**")
                    for i, lesson in enumerate(lessons):
                        title = lesson["title"]
                        l_id = lesson["id"]
                        response_lines.append(f"  - {i + 1}. {title} `[عرض: {l_id}]`")
            response_lines.append("\n---\n")

        response_lines.append(
            "\n💡 **نصيحة:** يمكنك نسخ كود الدرس (مثلاً `ex:101`) وطلبه مباشرة، أو قل 'ابدأ الدرس الأول'."
        )

        yield "\n".join(response_lines)

    async def _handle_recommendation(self, user_id: int) -> AsyncGenerator[str, None]:
        yield "🤔 **أبحث لك عن التحدي الأنسب لمستواك الحالي...**\n"

        try:
            mission = await self.tools.execute("recommend_next_mission", {"user_id": user_id})
        except Exception:
            # Fallback if tool is missing
            mission = None

        if not mission:
            yield "لم أتمكن من العثور على توصية محددة حالياً. يمكنك تصفح المناهج المتاحة."
            return

        yield (
            f"### 🎯 اقتراح المهمة القادمة\n"
            f"**العنوان:** {mission.get('title')}\n\n"
            f"**الوصف:** {mission.get('description')}\n\n"
            f"**السبب:** {mission.get('reason')}\n\n"
            f"هل تود البدء بهذه المهمة؟ (اكتب 'ابدأ' للتنفيذ)"
        )

    async def _handle_path_progress(self, user_id: int) -> str:
        try:
            progress = await self.tools.execute("get_learning_path_progress", {"user_id": user_id})
        except Exception:
            progress = None

        if not progress:
            return "تعذر جلب بيانات المسار."

        achievements = progress.get("recent_achievements", [])
        achievements_text = (
            "\n".join([f"- {a}" for a in achievements])
            if achievements
            else "لا توجد إنجازات مسجلة بعد."
        )

        return (
            f"## 🗺️ خارطة طريقك التعليمية\n"
            f"- **المرحلة الحالية:** {progress.get('current_stage')}\n"
            f"- **نسبة الإنجاز الكلية:** {progress.get('progress_percentage')}%\n"
            f"- **عدد المهام المنجزة:** {progress.get('completed_count')}\n"
            f"\n### 🏆 آخر الإنجازات:\n{achievements_text}"
        )

    async def _handle_difficulty_adjustment(self, user_id: int, feedback: str) -> str:
        try:
            result = await self.tools.execute(
                "adjust_difficulty_level", {"user_id": user_id, "feedback": feedback}
            )
            return f"✅ {result}"
        except Exception:
            return "حدث خطأ أثناء تعديل الإعدادات."
