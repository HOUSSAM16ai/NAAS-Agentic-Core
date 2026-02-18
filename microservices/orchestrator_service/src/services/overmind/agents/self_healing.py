"""
الوكيل ذاتي الإصلاح (Self-Healing Agent).
==========================================

يتعلم من أخطائه ويكيّف استراتيجيته تلقائياً.
مدمج مع:
- LangGraph: للتنسيق بين الوكلاء
- Kagent: لتنفيذ إجراءات الإصلاح

المعايير:
- CS50 2025: توثيق عربي
- SICP: Abstraction Barriers
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import ClassVar, TypeVar

from pydantic import BaseModel, Field

# استبدال الاستدعاء المباشر بتكاملات المشروع
try:
    from app.services.mcp.integrations import MCPIntegrations
except ImportError:
    MCPIntegrations = None  # Mock or fallback

logger = logging.getLogger(__name__)

T = TypeVar("T")


class FailureType(StrEnum):
    """أنواع الفشل."""

    TIMEOUT = "timeout"
    VALIDATION = "validation"
    API_ERROR = "api_error"
    LOGIC_ERROR = "logic_error"
    RESOURCE_ERROR = "resource_error"
    UNKNOWN = "unknown"
    AGENT_ERROR = "agent_error"  # فشل وكيل Kagent


class FailurePattern(BaseModel):
    """نمط فشل معروف."""

    pattern_id: str = Field(..., description="معرف النمط")
    failure_type: FailureType
    error_signature: str = Field(..., description="توقيع الخطأ")
    occurrence_count: int = Field(0)
    last_occurrence: datetime | None = None
    recovery_strategy: str = Field("", description="استراتيجية التعافي")
    success_rate: float = Field(0.0, description="معدل نجاح التعافي")


class HealingAction(BaseModel):
    """إجراء إصلاحي."""

    action_type: str
    parameters: dict[str, object] = Field(default_factory=dict)
    description: str = ""
    # دعم Kagent
    kagent_capability: str | None = None  # القدرة المطلوبة من Kagent


@dataclass
class FailureAnalysis:
    """تحليل الفشل."""

    failure_type: FailureType
    error_message: str
    root_cause: str
    suggested_actions: list[HealingAction] = field(default_factory=list)
    confidence: float = 0.0


class SelfHealingAgent:
    """
    وكيل يتعلم من أخطائه باستخدام LangGraph و Kagent.

    الاستراتيجية:
    1. يحلل الخطأ ويحدد نوعه
    2. يبحث عن أنماط مشابهة في الذاكرة
    3. يختار أفضل استراتيجية للإصلاح (محلياً أو عبر Kagent)
    4. ينفذ مع تعديل المعاملات
    5. يسجل النتيجة لتحسين المستقبل
    """

    # استراتيجيات التعافي الافتراضية
    DEFAULT_STRATEGIES: ClassVar[dict[FailureType, list[HealingAction]]] = {
        FailureType.TIMEOUT: [
            HealingAction(
                action_type="increase_timeout",
                parameters={"multiplier": 2.0},
                description="زيادة المهلة الزمنية",
            ),
            HealingAction(
                action_type="retry",
                parameters={"max_retries": 3, "delay_seconds": 1},
                description="إعادة المحاولة مع تأخير",
            ),
        ],
        FailureType.VALIDATION: [
            HealingAction(
                action_type="relax_validation",
                parameters={"strict": False},
                description="تخفيف شروط التحقق",
            ),
            HealingAction(
                action_type="kagent_fix_format",
                parameters={},
                description="طلب إصلاح التنسيق من Kagent",
                kagent_capability="formatter",
            ),
        ],
        FailureType.API_ERROR: [
            HealingAction(
                action_type="switch_model",
                parameters={"fallback_model": "gpt-3.5-turbo"},
                description="التبديل لنموذج بديل",
            ),
            HealingAction(
                action_type="retry_with_backoff",
                parameters={"base_delay": 2, "max_retries": 5},
                description="إعادة المحاولة مع تأخير تصاعدي",
            ),
        ],
        FailureType.LOGIC_ERROR: [
            HealingAction(
                action_type="simplify_prompt",
                parameters={"max_tokens": 1000},
                description="تبسيط الـ prompt",
            ),
            HealingAction(
                action_type="dspy_refine",
                parameters={},
                description="تحسين الطلب باستخدام DSPy",
            ),
        ],
        FailureType.RESOURCE_ERROR: [
            HealingAction(
                action_type="reduce_load",
                parameters={"batch_size": 1},
                description="تقليل الحمل",
            ),
        ],
        FailureType.AGENT_ERROR: [
            HealingAction(
                action_type="restart_agent",
                parameters={},
                description="إعادة تشغيل الوكيل عبر Kagent",
                kagent_capability="orchestration",
            ),
        ],
    }

    def __init__(self) -> None:
        self.failure_patterns: dict[str, FailurePattern] = {}
        self.recovery_history: list[dict[str, object]] = []
        self.mcp = MCPIntegrations() if MCPIntegrations else None

    def analyze_failure(self, error: Exception) -> FailureAnalysis:
        """يحلل الخطأ ويحدد نوعه والأسباب المحتملة."""
        error_msg = str(error)
        error_type = type(error).__name__

        failure_type = self._classify_failure(error_msg, error_type)
        root_cause = self._identify_root_cause(error_msg, failure_type)
        actions = self._suggest_healing_actions(failure_type, error_msg)
        confidence = self._calculate_confidence(failure_type, error_msg)

        analysis = FailureAnalysis(
            failure_type=failure_type,
            error_message=error_msg,
            root_cause=root_cause,
            suggested_actions=actions,
            confidence=confidence,
        )

        logger.info(
            f"Failure analyzed: type={failure_type.value}, "
            f"confidence={confidence:.0%}, actions={len(actions)}"
        )

        return analysis

    def _classify_failure(self, error_msg: str, error_type: str) -> FailureType:
        """يصنف نوع الفشل."""
        msg_lower = error_msg.lower()

        if "agent" in msg_lower and ("failed" in msg_lower or "died" in msg_lower):
            return FailureType.AGENT_ERROR

        if "timeout" in msg_lower or "timed out" in msg_lower:
            return FailureType.TIMEOUT

        if "validation" in msg_lower or "invalid" in msg_lower or "pydantic" in error_type.lower():
            return FailureType.VALIDATION

        if any(x in msg_lower for x in ["api", "rate limit", "quota", "openai", "connection"]):
            return FailureType.API_ERROR

        if any(x in msg_lower for x in ["memory", "resource", "disk", "cpu"]):
            return FailureType.RESOURCE_ERROR

        if any(x in msg_lower for x in ["key", "index", "type", "attribute"]):
            return FailureType.LOGIC_ERROR

        return FailureType.UNKNOWN

    def _identify_root_cause(self, error_msg: str, failure_type: FailureType) -> str:
        """يحدد السبب الجذري."""
        causes = {
            FailureType.TIMEOUT: "العملية استغرقت وقتاً أطول من المتوقع",
            FailureType.VALIDATION: "البيانات لا تتطابق مع التنسيق المتوقع",
            FailureType.API_ERROR: "مشكلة في الاتصال بالخدمة الخارجية",
            FailureType.LOGIC_ERROR: "خطأ في المنطق أو البيانات",
            FailureType.RESOURCE_ERROR: "نقص في الموارد المتاحة",
            FailureType.AGENT_ERROR: "فشل في وكيل فرعي (Kagent/LangGraph)",
            FailureType.UNKNOWN: "سبب غير محدد",
        }
        return causes.get(failure_type, causes[FailureType.UNKNOWN])

    def _suggest_healing_actions(
        self,
        failure_type: FailureType,
        error_msg: str,
    ) -> list[HealingAction]:
        """يقترح إجراءات الإصلاح."""

        # البحث عن أنماط سابقة ناجحة
        pattern = self._find_similar_pattern(error_msg)
        if pattern and pattern.success_rate > 0.7:
            return [
                HealingAction(
                    action_type="use_learned_strategy",
                    parameters={"strategy": pattern.recovery_strategy},
                    description=f"استخدام استراتيجية ناجحة سابقاً ({pattern.success_rate:.0%})",
                )
            ]

        # استخدام الاستراتيجيات الافتراضية
        return self.DEFAULT_STRATEGIES.get(failure_type, [])

    def _find_similar_pattern(self, error_msg: str) -> FailurePattern | None:
        """يبحث عن نمط فشل مشابه."""
        error_sig = self._generate_error_signature(error_msg)
        for pattern in self.failure_patterns.values():
            if pattern.error_signature == error_sig:
                return pattern
        return None

    def _generate_error_signature(self, error_msg: str) -> str:
        """يولّد توقيع فريد للخطأ."""
        import re

        signature = re.sub(r"\d+", "N", error_msg)
        signature = re.sub(r"'.*?'", "'X'", signature)
        return signature[:100]

    def _calculate_confidence(self, failure_type: FailureType, error_msg: str) -> float:
        """يحسب مستوى الثقة في التحليل."""
        base_confidence = {
            FailureType.TIMEOUT: 0.9,
            FailureType.VALIDATION: 0.85,
            FailureType.API_ERROR: 0.8,
            FailureType.LOGIC_ERROR: 0.7,
            FailureType.RESOURCE_ERROR: 0.75,
            FailureType.AGENT_ERROR: 0.85,
            FailureType.UNKNOWN: 0.3,
        }
        confidence = base_confidence.get(failure_type, 0.5)
        if self._find_similar_pattern(error_msg):
            confidence = min(1.0, confidence + 0.1)
        return confidence

    async def execute_with_healing(
        self,
        func: Callable[..., T],
        *args: object,
        max_attempts: int = 3,
        **kwargs: object,
    ) -> T:
        """
        ينفذ دالة مع إصلاح تلقائي باستخدام قدرات المشروع كاملة.
        """
        last_error: Exception | None = None
        current_kwargs = kwargs.copy()

        for attempt in range(max_attempts):
            try:
                logger.info(f"Attempt {attempt + 1}/{max_attempts}")

                if hasattr(func, "__await__"):
                    result = await func(*args, **current_kwargs)
                else:
                    result = func(*args, **current_kwargs)

                self._record_success(last_error, current_kwargs)
                return result

            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed: {e}")

                analysis = self.analyze_failure(e)

                if analysis.suggested_actions and attempt < max_attempts - 1:
                    action = analysis.suggested_actions[0]

                    # تنفيذ الإجراء عبر Kagent أو دمج التقنيات
                    try:
                        current_kwargs = await self._apply_advanced_healing(
                            action, current_kwargs, str(e)
                        )
                        logger.info(f"Applied healing: {action.description}")
                    except Exception as healing_err:
                        logger.error(f"Healing failed: {healing_err}")
                        # محاولة متابعة بسيطة إذا فشل الإصلاح المتقدم
                        pass

        self._record_failure(last_error)
        raise last_error  # type: ignore

    async def _apply_advanced_healing(
        self,
        action: HealingAction,
        kwargs: dict[str, object],
        error_context: str,
    ) -> dict[str, object]:
        """يطبق إصلاح متقدم باستخدام تقنيات المشروع."""

        new_kwargs = kwargs.copy()

        # 1. استخدام DSPy للتحسين
        if action.action_type == "dspy_refine" and self.mcp:
            prompt = kwargs.get("prompt", "") or kwargs.get("query", "")
            if prompt:
                refined = await self.mcp.refine_query(prompt)
                if refined.get("success"):
                    key = "prompt" if "prompt" in new_kwargs else "query"
                    new_kwargs[key] = refined.get("refined_query")
                    logger.info("Refined prompt using DSPy")
                    return new_kwargs

        # 2. استخدام Kagent للإصلاح
        if action.kagent_capability and self.mcp:
            result = await self.mcp.execute_action(
                action=action.action_type,
                capability=action.kagent_capability,
                payload={"error": error_context, "input": str(kwargs)},
            )
            if result.get("success") and result.get("result"):
                # دمج النتيجة المصححة
                try:
                    import json

                    fixed_params = result["result"]
                    if isinstance(fixed_params, str):
                        fixed_params = json.loads(fixed_params)
                    new_kwargs.update(fixed_params)
                    logger.info("Fixed parameters using Kagent")
                    return new_kwargs
                except Exception:
                    pass

        # 3. استخدام الاستراتيجيات المحلية (Fallback)
        return self._apply_local_healing(action, new_kwargs)

    def _apply_local_healing(
        self,
        action: HealingAction,
        kwargs: dict[str, object],
    ) -> dict[str, object]:
        """يطبق الإجراء محلياً (بدون خدمات خارجية)."""

        if action.action_type == "increase_timeout":
            if "timeout" in kwargs:
                kwargs["timeout"] *= action.parameters.get("multiplier", 2.0)

        elif action.action_type == "relax_validation":
            kwargs["strict"] = False

        elif action.action_type == "switch_model":
            kwargs["model"] = action.parameters.get("fallback_model")

        elif action.action_type == "simplify_prompt" and "max_tokens" in action.parameters:
            kwargs["max_tokens"] = action.parameters["max_tokens"]

        kwargs.update(action.parameters)
        return kwargs

    def _record_success(self, error: Exception | None, kwargs: dict[str, object]) -> None:
        """يسجل النجاح للتعلم."""
        if error is None:
            return

        error_sig = self._generate_error_signature(str(error))

        if error_sig in self.failure_patterns:
            pattern = self.failure_patterns[error_sig]
            pattern.success_rate = (pattern.success_rate * pattern.occurrence_count + 1) / (
                pattern.occurrence_count + 1
            )
            pattern.recovery_strategy = str(kwargs)
        else:
            self.failure_patterns[error_sig] = FailurePattern(
                pattern_id=f"pat_{len(self.failure_patterns)}",
                failure_type=self._classify_failure(str(error), type(error).__name__),
                error_signature=error_sig,
                occurrence_count=1,
                last_occurrence=datetime.now(),
                recovery_strategy=str(kwargs),
                success_rate=1.0,
            )

        logger.info(f"Recorded successful recovery for pattern: {error_sig[:50]}")

    def get_healing_stats(self) -> dict[str, object]:
        """
        إحصائيات الإصلاح الذاتي (للوحة تحكم الأدمن).

        Returns:
            dict: {
                "total_patterns": int,
                "total_failures": int,
                "success_rate": float,
                "top_patterns": list[dict],
            }
        """
        total_attempts = sum(p.occurrence_count for p in self.failure_patterns.values())
        if not total_attempts:
            return {
                "total_patterns": 0,
                "total_failures": 0,
                "success_rate": 0.0,
                "top_patterns": [],
            }

        # حساب معدل النجاح العام (Weighted Average)
        weighted_success = sum(
            p.success_rate * p.occurrence_count for p in self.failure_patterns.values()
        )
        overall_rate = weighted_success / total_attempts if total_attempts > 0 else 0.0

        # أهم الأنماط (الأكثر تكراراً)
        sorted_patterns = sorted(
            self.failure_patterns.values(), key=lambda p: p.occurrence_count, reverse=True
        )

        return {
            "total_patterns": len(self.failure_patterns),
            "total_failures": total_attempts,
            "success_rate": round(overall_rate, 2),
            "top_patterns": [
                {
                    "type": p.failure_type,
                    "count": p.occurrence_count,
                    "success": f"{p.success_rate:.0%}",
                    "strategy": p.recovery_strategy[:50] + "..." if p.recovery_strategy else "None",
                }
                for p in sorted_patterns[:5]
            ],
        }

    def _record_failure(self, error: Exception | None) -> None:
        """يسجل الفشل للتعلم."""
        if error is None:
            return

        error_sig = self._generate_error_signature(str(error))

        if error_sig in self.failure_patterns:
            pattern = self.failure_patterns[error_sig]
            pattern.success_rate = (pattern.success_rate * pattern.occurrence_count) / (
                pattern.occurrence_count + 1
            )
            pattern.occurrence_count += 1
            pattern.last_occurrence = datetime.now()
        else:
            self.failure_patterns[error_sig] = FailurePattern(
                pattern_id=f"pat_{len(self.failure_patterns)}",
                failure_type=self._classify_failure(str(error), type(error).__name__),
                error_signature=error_sig,
                occurrence_count=1,
                last_occurrence=datetime.now(),
                success_rate=0.0,
            )

        logger.warning(f"Recorded failure for pattern: {error_sig[:50]}")


# Singleton
_healing_agent: SelfHealingAgent | None = None


def get_self_healing_agent() -> SelfHealingAgent:
    """يحصل على الوكيل ذاتي الإصلاح."""
    global _healing_agent
    if _healing_agent is None:
        _healing_agent = SelfHealingAgent()
    return _healing_agent
