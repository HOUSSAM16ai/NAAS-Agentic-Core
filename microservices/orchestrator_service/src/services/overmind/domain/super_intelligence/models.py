"""
نماذج البيانات لخاصة بنظام الذكاء الجماعي الفائق.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class DecisionPriority(StrEnum):
    """
    أولوية القرار (Decision Priority).

    تحدد مدى إلحاح وأهمية القرار.
    """

    CRITICAL = "critical"  # حرج - تأثير فوري على النظام
    HIGH = "high"  # عالي - يحتاج اتخاذ قرار سريع
    MEDIUM = "medium"  # متوسط - يمكن التأجيل قليلاً
    LOW = "low"  # منخفض - ليس عاجلاً
    STRATEGIC = "strategic"  # استراتيجي - للمستقبل البعيد


class DecisionCategory(StrEnum):
    """
    فئة القرار (Decision Category).

    تصنف نوع القرار المطلوب اتخاذه.
    """

    TECHNICAL = "technical"  # تقني - يتعلق بالكود والبنية
    ARCHITECTURAL = "architectural"  # معماري - تصميم النظام
    STRATEGIC = "strategic"  # استراتيجي - الاتجاه العام
    OPERATIONAL = "operational"  # تشغيلي - العمليات اليومية
    RESOURCE_ALLOCATION = "resource"  # تخصيص الموارد
    RISK_MANAGEMENT = "risk"  # إدارة المخاطر
    INNOVATION = "innovation"  # الابتكار والتطوير
    HUMAN_BENEFIT = "human_benefit"  # فائدة البشرية


class DecisionImpact(StrEnum):
    """
    تأثير القرار (Decision Impact).

    يقيس مدى تأثير القرار على المدى البعيد.
    """

    IMMEDIATE = "immediate"  # فوري - أقل من يوم
    SHORT_TERM = "short_term"  # قصير المدى - أسبوع إلى شهر
    MEDIUM_TERM = "medium_term"  # متوسط المدى - شهر إلى سنة
    LONG_TERM = "long_term"  # طويل المدى - سنة إلى 5 سنوات
    GENERATIONAL = "generational"  # جيلي - أكثر من 5 سنوات


class Decision(BaseModel):
    """
    قرار ذكي مستقل (Intelligent Autonomous Decision).

    يمثل قراراً اتخذه الوكلاء بشكل مستقل مع كل التفاصيل.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: DecisionCategory
    priority: DecisionPriority
    impact: DecisionImpact
    title: str
    description: str
    reasoning: str
    agents_involved: list[str]

    # البيانات الإضافية
    alternatives_considered: list[dict[str, object]] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    risks: list[dict[str, object]] = Field(default_factory=list)
    mitigation_strategies: list[str] = Field(default_factory=list)
    execution_plan: dict[str, object] = Field(default_factory=dict)
    success_criteria: list[str] = Field(default_factory=list)

    # المقاييس
    confidence_score: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # الحالة
    approved: bool = False
    executed: bool = False
    outcome: str | None = None

    def to_dict(self) -> dict[str, object]:
        """
        تحويل القرار إلى dictionary (للتوافق مع الكود القديم).
        """
        return self.model_dump()

    def calculate_confidence(self) -> float:
        """
        حساب درجة الثقة في القرار.

        Returns:
            float: درجة الثقة (0-100)
        """
        score = 50.0  # نقطة البداية

        # التنوع
        score += len(self.agents_involved) * 10

        # الشمولية
        score += len(self.alternatives_considered) * 5

        # الوضوح
        score += min(len(self.reasoning) / 100, 10)

        # الوعي
        score += len(self.risks) * 5

        self.confidence_score = min(score, 100.0)
        return self.confidence_score
