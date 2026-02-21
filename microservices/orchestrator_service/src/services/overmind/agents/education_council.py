"""
Unified Education Council.
"""

from __future__ import annotations

from dataclasses import dataclass

from microservices.orchestrator_service.src.services.overmind.agents.base import (
    FORMAL_ARABIC_STYLE_PROMPT,
)
from microservices.orchestrator_service.src.services.overmind.utils.tools import ToolRegistry


@dataclass(frozen=True, slots=True)
class EducationQualityCharter:
    title: str
    pillars: tuple[str, ...]
    promises: tuple[str, ...]

    def render(self) -> str:
        lines = [f"{self.title}:"]
        lines.extend([f"- {pillar}" for pillar in self.pillars])
        lines.append("وعود الجودة:")
        lines.extend([f"- {promise}" for promise in self.promises])
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class EducationResponseRubric:
    phases: tuple[str, ...]
    quality_checks: tuple[str, ...]

    def render(self) -> str:
        lines = ["معيار الردود التعليمية:"]
        lines.append("مراحل الإجابة:")
        lines.extend([f"- {phase}" for phase in self.phases])
        lines.append("فحوص الجودة:")
        lines.extend([f"- {check}" for check in self.quality_checks])
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class EducationBrief:
    charter: EducationQualityCharter
    student_summary: tuple[str, ...]
    learning_curve: tuple[str, ...]
    guardrails: tuple[str, ...]
    rubric: EducationResponseRubric
    focus_directives: tuple[str, ...]

    def render(self) -> str:
        sections: list[str] = [self.charter.render(), self.rubric.render()]

        if self.focus_directives:
            sections.append("\nبوصلة التخصيص والتوجيه:")
            sections.extend([f"- {line}" for line in self.focus_directives])

        if self.student_summary:
            sections.append("\nملف الطالب المختصر:")
            sections.extend([f"- {line}" for line in self.student_summary])

        if self.learning_curve:
            sections.append("\nمنحنى التعلم:")
            sections.extend([f"- {line}" for line in self.learning_curve])

        if self.guardrails:
            sections.append("\nضوابط الجودة والانضباط:")
            sections.extend([f"- {line}" for line in self.guardrails])

        return "\n".join(sections)


