"""
Predictive Analytics Application Service
ML-based risk prediction and trend analysis
"""

import statistics

from microservices.observability_service.security_metrics.domain.models import (
    RiskPrediction,
    SecurityMetrics,
    TrendDirection,
)
from microservices.observability_service.security_metrics.domain.ports import (
    PredictiveAnalyticsPort,
)


class LinearRegressionPredictor(PredictiveAnalyticsPort):
    """
    Predictive analytics using linear regression
    Inspired by: Google's Predictive Security, AWS GuardDuty ML
    """

    def predict_future_risk(
        self, historical_metrics: list[SecurityMetrics], days_ahead: int = 30
    ) -> RiskPrediction:
        """
        التنبؤ بالمخاطر المستقبلية | Predict future risk using linear regression

        يستخدم الانحدار الخطي للتنبؤ بمستوى المخاطر
        Uses linear regression to predict risk level

        Args:
            historical_metrics: مقاييس تاريخية | Historical metrics
            days_ahead: أيام للتنبؤ | Days to predict ahead

        Returns:
            توقع المخاطر | Risk prediction
        """
        if len(historical_metrics) < 7:
            return self._create_insufficient_data_prediction()

        risk_scores = [m.overall_risk_score for m in historical_metrics[-30:]]
        slope, intercept = self._calculate_linear_regression(risk_scores)
        predicted_risk = self._predict_risk_value(slope, intercept, len(risk_scores), days_ahead)
        confidence = self._calculate_prediction_confidence(risk_scores, slope, intercept)
        trend = self._determine_trend(slope)

        return RiskPrediction(
            predicted_risk=round(predicted_risk, 2),
            confidence=round(confidence, 2),
            trend=trend,
            slope=round(slope, 4),
            current_risk=risk_scores[-1],
        )

    def _create_insufficient_data_prediction(self) -> RiskPrediction:
        """
        إنشاء توقع للبيانات غير الكافية | Create prediction for insufficient data

        Returns:
            توقع مخاطر افتراضي | Default risk prediction
        """
        return RiskPrediction(
            predicted_risk=0.0,
            confidence=0.0,
            trend=TrendDirection.STABLE,
            slope=0.0,
            current_risk=0.0,
        )

    def _calculate_linear_regression(self, risk_scores: list[float]) -> tuple[float, float]:
        """
        حساب الانحدار الخطي | Calculate linear regression

        Args:
            risk_scores: قيم المخاطر | Risk scores

        Returns:
            (الميل، نقطة التقاطع) | (slope, intercept)
        """
        n = len(risk_scores)
        x = list(range(n))
        y = risk_scores

        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        slope = 0 if denominator == 0 else numerator / denominator
        intercept = y_mean - slope * x_mean

        return slope, intercept

    def _predict_risk_value(self, slope: float, intercept: float, n: int, days_ahead: int) -> float:
        """
        حساب قيمة المخاطر المتوقعة | Calculate predicted risk value

        Args:
            slope: الميل | Slope
            intercept: نقطة التقاطع | Intercept
            n: عدد نقاط البيانات | Number of data points
            days_ahead: أيام للتنبؤ | Days ahead

        Returns:
            قيمة المخاطر المتوقعة (0-100) | Predicted risk value (0-100)
        """
        future_x = n + days_ahead
        predicted_risk = slope * future_x + intercept
        return max(0, min(100, predicted_risk))

    def _calculate_prediction_confidence(
        self, risk_scores: list[float], slope: float, intercept: float
    ) -> float:
        """
        حساب مستوى الثقة بالتنبؤ | Calculate prediction confidence

        يستخدم R-squared لقياس جودة الملاءمة
        Uses R-squared to measure goodness of fit

        Args:
            risk_scores: قيم المخاطر | Risk scores
            slope: الميل | Slope
            intercept: نقطة التقاطع | Intercept

        Returns:
            مستوى الثقة (0-100) | Confidence level (0-100)
        """
        n = len(risk_scores)
        x = list(range(n))
        y = risk_scores
        y_mean = statistics.mean(y)

        ss_total = sum((y[i] - y_mean) ** 2 for i in range(n))
        ss_residual = sum((y[i] - (slope * x[i] + intercept)) ** 2 for i in range(n))

        r_squared = 0 if ss_total == 0 else 1 - ss_residual / ss_total
        return max(0, min(100, r_squared * 100))

    def _determine_trend(self, slope: float) -> TrendDirection:
        """Determine trend direction from slope"""
        if slope > 0.5:
            return TrendDirection.DEGRADING
        if slope < -0.5:
            return TrendDirection.IMPROVING
        return TrendDirection.STABLE
