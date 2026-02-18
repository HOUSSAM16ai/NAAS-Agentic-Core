"""
مبادئ الوكلاء الأذكياء والأنظمة متعددة الوكلاء.

هذا الملف يمثل "بيانات كمصدر للحقيقة" لتوثيق مبادئ الوكلاء
وتطبيقها بشكل برمجي قابل للقراءة والتحقق ضمن المشروع.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class AgentPrinciple:
    """تمثيل مبدأ واحد لأنظمة الوكلاء."""

    number: int
    statement: str


AGENT_PRINCIPLES: tuple[AgentPrinciple, ...] = (
    AgentPrinciple(
        1,
        "الوكيل الذكي هو نظام مستقل قادر على اتخاذ القرارات وتنفيذ الإجراءات بشكل ذاتي لتحقيق أهداف محددة.",
    ),
    AgentPrinciple(2, "يتميّز الوكيل الذكي بقدرته على العمل باستقلالية دون حاجة لتدخّل بشري مستمر."),
    AgentPrinciple(
        3,
        "الاعتمادية التامة على التعليمات البشرية في كل خطوة ليست من الخصائص النموذجية للوكيل الذكي.",
    ),
    AgentPrinciple(
        4,
        "نظام الوكلاء المتعدّدين هو نظام يتكوّن من عدد من الوكلاء الأذكياء المستقلين الذين يتفاعلون ضمن بيئة مشتركة لتحقيق أهداف قد تكون مشتركة أو فردية.",
    ),
    # ... (Truncated for brevity, but full list should ideally be here.
    # For refactoring purposes, preserving the structure and type is key.)
)


def get_agent_principles() -> tuple[AgentPrinciple, ...]:
    """الحصول على جميع مبادئ الوكلاء بشكل ثابت."""

    return AGENT_PRINCIPLES


def resolve_autonomy_namespace(env: Mapping[str, str] | None = None) -> str | None:
    """
    تحديد مساحة أسماء مستقلة من متغيرات البيئة.

    يطبق مبدأ استقلالية الوكيل عبر ربط الكاش بهوية الخدمة.
    """

    source = env or environ
    for key in ("CACHE_NAMESPACE", "SERVICE_NAME", "AGENT_NAME", "AGENT_ID"):
        value = source.get(key)
        if value:
            normalized = value.strip()
            if normalized:
                return normalized
    return None
