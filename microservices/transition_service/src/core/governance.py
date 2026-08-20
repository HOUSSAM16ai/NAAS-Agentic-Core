"""طبقة الحوكمة — نموذج القرار من أربعة مستويات (دستور المشروع، القسم 5).

قواعد هذه الطبقة **مشفّرة تحديداً لا قابلة للتجاوز** بأي وكيل داخل الخدمة:
1. المستوى الأول — معلوماتي: توصيات واستشهادات، التنفيذ بيد الإنسان دائماً.
2. المستوى الثاني — مساند: مساعدات تنفيذية بشفافية كاملة وسجل قرار، التنفيذ بيد الإنسان.
3. المستوى الثالث — تنفيذي منخفض المخاطر: تنفيذ مباشر فقط داخل نطاقات مسموحة
   صراحةً (قوالب تعليم، توليد تقارير، تحديث لوائح داخلية) وبسقف زمني ومالي.
4. المستوى الرابع — عالي المخاطر: **مرفوض تلقائياً** (استبعاد أشخاص، فصل،
   رفض توظيف، تعديل أجور، قرارات مالية فردية) — يُحوَّل حصراً إلى لجنة حوكمة بشرية.

مبدأ التوثيق: كل قرار يُسجَّل في سجل حوكمة (decision log) قابل للتدقيق، وهو ما
تتطلبه الممارسة الرصينة للتدقيق الخوارزمي (EU AI Act Art. 6 & 14 — employment
high-risk obligations، OECD AI Recommendation 2019) ووثيقة المشروع §6.

هذه الطبقة حتمية (deterministic): لا LLM يقرر مستوى الخطورة — يُصنَّف من
مفاتيح القرار الصريحة، ويُستدعى المحرك اللغوي فقط للتبرير والسرد.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field

ALLOWED_LOW_RISK_ACTIONS: frozenset[str] = frozenset(
    {
        "generate_training_template",
        "generate_report",
        "update_internal_rules",
        "schedule_review_meeting",
        "publish_benchmark_summary",
        "send_training_enrollment_form",
    }
)

MAX_LOW_RISK_ACTION_DURATION_DAYS: int = 90
MAX_LOW_RISK_ACTION_BUDGET: float = 5_000_000.0  # سقف نقدي نسبي لوحدات النقد المحلية

HIGH_RISK_TRIGGER_WORDS: tuple[str, ...] = (
    "استبعاد",
    "فصل",
    "رفض",
    "رفض التوظيف",
    "خفض الأجر",
    "إيقاف خدمة",
    "تعديل الراتب",
    "termination",
    "rejection",
    "salary reduction",
    "dismissal",
    "individual financial decision",
)


class DecisionLevel(enum.IntEnum):
    """مستويات القرار الأربعة — الوثيقة §5 طبقة الحوكمة."""

    INFORMATIVE = 1  # معلوماتي: توصية فقط
    ASSISTIVE = 2  # مساند: تنفيذ مساعد بشفافية
    LOW_RISK_EXEC = 3  # تنفيذي منخفض المخاطر (مسموح فقط ضمن ALLOWED_LOW_RISK_ACTIONS)
    HIGH_RISK_REJECT = 4  # عالي المخاطر: رفض تلقائي وتحويل للجنة بشرية


@dataclass(frozen=True)
class GovernanceDecision:
    level: DecisionLevel
    allowed: bool
    reason: str
    human_oversight_required: bool
    human_action_description: str


def classify_decision(action_key: str, description: str) -> GovernanceDecision:
    """تصنيف حتمي لمستوى الخطورة — لا LLM هنا."""
    description_lower = description.lower()
    if any(word in description_lower for word in HIGH_RISK_TRIGGER_WORDS):
        return GovernanceDecision(
            level=DecisionLevel.HIGH_RISK_REJECT,
            allowed=False,
            reason="قرار عالي المخاطر — يخص مصيراً فردياً (عمل/دخل)؛ يتطلب لجنة حوكمة بشرية حصراً (وثيقة المشروع §5، EU AI Act Art.6 employment)",
            human_oversight_required=True,
            human_action_description="يُحوَّل إلى لجنة الحوكمة البشرية مع سجل كامل للأدلة والنطاق الزمني والسكان المتأثرين",
        )
    if action_key in ALLOWED_LOW_RISK_ACTIONS:
        return GovernanceDecision(
            level=DecisionLevel.LOW_RISK_EXEC,
            allowed=True,
            reason="إجراء ضمن القوالب المنخفضة المخاطر المسماة صراحةً، بتنفيذ مباشر وبسقف زمني ومالي",
            human_oversight_required=False,
            human_action_description="لا يتطلب إشرافاً مباشراً — يُدوَّن في سجل الحوكمة فقط",
        )
    if (
        "assist" in action_key.lower()
        or "help" in action_key.lower()
        or "translate" in action_key.lower()
    ):
        return GovernanceDecision(
            level=DecisionLevel.ASSISTIVE,
            allowed=True,
            reason="مساندة تنفيذية — تبقى صلاحيات التنفيذ النهائية للإنسان مع سجل قرار شفاف",
            human_oversight_required=True,
            human_action_description="مراجعة بشرية قبل اعتماد المخرج النهائي",
        )
    return GovernanceDecision(
        level=DecisionLevel.INFORMATIVE,
        allowed=True,
        reason="توصية معلوماتية — التنفيذ والتبني قرار بشري بحت",
        human_oversight_required=False,
        human_action_description="لا تنفيذ آلي — قرار بشري بحت",
    )


@dataclass
class DecisionLogEntry:
    """سجل حوكمة قابل للتدقيق — كل وكيل ملزم بالتسجيل هنا قبل أي مخرج."""

    request_id: str
    agent: str
    action_key: str
    description: str
    decision: GovernanceDecision
    timestamp: float = field(default_factory=time.time)
    outcome: str = "logged"  # logged | executed | rejected_by_board

    def to_dict(self) -> dict[str, object]:
        return {
            "request_id": self.request_id,
            "agent": self.agent,
            "action_key": self.action_key,
            "description": self.description,
            "decision_level": self.decision.level.name,
            "allowed": self.decision.allowed,
            "reason": self.decision.reason,
            "timestamp": self.timestamp,
            "outcome": self.outcome,
        }


class DecisionLog:
    """سجل حوكمة مركزي داخل الخدمة — يُغذَّي من كل الوكلاء ويقرأ من وكيل التقييم."""

    def __init__(self) -> None:
        self._entries: list[DecisionLogEntry] = []

    def log(self, entry: DecisionLogEntry) -> DecisionLogEntry:
        self._entries.append(entry)
        return entry

    def entries(self) -> list[DecisionLogEntry]:
        return list(self._entries)

    def rejected_count(self) -> int:
        return sum(1 for e in self._entries if not e.decision.allowed)

    def entries_by_agent(self, agent: str) -> list[DecisionLogEntry]:
        return [e for e in self._entries if e.agent == agent]

    def export_row(self) -> list[dict[str, object]]:
        """تصدير السجل كصفوف قابلة للتدقيق — يقرأها وكيل التقييم والمراجعات الخارجية."""
        return [entry.to_dict() for entry in self._entries]

    def clear(self) -> None:  # للاختبارات فقط
        self._entries.clear()


GOVERNANCE_LOG = DecisionLog()