class EducationCouncil:
    def __init__(self, tools: ToolRegistry) -> None:
        self.tools = tools

    async def build_brief(self, *, context: dict[str, object]) -> EducationBrief:
        charter = self._build_quality_charter()
        rubric = self._build_response_rubric()
        guardrails = self._build_guardrails()
        focus_directives = self._build_focus_directives(context)
        student_summary: tuple[str, ...] = ()
        learning_curve: tuple[str, ...] = ()

        user_id = context.get("user_id")
        if isinstance(user_id, int):
            student_summary = await self._build_student_summary(user_id)
            learning_curve = await self._build_learning_curve(user_id)

        return EducationBrief(
            charter=charter,
            student_summary=student_summary,
            learning_curve=learning_curve,
            guardrails=guardrails,
            rubric=rubric,
            focus_directives=focus_directives,
        )

    def _build_quality_charter(self) -> EducationQualityCharter:
        return EducationQualityCharter(
            title="ميثاق الجودة الهندسية للتعليم (Engineering-Grade Learning Charter)",
            pillars=(
                "الوضوح العميق القائم على تعريفات دقيقة ومنهجية (Specification-based Clarity).",
                "التخصيص وفق ملف الطالب مع الالتزام بالصرامة الأكاديمية.",
                "التركيز على المنهجية والتفكير المنطقي (Algorithmic Reasoning) قبل الإجابة النهائية.",
                "بناء المعرفة كبنية تراكمية (Incremental Construction) قابلة للتحقق.",
                "التغذية الراجعة التشخيصية المبنية على أدلة (Evidence-based Feedback).",
            ),
            promises=(
                "الالتزام الكامل بمعايير الصياغة الهندسية (كما هو محدد في المواصفة).",
                "عدم الاكتفاء بالنتيجة دون شرح آلية التفكير والتحقق.",
                "تقديم أمثلة معيارية لتثبيت المفاهيم.",
                f"الالتزام بـ: {FORMAL_ARABIC_STYLE_PROMPT}",
            ),
        )

    def _build_guardrails(self) -> tuple[str, ...]:
        return (
            "عدم اختلاق تمارين أو امتحانات رسمية غير موثقة.",
            "اعتماد السياق المتاح وعدم تجاوز حدود المعرفة المقدمة.",
            "الحفاظ على نبرة محترفة داعمة ومحفزة.",
            "التصريح عند نقص البيانات والاقتراح بخطوات بديلة.",
        )

    def _build_response_rubric(self) -> EducationResponseRubric:
        return EducationResponseRubric(
            phases=(
                "تلخيص الهدف التعليمي بلغة الطالب.",
                "شرح المفهوم الأساسي بصورة متدرجة.",
                "تحويل الشرح إلى خطوات منهجية قابلة للتطبيق.",
                "تثبيت الفهم بسؤال قصير أو تمرين موجّه.",
                "خاتمة محفزة تشير للخطوة التالية.",
            ),
            quality_checks=(
                "الوضوح بدون حشو أو تعقيد زائد.",
                "عدم تقديم الحل النهائي إن كان تمرينًا تقييميًا.",
                "تطابق النبرة مع مستوى الطالب واحتياجاته.",
                "ربط المفهوم بالتطبيق الواقعي أو الأكاديمي.",
            ),
        )

    def _build_focus_directives(self, context: dict[str, object]) -> tuple[str, ...]:
        focus: list[str] = []
        intent = context.get("intent")
        if intent is not None:
            focus.append(f"نية التفاعل الحالية: {intent}")
        intent_type = context.get("intent_type")
        if isinstance(intent_type, str) and intent_type:
            focus.append(f"مسار التخصيص: {intent_type}")
        difficulty = context.get("difficulty")
        if isinstance(difficulty, str) and difficulty:
            focus.append(f"تفضيل الصعوبة: {difficulty}")
        language = context.get("language")
        if isinstance(language, str) and language:
            focus.append(f"لغة الشرح المفضلة: {language}")
        experience_tier = context.get("experience_tier")
        if isinstance(experience_tier, str) and experience_tier:
            focus.append(f"مستوى التجربة المطلوبة: {experience_tier}")
        if not focus:
            focus.append("اعتمد على سياق السؤال لبناء أفضل توجيه ممكن.")
        focus.append("احرص على تقديم تجربة تعليمية راقية ومنظمة بأعلى مستوى من الدقة.")
        return tuple(focus)

    async def _build_student_summary(self, user_id: int) -> tuple[str, ...]:
        try:
            payload = await self.tools.execute(
                "fetch_comprehensive_student_history",
                {"user_id": user_id},
            )
        except Exception:
            return ()

        if not isinstance(payload, dict):
            return ()

        stats = payload.get("profile_stats")
        missions = payload.get("missions_summary")
        profile = self._derive_learning_profile(stats, missions)
        summary_lines = self._format_profile_summary(stats, missions, profile)
        return tuple(summary_lines)

    async def _build_learning_curve(self, user_id: int) -> tuple[str, ...]:
        try:
            payload = await self.tools.execute(
                "analyze_learning_curve",
                {"user_id": user_id},
            )
        except Exception:
            return ()

        if not isinstance(payload, dict):
            return ()

        status = payload.get("status")
        if isinstance(status, str) and status == "no_data":
            return ("لا توجد بيانات كافية لرسم منحنى التعلم حالياً.",)

        lines: list[str] = []
        total_completed = payload.get("total_completed")
        if isinstance(total_completed, int):
            lines.append(f"عدد المهام المكتملة: {total_completed}")
        last_active_date = payload.get("last_active_date")
        if isinstance(last_active_date, str) and last_active_date:
            lines.append(f"آخر نشاط مسجل: {last_active_date}")
        trend = payload.get("trend")
        if isinstance(trend, str) and trend:
            lines.append(f"اتجاه التعلم: {trend}")
        consistency = payload.get("consistency_score")
        if isinstance(consistency, str) and consistency:
            lines.append(f"مؤشر الثبات: {consistency}")

        return tuple(lines)

    def _derive_learning_profile(
        self,
        stats: object,
        missions: object,
    ) -> dict[str, str]:
        level = "متوسط"
        tone = "مشجع"
        pacing = "متوازن"

        if isinstance(stats, dict):
            total_missions = stats.get("total_missions")
            completed_missions = stats.get("completed_missions")
            failed_missions = stats.get("failed_missions")
            total_messages = stats.get("total_chat_messages")

            if isinstance(total_missions, int) and total_missions <= 1:
                level = "مبتدئ"
                pacing = "بطيء مع خطوات واضحة"
            if (
                isinstance(completed_missions, int)
                and isinstance(total_missions, int)
                and total_missions > 0
            ):
                completion_ratio = completed_missions / total_missions
                if completion_ratio >= 0.75:
                    level = "متقدم"
                    pacing = "سريع مع تحديات إضافية"
            if isinstance(failed_missions, int) and failed_missions >= 2:
                tone = "داعِم مع إعادة تبسيط"
                pacing = "متدرج مع أمثلة إضافية"
            if isinstance(total_messages, int) and total_messages < 5:
                tone = "ترحيبي وهادئ"

        focus = "الربط بين الفكرة والخطوات العملية"
        if isinstance(missions, dict):
            topics = missions.get("topics")
            if isinstance(topics, list):
                topic_list = [topic for topic in topics if isinstance(topic, str)]
                if topic_list:
                    focus = f"ربط الشرح بمواضيع الطالب الحديثة مثل: {', '.join(topic_list[:3])}"

        return {
            "level": level,
            "tone": tone,
            "pacing": pacing,
            "focus": focus,
        }

    def _format_profile_summary(
        self,
        stats: object,
        missions: object,
        profile: dict[str, str],
    ) -> list[str]:
        lines: list[str] = [
            f"مستوى تقريبي: {profile['level']}",
            f"أسلوب الشرح: {profile['tone']}، بإيقاع {profile['pacing']}",
            f"محور التركيز: {profile['focus']}",
        ]

        if isinstance(stats, dict):
            total_missions = stats.get("total_missions")
            completed_missions = stats.get("completed_missions")
            failed_missions = stats.get("failed_missions")
            total_messages = stats.get("total_chat_messages")
            last_activity = stats.get("last_activity")
            if isinstance(total_missions, int):
                lines.append(f"إجمالي المهام: {total_missions}")
            if isinstance(completed_missions, int):
                lines.append(f"المهام المكتملة: {completed_missions}")
            if isinstance(failed_missions, int):
                lines.append(f"المهام غير المكتملة: {failed_missions}")
            if isinstance(total_messages, int):
                lines.append(f"إجمالي رسائل التعلم: {total_messages}")
            if isinstance(last_activity, str) and last_activity:
                lines.append(f"آخر نشاط: {last_activity}")

        if isinstance(missions, dict):
            topics = missions.get("topics")
            recent = missions.get("recent_missions")
            if isinstance(topics, list):
                topic_list = [topic for topic in topics if isinstance(topic, str)]
                if topic_list:
                    lines.append(f"مواضيع حديثة: {', '.join(topic_list[:6])}")
            if isinstance(recent, list) and recent:
                latest = recent[0]
                if isinstance(latest, dict):
                    title = latest.get("title")
                    status = latest.get("status")
                    if isinstance(title, str) and isinstance(status, str):
                        lines.append(f"آخر مهمة: {title} ({status})")

        return lines
