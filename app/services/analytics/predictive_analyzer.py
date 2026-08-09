"""
المحلل التنبؤي (Predictive Analyzer).
=====================================

يتنبأ بنقاط ضعف الطالب قبل ظهورها.
"""

import logging
from typing import ClassVar

from pydantic import BaseModel, Field

from app.services.learning.student_profile import StudentProfile, get_student_profile

logger = logging.getLogger(__name__)


class StrugglePrediction(BaseModel):
    """تنبؤ بصعوبة مستقبلية."""

    topic_id: str
    topic_name: str
    probability: float = Field(..., ge=0.0, le=1.0, description="احتمال الصعوبة")
    confidence: float = Field(..., ge=0.0, le=1.0, description="مستوى الثقة")
    warning_signs: list[str]
    prevention_tips: list[str]


class PredictiveAnalyzer:
    """
    يحلل أنماط الطالب ويتنبأ بالصعوبات المستقبلية.

    المميزات:
    - كشف علامات الإنذار المبكر
    - تحليل أنماط الأخطاء
    - اقتراحات وقائية
    """

    # علامات الإنذار المبكر
    WARNING_SIGNS: ClassVar = {
        "declining_accuracy": "انخفاض الدقة في آخر 5 محاولات",
        "long_gaps": "فترات طويلة بدون ممارسة",
        "repeated_errors": "تكرار نفس الأخطاء",
        "skipping_steps": "تخطي خطوات الحل",
        "quick_surrender": "الاستسلام السريع",
    }

    async def predict_struggles(
        self,
        student_id: int,
    ) -> list[StrugglePrediction]:
        """
        يتنبأ بالمواضيع التي قد يواجه فيها الطالب صعوبة.
        """
        profile = await get_student_profile(student_id)
        predictions = []

        for topic_id, tm in profile.topic_mastery.items():
            # تحليل علامات الإنذار
            warning_signs = self._detect_warning_signs(profile, topic_id)

            if not warning_signs:
                continue

            # حساب احتمال الصعوبة
            probability = self._calculate_struggle_probability(tm, warning_signs)

            if probability < 0.3:  # تجاهل الاحتمالات الصغيرة
                continue

            # اقتراحات وقائية
            tips = self._generate_prevention_tips(topic_id, warning_signs)

            predictions.append(
                StrugglePrediction(
                    topic_id=topic_id,
                    topic_name=tm.topic_name,
                    probability=probability,
                    confidence=0.7,  # ثقة متوسطة
                    warning_signs=[self.WARNING_SIGNS.get(s, s) for s in warning_signs],
                    prevention_tips=tips,
                )
            )

        # ترتيب حسب الاحتمال
        predictions.sort(key=lambda p: p.probability, reverse=True)

        logger.info(f"Predicted {len(predictions)} potential struggles for student {student_id}")

        return predictions

    def _detect_warning_signs(
        self,
        profile: StudentProfile,
        topic_id: str,
    ) -> list[str]:
        """يكشف علامات الإنذار."""

        signs = []
        tm = profile.topic_mastery.get(topic_id)

        if not tm:
            return signs

        # 1. انخفاض الدقة
        recent_events = [e for e in profile.learning_history[-20:] if e.topic_id == topic_id]

        if len(recent_events) >= 5:
            recent_correct = sum(1 for e in recent_events[-5:] if e.event_type == "correct")
            older_correct = sum(1 for e in recent_events[:-5] if e.event_type == "correct")

            if recent_correct < older_correct * 0.7:
                signs.append("declining_accuracy")

        # 2. فترات طويلة بدون ممارسة
        from datetime import datetime

        if tm.last_practiced:
            days_since = (datetime.now() - tm.last_practiced).days
            if days_since > 14:
                signs.append("long_gaps")

        # 3. إتقان منخفض
        if tm.mastery_score < 0.4:
            signs.append("repeated_errors")

        return signs

    def _calculate_struggle_probability(
        self,
        tm,
        warning_signs: list[str],
    ) -> float:
        """يحسب احتمال الصعوبة."""

        base_prob = 1 - tm.mastery_score  # كلما قل الإتقان زاد الاحتمال

        # زيادة حسب عدد علامات الإنذار
        sign_factor = min(0.3, len(warning_signs) * 0.1)

        return min(1.0, base_prob + sign_factor)

    def _generate_prevention_tips(
        self,
        topic_id: str,
        warning_signs: list[str],
    ) -> list[str]:
        """يولّد نصائح وقائية."""

        tips = []

        if "declining_accuracy" in warning_signs:
            tips.append("راجع الأساسيات قبل المتابعة")

        if "long_gaps" in warning_signs:
            tips.append("حاول الممارسة يومياً ولو 10 دقائق")

        if "repeated_errors" in warning_signs:
            tips.append("حلل أخطاءك السابقة وافهم أسبابها")

        if not tips:
            tips.append("استمر في الممارسة المنتظمة")

        return tips

    async def get_risk_report(self, student_id: int) -> dict:
        """يولّد تقرير مخاطر شامل."""

        predictions = await self.predict_struggles(student_id)
        profile = await get_student_profile(student_id)

        high_risk = [p for p in predictions if p.probability >= 0.7]
        medium_risk = [p for p in predictions if 0.4 <= p.probability < 0.7]

        return {
            "student_id": student_id,
            "overall_risk": "high" if high_risk else ("medium" if medium_risk else "low"),
            "high_risk_topics": [p.topic_name for p in high_risk],
            "medium_risk_topics": [p.topic_name for p in medium_risk],
            "predictions": [p.model_dump() for p in predictions[:5]],
            "recommended_focus": profile.weaknesses[:3],
        }


# Singleton
_analyzer: PredictiveAnalyzer | None = None


def get_predictive_analyzer() -> PredictiveAnalyzer:
    """يحصل على المحلل التنبؤي."""
    global _analyzer
    if _analyzer is None:
        _analyzer = PredictiveAnalyzer()
    return _analyzer
